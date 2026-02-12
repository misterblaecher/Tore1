from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DrinkMarketConfigOut(BaseModel):
    id: int
    bar_id: int
    event_id: Optional[int] = None
    is_live: bool
    ticket_value_cents: Optional[int] = None
    price_floor_cents: int
    price_cap_cents: int
    step_cents: int
    updated_at: datetime
    created_at: datetime


class DrinkMarketItemOut(BaseModel):
    id: int
    config_id: int
    name: str
    is_active: bool
    base_price_cents: int
    current_price_cents: int
    unit: str
    sort_order: int


class DrinkPriceTickOut(BaseModel):
    id: int
    item_id: int
    price_cents: int
    ts: datetime
    source: str
    actor_user_id: Optional[int] = None


class MarketPublicOut(BaseModel):
    config: DrinkMarketConfigOut
    items: list[DrinkMarketItemOut]
    ticker: list[DrinkPriceTickOut]


class MarketItemHistoryOut(BaseModel):
    item: DrinkMarketItemOut
    history: list[DrinkPriceTickOut]


class MarketConfigUpsertIn(BaseModel):
    event_id: Optional[int] = None
    is_live: Optional[bool] = None
    ticket_value_cents: Optional[int] = Field(default=None, ge=1)
    price_floor_cents: Optional[int] = Field(default=None, ge=1)
    price_cap_cents: Optional[int] = Field(default=None, ge=1)
    step_cents: Optional[int] = Field(default=None, ge=1)


class MarketItemCreateIn(BaseModel):
    event_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=180)
    base_price_cents: int = Field(ge=1)
    unit: str = Field(default="unit", max_length=40)
    sort_order: int = 0


class MarketItemPatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=180)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    base_price_cents: Optional[int] = Field(default=None, ge=1)


class MarketSetPriceIn(BaseModel):
    price_cents: int = Field(ge=1)
    idempotency_key: Optional[str] = Field(default=None, min_length=1, max_length=120)


class MarketSetPriceOut(BaseModel):
    item: DrinkMarketItemOut
    tick: DrinkPriceTickOut
