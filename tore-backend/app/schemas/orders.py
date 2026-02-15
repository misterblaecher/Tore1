from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class CreateOrderItem(BaseModel):
    item_id: int
    variant_id: Optional[int] = None
    qty: int = Field(ge=1, le=50)
    market_item_id: Optional[int] = None


class CreateOrderIn(BaseModel):
    bar_id: int
    event_id: Optional[int] = None
    user_id: Optional[str] = None
    device_id: Optional[str] = None
    items: List[CreateOrderItem]
    note: Optional[str] = None
    zone_id: Optional[int] = None
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
    market_item_id: Optional[int] = None


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
    zone_id: Optional[int] = None
    zone_name: Optional[str] = None
    source: str
    idempotency_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemOut]


class OrderStatusPatchIn(BaseModel):
    status: str


class OrdersLiveOut(BaseModel):
    items: List[OrderOut]
    next_cursor: Optional[str] = None


class BarLiveOrderOut(BaseModel):
    id: int
    createdAt: datetime
    status: Literal["pending", "preparing", "ready", "claimed", "canceled"]
    totalTickets: int
    itemsSummary: str
    customerLabel: Optional[str] = None
    expiresAt: Optional[datetime] = None


class BarLiveOrdersOut(BaseModel):
    items: List[BarLiveOrderOut]


class BarOrderCancelIn(BaseModel):
    reason: str = Field(min_length=2, max_length=240)


class BarOrderAcceptIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=240)


class OrderClientQrOut(BaseModel):
    order_id: int
    qr_raw: str
    expires_at: datetime


class OrderClientQrScanIn(BaseModel):
    raw: Optional[str] = Field(default=None, min_length=8)
    ot: Optional[str] = Field(default=None, min_length=8)
    idempotency_key: str = Field(min_length=4, max_length=120)


class OrderClientQrScanOut(BaseModel):
    idempotent: bool
    order: OrderOut
    user_visible_to_staff: bool
    identity_visible: bool


class InventoryAlertOut(BaseModel):
    drinkId: int
    name: str
    status: Literal["LOW", "OUT"]
    remaining: Optional[int] = None


class BarDashboardEventSnapshotOut(BaseModel):
    eventState: str
    lastUpdatedAt: datetime


class BarDashboardOut(BaseModel):
    event: BarDashboardEventSnapshotOut
    ordersPending: int
    ordersPreparing: int
    ordersReady: int
    ordersTotalToday: int
    itemsSoldToday: Optional[int] = None
    revenueTicketsToday: int
    avgPrepTime: Optional[float] = None
    inventoryAlerts: List[InventoryAlertOut]
    lastUpdatedAt: datetime
