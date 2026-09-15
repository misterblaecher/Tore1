from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, now_utc


class ForumEventPage(Base):
    """Public-page and recap metadata layered on top of the live Event model."""

    __tablename__ = "forum_event_pages"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_forum_event_pages_event"),
        UniqueConstraint("slug", name="uq_forum_event_pages_slug"),
        Index("ix_forum_event_pages_recap_status", "recap_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    slug: Mapped[str] = mapped_column(String(220), index=True)
    capacity_public: Mapped[bool] = mapped_column(Boolean, default=False)
    cohost_structure_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    recap_status: Mapped[str] = mapped_column(String(24), default="NONE")
    recap_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recap_album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("structure_albums.id"), nullable=True, index=True)
    recap_stats_json: Mapped[list] = mapped_column(JSON, default=list)
    previous_event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    next_event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    recap_published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
