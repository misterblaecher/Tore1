from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel


class QrResolveIn(BaseModel):
    raw: str


class QrResolveOut(BaseModel):
    valid: bool
    type: str
    event_id: Optional[int] = None
    bar_id: Optional[int] = None
    item_id: Optional[int] = None
    category_id: Optional[int] = None
    zone_id: Optional[int] = None
    bet_id: Optional[int] = None
    order_id: Optional[int] = None
    battle_id: Optional[int] = None
    scope: Optional[str] = None
    route_front: Optional[str] = None
    token: Optional[str] = None
    user_id: Optional[str] = None
    amount_tickets: Optional[int] = None
    idempotency_key: Optional[str] = None
    reason: Optional[str] = None
    required_role: Optional[str] = None
    granted_role: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
