from __future__ import annotations

from typing import Any, Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from db import now_utc
from models import AppUser, Event, EventStructure, Organization, OrganizationMembership
from app.services.structure_rbac import capabilities_for_membership


COHOST_PERMISSION_FIELDS = {
    "edit": "can_edit",
    "publish": "can_publish",
    "staff": "can_staff",
    "documents": "can_documents",
    "finance": "can_finance",
    "recap": "can_recap",
}

def active_structure_membership(
    db: Session,
    *,
    organization_id: int,
    user_id: str,
) -> Optional[OrganizationMembership]:
    stamp = now_utc()
    return db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.status == "ACTIVE",
        OrganizationMembership.revoked_at.is_(None),
        or_(OrganizationMembership.starts_at.is_(None), OrganizationMembership.starts_at <= stamp),
        or_(OrganizationMembership.ends_at.is_(None), OrganizationMembership.ends_at > stamp),
    ).first()


def ensure_owner_relation(db: Session, event: Event, *, created_by_user_id: str | None = None) -> Optional[EventStructure]:
    if event.host_type != "orga" or not str(event.host_id or "").isdigit():
        return None
    organization_id = int(str(event.host_id))
    row = db.query(EventStructure).filter(
        EventStructure.event_id == event.id,
        EventStructure.organization_id == organization_id,
    ).first()
    if row is None:
        row = EventStructure(
            event_id=event.id,
            organization_id=organization_id,
            role="OWNER",
            can_edit=True,
            can_publish=True,
            can_staff=True,
            can_documents=True,
            can_finance=True,
            can_recap=True,
            created_by_user_id=created_by_user_id,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        db.add(row)
        db.flush()
    elif (row.role or "").upper() != "OWNER":
        # The canonical host wins over an accidental legacy COHOST row.
        row.role = "OWNER"
        row.can_edit = True
        row.can_publish = True
        row.can_staff = True
        row.can_documents = True
        row.can_finance = True
        row.can_recap = True
        row.updated_at = now_utc()
        db.flush()
    return row


def _resolve_legacy_structure(db: Session, raw: Any) -> Optional[Organization]:
    if isinstance(raw, dict):
        for key in ("id", "structure_id", "organization_id"):
            value = raw.get(key)
            if value is not None and str(value).isdigit():
                found = db.get(Organization, int(value))
                if found is not None:
                    return found
        raw = raw.get("slug") or raw.get("name")
    if isinstance(raw, int) or (isinstance(raw, str) and raw.strip().isdigit()):
        return db.get(Organization, int(raw))
    if not isinstance(raw, str) or not raw.strip():
        return None
    needle = raw.strip().lower()
    return db.query(Organization).filter(
        or_(func.lower(Organization.slug) == needle, func.lower(Organization.name) == needle)
    ).first()


def migrate_legacy_cohosts_for_event(db: Session, event: Event) -> list[str]:
    """Move rules_flags.co_organizers to relation rows without privilege escalation.

    Legacy values were descriptive strings only, so migrated COHOST rows receive
    no privileged permission by default. Unresolvable values are retained under
    an explicitly legacy key for manual cleanup, never treated as authorization.
    """

    ensure_owner_relation(db, event)
    rules = dict(event.rules_flags or {}) if isinstance(event.rules_flags, dict) else {}
    raw = rules.pop("co_organizers", None)
    if raw is None:
        return []
    values: Iterable[Any] = raw if isinstance(raw, list) else [raw]
    unresolved: list[str] = []
    owner_id = int(event.host_id) if event.host_type == "orga" and str(event.host_id or "").isdigit() else None
    for value in values:
        org = _resolve_legacy_structure(db, value)
        if org is None:
            unresolved.append(str(value))
            continue
        if owner_id is not None and org.id == owner_id:
            continue
        exists = db.query(EventStructure).filter(
            EventStructure.event_id == event.id,
            EventStructure.organization_id == org.id,
        ).first()
        if exists is None:
            db.add(EventStructure(
                event_id=event.id,
                organization_id=org.id,
                role="COHOST",
                can_edit=False,
                can_publish=False,
                can_staff=False,
                can_documents=False,
                can_finance=False,
                can_recap=False,
                created_at=now_utc(),
                updated_at=now_utc(),
            ))
    if unresolved:
        rules["legacy_unresolved_co_organizers"] = unresolved
    else:
        rules.pop("legacy_unresolved_co_organizers", None)
    event.rules_flags = rules
    event.last_updated_at = now_utc()
    db.flush()
    return unresolved


def relation_permissions(row: EventStructure) -> dict[str, bool]:
    if (row.role or "COHOST").upper() == "OWNER":
        return {name: True for name in COHOST_PERMISSION_FIELDS}
    return {name: bool(getattr(row, field)) for name, field in COHOST_PERMISSION_FIELDS.items()}


def effective_permission(
    db: Session,
    relation: EventStructure,
    membership: OrganizationMembership,
    permission: str,
) -> bool:
    role = (relation.role or "COHOST").upper()
    required = {
        "read": "event.read",
        "edit": "event.manage",
        "publish": "event.publish",
        "staff": "event.manage",
        "documents": "document.manage",
        "finance": "finance.read",
        "recap": "event.recap.manage",
    }.get(permission)
    if required is None or required not in capabilities_for_membership(db, membership):
        return False
    if permission == "read":
        return True
    if permission not in COHOST_PERMISSION_FIELDS:
        return False
    # Every COHOST permission remains explicit; a local capability alone never
    # expands the relation granted by the owning Structure.
    return role == "OWNER" or bool(getattr(relation, COHOST_PERMISSION_FIELDS[permission]))


def require_structure_event_relation(
    db: Session,
    *,
    organization_id: int,
    event_id: int,
    user: AppUser,
    permission: str = "read",
) -> tuple[Event, EventStructure, OrganizationMembership]:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    migrate_legacy_cohosts_for_event(db, event)
    relation = db.query(EventStructure).filter(
        EventStructure.event_id == event_id,
        EventStructure.organization_id == organization_id,
    ).first()
    membership = active_structure_membership(
        db, organization_id=organization_id, user_id=user.id
    )
    if relation is None or membership is None or not effective_permission(db, relation, membership, permission):
        raise HTTPException(
            status_code=403,
            detail={"reason": "EVENT_COHOST_PERMISSION_DENIED", "permission": permission},
        )
    return event, relation, membership


def cohost_capability_actions(row: EventStructure) -> set[str]:
    """Translate COHOST permissions to the existing operational capability surface."""
    if (row.role or "COHOST").upper() == "OWNER":
        return {"event.view_ops", "event.manage_entry", "event.manage_staff"}
    if row.can_staff:
        return {"event.view_ops", "event.manage_staff"}
    return set()
