from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import now_utc
from models import Event, EventRuntimeState, Organization, OrganizationMembership
from app.forum_models import (
    AccountingEntry,
    EventStructure,
    ForumEventLifecycle,
    StructureGovernance,
    StructureRole,
    StructureRoleAssignment,
)
from app.services.forum_authorization import AuthorizationContext, AuthorizationService
from app.services.forum_audit import write_structure_audit


EVENT_TRANSITIONS = {
    "DRAFT": {"PUBLISHED"},
    "PUBLISHED": {"SYNCED_TO_APP"},
    "SYNCED_TO_APP": {"LIVE"},
    "LIVE": {"CLOSED"},
    "CLOSED": {"RECAP_DRAFT"},
    "RECAP_DRAFT": {"RECAP_PUBLISHED"},
    "RECAP_PUBLISHED": {"ARCHIVED"},
    "ARCHIVED": set(),
}


class RoleService:
    @staticmethod
    def create(db: Session, *, ctx: AuthorizationContext, name: str, audience_level: str, permissions: list[str]) -> StructureRole:
        if "roles.manage" not in ctx.permissions:
            raise HTTPException(403, detail={"reason": "FORUM_PERMISSION_DENIED", "permission": "roles.manage"})
        safe_permissions = AuthorizationService.assert_grantable(ctx, permissions)
        clean_name = name.strip()
        if not clean_name:
            raise HTTPException(422, detail={"reason": "ROLE_NAME_REQUIRED"})
        if db.query(StructureRole).filter(
            StructureRole.organization_id == ctx.organization.id,
            StructureRole.name == clean_name,
        ).first():
            raise HTTPException(409, detail={"reason": "ROLE_NAME_EXISTS"})
        role = StructureRole(
            organization_id=ctx.organization.id,
            name=clean_name,
            system_role=False,
            audience_level=audience_level,
            permissions_json=safe_permissions,
            created_by_user_id=ctx.user.id,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        db.add(role)
        db.flush()
        write_structure_audit(
            db, organization_id=ctx.organization.id, actor_user_id=ctx.user.id, actor_role=ctx.role.name,
            action="forum.role.create", resource_type="structure_role", resource_id=str(role.id),
            before=None, after={"name": role.name, "audience": role.audience_level, "permissions": safe_permissions},
        )
        return role

    @staticmethod
    def update(db: Session, *, ctx: AuthorizationContext, role: StructureRole, name: Optional[str], audience_level: Optional[str], permissions: Optional[list[str]]) -> StructureRole:
        if "roles.manage" not in ctx.permissions:
            raise HTTPException(403, detail={"reason": "FORUM_PERMISSION_DENIED", "permission": "roles.manage"})
        if role.organization_id != ctx.organization.id:
            raise HTTPException(404, detail="Role not found")
        if role.system_role:
            raise HTTPException(403, detail={"reason": "SYSTEM_ROLE_IMMUTABLE"})
        before = {"name": role.name, "audience": role.audience_level, "permissions": list(role.permissions_json or [])}
        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                raise HTTPException(422, detail={"reason": "ROLE_NAME_REQUIRED"})
            duplicate = db.query(StructureRole).filter(
                StructureRole.organization_id == ctx.organization.id,
                StructureRole.name == clean_name,
                StructureRole.id != role.id,
            ).first()
            if duplicate:
                raise HTTPException(409, detail={"reason": "ROLE_NAME_EXISTS"})
            role.name = clean_name
        if audience_level is not None:
            role.audience_level = audience_level
        if permissions is not None:
            role.permissions_json = AuthorizationService.assert_grantable(ctx, permissions)
        role.updated_at = now_utc()
        db.flush()
        write_structure_audit(
            db, organization_id=ctx.organization.id, actor_user_id=ctx.user.id, actor_role=ctx.role.name,
            action="forum.role.update", resource_type="structure_role", resource_id=str(role.id),
            before=before, after={"name": role.name, "audience": role.audience_level, "permissions": list(role.permissions_json or [])},
        )
        return role

    @staticmethod
    def delete(db: Session, *, ctx: AuthorizationContext, role: StructureRole) -> None:
        if "roles.manage" not in ctx.permissions:
            raise HTTPException(403, detail={"reason": "FORUM_PERMISSION_DENIED", "permission": "roles.manage"})
        if role.organization_id != ctx.organization.id:
            raise HTTPException(404, detail="Role not found")
        if role.system_role:
            raise HTTPException(403, detail={"reason": "SYSTEM_ROLE_IMMUTABLE"})
        if db.query(StructureRoleAssignment).filter(StructureRoleAssignment.role_id == role.id).first():
            raise HTTPException(409, detail={"reason": "ROLE_STILL_ASSIGNED"})
        before = {"name": role.name, "audience": role.audience_level, "permissions": list(role.permissions_json or [])}
        db.delete(role)
        write_structure_audit(
            db, organization_id=ctx.organization.id, actor_user_id=ctx.user.id, actor_role=ctx.role.name,
            action="forum.role.delete", resource_type="structure_role", resource_id=str(role.id), before=before, after=None,
        )

    @staticmethod
    def assign(db: Session, *, ctx: AuthorizationContext, membership: OrganizationMembership, role: StructureRole) -> StructureRoleAssignment:
        if "members.manage" not in ctx.permissions:
            raise HTTPException(403, detail={"reason": "FORUM_PERMISSION_DENIED", "permission": "members.manage"})
        if membership.organization_id != ctx.organization.id or role.organization_id != ctx.organization.id:
            raise HTTPException(404, detail="Member or role not found")
        governance = db.get(StructureGovernance, ctx.organization.id)
        if governance and membership.user_id == governance.owner_user_id:
            raise HTTPException(409, detail={"reason": "OWNER_ROLE_CHANGE_REQUIRES_TRANSFER"})
        if role.system_role:
            raise HTTPException(403, detail={"reason": "SYSTEM_ROLE_ASSIGNMENT_REQUIRES_WORKFLOW"})
        AuthorizationService.assert_grantable(ctx, role.permissions_json or [])
        assignment = db.query(StructureRoleAssignment).filter(
            StructureRoleAssignment.membership_id == membership.id
        ).first()
        before = {"roleId": assignment.role_id if assignment else None}
        if assignment is None:
            assignment = StructureRoleAssignment(
                organization_id=ctx.organization.id,
                membership_id=membership.id,
                role_id=role.id,
                assigned_by_user_id=ctx.user.id,
                created_at=now_utc(),
                updated_at=now_utc(),
            )
            db.add(assignment)
        else:
            assignment.role_id = role.id
            assignment.assigned_by_user_id = ctx.user.id
            assignment.updated_at = now_utc()
        membership.role = role.name.upper().replace("É", "E")[:32]
        membership.updated_at = now_utc()
        db.flush()
        write_structure_audit(
            db, organization_id=ctx.organization.id, actor_user_id=ctx.user.id, actor_role=ctx.role.name,
            action="forum.member.role_change", resource_type="organization_membership", resource_id=str(membership.id),
            before=before, after={"roleId": role.id, "roleName": role.name},
        )
        return assignment


class StructureService:
    @staticmethod
    def transfer_ownership(db: Session, *, ctx: AuthorizationContext, new_owner_user_id: str) -> StructureGovernance:
        governance = db.get(StructureGovernance, ctx.organization.id)
        if governance is None or governance.owner_user_id != ctx.user.id:
            raise HTTPException(403, detail={"reason": "CURRENT_OWNER_REQUIRED"})
        if new_owner_user_id == ctx.user.id:
            return governance
        target = AuthorizationService.active_membership(db, ctx.organization.id, new_owner_user_id)
        if target is None:
            raise HTTPException(409, detail={"reason": "NEW_OWNER_MUST_BE_ACTIVE_MEMBER"})
        old_owner = AuthorizationService.active_membership(db, ctx.organization.id, ctx.user.id)
        if old_owner is None:
            raise HTTPException(409, detail={"reason": "CURRENT_OWNER_MEMBERSHIP_INVALID"})
        owner_role = db.query(StructureRole).filter_by(organization_id=ctx.organization.id, name="Owner", system_role=True).one()
        fallback_role = db.query(StructureRole).filter_by(organization_id=ctx.organization.id, name="Bureau", system_role=True).one()
        before = {"ownerUserId": governance.owner_user_id}
        for membership, target_role in ((old_owner, fallback_role), (target, owner_role)):
            assignment = db.query(StructureRoleAssignment).filter_by(membership_id=membership.id).first()
            if assignment is None:
                assignment = StructureRoleAssignment(
                    organization_id=ctx.organization.id,
                    membership_id=membership.id,
                    role_id=target_role.id,
                    assigned_by_user_id=ctx.user.id,
                    created_at=now_utc(),
                    updated_at=now_utc(),
                )
                db.add(assignment)
            else:
                assignment.role_id = target_role.id
                assignment.assigned_by_user_id = ctx.user.id
                assignment.updated_at = now_utc()
            membership.role = "OWNER" if target_role.name == "Owner" else "BUREAU"
            membership.status = "ACTIVE"
            membership.revoked_at = None
            membership.ends_at = None
            membership.updated_at = now_utc()
        governance.owner_user_id = new_owner_user_id
        governance.updated_at = now_utc()
        db.flush()
        active_owner_assignments = db.query(StructureRoleAssignment).join(
            OrganizationMembership, StructureRoleAssignment.membership_id == OrganizationMembership.id
        ).filter(
            StructureRoleAssignment.organization_id == ctx.organization.id,
            StructureRoleAssignment.role_id == owner_role.id,
            OrganizationMembership.status == "ACTIVE",
            OrganizationMembership.revoked_at.is_(None),
        ).all()
        if len(active_owner_assignments) != 1:
            raise HTTPException(409, detail={"reason": "OWNER_INVARIANT_VIOLATION"})
        write_structure_audit(
            db, organization_id=ctx.organization.id, actor_user_id=ctx.user.id, actor_role=ctx.role.name,
            action="forum.ownership.transfer", resource_type="organization", resource_id=str(ctx.organization.id),
            before=before, after={"ownerUserId": new_owner_user_id},
        )
        return governance


class EventLifecycleService:
    @staticmethod
    def ensure(db: Session, *, organization_id: int, event: Event, actor_user_id: Optional[str] = None) -> ForumEventLifecycle:
        row = db.get(ForumEventLifecycle, event.id)
        if row is None:
            row = ForumEventLifecycle(
                event_id=event.id,
                organization_id=organization_id,
                status="PUBLISHED" if (event.publication_status or "DRAFT").upper() == "PUBLISHED" else "DRAFT",
                updated_by_user_id=actor_user_id,
                created_at=now_utc(),
                updated_at=now_utc(),
            )
            db.add(row)
            db.flush()
        return row

    @classmethod
    def transition(cls, db: Session, *, ctx: AuthorizationContext, event: Event, target: str) -> ForumEventLifecycle:
        if "events.publish" not in ctx.permissions:
            raise HTTPException(403, detail={"reason": "FORUM_PERMISSION_DENIED", "permission": "events.publish"})
        relation = db.query(EventStructure).filter(
            EventStructure.event_id == event.id,
            EventStructure.organization_id == ctx.organization.id,
        ).first()
        legacy_scoped = event.host_type == "orga" and event.host_id == str(ctx.organization.id)
        if relation is None and not legacy_scoped:
            raise HTTPException(404, detail="Event not found")
        row = cls.ensure(db, organization_id=ctx.organization.id, event=event, actor_user_id=ctx.user.id)
        current = row.status
        if target not in EVENT_TRANSITIONS.get(current, set()):
            raise HTTPException(409, detail={"reason": "INVALID_EVENT_TRANSITION", "from": current, "to": target})
        row.status = target
        row.updated_by_user_id = ctx.user.id
        row.updated_at = now_utc()
        if target in {"PUBLISHED", "SYNCED_TO_APP", "LIVE", "CLOSED", "RECAP_DRAFT", "RECAP_PUBLISHED", "ARCHIVED"}:
            event.publication_status = "PUBLISHED"
        if target == "LIVE":
            event.event_state = "LIVE"
            runtime = db.get(EventRuntimeState, event.id)
            if runtime:
                runtime.state = "LIVE"
                runtime.updated_at = now_utc()
        elif target == "CLOSED":
            event.event_state = "CLOSED"
            runtime = db.get(EventRuntimeState, event.id)
            if runtime:
                runtime.state = "CLOSED"
                runtime.updated_at = now_utc()
        event.last_updated_at = now_utc()
        write_structure_audit(
            db, organization_id=ctx.organization.id, actor_user_id=ctx.user.id, actor_role=ctx.role.name,
            action="forum.event.transition", resource_type="event", resource_id=str(event.id), event_id=event.id,
            before={"status": current}, after={"status": target},
        )
        return row


class AccountingService:
    @staticmethod
    def assert_mutable(entry: AccountingEntry) -> None:
        if entry.status == "LOCKED" or entry.locked_at is not None:
            raise HTTPException(409, detail={"reason": "ACCOUNTING_ENTRY_LOCKED"})

    @staticmethod
    def lock(db: Session, *, ctx: AuthorizationContext, entry: AccountingEntry) -> AccountingEntry:
        if "accounting.manage" not in ctx.permissions:
            raise HTTPException(403, detail={"reason": "FORUM_PERMISSION_DENIED", "permission": "accounting.manage"})
        if entry.organization_id != ctx.organization.id:
            raise HTTPException(404, detail="Accounting entry not found")
        AccountingService.assert_mutable(entry)
        before = {"status": entry.status}
        entry.status = "LOCKED"
        entry.locked_at = now_utc()
        entry.locked_by_user_id = ctx.user.id
        entry.updated_at = now_utc()
        write_structure_audit(
            db, organization_id=ctx.organization.id, actor_user_id=ctx.user.id, actor_role=ctx.role.name,
            action="forum.accounting.lock", resource_type="accounting_entry", resource_id=str(entry.id),
            before=before, after={"status": "LOCKED", "lockedBy": ctx.user.id}, event_id=entry.event_id,
        )
        return entry

    @staticmethod
    def unlock(db: Session, *, ctx: AuthorizationContext, entry: AccountingEntry) -> AccountingEntry:
        if "accounting.unlock" not in ctx.permissions:
            raise HTTPException(403, detail={"reason": "FORUM_PERMISSION_DENIED", "permission": "accounting.unlock"})
        if entry.organization_id != ctx.organization.id:
            raise HTTPException(404, detail="Accounting entry not found")
        before = {"status": entry.status, "lockedAt": entry.locked_at.isoformat() if entry.locked_at else None}
        entry.status = "VALIDATED"
        entry.locked_at = None
        entry.locked_by_user_id = None
        entry.updated_at = now_utc()
        write_structure_audit(
            db, organization_id=ctx.organization.id, actor_user_id=ctx.user.id, actor_role=ctx.role.name,
            action="forum.accounting.unlock", resource_type="accounting_entry", resource_id=str(entry.id),
            before=before, after={"status": "VALIDATED"}, event_id=entry.event_id,
        )
        return entry
