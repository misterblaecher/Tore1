from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WalletAdminTopupIn(BaseModel):
    event_id: int
    target_user_id: Optional[str] = None
    user_id: Optional[str] = None
    amount_cents: Optional[int] = Field(default=None, ge=1, le=1000000)
    amount_tickets: Optional[int] = Field(default=None, ge=1, le=1000000)
    note: Optional[str] = Field(default=None, min_length=2, max_length=255)
    reason: Optional[str] = Field(default=None, min_length=2, max_length=255)
    reason_code: Optional[str] = Field(default=None, min_length=2, max_length=64)
    reason_text: Optional[str] = Field(default=None, min_length=2, max_length=255)
    client_key: Optional[str] = Field(default=None, min_length=1, max_length=128)
    idempotency_key: Optional[str] = Field(default=None, min_length=1, max_length=128)


class WalletAdminTopupOut(BaseModel):
    ledger_id: int
    event_id: int
    user_id: str
    amount_tickets: int
    reason: str
    balance_tickets: int
    idempotent: bool = False
    created_at: datetime


class WalletAdminExportRow(BaseModel):
    ts: datetime
    user_id: str
    type: str
    amount: int
    note: str
    ref_id: str


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
