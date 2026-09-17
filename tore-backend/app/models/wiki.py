from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from db import Base, now_utc

class StructurePageRevision(Base):
    __tablename__ = "structure_page_revisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("structure_pages.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, default="")
    author_user_id: Mapped[str] = mapped_column(String(120))
    message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
