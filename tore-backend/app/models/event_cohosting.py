from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, now_utc


class EventStructure(Base):
    """Persistent Event <-> Structure relation.

    OWNER rows represent the canonical host structure. COHOST rows carry a
    deliberately explicit permission matrix; finance is never implied by any
    other permission.
    """

    __tablename__ = "event_structures"
    __table_args__ = (
        UniqueConstraint("event_id", "organization_id", name="uq_event_structures_event_org"),
        CheckConstraint("role IN ('OWNER', 'COHOST')", name="ck_event_structures_role"),
        Index("ix_event_structures_org_role", "organization_id", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="COHOST", index=True)

    can_edit: Mapped[bool] = mapped_column(Boolean, default=False)
    can_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    can_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    can_documents: Mapped[bool] = mapped_column(Boolean, default=False)
    can_finance: Mapped[bool] = mapped_column(Boolean, default=False)
    can_recap: Mapped[bool] = mapped_column(Boolean, default=False)

    created_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventManagerSettings(Base):
    """Rich-manager fields that do not belong in legacy rules_flags."""

    __tablename__ = "event_manager_settings"

    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    pricing_json: Mapped[list] = mapped_column(JSON, default=list)
    banner_file_id: Mapped[Optional[str]] = mapped_column(ForeignKey("stored_files.id"), nullable=True, index=True)
    updated_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
