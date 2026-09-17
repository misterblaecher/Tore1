from __future__ import annotations

import re
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from db import now_utc
from models import AppUser, OrganizationMembership
from app.models.structure_rbac import (
    StructureCapability,
    StructureMembershipRole,
    StructureRole,
    StructureRoleCapability,
)


STRUCTURE_CAPABILITIES: tuple[str, ...] = (
    "structure.read",
    "structure.edit",
    "structure.publish",
    "member.read",
    "member.invite",
    "member.manage",
    "member.role.manage",
    "member.mandate.manage",
    "discussion.read",
    "discussion.write",
    "discussion.manage",
    "channel.create",
    "channel.manage",
    "event.read",
    "event.create",
    "event.manage",
    "event.publish",
    "event.recap.manage",
    "document.read",
    "document.manage",
    "document.publish",
    "album.read",
    "album.manage",
    "album.publish",
    "page.read",
    "page.manage",
    "page.publish",
    "planning.read",
    "planning.manage",
    "stats.read",
    "finance.read",
    "finance.write",
    "finance.review",
    "finance.lock",
    "finance.export",
    "visibility.manage",
    "audit.read",
    "ownership.transfer",
    "ownership.recover",
    "export.create",
)

_BASE_MEMBER = {
    "structure.read", "member.read", "discussion.read", "discussion.write",
    "event.read", "document.read", "album.read", "page.read", "planning.read", "stats.read",
}
_COMMUNICATION = _BASE_MEMBER | {
    "structure.edit", "structure.publish", "event.create", "event.manage", "event.publish",
    "event.recap.manage", "album.manage", "album.publish", "page.manage", "page.publish",
    "visibility.manage", "export.create",
}
_ARCHIVE = _BASE_MEMBER | {
    "event.recap.manage", "document.manage", "document.publish", "album.manage", "album.publish",
    "page.manage", "page.publish", "export.create",
}
_SECRETARY = _BASE_MEMBER | {
    "member.invite", "member.manage", "member.mandate.manage", "discussion.manage",
    "channel.create", "channel.manage", "event.create", "event.manage", "document.manage",
    "document.publish", "planning.manage", "export.create", "audit.read",
}
_TREASURY = _BASE_MEMBER | {
    "finance.read", "finance.write", "finance.review", "finance.lock", "finance.export", "export.create",
}
_MANAGEMENT = set(STRUCTURE_CAPABILITIES) - {"ownership.transfer", "ownership.recover"}
_ADMIN = set(STRUCTURE_CAPABILITIES) - {"ownership.transfer", "ownership.recover"}

# Important: these are explicit capability sets. No role inherits from another role at runtime.
SYSTEM_ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    "OWNER": frozenset(STRUCTURE_CAPABILITIES),
    "PRESIDENT": frozenset(_MANAGEMENT),
    "VICE_PRESIDENT": frozenset(_MANAGEMENT),
    "ADMIN": frozenset(_ADMIN),
    "MANAGER": frozenset(_MANAGEMENT),
    "TREASURER": frozenset(_TREASURY),
    "SECRETARY": frozenset(_SECRETARY),
    "COMMUNICATION": frozenset(_COMMUNICATION),
    "ARCHIVIST": frozenset(_ARCHIVE),
    "STAFF": frozenset(_BASE_MEMBER),
    "MEMBER": frozenset(_BASE_MEMBER),
}

SYSTEM_ROLE_CODES: tuple[str, ...] = tuple(SYSTEM_ROLE_CAPABILITIES)
LEGACY_ROLE_ALIASES = {
    "TRESORIER": "TREASURER",
    "BUREAU": "MANAGER",
}


def normalize_role_code(value: str) -> str:
    raw = re.sub(r"[^A-Z0-9]+", "_", (value or "").strip().upper()).strip("_")
    return raw[:64] or "MEMBER"


def _active_membership(db: Session, organization_id: int, user_id: str) -> Optional[OrganizationMembership]:
    now = now_utc()
    return db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.status == "ACTIVE",
        OrganizationMembership.revoked_at.is_(None),
        or_(OrganizationMembership.starts_at.is_(None), OrganizationMembership.starts_at <= now),
        or_(OrganizationMembership.ends_at.is_(None), OrganizationMembership.ends_at > now),
    ).first()


def fallback_capabilities_for_legacy_role(role: str) -> set[str]:
    code = normalize_role_code(role)
    code = LEGACY_ROLE_ALIASES.get(code, code)
    return set(SYSTEM_ROLE_CAPABILITIES.get(code, frozenset()))


def capabilities_for_membership(db: Session, membership: OrganizationMembership) -> set[str]:
    assignments = db.query(StructureMembershipRole).filter(
        StructureMembershipRole.membership_id == membership.id
    ).all()
    if not assignments:
        # Temporary compatibility path for fresh/local DBs and deployments during rolling migration.
        return fallback_capabilities_for_legacy_role(membership.role or "MEMBER")

    role_ids = [item.role_id for item in assignments]
    roles = db.query(StructureRole).filter(StructureRole.id.in_(role_ids)).all()
    allowed_role_ids = {
        role.id for role in roles
        if role.organization_id is None or role.organization_id == membership.organization_id
    }
    if not allowed_role_ids:
        # Explicit but invalid cross-Structure assignments must never fall back to the legacy role.
        return set()

    rows = db.query(StructureCapability.key).join(
        StructureRoleCapability,
        StructureRoleCapability.capability_id == StructureCapability.id,
    ).filter(StructureRoleCapability.role_id.in_(allowed_role_ids)).all()
    return {row[0] for row in rows}


def capabilities_for_user(db: Session, organization_id: int, user_id: str) -> tuple[OrganizationMembership, set[str]]:
    membership = _active_membership(db, organization_id, user_id)
    if membership is None:
        raise HTTPException(
            status_code=403,
            detail={"reason": "FORUM_CAPABILITY_DENIED", "capability": "structure.read"},
        )
    return membership, capabilities_for_membership(db, membership)


def require_capability(
    db: Session,
    organization_id: int,
    user: AppUser,
    capability: str,
) -> OrganizationMembership:
    if capability not in STRUCTURE_CAPABILITIES:
        raise RuntimeError(f"Unknown Structure capability: {capability}")
    membership, capabilities = capabilities_for_user(db, organization_id, user.id)
    if capability not in capabilities:
        raise HTTPException(
            status_code=403,
            detail={"reason": "FORUM_CAPABILITY_DENIED", "capability": capability},
        )
    return membership


def ensure_rbac_catalog(db: Session) -> None:
    existing_caps = {row.key: row for row in db.query(StructureCapability).all()}
    for key in STRUCTURE_CAPABILITIES:
        if key not in existing_caps:
            row = StructureCapability(key=key)
            db.add(row)
            db.flush()
            existing_caps[key] = row

    for code, keys in SYSTEM_ROLE_CAPABILITIES.items():
        scope_key = f"system:{code}"
        role = db.query(StructureRole).filter(StructureRole.scope_key == scope_key).first()
        if role is None:
            role = StructureRole(
                organization_id=None,
                scope_key=scope_key,
                code=code,
                name=code.replace("_", " ").title(),
                is_system=True,
                is_legacy=False,
            )
            db.add(role)
            db.flush()
        current = {
            row.capability_id for row in db.query(StructureRoleCapability).filter(
                StructureRoleCapability.role_id == role.id
            ).all()
        }
        for key in keys:
            cap_id = existing_caps[key].id
            if cap_id not in current:
                db.add(StructureRoleCapability(role_id=role.id, capability_id=cap_id))


def role_capabilities(db: Session, role_id: int) -> set[str]:
    rows = db.query(StructureCapability.key).join(
        StructureRoleCapability,
        StructureRoleCapability.capability_id == StructureCapability.id,
    ).filter(StructureRoleCapability.role_id == role_id).all()
    return {row[0] for row in rows}


def set_role_capabilities(db: Session, role: StructureRole, capabilities: Iterable[str]) -> None:
    requested = {str(item).strip() for item in capabilities if str(item).strip()}
    unknown = requested - set(STRUCTURE_CAPABILITIES)
    if unknown:
        raise HTTPException(status_code=422, detail={"reason": "UNKNOWN_CAPABILITY", "capabilities": sorted(unknown)})
    if role.is_system:
        raise HTTPException(status_code=409, detail={"reason": "SYSTEM_ROLE_IMMUTABLE"})

    ensure_rbac_catalog(db)
    db.query(StructureRoleCapability).filter(StructureRoleCapability.role_id == role.id).delete(
        synchronize_session=False
    )
    if requested:
        rows = db.query(StructureCapability).filter(StructureCapability.key.in_(requested)).all()
        for row in rows:
            db.add(StructureRoleCapability(role_id=role.id, capability_id=row.id))
    role.updated_at = now_utc()


def scoped_role_or_404(db: Session, organization_id: int, role_id: int) -> StructureRole:
    role = db.get(StructureRole, role_id)
    if role is None or (role.organization_id is not None and role.organization_id != organization_id):
        raise HTTPException(status_code=404, detail="Structure role not found")
    return role
