from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, now_utc


class StoredFile(Base):
    """Central metadata for managed uploads.

    Blob bytes live behind a storage backend. This row is the authorization and
    audit boundary: clients never choose the storage key and uploads start
    private until an explicit visibility change is made.
    """

    __tablename__ = "stored_files"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_stored_files_storage_key"),
        Index("ix_stored_files_org_visibility", "organization_id", "visibility", "deleted_at"),
        Index("ix_stored_files_owner", "owner_user_id", "deleted_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(127), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(512))
    storage_backend: Mapped[str] = mapped_column(String(16), default="local")
    visibility: Mapped[str] = mapped_column(String(16), default="PRIVATE", index=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    purpose: Mapped[str] = mapped_column(String(32), default="DOCUMENT", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
