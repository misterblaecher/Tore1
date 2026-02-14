from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EventModulesOut(BaseModel):
    event_id: int
    orders_enabled: bool
    market_enabled: bool
    battles_enabled: bool
    hunt_enabled: bool
    polymarket_enabled: bool
    entry_enabled: bool
    checkins_enabled: bool
    wifi_enabled: bool
    safety_enabled: bool
    updated_at: Optional[datetime] = None


class EventModulesUpdateIn(BaseModel):
    orders_enabled: Optional[bool] = None
    market_enabled: Optional[bool] = None
    battles_enabled: Optional[bool] = None
    hunt_enabled: Optional[bool] = None
    polymarket_enabled: Optional[bool] = None
    entry_enabled: Optional[bool] = None
    checkins_enabled: Optional[bool] = None
    wifi_enabled: Optional[bool] = None
    safety_enabled: Optional[bool] = None
