from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from db import Base, now_utc

NOTIFICATION_TYPES = {"MENTION", "INVITATION", "MEMBERSHIP_CHANGE", "EVENT_REMINDER", "DOCUMENT_CHANGED", "REVIEW_REQUIRED", "ACCOUNTING_REVIEW", "PUBLICATION_REQUEST"}
class StructureNotification(Base):
    __tablename__ = "structure_notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    target_permission: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
