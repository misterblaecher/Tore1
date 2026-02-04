from __future__ import annotations

import os
import logging
import secrets
import string
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

import jwt
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db import Base, engine, get_session, now_utc, DATABASE_URL
from models import (
    Bar,
    Event,
    Drink,
    EventDrink,
    PriceHistory,
    TicketBalance,
    Ban,
    Entry,
    Order,
    OrderItem,
    Beer,
    Checkin,
    Battle,
    BattleParticipant,
    AppUser,
    AppToken,
)
from partner_auth import router as partner_auth_router


# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------

JWT_SECRET = os.getenv("TORE_JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"

# Price engine knobs (simple but fun)
MIN_MULT = 0.50
MAX_MULT = 3.00
UP_STEP_PCT = 0.06  # +6% of base per purchase
DECAY_PCT_PER_MIN = 0.01  # 1%/min towards base
HISTORY_MAX_POINTS = 2000


# ---------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------

def get_db() -> Session:
    """
    FastAPI dependency that provides a SQLAlchemy Session.
    """
    db = get_session()
    try:
        yield db
    finally:
        db.close()


def ensure_seed() -> None:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        bar_count = s.scalar(select(func.count()).select_from(Bar)) or 0
        if bar_count == 0:
            b1 = Bar(name="TORÈ Test Bar", city="Liège", partner_code="TORE_TEST_LIEGE")
            b2 = Bar(name="Dow'n Drinks", city="Bruxelles", partner_code="DOWN_BRUX")
            s.add_all([b1, b2])
            s.flush()

            e1 = Event(
                bar_id=b1.id,
                name="Baptême — Soirée Marché",
                starts_at=now_utc(),
                ends_at=now_utc() + timedelta(hours=8),
                entry_price_cents=500,
                ticket_mode=True,
                ticket_value_cents=200,
                allow_self_ticket_adjust=True,
            )
            e2 = Event(
                bar_id=b1.id,
                name="Afond Night (gratuit)",
                starts_at=now_utc(),
                ends_at=now_utc() + timedelta(hours=6),
                entry_price_cents=0,
                ticket_mode=False,
                ticket_value_cents=200,
                allow_self_ticket_adjust=True,
            )
            s.add_all([e1, e2])
            s.flush()

            drinks = [
                Drink(name="Pils", type="beer"),
                Drink(name="Jupiler", type="beer"),
                Drink(name="Shot", type="shot"),
                Drink(name="Cocktail", type="cocktail"),
                Drink(name="Soft", type="soft"),
            ]
            s.add_all(drinks)
            s.flush()

            def add_event_drinks(ev: Event) -> None:
                base_prices = [250, 280, 220, 650, 200]
                for d, p in zip(drinks, base_prices):
                    ed = EventDrink(
                        event_id=ev.id,
                        drink_id=d.id,
                        base_price_cents=p,
                        current_price_cents=p,
                        last_price_update=now_utc(),
                    )
                    s.add(ed)
                    s.add(PriceHistory(event_id=ev.id, drink_id=d.id, price_cents=p, ts=now_utc()))

            add_event_drinks(e1)
            add_event_drinks(e2)
            s.commit()
    finally:
        s.close()


def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


def apply_decay(s: Session, event_id: int, t: Optional[datetime] = None) -> None:
    """Move current prices slowly back towards base (market cool-down).
    Robuste face à naive/aware + last_price_update None.
    """
    t = t or now_utc()
    if getattr(t, "tzinfo", None) is not None:
        t = t.replace(tzinfo=None)

    ev = s.get(Event, event_id)
    ev_starts = getattr(ev, "starts_at", None) if ev else None
    if ev_starts is not None and getattr(ev_starts, "tzinfo", None) is not None:
        ev_starts = ev_starts.replace(tzinfo=None)

    rows = s.scalars(select(EventDrink).where(EventDrink.event_id == event_id)).all()
    changed = False

    for ed in rows:
        last = ed.last_price_update or ev_starts or t
        if getattr(last, "tzinfo", None) is not None:
            last = last.replace(tzinfo=None)

        dt_min = max(0.0, (t - last).total_seconds() / 60.0)
        if dt_min < 1e-6:
            continue

        base = ed.base_price_cents
        cur = ed.current_price_cents

        steps = int(dt_min)
        if steps <= 0:
            continue

        for _ in range(min(steps, 180)):
            cur = int(cur + (base - cur) * DECAY_PCT_PER_MIN)

        if cur != ed.current_price_cents:
            ed.current_price_cents = cur
            ed.last_price_update = t
            changed = True
            s.add(PriceHistory(event_id=event_id, drink_id=ed.drink_id, price_cents=cur, ts=t))

    if changed:
        _trim_history(s, event_id)
        s.commit()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    from math import radians, sin, cos, sqrt, atan2
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> AppUser:
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing token")

    # HTTPBearer fournit déjà scheme + credentials séparés.
    raw = credentials.credentials or ""

    # Nettoyage ultra-robuste (PowerShell / curl / guillemets / espaces)
    raw = raw.strip().strip('"').strip("'").strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()

    token_hash = _hash_token(raw)

    tok = (
        db.query(AppToken)
        .filter(AppToken.token_hash == token_hash, AppToken.revoked_at.is_(None))
        .first()
    )
    if not tok:
        raise HTTPException(status_code=401, detail="Invalid token")

    # IMPORTANT: charger explicitement l'utilisateur dans CE session
    user = db.get(AppUser, tok.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def _effective_user_id(token_user: Optional[AppUser], user_id: Optional[str]) -> str:
    if token_user and user_id and user_id != token_user.id:
        raise HTTPException(403, "Forbidden")
    return token_user.id if token_user else (user_id or "")


def _trim_history(s: Session, event_id: int) -> None:
    drink_ids = s.scalars(select(EventDrink.drink_id).where(EventDrink.event_id == event_id)).all()
    for did in drink_ids:
        q = (
            select(PriceHistory.id)
            .where(PriceHistory.event_id == event_id, PriceHistory.drink_id == did)
            .order_by(PriceHistory.ts.desc())
        )
        ids = s.scalars(q).all()
        if len(ids) > HISTORY_MAX_POINTS:
            to_del = ids[HISTORY_MAX_POINTS:]
            s.query(PriceHistory).filter(PriceHistory.id.in_(to_del)).delete(synchronize_session=False)


def market_buy(s: Session, event_id: int, drink_id: int, qty: int) -> int:
    ed = s.get(EventDrink, {"event_id": event_id, "drink_id": drink_id})
    if not ed:
        raise HTTPException(404, "Drink not in this event")

    apply_decay(s, event_id)

    base = ed.base_price_cents
    cur = ed.current_price_cents
    lo = int(base * MIN_MULT)
    hi = int(base * MAX_MULT)
    step = max(10, int(base * UP_STEP_PCT))

    for _ in range(qty):
        cur = clamp(cur + step, lo, hi)
        s.add(PriceHistory(event_id=event_id, drink_id=drink_id, price_cents=cur, ts=now_utc()))

    ed.current_price_cents = cur
    ed.last_price_update = now_utc()
    s.add(ed)
    _trim_history(s, event_id)
    return cur


def random_code(n: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def is_banned(s: Session, event_id: int, user_id: str) -> Optional[Ban]:
    return s.scalar(select(Ban).where(Ban.event_id == event_id, Ban.user_id == user_id))


def get_or_create_balance(s: Session, event_id: int, user_id: str) -> TicketBalance:
    b = s.scalar(
        select(TicketBalance).where(
            TicketBalance.event_id == event_id, TicketBalance.user_id == user_id
        )
    )
    if b:
        return b
    b = TicketBalance(event_id=event_id, user_id=user_id, balance=0)
    s.add(b)
    s.flush()
    return b


# ---------------------------------------------------------------------
# API schemas
# ---------------------------------------------------------------------

class GuestIn(BaseModel):
    display_name: str | None = None


class GuestOut(BaseModel):
    token: str
    user: Dict[str, Any]


class PatchMeIn(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    address_text: Optional[str] = None
    show_address: Optional[bool] = None
    show_avatar: Optional[bool] = None


class CreditTicketsIn(BaseModel):
    event_id: int
    user_id: str
    delta: int


class CreateOrderItem(BaseModel):
    drink_id: int
    qty: int = Field(ge=1, le=50)


class CreateOrderIn(BaseModel):
    event_id: int
    user_id: str
    pay_mode: str = Field(default="tickets")
    items: List[CreateOrderItem]
    is_gift: bool = False
    gift_to_user_id: Optional[str] = None


class IssueEntryIn(BaseModel):
    user_id: str
    pay_mode: str = "manual"


class SetPricesIn(BaseModel):
    prices: List[Dict[str, Any]]


class SetTicketValueIn(BaseModel):
    ticket_value_cents: int = Field(ge=1)


class CrashIn(BaseModel):
    percent_down: int = Field(ge=10, le=90)


class ScanEntryIn(BaseModel):
    qr_payload: str


class BanIn(BaseModel):
    user_id: str
    reason: str = "reason"


class CreateBeerIn(BaseModel):
    barcode: str
    name: str
    brewery: str = ""
    style: str = ""


class CreateCheckinIn(BaseModel):
    user_id: str
    beer_id: int
    rating: float = Field(ge=0, le=5)
    comment: str = ""


class CreateBattleIn(BaseModel):
    user_id: str
    title: str = "Battle"
    mode: str = "1v1"
    event_id: Optional[int] = None


class JoinBattleIn(BaseModel):
    user_id: str
    join_code: str
    display_name: str = "Player"


class WinnerIn(BaseModel):
    user_id: str
    winner_user_id: str


# ---------------------------------------------------------------------
# App
# ---------------------------------------------------------------------

app = FastAPI(title="TORÈ backend", version="0.1.0")

logging.basicConfig(level=logging.INFO)
logging.info(f"BOOT commit={os.getenv('RENDER_GIT_COMMIT')} db={DATABASE_URL}")

app.include_router(partner_auth_router, prefix="/partner")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    ensure_seed()


# ---------------------------------------------------------------------
# Debug endpoints (pour diagnostiquer ton 401)
# ---------------------------------------------------------------------

@app.get("/debug/echo-auth")
def echo_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        return {"ok": False, "reason": "no credentials"}

    raw = credentials.credentials or ""
    raw_clean = raw.strip().strip('"').strip("'").strip()
    if raw_clean.lower().startswith("bearer "):
        raw_clean = raw_clean[7:].strip()

    return {
        "scheme": credentials.scheme,
        "raw_repr": repr(raw),
        "raw_len": len(raw),
        "raw_clean_repr": repr(raw_clean),
        "raw_clean_len": len(raw_clean),
        "hash_clean": _hash_token(raw_clean),
    }


@app.get("/debug/auth-check")
def debug_auth_check(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    if not credentials:
        return {"ok": False, "reason": "no credentials"}

    raw = (credentials.credentials or "").strip().strip('"').strip("'").strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()

    h = _hash_token(raw)
    tok = db.query(AppToken).filter(AppToken.token_hash == h, AppToken.revoked_at.is_(None)).first()
    user = db.get(AppUser, tok.user_id) if tok else None

    return {
        "ok": bool(tok and user),
        "hash": h,
        "tok_found": bool(tok),
        "user_found": bool(user),
        "user_id": (user.id if user else None),
        "db_url": DATABASE_URL,
    }


# ---------------------------------------------------------------------
# Guest auth + profil
# ---------------------------------------------------------------------

@app.post("/auth/guest", response_model=GuestOut)
def auth_guest(payload: GuestIn):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        user_id = secrets.token_hex(16)
        u = AppUser(
            id=user_id,
            display_name=(payload.display_name or ""),
            show_address=False,
            show_avatar=True,
        )
        s.add(u)
        s.flush()

        raw = secrets.token_urlsafe(32)
        th = _hash_token(raw)
        t = AppToken(user_id=u.id, token_hash=th)
        s.add(t)
        s.commit()

        return {
            "token": raw,
            "user": {
                "id": u.id,
                "display_name": u.display_name,
                "avatar_url": u.avatar_url,
                "address_text": u.address_text,
                "show_address": u.show_address,
                "show_avatar": u.show_avatar,
            },
        }
    finally:
        s.close()


@app.get("/auth/me")
def me(user: AppUser = Depends(get_current_user)):
    return {
        "id": user.id,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "address_text": user.address_text,
        "show_address": user.show_address,
        "show_avatar": user.show_avatar,
    }


@app.patch("/auth/me")
def patch_me(payload: PatchMeIn, user: AppUser = Depends(get_current_user)):
    s = get_session()
    try:
        u = s.get(AppUser, user.id)
        if not u:
            raise HTTPException(404, "User not found")

        if payload.display_name is not None:
            u.display_name = payload.display_name
        if payload.avatar_url is not None:
            u.avatar_url = payload.avatar_url
        if payload.address_text is not None:
            u.address_text = payload.address_text
        if payload.show_address is not None:
            u.show_address = payload.show_address
        if payload.show_avatar is not None:
            u.show_avatar = payload.show_avatar

        s.add(u)
        s.commit()

        return {
            "id": u.id,
            "display_name": u.display_name,
            "avatar_url": u.avatar_url,
            "address_text": u.address_text,
            "show_address": u.show_address,
            "show_avatar": u.show_avatar,
        }
    finally:
        s.close()


# ---------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------

@app.get("/bars")
def list_bars():
    s = get_session()
    try:
        rows = s.scalars(select(Bar)).all()
        return [{"id": b.id, "name": b.name, "city": b.city} for b in rows]
    finally:
        s.close()


@app.get("/bars/nearby")
def bars_nearby(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(5.0, ge=0.1, le=100.0),
):
    s = get_session()
    try:
        rows = s.scalars(select(Bar)).all()
        out = []
        for b in rows:
            if b.lat is None or b.lng is None:
                continue
            d = haversine_km(lat, lng, float(b.lat), float(b.lng))
            if d <= radius_km:
                out.append(
                    {
                        "id": b.id,
                        "name": b.name,
                        "city": b.city,
                        "lat": b.lat,
                        "lng": b.lng,
                        "distance_km": round(d, 3),
                    }
                )
        out.sort(key=lambda x: x["distance_km"])
        return out
    finally:
        s.close()


@app.get("/bars/{bar_id}/events")
def list_events(bar_id: int):
    s = get_session()
    try:
        rows = s.scalars(
            select(Event).where(Event.bar_id == bar_id).order_by(Event.starts_at.desc())
        ).all()
        return [
            {
                "id": e.id,
                "bar_id": e.bar_id,
                "name": e.name,
                "starts_at": e.starts_at.isoformat(),
                "ends_at": e.ends_at.isoformat(),
                "entry_price_cents": e.entry_price_cents,
                "ticket_mode": e.ticket_mode,
                "ticket_value_cents": e.ticket_value_cents,
            }
            for e in rows
        ]
    finally:
        s.close()


@app.get("/events/{event_id}")
def get_event(event_id: int):
    s = get_session()
    try:
        e = s.get(Event, event_id)
        if not e:
            raise HTTPException(404, "Event not found")
        return {
            "id": e.id,
            "bar_id": e.bar_id,
            "name": e.name,
            "starts_at": e.starts_at.isoformat(),
            "ends_at": e.ends_at.isoformat(),
            "entry_price_cents": e.entry_price_cents,
            "ticket_mode": e.ticket_mode,
            "ticket_value_cents": e.ticket_value_cents,
            "allow_self_ticket_adjust": e.allow_self_ticket_adjust,
        }
    finally:
        s.close()


@app.get("/events/{event_id}/menu")
def event_menu(event_id: int):
    s = get_session()
    try:
        e = s.get(Event, event_id)
        if not e:
            raise HTTPException(404, "Event not found")
        apply_decay(s, event_id)

        rows = s.scalars(select(EventDrink).where(EventDrink.event_id == event_id)).all()
        out = []
        for ed in rows:
            d = s.get(Drink, ed.drink_id)
            if not d:
                continue
            effective = ed.override_price_cents if ed.override_price_cents is not None else ed.current_price_cents
            out.append(
                {
                    "drink_id": d.id,
                    "name": d.name,
                    "type": d.type,
                    "base_price_cents": ed.base_price_cents,
                    "effective_price_cents": effective,
                }
            )
        return out
    finally:
        s.close()


@app.get("/events/{event_id}/drinks/{drink_id}/history")
def price_history(event_id: int, drink_id: int, limit: int = Query(default=120, ge=5, le=500)):
    s = get_session()
    try:
        q = (
            select(PriceHistory)
            .where(PriceHistory.event_id == event_id, PriceHistory.drink_id == drink_id)
            .order_by(PriceHistory.ts.desc())
            .limit(limit)
        )
        rows = list(reversed(s.scalars(q).all()))
        return [{"ts": r.ts.isoformat(), "price_cents": r.price_cents} for r in rows]
    finally:
        s.close()


@app.get("/events/{event_id}/drinks/{drink_id}/ohlc")
def price_ohlc(
    event_id: int,
    drink_id: int,
    bucket_minutes: int = Query(default=5, ge=1, le=60),
    limit: int = Query(default=60, ge=5, le=240),
):
    s = get_session()
    try:
        q = (
            select(PriceHistory)
            .where(PriceHistory.event_id == event_id, PriceHistory.drink_id == drink_id)
            .order_by(PriceHistory.ts.asc())
        )
        rows = s.scalars(q).all()
        if not rows:
            return {"ath": None, "atl": None, "candles": []}

        ath = max(r.price_cents for r in rows)
        atl = min(r.price_cents for r in rows)

        bucket = timedelta(minutes=bucket_minutes)
        candles = []
        cur_bucket_start = rows[0].ts.replace(second=0, microsecond=0)
        cur = []
        for r in rows:
            while r.ts >= cur_bucket_start + bucket:
                if cur:
                    candles.append(_candle(cur_bucket_start, cur))
                cur_bucket_start = cur_bucket_start + bucket
                cur = []
            cur.append(r)
        if cur:
            candles.append(_candle(cur_bucket_start, cur))

        candles = candles[-limit:]
        return {"ath": ath, "atl": atl, "candles": candles}
    finally:
        s.close()


def _candle(start: datetime, rows: List[PriceHistory]) -> Dict[str, Any]:
    prices = [r.price_cents for r in rows]
    return {"ts": start.isoformat(), "open": prices[0], "high": max(prices), "low": min(prices), "close": prices[-1]}


@app.post("/events/{event_id}/entry/issue")
def issue_entry(event_id: int, payload: IssueEntryIn):
    s = get_session()
    try:
        e = s.get(Event, event_id)
        if not e:
            raise HTTPException(404, "Event not found")
        if is_banned(s, event_id, payload.user_id):
            raise HTTPException(403, "User banned")

        entry = Entry(event_id=event_id, user_id=payload.user_id, pay_mode=payload.pay_mode)
        s.add(entry)
        s.flush()

        token = jwt.encode(
            {
                "typ": "entry",
                "entry_id": entry.id,
                "event_id": event_id,
                "user_id": payload.user_id,
                "iat": int((now_utc() - datetime(1970, 1, 1)).total_seconds()),
            },
            JWT_SECRET,
            algorithm=JWT_ALG,
        )
        s.commit()
        return {"entry_id": entry.id, "qr_payload": token}
    finally:
        s.close()


@app.get("/tickets/balance")
def ticket_balance(event_id: int = Query(...), user_id: str = Query(...)):
    s = get_session()
    try:
        b = get_or_create_balance(s, event_id, user_id)
        s.commit()
        return {"event_id": event_id, "user_id": user_id, "balance": b.balance}
    finally:
        s.close()


@app.post("/tickets/credit")
def credit_tickets(payload: CreditTicketsIn):
    s = get_session()
    try:
        e = s.get(Event, payload.event_id)
        if not e:
            raise HTTPException(404, "Event not found")
        if not e.allow_self_ticket_adjust:
            raise HTTPException(403, "Ticket adjust disabled for this event")

        b = get_or_create_balance(s, payload.event_id, payload.user_id)
        b.balance = max(0, b.balance + payload.delta)
        s.add(b)
        s.commit()
        return {"ok": True, "balance": b.balance}
    finally:
        s.close()


@app.post("/orders")
def create_order(payload: CreateOrderIn):
    s = get_session()
    try:
        e = s.get(Event, payload.event_id)
        if not e:
            raise HTTPException(404, "Event not found")
        if is_banned(s, payload.event_id, payload.user_id):
            raise HTTPException(403, "User banned")
        if not payload.items:
            raise HTTPException(400, "Empty order")

        total = 0
        order = Order(
            event_id=payload.event_id,
            user_id=payload.user_id,
            pay_mode=payload.pay_mode,
            is_gift=payload.is_gift,
            gift_to_user_id=payload.gift_to_user_id if payload.is_gift else None,
        )
        s.add(order)
        s.flush()

        for it in payload.items:
            ed = s.get(EventDrink, {"event_id": payload.event_id, "drink_id": it.drink_id})
            if not ed:
                raise HTTPException(404, f"Drink {it.drink_id} not in event")

            unit = ed.override_price_cents if ed.override_price_cents is not None else ed.current_price_cents
            if ed.override_price_cents is None:
                unit = market_buy(s, payload.event_id, it.drink_id, it.qty)

            item = OrderItem(order_id=order.id, drink_id=it.drink_id, qty=it.qty, unit_price_cents=unit)
            s.add(item)
            total += unit * it.qty

        order.total_cents = total
        s.add(order)

        if payload.pay_mode == "tickets" and e.ticket_mode:
            b = get_or_create_balance(s, payload.event_id, payload.user_id)
            needed = (total + e.ticket_value_cents - 1) // e.ticket_value_cents
            if b.balance < needed:
                raise HTTPException(402, f"Not enough tickets (need {needed}, have {b.balance})")
            b.balance -= needed
            s.add(b)

        s.commit()
        return {"id": order.id, "total_cents": total}
    finally:
        s.close()


@app.get("/orders")
def list_orders(event_id: int = Query(...), user_id: str = Query(...)):
    s = get_session()
    try:
        q = (
            select(Order)
            .where(Order.event_id == event_id, Order.user_id == user_id)
            .order_by(Order.created_at.desc())
        )
        rows = s.scalars(q).all()
        return [
            {"id": o.id, "total_cents": o.total_cents, "created_at": o.created_at.isoformat(), "pay_mode": o.pay_mode}
            for o in rows
        ]
    finally:
        s.close()


# ---------------------------------------------------------------------
# Untappd-like MVP
# ---------------------------------------------------------------------

@app.get("/beers/by_barcode/{barcode}")
def beer_by_barcode(barcode: str):
    s = get_session()
    try:
        b = s.scalar(select(Beer).where(Beer.barcode == barcode))
        if not b:
            raise HTTPException(404, "Beer not found")
        return {"id": b.id, "barcode": b.barcode, "name": b.name, "brewery": b.brewery, "style": b.style}
    finally:
        s.close()


@app.post("/beers")
def create_beer(payload: CreateBeerIn):
    s = get_session()
    try:
        existing = s.scalar(select(Beer).where(Beer.barcode == payload.barcode))
        if existing:
            return {"id": existing.id, "barcode": existing.barcode, "name": existing.name, "brewery": existing.brewery, "style": existing.style}
        b = Beer(barcode=payload.barcode, name=payload.name, brewery=payload.brewery, style=payload.style)
        s.add(b)
        s.commit()
        return {"id": b.id, "barcode": b.barcode, "name": b.name, "brewery": b.brewery, "style": b.style, "new": True}
    finally:
        s.close()


@app.get("/checkins")
def list_checkins(user_id: str = Query(...), limit: int = Query(default=30, ge=1, le=200)):
    s = get_session()
    try:
        q = select(Checkin).where(Checkin.user_id == user_id).order_by(Checkin.created_at.desc()).limit(limit)
        rows = s.scalars(q).all()
        out = []
        for c in rows:
            b = s.get(Beer, c.beer_id)
            out.append(
                {
                    "id": c.id,
                    "rating": (c.rating / 10.0),
                    "comment": c.comment,
                    "created_at": c.created_at.isoformat(),
                    "beer": {"id": b.id, "barcode": b.barcode, "name": b.name, "brewery": b.brewery, "style": b.style},
                }
            )
        return out
    finally:
        s.close()


@app.post("/checkins")
def create_checkin(payload: CreateCheckinIn):
    s = get_session()
    try:
        b = s.get(Beer, payload.beer_id)
        if not b:
            raise HTTPException(404, "Beer not found")
        c = Checkin(
            user_id=payload.user_id,
            beer_id=payload.beer_id,
            rating=int(round(payload.rating * 10)),
            comment=payload.comment,
        )
        s.add(c)
        s.commit()
        return {"id": c.id}
    finally:
        s.close()


@app.get("/leaderboard")
def leaderboard(limit: int = Query(default=50, ge=1, le=200)):
    s = get_session()
    try:
        q = (
            select(Checkin.user_id, func.count(Checkin.id).label("checkins"))
            .group_by(Checkin.user_id)
            .order_by(func.count(Checkin.id).desc())
            .limit(limit)
        )
        rows = s.execute(q).all()
        return [{"user_id": user_id, "display_name": user_id, "checkins": cnt} for user_id, cnt in rows]
    finally:
        s.close()


# ---------------------------------------------------------------------
# Battles (Afond) MVP
# ---------------------------------------------------------------------

@app.get("/battles")
def list_battles(event_id: Optional[int] = Query(default=None)):
    s = get_session()
    try:
        q = select(Battle).order_by(Battle.created_at.desc())
        if event_id is not None:
            q = q.where(Battle.event_id == event_id)

        rows = s.scalars(q).all()
        out = []
        for b in rows:
            parts = s.scalars(select(BattleParticipant).where(BattleParticipant.battle_id == b.id)).all()
            out.append(
                {
                    "id": b.id,
                    "event_id": b.event_id,
                    "title": b.title,
                    "mode": b.mode,
                    "join_code": b.join_code,
                    "created_at": b.created_at.isoformat(),
                    "ended": b.ended,
                    "winner_user_id": b.winner_user_id,
                    "participants": [
                        {"user_id": p.user_id, "display_name": p.display_name, "wins": p.wins, "losses": p.losses}
                        for p in parts
                    ],
                }
            )
        return out
    finally:
        s.close()


@app.post("/battles")
def create_battle(payload: CreateBattleIn):
    s = get_session()
    try:
        code = random_code(8)
        while s.scalar(select(Battle).where(Battle.join_code == code)):
            code = random_code(8)
        b = Battle(event_id=payload.event_id, title=payload.title, mode=payload.mode, join_code=code)
        s.add(b)
        s.flush()

        p = BattleParticipant(battle_id=b.id, user_id=payload.user_id, display_name=payload.user_id)
        s.add(p)
        s.commit()
        return {"id": b.id, "join_code": b.join_code}
    finally:
        s.close()


@app.post("/battles/join")
def join_battle(payload: JoinBattleIn):
    s = get_session()
    try:
        b = s.scalar(select(Battle).where(Battle.join_code == payload.join_code))
        if not b:
            raise HTTPException(404, "Battle not found")
        existing = s.scalar(
            select(BattleParticipant).where(
                BattleParticipant.battle_id == b.id, BattleParticipant.user_id == payload.user_id
            )
        )
        if existing:
            return {"ok": True}
        s.add(BattleParticipant(battle_id=b.id, user_id=payload.user_id, display_name=payload.display_name))
        s.commit()
        return {"ok": True}
    finally:
        s.close()


@app.post("/battles/{battle_id}/winner")
def declare_winner(battle_id: int, payload: WinnerIn):
    s = get_session()
    try:
        b = s.get(Battle, battle_id)
        if not b:
            raise HTTPException(404, "Battle not found")
        if b.ended:
            raise HTTPException(400, "Battle already ended")

        participants = s.scalars(select(BattleParticipant).where(BattleParticipant.battle_id == battle_id)).all()
        if not participants:
            raise HTTPException(400, "No participants")

        winner = next((p for p in participants if p.user_id == payload.winner_user_id), None)
        if not winner:
            raise HTTPException(404, "Winner must be a participant")

        for p in participants:
            if p.user_id == winner.user_id:
                p.wins += 1
            else:
                p.losses += 1
            s.add(p)

        b.ended = True
        b.winner_user_id = winner.user_id
        s.add(b)
        s.commit()
        return {"ok": True}
    finally:
        s.close()


# ---------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------

@app.get("/admin/events/{event_id}/prices")
def admin_prices(event_id: int):
    s = get_session()
    try:
        e = s.get(Event, event_id)
        if not e:
            raise HTTPException(404, "Event not found")
        apply_decay(s, event_id)
        rows = s.scalars(select(EventDrink).where(EventDrink.event_id == event_id)).all()
        out = []
        for ed in rows:
            d = s.get(Drink, ed.drink_id)
            if not d:
                continue
            effective = ed.override_price_cents if ed.override_price_cents is not None else ed.current_price_cents
            out.append(
                {
                    "drink_id": d.id,
                    "name": d.name,
                    "type": d.type,
                    "base_price_cents": ed.base_price_cents,
                    "override_price_cents": ed.override_price_cents,
                    "effective_price_cents": effective,
                }
            )
        return out
    finally:
        s.close()


@app.post("/admin/events/{event_id}/prices")
def admin_set_prices(event_id: int, payload: SetPricesIn):
    s = get_session()
    try:
        e = s.get(Event, event_id)
        if not e:
            raise HTTPException(404, "Event not found")
        for p in payload.prices:
            drink_id = int(p.get("drink_id"))
            price_cents = int(p.get("price_cents"))
            ed = s.get(EventDrink, {"event_id": event_id, "drink_id": drink_id})
            if not ed:
                continue
            ed.override_price_cents = price_cents
            s.add(ed)
        s.commit()
        return {"ok": True}
    finally:
        s.close()


@app.post("/admin/events/{event_id}/ticket_value")
def admin_ticket_value(event_id: int, payload: SetTicketValueIn):
    s = get_session()
    try:
        e = s.get(Event, event_id)
        if not e:
            raise HTTPException(404, "Event not found")
        e.ticket_value_cents = payload.ticket_value_cents
        s.add(e)
        s.commit()
        return {"ok": True, "ticket_value_cents": e.ticket_value_cents}
    finally:
        s.close()


@app.post("/admin/events/{event_id}/crash")
def admin_crash(event_id: int, payload: CrashIn):
    s = get_session()
    try:
        e = s.get(Event, event_id)
        if not e:
            raise HTTPException(404, "Event not found")
        apply_decay(s, event_id)
        rows = s.scalars(select(EventDrink).where(EventDrink.event_id == event_id)).all()
        t = now_utc()
        for ed in rows:
            if ed.override_price_cents is not None:
                continue
            new_price = int(ed.current_price_cents * (100 - payload.percent_down) / 100)
            lo = int(ed.base_price_cents * MIN_MULT)
            ed.current_price_cents = clamp(new_price, lo, int(ed.base_price_cents * MAX_MULT))
            ed.last_price_update = t
            s.add(ed)
            s.add(PriceHistory(event_id=event_id, drink_id=ed.drink_id, price_cents=ed.current_price_cents, ts=t))
        _trim_history(s, event_id)
        s.commit()
        return {"ok": True}
    finally:
        s.close()


@app.post("/admin/events/{event_id}/entry/scan")
def admin_scan_entry(event_id: int, payload: ScanEntryIn):
    try:
        data = jwt.decode(payload.qr_payload, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        raise HTTPException(400, "Invalid QR payload")

    if data.get("typ") != "entry" or int(data.get("event_id")) != event_id:
        raise HTTPException(400, "QR not for this event")

    entry_id = int(data.get("entry_id"))
    user_id = str(data.get("user_id"))

    s = get_session()
    try:
        if is_banned(s, event_id, user_id):
            return {"ok": False, "message": "Utilisateur banni"}
        entry = s.get(Entry, entry_id)
        if not entry or entry.event_id != event_id:
            return {"ok": False, "message": "Entrée inconnue"}
        if entry.used:
            return {"ok": False, "message": "Déjà scanné"}
        entry.used = True
        entry.used_at = now_utc()
        s.add(entry)
        s.commit()
        return {"ok": True, "message": f"Entrée OK ({user_id})"}
    finally:
        s.close()


@app.post("/admin/events/{event_id}/ban")
def admin_ban(event_id: int, payload: BanIn):
    s = get_session()
    try:
        e = s.get(Event, event_id)
        if not e:
            raise HTTPException(404, "Event not found")
        b = Ban(event_id=event_id, user_id=payload.user_id, reason=payload.reason)
        s.add(b)
        s.commit()
        return {"ok": True}
    finally:
        s.close()


@app.get("/version")
def version():
    info = {
        "render_git_commit": os.getenv("RENDER_GIT_COMMIT"),
        "database_url": DATABASE_URL,
    }
    if DATABASE_URL.startswith("sqlite:///"):
        info["sqlite_path"] = DATABASE_URL.replace("sqlite:///", "", 1)
    return info
