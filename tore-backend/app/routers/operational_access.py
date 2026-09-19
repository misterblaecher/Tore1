from __future__ import annotations

from typing import Iterator, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from db import now_utc
from models import AppUser, AuditLog, Bar, Event, EventStaff, EventStaffInviteCode, Order
from app.services.audit_service import write_audit_log
from app.services.event_staff_invitation_service import (
    accept_secure_event_invitation,
    create_secure_event_invitation,
    hash_invitation_token,
    revoke_secure_event_invitation,
)
from app.services.idempotency_service import ensure_idempotency_key
from app.services.operational_access_service import require_bar_action, require_event_action
from app.services.orders_service import transition_order_status_idempotent
from app.services.p3_common import ensure_event_action_allowed


router = APIRouter(tags=["operational-access"])


from app.deps.db import get_db


def current_app_user(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> AppUser:
    from app.legacy.monolith import _extract_bearer_token, _resolve_app_user_from_token

    raw = _extract_bearer_token(authorization)
    user = _resolve_app_user_from_token(raw, db) if raw else None
    if user is None or user.is_guest:
        raise HTTPException(401, detail={"reason": "registered_session_required"})
    return user


class SecureInvitationCreateIn(BaseModel):
    model_config = {"extra": "forbid"}

    target_user_id: str = Field(min_length=1, max_length=120)
    role: Literal["ENTRY", "HELPER", "MANAGER", "BAR"]
    expires_in_hours: int = Field(default=12, ge=1, le=168)


class SecureInvitationAcceptIn(BaseModel):
    model_config = {"extra": "forbid"}

    token: str = Field(min_length=24, max_length=256)


class ReasonIn(BaseModel):
    model_config = {"extra": "forbid"}

    reason: str = Field(min_length=3, max_length=280)


class OrderTransitionIn(BaseModel):
    model_config = {"extra": "forbid"}

    action: Literal["accept", "ready", "complete", "cancel"]
    reason: Optional[str] = Field(default=None, max_length=280)


def _invitation_status(invite: EventStaffInviteCode) -> str:
    if invite.revoked_at is not None or invite.status == "REVOKED":
        return "REVOKED"
    if invite.expires_at is None or invite.expires_at <= now_utc():
        return "EXPIRED"
    if invite.accepted_at is not None or invite.status == "ACCEPTED":
        return "ACCEPTED"
    if invite.status == "DECLINED":
        return "DECLINED"
    return "PENDING"


def _invitation_payload(invite: EventStaffInviteCode, event: Optional[Event]) -> dict:
    return {
        "id": invite.id,
        "event_id": invite.event_id,
        "event_name": event.name if event else f"Event #{invite.event_id}",
        "target_user_id": invite.target_user_id,
        "role": (invite.role or "HELPER").upper(),
        "actions": list(invite.actions_json or []),
        "status": _invitation_status(invite),
        "created_at": invite.created_at.isoformat() if invite.created_at else None,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "accepted_at": invite.accepted_at.isoformat() if invite.accepted_at else None,
        "revoked_at": invite.revoked_at.isoformat() if invite.revoked_at else None,
    }


@router.get("/ops/events/{event_id}")
def event_ops_hub(event_id: int, user: AppUser = Depends(current_app_user), db: Session = Depends(get_db)):
    capability = require_event_action(db, user, event_id, "event.view_ops")
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    from app.legacy.monolith import entry_count

    result = {
        "event": capability["event"],
        "role": capability["role"],
        "actions": capability["actions"],
        "source": capability["source"],
        "expires_at": capability["expires_at"],
        "server_time": now_utc().isoformat(),
    }
    if "event.manage_entry" in capability["actions"]:
        result["entry_count"] = entry_count(db, event_id)
    return result


@router.get("/ops/events/{event_id}/staff")
def event_ops_staff(event_id: int, user: AppUser = Depends(current_app_user), db: Session = Depends(get_db)):
    require_event_action(db, user, event_id, "event.manage_staff")
    rows = db.query(EventStaff, AppUser).outerjoin(AppUser, AppUser.id == EventStaff.user_id).filter(
        EventStaff.event_id == event_id
    ).order_by(EventStaff.created_at.desc()).all()
    invites = db.query(EventStaffInviteCode).filter(
        EventStaffInviteCode.event_id == event_id,
        EventStaffInviteCode.token_hash.is_not(None),
    ).order_by(EventStaffInviteCode.created_at.desc()).all()
    event = db.get(Event, event_id)
    return {"items": [{
        "user_id": staff.user_id,
        "display_name": member.display_name if member else None,
        "role": (staff.role or "helper").upper(),
        "status": "REVOKED" if staff.revoked_at else ("EXPIRED" if staff.expires_at and staff.expires_at <= now_utc() else ("ACTIVE" if staff.is_active else "INACTIVE")),
        "created_at": staff.created_at.isoformat() if staff.created_at else None,
        "expires_at": staff.expires_at.isoformat() if staff.expires_at else None,
        "revoked_at": staff.revoked_at.isoformat() if staff.revoked_at else None,
    } for staff, member in rows], "invitations": [
        _invitation_payload(invite, event) for invite in invites
    ]}


@router.post("/ops/events/{event_id}/staff-invitations")
def create_event_staff_invitation(
    event_id: int,
    payload: SecureInvitationCreateIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(current_app_user),
    db: Session = Depends(get_db),
):
    return create_secure_event_invitation(
        db, actor=user, event_id=event_id, target_user_id=payload.target_user_id,
        role=payload.role, expires_in_hours=payload.expires_in_hours,
        idempotency_key=ensure_idempotency_key(idempotency_key),
    )


@router.get("/me/event-staff-invitations")
def my_event_staff_invitations(user: AppUser = Depends(current_app_user), db: Session = Depends(get_db)):
    rows = db.query(EventStaffInviteCode).filter(
        EventStaffInviteCode.target_user_id == user.id,
        EventStaffInviteCode.token_hash.is_not(None),
    ).order_by(EventStaffInviteCode.created_at.desc()).all()
    return {"items": [_invitation_payload(row, db.get(Event, row.event_id)) for row in rows]}


@router.get("/me/event-staff-invitations/preview")
def preview_event_staff_invitation(
    token: str = Query(min_length=24, max_length=256),
    user: AppUser = Depends(current_app_user),
    db: Session = Depends(get_db),
):
    invite = db.query(EventStaffInviteCode).filter(EventStaffInviteCode.token_hash == hash_invitation_token(token.strip())).first()
    if invite is None:
        raise HTTPException(404, detail={"reason": "invitation_not_found"})
    if invite.target_user_id != user.id:
        raise HTTPException(403, detail={"reason": "invitation_wrong_account"})
    return _invitation_payload(invite, db.get(Event, invite.event_id))


@router.post("/me/event-staff-invitations/accept")
def accept_event_staff_invitation(
    payload: SecureInvitationAcceptIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(current_app_user),
    db: Session = Depends(get_db),
):
    return accept_secure_event_invitation(
        db, user=user, token=payload.token,
        idempotency_key=ensure_idempotency_key(idempotency_key),
    )


@router.post("/me/event-staff-invitations/{invite_id}/decline")
def decline_event_staff_invitation(
    invite_id: int,
    payload: ReasonIn,
    user: AppUser = Depends(current_app_user),
    db: Session = Depends(get_db),
):
    invite = db.get(EventStaffInviteCode, invite_id)
    if invite is None or not invite.token_hash:
        raise HTTPException(404, detail={"reason": "invitation_not_found"})
    if invite.target_user_id != user.id:
        raise HTTPException(403, detail={"reason": "invitation_wrong_account"})
    if _invitation_status(invite) != "PENDING":
        raise HTTPException(409, detail={"reason": "invitation_not_pending"})
    invite.status = "DECLINED"
    invite.updated_at = now_utc()
    write_audit_log(
        db, actor_partner_id=None, actor_user_id=user.id, actor_role="app_user",
        action="event.staff_invitation.decline", entity_type="event_staff_invite_code",
        entity_id=str(invite.id), event_id=invite.event_id, bar_id=None,
        payload={"reason": payload.reason},
    )
    db.commit()
    return {"ok": True, "id": invite.id, "status": "DECLINED"}


@router.post("/ops/events/{event_id}/staff-invitations/{invite_id}/revoke")
def revoke_event_staff_invitation(
    event_id: int, invite_id: int, payload: ReasonIn,
    user: AppUser = Depends(current_app_user), db: Session = Depends(get_db),
):
    return revoke_secure_event_invitation(
        db, actor=user, event_id=event_id, invite_id=invite_id, reason=payload.reason.strip()
    )


@router.post("/ops/events/{event_id}/staff/{target_user_id}/revoke")
def revoke_event_staff_access(
    event_id: int, target_user_id: str, payload: ReasonIn,
    user: AppUser = Depends(current_app_user), db: Session = Depends(get_db),
):
    capability = require_event_action(db, user, event_id, "event.manage_staff")
    staff = db.query(EventStaff).filter(EventStaff.event_id == event_id, EventStaff.user_id == target_user_id).first()
    if staff is None:
        raise HTTPException(404, detail={"reason": "staff_not_found"})
    if (staff.role or "").upper() in {"ADMIN", "MANAGER"}:
        active_managers = db.query(EventStaff).filter(
            EventStaff.event_id == event_id,
            EventStaff.is_active == True,  # noqa: E712
            EventStaff.revoked_at.is_(None),
            EventStaff.role.in_(["admin", "manager"]),
        ).count()
        event = db.get(Event, event_id)
        actor_is_host = event is not None and event.host_type == "user" and event.host_id == user.id
        if active_managers <= 1 and not actor_is_host:
            raise HTTPException(409, detail={"reason": "last_event_manager"})
    now = now_utc()
    staff.is_active = False
    staff.revoked_at = now
    staff.revoked_by_user_id = user.id
    write_audit_log(
        db, actor_partner_id=None, actor_user_id=user.id, actor_role=capability["role"],
        action="event.staff.revoke", entity_type="event_staff", entity_id=str(staff.id),
        event_id=event_id, bar_id=None,
        payload={"target_user_id": target_user_id, "role": staff.role, "reason": payload.reason},
    )
    db.commit()
    return {"ok": True, "user_id": target_user_id, "status": "REVOKED", "effective_immediately": True}


@router.get("/ops/events/{event_id}/audit")
def event_ops_audit(
    event_id: int, limit: int = Query(default=30, ge=1, le=100),
    user: AppUser = Depends(current_app_user), db: Session = Depends(get_db),
):
    require_event_action(db, user, event_id, "event.manage_staff")
    rows = db.query(AuditLog).filter(
        AuditLog.event_id == event_id,
        AuditLog.action.in_([
            "event.staff_invitation.secure_create", "event.staff_invitation.secure_accept",
            "event.staff_invitation.secure_revoke", "event.staff_invitation.decline", "event.staff.revoke",
        ]),
    ).order_by(AuditLog.ts.desc()).limit(limit).all()
    return {"items": [{
        "id": row.id, "at": row.ts.isoformat(), "action": row.action,
        "actor_user_id": row.actor_user_id, "entity_id": row.entity_id,
        "details": row.payload_json,
    } for row in rows]}


@router.get("/ops/bars/{bar_id}")
def bar_ops_hub(bar_id: int, user: AppUser = Depends(current_app_user), db: Session = Depends(get_db)):
    capability = require_bar_action(db, user, bar_id, "bar.view_ops")
    bar = db.get(Bar, bar_id)
    if bar is None:
        raise HTTPException(404, "Bar not found")
    return {
        "bar": {"id": bar.id, "name": bar.name, "logo_url": bar.logo_url, "banner_url": bar.banner_url, "primary_color": bar.primary_color, "partner_status": bar.partner_status},
        "role": capability["role"], "actions": capability["actions"],
        "source": capability["source"], "expires_at": capability["expires_at"],
        "server_time": now_utc().isoformat(),
    }


@router.get("/ops/bars/{bar_id}/orders")
def bar_ops_orders(
    bar_id: int, status: Optional[str] = Query(default=None), limit: int = Query(default=100, ge=1, le=300),
    user: AppUser = Depends(current_app_user), db: Session = Depends(get_db),
):
    require_bar_action(db, user, bar_id, "bar.manage_orders")
    query = db.query(Order).options(selectinload(Order.items)).filter(Order.bar_id == bar_id)
    if status:
        normalized = status.upper()
        if normalized not in {"NEW", "IN_PROGRESS", "READY", "SERVED", "CANCELLED"}:
            raise HTTPException(422, detail={"reason": "invalid_status"})
        query = query.filter(Order.status == normalized)
    rows = query.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit).all()
    return {"items": [{
        "id": order.id, "bar_id": order.bar_id, "event_id": order.event_id,
        "status": order.status, "total_tickets": int(order.total_tickets or 0),
        "items": [{"name": item.name_snapshot, "qty": item.qty} for item in order.items],
        "created_at": order.created_at.isoformat(), "updated_at": order.updated_at.isoformat(),
    } for order in rows], "server_time": now_utc().isoformat()}


@router.post("/ops/bars/{bar_id}/orders/{order_id}/transition")
def bar_ops_order_transition(
    bar_id: int, order_id: int, payload: OrderTransitionIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(current_app_user), db: Session = Depends(get_db),
):
    capability = require_bar_action(db, user, bar_id, "bar.manage_orders")
    order = db.query(Order).options(selectinload(Order.items)).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(404, "Order not found")
    if order.bar_id != bar_id:
        raise HTTPException(403, detail={"reason": "order_bar_scope_forbidden"})
    flow = {
        "accept": ({"NEW"}, "IN_PROGRESS"),
        "ready": ({"IN_PROGRESS"}, "READY"),
        "complete": ({"READY"}, "SERVED"),
        "cancel": ({"NEW", "IN_PROGRESS"}, "CANCELLED"),
    }
    expected, next_status = flow[payload.action]
    if payload.action == "cancel" and not (payload.reason or "").strip():
        raise HTTPException(422, detail={"reason": "cancel_reason_required"})
    if order.event_id is not None:
        ensure_event_action_allowed(db, order.event_id, "orders_enabled", write=True)
    return transition_order_status_idempotent(
        db, order=order, action=payload.action, expected_from=expected,
        next_status=next_status, idempotency_key=ensure_idempotency_key(idempotency_key),
        actor_user_id=user.id, actor_role=capability["role"], reason=payload.reason,
    )
