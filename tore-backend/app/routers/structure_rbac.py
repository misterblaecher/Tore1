from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import now_utc
from models import AppUser, Organization, OrganizationMembership
from app.core.security.user_auth import get_current_user
from app.deps.db import get_db
from app.models.structure_rbac import StructureMembershipRole, StructureRole
from app.services.structure_rbac import (
    SYSTEM_ROLE_CODES,
    STRUCTURE_CAPABILITIES,
    capabilities_for_membership,
    ensure_rbac_catalog,
    normalize_role_code,
    require_capability,
    role_capabilities,
    scoped_role_or_404,
    set_role_capabilities,
)


router = APIRouter(prefix="/forum", tags=["forum-rbac"])


class StructureRoleCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: Optional[str] = Field(default=None, max_length=64)
    capabilities: list[str] = Field(default_factory=list, max_length=len(STRUCTURE_CAPABILITIES))


class StructureRoleCapabilitiesIn(BaseModel):
    capabilities: list[str] = Field(default_factory=list, max_length=len(STRUCTURE_CAPABILITIES))


class MembershipRolesIn(BaseModel):
    role_ids: list[int] = Field(min_length=1, max_length=12)


def _org_by_slug(db: Session, slug: str) -> Organization:
    row = db.query(Organization).filter(Organization.slug == slug.strip()).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Structure not found")
    return row


def _role_payload(db: Session, row: StructureRole) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "system": bool(row.is_system),
        "legacy": bool(row.is_legacy),
        "capabilities": sorted(role_capabilities(db, row.id)),
    }


def _assert_no_escalation(db: Session, actor: OrganizationMembership, requested: set[str]) -> None:
    actor_caps = capabilities_for_membership(db, actor)
    missing = requested - actor_caps
    if missing:
        raise HTTPException(
            status_code=403,
            detail={"reason": "ROLE_CAPABILITY_ESCALATION", "capabilities": sorted(missing)},
        )


@router.get("/structures/{slug}/workspace")
def get_structure_workspace_capabilities(
    slug: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return server-resolved capabilities for UI composition.

    The UI may hide controls from this response, but every sensitive endpoint still
    validates the corresponding capability server-side.
    """
    org = _org_by_slug(db, slug)
    membership = require_capability(db, org.id, user, "structure.read")
    caps = sorted(capabilities_for_membership(db, membership))
    assignments = db.query(StructureMembershipRole).filter(
        StructureMembershipRole.membership_id == membership.id
    ).all()
    role_ids = [row.role_id for row in assignments]
    roles = []
    if role_ids:
        rows = db.query(StructureRole).filter(StructureRole.id.in_(role_ids)).all()
        roles = [
            _role_payload(db, role) for role in rows
            if role.organization_id is None or role.organization_id == org.id
        ]
    return {
        "structure": {"id": org.id, "slug": org.slug, "name": org.name},
        "membership": {
            "id": membership.id,
            "legacyRole": (membership.role or "MEMBER").upper(),
            "roles": roles,
        },
        "capabilities": caps,
    }


@router.get("/structures/{slug}/roles")
def list_structure_roles(
    slug: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _org_by_slug(db, slug)
    require_capability(db, org.id, user, "member.read")
    ensure_rbac_catalog(db)
    db.commit()
    rows = db.query(StructureRole).filter(
        (StructureRole.organization_id.is_(None)) | (StructureRole.organization_id == org.id)
    ).order_by(StructureRole.is_system.desc(), StructureRole.code.asc()).all()
    return {"items": [_role_payload(db, row) for row in rows]}


@router.post("/structures/{slug}/roles")
def create_custom_structure_role(
    slug: str,
    payload: StructureRoleCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _org_by_slug(db, slug)
    actor = require_capability(db, org.id, user, "member.role.manage")
    ensure_rbac_catalog(db)
    requested = {item.strip() for item in payload.capabilities if item.strip()}
    _assert_no_escalation(db, actor, requested)

    code = normalize_role_code(payload.code or payload.name)
    if code in SYSTEM_ROLE_CODES:
        raise HTTPException(status_code=409, detail={"reason": "SYSTEM_ROLE_CODE_RESERVED"})
    scope_key = f"org:{org.id}:{code}"
    if db.query(StructureRole).filter(StructureRole.scope_key == scope_key).first() is not None:
        raise HTTPException(status_code=409, detail={"reason": "ROLE_CODE_ALREADY_EXISTS"})

    role = StructureRole(
        organization_id=org.id,
        scope_key=scope_key,
        code=code,
        name=payload.name.strip(),
        is_system=False,
        is_legacy=False,
        created_by_user_id=user.id,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(role)
    db.flush()
    set_role_capabilities(db, role, requested)
    db.commit()
    db.refresh(role)
    return _role_payload(db, role)


@router.put("/structures/{slug}/roles/{role_id}/capabilities")
def replace_custom_role_capabilities(
    slug: str,
    role_id: int,
    payload: StructureRoleCapabilitiesIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _org_by_slug(db, slug)
    actor = require_capability(db, org.id, user, "member.role.manage")
    role = scoped_role_or_404(db, org.id, role_id)
    requested = {item.strip() for item in payload.capabilities if item.strip()}
    _assert_no_escalation(db, actor, requested)
    set_role_capabilities(db, role, requested)
    db.commit()
    db.refresh(role)
    return _role_payload(db, role)


@router.put("/structures/{slug}/members/{member_user_id}/roles")
def replace_membership_roles(
    slug: str,
    member_user_id: str,
    payload: MembershipRolesIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _org_by_slug(db, slug)
    actor = require_capability(db, org.id, user, "member.role.manage")
    target = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org.id,
        OrganizationMembership.user_id == member_user_id,
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Member not found")

    unique_ids = list(dict.fromkeys(payload.role_ids))
    roles = [scoped_role_or_404(db, org.id, role_id) for role_id in unique_ids]
    granted = set().union(*(role_capabilities(db, role.id) for role in roles)) if roles else set()
    _assert_no_escalation(db, actor, granted)

    db.query(StructureMembershipRole).filter(
        StructureMembershipRole.membership_id == target.id
    ).delete(synchronize_session=False)
    for role in roles:
        db.add(StructureMembershipRole(
            membership_id=target.id,
            role_id=role.id,
            assigned_by_user_id=user.id,
            created_at=now_utc(),
        ))
    db.commit()
    return {
        "membershipId": target.id,
        "userId": target.user_id,
        "roles": [_role_payload(db, role) for role in roles],
        "capabilities": sorted(capabilities_for_membership(db, target)),
    }
