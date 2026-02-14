from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import (
    Integer,
    Float,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Text,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base, now_utc

class Bar(Base):
    __tablename__ = "bars"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    city: Mapped[str] = mapped_column(String, default="")

    # Localisation (V1: floats, sans PostGIS)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    partner_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)

    events: Mapped[List["Event"]] = relationship(back_populates="bar")

    partner_accesses: Mapped[List["PartnerBarAccess"]] = relationship(
        back_populates="bar", cascade="all, delete-orphan"
    )
    menu_categories: Mapped[List["MenuCategory"]] = relationship(
        back_populates="bar", cascade="all, delete-orphan"
    )
    menu_items: Mapped[List["MenuItem"]] = relationship(
        back_populates="bar", cascade="all, delete-orphan"
    )


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bars.id"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    ends_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc() + timedelta(hours=6))

    entry_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    ticket_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    ticket_value_cents: Mapped[int] = mapped_column(Integer, default=200)

    allow_self_ticket_adjust: Mapped[bool] = mapped_column(Boolean, default=True)

    bar: Mapped["Bar"] = relationship(back_populates="events")
    drinks: Mapped[List["EventDrink"]] = relationship(back_populates="event")


class EventModuleConfig(Base):
    __tablename__ = "event_module_configs"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_module_config_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    orders_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    market_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    battles_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    hunt_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    polymarket_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    entry_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    checkins_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    wifi_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    safety_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("partner_users.id"), nullable=True
    )




class EventRuntimeState(Base):
    __tablename__ = "event_runtime_states"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_runtime_state_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    state: Mapped[str] = mapped_column(String(24), default="LIVE")
    reason: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)

class Hunt(Base):
    __tablename__ = "hunts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bars.id"), index=True, nullable=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(180), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    reward_tickets: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class HuntPoint(Base):
    __tablename__ = "hunt_points"
    __table_args__ = (
        UniqueConstraint("secret_code", name="uq_hunt_points_secret_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hunt_id: Mapped[int] = mapped_column(ForeignKey("hunts.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), default="")
    hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    secret_code: Mapped[str] = mapped_column(String(64), index=True)


class HuntScan(Base):
    __tablename__ = "hunt_scans"
    __table_args__ = (
        UniqueConstraint("point_id", "user_id", name="uq_hunt_scans_point_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hunt_id: Mapped[int] = mapped_column(ForeignKey("hunts.id"), index=True)
    point_id: Mapped[int] = mapped_column(ForeignKey("hunt_points.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class Drink(Base):
    __tablename__ = "drinks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    type: Mapped[str] = mapped_column(String, default="beer")


class EventDrink(Base):
    __tablename__ = "event_drinks"
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), primary_key=True)
    drink_id: Mapped[int] = mapped_column(ForeignKey("drinks.id"), primary_key=True)

    base_price_cents: Mapped[int] = mapped_column(Integer, default=250)
    override_price_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Market price (effective if no override)
    current_price_cents: Mapped[int] = mapped_column(Integer, default=250)
    last_price_update: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    event: Mapped["Event"] = relationship(back_populates="drinks")
    drink: Mapped["Drink"] = relationship()


class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    drink_id: Mapped[int] = mapped_column(Integer, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    price_cents: Mapped[int] = mapped_column(Integer)


class DrinkMarketConfig(Base):
    __tablename__ = "drink_market_configs"
    __table_args__ = (UniqueConstraint("bar_id", "event_id", name="uq_drink_market_config_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False)
    ticket_value_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price_floor_cents: Mapped[int] = mapped_column(Integer, default=50)
    price_cap_cents: Mapped[int] = mapped_column(Integer, default=2000)
    step_cents: Mapped[int] = mapped_column(Integer, default=10)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class DrinkMarketItem(Base):
    __tablename__ = "drink_market_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("drink_market_configs.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    base_price_cents: Mapped[int] = mapped_column(Integer)
    current_price_cents: Mapped[int] = mapped_column(Integer)
    unit: Mapped[str] = mapped_column(String(40), default="unit")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class DrinkPriceTick(Base):
    __tablename__ = "drink_price_ticks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("drink_market_items.id"), index=True)
    price_cents: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)
    ref_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)


class DrinkPriceTickIdempotency(Base):
    __tablename__ = "drink_price_tick_idempotency"
    __table_args__ = (UniqueConstraint("item_id", "idempotency_key", name="uq_market_price_idempotency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("drink_market_items.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    tick_id: Mapped[int] = mapped_column(ForeignKey("drink_price_ticks.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class TicketBalance(Base):
    __tablename__ = "ticket_balances"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)


class Ban(Base):
    __tablename__ = "bans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    reason: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class Entry(Base):
    __tablename__ = "entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    pay_mode: Mapped[str] = mapped_column(String, default="manual")
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class EntryLog(Base):
    __tablename__ = "entry_logs"
    __table_args__ = (
        UniqueConstraint("event_id", "idempotency_key", name="uq_entry_logs_event_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    delta: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String, default="scan")
    staff_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    device_id: Mapped[str] = mapped_column(String, default="")
    idempotency_key: Mapped[str] = mapped_column(String, default="")
    raw_qr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class EntryScanLog(Base):
    __tablename__ = "entry_scan_logs"
    __table_args__ = (
        UniqueConstraint("event_id", "payload_hash", name="uq_entry_scan_logs_event_payload"),
        UniqueConstraint("event_id", "scan_id", name="uq_entry_scan_logs_event_scan_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    scan_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    payload_raw: Mapped[str] = mapped_column(Text, default="")
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    decision: Mapped[str] = mapped_column(String(12), default="DENY")
    reason: Mapped[str] = mapped_column(String(120), default="invalid")
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("partner_users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    token_id: Mapped[Optional[int]] = mapped_column(ForeignKey("entry_tokens.id"), nullable=True, index=True)
    token_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)


class EntryToken(Base):
    __tablename__ = "entry_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_entry_tokens_token_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    used_by_partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)
    used_scan_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(12), default="ACTIVE", index=True)


class EventStaff(Base):
    __tablename__ = "event_staff"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_staff_event_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[str] = mapped_column(String, default="entry")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class StaffInviteToken(Base):
    __tablename__ = "staff_invite_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    role: Mapped[str] = mapped_column(String, default="entry")
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class EventAuditLog(Base):
    __tablename__ = "event_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class EventConfig(Base):
    __tablename__ = "event_configs"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_config_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    menu_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    wallet_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    entry_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    checkin_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    battles_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    hunt_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    report_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_user_bets: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    updated_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Bet(Base):
    __tablename__ = "polymarket_bets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(16), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    question: Mapped[str] = mapped_column(String(280), default="")
    kind: Mapped[str] = mapped_column(String(16), default="OBJECTIVE")
    status: Mapped[str] = mapped_column(String(16), default="LIVE")

    deadline_at: Mapped[datetime] = mapped_column(DateTime)
    resolver_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    rules_text: Mapped[str] = mapped_column(Text, default="")
    dispute_window_minutes: Mapped[int] = mapped_column(Integer, default=60)
    created_by_user_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_outcome: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    pool_yes_tickets: Mapped[int] = mapped_column(Integer, default=0)
    pool_no_tickets: Mapped[int] = mapped_column(Integer, default=0)

    positions: Mapped[List["BetPosition"]] = relationship(
        back_populates="bet", cascade="all, delete-orphan"
    )


class BetPosition(Base):
    __tablename__ = "polymarket_positions"
    __table_args__ = (
        UniqueConstraint("bet_id", "user_id", "idempotency_key", name="uq_bet_positions_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bet_id: Mapped[int] = mapped_column(ForeignKey("polymarket_bets.id"), index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    side: Mapped[str] = mapped_column(String(8))
    stake_tickets: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    bet: Mapped["Bet"] = relationship(back_populates="positions")


class BetResolutionLog(Base):
    __tablename__ = "polymarket_resolution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bet_id: Mapped[int] = mapped_column(ForeignKey("polymarket_bets.id"), index=True)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String(20), default="resolve")
    outcome: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class BetDispute(Base):
    __tablename__ = "polymarket_disputes"
    __table_args__ = (
        UniqueConstraint("bet_id", "user_id", name="uq_polymarket_dispute_bet_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bet_id: Mapped[int] = mapped_column(ForeignKey("polymarket_bets.id"), index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class EventConfigLog(Base):
    __tablename__ = "event_config_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    changed_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    changes_json: Mapped[str] = mapped_column(Text, default="{}")


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    bar: Mapped["Bar"] = relationship(back_populates="menu_categories")
    items: Mapped[List["MenuItem"]] = relationship(back_populates="category")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("menu_categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    image_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    alcohol: Mapped[bool] = mapped_column(Boolean, default=False)
    vegan: Mapped[bool] = mapped_column(Boolean, default=False)
    allergens: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    bar: Mapped["Bar"] = relationship(back_populates="menu_items")
    category: Mapped["MenuCategory"] = relationship(back_populates="items")
    variants: Mapped[List["MenuItemVariant"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class MenuItemVariant(Base):
    __tablename__ = "menu_item_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    price_delta_cents: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    item: Mapped["MenuItem"] = relationship(back_populates="variants")


class MenuTrackEvent(Base):
    __tablename__ = "menu_track_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("menu_items.id"), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(16), default="view")
    device_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    changes_json: Mapped[str] = mapped_column(Text, default="{}")


class EventCost(Base):
    __tablename__ = "event_costs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    label: Mapped[str] = mapped_column(String, default="")
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String, default="other")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_event_created", "event_id", "created_at"),
        Index("ix_orders_event_status_created", "event_id", "status", "created_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bars.id"), index=True, nullable=True)
    event_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    zone_id: Mapped[Optional[int]] = mapped_column(ForeignKey("zones.id"), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="NEW", index=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="menu_qr")
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    total_tickets: Mapped[int] = mapped_column(Integer, default=0)
    payment_status: Mapped[str] = mapped_column(String(20), default="UNPAID", index=True)
    pay_mode: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_gift: Mapped[bool] = mapped_column(Boolean, default=False)
    gift_to_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    items: Mapped[List["OrderItem"]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    menu_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("menu_items.id"), index=True, nullable=True)
    variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("menu_item_variants.id"), index=True, nullable=True)
    name_snapshot: Mapped[str] = mapped_column(String(180), default="")
    price_cents_snapshot: Mapped[int] = mapped_column(Integer, default=0)
    qty: Mapped[int] = mapped_column(Integer, default=1)
    line_total_cents: Mapped[int] = mapped_column(Integer, default=0)
    drink_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    unit_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    market_item_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="items")


# --- Untappd-like MVP ---


class Beer(Base):
    __tablename__ = "beers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    barcode: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, default="")
    brewery: Mapped[str] = mapped_column(String, default="")
    style: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class Checkin(Base):
    __tablename__ = "checkins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    beer_id: Mapped[int] = mapped_column(ForeignKey("beers.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer, default=0)  # store *10 as int for sqlite simplicity
    comment: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    beer: Mapped["Beer"] = relationship()


# --- Battles (Afond) MVP ---


class Battle(Base):
    __tablename__ = "battles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bars.id"), index=True, nullable=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(180), default="Battle")
    mode: Mapped[str] = mapped_column(String(16), default="teams")
    status: Mapped[str] = mapped_column(String(16), default="OPEN")
    join_code: Mapped[Optional[str]] = mapped_column(String(16), index=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    winner_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class BattleParticipant(Base):
    __tablename__ = "battle_participants"
    __table_args__ = (UniqueConstraint("battle_id", "user_id", name="uq_battle_participant_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    battle_id: Mapped[int] = mapped_column(ForeignKey("battles.id"), index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class BattleTeam(Base):
    __tablename__ = "battle_teams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    battle_id: Mapped[int] = mapped_column(ForeignKey("battles.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class BattleJoin(Base):
    __tablename__ = "battle_joins"
    __table_args__ = (UniqueConstraint("battle_id", "user_id", name="uq_battle_join_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    battle_id: Mapped[int] = mapped_column(ForeignKey("battles.id"), index=True)
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("battle_teams.id"), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class BattleAction(Base):
    __tablename__ = "battle_actions"
    __table_args__ = (UniqueConstraint("battle_id", "idempotency_key", name="uq_battle_action_idempotency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    battle_id: Mapped[int] = mapped_column(ForeignKey("battles.id"), index=True)
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("battle_teams.id"), nullable=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(16), default="AFFOND")
    delta: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

# --- Partner authentication / bar backoffice ---


class PartnerUser(Base):
    __tablename__ = "partner_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # PIN-based partner auth (nom d'affichage + code PIN hashé)
    display_name: Mapped[str] = mapped_column(String(80), index=True, default="")
    pin_hash: Mapped[str] = mapped_column(String, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    memberships: Mapped[List["PartnerMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    bar_accesses: Mapped[List["PartnerBarAccess"]] = relationship(
        back_populates="partner_user", cascade="all, delete-orphan"
    )



class PartnerBarAccess(Base):
    __tablename__ = "partner_bar_access"
    __table_args__ = (
        UniqueConstraint("partner_user_id", "bar_id", name="uq_partner_user_bar"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    partner_user_id: Mapped[int] = mapped_column(ForeignKey("partner_users.id"), index=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)

    role: Mapped[str] = mapped_column(String, default="owner")  # owner, manager, staff, ...
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    partner_user: Mapped["PartnerUser"] = relationship(back_populates="bar_accesses")
    bar: Mapped["Bar"] = relationship(back_populates="partner_accesses")


class PartnerMagicLinkToken(Base):
    __tablename__ = "partner_magic_link_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    partner_user_id: Mapped[int] = mapped_column(ForeignKey("partner_users.id"), index=True)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    partner_user: Mapped["PartnerUser"] = relationship()

class PartnerMembership(Base):
    __tablename__ = "partner_memberships"
    __table_args__ = (
        UniqueConstraint("bar_id", "display_name", name="uq_membership_bar_display_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("partner_users.id"), index=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)

    role: Mapped[str] = mapped_column(String(20), default="bartender")  # manager | bartender
    display_name: Mapped[str] = mapped_column(String(80), default="")

    user: Mapped["PartnerUser"] = relationship(back_populates="memberships")
    bar: Mapped["Bar"] = relationship()


class PartnerTokenRevocation(Base):
    __tablename__ = "partner_token_revocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    revoked_by_partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)


class PartnerInvite(Base):
    __tablename__ = "partner_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)

    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(20), default="bartender")
    max_uses: Mapped[int] = mapped_column(Integer, default=25)
    uses_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    bar: Mapped["Bar"] = relationship()


# ---------------------------------------------------------------------
# App users (guest auth) — V1
# ---------------------------------------------------------------------

class AppUser(Base):
    __tablename__ = "app_users"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid string
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    display_name: Mapped[str] = mapped_column(String, default="")
    avatar_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    address_text: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    show_address: Mapped[bool] = mapped_column(Boolean, default=False)
    show_avatar: Mapped[bool] = mapped_column(Boolean, default=True)

    tokens: Mapped[List["AppToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Wallet(Base):
    __tablename__ = "wallets"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), primary_key=True)
    balance_tickets: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    user: Mapped["AppUser"] = relationship()


class WalletTx(Base):
    __tablename__ = "wallet_txs"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_wallet_txs_user_idempotency"),
        Index("ix_wallet_txs_user_ts", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="CREDIT")
    amount_tickets: Mapped[int] = mapped_column(Integer)
    ref_type: Mapped[str] = mapped_column(String(20), default="TOPUP_QR")
    ref_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("partner_users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    user: Mapped["AppUser"] = relationship()


class WalletLedgerEntry(Base):
    __tablename__ = "wallet_ledger_entries"
    __table_args__ = (
        UniqueConstraint("event_id", "idempotency_key", name="uq_wallet_ledger_event_idempotency"),
        Index("ix_wallet_ledger_event_ts", "event_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    amount_tickets: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(255), default="")
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("partner_users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class WalletGift(Base):
    __tablename__ = "wallet_gifts"
    __table_args__ = (
        UniqueConstraint("from_user_id", "idempotency_key", name="uq_wallet_gifts_sender_idempotency"),
        Index("ix_wallet_gifts_from_ts", "from_user_id", "created_at"),
        Index("ix_wallet_gifts_to_ts", "to_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    from_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    to_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    amount_tickets: Mapped[int] = mapped_column(Integer)
    message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_event_ts", "event_id", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    actor_partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True, index=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), default="")
    entity_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    bar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bars.id"), nullable=True, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class BarPrivacySetting(Base):
    __tablename__ = "bar_privacy_settings"
    __table_args__ = (UniqueConstraint("bar_id", name="uq_bar_privacy_settings_bar"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    staff_identity_consent_required: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class AppUserPrivacySetting(Base):
    __tablename__ = "app_user_privacy_settings"
    __table_args__ = (UniqueConstraint("user_id", name="uq_app_user_privacy_settings_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    show_identity_to_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class OrderClientQrScan(Base):
    __tablename__ = "order_client_qr_scans"
    __table_args__ = (
        UniqueConstraint("bar_id", "idempotency_key", name="uq_order_client_qr_scan_bar_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    staff_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class BattleSubmit(Base):
    __tablename__ = "battle_submits"
    __table_args__ = (
        UniqueConstraint("battle_id", "scan_id", name="uq_battle_submit_scan"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    battle_id: Mapped[int] = mapped_column(ForeignKey("battles.id"), index=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    scan_id: Mapped[str] = mapped_column(String(120), index=True)
    target_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    points: Mapped[int] = mapped_column(Integer, default=1)
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    validated_by_partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class DrinkCheckin(Base):
    __tablename__ = "drink_checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    drink_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drinks.id"), index=True, nullable=True)
    name_snapshot: Mapped[str] = mapped_column(String(180), default="")
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    bar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bars.id"), index=True, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)




class Zone(Base):
    __tablename__ = "zones"
    __table_args__ = (
        UniqueConstraint("bar_id", "slug", name="uq_zones_bar_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    slug: Mapped[str] = mapped_column(String(120), default="", index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)

class WifiConfig(Base):
    __tablename__ = "wifi_configs"
    __table_args__ = (UniqueConstraint("bar_id", "event_id", name="uq_wifi_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    ssid: Mapped[str] = mapped_column(String(120), default="")
    password_enc: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("partner_users.id"))
    updated_by: Mapped[int] = mapped_column(ForeignKey("partner_users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class SafetyBuddySession(Base):
    __tablename__ = "safety_buddy_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    buddy_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AppToken(Base):
    __tablename__ = "app_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)

    # ✅ SHA256 hex = 64 chars
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["AppUser"] = relationship(back_populates="tokens")
