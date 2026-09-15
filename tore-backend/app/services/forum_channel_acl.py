from __future__ import annotations

"""Central, server-side channel ACL authorization.

Every channel-derived resource (messages, threads, reactions and attachments)
must resolve its parent channel through this service before being serialized or
mutated.  Denials intentionally use 404 so knowing an id never becomes an
existence oracle across ACLs or structures.
"""

from typing import Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import now_utc
from models import (
    AppUser,
    OrganizationMembership,
    StructureDiscussionChannel,
    StructureDiscussionPost,
    StructureDocument,
)
from app.forum_acl_models import StructureChannelAcl, StructureChannelAclGrant
from app.forum_models import StructureRole
from app.services.forum_authorization import (
    ALL_PERMISSIONS,
    AuthorizationContext,
    AuthorizationService,
    normalize_visibility,
)


class ChannelAclService:
    @staticmethod
    def _policy(db: Session, channel_id: int) -> StructureChannelAcl | None:
        return db.get(StructureChannelAcl, channel_id)

    @staticmethod
    def _grants(db: Session, organization_id: int, channel_id: int) -> list[StructureChannelAclGrant]:
        return db.query(StructureChannelAclGrant).filter_by(
            organization_id=organization_id,
            channel_id=channel_id,
        ).order_by(StructureChannelAclGrant.subject_type, StructureChannelAclGrant.subject_key).all()

    @classmethod
    def explicit_enabled(cls, db: Session, channel: StructureDiscussionChannel) -> bool:
        policy = cls._policy(db, channel.id)
        return bool(policy and policy.organization_id == channel.organization_id and policy.enabled)

    @classmethod
    def can_read(cls, db: Session, ctx: AuthorizationContext, channel: StructureDiscussionChannel) -> bool:
        if channel.organization_id != ctx.organization.id or channel.is_archived:
            return False
        policy = cls._policy(db, channel.id)
        if policy is None or policy.organization_id != ctx.organization.id or not policy.enabled:
            return AuthorizationService.can_read_channel(ctx, channel)
        if ctx.is_owner:
            return True

        grants = cls._grants(db, ctx.organization.id, channel.id)
        role_key = str(ctx.role.id)
        user_key = str(ctx.user.id)
        for grant in grants:
            if grant.subject_type == "ROLE" and grant.subject_key == role_key:
                return True
            if grant.subject_type == "MEMBER" and grant.subject_key == user_key:
                return True
            if grant.subject_type == "CAPABILITY" and grant.subject_key in ctx.permissions:
                return True
        return False

    @classmethod
    def require_read(cls, db: Session, ctx: AuthorizationContext, channel: StructureDiscussionChannel) -> StructureDiscussionChannel:
        if not cls.can_read(db, ctx, channel):
            raise HTTPException(status_code=404, detail="Channel not found")
        return channel

    @classmethod
    def can_post(cls, db: Session, ctx: AuthorizationContext, channel: StructureDiscussionChannel) -> bool:
        return "channels.post" in ctx.permissions and cls.can_read(db, ctx, channel)

    @classmethod
    def require_post(cls, db: Session, ctx: AuthorizationContext, channel: StructureDiscussionChannel) -> StructureDiscussionChannel:
        if not cls.can_post(db, ctx, channel):
            raise HTTPException(status_code=404, detail="Channel not found")
        return channel

    @classmethod
    def message_for_user(
        cls,
        db: Session,
        ctx: AuthorizationContext,
        message_id: int,
        *,
        channel_id: int | None = None,
    ) -> StructureDiscussionPost:
        message = db.get(StructureDiscussionPost, message_id)
        if (
            message is None
            or message.organization_id != ctx.organization.id
            or message.is_archived
            or (channel_id is not None and message.channel_id != channel_id)
        ):
            raise HTTPException(status_code=404, detail="Message not found")
        channel = db.get(StructureDiscussionChannel, message.channel_id)
        if channel is None or channel.organization_id != ctx.organization.id:
            raise HTTPException(status_code=404, detail="Message not found")
        if not cls.can_read(db, ctx, channel):
            raise HTTPException(status_code=404, detail="Message not found")
        return message

    @classmethod
    def can_read_document(
        cls,
        db: Session,
        ctx: AuthorizationContext,
        document: StructureDocument,
    ) -> bool:
        if not AuthorizationService.can_read_document(ctx, document):
            return False

        # If a document is used as a message attachment, direct document access
        # must not bypass all channels that expose it.  Loading the small set of
        # attachment-bearing posts keeps this portable across SQLite/Postgres JSON.
        attached_posts = db.query(StructureDiscussionPost).filter(
            StructureDiscussionPost.organization_id == ctx.organization.id,
            StructureDiscussionPost.is_archived.is_(False),
            StructureDiscussionPost.document_ids.is_not(None),
        ).all()
        attached_channel_ids = {
            post.channel_id
            for post in attached_posts
            if document.id in {int(value) for value in (post.document_ids or []) if str(value).isdigit()}
        }
        if not attached_channel_ids:
            return True
        channels = db.query(StructureDiscussionChannel).filter(
            StructureDiscussionChannel.organization_id == ctx.organization.id,
            StructureDiscussionChannel.id.in_(attached_channel_ids),
            StructureDiscussionChannel.is_archived.is_(False),
        ).all()
        return any(cls.can_read(db, ctx, channel) for channel in channels)

    @classmethod
    def attachment_for_user(
        cls,
        db: Session,
        ctx: AuthorizationContext,
        message_id: int,
        document_id: int,
    ) -> tuple[StructureDiscussionPost, StructureDocument]:
        message = cls.message_for_user(db, ctx, message_id)
        document_ids = {int(value) for value in (message.document_ids or []) if str(value).isdigit()}
        if document_id not in document_ids:
            raise HTTPException(status_code=404, detail="Attachment not found")
        document = db.get(StructureDocument, document_id)
        if (
            document is None
            or document.organization_id != ctx.organization.id
            or document.archived_at is not None
            or not cls.can_read_document(db, ctx, document)
        ):
            raise HTTPException(status_code=404, detail="Attachment not found")
        return message, document

    @classmethod
    def state(cls, db: Session, ctx: AuthorizationContext, channel: StructureDiscussionChannel, *, options: bool = False) -> dict:
        if channel.organization_id != ctx.organization.id:
            raise HTTPException(status_code=404, detail="Channel not found")
        policy = cls._policy(db, channel.id)
        grants = cls._grants(db, ctx.organization.id, channel.id)
        payload = {
            "channelId": channel.id,
            "enabled": bool(policy and policy.enabled),
            "legacyVisibility": normalize_visibility(channel.visibility),
            "roleIds": sorted(int(grant.subject_key) for grant in grants if grant.subject_type == "ROLE" and grant.subject_key.isdigit()),
            "capabilities": sorted(grant.subject_key for grant in grants if grant.subject_type == "CAPABILITY"),
            "memberUserIds": sorted(grant.subject_key for grant in grants if grant.subject_type == "MEMBER"),
        }
        if not options:
            return payload

        roles = db.query(StructureRole).filter_by(organization_id=ctx.organization.id).order_by(StructureRole.name).all()
        memberships = db.query(OrganizationMembership).filter_by(organization_id=ctx.organization.id).all()
        members: list[dict] = []
        for membership in memberships:
            active = AuthorizationService.active_membership(db, ctx.organization.id, membership.user_id)
            if active is None:
                continue
            user = db.get(AppUser, membership.user_id)
            members.append({
                "userId": membership.user_id,
                "displayName": user.display_name if user else "Membre TORÈ",
            })
        payload["options"] = {
            "roles": [{"id": role.id, "name": role.name} for role in roles],
            "capabilities": sorted(ALL_PERMISSIONS),
            "members": sorted(members, key=lambda item: (item["displayName"].lower(), item["userId"])),
        }
        return payload

    @classmethod
    def replace(
        cls,
        db: Session,
        ctx: AuthorizationContext,
        channel: StructureDiscussionChannel,
        *,
        enabled: bool,
        role_ids: Iterable[int],
        capabilities: Iterable[str],
        member_user_ids: Iterable[str],
    ) -> dict:
        if channel.organization_id != ctx.organization.id:
            raise HTTPException(status_code=404, detail="Channel not found")

        normalized_role_ids = sorted(set(int(value) for value in role_ids))
        normalized_capabilities = sorted(set(str(value).strip() for value in capabilities if str(value).strip()))
        normalized_members = sorted(set(str(value).strip() for value in member_user_ids if str(value).strip()))

        if len(normalized_role_ids) + len(normalized_capabilities) + len(normalized_members) > 250:
            raise HTTPException(status_code=422, detail={"reason": "CHANNEL_ACL_TOO_LARGE", "maxGrants": 250})

        roles = db.query(StructureRole).filter(
            StructureRole.organization_id == ctx.organization.id,
            StructureRole.id.in_(normalized_role_ids or [-1]),
        ).all()
        if {role.id for role in roles} != set(normalized_role_ids):
            raise HTTPException(status_code=422, detail={"reason": "CHANNEL_ACL_ROLE_SCOPE_INVALID"})

        unknown_capabilities = [value for value in normalized_capabilities if value not in ALL_PERMISSIONS]
        if unknown_capabilities:
            raise HTTPException(status_code=422, detail={"reason": "UNKNOWN_PERMISSIONS", "permissions": unknown_capabilities})

        invalid_members = [
            user_id for user_id in normalized_members
            if AuthorizationService.active_membership(db, ctx.organization.id, user_id) is None
        ]
        if invalid_members:
            raise HTTPException(status_code=422, detail={"reason": "CHANNEL_ACL_MEMBER_SCOPE_INVALID", "userIds": invalid_members})

        policy = cls._policy(db, channel.id)
        stamp = now_utc()
        if policy is None:
            policy = StructureChannelAcl(
                channel_id=channel.id,
                organization_id=ctx.organization.id,
                enabled=enabled,
                updated_by_user_id=ctx.user.id,
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(policy)
        else:
            if policy.organization_id != ctx.organization.id:
                raise HTTPException(status_code=404, detail="Channel not found")
            policy.enabled = enabled
            policy.updated_by_user_id = ctx.user.id
            policy.updated_at = stamp

        db.query(StructureChannelAclGrant).filter_by(
            organization_id=ctx.organization.id,
            channel_id=channel.id,
        ).delete(synchronize_session=False)

        grants: list[StructureChannelAclGrant] = []
        grants.extend(
            StructureChannelAclGrant(
                organization_id=ctx.organization.id,
                channel_id=channel.id,
                subject_type="ROLE",
                subject_key=str(role_id),
                created_by_user_id=ctx.user.id,
                created_at=stamp,
            )
            for role_id in normalized_role_ids
        )
        grants.extend(
            StructureChannelAclGrant(
                organization_id=ctx.organization.id,
                channel_id=channel.id,
                subject_type="CAPABILITY",
                subject_key=capability,
                created_by_user_id=ctx.user.id,
                created_at=stamp,
            )
            for capability in normalized_capabilities
        )
        grants.extend(
            StructureChannelAclGrant(
                organization_id=ctx.organization.id,
                channel_id=channel.id,
                subject_type="MEMBER",
                subject_key=user_id,
                created_by_user_id=ctx.user.id,
                created_at=stamp,
            )
            for user_id in normalized_members
        )
        db.add_all(grants)
        db.flush()
        return cls.state(db, ctx, channel)
