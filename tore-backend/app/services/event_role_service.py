"""Event role resolution extracted from the legacy runtime."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from db import now_utc
from models import Event, EventStaff, OrganizationMembership


_STRUCTURE_AUTH_ROLES = {"OWNER", "PRESIDENT", "BUREAU", "TRESORIER", "MANAGER", "STAFF"}


def _role_rank(role: str) -> int:
    if role == "admin":
        return 3
    if role == "entry":
        return 2
    return 1


def _active_membership(
    db: Session,
    *,
    organization_id: int,
    user_id: str,
) -> OrganizationMembership | None:
    now = now_utc()
    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == "ACTIVE",
            OrganizationMembership.revoked_at.is_(None),
            or_(OrganizationMembership.starts_at.is_(None), OrganizationMembership.starts_at <= now),
            or_(OrganizationMembership.ends_at.is_(None), OrganizationMembership.ends_at > now),
        )
        .first()
    )


def resolve_event_role(db: Session, user_id: str, event_id: int) -> str:
    event = db.get(Event, event_id)
    if event is None or (event.ends_at is not None and event.ends_at <= now_utc()):
        return "guest"
    if event.host_type == "user" and event.host_id == user_id:
        return "admin"
    if event.host_type == "orga" and str(event.host_id or "").isdigit():
        membership = _active_membership(
            db,
            organization_id=int(event.host_id),
            user_id=user_id,
        )
        if membership is not None and (membership.role or "").upper() in _STRUCTURE_AUTH_ROLES:
            return "admin"

    staff = (
        db.query(EventStaff)
        .filter(EventStaff.event_id == event_id, EventStaff.user_id == user_id)
        .first()
    )
    if (
        staff is None
        or staff.is_active is False
        or staff.revoked_at is not None
        or (staff.expires_at is not None and staff.expires_at <= now_utc())
    ):
        return "guest"

    role = (staff.role or "").lower()
    if role in {"admin", "manager"}:
        return "admin"
    if role == "entry":
        return "entry"
    return "guest"


def require_role_for_event(
    db: Session,
    user_id: str,
    event_id: int,
    required_role: str,
) -> str:
    granted = resolve_event_role(db, user_id, event_id)
    if _role_rank(granted) < _role_rank(required_role):
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "required_role": required_role},
        )
    return granted


__all__ = ["_role_rank", "resolve_event_role", "require_role_for_event"]
