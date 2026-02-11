from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class BetOut(BaseModel):
    id: int
    scope: str
    event_id: Optional[int] = None
    question: str
    kind: str
    status: str
    deadline_at: Optional[str] = None
    resolver_user_id: Optional[str] = None
    rules_text: str
    dispute_window_minutes: int
    created_by_user_id: str
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_outcome: Optional[str] = None
    pool_yes_tickets: int
    pool_no_tickets: int
    total_pool_tickets: int
    pct_yes: float
    pct_no: float


class BetCreateIn(BaseModel):
    scope: str
    event_id: Optional[int] = None
    question: str
    kind: str = "OBJECTIVE"
    deadline_at: datetime
    resolver_user_id: Optional[str] = None
    rules_text: str
    dispute_window_minutes: int = Field(default=60, ge=1, le=1440)


class BetPositionCreateIn(BaseModel):
    side: str
    stake_tickets: int = Field(ge=1, le=1000000)
    idempotency_key: str = Field(min_length=4, max_length=64)


class BetPositionOut(BaseModel):
    id: int
    bet_id: int
    user_id: str
    side: str
    stake_tickets: int
    created_at: Optional[str] = None


class BetPositionResponseOut(BaseModel):
    bet: BetOut
    position: BetPositionOut


class BetDetailOut(BetOut):
    positions_count: int
    user_position: Optional[Dict[str, Any]] = None


class BetMeOut(BaseModel):
    bet_id: int
    user_id: str
    stake_yes: int
    stake_no: int
    stake_total: int
    payout_yes: float
    payout_no: float
    wallet_balance_tickets: Optional[int] = None


class BetResolveIn(BaseModel):
    outcome: str


class BetTimelinePointOut(BaseModel):
    timestamp: str
    pct_yes: float
    total_pool_tickets: int


class BetShareOut(BaseModel):
    deep_link: str
    web_url: str
    qr_payload: str
