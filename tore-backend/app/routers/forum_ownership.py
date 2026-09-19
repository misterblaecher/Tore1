from __future__ import annotations

import hashlib
import hmac
import os
import re
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import SessionLocal, now_utc
from models import AppToken, AppUser, Organization, OrganizationMembership
from app.core.security.user_auth import get_current_user
from app.deps.db import get_db
from app.ownership_models import StructureOwnership, StructureOwnershipTransfer, StructureRecoveryRequest
from app.services.audit_service import write_audit_log


router = APIRouter(prefix="/forum", tags=["forum-ownership"])

TRANSFER_TTL_HOURS = 72
OPEN_TRANSFER_STATES = {"REQUESTED", "CONFIRMED"}
OPEN_RECOVERY_STATES = {"REQUESTED"}
CRITICAL_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
STRUCTURE_PATH_RE = re.compile(r"^/forum/structures/([^/]+)(?:/.*)?$")
ORGA_PATH_RE = re.compile(r"^/orgas/(\d+)(?:/.*)?$")


class RecoveryOwnerIn(BaseModel):
    user_id: Optional[str] = Field(default=None, max_length=120)


class TransferRequestIn(BaseModel):
    to_user_id: str = Field(min_length=3, max_length=120)


class RecoveryRequestIn(BaseModel):
    reason: str = Field(min_length=8, max_length=4000)


class AdminFreezeIn(BaseModel):
    reason: str = Field(min_length=8, max_length=4000)
    keep_public_visible: bool = True


class AdminRecoveryResolveIn(BaseModel):
    approve: bool
    reason: str = Field(min_length=8, max_length=4000)


def _admin_key(x_admin_api_key: str | None = Header(default=None, alias="X-Admin-Api-Key")) -> str:
    expected = (os.getenv("ADMIN_API_KEY") or "").strip()
    supplied = (x_admin_api_key or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail={"reason": "admin_api_disabled", "message": "ADMIN_API_KEY non configurée"})
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail={"reason": "invalid_admin_key", "message": "Clé admin invalide"})
    return "ADMIN_API_KEY"


def _org(db: Session, slug: str, *, lock: bool = False) -> Organization:
    query = db.query(Organization).filter(Organization.slug == slug)
    if lock:
        query = query.with_for_update()
    org = query.first()
    if not org:
        raise HTTPException(status_code=404, detail={"reason": "structure_not_found"})
    return org


def _active_membership(db: Session, org_id: int, user_id: str, *, lock: bool = False) -> Optional[OrganizationMembership]:
    query = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.status == "ACTIVE",
        OrganizationMembership.revoked_at.is_(None),
    )
    if lock:
        query = query.with_for_update()
    membership = query.first()
    if not membership:
        return None
    stamp = now_utc()
    if membership.starts_at is not None and membership.starts_at > stamp:
        return None
    if membership.ends_at is not None and membership.ends_at <= stamp:
        return None
    return membership


def _audit(
    db: Session,
    *,
    action: str,
    org_id: int,
    actor_user_id: Optional[str],
    actor_role: str,
    payload: dict,
) -> None:
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        entity_type="structure",
        entity_id=str(org_id),
        event_id=None,
        committee_id=None,
        bar_id=None,
        payload=payload,
    )


def _ownership(db: Session, org: Organization, *, lock: bool = False) -> StructureOwnership:
    query = db.query(StructureOwnership).filter(StructureOwnership.organization_id == org.id)
    if lock:
        query = query.with_for_update()
    state = query.first()
    if state:
        return state

    owner_query = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org.id,
        OrganizationMembership.role == "OWNER",
        OrganizationMembership.status == "ACTIVE",
        OrganizationMembership.revoked_at.is_(None),
    )
    owners = []
    for membership in owner_query.order_by(OrganizationMembership.id.asc()).all():
        if _active_membership(db, org.id, membership.user_id):
            owners.append(membership)
    if len(owners) != 1:
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "ownership_ambiguous",
                "message": "La propriété historique ne peut pas être déterminée automatiquement; intervention TORÈ requise.",
            },
        )
    state = StructureOwnership(
        organization_id=org.id,
        primary_owner_user_id=owners[0].user_id,
        updated_at=now_utc(),
    )
    db.add(state)
    db.flush()
    _audit(
        db,
        action="ownership.bootstrap",
        org_id=org.id,
        actor_user_id=owners[0].user_id,
        actor_role="OWNER",
        payload={"primary_owner_user_id": owners[0].user_id},
    )
    return state


def _expire_transfers(db: Session, org_id: int) -> None:
    stamp = now_utc()
    rows = db.query(StructureOwnershipTransfer).filter(
        StructureOwnershipTransfer.organization_id == org_id,
        StructureOwnershipTransfer.status.in_(OPEN_TRANSFER_STATES),
        StructureOwnershipTransfer.expires_at <= stamp,
    ).with_for_update().all()
    for row in rows:
        row.status = "EXPIRED"
        _audit(
            db,
            action="ownership.transfer.expired",
            org_id=org_id,
            actor_user_id=None,
            actor_role="SYSTEM",
            payload={"transfer_id": row.id, "from": row.from_owner_user_id, "to": row.to_owner_user_id},
        )


def _ensure_not_frozen(state: StructureOwnership) -> None:
    if state.is_frozen:
        raise HTTPException(
            status_code=423,
            detail={"reason": "structure_frozen", "message": "Structure gelée: opération administrative critique bloquée."},
        )


def _capabilities(state: StructureOwnership, user_id: str) -> list[str]:
    capabilities: list[str] = []
    if user_id == state.primary_owner_user_id:
        capabilities.extend(["ownership.transfer", "ownership.recover"])
    elif user_id == state.recovery_owner_user_id:
        capabilities.append("ownership.recover")
    if state.is_frozen:
        capabilities = [item for item in capabilities if item == "ownership.recover"]
    return capabilities


def _require_capability(state: StructureOwnership, user_id: str, capability: str) -> None:
    if capability not in _capabilities(state, user_id):
        raise HTTPException(status_code=403, detail={"reason": "missing_capability", "capability": capability})


def _ownership_payload(db: Session, org: Organization, state: StructureOwnership, viewer_id: str) -> dict:
    _expire_transfers(db, org.id)
    pending = db.query(StructureOwnershipTransfer).filter(
        StructureOwnershipTransfer.organization_id == org.id,
        StructureOwnershipTransfer.status.in_(OPEN_TRANSFER_STATES),
    ).order_by(StructureOwnershipTransfer.id.desc()).first()
    recovery = db.query(StructureRecoveryRequest).filter(
        StructureRecoveryRequest.organization_id == org.id,
        StructureRecoveryRequest.status.in_(OPEN_RECOVERY_STATES),
    ).order_by(StructureRecoveryRequest.id.desc()).first()
    return {
        "structureId": org.id,
        "slug": org.slug,
        "viewerUserId": viewer_id,
        "primaryOwnerUserId": state.primary_owner_user_id,
        "recoveryOwnerUserId": state.recovery_owner_user_id,
        "capabilities": _capabilities(state, viewer_id),
        "frozen": state.is_frozen,
        "keepPublicVisible": state.keep_public_visible,
        "frozenReason": state.frozen_reason,
        "pendingTransfer": None if not pending else {
            "id": pending.id,
            "status": pending.status,
            "fromUserId": pending.from_owner_user_id,
            "toUserId": pending.to_owner_user_id,
            "requestedAt": pending.requested_at.isoformat(),
            "expiresAt": pending.expires_at.isoformat(),
            "canConfirm": pending.to_owner_user_id == viewer_id and not state.is_frozen,
            "canCancel": viewer_id in {pending.from_owner_user_id, pending.to_owner_user_id},
        },
        "pendingRecovery": None if not recovery else {
            "id": recovery.id,
            "status": recovery.status,
            "requestedByUserId": recovery.requested_by_user_id,
            "reason": recovery.reason,
            "requestedAt": recovery.requested_at.isoformat(),
            "canApprove": viewer_id == state.primary_owner_user_id,
        },
    }


def _complete_ownership_change(
    db: Session,
    org: Organization,
    state: StructureOwnership,
    *,
    new_owner_user_id: str,
    actor_user_id: Optional[str],
    actor_role: str,
    source: str,
    source_id: int,
) -> None:
    target = _active_membership(db, org.id, new_owner_user_id, lock=True)
    if not target:
        raise HTTPException(status_code=409, detail={"reason": "recovery_target_not_active_member"})
    previous_owner = state.primary_owner_user_id
    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org.id,
        OrganizationMembership.role == "OWNER",
        OrganizationMembership.status == "ACTIVE",
        OrganizationMembership.revoked_at.is_(None),
    ).with_for_update().all()
    for membership in memberships:
        if membership.user_id != new_owner_user_id:
            membership.role = "ADMIN"
    target.role = "OWNER"
    target.status = "ACTIVE"
    state.primary_owner_user_id = new_owner_user_id
    if state.recovery_owner_user_id == new_owner_user_id:
        state.recovery_owner_user_id = previous_owner if previous_owner != new_owner_user_id else None
    state.updated_at = now_utc()
    _audit(
        db,
        action="ownership.changed",
        org_id=org.id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        payload={
            "source": source,
            "source_id": source_id,
            "previous_owner_user_id": previous_owner,
            "new_owner_user_id": new_owner_user_id,
        },
    )


@router.get("/structures/{slug}/ownership")
def get_ownership(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _org(db, slug)
    if not _active_membership(db, org.id, user.id):
        raise HTTPException(status_code=403, detail={"reason": "structure_membership_required"})
    state = _ownership(db, org)
    payload = _ownership_payload(db, org, state, user.id)
    db.commit()
    return payload


@router.put("/structures/{slug}/ownership/recovery-owner")
def set_recovery_owner(
    slug: str,
    payload: RecoveryOwnerIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _org(db, slug, lock=True)
    state = _ownership(db, org, lock=True)
    _ensure_not_frozen(state)
    _require_capability(state, user.id, "ownership.recover")
    if user.id != state.primary_owner_user_id:
        raise HTTPException(status_code=403, detail={"reason": "primary_owner_required"})
    if payload.user_id == state.primary_owner_user_id:
        raise HTTPException(status_code=409, detail={"reason": "recovery_owner_must_differ"})
    if payload.user_id is not None and not _active_membership(db, org.id, payload.user_id):
        raise HTTPException(status_code=409, detail={"reason": "recovery_owner_must_be_active_member"})
    previous = state.recovery_owner_user_id
    state.recovery_owner_user_id = payload.user_id
    state.updated_at = now_utc()
    _audit(
        db,
        action="ownership.recovery_owner.updated",
        org_id=org.id,
        actor_user_id=user.id,
        actor_role="OWNER",
        payload={"previous_user_id": previous, "recovery_owner_user_id": payload.user_id},
    )
    db.commit()
    return _ownership_payload(db, org, state, user.id)


@router.post("/structures/{slug}/ownership/transfers")
def request_transfer(
    slug: str,
    payload: TransferRequestIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _org(db, slug, lock=True)
    state = _ownership(db, org, lock=True)
    _ensure_not_frozen(state)
    _require_capability(state, user.id, "ownership.transfer")
    if payload.to_user_id == user.id:
        raise HTTPException(status_code=409, detail={"reason": "transfer_target_is_current_owner"})
    if not _active_membership(db, org.id, payload.to_user_id):
        raise HTTPException(status_code=409, detail={"reason": "transfer_target_must_be_active_member"})
    _expire_transfers(db, org.id)
    existing = db.query(StructureOwnershipTransfer).filter(
        StructureOwnershipTransfer.organization_id == org.id,
        StructureOwnershipTransfer.status.in_(OPEN_TRANSFER_STATES),
    ).with_for_update().first()
    if existing:
        if existing.from_owner_user_id == user.id and existing.to_owner_user_id == payload.to_user_id:
            db.commit()
            return {"id": existing.id, "status": existing.status, "expiresAt": existing.expires_at.isoformat()}
        raise HTTPException(status_code=409, detail={"reason": "ownership_transfer_already_pending"})
    transfer = StructureOwnershipTransfer(
        organization_id=org.id,
        from_owner_user_id=state.primary_owner_user_id,
        to_owner_user_id=payload.to_user_id,
        requested_by_user_id=user.id,
        status="REQUESTED",
        requested_at=now_utc(),
        expires_at=now_utc() + timedelta(hours=TRANSFER_TTL_HOURS),
    )
    db.add(transfer)
    db.flush()
    _audit(
        db,
        action="ownership.transfer.requested",
        org_id=org.id,
        actor_user_id=user.id,
        actor_role="OWNER",
        payload={"transfer_id": transfer.id, "to_user_id": transfer.to_owner_user_id, "expires_at": transfer.expires_at.isoformat()},
    )
    db.commit()
    return {"id": transfer.id, "status": transfer.status, "expiresAt": transfer.expires_at.isoformat()}


@router.post("/structures/{slug}/ownership/transfers/{transfer_id}/confirm")
def confirm_transfer(
    slug: str,
    transfer_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _org(db, slug, lock=True)
    state = _ownership(db, org, lock=True)
    _ensure_not_frozen(state)
    transfer = db.query(StructureOwnershipTransfer).filter(
        StructureOwnershipTransfer.id == transfer_id,
        StructureOwnershipTransfer.organization_id == org.id,
    ).with_for_update().first()
    if not transfer:
        raise HTTPException(status_code=404, detail={"reason": "transfer_not_found"})
    if transfer.to_owner_user_id != user.id:
        raise HTTPException(status_code=403, detail={"reason": "transfer_target_required"})
    if transfer.status == "COMPLETED":
        return {"id": transfer.id, "status": transfer.status}
    if transfer.status != "REQUESTED":
        raise HTTPException(status_code=409, detail={"reason": "invalid_transfer_state", "state": transfer.status})
    if transfer.expires_at <= now_utc():
        transfer.status = "EXPIRED"
        _audit(db, action="ownership.transfer.expired", org_id=org.id, actor_user_id=user.id, actor_role="TARGET", payload={"transfer_id": transfer.id})
        db.commit()
        raise HTTPException(status_code=409, detail={"reason": "transfer_expired"})
    if state.primary_owner_user_id != transfer.from_owner_user_id:
        raise HTTPException(status_code=409, detail={"reason": "ownership_changed_since_request"})
    if not _active_membership(db, org.id, user.id):
        raise HTTPException(status_code=409, detail={"reason": "transfer_target_must_be_active_member"})
    transfer.status = "CONFIRMED"
    transfer.confirmed_at = now_utc()
    _audit(db, action="ownership.transfer.confirmed", org_id=org.id, actor_user_id=user.id, actor_role="TARGET", payload={"transfer_id": transfer.id})
    _complete_ownership_change(
        db, org, state,
        new_owner_user_id=user.id,
        actor_user_id=user.id,
        actor_role="TARGET",
        source="transfer",
        source_id=transfer.id,
    )
    transfer.status = "COMPLETED"
    transfer.completed_at = now_utc()
    _audit(db, action="ownership.transfer.completed", org_id=org.id, actor_user_id=user.id, actor_role="OWNER", payload={"transfer_id": transfer.id})
    db.commit()
    return {"id": transfer.id, "status": transfer.status, "primaryOwnerUserId": user.id}


@router.post("/structures/{slug}/ownership/transfers/{transfer_id}/cancel")
def cancel_transfer(
    slug: str,
    transfer_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _org(db, slug, lock=True)
    state = _ownership(db, org, lock=True)
    transfer = db.query(StructureOwnershipTransfer).filter(
        StructureOwnershipTransfer.id == transfer_id,
        StructureOwnershipTransfer.organization_id == org.id,
    ).with_for_update().first()
    if not transfer:
        raise HTTPException(status_code=404, detail={"reason": "transfer_not_found"})
    if user.id not in {transfer.from_owner_user_id, transfer.to_owner_user_id}:
        raise HTTPException(status_code=403, detail={"reason": "transfer_party_required"})
    if transfer.status not in OPEN_TRANSFER_STATES:
        if transfer.status == "CANCELLED":
            return {"id": transfer.id, "status": transfer.status}
        raise HTTPException(status_code=409, detail={"reason": "invalid_transfer_state", "state": transfer.status})
    transfer.status = "CANCELLED"
    transfer.cancelled_at = now_utc()
    transfer.cancelled_by_user_id = user.id
    _audit(db, action="ownership.transfer.cancelled", org_id=org.id, actor_user_id=user.id, actor_role="TRANSFER_PARTY", payload={"transfer_id": transfer.id})
    db.commit()
    return {"id": transfer.id, "status": transfer.status}


@router.post("/structures/{slug}/ownership/recovery")
def request_recovery(
    slug: str,
    payload: RecoveryRequestIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _org(db, slug, lock=True)
    state = _ownership(db, org, lock=True)
    _require_capability(state, user.id, "ownership.recover")
    if user.id != state.recovery_owner_user_id:
        raise HTTPException(status_code=403, detail={"reason": "configured_recovery_owner_required"})
    if not _active_membership(db, org.id, user.id):
        raise HTTPException(status_code=403, detail={"reason": "active_recovery_member_required"})
    existing = db.query(StructureRecoveryRequest).filter(
        StructureRecoveryRequest.organization_id == org.id,
        StructureRecoveryRequest.requested_by_user_id == user.id,
        StructureRecoveryRequest.status.in_(OPEN_RECOVERY_STATES),
    ).with_for_update().first()
    if existing:
        return {"id": existing.id, "status": existing.status}
    recovery = StructureRecoveryRequest(
        organization_id=org.id,
        requested_by_user_id=user.id,
        status="REQUESTED",
        reason=payload.reason.strip(),
        requested_at=now_utc(),
    )
    db.add(recovery)
    db.flush()
    _audit(
        db,
        action="ownership.recovery.requested",
        org_id=org.id,
        actor_user_id=user.id,
        actor_role="RECOVERY_OWNER",
        payload={"recovery_id": recovery.id, "frozen": state.is_frozen},
    )
    db.commit()
    return {"id": recovery.id, "status": recovery.status}


@router.post("/structures/{slug}/ownership/recoveries/{recovery_id}/approve")
def approve_recovery(
    slug: str,
    recovery_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _org(db, slug, lock=True)
    state = _ownership(db, org, lock=True)
    if user.id != state.primary_owner_user_id:
        raise HTTPException(status_code=403, detail={"reason": "primary_owner_required"})
    recovery = db.query(StructureRecoveryRequest).filter(
        StructureRecoveryRequest.id == recovery_id,
        StructureRecoveryRequest.organization_id == org.id,
    ).with_for_update().first()
    if not recovery:
        raise HTTPException(status_code=404, detail={"reason": "recovery_not_found"})
    if recovery.status != "REQUESTED":
        raise HTTPException(status_code=409, detail={"reason": "invalid_recovery_state", "state": recovery.status})
    if recovery.requested_by_user_id != state.recovery_owner_user_id:
        raise HTTPException(status_code=409, detail={"reason": "recovery_owner_changed"})
    _complete_ownership_change(
        db, org, state,
        new_owner_user_id=recovery.requested_by_user_id,
        actor_user_id=user.id,
        actor_role="OWNER",
        source="recovery_owner_approval",
        source_id=recovery.id,
    )
    recovery.status = "APPROVED"
    recovery.resolved_at = now_utc()
    recovery.resolved_by_user_id = user.id
    recovery.resolution_reason = "Approved by current primary owner"
    _audit(db, action="ownership.recovery.approved", org_id=org.id, actor_user_id=user.id, actor_role="OWNER", payload={"recovery_id": recovery.id})
    db.commit()
    return {"id": recovery.id, "status": recovery.status, "primaryOwnerUserId": recovery.requested_by_user_id}


@router.post("/admin/structures/{slug}/freeze")
def admin_freeze_structure(
    slug: str,
    payload: AdminFreezeIn,
    admin: str = Depends(_admin_key),
    db: Session = Depends(get_db),
):
    org = _org(db, slug, lock=True)
    state = _ownership(db, org, lock=True)
    state.is_frozen = True
    state.keep_public_visible = payload.keep_public_visible
    state.frozen_reason = payload.reason.strip()
    state.frozen_at = now_utc()
    state.frozen_by = admin
    state.updated_at = now_utc()
    _audit(
        db,
        action="ownership.freeze",
        org_id=org.id,
        actor_user_id=None,
        actor_role="TORE_ADMIN",
        payload={"reason": state.frozen_reason, "keep_public_visible": state.keep_public_visible},
    )
    db.commit()
    return {"frozen": True, "keepPublicVisible": state.keep_public_visible}


@router.post("/admin/structures/{slug}/unfreeze")
def admin_unfreeze_structure(
    slug: str,
    admin: str = Depends(_admin_key),
    db: Session = Depends(get_db),
):
    org = _org(db, slug, lock=True)
    state = _ownership(db, org, lock=True)
    previous_reason = state.frozen_reason
    state.is_frozen = False
    state.frozen_reason = None
    state.frozen_at = None
    state.frozen_by = None
    state.updated_at = now_utc()
    _audit(db, action="ownership.unfreeze", org_id=org.id, actor_user_id=None, actor_role="TORE_ADMIN", payload={"previous_reason": previous_reason})
    db.commit()
    return {"frozen": False}


@router.post("/admin/structures/{slug}/recoveries/{recovery_id}/resolve")
def admin_resolve_recovery(
    slug: str,
    recovery_id: int,
    payload: AdminRecoveryResolveIn,
    admin: str = Depends(_admin_key),
    db: Session = Depends(get_db),
):
    org = _org(db, slug, lock=True)
    state = _ownership(db, org, lock=True)
    recovery = db.query(StructureRecoveryRequest).filter(
        StructureRecoveryRequest.id == recovery_id,
        StructureRecoveryRequest.organization_id == org.id,
    ).with_for_update().first()
    if not recovery:
        raise HTTPException(status_code=404, detail={"reason": "recovery_not_found"})
    if recovery.status != "REQUESTED":
        raise HTTPException(status_code=409, detail={"reason": "invalid_recovery_state", "state": recovery.status})
    if payload.approve:
        _complete_ownership_change(
            db, org, state,
            new_owner_user_id=recovery.requested_by_user_id,
            actor_user_id=None,
            actor_role="TORE_ADMIN",
            source="tore_admin_recovery",
            source_id=recovery.id,
        )
        recovery.status = "APPROVED"
        action = "ownership.recovery.admin_approved"
    else:
        recovery.status = "REJECTED"
        action = "ownership.recovery.admin_rejected"
    recovery.resolved_at = now_utc()
    recovery.resolved_by_admin = admin
    recovery.resolution_reason = payload.reason.strip()
    _audit(
        db,
        action=action,
        org_id=org.id,
        actor_user_id=None,
        actor_role="TORE_ADMIN",
        payload={"recovery_id": recovery.id, "reason": recovery.resolution_reason},
    )
    db.commit()
    return {"id": recovery.id, "status": recovery.status, "primaryOwnerUserId": state.primary_owner_user_id}


def _request_actor_id(db: Session, request: Request) -> Optional[str]:
    header = (request.headers.get("authorization") or "").strip()
    if not header.lower().startswith("bearer "):
        return None
    raw = header[7:].strip().strip('"').strip("'")
    if not raw:
        return None
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    token = db.query(AppToken).filter(AppToken.token_hash == token_hash, AppToken.revoked_at.is_(None)).first()
    return token.user_id if token else None


async def freeze_guard_middleware(request: Request, call_next):
    path = request.url.path
    method = request.method.upper()
    forum_match = STRUCTURE_PATH_RE.match(path)
    orga_match = ORGA_PATH_RE.match(path)

    if not forum_match and not orga_match:
        return await call_next(request)

    # Ownership recovery/admin endpoints carry their own stricter freeze semantics.
    if forum_match and "/ownership/" in path:
        return await call_next(request)

    db = SessionLocal()
    try:
        if forum_match:
            slug = forum_match.group(1)
            org = db.query(Organization).filter(Organization.slug == slug).first()
        else:
            org = db.get(Organization, int(orga_match.group(1)))
        if not org:
            return await call_next(request)
        state = db.query(StructureOwnership).filter(StructureOwnership.organization_id == org.id).first()
        if not state or not state.is_frozen:
            return await call_next(request)

        if method == "GET" and forum_match and path == f"/forum/structures/{org.slug}" and state.keep_public_visible:
            return await call_next(request)
        if method not in CRITICAL_METHODS and not (
            method == "GET" and forum_match and path == f"/forum/structures/{org.slug}" and not state.keep_public_visible
        ):
            return await call_next(request)

        actor_id = _request_actor_id(db, request)
        _audit(
            db,
            action="ownership.freeze.blocked_operation",
            org_id=org.id,
            actor_user_id=actor_id,
            actor_role="USER" if actor_id else "ANONYMOUS",
            payload={"method": method, "path": path, "keep_public_visible": state.keep_public_visible},
        )
        db.commit()
        return JSONResponse(
            status_code=423,
            content={"detail": {"reason": "structure_frozen", "message": "Structure gelée par TORÈ; opération bloquée."}},
        )
    finally:
        db.close()
