from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WalletAdminTopupIn(BaseModel):
    event_id: int
    user_id: str
    amount_tickets: int = Field(ge=1, le=1000000)
    reason: str = Field(min_length=2, max_length=255)
    idempotency_key: str = Field(min_length=4, max_length=128)


class WalletAdminTopupOut(BaseModel):
    ledger_id: int
    event_id: int
    user_id: str
    amount_tickets: int
    reason: str
    balance_tickets: int
    idempotent: bool = False
    created_at: datetime


class WalletAdminLogOut(BaseModel):
    id: int
    event_id: int
    user_id: str
    amount_tickets: int
    reason: str
    idempotency_key: str
    created_at: datetime


class WalletAdminLogPageOut(BaseModel):
    items: list[WalletAdminLogOut]
    next_cursor: Optional[str] = None
