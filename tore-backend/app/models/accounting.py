from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from db import Base, now_utc

class StructureBudget(Base):
    __tablename__ = "structure_budgets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    period: Mapped[str] = mapped_column(String(32), default="ANNUAL")
    status: Mapped[str] = mapped_column(String(16), default="COLLECTING", index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

class BudgetCategory(Base):
    __tablename__ = "budget_categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("structure_budgets.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    budget_cents: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class AccountingEntry(Base):
    __tablename__ = "accounting_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    budget_id: Mapped[Optional[int]] = mapped_column(ForeignKey("structure_budgets.id", ondelete="SET NULL"), nullable=True, index=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(120))
    entry_type: Mapped[str] = mapped_column(String(16))
    amount_cents: Mapped[int] = mapped_column(Integer)
    entry_date: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachment_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
