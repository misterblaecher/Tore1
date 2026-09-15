from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, now_utc


class StructureOwnership(Base):
    __tablename__ = "structure_ownership"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_structure_ownership_org"),
        Index("ix_structure_ownership_primary", "primary_owner_user_id"),
        Index("ix_structure_ownership_recovery", "recovery_owner_user_id"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    primary_owner_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False)
    recovery_owner_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    is_frozen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    keep_public_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    frozen_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    frozen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    frozen_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False, index=True)


class StructureOwnershipTransfer(Base):
    __tablename__ = "structure_ownership_transfers"
    __table_args__ = (
        Index("ix_structure_transfer_org_status", "organization_id", "status"),
        Index("ix_structure_transfer_target_status", "to_owner_user_id", "status"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    from_owner_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False)
    to_owner_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False)
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="REQUESTED", nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True)


class StructureRecoveryRequest(Base):
    __tablename__ = "structure_recovery_requests"
    __table_args__ = (
        Index("ix_structure_recovery_org_status", "organization_id", "status"),
        Index("ix_structure_recovery_requester_status", "requested_by_user_id", "status"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="REQUESTED", nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    resolved_by_admin: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    resolution_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
