from __future__ import annotations

"""Persistent ACL primitives for Forum discussion channels.

The existing ``StructureDiscussionChannel.visibility`` remains a compatibility
fallback. Once an ACL row is enabled for a channel, access is decided only from
explicit role/capability/member grants (plus the structure owner break-glass).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, now_utc


class StructureChannelAcl(Base):
    __tablename__ = "structure_channel_acls"
    __table_args__ = (
        Index("ix_structure_channel_acls_org_enabled", "organization_id", "enabled"),
    )

    channel_id: Mapped[int] = mapped_column(
        ForeignKey("structure_discussion_channels.id"), primary_key=True
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    updated_by_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("app_users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False, index=True)


class StructureChannelAclGrant(Base):
    __tablename__ = "structure_channel_acl_grants"
    __table_args__ = (
        UniqueConstraint(
            "channel_id", "subject_type", "subject_key",
            name="uq_structure_channel_acl_grant_subject",
        ),
        CheckConstraint(
            "subject_type IN ('ROLE','CAPABILITY','MEMBER')",
            name="ck_structure_channel_acl_grant_subject_type",
        ),
        Index(
            "ix_structure_channel_acl_grants_lookup",
            "organization_id", "channel_id", "subject_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("structure_discussion_channels.id"), nullable=False, index=True
    )
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # ROLE stores StructureRole.id as a decimal string, CAPABILITY stores the
    # capability key, MEMBER stores AppUser.id. Keeping one normalized grant
    # table makes replacement atomic while validation keeps tenant scope strict.
    subject_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("app_users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False, index=True)
