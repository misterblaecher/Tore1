from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class CreateOrderItem(BaseModel):
    item_id: int
    variant_id: Optional[int] = None
    qty: int = Field(ge=1, le=50)


class CreateOrderIn(BaseModel):
    bar_id: int
    event_id: Optional[int] = None
    user_id: Optional[str] = None
    device_id: Optional[str] = None
    items: List[CreateOrderItem]
    note: Optional[str] = None
    payment_mode: Literal["pay_later", "tickets"] = "pay_later"
    idempotency_key: str = Field(min_length=4, max_length=120)


class OrderItemOut(BaseModel):
    id: int
    menu_item_id: Optional[int] = None
    variant_id: Optional[int] = None
    name_snapshot: str
    price_cents_snapshot: int
    qty: int
    line_total_cents: int


class OrderOut(BaseModel):
    id: int
    bar_id: Optional[int] = None
    event_id: Optional[int] = None
    user_id: Optional[str] = None
    status: str
    payment_status: str
    total_cents: int
    total_tickets: int
    note: Optional[str] = None
    source: str
    idempotency_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemOut]


class OrderStatusPatchIn(BaseModel):
    status: str
