from __future__ import annotations

import os
import logging
import secrets
import string
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

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


def resolve_qr_payload(raw: str) -> Dict[str, Any]:
    trimmed = (raw or "").strip()
    if not trimmed:
        return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}

    parsed = urlparse(trimmed)
    if parsed.scheme.lower() != "tore":
        return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}

    qr_type = (parsed.netloc or parsed.path.lstrip("/")).lower()
    if qr_type not in {"join", "menu", "entry", "admin_config", "staff_entry", "staff_invite"}:
        return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}

    params = parse_qs(parsed.query)
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

    return {"valid": True, "type": qr_type, "event_id": event_id, "token": token, "reason": None}


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


class QrResolveIn(BaseModel):
    raw: str


class QrResolveOut(BaseModel):
    valid: bool
    type: str
    event_id: Optional[int] = None
    token: Optional[str] = None
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
            "token": None,
            "reason": base.get("reason"),
            "required_role": None,
            "granted_role": "guest",
        }

    event_id = base.get("event_id")
    qr_type = base.get("type")
    token = base.get("token")
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
            "token": None,
            "reason": "forbidden",
            "required_role": required_role,
            "granted_role": granted_role,
        }

    return {
        "valid": True,
        "type": qr_type,
        "event_id": event_id,
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


@app.post("/orders")
def create_order(payload: CreateOrderIn):
    s = get_session()
    try:
        e = s.get(Event, payload.event_id)
        if not e:
            raise HTTPException(404, "Event not found")
        if payload.pay_mode in {"checkin", "checkin_staff"}:
            require_feature(s, payload.event_id, "checkin_enabled")
        else:
            require_feature(s, payload.event_id, "menu_enabled")
        if payload.pay_mode == "tickets":
            require_feature(s, payload.event_id, "wallet_enabled")
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
        require_feature(s, event_id, "entry_enabled")
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
