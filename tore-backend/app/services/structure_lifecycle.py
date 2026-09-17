from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, event, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Session, mapped_column

from db import Base, now_utc
from models import Event, Organization


STRUCTURE_LIFECYCLE_STATES = {"REQUESTED", "SETUP", "ACTIVE", "SUSPENDED", "ARCHIVED"}
STRUCTURE_LIFECYCLE_TRANSITIONS = {
    "REQUESTED": {"SETUP"},
    "SETUP": {"ACTIVE"},
    "ACTIVE": {"SUSPENDED"},
    "SUSPENDED": {"ARCHIVED"},
    "ARCHIVED": set(),
}

PRIVATE_STRUCTURE_VISIBILITY = {
    "page": "PRIVATE",
    "description": "PRIVATE",
    "contact": "PRIVATE",
    "events": "PRIVATE",
    "members": "PRIVATE",
    "albums": "PRIVATE",
    "documents": "PRIVATE",
    "folklore": "PRIVATE",
    "stats": "PRIVATE",
}


class StructureLifecycleState(Base):
    """Additive lifecycle state for Organization without changing legacy Organization contracts."""

    __tablename__ = "organization_lifecycle_states"

    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(16), default="SETUP", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


def lifecycle_status(db: Session, organization_id: int) -> str:
    row = db.get(StructureLifecycleState, organization_id)
    # Rows predating the additive lifecycle migration are historical and remain ACTIVE.
    # The Alembic migration backfills them; this fallback keeps partial/rolling deploys safe.
    return (row.status if row is not None else "ACTIVE").upper()


def ensure_lifecycle(
    db: Session,
    organization_id: int,
    *,
    initial_status: str = "SETUP",
) -> StructureLifecycleState:
    status = initial_status.strip().upper()
    if status not in STRUCTURE_LIFECYCLE_STATES:
        raise ValueError(f"Unknown structure lifecycle state: {status}")
    row = db.get(StructureLifecycleState, organization_id)
    if row is None:
        row = StructureLifecycleState(
            organization_id=organization_id,
            status=status,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        db.add(row)
        db.flush()
    return row


def validate_transition(current: str, target: str) -> tuple[str, str]:
    source = (current or "").strip().upper()
    destination = (target or "").strip().upper()
    if source not in STRUCTURE_LIFECYCLE_STATES or destination not in STRUCTURE_LIFECYCLE_STATES:
        raise ValueError("UNKNOWN_LIFECYCLE_STATE")
    if destination not in STRUCTURE_LIFECYCLE_TRANSITIONS[source]:
        raise ValueError("INVALID_LIFECYCLE_TRANSITION")
    return source, destination


def transition_lifecycle(db: Session, organization_id: int, target: str) -> tuple[str, str]:
    row = ensure_lifecycle(db, organization_id, initial_status="ACTIVE")
    source, destination = validate_transition(row.status, target)
    row.status = destination
    row.updated_at = now_utc()
    db.flush()
    return source, destination


def private_visibility_settings(existing: Optional[dict] = None) -> dict[str, str]:
    # Creation is deliberately strict: no incoming/public value can publish a block implicitly.
    return dict(PRIVATE_STRUCTURE_VISIBILITY)


def visibility_settings(org: Organization) -> dict[str, str]:
    raw = org.visibility_settings_json if isinstance(org.visibility_settings_json, dict) else {}
    # Historical rows intentionally keep the pre-lifecycle fallback values for retro-compatibility.
    historical_defaults = {
        "page": "PUBLIC",
        "description": "PUBLIC",
        "contact": "PUBLIC",
        "events": "PUBLIC",
        "members": "STRUCTURE_MEMBERS",
        "albums": "PUBLIC",
        "documents": "STRUCTURE_MEMBERS",
        "folklore": "PUBLIC",
        "stats": "ADMINS",
    }
    return {
        **historical_defaults,
        **{str(key): str(value).upper() for key, value in raw.items() if str(key) in PRIVATE_STRUCTURE_VISIBILITY},
    }


def structure_is_published(db: Session, org: Organization) -> bool:
    return (
        lifecycle_status(db, org.id) == "ACTIVE"
        and (org.visibility or "PRIVATE").upper() == "PUBLIC"
        and visibility_settings(org)["page"] == "PUBLIC"
    )


def set_page_published(org: Organization, published: bool) -> None:
    settings = visibility_settings(org)
    settings["page"] = "PUBLIC" if published else "PRIVATE"
    org.visibility_settings_json = settings
    org.visibility = "PUBLIC" if published else "PRIVATE"


def hide_structure_events(db: Session, organization_id: int) -> int:
    rows = db.query(Event).filter(
        Event.host_type == "orga",
        Event.host_id == str(organization_id),
    ).all()
    changed = 0
    for row in rows:
        if (row.visibility or "PRIVATE").upper() != "PRIVATE" or (row.publication_status or "DRAFT").upper() != "DRAFT":
            row.visibility = "PRIVATE"
            row.publication_status = "DRAFT"
            changed += 1
    return changed


def _tracked_lifecycle_from_connection(connection: Connection, organization_id: int) -> Optional[str]:
    value = connection.execute(
        select(StructureLifecycleState.__table__.c.status).where(
            StructureLifecycleState.__table__.c.organization_id == organization_id
        )
    ).scalar_one_or_none()
    return str(value).upper() if value is not None else None


def _guard_event_publication(_mapper, connection: Connection, target: Event) -> None:
    if (target.host_type or "").lower() != "orga" or not target.host_id:
        return
    try:
        organization_id = int(target.host_id)
    except (TypeError, ValueError):
        return
    status = _tracked_lifecycle_from_connection(connection, organization_id)
    # Only lifecycle-tracked structures are governed here. Missing rows are legacy fixtures or
    # rolling-deploy historical data and are handled by the migration/fallback path.
    if status is not None and status != "ACTIVE":
        target.visibility = "PRIVATE"
        target.publication_status = "DRAFT"


# DB-level safety net: no event belonging to a lifecycle-tracked non-ACTIVE structure can be
# persisted as public, regardless of which HTTP surface attempted the write.
event.listen(Event, "before_insert", _guard_event_publication, propagate=True)
event.listen(Event, "before_update", _guard_event_publication, propagate=True)
