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


class WalletTopupIn(BaseModel):
    user_id: str
    amount_tickets: int = Field(ge=1)
    idempotency_key: str
    raw_qr: Optional[str] = None


class WalletTopupFromQrIn(BaseModel):
    raw_qr: str
