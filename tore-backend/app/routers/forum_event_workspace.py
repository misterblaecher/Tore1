"""Rich Forum event workspace built on the existing TORÈ event model.

This router is intentionally additive: it does not replace the historical
``/forum`` contract and it does not require a schema migration.  Rich fields
which have no dedicated legacy column are kept in a namespaced ``rules_flags``
object so existing event consumers continue to see their data unchanged.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import now_utc
from models import (
    AppUser,
    Event,
    EventRuntimeState,
    EventStaffAssignment,
    StructureAlbum,
    StructureDocument,
)
from app.core.security.user_auth import get_current_user
from app.deps.db import get_db
from app.routers.forum import (
    _save_idem,
    _structure_or_404,
    _verify_event_scope,
    _write_idem,
)
from app.services.audit_service import write_audit_log
from app.services.structure_rbac import require_capability


router = APIRouter(prefix="/forum", tags=["forum-events"])

LIFECYCLE = (
    "DRAFT",
    "PUBLISHED",
    "SYNCED_TO_APP",
    "LIVE",
    "CLOSED",
    "RECAP_DRAFT",
    "RECAP_PUBLISHED",
    "ARCHIVED",
)

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"PUBLISHED"},
    "PUBLISHED": {"DRAFT", "SYNCED_TO_APP"},
    "SYNCED_TO_APP": {"PUBLISHED", "LIVE"},
    "LIVE": {"CLOSED"},
    "CLOSED": {"RECAP_DRAFT", "ARCHIVED"},
    "RECAP_DRAFT": {"CLOSED", "RECAP_PUBLISHED"},
    "RECAP_PUBLISHED": {"RECAP_DRAFT", "ARCHIVED"},
    "ARCHIVED": set(),
}


class EventWorkspaceCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    starts_at: datetime
    ends_at: datetime
    venue: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=10000)
    visibility: Literal["PUBLIC", "PRIVATE"] = "PRIVATE"
    publication_status: Literal["DRAFT", "PUBLISHED"] = "DRAFT"
    entry_price_cents: int = Field(default=0, ge=0, le=100000)
    capacity: Optional[int] = Field(default=None, ge=1, le=100000)
    banner_url: Optional[str] = Field(default=None, max_length=1000)
    modules: list[str] = Field(default_factory=list, max_length=32)
    co_organizers: list[str] = Field(default_factory=list, max_length=20)
    recap: str = Field(default="", max_length=20000)


class EventWorkspacePatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    venue: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=10000)
    visibility: Optional[Literal["PUBLIC", "PRIVATE"]] = None
    publication_status: Optional[Literal["DRAFT", "PUBLISHED"]] = None
    entry_price_cents: Optional[int] = Field(default=None, ge=0, le=100000)
    capacity: Optional[int] = Field(default=None, ge=1, le=100000)
    banner_url: Optional[str] = Field(default=None, max_length=1000)
    modules: Optional[list[str]] = Field(default=None, max_length=32)
    co_organizers: Optional[list[str]] = Field(default=None, max_length=20)
    recap: Optional[str] = Field(default=None, max_length=20000)
    lifecycle_status: Optional[Literal[
        "DRAFT", "PUBLISHED", "SYNCED_TO_APP", "LIVE", "CLOSED",
        "RECAP_DRAFT", "RECAP_PUBLISHED", "ARCHIVED"
    ]] = None


def _forum_meta(event: Event) -> dict[str, Any]:
    flags = event.rules_flags if isinstance(event.rules_flags, dict) else {}
    value = flags.get("forum")
    return dict(value) if isinstance(value, dict) else {}


def _set_forum_meta(event: Event, **changes: Any) -> None:
    flags = dict(event.rules_flags) if isinstance(event.rules_flags, dict) else {}
    meta = dict(flags.get("forum")) if isinstance(flags.get("forum"), dict) else {}
    meta.update(changes)
    flags["forum"] = meta
    event.rules_flags = flags


def _module_names(event: Event) -> list[str]:
    raw = event.modules_on
    if isinstance(raw, dict):
        return sorted(str(key) for key, enabled in raw.items() if enabled)
    if isinstance(raw, list):
        return sorted(str(value) for value in raw)
    return []


def _set_modules(event: Event, modules: list[str]) -> None:
    normalized = []
    seen: set[str] = set()
    for value in modules:
        item = value.strip().lower().replace(" ", "_")[:64]
        if item and item not in seen:
            seen.add(item)
            normalized.append(item)
    event.modules_on = {item: True for item in normalized}


def _current_lifecycle(event: Event) -> str:
    meta = _forum_meta(event)
    value = str(meta.get("lifecycle_status") or "").upper()
    if value in LIFECYCLE:
        return value
    if (event.publication_status or "DRAFT").upper() == "PUBLISHED":
        return "PUBLISHED"
    return "DRAFT"


def _set_lifecycle(event: Event, next_status: str, *, force: bool = False) -> None:
    current = _current_lifecycle(event)
    if not force and next_status != current and next_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=409,
            detail={"reason": "INVALID_EVENT_TRANSITION", "from": current, "to": next_status},
        )

    _set_forum_meta(event, lifecycle_status=next_status)
    if next_status == "DRAFT":
        event.publication_status = "DRAFT"
    elif next_status in {"PUBLISHED", "SYNCED_TO_APP", "LIVE", "CLOSED", "RECAP_DRAFT", "RECAP_PUBLISHED", "ARCHIVED"}:
        event.publication_status = "PUBLISHED"


def _sync_runtime_state(db: Session, event: Event, lifecycle: str) -> None:
    runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event.id).first()
    runtime_state = "LIVE" if lifecycle == "LIVE" else "ARCHIVED" if lifecycle == "ARCHIVED" else "CLOSED" if lifecycle in {"CLOSED", "RECAP_DRAFT", "RECAP_PUBLISHED"} else "DRAFT"
    if runtime is None:
        db.add(EventRuntimeState(event_id=event.id, state=runtime_state, updated_at=now_utc()))
    else:
        runtime.state = runtime_state
        runtime.updated_at = now_utc()


def _event_counts(db: Session, organization_id: int, event_id: int) -> tuple[int, int, Optional[int]]:
    document_count = int(db.scalar(
        select(func.count()).select_from(StructureDocument).where(
            StructureDocument.organization_id == organization_id,
            StructureDocument.event_id == event_id,
            StructureDocument.archived_at.is_(None),
        )
    ) or 0)
    staff_count = int(db.scalar(
        select(func.count()).select_from(EventStaffAssignment).where(
            EventStaffAssignment.event_id == event_id,
            EventStaffAssignment.revoked_at.is_(None),
        )
    ) or 0)
    album = db.query(StructureAlbum).filter(
        StructureAlbum.organization_id == organization_id,
        StructureAlbum.event_id == event_id,
        StructureAlbum.archived_at.is_(None),
    ).order_by(StructureAlbum.id.desc()).first()
    return document_count, staff_count, album.id if album else None


def _workspace_payload(db: Session, organization_id: int, event: Event) -> dict[str, Any]:
    meta = _forum_meta(event)
    document_count, staff_count, album_id = _event_counts(db, organization_id, event.id)
    lifecycle = _current_lifecycle(event)
    return {
        "id": event.id,
        "name": event.name,
        "startsAt": event.starts_at.isoformat() if event.starts_at else None,
        "endsAt": event.ends_at.isoformat() if event.ends_at else None,
        "venue": event.venue,
        "city": event.city,
        "description": event.public_description,
        "visibility": (event.visibility or "PRIVATE").upper(),
        "publicationStatus": (event.publication_status or "DRAFT").upper(),
        "entryPriceCents": event.entry_price_cents,
        "capacity": event.capacity,
        "coverUrl": event.banner_url,
        "modules": _module_names(event),
        "coOrganizers": [str(value) for value in meta.get("co_organizers", []) if str(value).strip()],
        "recap": str(meta.get("recap") or ""),
        "lifecycleStatus": lifecycle,
        "appSyncStatus": "SYNCED" if lifecycle in {"SYNCED_TO_APP", "LIVE", "CLOSED", "RECAP_DRAFT", "RECAP_PUBLISHED", "ARCHIVED"} else "NOT_SYNCED",
        "staffCount": staff_count,
        "documentCount": document_count,
        "albumId": album_id,
    }


def _apply_patch(event: Event, payload: EventWorkspacePatchIn) -> None:
    # The workspace form always includes its initial visibility value. If an
    # already-public event is edited later, that stale PRIVATE value must not
    # silently unpublish it during an ordinary content save. Publication and
    # lifecycle transitions below remain the explicit source of truth.
    stale_private_visibility = (
        (event.visibility or "PRIVATE").upper() == "PUBLIC"
        and payload.visibility == "PRIVATE"
        and payload.publication_status is None
        and payload.lifecycle_status is None
    )
    if payload.name is not None:
        event.name = payload.name.strip()
    if payload.starts_at is not None:
        event.starts_at = payload.starts_at.replace(tzinfo=None)
    if payload.ends_at is not None:
        event.ends_at = payload.ends_at.replace(tzinfo=None)
    if event.ends_at <= event.starts_at:
        raise HTTPException(status_code=400, detail={"reason": "INVALID_EVENT_DATES"})
    if payload.venue is not None:
        event.venue = payload.venue.strip() or None
    if payload.city is not None:
        event.city = payload.city.strip() or None
    if payload.description is not None:
        event.public_description = payload.description
    if payload.visibility is not None and not stale_private_visibility:
        event.visibility = payload.visibility
    if payload.publication_status is not None:
        event.publication_status = payload.publication_status
        event.visibility = "PUBLIC" if payload.publication_status == "PUBLISHED" else "PRIVATE"
        if payload.lifecycle_status is None:
            _set_forum_meta(event, lifecycle_status="PUBLISHED" if payload.publication_status == "PUBLISHED" else "DRAFT")
    if payload.entry_price_cents is not None:
        event.entry_price_cents = payload.entry_price_cents
    if payload.capacity is not None:
        event.capacity = payload.capacity
    if payload.banner_url is not None:
        event.banner_url = payload.banner_url.strip() or None
    if payload.modules is not None:
        _set_modules(event, payload.modules)
    meta_changes: dict[str, Any] = {}
    if payload.co_organizers is not None:
        meta_changes["co_organizers"] = [value.strip() for value in payload.co_organizers if value.strip()][:20]
    if payload.recap is not None:
        meta_changes["recap"] = payload.recap
    if meta_changes:
        _set_forum_meta(event, **meta_changes)
    if payload.lifecycle_status is not None:
        _set_lifecycle(event, payload.lifecycle_status)
        event.visibility = "PUBLIC" if payload.lifecycle_status != "DRAFT" else "PRIVATE"
    event.last_updated_at = now_utc()


@router.get("/structures/{slug}/event-workspace")
def list_event_workspace(
    slug: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    require_capability(db, org.id, user, "event.read")
    events = db.query(Event).filter(
        Event.host_type == "orga",
        Event.host_id == str(org.id),
    ).order_by(Event.starts_at.asc(), Event.id.asc()).all()
    return {"items": [_workspace_payload(db, org.id, event) for event in events]}


@router.post("/structures/{slug}/event-workspace")
def create_event_workspace(
    slug: str,
    payload: EventWorkspaceCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    org = _structure_or_404(db, slug)
    actor = require_capability(db, org.id, user, "event.create")
    if payload.publication_status == "PUBLISHED":
        require_capability(db, org.id, user, "event.publish")
    action_key = f"forum_event_workspace_create:{org.id}"
    key, previous = _write_idem(db, user, action_key, idempotency_key)
    if previous is not None:
        return previous
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=400, detail={"reason": "INVALID_EVENT_DATES"})

    event = Event(
        host_type="orga",
        host_id=str(org.id),
        host_display_name=org.name,
        name=payload.name.strip(),
        starts_at=payload.starts_at.replace(tzinfo=None),
        ends_at=payload.ends_at.replace(tzinfo=None),
        venue=payload.venue,
        city=payload.city or org.city,
        public_description=payload.description,
        visibility=payload.visibility,
        publication_status=payload.publication_status,
        entry_price_cents=payload.entry_price_cents,
        capacity=payload.capacity,
        banner_url=payload.banner_url,
        created_by=f"app:{user.id}",
        last_state_updated_at=now_utc(),
        last_updated_at=now_utc(),
    )
    _set_modules(event, payload.modules)
    _set_forum_meta(
        event,
        co_organizers=[value.strip() for value in payload.co_organizers if value.strip()][:20],
        recap=payload.recap,
        lifecycle_status="PUBLISHED" if payload.publication_status == "PUBLISHED" else "DRAFT",
    )
    db.add(event)
    db.flush()
    _sync_runtime_state(db, event, _current_lifecycle(event))
    response = _workspace_payload(db, org.id, event)
    _save_idem(db, user, action_key, key, response)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="forum.event.workspace.create",
        entity_type="event",
        entity_id=str(event.id),
        event_id=event.id,
        committee_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={"structure_id": org.id, "publication_status": event.publication_status, "visibility": event.visibility},
    )
    db.commit()
    return response


@router.patch("/structures/{slug}/event-workspace/{event_id}")
def patch_event_workspace(
    slug: str,
    event_id: int,
    payload: EventWorkspacePatchIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    org = _structure_or_404(db, slug)
    actor = require_capability(db, org.id, user, "event.manage")
    if payload.publication_status is not None or payload.lifecycle_status == "PUBLISHED":
        require_capability(db, org.id, user, "event.publish")
    event = _verify_event_scope(db, org.id, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    action_key = f"forum_event_workspace_patch:{event_id}"
    key, previous = _write_idem(db, user, action_key, idempotency_key)
    if previous is not None:
        return previous

    _apply_patch(event, payload)
    _sync_runtime_state(db, event, _current_lifecycle(event))
    response = _workspace_payload(db, org.id, event)
    _save_idem(db, user, action_key, key, response)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="forum.event.workspace.patch",
        entity_type="event",
        entity_id=str(event.id),
        event_id=event.id,
        committee_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={
            "structure_id": org.id,
            "publication_status": event.publication_status,
            "visibility": event.visibility,
            "lifecycle_status": _current_lifecycle(event),
        },
    )
    db.commit()
    return response
