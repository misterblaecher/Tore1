from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import now_utc
from models import AppUser, OrganizationMembership, StructureInvitation
from app.legacy.monolith import get_current_user
from app.deps.db import get_db
from app.models.structure_rbac import StructureMembershipRole, StructureRole
from app.routers.forum import _structure_or_404
from app.routers.forum_invitations import _INVITATION_STATES, _client_rate_key, _deliver, _expires_at, _lookup_token, _new_token, _not_available, _payload, _rate, _recipient_rate_key, _status
from app.services.audit_service import write_audit_log
from app.services.structure_rbac import SYSTEM_ROLE_CAPABILITIES, SYSTEM_ROLE_CODES, capabilities_for_membership, ensure_rbac_catalog, normalize_role_code, require_capability, role_capabilities, scoped_role_or_404

router = APIRouter(prefix="/forum", tags=["forum-invitations-rbac"])
NON_DELEGABLE = {"ownership.transfer", "ownership.recover"}

class InviteIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    invited_role: str = Field(default="MEMBER", min_length=2, max_length=64)
    invited_role_id: Optional[int] = Field(default=None, gt=0)

def _actor(db: Session, org_id: int, user: AppUser):
    membership = require_capability(db, org_id, user, "member.invite")
    return membership, capabilities_for_membership(db, membership)

def _target(db: Session, org_id: int, actor_caps: set[str], code: str, role_id: Optional[int]):
    ensure_rbac_catalog(db)
    if role_id is not None:
        role = scoped_role_or_404(db, org_id, role_id)
        caps = role_capabilities(db, role.id)
        if (role.is_system and role.code == "OWNER") or caps & NON_DELEGABLE or not caps.issubset(actor_caps):
            raise HTTPException(403, detail={"reason": "INVITED_ROLE_NOT_ALLOWED"})
        return role
    code = normalize_role_code(code)
    if code == "OWNER" or code not in SYSTEM_ROLE_CODES:
        raise HTTPException(403, detail={"reason": "INVITED_ROLE_NOT_ALLOWED"})
    caps = set(SYSTEM_ROLE_CAPABILITIES[code])
    if caps & NON_DELEGABLE or not caps.issubset(actor_caps):
        raise HTTPException(403, detail={"reason": "INVITED_ROLE_EXCEEDS_GRANT_CEILING"})
    return db.query(StructureRole).filter(StructureRole.scope_key == f"system:{code}").one()

def _allowed(db: Session, org_id: int, actor_caps: set[str]):
    ensure_rbac_catalog(db)
    system = [code for code in SYSTEM_ROLE_CODES if code != "OWNER" and not (set(SYSTEM_ROLE_CAPABILITIES[code]) & NON_DELEGABLE) and set(SYSTEM_ROLE_CAPABILITIES[code]).issubset(actor_caps)]
    custom = []
    for role in db.query(StructureRole).filter(StructureRole.organization_id == org_id).order_by(StructureRole.name).all():
        caps = role_capabilities(db, role.id)
        if not (caps & NON_DELEGABLE) and caps.issubset(actor_caps):
            custom.append({"id": role.id, "code": role.code, "name": role.name})
    return system, custom

def _audit(db, actor, action, row, org_id):
    write_audit_log(db, actor_partner_id=None, actor_user_id=actor.id, actor_role=actor.role, action=action, entity_type="structure_invitation", entity_id=str(row.id), event_id=None, committee_id=None, bar_id=None, payload={"structure_id": org_id, "invited_role": row.invited_role, "invited_role_id": row.invited_role_id})

@router.get("/structures/{slug}/invitations")
def list_invitations(slug: str, invitation_status: Optional[str] = Query(default=None, alias="status"), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); _, caps = _actor(db, org.id, user)
    wanted = invitation_status.strip().upper() if invitation_status else None
    if wanted and wanted not in _INVITATION_STATES: raise HTTPException(400, detail={"reason": "INVALID_INVITATION_STATUS"})
    rows = db.query(StructureInvitation).filter(StructureInvitation.structure_id == org.id).order_by(StructureInvitation.created_at.desc()).all()
    system, custom = _allowed(db, org.id, caps)
    return {"items": [_payload(row) | {"invitedRoleId": row.invited_role_id} for row in rows if wanted is None or _status(row) == wanted], "allowedRoles": system, "allowedCustomRoles": custom}

@router.post("/structures/{slug}/invitations", status_code=status.HTTP_202_ACCEPTED)
def create_invitation(slug: str, payload: InviteIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); actor, caps = _actor(db, org.id, user)
    email = payload.email.strip().lower()
    if "@" not in email: raise HTTPException(422, detail={"reason": "INVALID_EMAIL"})
    role = _target(db, org.id, caps, payload.invited_role, payload.invited_role_id)
    _rate("forum_invitation_actor", f"{user.id}:{org.id}"); _rate("forum_invitation_recipient", f"{org.id}:{_recipient_rate_key(email)}")
    now = now_utc(); row = db.query(StructureInvitation).filter(StructureInvitation.structure_id == org.id, StructureInvitation.email == email, StructureInvitation.accepted_at.is_(None), StructureInvitation.declined_at.is_(None), StructureInvitation.revoked_at.is_(None), StructureInvitation.expires_at > now).first()
    token, digest = _new_token()
    if row is None:
        row = StructureInvitation(structure_id=org.id, email=email, token_hash=digest, invited_role=role.code, invited_role_id=role.id, invited_by=user.id, expires_at=_expires_at(), created_at=now); db.add(row)
    else:
        row.token_hash=digest; row.invited_role=role.code; row.invited_role_id=role.id; row.invited_by=user.id; row.expires_at=_expires_at()
    db.flush(); delivery = _deliver(row, token, org.name); _audit(db, actor, "forum.invitation.create", row, org.id); db.commit(); db.refresh(row)
    return _payload(row, share_token=token, delivery_status=delivery) | {"invitedRoleId": row.invited_role_id}

@router.post("/structures/{slug}/invitations/{invitation_id}/resend", status_code=status.HTTP_202_ACCEPTED)
def resend(slug: str, invitation_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org=_structure_or_404(db,slug); actor,caps=_actor(db,org.id,user); row=db.query(StructureInvitation).filter_by(id=invitation_id,structure_id=org.id).with_for_update().first()
    if row is None: raise HTTPException(404,detail="Invitation not found")
    if _status(row) not in {"PENDING","EXPIRED"}: raise HTTPException(409,detail={"reason":"INVITATION_CANNOT_BE_RESENT"})
    _target(db,org.id,caps,row.invited_role,row.invited_role_id); token,digest=_new_token(); row.token_hash=digest; row.invited_by=user.id; row.expires_at=_expires_at(); db.flush(); delivery=_deliver(row,token,org.name); _audit(db,actor,"forum.invitation.resend",row,org.id); db.commit(); db.refresh(row)
    return _payload(row,share_token=token,delivery_status=delivery) | {"invitedRoleId":row.invited_role_id}

@router.post("/structures/{slug}/invitations/{invitation_id}/revoke")
def revoke(slug: str, invitation_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org=_structure_or_404(db,slug); actor,_=_actor(db,org.id,user); row=db.query(StructureInvitation).filter_by(id=invitation_id,structure_id=org.id).with_for_update().first()
    if row is None: raise HTTPException(404,detail="Invitation not found")
    if _status(row) in {"ACCEPTED","DECLINED","REVOKED"}: raise HTTPException(409,detail={"reason":"INVITATION_CANNOT_BE_REVOKED"})
    row.revoked_at=now_utc(); _audit(db,actor,"forum.invitation.revoke",row,org.id); db.commit(); return {"ok":True,"id":row.id,"status":"REVOKED","revokedAt":row.revoked_at.isoformat()}

@router.post("/invitations/{token}/accept")
def accept(token: str, request: Request, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _rate("forum_invitation_consume", _client_rate_key(request)); row=_lookup_token(db,token,lock=True)
    if row is None or _status(row) != "PENDING": raise _not_available()
    if (user.email or "").strip().lower() != row.email: raise HTTPException(403,detail={"reason":"INVITATION_ACCOUNT_MISMATCH"})
    ensure_rbac_catalog(db); role=_target(db,row.structure_id,set(SYSTEM_ROLE_CAPABILITIES["OWNER"]),row.invited_role,row.invited_role_id); now=now_utc()
    membership=db.query(OrganizationMembership).filter_by(organization_id=row.structure_id,user_id=user.id).with_for_update().first()
    if membership is None:
        membership=OrganizationMembership(organization_id=row.structure_id,user_id=user.id,role=role.code,status="ACTIVE",visibility="PRIVATE",created_by_user_id=row.invited_by,created_at=now,joined_at=now,starts_at=now); db.add(membership); db.flush()
    elif (membership.role or "").upper() != "OWNER":
        membership.role=role.code; membership.status="ACTIVE"; membership.revoked_at=None; membership.starts_at=membership.starts_at or now
    if (membership.role or "").upper() != "OWNER":
        db.query(StructureMembershipRole).filter_by(membership_id=membership.id).delete(synchronize_session=False); db.add(StructureMembershipRole(membership_id=membership.id,role_id=role.id,assigned_by_user_id=row.invited_by))
    membership.validated_by_user_id=user.id; membership.validated_at=now; membership.validation_source="EMAIL_INVITATION"; membership.updated_at=now; row.accepted_at=now; db.commit()
    return {"ok":True,"status":"ACCEPTED","role":membership.role}
