from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, now_utc


class StructureCapability(Base):
    __tablename__ = "structure_capabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(96), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(280), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)


class StructureRole(Base):
    __tablename__ = "structure_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # NULL means a platform-defined system role reusable by every Structure.
    organization_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    scope_key: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_legacy: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("app_users.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)


class StructureRoleCapability(Base):
    __tablename__ = "structure_role_capabilities"
    __table_args__ = (
        UniqueConstraint("role_id", "capability_id", name="uq_structure_role_capability"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("structure_roles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    capability_id: Mapped[int] = mapped_column(
        ForeignKey("structure_capabilities.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)


class StructureMembershipRole(Base):
    __tablename__ = "structure_membership_roles"
    __table_args__ = (
        UniqueConstraint("membership_id", "role_id", name="uq_structure_membership_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    membership_id: Mapped[int] = mapped_column(
        ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("structure_roles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    assigned_by_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("app_users.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
