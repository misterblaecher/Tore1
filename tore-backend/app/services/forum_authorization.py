from __future__ import annotations

"""Server-side authorization and visibility primitives for TORÈ Forum.

No caller-provided ``organization_id`` is trusted as an authorization claim.  The
organization is resolved first, then membership/role/permission decisions are
recomputed from the database for every request.
"""

from dataclasses import dataclass
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from db import now_utc
from models import AppUser, Organization, OrganizationMembership
from app.forum_models import (
    StructureGovernance,
    StructurePublicPage,
    StructureRole,
    StructureRoleAssignment,
    VisibilityPolicy,
)


NON_DELEGABLE_PERMISSIONS = frozenset({
    "structure.admin",
    "ownership.transfer",
    "accounting.unlock",
})

ALL_PERMISSIONS = frozenset({
    "structure.read", "structure.manage", "structure.admin", "ownership.transfer",
    "members.view", "members.manage", "roles.manage", "visibility.manage",
    "events.view", "events.manage", "events.publish",
    "stats.view", "accounting.view", "accounting.manage", "accounting.unlock",
    "channels.read", "channels.post", "channels.manage",
    "documents.view", "documents.download", "documents.manage",
    "albums.view", "albums.manage", "folklore.view", "folklore.manage",
    "publications.manage", "audit.view", "search.view",
})

SYSTEM_ROLE_DEFINITIONS = {
    "Owner": {
        "audience": "PRIVATE",
        "permissions": sorted(ALL_PERMISSIONS),
    },
    "Bureau": {
        "audience": "BUREAU",
        "permissions": sorted({
            "structure.read", "structure.manage", "members.view", "members.manage", "roles.manage",
            "visibility.manage", "events.view", "events.manage", "events.publish", "stats.view",
            "channels.read", "channels.post", "channels.manage", "documents.view", "documents.download",
            "documents.manage", "albums.view", "albums.manage", "folklore.view", "folklore.manage",
            "publications.manage", "audit.view", "search.view",
        }),
    },
    "Trésorerie": {
        "audience": "TREASURY",
        "permissions": sorted({
            "structure.read", "members.view", "events.view", "stats.view", "accounting.view",
            "accounting.manage", "channels.read", "channels.post", "documents.view", "documents.download",
            "albums.view", "folklore.view", "audit.view", "search.view",
        }),
    },
    "Staff": {
        "audience": "STAFF",
        "permissions": sorted({
            "structure.read", "members.view", "events.view", "stats.view", "channels.read", "channels.post",
            "documents.view", "documents.download", "albums.view", "folklore.view", "search.view",
        }),
    },
    "Membre": {
        "audience": "MEMBERS",
        "permissions": sorted({
            "structure.read", "members.view", "events.view", "channels.read", "channels.post",
            "documents.view", "documents.download", "albums.view", "folklore.view", "search.view",
        }),
    },
}

LEGACY_ROLE_TO_SYSTEM = {
    "OWNER": "Owner",
    "ADMIN": "Bureau",
    "PRESIDENT": "Bureau",
    "VICE_PRESIDENT": "Bureau",
    "BUREAU": "Bureau",
    "SECRETARY": "Bureau",
    "MANAGER": "Bureau",
    "TREASURER": "Trésorerie",
    "TRESORIER": "Trésorerie",
    "STAFF": "Staff",
    "COMMUNICATION": "Staff",
    "ARCHIVIST": "Staff",
    "MEMBER": "Membre",
}

AUDIENCE_RANK = {
    "PUBLIC": 0,
    "TORE": 1,
    "MEMBERS": 2,
    "STAFF": 3,
    "BUREAU": 4,
    "TREASURY": 5,
    "PRIVATE": 6,
}

VISIBILITY_ALIASES = {
    "PUBLIC": "PUBLIC",
    "TORE": "TORE",
    "TORE_USERS": "TORE",
    "MEMBERS": "MEMBERS",
    "STRUCTURE_MEMBERS": "MEMBERS",
    "STAFF": "STAFF",
    "BUREAU": "BUREAU",
    "OFFICE": "BUREAU",
    "TREASURY": "TREASURY",
    "TRESORERIE": "TREASURY",
    "PRIVE": "PRIVATE",
    "PRIVATE": "PRIVATE",
    "ADMINS": "PRIVATE",
}

DEFAULT_SECTION_VISIBILITY = {
    "presentation": "PUBLIC",
    "events": "PUBLIC",
    "members": "PUBLIC",
    "albums": "PUBLIC",
    "folklore": "PUBLIC",
    "contact": "PUBLIC",
    "publications": "PUBLIC",
    "documents": "MEMBERS",
    "stats": "PRIVATE",
}


@dataclass(frozen=True)
class AuthorizationContext:
    user: AppUser
    organization: Organization
    membership: OrganizationMembership
    role: StructureRole
    permissions: frozenset[str]
    audience_level: str
    is_owner: bool


class AuthorizationService:
    @staticmethod
    def active_membership(db: Session, organization_id: int, user_id: str) -> Optional[OrganizationMembership]:
        stamp = now_utc()
        return db.query(OrganizationMembership).filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == "ACTIVE",
            OrganizationMembership.revoked_at.is_(None),
            or_(OrganizationMembership.starts_at.is_(None), OrganizationMembership.starts_at <= stamp),
            or_(OrganizationMembership.ends_at.is_(None), OrganizationMembership.ends_at > stamp),
        ).first()

    @classmethod
    def ensure_foundation(cls, db: Session, organization: Organization) -> bool:
        """Lazily upgrades legacy Organizations without creating a second structure model.

        Alembic creates/backfills these rows for existing data.  This fallback is
        also required for Organizations created by older mobile endpoints after
        the migration has shipped.
        """
        changed = False
        governance = db.get(StructureGovernance, organization.id)
        if governance is None:
            owner_membership = db.query(OrganizationMembership).filter(
                OrganizationMembership.organization_id == organization.id,
                OrganizationMembership.status == "ACTIVE",
                OrganizationMembership.revoked_at.is_(None),
                OrganizationMembership.role == "OWNER",
            ).first()
            owner_user_id = owner_membership.user_id if owner_membership else organization.created_by_user_id
            if not owner_user_id:
                raise HTTPException(status_code=409, detail={"reason": "STRUCTURE_OWNER_REQUIRED"})
            governance = StructureGovernance(
                organization_id=organization.id,
                owner_user_id=owner_user_id,
                status="ACTIVE",
                created_at=now_utc(),
                updated_at=now_utc(),
            )
            db.add(governance)
            changed = True

        public_page = db.get(StructurePublicPage, organization.id)
        if public_page is None:
            is_public = (organization.visibility or "PRIVATE").upper() == "PUBLIC"
            db.add(StructurePublicPage(
                organization_id=organization.id,
                status="PUBLISHED" if is_public else "DRAFT",
                published_at=organization.created_at if is_public else None,
                created_at=now_utc(),
                updated_at=now_utc(),
            ))
            changed = True

        role_by_name = {
            role.name: role
            for role in db.query(StructureRole).filter(StructureRole.organization_id == organization.id).all()
        }
        for name, definition in SYSTEM_ROLE_DEFINITIONS.items():
            role = role_by_name.get(name)
            if role is None:
                role = StructureRole(
                    organization_id=organization.id,
                    name=name,
                    system_role=True,
                    audience_level=definition["audience"],
                    permissions_json=list(definition["permissions"]),
                    created_by_user_id=governance.owner_user_id,
                    created_at=now_utc(),
                    updated_at=now_utc(),
                )
                db.add(role)
                db.flush()
                role_by_name[name] = role
                changed = True
            elif name == "Owner":
                required = set(SYSTEM_ROLE_DEFINITIONS["Owner"]["permissions"])
                current = set(role.permissions_json or [])
                if not role.system_role or not required.issubset(current) or role.audience_level != "PRIVATE":
                    role.system_role = True
                    role.audience_level = "PRIVATE"
                    role.permissions_json = sorted(current | required)
                    role.updated_at = now_utc()
                    changed = True

        memberships = db.query(OrganizationMembership).filter(
            OrganizationMembership.organization_id == organization.id
        ).all()
        for membership in memberships:
            assignment = db.query(StructureRoleAssignment).filter(
                StructureRoleAssignment.membership_id == membership.id
            ).first()
            if assignment is not None:
                continue
            target_name = "Owner" if membership.user_id == governance.owner_user_id else LEGACY_ROLE_TO_SYSTEM.get((membership.role or "MEMBER").upper(), "Membre")
            target_role = role_by_name[target_name]
            db.add(StructureRoleAssignment(
                organization_id=organization.id,
                membership_id=membership.id,
                role_id=target_role.id,
                assigned_by_user_id=governance.owner_user_id,
                created_at=now_utc(),
                updated_at=now_utc(),
            ))
            changed = True

        existing_sections = {
            policy.resource_type
            for policy in db.query(VisibilityPolicy).filter(
                VisibilityPolicy.organization_id == organization.id,
                VisibilityPolicy.resource_id == "__section__",
            ).all()
        }
        legacy = organization.visibility_settings_json if isinstance(organization.visibility_settings_json, dict) else {}
        legacy_keys = {
            "description": "presentation", "events": "events", "members": "members", "albums": "albums",
            "folklore": "folklore", "contact": "contact", "publications": "publications",
            "documents": "documents", "stats": "stats",
        }
        for section, default_level in DEFAULT_SECTION_VISIBILITY.items():
            if section in existing_sections:
                continue
            legacy_key = next((key for key, value in legacy_keys.items() if value == section), None)
            level = normalize_visibility(legacy.get(legacy_key, default_level)) if legacy_key else default_level
            db.add(VisibilityPolicy(
                organization_id=organization.id,
                resource_type=section,
                resource_id="__section__",
                level=level,
                updated_by_user_id=governance.owner_user_id,
                created_at=now_utc(),
                updated_at=now_utc(),
            ))
            changed = True

        if changed:
            db.flush()
        return changed

    @classmethod
    def context(cls, db: Session, organization: Organization, user: AppUser) -> AuthorizationContext:
        cls.ensure_foundation(db, organization)
        membership = cls.active_membership(db, organization.id, user.id)
        if membership is None:
            raise HTTPException(status_code=403, detail={"reason": "FORUM_MEMBERSHIP_REQUIRED"})
        assignment = db.query(StructureRoleAssignment).filter(
            StructureRoleAssignment.organization_id == organization.id,
            StructureRoleAssignment.membership_id == membership.id,
        ).first()
        role = db.get(StructureRole, assignment.role_id) if assignment else None
        governance = db.get(StructureGovernance, organization.id)
        is_owner = bool(governance and governance.owner_user_id == user.id)
        if is_owner:
            role = db.query(StructureRole).filter(
                StructureRole.organization_id == organization.id,
                StructureRole.name == "Owner",
                StructureRole.system_role.is_(True),
            ).first()
        if role is None or role.organization_id != organization.id:
            raise HTTPException(status_code=403, detail={"reason": "FORUM_ROLE_REQUIRED"})
        permissions = frozenset(str(p) for p in (role.permissions_json or []) if str(p) in ALL_PERMISSIONS)
        if is_owner:
            permissions = frozenset(ALL_PERMISSIONS)
        return AuthorizationContext(
            user=user,
            organization=organization,
            membership=membership,
            role=role,
            permissions=permissions,
            audience_level=normalize_visibility(role.audience_level),
            is_owner=is_owner,
        )

    @classmethod
    def require_permission(cls, db: Session, organization: Organization, user: AppUser, permission: str) -> AuthorizationContext:
        if permission not in ALL_PERMISSIONS:
            raise RuntimeError(f"Unknown Forum permission: {permission}")
        ctx = cls.context(db, organization, user)
        if permission not in ctx.permissions:
            raise HTTPException(status_code=403, detail={"reason": "FORUM_PERMISSION_DENIED", "permission": permission})
        return ctx

    @classmethod
    def can_view_level(cls, level: str, user: Optional[AppUser], ctx: Optional[AuthorizationContext]) -> bool:
        normalized = normalize_visibility(level)
        if normalized == "PUBLIC":
            return True
        if normalized == "TORE":
            return bool(user is not None and not getattr(user, "is_deleted", False) and not getattr(user, "is_guest", False))
        if ctx is None:
            return False
        return AUDIENCE_RANK.get(ctx.audience_level, 0) >= AUDIENCE_RANK.get(normalized, 99)

    @classmethod
    def assert_grantable(cls, ctx: AuthorizationContext, requested_permissions: Iterable[str]) -> list[str]:
        requested = sorted(set(str(p) for p in requested_permissions))
        unknown = [p for p in requested if p not in ALL_PERMISSIONS]
        if unknown:
            raise HTTPException(status_code=422, detail={"reason": "UNKNOWN_PERMISSIONS", "permissions": unknown})
        forbidden_system = [p for p in requested if p in NON_DELEGABLE_PERMISSIONS]
        if forbidden_system:
            raise HTTPException(status_code=403, detail={"reason": "NON_DELEGABLE_PERMISSION", "permissions": forbidden_system})
        missing = [p for p in requested if p not in ctx.permissions]
        if missing:
            raise HTTPException(status_code=403, detail={"reason": "PERMISSION_GRANT_CEILING", "permissions": missing})
        return requested

    @classmethod
    def can_read_document(cls, ctx: AuthorizationContext, document) -> bool:
        return document.organization_id == ctx.organization.id and cls.can_view_level(document.visibility, ctx.user, ctx)

    @classmethod
    def can_read_channel(cls, ctx: AuthorizationContext, channel) -> bool:
        return channel.organization_id == ctx.organization.id and not channel.is_archived and cls.can_view_level(channel.visibility, ctx.user, ctx)

    @classmethod
    def can_post_channel(cls, ctx: AuthorizationContext, channel) -> bool:
        return "channels.post" in ctx.permissions and cls.can_read_channel(ctx, channel)


def normalize_visibility(value: Optional[str]) -> str:
    raw = str(value or "MEMBERS").strip().upper().replace("É", "E")
    return VISIBILITY_ALIASES.get(raw, "PRIVATE")


class VisibilityService:
    @staticmethod
    def policy(db: Session, organization_id: int, resource_type: str, resource_id: str = "__section__") -> Optional[VisibilityPolicy]:
        return db.query(VisibilityPolicy).filter(
            VisibilityPolicy.organization_id == organization_id,
            VisibilityPolicy.resource_type == resource_type,
            VisibilityPolicy.resource_id == resource_id,
        ).first()

    @classmethod
    def level(cls, db: Session, organization_id: int, resource_type: str, resource_id: str = "__section__", default: str = "PRIVATE") -> str:
        row = cls.policy(db, organization_id, resource_type, resource_id)
        if row is None and resource_id != "__section__":
            row = cls.policy(db, organization_id, resource_type, "__section__")
        return normalize_visibility(row.level if row else default)

    @classmethod
    def can_view(cls, db: Session, organization_id: int, resource_type: str, *, user: Optional[AppUser], ctx: Optional[AuthorizationContext], resource_id: str = "__section__", fallback_level: str = "PRIVATE") -> bool:
        return AuthorizationService.can_view_level(
            cls.level(db, organization_id, resource_type, resource_id, fallback_level), user, ctx
        )
