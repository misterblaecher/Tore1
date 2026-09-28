from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from db import now_utc
from models import (
    AppUser,
    Bar,
    Event,
    EventAppWriteIdempotency,
    EventRuntimeState,
    EventStaff,
    OrganizationMembership,
    PartnerBarAccess,
    PartnerMembership,
    PartnerUser,
)
from app.services.audit_service import write_audit_log


EVENT_RUNTIME_STATES = frozenset(
    {"LIVE", "PAUSE", "MENU_ONLY", "DEGRADED", "FROZEN", "CLOSED"}
)

EVENT_ROLE_ACTIONS: dict[str, set[str]] = {
    "ADMIN": {"event.view_ops", "event.manage_entry", "event.manage_staff", "event.broadcast", "event.manage_state"},
    "MANAGER": {"event.view_ops", "event.manage_entry", "event.manage_staff", "event.broadcast", "event.manage_state"},
    "ENTRY": {"event.view_ops", "event.manage_entry"},
    "BAR": {"event.view_ops"},
    "HELPER": {"event.view_ops"},
}

BAR_ROLE_ACTIONS: dict[str, set[str]] = {
    "OWNER": {"bar.view_ops", "bar.manage_orders", "bar.manage_menu"},
    "MANAGER": {"bar.view_ops", "bar.manage_orders", "bar.manage_menu"},
    "STAFF": {"bar.view_ops", "bar.manage_orders"},
    "BARTENDER": {"bar.view_ops", "bar.manage_orders"},
    "ENTRY": {"bar.view_ops"},
}

STRUCTURE_MANAGE_ROLES = {"OWNER", "PRESIDENT", "BUREAU", "TRESORIER", "MANAGER", "STAFF"}


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _event_is_active(event: Event, at: datetime) -> bool:
    return event.ends_at is None or event.ends_at > at


def _merge_capability(target: dict[int, dict[str, Any]], candidate: dict[str, Any]) -> None:
    scope_id = int(candidate["event_id"] if candidate.get("event_id") is not None else candidate["bar_id"])
    current = target.get(scope_id)
    if current is None:
        target[scope_id] = candidate
        return
    current["actions"] = sorted(set(current["actions"]) | set(candidate["actions"]))
    current["sources"] = sorted(set(current.get("sources", [current["source"]])) | {candidate["source"]})
    if candidate.get("expires_at") and (
        not current.get("expires_at") or candidate["expires_at"] < current["expires_at"]
    ):
        current["expires_at"] = candidate["expires_at"]


def event_capabilities(db: Session, user: AppUser, *, at: Optional[datetime] = None) -> list[dict[str, Any]]:
    stamp = at or now_utc()
    merged: dict[int, dict[str, Any]] = {}

    staff_rows = (
        db.query(EventStaff, Event)
        .join(Event, Event.id == EventStaff.event_id)
        .filter(
            EventStaff.user_id == user.id,
            EventStaff.is_active == True,  # noqa: E712
            EventStaff.revoked_at.is_(None),
            or_(EventStaff.expires_at.is_(None), EventStaff.expires_at > stamp),
        )
        .all()
    )
    for staff, event in staff_rows:
        if not _event_is_active(event, stamp):
            continue
        role = (staff.role or "HELPER").upper()
        actions = sorted(EVENT_ROLE_ACTIONS.get(role, EVENT_ROLE_ACTIONS["HELPER"]))
        expires_at = staff.expires_at
        if event.ends_at and (expires_at is None or event.ends_at < expires_at):
            expires_at = event.ends_at
        _merge_capability(merged, {
            "id": f"event:{event.id}:staff:{staff.id}",
            "type": "EVENT",
            "scope": f"event:{event.id}",
            "event_id": event.id,
            "bar_id": event.bar_id,
            "organization_id": int(event.host_id) if event.host_type == "orga" and str(event.host_id or "").isdigit() else None,
            "role": role,
            "actions": actions,
            "source": "EVENT_STAFF",
            "activated_at": _iso(staff.created_at),
            "expires_at": _iso(expires_at),
            "status": "ACTIVE",
            "updated_at": _iso(staff.created_at),
            "event": {"id": event.id, "name": event.name, "state": (event.event_state or "LIVE").upper(), "starts_at": _iso(event.starts_at), "ends_at": _iso(event.ends_at)},
        })

    hosted = db.query(Event).filter(Event.host_type == "user", Event.host_id == user.id).all()
    for event in hosted:
        if not _event_is_active(event, stamp):
            continue
        _merge_capability(merged, {
            "id": f"event:{event.id}:host:{user.id}", "type": "EVENT", "scope": f"event:{event.id}",
            "event_id": event.id, "bar_id": event.bar_id, "organization_id": None, "role": "MANAGER",
            "actions": sorted(EVENT_ROLE_ACTIONS["MANAGER"]), "source": "EVENT_HOST",
            "activated_at": _iso(event.starts_at), "expires_at": _iso(event.ends_at), "status": "ACTIVE",
            "updated_at": _iso(event.last_updated_at),
            "event": {"id": event.id, "name": event.name, "state": (event.event_state or "LIVE").upper(), "starts_at": _iso(event.starts_at), "ends_at": _iso(event.ends_at)},
        })

    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.status == "ACTIVE",
        OrganizationMembership.revoked_at.is_(None),
        or_(OrganizationMembership.starts_at.is_(None), OrganizationMembership.starts_at <= stamp),
        or_(OrganizationMembership.ends_at.is_(None), OrganizationMembership.ends_at > stamp),
    ).all()
    for membership in memberships:
        role = (membership.role or "MEMBER").upper()
        if role not in STRUCTURE_MANAGE_ROLES:
            continue
        events = db.query(Event).filter(Event.host_type == "orga", Event.host_id == str(membership.organization_id)).all()
        for event in events:
            if not _event_is_active(event, stamp):
                continue
            expires_at = event.ends_at
            if membership.ends_at and (expires_at is None or membership.ends_at < expires_at):
                expires_at = membership.ends_at
            _merge_capability(merged, {
                "id": f"event:{event.id}:organization:{membership.id}", "type": "EVENT", "scope": f"event:{event.id}",
                "event_id": event.id, "bar_id": event.bar_id, "organization_id": membership.organization_id,
                "role": "MANAGER", "actions": sorted(EVENT_ROLE_ACTIONS["MANAGER"]),
                "source": "ORGANIZATION_MEMBERSHIP", "activated_at": _iso(membership.starts_at or membership.joined_at),
                "expires_at": _iso(expires_at), "status": "ACTIVE", "updated_at": _iso(membership.updated_at),
                "event": {"id": event.id, "name": event.name, "state": (event.event_state or "LIVE").upper(), "starts_at": _iso(event.starts_at), "ends_at": _iso(event.ends_at)},
            })
    return sorted(merged.values(), key=lambda item: item["event_id"])


def event_runtime_state_payload(db: Session, event_id: int) -> dict[str, Any]:
    runtime = (
        db.query(EventRuntimeState)
        .filter(EventRuntimeState.event_id == event_id)
        .first()
    )
    return {
        "state": ((runtime.state if runtime else "LIVE") or "LIVE").upper(),
        "reason": runtime.reason if runtime else None,
        "updated_at": _iso(runtime.updated_at) if runtime else None,
    }


def update_event_runtime_state(
    db: Session,
    *,
    event_id: int,
    state: str,
    reason: Optional[str],
    actor_user_id: str,
    actor_role: str,
    idempotency_key: str,
) -> dict[str, Any]:
    normalized_state = (state or "").upper()
    if normalized_state not in EVENT_RUNTIME_STATES:
        raise HTTPException(
            status_code=422,
            detail={"reason": "invalid_state", "state": normalized_state},
        )
    if len(idempotency_key) > 120:
        raise HTTPException(
            status_code=422,
            detail={"reason": "idempotency_key_too_long"},
        )

    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail={"reason": "event_not_found"})

    action = f"event_state:{event_id}"
    replay = (
        db.query(EventAppWriteIdempotency)
        .filter(
            EventAppWriteIdempotency.actor_user_id == actor_user_id,
            EventAppWriteIdempotency.action == action,
            EventAppWriteIdempotency.idempotency_key == idempotency_key,
        )
        .first()
    )
    if replay is not None:
        response = dict(replay.response_json or {})
        response["idempotent"] = True
        return response

    runtime = (
        db.query(EventRuntimeState)
        .filter(EventRuntimeState.event_id == event_id)
        .first()
    )
    if runtime is None:
        runtime = EventRuntimeState(event_id=event_id, state="LIVE")
        db.add(runtime)

    before = {
        "state": ((runtime.state or "LIVE")).upper(),
        "reason": runtime.reason,
    }
    normalized_reason = (reason or "").strip()[:180]
    if before["state"] != normalized_state and not normalized_reason:
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "reason_required",
                "message": "Reason is required for runtime state change",
            },
        )

    runtime.state = normalized_state
    runtime.reason = normalized_reason or None
    runtime.updated_by_user_id = actor_user_id
    runtime.updated_at = now_utc()
    after = {
        "state": runtime.state,
        "reason": runtime.reason,
    }
    response = {
        "ok": True,
        "event_id": event_id,
        "state": runtime.state,
        "reason": runtime.reason,
        "updated_at": _iso(runtime.updated_at),
        "idempotent": False,
    }
    db.add(
        EventAppWriteIdempotency(
            actor_user_id=actor_user_id,
            action=action,
            idempotency_key=idempotency_key,
            response_json=response,
        )
    )
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action="event_state.update",
        entity_type="event",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=event.bar_id,
        idempotency_key=idempotency_key,
        payload={"before": before, "after": after},
    )
    db.commit()
    return response


def bar_capabilities(db: Session, user: AppUser, *, at: Optional[datetime] = None) -> list[dict[str, Any]]:
    stamp = at or now_utc()
    partner = db.query(PartnerUser).filter(PartnerUser.app_user_id == user.id, PartnerUser.is_active == True).first()  # noqa: E712
    if partner is None:
        return []
    merged: dict[int, dict[str, Any]] = {}
    rows = db.query(PartnerBarAccess, Bar).join(Bar, Bar.id == PartnerBarAccess.bar_id).filter(
        PartnerBarAccess.partner_user_id == partner.id,
        PartnerBarAccess.is_active == True,  # noqa: E712
        PartnerBarAccess.status == "ACTIVE",
        PartnerBarAccess.revoked_at.is_(None),
        or_(PartnerBarAccess.starts_at.is_(None), PartnerBarAccess.starts_at <= stamp),
        or_(PartnerBarAccess.expires_at.is_(None), PartnerBarAccess.expires_at > stamp),
    ).all()
    for access, bar in rows:
        if (bar.partner_status or "ACTIVE").upper() != "ACTIVE":
            continue
        role = (access.role or "STAFF").upper()
        allowed = BAR_ROLE_ACTIONS.get(role, BAR_ROLE_ACTIONS["STAFF"])
        stored = {str(action) for action in (access.actions_json or [])}
        actions = sorted(allowed if not stored else allowed & stored)
        _merge_capability(merged, {
            "id": f"bar:{bar.id}:access:{access.id}", "type": "BAR", "scope": f"bar:{bar.id}",
            "event_id": None, "bar_id": bar.id, "organization_id": None, "role": role,
            "actions": actions, "source": access.source or "PARTNER_ACCESS",
            "activated_at": _iso(access.starts_at or access.created_at), "expires_at": _iso(access.expires_at),
            "status": "ACTIVE", "updated_at": _iso(access.updated_at or access.created_at),
            "bar": {"id": bar.id, "name": bar.name, "logo_url": bar.logo_url, "primary_color": bar.primary_color, "partner_status": bar.partner_status},
        })
    legacy = db.query(PartnerMembership, Bar).join(Bar, Bar.id == PartnerMembership.bar_id).filter(PartnerMembership.user_id == partner.id).all()
    for membership, bar in legacy:
        if bar.id in merged or (bar.partner_status or "ACTIVE").upper() != "ACTIVE":
            continue
        role = (membership.role or "BARTENDER").upper()
        _merge_capability(merged, {
            "id": f"bar:{bar.id}:legacy:{membership.id}", "type": "BAR", "scope": f"bar:{bar.id}",
            "event_id": None, "bar_id": bar.id, "organization_id": None, "role": role,
            "actions": sorted(BAR_ROLE_ACTIONS.get(role, BAR_ROLE_ACTIONS["BARTENDER"])),
            "source": "PARTNER_MEMBERSHIP_LEGACY", "activated_at": _iso(partner.created_at), "expires_at": None,
            "status": "ACTIVE", "updated_at": _iso(partner.created_at),
            "bar": {"id": bar.id, "name": bar.name, "logo_url": bar.logo_url, "primary_color": bar.primary_color, "partner_status": bar.partner_status},
        })
    return sorted(merged.values(), key=lambda item: item["bar_id"])


def effective_capabilities_payload(db: Session, user: AppUser) -> dict[str, Any]:
    stamp = now_utc()
    global_role = (user.global_role or "USER").upper()
    if global_role not in {"USER", "SUPPORT", "ADMIN"}:
        global_role = "USER"
    global_roles = ["USER"] if global_role == "USER" else ["USER", global_role]
    events = event_capabilities(db, user, at=stamp)
    bars = bar_capabilities(db, user, at=stamp)
    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.status == "ACTIVE",
        OrganizationMembership.revoked_at.is_(None),
        or_(OrganizationMembership.starts_at.is_(None), OrganizationMembership.starts_at <= stamp),
        or_(OrganizationMembership.ends_at.is_(None), OrganizationMembership.ends_at > stamp),
    ).all()
    structures = [{
        "organization_id": row.organization_id,
        "role": (row.role or "MEMBER").upper(),
        "can_manage": (row.role or "MEMBER").upper() in STRUCTURE_MANAGE_ROLES,
        "expires_at": _iso(row.ends_at),
    } for row in memberships]
    return {
        "user_id": user.id,
        "global_roles": global_roles,
        "structures": structures,
        "events": events,
        "bars": bars,
        "capabilities": [*events, *bars],
        # Keep the Lot 3 discovery flag compatible for structure members. The
        # scoped `events`/`capabilities` collections remain the sole authority
        # for opening an operational event context.
        "modes": {"organizer": bool(events) or any(row["can_manage"] for row in structures), "bar": bool(bars)},
        "operational_modes": {"organizer": bool(events), "bar": bool(bars)},
        "evaluated_at": _iso(stamp),
        "cache_ttl_seconds": 60,
    }


def require_event_action(db: Session, user: AppUser, event_id: int, action: str) -> dict[str, Any]:
    capability = next((item for item in event_capabilities(db, user) if item["event_id"] == event_id), None)
    if capability is None or action not in capability["actions"]:
        raise HTTPException(status_code=403, detail={"reason": "event_scope_forbidden", "event_id": event_id, "action": action})
    return capability


def require_bar_action(db: Session, user: AppUser, bar_id: int, action: str) -> dict[str, Any]:
    capability = next((item for item in bar_capabilities(db, user) if item["bar_id"] == bar_id), None)
    if capability is None or action not in capability["actions"]:
        raise HTTPException(status_code=403, detail={"reason": "bar_scope_forbidden", "bar_id": bar_id, "action": action})
    return capability
