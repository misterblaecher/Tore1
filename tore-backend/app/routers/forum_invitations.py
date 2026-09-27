from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import secrets
from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from db import now_utc
from models import AppUser, Organization, OrganizationMembership, StructureInvitation
from app.core.security.user_auth import get_current_user
from app.deps.db import get_db
from app.routers.forum import ROLE_RANK, _require_role, _structure_or_404
from app.services.audit_service import write_audit_log
from app.services.rate_limit_service import RateLimitExceeded, enforce_rate_limit, standard_rate_limit_http_exception
from app.services.structure_invitation_email_service import send_structure_invitation_email


router = APIRouter(prefix="/forum", tags=["forum-invitations"])

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_INVITABLE_ROLES = (
    "MEMBER",
    "STAFF",
    "COMMUNICATION",
    "ARCHIVIST",
    "SECRETARY",
    "TREASURER",
    "TRESORIER",
    "BUREAU",
    "VICE_PRESIDENT",
    "PRESIDENT",
    "MANAGER",
    "ADMIN",
)
_INVITATION_STATES = {"PENDING", "ACCEPTED", "DECLINED", "EXPIRED", "REVOKED"}


class StructureInvitationCreateIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    invited_role: str = Field(default="MEMBER", min_length=2, max_length=32)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not _EMAIL_RE.match(cleaned):
            raise ValueError("Email invalide")
        return cleaned

    @field_validator("invited_role")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        return value.strip().upper()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(48)
    return token, _token_hash(token)


def _status(row: StructureInvitation) -> str:
    if row.accepted_at is not None:
        return "ACCEPTED"
    if row.declined_at is not None:
        return "DECLINED"
    if row.revoked_at is not None:
        return "REVOKED"
    if row.expires_at <= now_utc():
        return "EXPIRED"
    return "PENDING"


def _allowed_roles(actor_role: str) -> list[str]:
    actor_rank = ROLE_RANK.get((actor_role or "MEMBER").upper(), 0)
    return [role for role in _INVITABLE_ROLES if ROLE_RANK.get(role, 0) <= actor_rank]


def _assert_role_can_be_invited(actor_role: str, invited_role: str) -> None:
    if invited_role not in _INVITABLE_ROLES or invited_role not in _allowed_roles(actor_role):
        raise HTTPException(status_code=403, detail={"reason": "INVITED_ROLE_NOT_ALLOWED"})


def _expires_at():
    days = max(1, min(30, int(os.getenv("TORE_STRUCTURE_INVITATION_EXPIRY_DAYS", "7"))))
    return now_utc() + timedelta(days=days)


def _portal_base_url() -> str:
    return (os.getenv("TORE_PORTAL_BASE_URL") or "http://localhost:5173").rstrip("/")


def _invite_url(token: str) -> str:
    return f"{_portal_base_url()}/forum/invite/{token}"


def _qr_svg_data_uri(value: str) -> str:
    import qrcode
    from qrcode.image.svg import SvgPathImage

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=7, border=2)
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(image_factory=SvgPathImage)
    buffer = io.BytesIO()
    image.save(buffer)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _masked_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    visible = local[:1] if local else "*"
    return f"{visible}{'*' * max(3, len(local) - 1)}@{domain}"


def _payload(row: StructureInvitation, *, share_token: Optional[str] = None, delivery_status: Optional[str] = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": row.id,
        "email": row.email,
        "invitedRole": row.invited_role,
        "invitedBy": row.invited_by,
        "status": _status(row),
        "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
        "acceptedAt": row.accepted_at.isoformat() if row.accepted_at else None,
        "declinedAt": row.declined_at.isoformat() if row.declined_at else None,
        "revokedAt": row.revoked_at.isoformat() if row.revoked_at else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }
    if share_token:
        url = _invite_url(share_token)
        payload["inviteUrl"] = url
        payload["qrSvgDataUri"] = _qr_svg_data_uri(url)
    if delivery_status:
        payload["deliveryStatus"] = delivery_status
    return payload


def _rate(scope: str, key: str) -> None:
    try:
        enforce_rate_limit(scope, key)
    except RateLimitExceeded as exc:
        raise standard_rate_limit_http_exception(exc.scope, exc.retry_after_seconds) from exc


def _recipient_rate_key(email: str) -> str:
    return hashlib.sha256(email.encode("utf-8")).hexdigest()[:24]


def _client_rate_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for") or ""
    ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else "unknown")
    user_agent = (request.headers.get("user-agent") or "")[:160]
    return hashlib.sha256(f"{ip}|{user_agent}".encode("utf-8")).hexdigest()[:24]


def _lookup_token(db: Session, token: str, *, lock: bool = False) -> Optional[StructureInvitation]:
    if len(token) < 32 or len(token) > 256:
        return None
    query = db.query(StructureInvitation).filter(StructureInvitation.token_hash == _token_hash(token))
    if lock:
        query = query.with_for_update()
    return query.first()


def _not_available() -> HTTPException:
    return HTTPException(status_code=410, detail={"reason": "INVITATION_NOT_AVAILABLE"})


def _deliver(row: StructureInvitation, token: str, structure_name: str) -> str:
    return send_structure_invitation_email(
        recipient_email=row.email,
        structure_name=structure_name,
        invited_role=row.invited_role,
        invite_url=_invite_url(token),
        expires_label=row.expires_at.isoformat(),
    )


@router.get("/structures/{slug}/invitations")
def list_structure_invitations(
    slug: str,
    invitation_status: Optional[str] = Query(default=None, alias="status", max_length=20),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    normalized = invitation_status.strip().upper() if invitation_status else None
    if normalized and normalized not in _INVITATION_STATES:
        raise HTTPException(status_code=400, detail={"reason": "INVALID_INVITATION_STATUS"})
    rows = db.query(StructureInvitation).filter(StructureInvitation.structure_id == org.id).order_by(StructureInvitation.created_at.desc(), StructureInvitation.id.desc()).all()
    items = [_payload(row) for row in rows if normalized is None or _status(row) == normalized]
    return {"items": items, "allowedRoles": _allowed_roles(actor.role)}


@router.post("/structures/{slug}/invitations", status_code=status.HTTP_202_ACCEPTED)
def create_structure_invitation(
    slug: str,
    payload: StructureInvitationCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    _assert_role_can_be_invited(actor.role, payload.invited_role)
    _rate("forum_invitation_actor", f"{user.id}:{org.id}")
    _rate("forum_invitation_recipient", f"{org.id}:{_recipient_rate_key(payload.email)}")

    now = now_utc()
    existing = db.query(StructureInvitation).filter(
        StructureInvitation.structure_id == org.id,
        StructureInvitation.email == payload.email,
        StructureInvitation.accepted_at.is_(None),
        StructureInvitation.declined_at.is_(None),
        StructureInvitation.revoked_at.is_(None),
        StructureInvitation.expires_at > now,
    ).order_by(StructureInvitation.created_at.desc()).first()

    token, token_hash = _new_token()
    if existing is None:
        row = StructureInvitation(
            structure_id=org.id,
            email=payload.email,
            token_hash=token_hash,
            invited_role=payload.invited_role,
            invited_by=user.id,
            expires_at=_expires_at(),
            created_at=now,
        )
        db.add(row)
    else:
        row = existing
        row.token_hash = token_hash
        row.invited_role = payload.invited_role
        row.invited_by = user.id
        row.expires_at = _expires_at()
    db.flush()

    delivery = _deliver(row, token, org.name)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="forum.invitation.create" if existing is None else "forum.invitation.rotate",
        entity_type="structure_invitation",
        entity_id=str(row.id),
        event_id=None,
        committee_id=None,
        bar_id=None,
        payload={"structure_id": org.id, "email_hash": _recipient_rate_key(row.email), "invited_role": row.invited_role, "delivery_status": delivery},
    )
    db.commit()
    db.refresh(row)
    return _payload(row, share_token=token, delivery_status=delivery)


@router.post("/structures/{slug}/invitations/{invitation_id}/resend", status_code=status.HTTP_202_ACCEPTED)
def resend_structure_invitation(
    slug: str,
    invitation_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    row = db.query(StructureInvitation).filter(StructureInvitation.id == invitation_id, StructureInvitation.structure_id == org.id).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if _status(row) not in {"PENDING", "EXPIRED"}:
        raise HTTPException(status_code=409, detail={"reason": "INVITATION_CANNOT_BE_RESENT"})
    _assert_role_can_be_invited(actor.role, row.invited_role)
    _rate("forum_invitation_actor", f"{user.id}:{org.id}")
    _rate("forum_invitation_recipient", f"{org.id}:{_recipient_rate_key(row.email)}")

    token, token_hash = _new_token()
    row.token_hash = token_hash
    row.invited_by = user.id
    row.expires_at = _expires_at()
    db.flush()
    delivery = _deliver(row, token, org.name)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="forum.invitation.resend",
        entity_type="structure_invitation",
        entity_id=str(row.id),
        event_id=None,
        committee_id=None,
        bar_id=None,
        payload={"structure_id": org.id, "email_hash": _recipient_rate_key(row.email), "invited_role": row.invited_role, "delivery_status": delivery},
    )
    db.commit()
    db.refresh(row)
    return _payload(row, share_token=token, delivery_status=delivery)


@router.post("/structures/{slug}/invitations/{invitation_id}/revoke")
def revoke_structure_invitation(
    slug: str,
    invitation_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    row = db.query(StructureInvitation).filter(StructureInvitation.id == invitation_id, StructureInvitation.structure_id == org.id).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if _status(row) in {"ACCEPTED", "DECLINED", "REVOKED"}:
        raise HTTPException(status_code=409, detail={"reason": "INVITATION_CANNOT_BE_REVOKED"})
    row.revoked_at = now_utc()
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="forum.invitation.revoke",
        entity_type="structure_invitation",
        entity_id=str(row.id),
        event_id=None,
        committee_id=None,
        bar_id=None,
        payload={"structure_id": org.id, "email_hash": _recipient_rate_key(row.email), "invited_role": row.invited_role},
    )
    db.commit()
    return {"ok": True, "id": row.id, "status": "REVOKED", "revokedAt": row.revoked_at.isoformat()}


@router.get("/invitations/{token}")
def inspect_structure_invitation(token: str, request: Request, db: Session = Depends(get_db)):
    _rate("forum_invitation_consume", _client_rate_key(request))
    row = _lookup_token(db, token)
    if row is None:
        raise _not_available()
    org = db.get(Organization, row.structure_id)
    if org is None:
        raise _not_available()
    return {
        "structure": {"name": org.name, "slug": org.slug, "logoUrl": org.logo_url},
        "emailMasked": _masked_email(row.email),
        "invitedRole": row.invited_role,
        "status": _status(row),
        "expiresAt": row.expires_at.isoformat(),
    }


@router.post("/invitations/{token}/accept")
def accept_structure_invitation(
    token: str,
    request: Request,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _rate("forum_invitation_consume", _client_rate_key(request))
    row = _lookup_token(db, token, lock=True)
    if row is None or _status(row) != "PENDING":
        raise _not_available()
    user_email = (user.email or "").strip().lower()
    if not user_email or user_email != row.email:
        raise HTTPException(status_code=403, detail={"reason": "INVITATION_ACCOUNT_MISMATCH"})

    org = db.get(Organization, row.structure_id)
    if org is None:
        raise _not_available()
    if row.invited_role not in _INVITABLE_ROLES:
        raise HTTPException(status_code=409, detail={"reason": "INVITED_ROLE_NO_LONGER_VALID"})

    now = now_utc()
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == row.structure_id,
        OrganizationMembership.user_id == user.id,
    ).with_for_update().first()
    if membership is None:
        membership = OrganizationMembership(
            organization_id=row.structure_id,
            user_id=user.id,
            role=row.invited_role,
            status="ACTIVE",
            visibility="PRIVATE",
            created_by_user_id=row.invited_by,
            created_at=now,
            joined_at=now,
            starts_at=now,
        )
        db.add(membership)
    else:
        if (membership.role or "").upper() != "OWNER":
            membership.role = row.invited_role
        membership.status = "ACTIVE"
        membership.revoked_at = None
        membership.revoked_by_user_id = None
        membership.revoke_reason = None
        membership.starts_at = membership.starts_at or now
        membership.joined_at = membership.joined_at or now
    membership.validated_by_user_id = user.id
    membership.validated_at = now
    membership.validation_source = "EMAIL_INVITATION"
    membership.updated_at = now
    row.accepted_at = now
    db.flush()

    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=membership.role,
        action="forum.invitation.accept",
        entity_type="structure_invitation",
        entity_id=str(row.id),
        event_id=None,
        committee_id=None,
        bar_id=None,
        payload={"structure_id": row.structure_id, "membership_id": membership.id, "invited_role": row.invited_role},
    )
    db.commit()
    return {"ok": True, "status": "ACCEPTED", "structure": {"slug": org.slug, "name": org.name}, "role": membership.role}


@router.post("/invitations/{token}/decline")
def decline_structure_invitation(token: str, request: Request, db: Session = Depends(get_db)):
    _rate("forum_invitation_consume", _client_rate_key(request))
    row = _lookup_token(db, token, lock=True)
    if row is None or _status(row) != "PENDING":
        raise _not_available()
    row.declined_at = now_utc()
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=None,
        actor_role="INVITEE",
        action="forum.invitation.decline",
        entity_type="structure_invitation",
        entity_id=str(row.id),
        event_id=None,
        committee_id=None,
        bar_id=None,
        payload={"structure_id": row.structure_id, "invited_role": row.invited_role},
    )
    db.commit()
    return {"ok": True, "status": "DECLINED"}
