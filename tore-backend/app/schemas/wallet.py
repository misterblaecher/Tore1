from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class WalletTxOut(BaseModel):
    id: int
    user_id: str
    kind: str
    amount_tickets: int
    ref_type: str
    ref_id: Optional[str] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    idempotency_key: Optional[str] = None


class WalletMeOut(BaseModel):
    user_id: str
    balance_tickets: int
    updated_at: datetime
    transactions: List[WalletTxOut]


class WalletMeLiteOut(BaseModel):
    balance_tickets: int
    updated_at: datetime


class WalletLedgerRowOut(BaseModel):
    id: int
    ts: datetime
    type: str
    amount: int
    ref_id: Optional[str] = None
    note: Optional[str] = None


class WalletLedgerPageOut(BaseModel):
    items: List[WalletLedgerRowOut]
    next_cursor: Optional[str] = None


class WalletGiftIn(BaseModel):
    event_id: Optional[int] = None
    to_user_id: str
    amount_cents: int = Field(le=1000000)
    message: Optional[str] = Field(default=None, max_length=255)
    client_key: Optional[str] = Field(default=None, min_length=1, max_length=128)


class WalletGiftOut(BaseModel):
    gift_id: int
    new_balance_sender: int


class WalletGiftRowOut(BaseModel):
    id: int
    ts: datetime
    direction: str
    amount: int
    counterparty_user_id: str
    message: Optional[str] = None


class WalletGiftPageOut(BaseModel):
    items: List[WalletGiftRowOut]
    next_cursor: Optional[str] = None


class WalletTopupIn(BaseModel):
    user_id: str
    amount_tickets: int = Field(ge=1)
    idempotency_key: str
    raw_qr: Optional[str] = None


class WalletTopupFromQrIn(BaseModel):
    raw_qr: str


class WalletMyQrOut(BaseModel):
    user_id: str
    event_id: int
    qr_type: str
    deeplink: str
