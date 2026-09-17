from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from db import Base, now_utc

class StructurePlanningItem(Base):
    __tablename__ = "structure_planning_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(180))
    kind: Mapped[str] = mapped_column(String(16), default="OTHER", index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    recurrence: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    reminder_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by_user_id: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

class StructurePlanningAssignee(Base):
    __tablename__ = "structure_planning_assignees"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    planning_item_id: Mapped[int] = mapped_column(ForeignKey("structure_planning_items.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True)
