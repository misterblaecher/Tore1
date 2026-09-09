from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import now_utc
from models import AppUser, Event, EventStaff, EventStaffInviteCode, EventStaffInviteIdempotency
from app.services.audit_service import write_audit_log
from app.services.operational_access_service import EVENT_ROLE_ACTIONS, require_event_action


ALLOWED_INVITE_ROLES = {"ENTRY", "HELPER", "MANAGER", "BAR"}


def hash_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_secure_event_invitation(
    db: Session,
    *,
    actor: AppUser,
    event_id: int,
    target_user_id: str,
    role: str,
    expires_in_hours: int,
    idempotency_key: str,
) -> dict:
    capability = require_event_action(db, actor, event_id, "event.manage_staff")
    normalized_role = role.upper().strip()
    if normalized_role not in ALLOWED_INVITE_ROLES:
        raise HTTPException(422, detail={"reason": "invalid_role"})
    target = db.get(AppUser, target_user_id)
    if target is None or target.is_deleted or target.is_guest:
        raise HTTPException(404, detail={"reason": "target_user_not_found"})
    existing = db.query(EventStaffInviteIdempotency).filter(
        EventStaffInviteIdempotency.event_id == event_id,
        EventStaffInviteIdempotency.action == "secure_create",
        EventStaffInviteIdempotency.actor_user_id == actor.id,
        EventStaffInviteIdempotency.idempotency_key == idempotency_key,
    ).first()
    if existing is not None:
        response = dict(existing.response_json or {})
        response["token"] = None
        response["idempotent"] = True
        return response

    now = now_utc()
    token = secrets.token_urlsafe(32)
    token_hash = hash_invitation_token(token)
    expires_at = now + timedelta(hours=expires_in_hours)
    invite = EventStaffInviteCode(
        event_id=event_id,
        role=normalized_role,
        code=f"SECURE-{token_hash[:16]}",
        token_hash=token_hash,
        target_user_id=target.id,
        actions_json=sorted(EVENT_ROLE_ACTIONS[normalized_role]),
        expires_at=expires_at,
        created_by=actor.id,
        status="PENDING",
        max_uses=1,
        used_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add(invite)
    db.flush()
    response = {
        "id": invite.id,
        "event_id": event_id,
        "target_user_id": target.id,
        "role": normalized_role,
        "actions": invite.actions_json,
        "status": "PENDING",
        "expires_at": expires_at.isoformat(),
        "token": token,
        "deep_link": f"tore://event-staff-invite?token={token}",
        "idempotent": False,
    }
    stored_response = dict(response)
    stored_response["token"] = None
    stored_response["deep_link"] = None
    db.add(EventStaffInviteIdempotency(
        event_id=event_id, action="secure_create", actor_user_id=actor.id,
        idempotency_key=idempotency_key, invite_id=invite.id, response_json=stored_response,
    ))
    event = db.get(Event, event_id)
    write_audit_log(
        db, actor_partner_id=None, actor_user_id=actor.id, actor_role=capability["role"],
        action="event.staff_invitation.secure_create", entity_type="event_staff_invite_code",
        entity_id=str(invite.id), event_id=event_id, bar_id=event.bar_id if event else None,
        idempotency_key=idempotency_key,
        payload={"target_user_id": target.id, "role": normalized_role, "expires_at": expires_at.isoformat()},
    )
    db.commit()
    return response


def accept_secure_event_invitation(
    db: Session,
    *,
    user: AppUser,
    token: str,
    idempotency_key: str,
) -> dict:
    token_hash = hash_invitation_token(token.strip())
    invite = db.query(EventStaffInviteCode).filter(EventStaffInviteCode.token_hash == token_hash).first()
    if invite is None:
        raise HTTPException(404, detail={"reason": "invitation_not_found"})
    existing = db.query(EventStaffInviteIdempotency).filter(
        EventStaffInviteIdempotency.event_id == invite.event_id,
        EventStaffInviteIdempotency.action == "secure_accept",
        EventStaffInviteIdempotency.actor_user_id == user.id,
        EventStaffInviteIdempotency.idempotency_key == idempotency_key,
    ).first()
    if existing is not None:
        return {**dict(existing.response_json or {}), "idempotent": True}
    if invite.target_user_id != user.id:
        raise HTTPException(403, detail={"reason": "invitation_wrong_account"})
    now = now_utc()
    if invite.revoked_at is not None or invite.status == "REVOKED":
        raise HTTPException(409, detail={"reason": "invitation_revoked"})
    if invite.expires_at is None or invite.expires_at <= now:
        invite.status = "EXPIRED"
        invite.updated_at = now
        db.commit()
        raise HTTPException(409, detail={"reason": "invitation_expired"})
    if invite.status == "ACCEPTED" or invite.used_count >= invite.max_uses:
        raise HTTPException(409, detail={"reason": "invitation_replayed"})
    if invite.status not in {"PENDING", "ACTIVE"}:
        raise HTTPException(409, detail={"reason": "invitation_not_active", "status": invite.status})

    role = (invite.role or "HELPER").lower()
    staff = db.query(EventStaff).filter(EventStaff.event_id == invite.event_id, EventStaff.user_id == user.id).first()
    if staff is None:
        staff = EventStaff(
            event_id=invite.event_id, user_id=user.id, role=role, is_active=True,
            created_at=now, created_by_user_id=invite.created_by, expires_at=invite.expires_at,
        )
        db.add(staff)
    else:
        staff.role = role
        staff.is_active = True
        staff.revoked_at = None
        staff.revoked_by_user_id = None
        staff.expires_at = invite.expires_at
    invite.status = "ACCEPTED"
    invite.used_count += 1
    invite.accepted_at = now
    invite.accepted_by_user_id = user.id
    invite.updated_at = now
    db.flush()
    response = {
        "ok": True, "invitation_id": invite.id, "event_id": invite.event_id,
        "role": (invite.role or "HELPER").upper(), "actions": list(invite.actions_json or []),
        "status": "ACCEPTED", "expires_at": invite.expires_at.isoformat(), "idempotent": False,
    }
    db.add(EventStaffInviteIdempotency(
        event_id=invite.event_id, action="secure_accept", actor_user_id=user.id,
        idempotency_key=idempotency_key, invite_id=invite.id, response_json=response,
    ))
    event = db.get(Event, invite.event_id)
    write_audit_log(
        db, actor_partner_id=None, actor_user_id=user.id, actor_role="app_user",
        action="event.staff_invitation.secure_accept", entity_type="event_staff_invite_code",
        entity_id=str(invite.id), event_id=invite.event_id, bar_id=event.bar_id if event else None,
        idempotency_key=idempotency_key, payload={"role": response["role"], "target_user_id": user.id},
    )
    db.commit()
    return response


def revoke_secure_event_invitation(
    db: Session,
    *, actor: AppUser, event_id: int, invite_id: int, reason: str,
) -> dict:
    capability = require_event_action(db, actor, event_id, "event.manage_staff")
    invite = db.get(EventStaffInviteCode, invite_id)
    if invite is None or invite.event_id != event_id or not invite.token_hash:
        raise HTTPException(404, detail={"reason": "invitation_not_found"})
    if invite.status == "ACCEPTED":
        raise HTTPException(409, detail={"reason": "invitation_already_accepted"})
    now = now_utc()
    invite.status = "REVOKED"
    invite.revoked_at = now
    invite.revoked_reason = reason
    invite.updated_at = now
    event = db.get(Event, event_id)
    write_audit_log(
        db, actor_partner_id=None, actor_user_id=actor.id, actor_role=capability["role"],
        action="event.staff_invitation.secure_revoke", entity_type="event_staff_invite_code",
        entity_id=str(invite.id), event_id=event_id, bar_id=event.bar_id if event else None,
        payload={"reason": reason, "target_user_id": invite.target_user_id},
    )
    db.commit()
    return {"ok": True, "id": invite.id, "status": "REVOKED"}
