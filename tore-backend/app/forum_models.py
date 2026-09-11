from __future__ import annotations

"""Additive ORM models for the production Forum foundation.

The existing ``Organization``, ``OrganizationMembership``, ``Event`` and Forum MVP
models remain canonical.  These tables extend them instead of introducing a
parallel Structure/User/Event model.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, now_utc


VISIBILITY_LEVELS = ("PUBLIC", "TORE", "MEMBERS", "STAFF", "BUREAU", "TREASURY", "PRIVATE")


class StructureGovernance(Base):
    __tablename__ = "structure_governance"
    __table_args__ = (
        CheckConstraint("status IN ('REQUESTED','SETUP','ACTIVE','LOCKED','ARCHIVED')", name="ck_structure_governance_status"),
    )

    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", index=True)
    seo_title: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    seo_description: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)


class StructurePublicPage(Base):
    __tablename__ = "structure_public_pages"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','PUBLISHED','HIDDEN','SUSPENDED','ARCHIVED')", name="ck_structure_public_page_status"),
    )

    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)
    seo_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    indexable: Mapped[bool] = mapped_column(Boolean, default=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)


class StructureRole(Base):
    __tablename__ = "structure_roles"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_structure_roles_org_name"),
        CheckConstraint("audience_level IN ('PUBLIC','TORE','MEMBERS','STAFF','BUREAU','TREASURY','PRIVATE')", name="ck_structure_role_audience"),
        Index("ix_structure_roles_org_system", "organization_id", "system_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    system_role: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    audience_level: Mapped[str] = mapped_column(String(16), default="MEMBERS", index=True)
    permissions_json: Mapped[list] = mapped_column(JSON, default=list)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)


class StructureRoleAssignment(Base):
    __tablename__ = "structure_role_assignments"
    __table_args__ = (
        UniqueConstraint("membership_id", name="uq_structure_role_assignment_membership"),
        Index("ix_structure_role_assignments_org_role", "organization_id", "role_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    membership_id: Mapped[int] = mapped_column(ForeignKey("organization_memberships.id"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("structure_roles.id"), index=True)
    assigned_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class StructureInvitation(Base):
    __tablename__ = "structure_invitations"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING','ACCEPTED','EXPIRED','REVOKED')", name="ck_structure_invitation_status"),
        Index("ix_structure_invitations_org_status", "organization_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("structure_roles.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)
    invited_by_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    accepted_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True)


class StructureClaim(Base):
    __tablename__ = "structure_claims"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','CANCELLED')", name="ck_structure_claim_status"),
        Index("ix_structure_claims_org_status", "organization_id", "status"),
        Index("ix_structure_claims_requester_status", "requested_by_user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewed_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True)


class VisibilityPolicy(Base):
    __tablename__ = "structure_visibility_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "resource_type", "resource_id", name="uq_structure_visibility_policy_resource"),
        CheckConstraint("level IN ('PUBLIC','TORE','MEMBERS','STAFF','BUREAU','TREASURY','PRIVATE')", name="ck_structure_visibility_policy_level"),
        Index("ix_structure_visibility_policy_lookup", "organization_id", "resource_type", "resource_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(48), index=True)
    resource_id: Mapped[str] = mapped_column(String(80), default="__section__", index=True)
    level: Mapped[str] = mapped_column(String(16), default="MEMBERS", index=True)
    updated_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class EventStructure(Base):
    __tablename__ = "event_structures"
    __table_args__ = (
        UniqueConstraint("event_id", "organization_id", name="uq_event_structures_event_org"),
        CheckConstraint("role IN ('HOST','CO_HOST')", name="ck_event_structure_role"),
        Index("ix_event_structures_org_role", "organization_id", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="HOST", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class ForumEventLifecycle(Base):
    __tablename__ = "forum_event_lifecycle"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','PUBLISHED','SYNCED_TO_APP','LIVE','CLOSED','RECAP_DRAFT','RECAP_PUBLISHED','ARCHIVED')", name="ck_forum_event_lifecycle_status"),
    )

    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", index=True)
    updated_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)


class EventPublicSummary(Base):
    __tablename__ = "event_public_summaries"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_public_summary_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    entries: Mapped[int] = mapped_column(Integer, default=0)
    scans: Mapped[int] = mapped_column(Integer, default=0)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    occupancy_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
    published_by_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)


class AccountingEntry(Base):
    __tablename__ = "structure_accounting_entries"
    __table_args__ = (
        CheckConstraint("entry_type IN ('INCOME','EXPENSE')", name="ck_structure_accounting_type"),
        CheckConstraint("status IN ('DRAFT','VALIDATED','LOCKED')", name="ck_structure_accounting_status"),
        Index("ix_structure_accounting_org_event", "organization_id", "event_id"),
        Index("ix_structure_accounting_org_status", "organization_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    entry_type: Mapped[str] = mapped_column(String(16), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    label: Mapped[str] = mapped_column(String(180))
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)
    supplier: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    paid: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    locked_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True)


class StructureDocumentVersion(Base):
    __tablename__ = "structure_document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_structure_document_version_number"),
        Index("ix_structure_document_versions_document_created", "document_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("structure_documents.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(160))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    uploaded_by_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)


class StructureMediaAsset(Base):
    __tablename__ = "structure_media_assets"
    __table_args__ = (Index("ix_structure_media_assets_org_created", "organization_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    mime_type: Mapped[str] = mapped_column(String(160))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    uploaded_by_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)


class StructureAlbumMedia(Base):
    __tablename__ = "structure_album_media_links"
    __table_args__ = (
        UniqueConstraint("album_id", "media_id", name="uq_structure_album_media_link"),
        Index("ix_structure_album_media_position", "album_id", "position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    album_id: Mapped[int] = mapped_column(ForeignKey("structure_albums.id"), index=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("structure_media_assets.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_cover: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class StructurePageVersion(Base):
    __tablename__ = "structure_page_versions"
    __table_args__ = (
        UniqueConstraint("page_id", "version_number", name="uq_structure_page_version_number"),
        Index("ix_structure_page_versions_page_created", "page_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("structure_pages.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(180))
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(24))
    visibility: Mapped[str] = mapped_column(String(24))
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)


class OrgaPostPublication(Base):
    __tablename__ = "organization_post_publications"
    __table_args__ = (
        UniqueConstraint("post_id", name="uq_organization_post_publication_post"),
        CheckConstraint("status IN ('DRAFT','SCHEDULED','PUBLISHED','ARCHIVED')", name="ck_organization_post_publication_status"),
        CheckConstraint("visibility IN ('PUBLIC','TORE','MEMBERS','STAFF','BUREAU','TREASURY','PRIVATE')", name="ck_organization_post_publication_visibility"),
        Index("ix_organization_post_publications_org_schedule", "organization_id", "status", "publish_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("organization_posts.id"), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    media_id: Mapped[Optional[int]] = mapped_column(ForeignKey("structure_media_assets.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(180), default="")
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)
    visibility: Mapped[str] = mapped_column(String(16), default="PUBLIC", index=True)
    publish_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class StructureAuditContext(Base):
    __tablename__ = "structure_audit_contexts"
    __table_args__ = (Index("ix_structure_audit_contexts_org_audit", "organization_id", "audit_log_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_log_id: Mapped[int] = mapped_column(ForeignKey("audit_logs.id"), unique=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    before_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    context_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
