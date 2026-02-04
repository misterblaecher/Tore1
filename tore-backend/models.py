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


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    name: Mapped[str] = mapped_column(String, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    ends_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc() + timedelta(hours=6))

    entry_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    ticket_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    ticket_value_cents: Mapped[int] = mapped_column(Integer, default=200)

    allow_self_ticket_adjust: Mapped[bool] = mapped_column(Boolean, default=True)

    bar: Mapped["Bar"] = relationship(back_populates="events")
    drinks: Mapped[List["EventDrink"]] = relationship(back_populates="event")


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


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    pay_mode: Mapped[str] = mapped_column(String, default="tickets")
    is_gift: Mapped[bool] = mapped_column(Boolean, default=False)
    gift_to_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    items: Mapped[List["OrderItem"]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    drink_id: Mapped[int] = mapped_column(Integer, index=True)
    qty: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_cents: Mapped[int] = mapped_column(Integer, default=0)

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
    event_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String, default="Battle")
    mode: Mapped[str] = mapped_column(String, default="1v1")
    join_code: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    ended: Mapped[bool] = mapped_column(Boolean, default=False)
    winner_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class BattleParticipant(Base):
    __tablename__ = "battle_participants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    battle_id: Mapped[int] = mapped_column(ForeignKey("battles.id"), index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    display_name: Mapped[str] = mapped_column(String, default="")

    # Stats
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)

    battle: Mapped["Battle"] = relationship()
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


class AppToken(Base):
    __tablename__ = "app_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)

    # ✅ SHA256 hex = 64 chars
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["AppUser"] = relationship(back_populates="tokens")

