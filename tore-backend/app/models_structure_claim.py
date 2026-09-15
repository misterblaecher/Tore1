from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, now_utc


class StructureClaim(Base):
    """A request to receive ownership of an existing Structure.

    Creating a claim never changes structure permissions. Ownership is granted
    only by the explicit approval transition in the claim service.
    """

    __tablename__ = "structure_claims"
    __table_args__ = (
        Index("ix_structure_claims_structure_status", "structure_id", "status"),
        Index("ix_structure_claims_claimant_status", "claimant_user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    structure_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    claimant_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)

    reviewer_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("app_users.id"), nullable=True, index=True
    )
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: now_utc(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: now_utc(), index=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )
