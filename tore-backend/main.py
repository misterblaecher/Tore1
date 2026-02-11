from __future__ import annotations

# Orders and wallet routes are now implemented in app/routers/orders.py and app/routers/wallet.py.

import os
import logging
import secrets
import string
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Literal
from urllib.parse import urlparse, parse_qs

import jwt
from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, case, text
from sqlalchemy.exc import IntegrityError
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
    EntryLog,
    EventStaff,
    StaffInviteToken,
    EventAuditLog,
    EventConfig,
    EventConfigLog,
    EventCost,
    Order,
    OrderItem,
    Beer,
    Checkin,
    Battle,
    BattleParticipant,
    AppUser,
    AppToken,
    PartnerMembership,
    Wallet,
    WalletTx,
    Bet,
    BetPosition,
    BetResolutionLog,
    MenuCategory,
    MenuItem,
    MenuItemVariant,
    MenuTrackEvent,
)

from partner_auth import router as partner_auth_router, current_identity as current_partner_identity


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

# Polymarket V1
POLYMARKET_TIMELINE_MAX_POINTS = 200


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


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _polymarket_global_creators() -> set[str]:
    raw = os.getenv("POLYMARKET_GLOBAL_CREATORS", "")
    creators = {item.strip() for item in raw.split(",") if item.strip()}
    if not creators:
        return set()
    return creators


def _polymarket_global_enabled() -> bool:
    return _env_bool("POLYMARKET_GLOBAL_ENABLED", False)




def _ensure_orders_payment_columns() -> None:
    if engine.dialect.name != "sqlite":
        return
    s = get_session()
    try:
        columns = {
            row[1]
            for row in s.execute(text("PRAGMA table_info(orders)")).fetchall()
        }
        if "total_tickets" not in columns:
            s.execute(text("ALTER TABLE orders ADD COLUMN total_tickets INTEGER DEFAULT 0"))
        if "payment_status" not in columns:
            s.execute(text("ALTER TABLE orders ADD COLUMN payment_status VARCHAR(20) DEFAULT 'UNPAID'"))
        s.commit()
    finally:
        s.close()

def ensure_seed() -> None:
    Base.metadata.create_all(engine)
    _ensure_orders_payment_columns()
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


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    raw = authorization.strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    raw = raw.strip().strip('"').strip("'").strip()
    return raw or None


def _resolve_app_user_from_token(raw: str, db: Session) -> Optional[AppUser]:
    token_hash = _hash_token(raw)
    tok = (
        db.query(AppToken)
        .filter(AppToken.token_hash == token_hash, AppToken.revoked_at.is_(None))
        .first()
    )
    if not tok:
        return None
    return db.get(AppUser, tok.user_id)


def _resolve_partner_identity_from_token(raw: str, db: Session) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(raw, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None

    try:
        user_id = int(payload.get("sub"))
        bar_id = int(payload.get("bar_id"))
    except (TypeError, ValueError):
        return None

    role = payload.get("role")
    name = payload.get("name")

    m = (
        db.query(PartnerMembership)
        .filter(PartnerMembership.user_id == user_id, PartnerMembership.bar_id == bar_id)
        .first()
    )
    if not m:
        return None

    return {"user_id": user_id, "bar_id": bar_id, "role": role, "display_name": name}


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

def get_or_create_wallet(s: Session, user_id: str) -> Wallet:
    wallet = s.get(Wallet, user_id)
    if wallet:
        return wallet
    wallet = Wallet(user_id=user_id, balance_tickets=0, updated_at=now_utc())
    s.add(wallet)
    s.flush()
    return wallet


def _wallet_tx_out(tx: WalletTx) -> WalletTxOut:
    return WalletTxOut(
        id=tx.id,
        user_id=tx.user_id,
        kind=tx.kind,
        amount_tickets=tx.amount_tickets,
        ref_type=tx.ref_type,
        ref_id=tx.ref_id,
        created_by_user_id=tx.created_by_user_id,
        created_at=tx.created_at,
        idempotency_key=tx.idempotency_key,
    )


def _wallet_tx_exists(s: Session, user_id: str, idempotency_key: str) -> Optional[WalletTx]:
    return (
        s.query(WalletTx)
        .filter(
            WalletTx.user_id == user_id,
            WalletTx.idempotency_key == idempotency_key,
        )
        .first()
    )


def _apply_wallet_tx(
    s: Session,
    *,
    user_id: str,
    amount_tickets: int,
    kind: str,
    ref_type: str,
    ref_id: Optional[str],
    idempotency_key: str,
    created_by_user_id: Optional[int] = None,
) -> tuple[Wallet, WalletTx, bool]:
    wallet = get_or_create_wallet(s, user_id)
    existing = _wallet_tx_exists(s, user_id, idempotency_key)
    if existing:
        return wallet, existing, False

    wallet.balance_tickets += amount_tickets
    wallet.updated_at = now_utc()
    tx = WalletTx(
        user_id=user_id,
        kind=kind,
        amount_tickets=amount_tickets,
        ref_type=ref_type,
        ref_id=ref_id,
        created_by_user_id=created_by_user_id,
        idempotency_key=idempotency_key,
    )
    s.add_all([wallet, tx])
    s.flush()
    return wallet, tx, True


def _wallet_tx_key(prefix: str, bet_id: int, user_id: str) -> str:
    return f"{prefix}:{bet_id}:{user_id}"


def _optional_current_user(
    authorization: Optional[str],
    db: Session,
) -> Optional[AppUser]:
    raw = _extract_bearer_token(authorization)
    if not raw:
        return None
    return _resolve_app_user_from_token(raw, db)


def _bet_total_pool(bet: Bet) -> int:
    return int(bet.pool_yes_tickets or 0) + int(bet.pool_no_tickets or 0)


def _bet_pct_yes(bet: Bet) -> float:
    total = _bet_total_pool(bet)
    if total <= 0:
        return 0.5
    return float(bet.pool_yes_tickets or 0) / float(total)


def _bet_out(bet: Bet) -> Dict[str, Any]:
    total = _bet_total_pool(bet)
    pct_yes = _bet_pct_yes(bet)
    return {
        "id": bet.id,
        "scope": bet.scope,
        "event_id": bet.event_id,
        "question": bet.question,
        "kind": bet.kind,
        "status": bet.status,
        "deadline_at": bet.deadline_at.isoformat() if bet.deadline_at else None,
        "resolver_user_id": bet.resolver_user_id,
        "rules_text": bet.rules_text,
        "dispute_window_minutes": bet.dispute_window_minutes,
        "created_by_user_id": bet.created_by_user_id,
        "created_at": bet.created_at.isoformat() if bet.created_at else None,
        "resolved_at": bet.resolved_at.isoformat() if bet.resolved_at else None,
        "resolved_outcome": bet.resolved_outcome,
        "pool_yes_tickets": bet.pool_yes_tickets,
        "pool_no_tickets": bet.pool_no_tickets,
        "total_pool_tickets": total,
        "pct_yes": pct_yes,
        "pct_no": 1.0 - pct_yes if total > 0 else 0.5,
    }


def _is_polymarket_admin(user_id: str) -> bool:
    allowlist = _polymarket_global_creators()
    return user_id in allowlist if user_id else False


def _normalize_upper(value: Optional[str]) -> str:
    return (value or "").strip().upper()


def _ensure_bet_scope(scope: str) -> str:
    scope = _normalize_upper(scope)
    if scope not in {"GLOBAL", "EVENT"}:
        raise HTTPException(status_code=422, detail="Invalid scope")
    return scope


def _ensure_bet_kind(kind: str) -> str:
    kind = _normalize_upper(kind)
    if kind not in {"OBJECTIVE", "SUBJECTIVE"}:
        raise HTTPException(status_code=422, detail="Invalid kind")
    return kind


def _ensure_bet_side(side: str) -> str:
    side = _normalize_upper(side)
    if side not in {"YES", "NO"}:
        raise HTTPException(status_code=422, detail="Invalid side")
    return side



def resolve_qr_payload(raw: str) -> Dict[str, Any]:
    trimmed = (raw or "").strip()
    if not trimmed:
        return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}

    parsed = urlparse(trimmed)
    if parsed.scheme.lower() != "tore":
        return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}

    qr_type = (parsed.netloc or parsed.path.lstrip("/")).lower()
    if qr_type == "wallet":
        action = parsed.path.lstrip("/").lower()
        if action != "topup":
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        params = parse_qs(parsed.query)
        user_id = (params.get("user_id") or [None])[0]
        amount_raw = (params.get("amount") or [None])[0]
        nonce = (params.get("nonce") or [None])[0]
        if not user_id or not amount_raw or not nonce:
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        try:
            amount_tickets = int(amount_raw)
        except (TypeError, ValueError):
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        if amount_tickets <= 0:
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        return {
            "valid": True,
            "type": "wallet_topup",
            "event_id": None,
            "user_id": user_id,
            "amount_tickets": amount_tickets,
            "idempotency_key": nonce,
            "reason": None,
        }
    params = parse_qs(parsed.query)

    if qr_type == "menu":
        raw_bar_id = (params.get("bar_id") or [None])[0]
        raw_item_id = (params.get("item_id") or [None])[0]
        raw_category_id = (params.get("category_id") or [None])[0]
        try:
            bar_id = int(raw_bar_id) if raw_bar_id is not None else None
            item_id = int(raw_item_id) if raw_item_id is not None else None
            category_id = int(raw_category_id) if raw_category_id is not None else None
        except (TypeError, ValueError):
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        if bar_id is None:
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        route_front = f"/menu/{bar_id}"
        if item_id is not None:
            route_front = f"/menu/{bar_id}/item/{item_id}"
        return {
            "valid": True,
            "type": "menu",
            "event_id": None,
            "bar_id": bar_id,
            "item_id": item_id,
            "category_id": category_id,
            "route_front": route_front,
            "reason": None,
        }

    if qr_type not in {"join", "entry", "admin_config", "staff_entry", "staff_invite"}:
        return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}

    raw_event_id = (params.get("event_id") or [None])[0]
    try:
        event_id = int(raw_event_id) if raw_event_id is not None else None
    except (TypeError, ValueError):
        event_id = None

    if event_id is None:
        return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}

    token = None
    if qr_type == "staff_invite":
        token = (params.get("token") or [None])[0]
        if not token:
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}

    return {"valid": True, "type": qr_type, "event_id": event_id, "bar_id": None, "item_id": None, "category_id": None, "route_front": None, "token": token, "reason": None}


def _role_rank(role: str) -> int:
    if role == "admin":
        return 3
    if role == "entry":
        return 2
    return 1


def resolve_event_role(db: Session, user_id: str, event_id: int) -> str:
    staff = (
        db.query(EventStaff)
        .filter(EventStaff.event_id == event_id, EventStaff.user_id == user_id)
        .first()
    )
    if not staff or staff.is_active is False:
        return "guest"
    role = (staff.role or "").lower()
    if role == "admin":
        return "admin"
    if role == "entry":
        return "entry"
    return "guest"


def default_event_config_payload() -> Dict[str, Any]:
    return {
        "menu_enabled": True,
        "wallet_enabled": True,
        "entry_enabled": False,
        "checkin_enabled": False,
        "battles_enabled": False,
        "hunt_enabled": False,
        "report_enabled": True,
        "allow_user_bets": False,
    }


def get_or_create_event_config(db: Session, event_id: int, commit: bool = False) -> EventConfig:
    cfg = db.query(EventConfig).filter(EventConfig.event_id == event_id).first()
    if cfg:
        return cfg
    defaults = default_event_config_payload()
    cfg = EventConfig(event_id=event_id, **defaults, updated_at=now_utc())
    db.add(cfg)
    db.flush()
    if commit:
        db.commit()
    return cfg


def require_role_for_event(db: Session, user_id: str, event_id: int, required_role: str) -> str:
    granted = resolve_event_role(db, user_id, event_id)
    if _role_rank(granted) < _role_rank(required_role):
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "required_role": required_role},
        )
    return granted


def require_feature(db: Session, event_id: int, feature: str) -> EventConfig:
    cfg = get_or_create_event_config(db, event_id, commit=True)
    enabled = getattr(cfg, feature, None)
    if enabled is not True:
        raise HTTPException(
            status_code=403,
            detail={"error": "feature_disabled", "feature": feature},
        )
    return cfg


def entry_stats(db: Session, event_id: int) -> Dict[str, int]:
    total = db.scalar(
        select(func.coalesce(func.sum(EntryLog.delta), 0)).where(EntryLog.event_id == event_id)
    ) or 0
    since = now_utc() - timedelta(hours=1)
    last_hour = db.scalar(
        select(func.coalesce(func.sum(EntryLog.delta), 0)).where(
            EntryLog.event_id == event_id,
            EntryLog.created_at >= since,
        )
    ) or 0
    return {"total": int(total), "last_hour": int(last_hour)}


def log_event_action(
    db: Session,
    event_id: int,
    actor_user_id: Optional[str],
    action: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    entry = EventAuditLog(
        event_id=event_id,
        actor_user_id=actor_user_id,
        action=action,
        payload_json=json.dumps(payload or {}, ensure_ascii=False),
    )
    db.add(entry)


def generate_staff_invite_token(db: Session) -> str:
    for _ in range(5):
        token = secrets.token_urlsafe(32)
        exists = db.query(StaffInviteToken).filter(StaffInviteToken.token == token).first()
        if not exists:
            return token
    raise HTTPException(status_code=500, detail="token_generation_failed")


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

def _order_out(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        bar_id=order.bar_id,
        event_id=order.event_id,
        user_id=order.user_id,
        status=order.status,
        payment_status=order.payment_status,
        total_cents=order.total_cents,
        total_tickets=order.total_tickets,
        note=order.note,
        source=order.source,
        idempotency_key=order.idempotency_key,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=[
            OrderItemOut(
                id=item.id,
                menu_item_id=item.menu_item_id,
                variant_id=item.variant_id,
                name_snapshot=item.name_snapshot,
                price_cents_snapshot=item.price_cents_snapshot,
                qty=item.qty,
                line_total_cents=item.line_total_cents,
            )
            for item in order.items
        ],
    )



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


class EntryScanIn(BaseModel):
    delta: int = Field(..., description="+1 ou -1")
    source: str = Field(..., description="scan|manual")
    device_id: str
    idempotency_key: str
    raw_qr: Optional[str] = None


class EntryStatsOut(BaseModel):
    total: int
    last_hour: int


class EntryLogOut(BaseModel):
    id: int
    event_id: int
    created_at: datetime
    delta: int
    source: str
    staff_id: Optional[str]
    device_id: str
    idempotency_key: str
    raw_qr: Optional[str]


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


class QrResolveIn(BaseModel):
    raw: str


class QrResolveOut(BaseModel):
    valid: bool
    type: str
    event_id: Optional[int] = None
    bar_id: Optional[int] = None
    item_id: Optional[int] = None
    category_id: Optional[int] = None
    route_front: Optional[str] = None
    token: Optional[str] = None
    user_id: Optional[str] = None
    amount_tickets: Optional[int] = None
    idempotency_key: Optional[str] = None
    reason: Optional[str] = None
    required_role: Optional[str] = None
    granted_role: Optional[str] = None


class StaffInviteIn(BaseModel):
    role: str = "entry"
    max_uses: int = Field(default=1, ge=1, le=50)
    expires_in_hours: int = Field(default=24, ge=1, le=168)


class StaffInviteOut(BaseModel):
    event_id: int
    role: str
    token: str
    invite_qr: str
    expires_at: Optional[str] = None


class StaffAcceptIn(BaseModel):
    token: str


class StaffAcceptOut(BaseModel):
    ok: bool
    role_granted: str


class StaffMemberOut(BaseModel):
    user_id: str
    display_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[str] = None
    created_by_user_id: Optional[str] = None
    revoked_at: Optional[str] = None
    revoked_by_user_id: Optional[str] = None


class EventConfigOut(BaseModel):
    event_id: int
    menu_enabled: bool
    wallet_enabled: bool
    entry_enabled: bool
    checkin_enabled: bool
    battles_enabled: bool
    hunt_enabled: bool
    report_enabled: bool
    allow_user_bets: bool
    updated_at: Optional[str] = None
    updated_by_user_id: Optional[str] = None
    role: Optional[str] = None


class EventConfigPatchIn(BaseModel):
    menu_enabled: Optional[bool] = None
    wallet_enabled: Optional[bool] = None
    entry_enabled: Optional[bool] = None
    checkin_enabled: Optional[bool] = None
    battles_enabled: Optional[bool] = None
    hunt_enabled: Optional[bool] = None
    report_enabled: Optional[bool] = None
    allow_user_bets: Optional[bool] = None


class EventCostIn(BaseModel):
    label: str
    amount_cents: int = Field(ge=0)
    category: str


class EventCostOut(BaseModel):
    id: int
    event_id: int
    label: str
    amount_cents: int
    category: str
    created_at: Optional[str] = None
    created_by_user_id: Optional[str] = None


class CreateEventIn(BaseModel):
    name: str
    starts_at: datetime
    ends_at: datetime
    bar_id: Optional[int] = None
    city: Optional[str] = None


class CreateEventOut(BaseModel):
    event_id: int
    name: str
    starts_at: str
    ends_at: str
    bar_id: Optional[int] = None


class EventSummaryOut(BaseModel):
    id: int
    bar_id: Optional[int] = None
    name: str
    starts_at: datetime
    ends_at: datetime
    entry_price_cents: int
    ticket_mode: bool
    ticket_value_cents: int


class PartnerEventCreateIn(BaseModel):
    name: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    entry_price_cents: Optional[int] = Field(default=None, ge=0)
    tickets_enabled: Optional[bool] = None


class PartnerEventUpdateIn(BaseModel):
    name: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    entry_price_cents: Optional[int] = Field(default=None, ge=0)
    tickets_enabled: Optional[bool] = None
    entry_enabled: Optional[bool] = None


class PartnerEventOut(BaseModel):
    id: int
    bar_id: Optional[int] = None
    name: str
    starts_at: datetime
    ends_at: datetime
    entry_price_cents: int
    tickets_enabled: bool
    entry_enabled: bool


class PartnerEventDrinkOut(BaseModel):
    drink_id: int
    name: str
    type: str
    base_price_cents: int
    current_price_cents: int
    override_price_cents: Optional[int] = None


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


class PartnerEventDrinkIn(BaseModel):
    name: str
    type: str
    base_price_cents: int = Field(ge=0)
    override_price_cents: Optional[int] = Field(default=None, ge=0)


class MenuVariantOut(BaseModel):
    id: int
    name: str
    price_delta_cents: int
    is_active: bool


class MenuItemOut(BaseModel):
    id: int
    bar_id: int
    category_id: int
    name: str
    description: str
    price_cents: int
    image_url: Optional[str] = None
    tags: Optional[str] = None
    is_active: bool
    is_available: bool
    alcohol: bool
    vegan: bool
    allergens: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    variants: List[MenuVariantOut] = []


class MenuCategoryOut(BaseModel):
    id: int
    bar_id: int
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    items: List[MenuItemOut] = []


class MenuPublicOut(BaseModel):
    bar: Dict[str, Any]
    categories: List[MenuCategoryOut]


class MenuCategoryCreateIn(BaseModel):
    name: str
    sort_order: int = 0
    is_active: bool = True


class MenuCategoryUpdateIn(BaseModel):
    name: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class MenuItemCreateIn(BaseModel):
    category_id: int
    name: str
    description: str = ""
    price_cents: int = Field(ge=0)
    image_url: Optional[str] = None
    tags: Optional[str] = None
    is_active: bool = True
    is_available: bool = True
    alcohol: bool = False
    vegan: bool = False
    allergens: Optional[str] = None


class MenuItemUpdateIn(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price_cents: Optional[int] = Field(default=None, ge=0)
    image_url: Optional[str] = None
    tags: Optional[str] = None
    is_active: Optional[bool] = None
    is_available: Optional[bool] = None
    alcohol: Optional[bool] = None
    vegan: Optional[bool] = None
    allergens: Optional[str] = None


class MenuTrackIn(BaseModel):
    bar_id: int
    item_id: Optional[int] = None
    action: str
    event_id: Optional[int] = None
    device_id: Optional[str] = None


class MenuAnalyticsItemOut(BaseModel):
    item_id: int
    item_name: str
    views: int
    clicks: int
    adds: int


class MenuAnalyticsOut(BaseModel):
    period_days: int
    top_items: List[MenuAnalyticsItemOut]


class PartnerBarOut(BaseModel):
    id: int
    name: str
    city: str
    lat: Optional[float] = None
    lng: Optional[float] = None


class QrPackOut(BaseModel):
    event_id: int
    qrs: Dict[str, str]


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

app = FastAPI(
    title="TORÈ backend",
    version="0.1.0",
    swagger_ui_parameters={
        "persistAuthorization": True,
        "docExpansion": "none",
        "filter": True,
    },
)

logging.basicConfig(level=logging.INFO)
logging.info(f"BOOT commit={os.getenv('RENDER_GIT_COMMIT')} db={DATABASE_URL}")

app.include_router(partner_auth_router, prefix="/partner")
from app.routers.orders import router as orders_router
from app.routers.wallet import router as wallet_router
app.include_router(orders_router)
app.include_router(wallet_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    ensure_seed()


@app.get("/partner/portal/bar", response_model=PartnerBarOut)
def partner_portal_bar(
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    bar = db.get(Bar, identity["bar_id"])
    if not bar:
        raise HTTPException(404, "Bar not found")
    return PartnerBarOut(
        id=bar.id,
        name=bar.name,
        city=bar.city,
        lat=bar.lat,
        lng=bar.lng,
    )


@app.get("/partner/portal/events", response_model=List[PartnerEventOut])
def partner_portal_events(
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Event)
        .filter(Event.bar_id == identity["bar_id"])
        .order_by(Event.starts_at.desc())
        .all()
    )
    event_ids = [row.id for row in rows]
    configs = {}
    if event_ids:
        config_rows = db.query(EventConfig).filter(EventConfig.event_id.in_(event_ids)).all()
        configs = {config.event_id: config for config in config_rows}
    return [_partner_event_out(row, configs.get(row.id)) for row in rows]


@app.post("/partner/portal/events", response_model=PartnerEventOut)
def partner_portal_event_create(
    payload: PartnerEventCreateIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    bar = db.get(Bar, identity["bar_id"])
    if not bar:
        raise HTTPException(404, "Bar not found")

    starts_at = payload.start_at or now_utc()
    ends_at = payload.end_at or (starts_at + timedelta(hours=6))
    entry_price_cents = payload.entry_price_cents if payload.entry_price_cents is not None else 0
    ticket_mode = payload.tickets_enabled if payload.tickets_enabled is not None else True

    event = Event(
        bar_id=identity["bar_id"],
        name=payload.name,
        starts_at=starts_at,
        ends_at=ends_at,
        entry_price_cents=entry_price_cents,
        ticket_mode=ticket_mode,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return _partner_event_out(event, None)


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "commit": os.getenv("RENDER_GIT_COMMIT"),
        }
    )


@app.get("/quickstart", response_class=HTMLResponse)
def quickstart() -> HTMLResponse:
    html = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TORÈ Partner QuickStart</title>
  <style>
    :root {
      color-scheme: light dark;
    }
    body {
      font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
      margin: 0;
      background: #0f1115;
      color: #f7f7f7;
    }
    main {
      max-width: 860px;
      margin: 0 auto;
      padding: 32px 20px 60px;
    }
    h1 {
      font-size: 2rem;
      margin-bottom: 6px;
    }
    p {
      line-height: 1.5;
    }
    .card {
      background: #1c1f26;
      border-radius: 12px;
      padding: 20px;
      margin-top: 16px;
      box-shadow: 0 6px 24px rgba(0, 0, 0, 0.3);
    }
    label {
      font-weight: 600;
      display: block;
      margin-bottom: 6px;
    }
    input, select, button, textarea {
      font-size: 1rem;
      padding: 10px 12px;
      border-radius: 8px;
      border: 1px solid #2e3440;
      background: #10131a;
      color: #f7f7f7;
      width: 100%;
      box-sizing: border-box;
    }
    input::placeholder {
      color: #9aa3b2;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }
    .row {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }
    .row > * {
      flex: 1;
    }
    button {
      cursor: pointer;
      background: #2563eb;
      border: none;
      font-weight: 600;
    }
    button.secondary {
      background: #374151;
    }
    button.copy {
      background: #059669;
      max-width: 160px;
    }
    pre {
      background: #0b0d12;
      padding: 12px;
      border-radius: 8px;
      overflow-x: auto;
      font-size: 0.9rem;
    }
    .status {
      margin-top: 10px;
      padding: 10px 12px;
      border-radius: 8px;
      background: #111827;
      border: 1px solid #1f2937;
      font-size: 0.95rem;
      white-space: pre-wrap;
    }
    .status.error {
      border-color: #ef4444;
      color: #fecaca;
    }
    .status.success {
      border-color: #22c55e;
      color: #bbf7d0;
    }
    .hint {
      font-size: 0.9rem;
      color: #9aa3b2;
    }
    a {
      color: #60a5fa;
    }
  </style>
</head>
<body>
  <main>
    <h1>QuickStart Partner — TORÈ</h1>
    <p>Cette page vous guide pas à pas pour créer un bar, vous connecter et tester les endpoints essentiels.</p>
    <div class="card">
      <h2>1) Créer un bar + manager</h2>
      <div class="grid">
        <div>
          <label for="barName">Nom du bar</label>
          <input id="barName" placeholder="Ex: Le Zinc" />
        </div>
        <div>
          <label for="city">Ville</label>
          <input id="city" placeholder="Ex: Lille" />
        </div>
        <div>
          <label for="managerName">Nom du manager</label>
          <input id="managerName" placeholder="Ex: Alex" />
        </div>
        <div>
          <label for="pin">PIN (4 chiffres)</label>
          <input id="pin" placeholder="1234" maxlength="4" />
        </div>
      </div>
      <div class="row" style="margin-top: 12px;">
        <button id="signupBtn">Créer le bar</button>
        <button class="secondary" id="signupFill">Remplir un exemple</button>
      </div>
      <div id="signupStatus" class="status"></div>
    </div>

    <div class="card">
      <h2>2) Login</h2>
      <div class="grid">
        <div>
          <label for="loginBarId">Bar ID</label>
          <input id="loginBarId" placeholder="Ex: 12" />
        </div>
        <div>
          <label for="loginDisplayName">Nom d'affichage</label>
          <input id="loginDisplayName" placeholder="Ex: Alex" />
        </div>
        <div>
          <label for="loginPin">PIN</label>
          <input id="loginPin" placeholder="1234" maxlength="4" />
        </div>
      </div>
      <div class="row" style="margin-top: 12px;">
        <button id="loginBtn">Se connecter</button>
      </div>
      <div id="loginStatus" class="status"></div>
    </div>

    <div class="card">
      <h2>3) Token</h2>
      <label for="tokenInput">Token Bearer</label>
      <textarea id="tokenInput" rows="3" placeholder="Votre token..."></textarea>
      <div class="row" style="margin-top: 12px;">
        <button class="copy" id="copyToken">Copier</button>
        <button class="secondary" id="saveToken">Sauvegarder</button>
        <button class="secondary" id="clearToken">Effacer</button>
      </div>
      <p class="hint">Le token est stocké en localStorage pour les prochains tests.</p>
    </div>

    <div class="card">
      <h2>4) Staff onboarding</h2>
      <div class="grid">
        <div>
          <label for="inviteRole">Rôle</label>
          <select id="inviteRole">
            <option value="entry" selected>entry</option>
            <option value="bartender">bartender</option>
          </select>
        </div>
        <div>
          <label for="inviteMaxUses">Max uses</label>
          <input id="inviteMaxUses" type="number" min="1" max="1000" value="3" />
        </div>
        <div>
          <label for="inviteExpires">Expire (jours)</label>
          <input id="inviteExpires" type="number" min="1" max="365" value="14" />
        </div>
      </div>
      <div class="row" style="margin-top: 12px;">
        <button id="createInviteBtn">Créer invite</button>
      </div>
      <div id="inviteStatus" class="status"></div>
      <h3>Staff join</h3>
      <div class="grid">
        <div>
          <label for="staffJoinCode">Code invite</label>
          <input id="staffJoinCode" placeholder="Ex: ABC123" />
        </div>
        <div>
          <label for="staffJoinName">Nom d'affichage</label>
          <input id="staffJoinName" placeholder="Ex: Léa" />
        </div>
        <div>
          <label for="staffJoinPin">PIN (4 chiffres)</label>
          <input id="staffJoinPin" placeholder="1234" maxlength="4" />
        </div>
      </div>
      <div class="row" style="margin-top: 12px;">
        <button id="staffJoinBtn" class="secondary">Staff join</button>
      </div>
      <div id="staffJoinStatus" class="status"></div>
      <label for="staffTokenInput">Token staff</label>
      <textarea id="staffTokenInput" rows="3" placeholder="Token staff..."></textarea>
      <p class="hint">Le token staff est stocké en localStorage.</p>
    </div>

    <div class="card">
      <h2>5) Simuler scans</h2>
      <div class="grid">
        <div>
          <label for="scanEventId">Event ID</label>
          <input id="scanEventId" placeholder="Ex: 42" />
        </div>
        <div>
          <label for="scanDelta">Delta</label>
          <select id="scanDelta">
            <option value="1" selected>+1</option>
            <option value="-1">-1</option>
          </select>
        </div>
        <div>
          <label for="scanDeviceId">Device ID</label>
          <input id="scanDeviceId" placeholder="quickstart-device" />
        </div>
        <div>
          <label for="scanIdempotency">Idempotency key</label>
          <input id="scanIdempotency" />
        </div>
      </div>
      <div class="row" style="margin-top: 12px;">
        <button id="scanEntryBtn">POST entry/scans</button>
        <button id="scanRefreshId" class="secondary">Regénérer clé</button>
      </div>
      <div id="scanStatus" class="status"></div>
      <div id="scanStatsStatus" class="status"></div>
    </div>

    <div class="card">
      <h2>6) Wallet tickets</h2>
      <p class="hint">Créez un user app, consultez son wallet, puis créditez via un token manager.</p>
      <div class="grid">
        <div>
          <label for="walletGuestName">Nom user app</label>
          <input id="walletGuestName" placeholder="Ex: Clara" />
        </div>
        <div>
          <label for="walletUserId">User ID</label>
          <input id="walletUserId" placeholder="ID app user" />
        </div>
        <div>
          <label for="walletUserToken">Token user app</label>
          <input id="walletUserToken" placeholder="Token Bearer user app" />
        </div>
      </div>
      <div class="row" style="margin-top: 12px;">
        <button id="walletCreateGuestBtn" class="secondary">Créer un user app</button>
        <button id="walletMeBtn">Voir wallet me</button>
      </div>
      <div id="walletStatus" class="status"></div>
      <div class="grid" style="margin-top: 16px;">
        <div>
          <label for="walletTopupAmount">Montant tickets</label>
          <input id="walletTopupAmount" type="number" min="1" value="10" />
        </div>
        <div>
          <label for="walletTopupNonce">Idempotency key</label>
          <input id="walletTopupNonce" placeholder="nonce" />
        </div>
      </div>
      <div class="row" style="margin-top: 12px;">
        <button id="walletTopupBtn">Topup user (manager)</button>
        <button class="secondary" id="walletNonceBtn">Générer nonce</button>
      </div>
      <div id="walletTopupStatus" class="status"></div>
    </div>

    <div class="card">
      <h2>7) Tester les endpoints</h2>
      <div class="row">
        <button id="getBarBtn">Get my bar</button>
        <button class="secondary" id="listEventsBtn">List events</button>
      </div>
      <div id="apiStatus" class="status"></div>
    </div>

    <div class="card">
      <h2>8) Créer un event</h2>
      <div class="grid">
        <div>
          <label for="eventName">Nom</label>
          <input id="eventName" placeholder="Ex: Soirée lancement" />
        </div>
        <div>
          <label for="eventStart">Start (optionnel)</label>
          <input id="eventStart" type="datetime-local" />
        </div>
        <div>
          <label for="eventEnd">End (optionnel)</label>
          <input id="eventEnd" type="datetime-local" />
        </div>
      </div>
      <div class="row" style="margin-top: 12px;">
        <button id="createEventBtn">Créer l’event</button>
        <button class="secondary" id="testEntryStatsBtn" disabled>Tester entry stats</button>
      </div>
      <div id="eventStatus" class="status"></div>
    </div>

    <div class="card">
      <h2>9) Modifier un event</h2>
      <div class="grid">
        <div>
          <label for="editEventId">Event ID</label>
          <input id="editEventId" placeholder="Ex: 42" />
        </div>
        <div>
          <label for="editEventName">Nom (optionnel)</label>
          <input id="editEventName" placeholder="Nouveau nom" />
        </div>
        <div>
          <label for="editEntryPrice">Prix entrée (€)</label>
          <input id="editEntryPrice" type="number" step="0.01" min="0" />
        </div>
      </div>
      <div class="row" style="margin-top: 12px;">
        <label style="display:flex; align-items:center; gap:8px;">
          <input id="editTicketsEnabled" type="checkbox" />
          Tickets ON
        </label>
        <label style="display:flex; align-items:center; gap:8px;">
          <input id="editEntryEnabled" type="checkbox" />
          Entrée ON
        </label>
        <button id="patchEventBtn">PATCH event</button>
      </div>
      <div id="editEventStatus" class="status"></div>
    </div>

    <div class="card">
      <h2>Endpoints utiles</h2>
      <pre id="endpointList"></pre>
    </div>
  </main>
  <script>
    const baseUrl = window.location.origin;
    const endpointList = document.getElementById("endpointList");
    endpointList.textContent = [
      `POST ${baseUrl}/partner/auth/manager/signup`,
      `POST ${baseUrl}/partner/auth/login`,
      `POST ${baseUrl}/partner/auth/invites`,
      `POST ${baseUrl}/partner/auth/staff/join`,
      `GET  ${baseUrl}/partner/portal/bar`,
      `GET  ${baseUrl}/partner/portal/events`,
      `POST ${baseUrl}/partner/portal/events`,
      `PATCH ${baseUrl}/partner/portal/events/{eventId}`,
      `POST ${baseUrl}/events/{eventId}/entry/scans`,
      `GET  ${baseUrl}/events/{eventId}/entry/stats`,
      `GET  ${baseUrl}/wallet/me`,
      `POST ${baseUrl}/wallet/topup`,
      `POST ${baseUrl}/wallet/topup/from_qr`,
      `GET  ${baseUrl}/health`
    ].join("\\n");

    const tokenInput = document.getElementById("tokenInput");
    const staffTokenInput = document.getElementById("staffTokenInput");
    const walletUserTokenInput = document.getElementById("walletUserToken");
    const walletUserIdInput = document.getElementById("walletUserId");
    const savedToken = localStorage.getItem("partnerToken");
    if (savedToken) {
      tokenInput.value = savedToken;
    }
    const savedStaffToken = localStorage.getItem("staffToken");
    if (savedStaffToken) {
      staffTokenInput.value = savedStaffToken;
    }
    const savedWalletToken = localStorage.getItem("walletUserToken");
    if (savedWalletToken && walletUserTokenInput) {
      walletUserTokenInput.value = savedWalletToken;
    }
    const savedWalletUserId = localStorage.getItem("walletUserId");
    if (savedWalletUserId && walletUserIdInput) {
      walletUserIdInput.value = savedWalletUserId;
    }

    function setStatus(element, message, ok = true) {
      element.textContent = message;
      element.classList.toggle("error", !ok);
      element.classList.toggle("success", ok);
    }

    function handleError(element, res, payload) {
      let message = "Erreur inconnue.";
      if (res.status === 401) message = "401 — Token manquant ou invalide.";
      else if (res.status === 403) message = "403 — Accès interdit pour ce rôle.";
      else if (res.status === 422) message = "422 — Données invalides (vérifiez les champs).";
      else if (res.status >= 500) message = "500 — Erreur serveur. Réessayez plus tard.";
      else if (payload?.detail) message = payload.detail;
      else message = `Erreur ${res.status}`;
      setStatus(element, message, false);
    }

    async function postJson(url, body, token) {
      const headers = { "Content-Type": "application/json" };
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
      const res = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(body)
      });
      const payload = await res.json().catch(() => ({}));
      return { res, payload };
    }

    async function patchJson(url, body, token) {
      const headers = { "Content-Type": "application/json" };
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
      const res = await fetch(url, {
        method: "PATCH",
        headers,
        body: JSON.stringify(body),
      });
      let payload = null;
      try {
        payload = await res.json();
      } catch (err) {
        payload = null;
      }
      return { res, payload };
    }

    async function getJson(url, token) {
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      const payload = await res.json().catch(() => ({}));
      return { res, payload };
    }

    function generateIdempotencyKey() {
      if (window.crypto && crypto.randomUUID) {
        return crypto.randomUUID();
      }
      return `qs-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    function normalizeDateTime(value) {
      if (!value) return null;
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return null;
      return parsed.toISOString();
    }

    document.getElementById("signupFill").addEventListener("click", () => {
      document.getElementById("barName").value = "Le Zinc";
      document.getElementById("city").value = "Lille";
      document.getElementById("managerName").value = "Alex";
      document.getElementById("pin").value = "1234";
    });

    document.getElementById("signupBtn").addEventListener("click", async () => {
      const body = {
        bar_name: document.getElementById("barName").value.trim(),
        city: document.getElementById("city").value.trim(),
        manager_name: document.getElementById("managerName").value.trim(),
        pin: document.getElementById("pin").value.trim()
      };
      const { res, payload } = await postJson(`${baseUrl}/partner/auth/manager/signup`, body);
      if (res.ok) {
        tokenInput.value = payload.token;
        localStorage.setItem("partnerToken", payload.token);
        setStatus(
          document.getElementById("signupStatus"),
          `✅ Bar créé !\\nbar_id: ${payload.bar_id}\\nrole: ${payload.role}\\nname: ${payload.display_name}`
        );
      } else {
        handleError(document.getElementById("signupStatus"), res, payload);
      }
    });

    document.getElementById("loginBtn").addEventListener("click", async () => {
      const body = {
        bar_id: Number(document.getElementById("loginBarId").value),
        display_name: document.getElementById("loginDisplayName").value.trim(),
        pin: document.getElementById("loginPin").value.trim()
      };
      const { res, payload } = await postJson(`${baseUrl}/partner/auth/login`, body);
      if (res.ok) {
        tokenInput.value = payload.token;
        localStorage.setItem("partnerToken", payload.token);
        setStatus(
          document.getElementById("loginStatus"),
          `✅ Connecté !\\nbar_id: ${payload.bar_id}\\nrole: ${payload.role}\\nname: ${payload.display_name}`
        );
      } else {
        handleError(document.getElementById("loginStatus"), res, payload);
      }
    });

    document.getElementById("copyToken").addEventListener("click", async () => {
      if (!tokenInput.value.trim()) {
        setStatus(document.getElementById("apiStatus"), "Aucun token à copier.", false);
        return;
      }
      try {
        await navigator.clipboard.writeText(tokenInput.value.trim());
        setStatus(document.getElementById("apiStatus"), "Token copié ✅");
      } catch (err) {
        setStatus(document.getElementById("apiStatus"), "Impossible de copier le token.", false);
      }
    });

    document.getElementById("saveToken").addEventListener("click", () => {
      localStorage.setItem("partnerToken", tokenInput.value.trim());
      setStatus(document.getElementById("apiStatus"), "Token sauvegardé ✅");
    });

    document.getElementById("clearToken").addEventListener("click", () => {
      tokenInput.value = "";
      localStorage.removeItem("partnerToken");
      setStatus(document.getElementById("apiStatus"), "Token effacé.");
    });

    document.getElementById("createInviteBtn").addEventListener("click", async () => {
      const token = tokenInput.value.trim();
      const body = {
        role: document.getElementById("inviteRole").value,
        max_uses: Number(document.getElementById("inviteMaxUses").value || 1),
        expires_days: Number(document.getElementById("inviteExpires").value || 30),
      };
      const { res, payload } = await postJson(`${baseUrl}/partner/auth/invites`, body, token);
      if (res.ok) {
        document.getElementById("staffJoinCode").value = payload.code;
        setStatus(
          document.getElementById("inviteStatus"),
          `✅ Invite créée !\\ncode: ${payload.code}\\nrole: ${payload.role}\\nmax_uses: ${payload.max_uses}`
        );
      } else {
        handleError(document.getElementById("inviteStatus"), res, payload);
      }
    });

    document.getElementById("staffJoinBtn").addEventListener("click", async () => {
      const body = {
        invite_code: document.getElementById("staffJoinCode").value.trim(),
        display_name: document.getElementById("staffJoinName").value.trim(),
        pin: document.getElementById("staffJoinPin").value.trim(),
      };
      const { res, payload } = await postJson(`${baseUrl}/partner/auth/staff/join`, body);
      if (res.ok) {
        staffTokenInput.value = payload.token;
        localStorage.setItem("staffToken", payload.token);
        setStatus(
          document.getElementById("staffJoinStatus"),
          `✅ Staff connecté !\\nrole: ${payload.role}\\nname: ${payload.display_name}`
        );
      } else {
        handleError(document.getElementById("staffJoinStatus"), res, payload);
      }
    });

    const walletNonceInput = document.getElementById("walletTopupNonce");
    if (walletNonceInput) {
      walletNonceInput.value = generateIdempotencyKey();
    }

    document.getElementById("walletNonceBtn").addEventListener("click", () => {
      walletNonceInput.value = generateIdempotencyKey();
      setStatus(document.getElementById("walletTopupStatus"), "Nonce régénéré ✅");
    });

    document.getElementById("walletCreateGuestBtn").addEventListener("click", async () => {
      const body = { display_name: document.getElementById("walletGuestName").value.trim() };
      const { res, payload } = await postJson(`${baseUrl}/auth/guest`, body);
      if (res.ok) {
        walletUserTokenInput.value = payload.token;
        walletUserIdInput.value = payload.user.id;
        localStorage.setItem("walletUserToken", payload.token);
        localStorage.setItem("walletUserId", payload.user.id);
        setStatus(
          document.getElementById("walletStatus"),
          `✅ User app créé !\\nuser_id: ${payload.user.id}`
        );
      } else {
        handleError(document.getElementById("walletStatus"), res, payload);
      }
    });

    document.getElementById("walletMeBtn").addEventListener("click", async () => {
      const token = walletUserTokenInput.value.trim();
      if (!token) {
        setStatus(document.getElementById("walletStatus"), "Token user app manquant.", false);
        return;
      }
      localStorage.setItem("walletUserToken", token);
      const { res, payload } = await getJson(`${baseUrl}/wallet/me`, token);
      if (res.ok) {
        if (payload.user_id) {
          walletUserIdInput.value = payload.user_id;
          localStorage.setItem("walletUserId", payload.user_id);
        }
        setStatus(document.getElementById("walletStatus"), JSON.stringify(payload, null, 2));
      } else {
        handleError(document.getElementById("walletStatus"), res, payload);
      }
    });

    document.getElementById("walletTopupBtn").addEventListener("click", async () => {
      const managerToken = tokenInput.value.trim();
      if (!managerToken) {
        setStatus(document.getElementById("walletTopupStatus"), "Token manager manquant.", false);
        return;
      }
      const userId = walletUserIdInput.value.trim();
      if (!userId) {
        setStatus(document.getElementById("walletTopupStatus"), "User ID manquant.", false);
        return;
      }
      const body = {
        user_id: userId,
        amount_tickets: Number(document.getElementById("walletTopupAmount").value || 0),
        idempotency_key: walletNonceInput.value.trim(),
      };
      const { res, payload } = await postJson(`${baseUrl}/wallet/topup`, body, managerToken);
      if (res.ok) {
        setStatus(document.getElementById("walletTopupStatus"), JSON.stringify(payload, null, 2));
      } else {
        handleError(document.getElementById("walletTopupStatus"), res, payload);
      }
    });

    const scanIdempotencyInput = document.getElementById("scanIdempotency");
    scanIdempotencyInput.value = generateIdempotencyKey();

    document.getElementById("scanRefreshId").addEventListener("click", () => {
      scanIdempotencyInput.value = generateIdempotencyKey();
      setStatus(document.getElementById("scanStatus"), "Clé régénérée ✅");
    });

    document.getElementById("scanEntryBtn").addEventListener("click", async () => {
      const eventId = document.getElementById("scanEventId").value.trim();
      if (!eventId) {
        setStatus(document.getElementById("scanStatus"), "Event ID manquant.", false);
        return;
      }
      const token = staffTokenInput.value.trim();
      if (!token) {
        setStatus(document.getElementById("scanStatus"), "Token staff manquant.", false);
        return;
      }
      const body = {
        delta: Number(document.getElementById("scanDelta").value),
        source: "manual",
        device_id: document.getElementById("scanDeviceId").value.trim() || "quickstart-device",
        idempotency_key: scanIdempotencyInput.value.trim(),
      };
      const { res, payload } = await postJson(`${baseUrl}/events/${eventId}/entry/scans`, body, token);
      if (res.ok) {
        setStatus(document.getElementById("scanStatus"), JSON.stringify(payload, null, 2));
        scanIdempotencyInput.value = generateIdempotencyKey();
        const stats = await getJson(`${baseUrl}/events/${eventId}/entry/stats`, token);
        if (stats.res.ok) {
          setStatus(document.getElementById("scanStatsStatus"), JSON.stringify(stats.payload, null, 2));
        } else {
          handleError(document.getElementById("scanStatsStatus"), stats.res, stats.payload);
        }
      } else {
        handleError(document.getElementById("scanStatus"), res, payload);
      }
    });

    document.getElementById("getBarBtn").addEventListener("click", async () => {
      const token = tokenInput.value.trim();
      const { res, payload } = await getJson(`${baseUrl}/partner/portal/bar`, token);
      if (res.ok) {
        setStatus(document.getElementById("apiStatus"), JSON.stringify(payload, null, 2));
      } else {
        handleError(document.getElementById("apiStatus"), res, payload);
      }
    });

    document.getElementById("listEventsBtn").addEventListener("click", async () => {
      const token = tokenInput.value.trim();
      const { res, payload } = await getJson(`${baseUrl}/partner/portal/events`, token);
      if (res.ok) {
        setStatus(document.getElementById("apiStatus"), JSON.stringify(payload, null, 2));
      } else {
        handleError(document.getElementById("apiStatus"), res, payload);
      }
    });

    let lastEventId = null;
    const testEntryStatsBtn = document.getElementById("testEntryStatsBtn");

    document.getElementById("createEventBtn").addEventListener("click", async () => {
      const token = tokenInput.value.trim();
      const body = {
        name: document.getElementById("eventName").value.trim(),
      };
      const startValue = normalizeDateTime(document.getElementById("eventStart").value);
      const endValue = normalizeDateTime(document.getElementById("eventEnd").value);
      if (startValue) body.start_at = startValue;
      if (endValue) body.end_at = endValue;

      const { res, payload } = await postJson(`${baseUrl}/partner/portal/events`, body, token);
      if (res.ok) {
        lastEventId = payload.id;
        testEntryStatsBtn.disabled = false;
        setStatus(
          document.getElementById("eventStatus"),
          `✅ Event créé !\\nEvent ID: ${payload.id}\\nNom: ${payload.name}`
        );
      } else {
        handleError(document.getElementById("eventStatus"), res, payload);
      }
    });

    testEntryStatsBtn.addEventListener("click", async () => {
      if (!lastEventId) {
        setStatus(document.getElementById("eventStatus"), "Aucun event à tester.", false);
        return;
      }
      const token = tokenInput.value.trim();
      const { res, payload } = await getJson(`${baseUrl}/events/${lastEventId}/entry/stats`, token);
      if (res.ok) {
        setStatus(document.getElementById("eventStatus"), JSON.stringify(payload, null, 2));
      } else {
        handleError(document.getElementById("eventStatus"), res, payload);
      }
    });

    const editTicketsEnabled = document.getElementById("editTicketsEnabled");
    const editEntryEnabled = document.getElementById("editEntryEnabled");

    editTicketsEnabled.addEventListener("change", () => {
      editTicketsEnabled.dataset.changed = "1";
    });
    editEntryEnabled.addEventListener("change", () => {
      editEntryEnabled.dataset.changed = "1";
    });

    document.getElementById("patchEventBtn").addEventListener("click", async () => {
      const token = tokenInput.value.trim();
      const eventId = document.getElementById("editEventId").value.trim();
      if (!eventId) {
        setStatus(document.getElementById("editEventStatus"), "Event ID manquant.", false);
        return;
      }
      const body = {};
      const name = document.getElementById("editEventName").value.trim();
      if (name) body.name = name;
      const entryPrice = document.getElementById("editEntryPrice").value.trim();
      if (entryPrice) {
        body.entry_price_cents = Math.round(Number(entryPrice) * 100);
      }
      if (editTicketsEnabled.dataset.changed) {
        body.tickets_enabled = editTicketsEnabled.checked;
      }
      if (editEntryEnabled.dataset.changed) {
        body.entry_enabled = editEntryEnabled.checked;
      }

      const { res, payload } = await patchJson(`${baseUrl}/partner/portal/events/${eventId}`, body, token);
      if (res.ok) {
        setStatus(document.getElementById("editEventStatus"), JSON.stringify(payload, null, 2));
      } else {
        handleError(document.getElementById("editEventStatus"), res, payload);
      }
    });
  </script>
</body>
</html>
    """
    return HTMLResponse(html)


def _get_partner_event(event_id: int, identity: Dict[str, Any], db: Session) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if event.bar_id != identity["bar_id"]:
        raise HTTPException(403, "Forbidden")
    return event


def _get_event_config(db: Session, event_id: int) -> Optional[EventConfig]:
    return db.query(EventConfig).filter(EventConfig.event_id == event_id).first()


def _partner_event_out(event: Event, config: Optional[EventConfig]) -> PartnerEventOut:
    return PartnerEventOut(
        id=event.id,
        bar_id=event.bar_id,
        name=event.name,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        entry_price_cents=event.entry_price_cents,
        tickets_enabled=event.ticket_mode,
        entry_enabled=config.entry_enabled if config else False,
    )


def _require_partner_role(identity: Dict[str, Any], role: str) -> None:
    if identity.get("role") != role:
        raise HTTPException(status_code=403, detail="Forbidden")


def _require_partner_roles(identity: Dict[str, Any], roles: set[str]) -> None:
    if identity.get("role") not in roles:
        raise HTTPException(status_code=403, detail="Forbidden")


def _require_wallet_staff(identity: Dict[str, Any]) -> None:
    _require_partner_roles(identity, {"manager", "cashier", "wallet"})


def _menu_variant_out(variant: MenuItemVariant) -> MenuVariantOut:
    return MenuVariantOut(
        id=variant.id,
        name=variant.name,
        price_delta_cents=variant.price_delta_cents,
        is_active=variant.is_active,
    )


def _menu_item_out(item: MenuItem, include_inactive_variants: bool = True) -> MenuItemOut:
    variants = item.variants or []
    if not include_inactive_variants:
        variants = [variant for variant in variants if variant.is_active]
    return MenuItemOut(
        id=item.id,
        bar_id=item.bar_id,
        category_id=item.category_id,
        name=item.name,
        description=item.description,
        price_cents=item.price_cents,
        image_url=item.image_url,
        tags=item.tags,
        is_active=item.is_active,
        is_available=item.is_available,
        alcohol=item.alcohol,
        vegan=item.vegan,
        allergens=item.allergens,
        created_at=item.created_at,
        updated_at=item.updated_at,
        variants=[_menu_variant_out(variant) for variant in variants],
    )


def _menu_category_out(category: MenuCategory, public_only: bool = False) -> MenuCategoryOut:
    items = category.items or []
    if public_only:
        items = [it for it in items if it.is_active and it.is_available]
    items = sorted(items, key=lambda it: (it.name.lower(), it.id))
    return MenuCategoryOut(
        id=category.id,
        bar_id=category.bar_id,
        name=category.name,
        sort_order=category.sort_order,
        is_active=category.is_active,
        created_at=category.created_at,
        items=[_menu_item_out(item, include_inactive_variants=not public_only) for item in items],
    )


def _get_partner_category(category_id: int, identity: Dict[str, Any], db: Session) -> MenuCategory:
    category = db.get(MenuCategory, category_id)
    if not category:
        raise HTTPException(404, "Category not found")
    if category.bar_id != identity["bar_id"]:
        raise HTTPException(403, "Forbidden")
    return category


def _get_partner_item(item_id: int, identity: Dict[str, Any], db: Session) -> MenuItem:
    item = db.get(MenuItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    if item.bar_id != identity["bar_id"]:
        raise HTTPException(403, "Forbidden")
    return item


@app.get("/menu/public/{bar_id}", response_model=MenuPublicOut)
def menu_public(bar_id: int, db: Session = Depends(get_db)):
    bar = db.get(Bar, bar_id)
    if not bar:
        raise HTTPException(404, "Bar not found")

    categories = (
        db.query(MenuCategory)
        .filter(MenuCategory.bar_id == bar_id, MenuCategory.is_active.is_(True))
        .order_by(MenuCategory.sort_order.asc(), MenuCategory.id.asc())
        .all()
    )
    response = MenuPublicOut(
        bar={"id": bar.id, "name": bar.name, "city": bar.city},
        categories=[_menu_category_out(category, public_only=True) for category in categories],
    )
    return JSONResponse(content=response.model_dump(mode="json"), headers={"Cache-Control": "public, max-age=30"})


@app.get("/menu/public/{bar_id}/items/{item_id}", response_model=MenuItemOut)
def menu_public_item(bar_id: int, item_id: int, db: Session = Depends(get_db)):
    item = db.get(MenuItem, item_id)
    if not item or item.bar_id != bar_id:
        raise HTTPException(404, "Item not found")
    if not item.is_active or not item.is_available:
        raise HTTPException(404, "Item not available")
    return _menu_item_out(item, include_inactive_variants=False)


@app.post("/menu/track")
def menu_track(payload: MenuTrackIn, db: Session = Depends(get_db)):
    if payload.action not in {"view", "click", "add"}:
        raise HTTPException(422, "Invalid action")
    bar = db.get(Bar, payload.bar_id)
    if not bar:
        raise HTTPException(404, "Bar not found")
    if payload.item_id is not None:
        item = db.get(MenuItem, payload.item_id)
        if not item or item.bar_id != payload.bar_id:
            raise HTTPException(404, "Item not found")

    row = MenuTrackEvent(
        bar_id=payload.bar_id,
        event_id=payload.event_id,
        item_id=payload.item_id,
        action=payload.action,
        device_id=payload.device_id,
        changes_json="{}",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id}


@app.get("/partner/portal/menu", response_model=List[MenuCategoryOut])
def partner_portal_menu(identity=Depends(current_partner_identity), db: Session = Depends(get_db)):
    categories = (
        db.query(MenuCategory)
        .filter(MenuCategory.bar_id == identity["bar_id"])
        .order_by(MenuCategory.sort_order.asc(), MenuCategory.id.asc())
        .all()
    )
    return [_menu_category_out(category, public_only=False) for category in categories]


@app.post("/partner/portal/menu/categories", response_model=MenuCategoryOut)
def partner_portal_menu_category_create(
    payload: MenuCategoryCreateIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    category = MenuCategory(
        bar_id=identity["bar_id"],
        name=payload.name,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _menu_category_out(category)


@app.patch("/partner/portal/menu/categories/{id}", response_model=MenuCategoryOut)
def partner_portal_menu_category_patch(
    id: int,
    payload: MenuCategoryUpdateIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    category = _get_partner_category(id, identity, db)
    if payload.name is not None:
        category.name = payload.name
    if payload.sort_order is not None:
        category.sort_order = payload.sort_order
    if payload.is_active is not None:
        category.is_active = payload.is_active
    db.add(category)
    db.commit()
    db.refresh(category)
    return _menu_category_out(category)


@app.delete("/partner/portal/menu/categories/{id}")
def partner_portal_menu_category_delete(
    id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    category = _get_partner_category(id, identity, db)
    db.delete(category)
    db.commit()
    return {"ok": True}


@app.post("/partner/portal/menu/items", response_model=MenuItemOut)
def partner_portal_menu_item_create(
    payload: MenuItemCreateIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    category = _get_partner_category(payload.category_id, identity, db)
    item = MenuItem(
        bar_id=identity["bar_id"],
        category_id=category.id,
        name=payload.name,
        description=payload.description,
        price_cents=payload.price_cents,
        image_url=payload.image_url,
        tags=payload.tags,
        is_active=payload.is_active,
        is_available=payload.is_available,
        alcohol=payload.alcohol,
        vegan=payload.vegan,
        allergens=payload.allergens,
        updated_at=now_utc(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _menu_item_out(item)


@app.patch("/partner/portal/menu/items/{id}", response_model=MenuItemOut)
def partner_portal_menu_item_patch(
    id: int,
    payload: MenuItemUpdateIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    item = _get_partner_item(id, identity, db)
    if payload.category_id is not None:
        category = _get_partner_category(payload.category_id, identity, db)
        item.category_id = category.id
    if payload.name is not None:
        item.name = payload.name
    if payload.description is not None:
        item.description = payload.description
    if payload.price_cents is not None:
        item.price_cents = payload.price_cents
    if payload.image_url is not None:
        item.image_url = payload.image_url
    if payload.tags is not None:
        item.tags = payload.tags
    if payload.is_active is not None:
        item.is_active = payload.is_active
    if payload.is_available is not None:
        item.is_available = payload.is_available
    if payload.alcohol is not None:
        item.alcohol = payload.alcohol
    if payload.vegan is not None:
        item.vegan = payload.vegan
    if payload.allergens is not None:
        item.allergens = payload.allergens
    item.updated_at = now_utc()
    db.add(item)
    db.commit()
    db.refresh(item)
    return _menu_item_out(item)


@app.delete("/partner/portal/menu/items/{id}")
def partner_portal_menu_item_delete(
    id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    item = _get_partner_item(id, identity, db)
    db.delete(item)
    db.commit()
    return {"ok": True}


@app.get("/partner/portal/menu/analytics", response_model=MenuAnalyticsOut)
def partner_portal_menu_analytics(identity=Depends(current_partner_identity), db: Session = Depends(get_db)):
    since = now_utc() - timedelta(days=7)
    rows = (
        db.query(
            MenuTrackEvent.item_id,
            MenuItem.name,
            func.sum(case((MenuTrackEvent.action == "view", 1), else_=0)).label("views"),
            func.sum(case((MenuTrackEvent.action == "click", 1), else_=0)).label("clicks"),
            func.sum(case((MenuTrackEvent.action == "add", 1), else_=0)).label("adds"),
        )
        .join(MenuItem, MenuItem.id == MenuTrackEvent.item_id)
        .filter(
            MenuTrackEvent.bar_id == identity["bar_id"],
            MenuTrackEvent.created_at >= since,
            MenuTrackEvent.item_id.is_not(None),
        )
        .group_by(MenuTrackEvent.item_id, MenuItem.name)
        .order_by(desc("views"), desc("clicks"), desc("adds"))
        .limit(20)
        .all()
    )
    top_items = [
        MenuAnalyticsItemOut(
            item_id=item_id,
            item_name=item_name,
            views=int(views or 0),
            clicks=int(clicks or 0),
            adds=int(adds or 0),
        )
        for item_id, item_name, views, clicks, adds in rows
    ]
    return MenuAnalyticsOut(period_days=7, top_items=top_items)


@app.get("/partner/portal/events/{event_id}", response_model=PartnerEventOut)
def partner_portal_event_detail(
    event_id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    event = _get_partner_event(event_id, identity, db)
    config = _get_event_config(db, event.id)
    return _partner_event_out(event, config)


@app.patch("/partner/portal/events/{event_id}", response_model=PartnerEventOut)
def partner_portal_event_update(
    event_id: int,
    payload: PartnerEventUpdateIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    event = _get_partner_event(event_id, identity, db)

    if payload.name is not None:
        event.name = payload.name
    if payload.start_at is not None:
        event.starts_at = payload.start_at
    if payload.end_at is not None:
        event.ends_at = payload.end_at
    if payload.entry_price_cents is not None:
        event.entry_price_cents = payload.entry_price_cents
    if payload.tickets_enabled is not None:
        event.ticket_mode = payload.tickets_enabled

    config = None
    if payload.entry_enabled is not None:
        config = _get_event_config(db, event.id)
        if not config:
            config = EventConfig(event_id=event.id, entry_enabled=payload.entry_enabled)
        else:
            config.entry_enabled = payload.entry_enabled
        config.updated_at = now_utc()
        db.add(config)

    db.add(event)
    db.commit()
    db.refresh(event)
    if config is None:
        config = _get_event_config(db, event.id)
    return _partner_event_out(event, config)


@app.get("/partner/portal/events/{event_id}/drinks", response_model=List[PartnerEventDrinkOut])
def partner_portal_event_drinks(
    event_id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _get_partner_event(event_id, identity, db)
    rows = (
        db.query(EventDrink, Drink)
        .join(Drink, Drink.id == EventDrink.drink_id)
        .filter(EventDrink.event_id == event_id)
        .order_by(Drink.type.asc(), Drink.name.asc())
        .all()
    )
    return [
        PartnerEventDrinkOut(
            drink_id=drink.id,
            name=drink.name,
            type=drink.type,
            base_price_cents=event_drink.base_price_cents,
            current_price_cents=event_drink.current_price_cents,
            override_price_cents=event_drink.override_price_cents,
        )
        for event_drink, drink in rows
    ]


@app.post("/partner/portal/events/{event_id}/drinks", response_model=PartnerEventDrinkOut)
def partner_portal_event_drink_add(
    event_id: int,
    payload: PartnerEventDrinkIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    _get_partner_event(event_id, identity, db)

    drink = (
        db.query(Drink)
        .filter(Drink.name == payload.name, Drink.type == payload.type)
        .first()
    )
    if not drink:
        drink = Drink(name=payload.name, type=payload.type)
        db.add(drink)
        db.flush()

    event_drink = db.get(EventDrink, {"event_id": event_id, "drink_id": drink.id})
    if not event_drink:
        event_drink = EventDrink(
            event_id=event_id,
            drink_id=drink.id,
            base_price_cents=payload.base_price_cents,
            current_price_cents=payload.base_price_cents,
            override_price_cents=payload.override_price_cents,
            last_price_update=now_utc(),
        )
        db.add(event_drink)
    else:
        event_drink.base_price_cents = payload.base_price_cents
        event_drink.current_price_cents = payload.base_price_cents
        event_drink.override_price_cents = payload.override_price_cents
        event_drink.last_price_update = now_utc()
        db.add(event_drink)

    db.add(
        PriceHistory(
            event_id=event_id,
            drink_id=drink.id,
            price_cents=event_drink.current_price_cents,
            ts=now_utc(),
        )
    )
    db.commit()
    return PartnerEventDrinkOut(
        drink_id=drink.id,
        name=drink.name,
        type=drink.type,
        base_price_cents=event_drink.base_price_cents,
        current_price_cents=event_drink.current_price_cents,
        override_price_cents=event_drink.override_price_cents,
    )


@app.delete("/partner/portal/events/{event_id}/drinks/{drink_id}")
def partner_portal_event_drink_remove(
    event_id: int,
    drink_id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    _get_partner_event(event_id, identity, db)

    event_drink = db.get(EventDrink, {"event_id": event_id, "drink_id": drink_id})
    if not event_drink:
        raise HTTPException(404, "Drink not in this event")

    db.query(PriceHistory).filter(
        PriceHistory.event_id == event_id, PriceHistory.drink_id == drink_id
    ).delete(synchronize_session=False)
    db.delete(event_drink)
    db.commit()
    return {"ok": True}


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
    _ensure_orders_payment_columns()
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


@app.post("/qr/resolve", response_model=QrResolveOut)
def qr_resolve(
    payload: QrResolveIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = resolve_qr_payload(payload.raw)
    if not base.get("valid"):
        return {
            "valid": False,
            "type": "unknown",
            "event_id": None,
            "bar_id": None,
            "item_id": None,
            "category_id": None,
            "route_front": None,
            "token": None,
            "reason": base.get("reason"),
            "required_role": None,
            "granted_role": "guest",
        }

    event_id = base.get("event_id")
    qr_type = base.get("type")
    token = base.get("token")
    if qr_type == "wallet_topup":
        return {
            "valid": True,
            "type": qr_type,
            "event_id": None,
            "bar_id": None,
            "item_id": None,
            "category_id": None,
            "route_front": None,
            "token": None,
            "user_id": base.get("user_id"),
            "amount_tickets": base.get("amount_tickets"),
            "idempotency_key": base.get("idempotency_key"),
            "reason": None,
            "required_role": None,
            "granted_role": "guest",
        }
    if qr_type == "menu":
        return {
            "valid": True,
            "type": "menu",
            "event_id": None,
            "bar_id": base.get("bar_id"),
            "item_id": base.get("item_id"),
            "category_id": base.get("category_id"),
            "route_front": base.get("route_front"),
            "token": None,
            "reason": None,
            "required_role": None,
            "granted_role": "guest",
        }

    role_map = {
        "join": "guest",
        "menu": "guest",
        "entry": "entry",
        "admin_config": "admin",
        "staff_entry": "entry",
        "staff_invite": "guest",
    }
    required_role = role_map.get(qr_type, "guest")
    granted_role = resolve_event_role(db, user.id, event_id)

    if _role_rank(granted_role) < _role_rank(required_role):
        return {
            "valid": False,
            "type": "unknown",
            "event_id": None,
            "bar_id": None,
            "item_id": None,
            "category_id": None,
            "route_front": None,
            "token": None,
            "reason": "forbidden",
            "required_role": required_role,
            "granted_role": granted_role,
        }

    return {
        "valid": True,
        "type": qr_type,
        "event_id": event_id,
        "bar_id": None,
        "item_id": None,
        "category_id": None,
        "route_front": None,
        "token": token,
        "reason": None,
        "required_role": required_role,
        "granted_role": granted_role,
    }


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
# Polymarket V1
# ---------------------------------------------------------------------

@app.get("/polymarket/bets", response_model=List[BetOut])
def list_polymarket_bets(
    scope: Optional[str] = Query(default=None),
    event_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    q = select(Bet)
    if scope:
        q = q.where(Bet.scope == _ensure_bet_scope(scope))
    if event_id is not None:
        q = q.where(Bet.event_id == event_id)
    if status:
        status_norm = _normalize_upper(status)
        if status_norm not in {"LIVE", "RESOLVED", "CANCELLED"}:
            raise HTTPException(status_code=422, detail="Invalid status")
        q = q.where(Bet.status == status_norm)
    if kind:
        q = q.where(Bet.kind == _ensure_bet_kind(kind))

    rows = db.scalars(q.order_by(Bet.created_at.desc()).limit(limit).offset(offset)).all()
    return [_bet_out(row) for row in rows]


@app.post("/polymarket/bets", response_model=BetOut)
def create_polymarket_bet(
    payload: BetCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope = _ensure_bet_scope(payload.scope)
    kind = _ensure_bet_kind(payload.kind)
    if scope == "GLOBAL":
        if not _polymarket_global_enabled() or not _is_polymarket_admin(user.id):
            raise HTTPException(status_code=403, detail="Forbidden")
    if scope == "EVENT":
        if payload.event_id is None:
            raise HTTPException(status_code=422, detail="event_id required")
        event = db.get(Event, payload.event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        cfg = get_or_create_event_config(db, payload.event_id, commit=True)
        if not cfg.allow_user_bets:
            require_role_for_event(db, user.id, payload.event_id, "admin")

    resolver_user_id = payload.resolver_user_id
    if kind == "SUBJECTIVE" and not resolver_user_id:
        raise HTTPException(status_code=422, detail="resolver_user_id required")

    bet = Bet(
        scope=scope,
        event_id=payload.event_id if scope == "EVENT" else None,
        question=payload.question.strip(),
        kind=kind,
        status="LIVE",
        deadline_at=payload.deadline_at,
        resolver_user_id=resolver_user_id,
        rules_text=payload.rules_text,
        dispute_window_minutes=payload.dispute_window_minutes,
        created_by_user_id=user.id,
        created_at=now_utc(),
        resolved_outcome=None,
        pool_yes_tickets=0,
        pool_no_tickets=0,
    )
    db.add(bet)
    db.commit()
    db.refresh(bet)
    return _bet_out(bet)


@app.get("/polymarket/bets/{bet_id}", response_model=BetDetailOut)
def get_polymarket_bet(
    bet_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    bet = db.get(Bet, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    data = _bet_out(bet)
    positions_count = db.scalar(
        select(func.count()).select_from(BetPosition).where(BetPosition.bet_id == bet_id)
    )

    user = _optional_current_user(authorization, db)
    user_position = None
    if user:
        rows = db.scalars(
            select(BetPosition).where(
                BetPosition.bet_id == bet_id, BetPosition.user_id == user.id
            )
        ).all()
        yes_total = sum(r.stake_tickets for r in rows if r.side == "YES")
        no_total = sum(r.stake_tickets for r in rows if r.side == "NO")
        total_pool = _bet_total_pool(bet)
        payout_yes = (
            (yes_total * total_pool / bet.pool_yes_tickets)
            if bet.pool_yes_tickets > 0 and yes_total > 0
            else 0
        )
        payout_no = (
            (no_total * total_pool / bet.pool_no_tickets)
            if bet.pool_no_tickets > 0 and no_total > 0
            else 0
        )
        user_position = {
            "stake_yes": yes_total,
            "stake_no": no_total,
            "stake_total": yes_total + no_total,
            "payout_yes": payout_yes,
            "payout_no": payout_no,
        }

    return {
        **data,
        "positions_count": positions_count or 0,
        "user_position": user_position,
    }


@app.get("/polymarket/bets/{bet_id}/me", response_model=BetMeOut)
def get_polymarket_bet_me(
    bet_id: int,
    include_wallet_balance: bool = Query(default=True),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bet = db.get(Bet, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")

    rows = db.scalars(
        select(BetPosition).where(BetPosition.bet_id == bet_id, BetPosition.user_id == user.id)
    ).all()
    yes_total = sum(r.stake_tickets for r in rows if r.side == "YES")
    no_total = sum(r.stake_tickets for r in rows if r.side == "NO")
    total_pool = _bet_total_pool(bet)

    payout_yes = (
        (yes_total * total_pool / bet.pool_yes_tickets)
        if bet.pool_yes_tickets > 0 and yes_total > 0
        else 0
    )
    payout_no = (
        (no_total * total_pool / bet.pool_no_tickets)
        if bet.pool_no_tickets > 0 and no_total > 0
        else 0
    )

    wallet_balance = None
    if include_wallet_balance:
        wallet_balance = get_or_create_wallet(db, user.id).balance_tickets
        db.commit()

    return BetMeOut(
        bet_id=bet_id,
        user_id=user.id,
        stake_yes=yes_total,
        stake_no=no_total,
        stake_total=yes_total + no_total,
        payout_yes=payout_yes,
        payout_no=payout_no,
        wallet_balance_tickets=wallet_balance,
    )


@app.post("/polymarket/bets/{bet_id}/positions", response_model=BetPositionResponseOut)
def create_polymarket_position(
    bet_id: int,
    payload: BetPositionCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    side = _ensure_bet_side(payload.side)
    stake = payload.stake_tickets
    idempotency_key = payload.idempotency_key.strip()

    try:
        bet = db.execute(
            select(Bet).where(Bet.id == bet_id).with_for_update()
        ).scalar_one_or_none()
        if not bet:
            raise HTTPException(status_code=404, detail="Bet not found")
        if bet.status != "LIVE":
            raise HTTPException(status_code=409, detail="Bet not live")
        if bet.deadline_at and now_utc() > bet.deadline_at:
            raise HTTPException(status_code=409, detail="Bet closed")

        wallet = get_or_create_wallet(db, user.id)
        if wallet.balance_tickets < stake:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient wallet balance: required {stake}, available {wallet.balance_tickets}",
            )

        position = BetPosition(
            bet_id=bet_id,
            user_id=user.id,
            side=side,
            stake_tickets=stake,
            idempotency_key=idempotency_key,
            created_at=now_utc(),
        )
        db.add(position)
        db.flush()
        _apply_wallet_tx(
            db,
            user_id=user.id,
            amount_tickets=-stake,
            kind="BET_STAKE",
            ref_type="BET",
            ref_id=str(bet_id),
            idempotency_key=idempotency_key,
        )
        if side == "YES":
            bet.pool_yes_tickets += stake
        else:
            bet.pool_no_tickets += stake
        db.add(bet)
        db.commit()
        db.refresh(position)
        return {
            "bet": _bet_out(bet),
            "position": {
                "id": position.id,
                "bet_id": position.bet_id,
                "user_id": position.user_id,
                "side": position.side,
                "stake_tickets": position.stake_tickets,
                "created_at": position.created_at.isoformat() if position.created_at else None,
            },
        }
    except IntegrityError:
        db.rollback()
        existing = db.query(BetPosition).filter(
            BetPosition.bet_id == bet_id,
            BetPosition.user_id == user.id,
            BetPosition.idempotency_key == idempotency_key,
        ).first()
        if not existing:
            raise
        bet = db.get(Bet, bet_id)
        if not bet:
            raise HTTPException(status_code=404, detail="Bet not found")
        return {
            "bet": _bet_out(bet),
            "position": {
                "id": existing.id,
                "bet_id": existing.bet_id,
                "user_id": existing.user_id,
                "side": existing.side,
                "stake_tickets": existing.stake_tickets,
                "created_at": existing.created_at.isoformat() if existing.created_at else None,
            },
        }


@app.post("/polymarket/bets/{bet_id}/resolve", response_model=BetOut)
def resolve_polymarket_bet(
    bet_id: int,
    payload: BetResolveIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bet = db.execute(select(Bet).where(Bet.id == bet_id).with_for_update()).scalar_one_or_none()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    if bet.status == "RESOLVED":
        return _bet_out(bet)
    if bet.status != "LIVE":
        raise HTTPException(status_code=409, detail="Bet not live")

    outcome = _ensure_bet_side(payload.outcome)
    is_admin = _is_polymarket_admin(user.id)
    if bet.scope == "EVENT" and bet.event_id is not None:
        role = resolve_event_role(db, user.id, bet.event_id)
        if _role_rank(role) >= _role_rank("admin"):
            is_admin = True

    if bet.kind == "SUBJECTIVE":
        if user.id != bet.resolver_user_id and not is_admin:
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Forbidden")

    bet.status = "RESOLVED"
    bet.resolved_outcome = outcome
    bet.resolved_at = now_utc()
    db.add(bet)

    positions = db.scalars(select(BetPosition).where(BetPosition.bet_id == bet_id)).all()
    total_pool = _bet_total_pool(bet)
    winning_pool = bet.pool_yes_tickets if outcome == "YES" else bet.pool_no_tickets
    if winning_pool > 0 and total_pool > 0:
        payouts_by_user: Dict[str, int] = {}
        for pos in positions:
            if pos.side != outcome:
                continue
            payout = int(round(pos.stake_tickets * total_pool / winning_pool))
            payouts_by_user[pos.user_id] = payouts_by_user.get(pos.user_id, 0) + payout

        for winner_user_id, payout in payouts_by_user.items():
            if payout <= 0:
                continue
            _apply_wallet_tx(
                db,
                user_id=winner_user_id,
                amount_tickets=payout,
                kind="BET_PAYOUT",
                ref_type="BET",
                ref_id=str(bet_id),
                idempotency_key=_wallet_tx_key("BET_PAYOUT", bet_id, winner_user_id),
            )

    db.add(
        BetResolutionLog(
            bet_id=bet.id,
            actor_user_id=user.id,
            action="resolve",
            outcome=outcome,
            notes="manual",
        )
    )
    db.commit()
    return _bet_out(bet)


@app.post("/polymarket/bets/{bet_id}/cancel", response_model=BetOut)
def cancel_polymarket_bet(
    bet_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bet = db.execute(select(Bet).where(Bet.id == bet_id).with_for_update()).scalar_one_or_none()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    if bet.status == "CANCELLED":
        return _bet_out(bet)
    if bet.status != "LIVE":
        raise HTTPException(status_code=409, detail="Bet not live")

    is_admin = _is_polymarket_admin(user.id)
    if bet.scope == "EVENT" and bet.event_id is not None:
        role = resolve_event_role(db, user.id, bet.event_id)
        if _role_rank(role) >= _role_rank("admin"):
            is_admin = True
    if not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    bet.status = "CANCELLED"
    bet.resolved_at = now_utc()
    bet.resolved_outcome = None
    db.add(bet)

    positions = db.scalars(select(BetPosition).where(BetPosition.bet_id == bet_id)).all()
    refunds_by_user: Dict[str, int] = {}
    for pos in positions:
        refunds_by_user[pos.user_id] = refunds_by_user.get(pos.user_id, 0) + pos.stake_tickets

    for user_id, refund in refunds_by_user.items():
        if refund <= 0:
            continue
        _apply_wallet_tx(
            db,
            user_id=user_id,
            amount_tickets=refund,
            kind="REFUND",
            ref_type="BET",
            ref_id=str(bet_id),
            idempotency_key=_wallet_tx_key("BET_REFUND", bet_id, user_id),
        )

    db.add(
        BetResolutionLog(
            bet_id=bet.id,
            actor_user_id=user.id,
            action="cancel",
            outcome=None,
            notes=None,
        )
    )
    db.commit()
    return _bet_out(bet)


@app.get("/polymarket/bets/{bet_id}/timeline", response_model=List[BetTimelinePointOut])
def polymarket_bet_timeline(
    bet_id: int,
    db: Session = Depends(get_db),
):
    bet = db.get(Bet, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")

    positions = db.scalars(
        select(BetPosition)
        .where(BetPosition.bet_id == bet_id)
        .order_by(BetPosition.created_at.asc())
    ).all()

    points: List[Dict[str, Any]] = []
    yes_pool = 0
    no_pool = 0
    for pos in positions:
        if pos.side == "YES":
            yes_pool += pos.stake_tickets
        else:
            no_pool += pos.stake_tickets
        total = yes_pool + no_pool
        pct_yes = yes_pool / total if total > 0 else 0.5
        points.append(
            {
                "timestamp": pos.created_at.isoformat() if pos.created_at else now_utc().isoformat(),
                "pct_yes": pct_yes,
                "total_pool_tickets": total,
            }
        )

    if len(points) > POLYMARKET_TIMELINE_MAX_POINTS:
        step = max(1, len(points) // POLYMARKET_TIMELINE_MAX_POINTS)
        trimmed = points[::step]
        if trimmed[-1] != points[-1]:
            trimmed.append(points[-1])
        points = trimmed

    return points


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


@app.get("/events", response_model=List[EventSummaryOut])
def list_all_events(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = db.query(Event).order_by(Event.starts_at.desc()).limit(limit).all()
    return [
        EventSummaryOut(
            id=row.id,
            bar_id=row.bar_id,
            name=row.name,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            entry_price_cents=row.entry_price_cents,
            ticket_mode=row.ticket_mode,
            ticket_value_cents=row.ticket_value_cents,
        )
        for row in rows
    ]


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


@app.post("/events", response_model=CreateEventOut)
def create_event(
    payload: CreateEventIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.bar_id is not None:
        bar = db.get(Bar, payload.bar_id)
        if not bar:
            raise HTTPException(404, "Bar not found")

    event = Event(
        bar_id=payload.bar_id,
        name=payload.name,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
    )
    db.add(event)
    db.flush()

    get_or_create_event_config(db, event.id)
    db.add(
        EventStaff(
            event_id=event.id,
            user_id=user.id,
            role="admin",
            is_active=True,
            created_at=now_utc(),
            created_by_user_id=user.id,
        )
    )
    db.commit()

    return {
        "event_id": event.id,
        "name": event.name,
        "starts_at": event.starts_at.isoformat(),
        "ends_at": event.ends_at.isoformat(),
        "bar_id": event.bar_id,
    }


@app.get("/events/{event_id}/qr-pack", response_model=QrPackOut)
def get_event_qr_pack(
    event_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    require_role_for_event(db, user.id, event_id, "admin")

    return {
        "event_id": event_id,
        "qrs": {
            "join": f"tore://join?event_id={event_id}",
            "menu": f"tore://menu?event_id={event_id}",
            "entry": f"tore://entry?event_id={event_id}",
            "admin_config": f"tore://admin_config?event_id={event_id}",
            "staff_entry": f"tore://staff_entry?event_id={event_id}",
        },
    }


@app.get("/events/{event_id}/config", response_model=EventConfigOut)
def get_event_config(
    event_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    e = db.get(Event, event_id)
    if not e:
        raise HTTPException(404, "Event not found")
    cfg = get_or_create_event_config(db, event_id, commit=True)
    role = resolve_event_role(db, user.id, event_id)
    db.commit()
    return {
        "event_id": event_id,
        "menu_enabled": cfg.menu_enabled,
        "wallet_enabled": cfg.wallet_enabled,
        "entry_enabled": cfg.entry_enabled,
        "checkin_enabled": cfg.checkin_enabled,
        "battles_enabled": cfg.battles_enabled,
        "hunt_enabled": cfg.hunt_enabled,
        "report_enabled": cfg.report_enabled,
        "allow_user_bets": cfg.allow_user_bets,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
        "updated_by_user_id": cfg.updated_by_user_id,
        "role": role,
    }


@app.patch("/events/{event_id}/config", response_model=EventConfigOut)
def patch_event_config(
    event_id: int,
    payload: EventConfigPatchIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    e = db.get(Event, event_id)
    if not e:
        raise HTTPException(404, "Event not found")

    require_role_for_event(db, user.id, event_id, "admin")

    cfg = get_or_create_event_config(db, event_id)
    changes: Dict[str, Any] = {}
    for field in [
        "menu_enabled",
        "wallet_enabled",
        "entry_enabled",
        "checkin_enabled",
        "battles_enabled",
        "hunt_enabled",
        "report_enabled",
        "allow_user_bets",
    ]:
        value = getattr(payload, field)
        if value is None:
            continue
        current = getattr(cfg, field)
        if current != value:
            setattr(cfg, field, value)
            changes[field] = {"from": current, "to": value}

    if changes:
        cfg.updated_at = now_utc()
        cfg.updated_by_user_id = user.id
        log = EventConfigLog(
            event_id=event_id,
            changed_by_user_id=user.id,
            changes_json=json.dumps(changes, ensure_ascii=False),
        )
        db.add(log)

    db.add(cfg)
    db.commit()

    role = resolve_event_role(db, user.id, event_id)
    return {
        "event_id": event_id,
        "menu_enabled": cfg.menu_enabled,
        "wallet_enabled": cfg.wallet_enabled,
        "entry_enabled": cfg.entry_enabled,
        "checkin_enabled": cfg.checkin_enabled,
        "battles_enabled": cfg.battles_enabled,
        "hunt_enabled": cfg.hunt_enabled,
        "report_enabled": cfg.report_enabled,
        "allow_user_bets": cfg.allow_user_bets,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
        "updated_by_user_id": cfg.updated_by_user_id,
        "role": role,
    }


ALLOWED_COST_CATEGORIES = {"stock", "location", "staff", "other"}


@app.get("/events/{event_id}/costs", response_model=List[EventCostOut])
def list_event_costs(
    event_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    require_role_for_event(db, user.id, event_id, "admin")
    require_feature(db, event_id, "report_enabled")

    rows = (
        db.query(EventCost)
        .filter(EventCost.event_id == event_id)
        .order_by(EventCost.created_at.desc())
        .all()
    )
    return [
        {
            "id": cost.id,
            "event_id": cost.event_id,
            "label": cost.label,
            "amount_cents": cost.amount_cents,
            "category": cost.category,
            "created_at": cost.created_at.isoformat() if cost.created_at else None,
            "created_by_user_id": cost.created_by_user_id,
        }
        for cost in rows
    ]


@app.post("/events/{event_id}/costs", response_model=EventCostOut)
def create_event_cost(
    event_id: int,
    payload: EventCostIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    require_role_for_event(db, user.id, event_id, "admin")
    require_feature(db, event_id, "report_enabled")

    category = (payload.category or "").strip().lower()
    if category not in ALLOWED_COST_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_category", "allowed": sorted(ALLOWED_COST_CATEGORIES)},
        )

    cost = EventCost(
        event_id=event_id,
        label=payload.label.strip(),
        amount_cents=payload.amount_cents,
        category=category,
        created_at=now_utc(),
        created_by_user_id=user.id,
    )
    db.add(cost)
    db.commit()
    db.refresh(cost)
    return {
        "id": cost.id,
        "event_id": cost.event_id,
        "label": cost.label,
        "amount_cents": cost.amount_cents,
        "category": cost.category,
        "created_at": cost.created_at.isoformat() if cost.created_at else None,
        "created_by_user_id": cost.created_by_user_id,
    }


@app.delete("/events/{event_id}/costs/{cost_id}")
def delete_event_cost(
    event_id: int,
    cost_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    require_role_for_event(db, user.id, event_id, "admin")
    require_feature(db, event_id, "report_enabled")

    cost = db.get(EventCost, cost_id)
    if not cost or cost.event_id != event_id:
        raise HTTPException(404, "Cost not found")
    db.delete(cost)
    db.commit()
    return {"ok": True}


@app.get("/events/{event_id}/report")
def get_event_report(
    event_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    require_role_for_event(db, user.id, event_id, "admin")
    require_feature(db, event_id, "report_enabled")

    total_orders = (
        db.scalar(select(func.count()).select_from(Order).where(Order.event_id == event_id)) or 0
    )
    gross_revenue_cents = (
        db.scalar(
            select(func.coalesce(func.sum(Order.total_cents), 0)).where(Order.event_id == event_id)
        )
        or 0
    )

    item_rows = db.execute(
        select(
            OrderItem.drink_id,
            Drink.name,
            Drink.type,
            func.coalesce(func.sum(OrderItem.qty), 0).label("qty"),
            func.coalesce(func.sum(OrderItem.qty * OrderItem.unit_price_cents), 0).label(
                "revenue_cents"
            ),
        )
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Drink, Drink.id == OrderItem.drink_id, isouter=True)
        .where(Order.event_id == event_id)
        .group_by(OrderItem.drink_id, Drink.name, Drink.type)
        .order_by(func.sum(OrderItem.qty * OrderItem.unit_price_cents).desc())
    ).all()

    by_item = []
    for row in item_rows:
        by_item.append(
            {
                "item_id": row.drink_id,
                "name": row.name or "Unknown",
                "qty": int(row.qty or 0),
                "revenue_cents": int(row.revenue_cents or 0),
            }
        )

    category_rows = db.execute(
        select(
            Drink.type,
            func.coalesce(func.sum(OrderItem.qty), 0).label("qty"),
            func.coalesce(func.sum(OrderItem.qty * OrderItem.unit_price_cents), 0).label(
                "revenue_cents"
            ),
        )
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Drink, Drink.id == OrderItem.drink_id, isouter=True)
        .where(Order.event_id == event_id)
        .group_by(Drink.type)
        .order_by(func.sum(OrderItem.qty * OrderItem.unit_price_cents).desc())
    ).all()

    by_category = []
    for row in category_rows:
        category = (row.type or "").strip().lower() or "unknown"
        by_category.append(
            {
                "category": category,
                "qty": int(row.qty or 0),
                "revenue_cents": int(row.revenue_cents or 0),
            }
        )

    cost_rows = (
        db.query(EventCost)
        .filter(EventCost.event_id == event_id)
        .order_by(EventCost.created_at.desc())
        .all()
    )
    cost_lines = [
        {
            "id": cost.id,
            "label": cost.label,
            "amount_cents": cost.amount_cents,
            "category": cost.category,
        }
        for cost in cost_rows
    ]
    total_cost_cents = sum(cost.amount_cents for cost in cost_rows)

    return {
        "event_id": event_id,
        "generated_at": now_utc().isoformat(),
        "sales": {
            "total_orders": int(total_orders),
            "gross_revenue_cents": int(gross_revenue_cents),
            "by_item": by_item,
            "by_category": by_category,
        },
        "costs": {"total_cost_cents": int(total_cost_cents), "lines": cost_lines},
        "profit": {"gross_profit_cents": int(gross_revenue_cents) - int(total_cost_cents)},
    }


@app.post("/events/{event_id}/staff/invite", response_model=StaffInviteOut)
def invite_staff(
    event_id: int,
    payload: StaffInviteIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    require_role_for_event(db, user.id, event_id, "admin")

    role = (payload.role or "").lower()
    if role != "entry":
        raise HTTPException(status_code=400, detail={"error": "invalid_role"})

    token_value = generate_staff_invite_token(db)
    expires_at = now_utc() + timedelta(hours=payload.expires_in_hours)
    invite = StaffInviteToken(
        event_id=event_id,
        role=role,
        token=token_value,
        max_uses=payload.max_uses,
        used_count=0,
        expires_at=expires_at,
        is_revoked=False,
        created_at=now_utc(),
        created_by_user_id=user.id,
    )
    db.add(invite)
    db.flush()
    log_event_action(
        db,
        event_id=event_id,
        actor_user_id=user.id,
        action="staff_invite_created",
        payload={
            "role": role,
            "max_uses": payload.max_uses,
            "expires_at": expires_at.isoformat(),
            "token_id": invite.id,
        },
    )
    db.commit()

    return {
        "event_id": event_id,
        "role": role,
        "token": token_value,
        "invite_qr": f"tore://staff_invite?event_id={event_id}&token={token_value}",
        "expires_at": expires_at.isoformat(),
    }


@app.post("/events/{event_id}/staff/accept", response_model=StaffAcceptOut)
def accept_staff_invite(
    event_id: int,
    payload: StaffAcceptIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invite = (
        db.query(StaffInviteToken)
        .filter(StaffInviteToken.event_id == event_id, StaffInviteToken.token == payload.token)
        .first()
    )
    if not invite or invite.is_revoked:
        raise HTTPException(status_code=400, detail={"error": "invalid_token"})

    if invite.expires_at and now_utc() > invite.expires_at:
        raise HTTPException(status_code=400, detail={"error": "expired_token"})

    if invite.used_count >= invite.max_uses:
        raise HTTPException(status_code=400, detail={"error": "max_uses_reached"})

    staff = (
        db.query(EventStaff)
        .filter(EventStaff.event_id == event_id, EventStaff.user_id == user.id)
        .first()
    )
    role_granted = invite.role
    if staff:
        if (staff.role or "").lower() == "admin":
            role_granted = "admin"
        else:
            staff.role = invite.role
        staff.is_active = True
        staff.revoked_at = None
        staff.revoked_by_user_id = None
    else:
        staff = EventStaff(
            event_id=event_id,
            user_id=user.id,
            role=invite.role,
            is_active=True,
            created_at=now_utc(),
            created_by_user_id=invite.created_by_user_id,
        )
        db.add(staff)

    invite.used_count += 1
    log_event_action(
        db,
        event_id=event_id,
        actor_user_id=user.id,
        action="staff_invite_accepted",
        payload={"role": role_granted, "token_id": invite.id, "user_id": user.id},
    )
    db.commit()

    return {"ok": True, "role_granted": role_granted}


@app.get("/events/{event_id}/staff", response_model=List[StaffMemberOut])
def list_staff(
    event_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    require_role_for_event(db, user.id, event_id, "admin")

    rows = (
        db.query(EventStaff, AppUser)
        .outerjoin(AppUser, AppUser.id == EventStaff.user_id)
        .filter(EventStaff.event_id == event_id)
        .order_by(EventStaff.created_at.desc())
        .all()
    )
    result = []
    for staff, staff_user in rows:
        result.append(
            {
                "user_id": staff.user_id,
                "display_name": staff_user.display_name if staff_user else None,
                "role": staff.role,
                "is_active": staff.is_active,
                "created_at": staff.created_at.isoformat() if staff.created_at else None,
                "created_by_user_id": staff.created_by_user_id,
                "revoked_at": staff.revoked_at.isoformat() if staff.revoked_at else None,
                "revoked_by_user_id": staff.revoked_by_user_id,
            }
        )
    return result


@app.patch("/events/{event_id}/staff/{user_id}/revoke")
def revoke_staff(
    event_id: int,
    user_id: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    require_role_for_event(db, user.id, event_id, "admin")

    staff = (
        db.query(EventStaff)
        .filter(EventStaff.event_id == event_id, EventStaff.user_id == user_id)
        .first()
    )
    if not staff:
        raise HTTPException(404, "Staff not found")

    staff.is_active = False
    staff.revoked_at = now_utc()
    staff.revoked_by_user_id = user.id
    log_event_action(
        db,
        event_id=event_id,
        actor_user_id=user.id,
        action="staff_revoked",
        payload={"user_id": user_id, "role": staff.role},
    )
    db.commit()
    return {"ok": True}


@app.get("/events/{event_id}/menu")
def event_menu(event_id: int):
    s = get_session()
    try:
        e = s.get(Event, event_id)
        if not e:
            raise HTTPException(404, "Event not found")
        require_feature(s, event_id, "menu_enabled")
        apply_decay(s, event_id)

        rows = s.scalars(select(EventDrink).where(EventDrink.event_id == event_id)).all()
        out = []
        for ed in rows:
            d = s.get(Drink, ed.drink_id)
            if not d:
                continue
            effective = (
                ed.override_price_cents
                if ed.override_price_cents is not None
                else ed.current_price_cents
            )
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
    return {
        "ts": start.isoformat(),
        "open": prices[0],
        "high": max(prices),
        "low": min(prices),
        "close": prices[-1],
    }


@app.post("/events/{event_id}/entry/issue")
def issue_entry(event_id: int, payload: IssueEntryIn):
    s = get_session()
    try:
        e = s.get(Event, event_id)
        if not e:
            raise HTTPException(404, "Event not found")
        require_feature(s, event_id, "entry_enabled")
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


@app.post("/events/{event_id}/entry/scans", response_model=EntryStatsOut)
def record_entry_scan(
    event_id: int,
    payload: EntryScanIn,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    raw = _extract_bearer_token(authorization)
    if not raw:
        raise HTTPException(status_code=401, detail="Missing token")

    staff_id = None
    user = _resolve_app_user_from_token(raw, db)
    if user:
        require_feature(db, event_id, "entry_enabled")
        require_role_for_event(db, user.id, event_id, "entry")
        staff_id = user.id
    else:
        identity = _resolve_partner_identity_from_token(raw, db)
        if not identity:
            raise HTTPException(status_code=401, detail="Invalid token")
        if event.bar_id != identity["bar_id"]:
            raise HTTPException(status_code=403, detail="Forbidden")
        require_feature(db, event_id, "entry_enabled")
        _require_partner_roles(identity, {"entry", "manager"})
        staff_id = str(identity["user_id"])

    if payload.delta not in (-1, 1):
        raise HTTPException(400, "delta must be +1 or -1")
    if payload.source not in {"scan", "manual"}:
        raise HTTPException(400, "source must be scan or manual")
    if not payload.device_id or not payload.idempotency_key:
        raise HTTPException(400, "device_id and idempotency_key are required")

    existing = (
        db.query(EntryLog)
        .filter(
            EntryLog.event_id == event_id,
            EntryLog.idempotency_key == payload.idempotency_key,
        )
        .first()
    )
    if existing:
        return entry_stats(db, event_id)

    log = EntryLog(
        event_id=event_id,
        created_at=now_utc(),
        delta=payload.delta,
        source=payload.source,
        staff_id=staff_id,
        device_id=payload.device_id,
        idempotency_key=payload.idempotency_key,
        raw_qr=payload.raw_qr,
    )
    db.add(log)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return entry_stats(db, event_id)
    return entry_stats(db, event_id)


@app.get("/events/{event_id}/entry/stats", response_model=EntryStatsOut)
def get_entry_stats(
    event_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    raw = _extract_bearer_token(authorization)
    if not raw:
        raise HTTPException(status_code=401, detail="Missing token")

    user = _resolve_app_user_from_token(raw, db)
    if user:
        require_feature(db, event_id, "entry_enabled")
        require_role_for_event(db, user.id, event_id, "entry")
        return entry_stats(db, event_id)

    identity = _resolve_partner_identity_from_token(raw, db)
    if identity:
        if event.bar_id != identity["bar_id"]:
            raise HTTPException(status_code=403, detail="Forbidden")
        require_feature(db, event_id, "entry_enabled")
        return entry_stats(db, event_id)

    raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/events/{event_id}/entry/logs", response_model=List[EntryLogOut])
def get_entry_logs(
    event_id: int,
    limit: int = Query(200, ge=1, le=200),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    require_feature(db, event_id, "entry_enabled")
    require_role_for_event(db, user.id, event_id, "entry")
    rows = (
        db.query(EntryLog)
        .filter(EntryLog.event_id == event_id)
        .order_by(EntryLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        EntryLogOut(
            id=row.id,
            event_id=row.event_id,
            created_at=row.created_at,
            delta=row.delta,
            source=row.source,
            staff_id=row.staff_id,
            device_id=row.device_id,
            idempotency_key=row.idempotency_key,
            raw_qr=row.raw_qr,
        )
        for row in rows
    ]


@app.get("/tickets/balance")
def ticket_balance(event_id: int = Query(...), user_id: str = Query(...)):
    s = get_session()
    try:
        require_feature(s, event_id, "wallet_enabled")
        b = get_or_create_balance(s, event_id, user_id)
        s.commit()
        return {"event_id": event_id, "user_id": user_id, "balance": b.balance}
    finally:
        s.close()


@app.get("/events/{event_id}/wallet/history")
def wallet_history(
    event_id: int,
    user_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = None,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    require_feature(db, event_id, "wallet_enabled")
    return []


@app.post("/tickets/credit")
def credit_tickets(payload: CreditTicketsIn):
    s = get_session()
    try:
        e = s.get(Event, payload.event_id)
        if not e:
            raise HTTPException(404, "Event not found")
        require_feature(s, payload.event_id, "wallet_enabled")
        if not e.allow_self_ticket_adjust:
            raise HTTPException(403, "Ticket adjust disabled for this event")

        b = get_or_create_balance(s, payload.event_id, payload.user_id)
        b.balance = max(0, b.balance + payload.delta)
        s.add(b)
        s.commit()
        return {"ok": True, "balance": b.balance}
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
        return {
            "id": b.id,
            "barcode": b.barcode,
            "name": b.name,
            "brewery": b.brewery,
            "style": b.style,
        }
    finally:
        s.close()


@app.post("/beers")
def create_beer(payload: CreateBeerIn):
    s = get_session()
    try:
        existing = s.scalar(select(Beer).where(Beer.barcode == payload.barcode))
        if existing:
            return {
                "id": existing.id,
                "barcode": existing.barcode,
                "name": existing.name,
                "brewery": existing.brewery,
                "style": existing.style,
            }
        b = Beer(
            barcode=payload.barcode,
            name=payload.name,
            brewery=payload.brewery,
            style=payload.style,
        )
        s.add(b)
        s.commit()
        return {
            "id": b.id,
            "barcode": b.barcode,
            "name": b.name,
            "brewery": b.brewery,
            "style": b.style,
            "new": True,
        }
    finally:
        s.close()


@app.get("/checkins")
def list_checkins(user_id: str = Query(...), limit: int = Query(default=30, ge=1, le=200)):
    s = get_session()
    try:
        q = (
            select(Checkin)
            .where(Checkin.user_id == user_id)
            .order_by(Checkin.created_at.desc())
            .limit(limit)
        )
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
                    "beer": {
                        "id": b.id,
                        "barcode": b.barcode,
                        "name": b.name,
                        "brewery": b.brewery,
                        "style": b.style,
                    },
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
        return [{"user_id": r.user_id, "checkins": int(r.checkins)} for r in rows]
    finally:
        s.close()


# ---------------------------------------------------------------------
# Battles (simple mini-game)
# ---------------------------------------------------------------------

@app.post("/battles")
def create_battle(payload: CreateBattleIn):
    s = get_session()
    try:
        require_feature(s, payload.event_id or 0, "battles_enabled") if payload.event_id else None
        code = random_code(6)
        b = Battle(
            event_id=payload.event_id,
            created_by_user_id=payload.user_id,
            title=payload.title,
            mode=payload.mode,
            join_code=code,
            created_at=now_utc(),
        )
        s.add(b)
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
        require_feature(s, b.event_id or 0, "battles_enabled") if b.event_id else None

        exists = s.scalar(
            select(BattleParticipant).where(
                BattleParticipant.battle_id == b.id, BattleParticipant.user_id == payload.user_id
            )
        )
        if exists:
            return {"ok": True, "battle_id": b.id}

        p = BattleParticipant(
            battle_id=b.id,
            user_id=payload.user_id,
            display_name=payload.display_name,
            joined_at=now_utc(),
        )
        s.add(p)
        s.commit()
        return {"ok": True, "battle_id": b.id}
    finally:
        s.close()


@app.post("/battles/{battle_id}/winner")
def set_winner(battle_id: int, payload: WinnerIn):
    s = get_session()
    try:
        b = s.get(Battle, battle_id)
        if not b:
            raise HTTPException(404, "Battle not found")
        b.winner_user_id = payload.winner_user_id
        b.ended_at = now_utc()
        s.add(b)
        s.commit()
        return {"ok": True}
    finally:
        s.close()
