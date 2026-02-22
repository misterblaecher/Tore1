from __future__ import annotations

import csv
import io
from typing import Any, Iterator, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.services.audit_service import write_audit_log
from app.services.entry_service import get_owned_event_or_403
from app.services.idempotency_service import ensure_idempotency_key
from app.services.p3_common import ensure_event_action_allowed
from db import now_utc
from models import (
    AppUser,
    EventSafetyBuddy,
    EventSafetyCheckin,
    EventSafetyIdempotency,
    EventSafetySettings,
)
from partner_auth import current_identity

router = APIRouter(tags=["safety-v1"])
security = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    from app.legacy.monolith import get_db as _get_db

    yield from _get_db()


def _app_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    from app.legacy.monolith import get_current_user

    return get_current_user(credentials=credentials, db=db)


def _assert_module_on(db: Session, event_id: int) -> None:
    try:
        ensure_event_action_allowed(db, event_id, "safety_enabled", write=False)
    except HTTPException as exc:
        if isinstance(exc.detail, dict) and exc.detail.get("code") == "MODULE_OFF":
            raise HTTPException(status_code=404, detail={"code": "MODULE_OFF", "message": "Safety module is disabled"})
        raise


def _ensure_portal_access(identity: dict[str, Any]) -> None:
    if identity.get("role") not in {"manager", "safety"}:
        raise HTTPException(status_code=403, detail="Forbidden")


def _idem_lookup(db: Session, *, event_id: int, action: str, actor_scope: str, actor_id: str, idempotency_key: str):
    return (
        db.query(EventSafetyIdempotency)
        .filter(
            EventSafetyIdempotency.event_id == event_id,
            EventSafetyIdempotency.action == action,
            EventSafetyIdempotency.actor_scope == actor_scope,
            EventSafetyIdempotency.actor_id == actor_id,
            EventSafetyIdempotency.idempotency_key == idempotency_key,
        )
        .first()
    )


def _idem_store(db: Session, *, event_id: int, action: str, actor_scope: str, actor_id: str, idempotency_key: str, response_json: dict[str, Any]) -> None:
    db.add(
        EventSafetyIdempotency(
            event_id=event_id,
            action=action,
            actor_scope=actor_scope,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            response_json=response_json,
        )
    )


@router.get("/events/{event_id}/safety/state")
def get_safety_state(event_id: int, user=Depends(_app_user), db: Session = Depends(get_db)):
    _assert_module_on(db, event_id)
    settings = db.query(EventSafetySettings).filter(EventSafetySettings.event_id == event_id).first()
    mapping = db.query(EventSafetyBuddy).filter(EventSafetyBuddy.event_id == event_id, EventSafetyBuddy.user_id == user.id).first()
    my_last = (
        db.query(EventSafetyCheckin)
        .filter(EventSafetyCheckin.event_id == event_id, EventSafetyCheckin.user_id == user.id)
        .order_by(EventSafetyCheckin.created_at.desc(), EventSafetyCheckin.id.desc())
        .first()
    )
    buddy_last = None
    if mapping:
        buddy_last = (
            db.query(EventSafetyCheckin)
            .filter(EventSafetyCheckin.event_id == event_id, EventSafetyCheckin.user_id == mapping.buddy_user_id)
            .order_by(EventSafetyCheckin.created_at.desc(), EventSafetyCheckin.id.desc())
            .first()
        )
    return {
        "enabled": bool(settings.enabled) if settings else True,
        "orgaPhone": settings.orga_phone if settings else None,
        "messageHint": settings.message_hint if settings else None,
        "myBuddy": {"userId": mapping.buddy_user_id} if mapping else None,
        "myLastCheckin": {"type": my_last.type, "createdAt": my_last.created_at.isoformat()} if my_last else None,
        "buddyLastCheckin": {"type": buddy_last.type, "createdAt": buddy_last.created_at.isoformat()} if buddy_last else None,
    }


@router.post("/events/{event_id}/safety/buddy")
def set_buddy(
    event_id: int,
    payload: dict[str, Any],
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user=Depends(_app_user),
    db: Session = Depends(get_db),
):
    _assert_module_on(db, event_id)
    ensure_event_action_allowed(db, event_id, "safety_enabled", write=True)
    key = ensure_idempotency_key(idempotency_key)
    existing = _idem_lookup(db, event_id=event_id, action="buddy", actor_scope="user", actor_id=user.id, idempotency_key=key)
    if existing:
        return existing.response_json
    buddy_user_id = str(payload.get("buddyUserId") or "").strip()
    if not buddy_user_id:
        raise HTTPException(status_code=422, detail="buddyUserId required")
    buddy = db.get(AppUser, buddy_user_id)
    if not buddy:
        raise HTTPException(status_code=404, detail="Buddy not found")
    row = db.query(EventSafetyBuddy).filter(EventSafetyBuddy.event_id == event_id, EventSafetyBuddy.user_id == user.id).first()
    if not row:
        row = EventSafetyBuddy(event_id=event_id, user_id=user.id, buddy_user_id=buddy_user_id)
    else:
        row.buddy_user_id = buddy_user_id
        row.created_at = now_utc()
    db.add(row)
    response = {"ok": True, "buddyUserId": buddy_user_id}
    _idem_store(db, event_id=event_id, action="buddy", actor_scope="user", actor_id=user.id, idempotency_key=key, response_json=response)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="safety.buddy.set",
        entity_type="event_safety_buddy",
        entity_id=f"{event_id}:{user.id}",
        event_id=event_id,
        bar_id=None,
        idempotency_key=key,
        payload={"buddy_user_id": buddy_user_id},
    )
    db.commit()
    return response


@router.post("/events/{event_id}/safety/checkin")
def create_checkin(
    event_id: int,
    payload: dict[str, Any],
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user=Depends(_app_user),
    db: Session = Depends(get_db),
):
    _assert_module_on(db, event_id)
    ensure_event_action_allowed(db, event_id, "safety_enabled", write=True)
    key = ensure_idempotency_key(idempotency_key)
    existing = _idem_lookup(db, event_id=event_id, action="checkin", actor_scope="user", actor_id=user.id, idempotency_key=key)
    if existing:
        return existing.response_json
    checkin_type = str(payload.get("type") or "").upper()
    if checkin_type not in {"OK", "PANIC"}:
        raise HTTPException(status_code=422, detail="type must be OK|PANIC")
    row = EventSafetyCheckin(event_id=event_id, user_id=user.id, type=checkin_type)
    db.add(row)
    db.flush()
    response = {"ok": True, "createdAt": row.created_at.isoformat(), "id": row.id}
    _idem_store(db, event_id=event_id, action="checkin", actor_scope="user", actor_id=user.id, idempotency_key=key, response_json=response)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="safety.checkin.create",
        entity_type="event_safety_checkin",
        entity_id=str(row.id),
        event_id=event_id,
        bar_id=None,
        idempotency_key=key,
        payload={"type": checkin_type},
    )
    db.commit()
    return response


@router.get("/events/{event_id}/safety/history")
def safety_history(event_id: int, limit: int = Query(default=50, ge=1, le=100), user=Depends(_app_user), db: Session = Depends(get_db)):
    _assert_module_on(db, event_id)
    rows = (
        db.query(EventSafetyCheckin)
        .filter(EventSafetyCheckin.event_id == event_id, EventSafetyCheckin.user_id == user.id)
        .order_by(EventSafetyCheckin.created_at.desc(), EventSafetyCheckin.id.desc())
        .limit(limit)
        .all()
    )
    mapping = db.query(EventSafetyBuddy).filter(EventSafetyBuddy.event_id == event_id, EventSafetyBuddy.user_id == user.id).first()
    buddy_last = None
    if mapping:
        buddy_row = (
            db.query(EventSafetyCheckin)
            .filter(EventSafetyCheckin.event_id == event_id, EventSafetyCheckin.user_id == mapping.buddy_user_id)
            .order_by(EventSafetyCheckin.created_at.desc(), EventSafetyCheckin.id.desc())
            .first()
        )
        if buddy_row:
            buddy_last = {"userId": mapping.buddy_user_id, "type": buddy_row.type, "createdAt": buddy_row.created_at.isoformat()}
    return {
        "items": [{"id": r.id, "type": r.type, "createdAt": r.created_at.isoformat()} for r in rows],
        "buddyLastCheckin": buddy_last,
    }


@router.get("/partner/portal/orga/events/{event_id}/safety/alerts")
def portal_alerts(event_id: int, status: Literal["open", "resolved"] = Query(default="open"), identity=Depends(current_identity), db: Session = Depends(get_db)):
    _ensure_portal_access(identity)
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    _assert_module_on(db, event_id)
    q = db.query(EventSafetyCheckin).filter(EventSafetyCheckin.event_id == event_id, EventSafetyCheckin.type == "PANIC")
    q = q.filter(EventSafetyCheckin.resolved_at.is_(None) if status == "open" else EventSafetyCheckin.resolved_at.is_not(None))
    rows = q.order_by(EventSafetyCheckin.created_at.desc(), EventSafetyCheckin.id.desc()).all()
    recent = (
        db.query(EventSafetyCheckin)
        .filter(EventSafetyCheckin.event_id == event_id)
        .order_by(EventSafetyCheckin.created_at.desc(), EventSafetyCheckin.id.desc())
        .limit(50)
        .all()
    )
    return {
        "alerts": [
            {
                "id": r.id,
                "userId": r.user_id,
                "type": r.type,
                "createdAt": r.created_at.isoformat(),
                "assignedToUserId": r.assigned_to_user_id,
                "resolvedAt": r.resolved_at.isoformat() if r.resolved_at else None,
                "resolveReason": r.resolve_reason,
            }
            for r in rows
        ],
        "recentCheckins": [{"id": r.id, "userId": r.user_id, "type": r.type, "createdAt": r.created_at.isoformat()} for r in recent],
    }


def _portal_alert_write(
    *,
    event_id: int,
    alert_id: int,
    action: str,
    idempotency_key: Optional[str],
    identity: dict[str, Any],
    db: Session,
    apply_fn,
):
    _ensure_portal_access(identity)
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    _assert_module_on(db, event_id)
    ensure_event_action_allowed(db, event_id, "safety_enabled", write=True)
    key = ensure_idempotency_key(idempotency_key)
    actor_id = str(identity["user_id"])
    existing = _idem_lookup(db, event_id=event_id, action=action, actor_scope="partner", actor_id=actor_id, idempotency_key=key)
    if existing:
        return existing.response_json
    row = db.get(EventSafetyCheckin, alert_id)
    if not row or row.event_id != event_id or row.type != "PANIC":
        raise HTTPException(status_code=404, detail="Alert not found")
    response = apply_fn(row)
    _idem_store(db, event_id=event_id, action=action, actor_scope="partner", actor_id=actor_id, idempotency_key=key, response_json=response)
    db.commit()
    return response


@router.post("/partner/portal/orga/events/{event_id}/safety/alerts/{alert_id}/assign")
def portal_assign_alert(
    event_id: int,
    alert_id: int,
    payload: dict[str, Any],
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(current_identity),
    db: Session = Depends(get_db),
):
    def _apply(row: EventSafetyCheckin):
        assignee = payload.get("assigneeUserId")
        row.assigned_to_user_id = int(assignee) if assignee is not None else identity["user_id"]
        db.add(row)
        response = {"ok": True, "id": row.id, "assignedToUserId": row.assigned_to_user_id}
        write_audit_log(
            db,
            actor_partner_id=identity["user_id"],
            actor_role=identity["role"],
            action="safety.alert.assign",
            entity_type="event_safety_checkin",
            entity_id=str(row.id),
            event_id=event_id,
            bar_id=identity["bar_id"],
            idempotency_key=key,
            payload={"assigned_to_user_id": row.assigned_to_user_id},
        )
        return response

    key = ensure_idempotency_key(idempotency_key)
    return _portal_alert_write(event_id=event_id, alert_id=alert_id, action="assign", idempotency_key=key, identity=identity, db=db, apply_fn=_apply)


@router.post("/partner/portal/orga/events/{event_id}/safety/alerts/{alert_id}/resolve")
def portal_resolve_alert(
    event_id: int,
    alert_id: int,
    payload: dict[str, Any],
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(current_identity),
    db: Session = Depends(get_db),
):
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=422, detail="reason required")

    def _apply(row: EventSafetyCheckin):
        if row.resolved_at is None:
            row.resolved_at = now_utc()
            row.resolved_by = identity["user_id"]
            row.resolve_reason = reason
        db.add(row)
        response = {"ok": True, "id": row.id, "resolvedAt": row.resolved_at.isoformat(), "reason": row.resolve_reason}
        write_audit_log(
            db,
            actor_partner_id=identity["user_id"],
            actor_role=identity["role"],
            action="safety.alert.resolve",
            entity_type="event_safety_checkin",
            entity_id=str(row.id),
            event_id=event_id,
            bar_id=identity["bar_id"],
            idempotency_key=key,
            payload={"reason": reason},
        )
        return response

    key = ensure_idempotency_key(idempotency_key)
    return _portal_alert_write(event_id=event_id, alert_id=alert_id, action="resolve", idempotency_key=key, identity=identity, db=db, apply_fn=_apply)


@router.get("/partner/portal/orga/events/{event_id}/safety/export.json")
def portal_export_json(event_id: int, identity=Depends(current_identity), db: Session = Depends(get_db)):
    _ensure_portal_access(identity)
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    _assert_module_on(db, event_id)
    rows = db.query(EventSafetyCheckin).filter(EventSafetyCheckin.event_id == event_id).order_by(EventSafetyCheckin.created_at.desc(), EventSafetyCheckin.id.desc()).all()
    return {"eventId": event_id, "items": [{"id": r.id, "userId": r.user_id, "type": r.type, "createdAt": r.created_at.isoformat(), "resolvedAt": r.resolved_at.isoformat() if r.resolved_at else None, "assignedToUserId": r.assigned_to_user_id} for r in rows]}


@router.get("/partner/portal/orga/events/{event_id}/safety/export.csv")
def portal_export_csv(event_id: int, identity=Depends(current_identity), db: Session = Depends(get_db)):
    payload = portal_export_json(event_id=event_id, identity=identity, db=db)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "user_id", "type", "created_at", "resolved_at", "assigned_to_user_id"])
    for row in payload["items"]:
        writer.writerow([row["id"], row["userId"], row["type"], row["createdAt"], row["resolvedAt"] or "", row["assignedToUserId"] or ""])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=safety_event_{event_id}.csv"})


@router.get("/partner/portal/orga/events/{event_id}/safety/settings")
def portal_settings_get(event_id: int, identity=Depends(current_identity), db: Session = Depends(get_db)):
    _ensure_portal_access(identity)
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    _assert_module_on(db, event_id)
    row = db.query(EventSafetySettings).filter(EventSafetySettings.event_id == event_id).first()
    return {
        "enabled": bool(row.enabled) if row else True,
        "orgaPhone": row.orga_phone if row else None,
        "messageHint": row.message_hint if row else None,
        "updatedAt": row.updated_at.isoformat() if row else None,
    }


@router.put("/partner/portal/orga/events/{event_id}/safety/settings")
def portal_settings_put(
    event_id: int,
    payload: dict[str, Any],
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(current_identity),
    db: Session = Depends(get_db),
):
    _ensure_portal_access(identity)
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    _assert_module_on(db, event_id)
    ensure_event_action_allowed(db, event_id, "safety_enabled", write=True)
    key = ensure_idempotency_key(idempotency_key)
    actor_id = str(identity["user_id"])
    existing = _idem_lookup(db, event_id=event_id, action="settings", actor_scope="partner", actor_id=actor_id, idempotency_key=key)
    if existing:
        return existing.response_json
    row = db.query(EventSafetySettings).filter(EventSafetySettings.event_id == event_id).first()
    if not row:
        row = EventSafetySettings(event_id=event_id)
    if "enabled" in payload:
        row.enabled = bool(payload.get("enabled"))
    row.orga_phone = str(payload.get("orgaPhone") or "").strip() or None
    row.message_hint = str(payload.get("messageHint") or "").strip() or None
    row.updated_at = now_utc()
    row.updated_by = identity["user_id"]
    db.add(row)
    db.flush()
    response = {"ok": True, "enabled": bool(row.enabled), "orgaPhone": row.orga_phone, "messageHint": row.message_hint, "updatedAt": row.updated_at.isoformat()}
    _idem_store(db, event_id=event_id, action="settings", actor_scope="partner", actor_id=actor_id, idempotency_key=key, response_json=response)
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="safety.settings.put",
        entity_type="event_safety_settings",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=identity["bar_id"],
        idempotency_key=key,
        payload={"enabled": bool(row.enabled), "message_hint": row.message_hint},
    )
    db.commit()
    return response
