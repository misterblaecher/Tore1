from __future__ import annotations

# Routes refactor map: Orders -> app/routers/orders.py, Wallet -> app/routers/wallet.py, Polymarket -> app/routers/polymarket.py.

import os
import logging
import csv
import io
import secrets
import string
import hashlib
import json
import subprocess
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Literal

import jwt
from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, case, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import Base, engine, get_session, now_utc, DATABASE_URL
from app.services.rate_limit_service import record_status_code, enforce_rate_limit
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
    EntryScanLog,
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
    AppUser,
    AppToken,
    PartnerMembership,
    Wallet,
    WalletTx,
    WalletGift,
    Bet,
    BetPosition,
    BetResolutionLog,
    Battle,
    BattleTeam,
    BattleJoin,
    BattleAction,
    MenuCategory,
    MenuItem,
    MenuItemVariant,
    MenuTrackEvent,
    BarPrivacySetting,
    AppUserPrivacySetting,
    EventModuleConfig,
    EventRuntimeState,
    EventJoin,
    EventCharterAcceptance,
    TicketTransfer,
    Committee,
    CommitteeYear,
    CommitteeMembership,
    CommitteeInviteCode,
    CommitteeRolePermission,
    CommitteeAdminIdempotency,
    CommitteeForumCategory,
    CommitteeForumPost,
    CommitteeLedgerEntry,
    CommitteeLedgerIdempotency,
    CommitteeBudgetBucket,
    CommitteeBaptemeCampaign,
    CommitteeBaptemeInvite,
    CommitteeBaptemeSlot,
    CommitteeBaptemeAssignment,
    CommitteeBaptemeIncident,
    CommitteeBaptemeIdempotency,
    CommitteeGlossarySettings,
    CommitteeGlossaryTerm,
    CommitteeGlossaryIdempotency,
    Organization,
    OrganizationMembership,
    OrganizationInviteCode,
    OrganizationWriteIdempotency,
    AuditLog,
    UserPrivacyDeleteRequest,
    UserSanction,
    GlobalFeatureFlag,
)

from partner_auth import router as partner_auth_router, current_identity as current_partner_identity
from app.db.sqlite_compat import ensure_sqlite_compat
from app.services.audit_service import write_audit_log
from app.services.idempotency_service import ensure_idempotency_key


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


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _strict_dev_env_enabled() -> bool:
    return (os.getenv("ENV") or "").strip().upper() == "DEV"


def _debug_git_sha() -> Optional[str]:
    env_sha = (os.getenv("GIT_SHA") or os.getenv("TORE_GIT_SHA") or "").strip()
    if env_sha:
        return env_sha
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip() or None
    except Exception:
        return None


def _debug_signing_key_ids() -> list[str]:
    ring = (os.getenv("TORE_QR_SIGNING_KEYS") or "").strip()
    if ring:
        values = [item.strip() for item in ring.split(",") if item.strip()]
    else:
        fallback = (os.getenv("TORE_QR_SIGNING_SECRET") or os.getenv("TORE_JWT_SECRET") or "").strip()
        values = [fallback] if fallback else []

    key_ids: list[str] = []
    for value in values:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        key_ids.append(digest[:12])
    return key_ids


def _cors_origins() -> list[str]:
    raw = (os.getenv("TORE_CORS_ORIGINS") or "").strip()
    if raw:
        values = [v.strip() for v in raw.split(",") if v.strip()]
        return values or ["*"]

    env_name = (os.getenv("TORE_ENV") or os.getenv("ENV") or "dev").strip().lower()
    if env_name in {"prod", "production"}:
        logging.warning("TORE_CORS_ORIGINS is empty in production profile; CORS allowlist is empty.")
        return []

    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]


def _validate_qr_signing_keys_format() -> tuple[bool, str]:
    ring = (os.getenv("TORE_QR_SIGNING_KEYS") or "").strip()
    if not ring:
        return True, "TORE_QR_SIGNING_KEYS not set (fallback secret strategy enabled)"

    values = [item.strip() for item in ring.split(",") if item.strip()]
    if not values:
        return False, "TORE_QR_SIGNING_KEYS is present but empty after parsing"

    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-:.")
    invalid: list[str] = []
    for idx, value in enumerate(values, start=1):
        if len(value) < 16:
            invalid.append(f"#{idx}:too_short")
            continue
        if any(ch not in allowed for ch in value):
            invalid.append(f"#{idx}:invalid_chars")

    if invalid:
        return False, f"invalid keys ({', '.join(invalid)})"
    return True, f"{len(values)} key(s)"


def _startup_sanity_checks() -> None:
    ok, msg = _validate_qr_signing_keys_format()
    if ok:
        logging.info(f"startup.sanity.qr_signing_keys={msg}")
    else:
        logging.warning(f"startup.sanity.qr_signing_keys={msg}")

    cors = _cors_origins()
    if cors:
        logging.info(f"startup.sanity.cors={cors}")
    else:
        logging.warning("startup.sanity.cors=EMPTY_ALLOWLIST")


def _should_bootstrap_on_startup() -> bool:
    if engine.dialect.name == "sqlite":
        return True
    return _env_bool("TORE_AUTO_DB_BOOTSTRAP", default=False)


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



def _ensure_market_tick_columns() -> None:
    if engine.dialect.name != "sqlite":
        return
    s = get_session()
    try:
        columns = {
            row[1]
            for row in s.execute(text("PRAGMA table_info(drink_price_ticks)")).fetchall()
        }
        if "ref_order_id" not in columns:
            s.execute(text("ALTER TABLE drink_price_ticks ADD COLUMN ref_order_id INTEGER"))
            s.execute(text("CREATE INDEX IF NOT EXISTS ix_drink_price_ticks_ref_order_id ON drink_price_ticks (ref_order_id)"))
        s.commit()
    finally:
        s.close()



def _ensure_polymarket_v1_columns() -> None:
    if engine.dialect.name != "sqlite":
        return
    s = get_session()
    try:
        bet_columns = {
            row[1]
            for row in s.execute(text("PRAGMA table_info(polymarket_bets)")).fetchall()
        }
        if "dispute_window_minutes" not in bet_columns:
            s.execute(text("ALTER TABLE polymarket_bets ADD COLUMN dispute_window_minutes INTEGER DEFAULT 60"))
        if "resolved_at" not in bet_columns:
            s.execute(text("ALTER TABLE polymarket_bets ADD COLUMN resolved_at DATETIME"))
        if "finalized_at" not in bet_columns:
            s.execute(text("ALTER TABLE polymarket_bets ADD COLUMN finalized_at DATETIME"))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS polymarket_disputes (
                id INTEGER NOT NULL PRIMARY KEY,
                bet_id INTEGER NOT NULL,
                user_id VARCHAR NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                created_at DATETIME,
                CONSTRAINT uq_polymarket_dispute_bet_user UNIQUE (bet_id, user_id),
                FOREIGN KEY(bet_id) REFERENCES polymarket_bets (id)
            )
        """))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_polymarket_disputes_bet_id ON polymarket_disputes (bet_id)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_polymarket_disputes_user_id ON polymarket_disputes (user_id)"))
        s.commit()
    finally:
        s.close()


def _ensure_wallet_indexes() -> None:
    s = get_session()
    try:
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_wallet_txs_user_ts ON wallet_txs (user_id, created_at)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_wallet_ledger_event_ts ON wallet_ledger_entries (event_id, created_at)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_wallet_gifts_from_ts ON wallet_gifts (from_user_id, created_at)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_wallet_gifts_to_ts ON wallet_gifts (to_user_id, created_at)"))
        s.commit()
    finally:
        s.close()


def _ensure_app_user_privacy_columns() -> None:
    if engine.dialect.name != "sqlite":
        return
    s = get_session()
    try:
        columns = {row[1] for row in s.execute(text("PRAGMA table_info(app_users)")).fetchall()}
        if "email" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN email VARCHAR(255)"))
            s.execute(text("CREATE INDEX IF NOT EXISTS ix_app_users_email ON app_users (email)"))
        if "phone" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN phone VARCHAR(64)"))
            s.execute(text("CREATE INDEX IF NOT EXISTS ix_app_users_phone ON app_users (phone)"))
        if "is_deleted" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
            s.execute(text("CREATE INDEX IF NOT EXISTS ix_app_users_is_deleted ON app_users (is_deleted)"))
        if "deleted_at" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN deleted_at DATETIME"))
        if "anonymized_at" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN anonymized_at DATETIME"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_app_users_deleted_at ON app_users (deleted_at)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_app_users_anonymized_at ON app_users (anonymized_at)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_user_ts ON audit_logs (actor_user_id, ts)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_committee_ts ON audit_logs (committee_id, ts)"))
        s.commit()
    finally:
        s.close()


def ensure_seed() -> None:
    Base.metadata.create_all(engine)
    _ensure_orders_payment_columns()
    _ensure_market_tick_columns()
    _ensure_polymarket_v1_columns()
    _ensure_wallet_indexes()
    _ensure_app_user_privacy_columns()
    ensure_sqlite_compat(engine)
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


def _retention_days() -> int:
    try:
        return max(1, int(os.getenv("TORE_PRIVACY_RETENTION_DAYS", "30")))
    except ValueError:
        return 30


def _serialize_dt(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _active_sanction_for_user(db: Session, user_id: str) -> Optional[UserSanction]:
    now = now_utc()
    rows = db.query(UserSanction).filter(UserSanction.user_id == user_id, UserSanction.status == "ACTIVE").order_by(UserSanction.created_at.desc()).all()
    for row in rows:
        if row.starts_at and row.starts_at > now:
            continue
        if row.ends_at and row.ends_at <= now:
            row.status = "EXPIRED"
            db.add(row)
            continue
        return row
    return None


def _enforce_user_sanctions(db: Session, user: AppUser) -> None:
    if bool(getattr(user, "is_deleted", False)):
        raise HTTPException(status_code=403, detail={"reason": "ACCOUNT_DELETED"})
    sanction = _active_sanction_for_user(db, user.id)
    if sanction and sanction.type in {"SUSPEND", "BAN"}:
        raise HTTPException(
            status_code=403,
            detail={
                "reason": "SANCTIONED",
                "type": sanction.type,
                "endsAt": _serialize_dt(sanction.ends_at),
            },
        )


def _apply_user_anonymization(user: AppUser) -> None:
    user.display_name = "Deleted User"
    user.avatar_url = None
    user.address_text = None
    user.show_address = False
    user.email = None
    user.phone = None
    user.is_deleted = True
    now = now_utc()
    if user.deleted_at is None:
        user.deleted_at = now
    user.anonymized_at = now


def _require_global_admin(identity: Dict[str, Any]) -> None:
    if (identity.get("role") or "").upper() != "ADMIN_GLOBAL":
        raise HTTPException(status_code=403, detail={"reason": "FORBIDDEN_ADMIN_GLOBAL"})


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

    _enforce_user_sanctions(db, user)
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


def entry_count(db: Session, event_id: int) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(EntryLog.delta), 0)).where(EntryLog.event_id == event_id)) or 0)


def _entry_status_for_raw(db: Session, event_id: int, raw_qr: str) -> str:
    seen = (
        db.query(EntryLog.id)
        .filter(EntryLog.event_id == event_id, EntryLog.raw_qr == raw_qr, EntryLog.delta > 0)
        .first()
    )
    return "already_checked" if seen else "accepted"


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
    show_identity_to_staff: Optional[bool] = None
    visibility: Optional[str] = None
    show_identity_in_bar: Optional[bool] = None


class IdentityConsentBarPatchIn(BaseModel):
    staff_identity_consent_required: bool


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


class EntryCheckinIn(BaseModel):
    ticket_qr_raw: Optional[str] = None
    user_id: Optional[str] = None
    ticket_id: Optional[str] = None
    scanned_at: Optional[datetime] = None
    device_id: str


class EntryCheckinOut(BaseModel):
    status: str
    entryCount: int
    userLabel: Optional[str] = None
    timestamp: datetime
    pendingSync: bool = False


class EntryCountOut(BaseModel):
    entryCount: int
    timestamp: datetime


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


class JoinByCodeIn(BaseModel):
    code: str
    accepted_charter_version: Optional[str] = None


class JoinEventIn(BaseModel):
    accepted_charter_version: Optional[str] = None


class CommitteeJoinByCodeIn(BaseModel):
    code: str


class CommitteeInviteCodeIn(BaseModel):
    expiresAt: Optional[datetime] = None
    usesLeft: Optional[int] = Field(default=None, ge=1)


class CommitteeSetRoleIn(BaseModel):
    role: Literal["OWNER", "ADMIN", "MOD", "MEMBER"]
    reason: str = Field(min_length=2, max_length=280)


class CommitteeRevokeIn(BaseModel):
    reason: str = Field(min_length=2, max_length=280)


class CommitteeForumCreatePostIn(BaseModel):
    yearId: int
    categoryId: int
    title: str = Field(min_length=3, max_length=180)
    body: str = Field(min_length=1, max_length=5000)


class CommitteeForumPinIn(BaseModel):
    pinned: bool
    reason: str = Field(min_length=2, max_length=280)


class CommitteeForumLockIn(BaseModel):
    locked: bool
    reason: str = Field(min_length=2, max_length=280)


class CommitteeForumDeleteIn(BaseModel):
    reason: str = Field(min_length=2, max_length=280)


class CommitteeForumCreateCategoryIn(BaseModel):
    yearId: int
    name: str = Field(min_length=2, max_length=120)
    orderIndex: Optional[int] = Field(default=0, ge=0, le=1000)


class CommitteeForumUpdateCategoryIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    orderIndex: Optional[int] = Field(default=None, ge=0, le=1000)
    isArchived: Optional[bool] = None


class CommitteeFinanceLedgerCreateIn(BaseModel):
    yearId: int
    type: Literal["INCOME", "EXPENSE"]
    amountCents: int = Field(ge=1)
    currency: str = Field(default="EUR", min_length=3, max_length=8)
    category: str = Field(min_length=2, max_length=120)
    occurredAt: str = Field(min_length=10, max_length=10)
    note: Optional[str] = Field(default=None, max_length=5000)
    attachmentUrl: Optional[str] = Field(default=None, max_length=512)


class CommitteeBudgetBucketIn(BaseModel):
    month: str = Field(min_length=7, max_length=7)
    category: str = Field(min_length=2, max_length=120)
    budgetCents: int = Field(ge=0)


class CommitteeBaptemeCampaignIn(BaseModel):
    yearId: int
    name: str = Field(min_length=2, max_length=180)


class CommitteeBaptemeInviteIn(BaseModel):
    campaignId: int
    blueDisplayName: str = Field(min_length=2, max_length=180)
    expiresAt: Optional[datetime] = None


class CommitteeBaptemeAcceptIn(BaseModel):
    inviteCode: str = Field(min_length=4, max_length=32)


class CommitteeBaptemeSlotIn(BaseModel):
    campaignId: int
    startsAt: datetime
    endsAt: datetime
    location: str = Field(min_length=2, max_length=180)
    description: str = Field(min_length=2, max_length=1000)


class CommitteeBaptemeAssignIn(BaseModel):
    inviteId: int
    slotId: int


class CommitteeBaptemeIncidentIn(BaseModel):
    campaignId: int
    inviteId: Optional[int] = None
    type: str = Field(min_length=2, max_length=48)
    note: str = Field(min_length=2, max_length=2000)


class CommitteeGlossaryTermCreateIn(BaseModel):
    term: str = Field(min_length=1, max_length=140)
    definition: str = Field(min_length=1, max_length=10000)
    examples: Optional[str] = Field(default=None, max_length=10000)
    tags: Optional[List[str]] = None
    yearId: Optional[int] = None
    isOfficial: Optional[bool] = False


class CommitteeGlossaryTermUpdateIn(BaseModel):
    definition: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    examples: Optional[str] = Field(default=None, max_length=10000)
    tags: Optional[List[str]] = None
    isOfficial: Optional[bool] = None
    status: Optional[Literal["ACTIVE", "ARCHIVED", "DELETED"]] = None


class CommitteeGlossaryArchiveIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=280)


class CommitteeGlossaryDeleteIn(BaseModel):
    reason: str = Field(min_length=2, max_length=280)


class CommitteeGlossarySettingsIn(BaseModel):
    public_enabled: bool


class EventCharterOut(BaseModel):
    event_id: int
    enabled: bool
    version: Optional[str] = None
    text: Optional[str] = None


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



@app.middleware("http")
async def _metrics_lite_middleware(request, call_next):
    response = await call_next(request)
    try:
        record_status_code(int(response.status_code))
    except Exception:
        pass
    return response

app.include_router(partner_auth_router, prefix="/partner")
from app.routers.orders import router as orders_router
from app.routers.wallet import router as wallet_router
from app.routers.polymarket import router as polymarket_router
from app.routers.qr import router as qr_router
from app.routers.analytics import router as analytics_router
from app.routers.hunt import router as hunt_router
from app.routers.battles import router as battles_router
from app.routers.market import router as market_router
from app.routers.entry import router as entry_router
from app.routers.portal_event_control import router as portal_event_control_router
from app.routers.p3 import router as p3_router
from app.routers.zones import router as zones_router
from app.routers.ops import router as ops_router
from app.routers.ticker import router as ticker_router
from app.routers.broadcasts import router as broadcasts_router
from app.routers.incidents import router as incidents_router
from app.routers.bar_menu_admin import router as bar_menu_admin_router
from app.routers.music_vote import router as music_vote_router
from app.routers.event_wifi import router as event_wifi_router
from app.routers.safety_v1 import router as safety_v1_router
from app.routers.map_calendar import router as map_calendar_router
app.include_router(orders_router)
app.include_router(wallet_router)
app.include_router(analytics_router)
app.include_router(polymarket_router)
app.include_router(qr_router)
app.include_router(hunt_router)
app.include_router(battles_router)
app.include_router(market_router)
app.include_router(entry_router)
app.include_router(portal_event_control_router)
app.include_router(p3_router)
app.include_router(zones_router)
app.include_router(ops_router)
app.include_router(ticker_router)
app.include_router(broadcasts_router)
app.include_router(incidents_router)
app.include_router(bar_menu_admin_router)
app.include_router(music_vote_router)
app.include_router(event_wifi_router)
app.include_router(safety_v1_router)
app.include_router(map_calendar_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    _startup_sanity_checks()
    if _should_bootstrap_on_startup():
        ensure_seed()
    else:
        logging.info("Startup bootstrap disabled (expected in Postgres prod with Alembic migrations).")


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


@app.get("/partner/portal/settings/identity-consent")
def partner_portal_identity_consent(identity=Depends(current_partner_identity), db: Session = Depends(get_db)):
    bar = db.get(Bar, identity["bar_id"])
    if not bar:
        raise HTTPException(404, "Bar not found")
    settings = db.query(BarPrivacySetting).filter(BarPrivacySetting.bar_id == bar.id).first()
    return {"staff_identity_consent_required": bool(settings and settings.staff_identity_consent_required)}


@app.patch("/partner/portal/settings/identity-consent")
def partner_portal_identity_consent_patch(
    payload: IdentityConsentBarPatchIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    bar = db.get(Bar, identity["bar_id"])
    if not bar:
        raise HTTPException(404, "Bar not found")
    settings = db.query(BarPrivacySetting).filter(BarPrivacySetting.bar_id == bar.id).first()
    if not settings:
        settings = BarPrivacySetting(bar_id=bar.id)
    settings.staff_identity_consent_required = payload.staff_identity_consent_required
    db.add(settings)
    db.commit()
    return {"staff_identity_consent_required": settings.staff_identity_consent_required}


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


@app.get("/debug/info")
def debug_info(db: Session = Depends(get_db)):
    if not _strict_dev_env_enabled():
        raise HTTPException(404, "Not found")

    modules_flags_count = db.query(GlobalFeatureFlag).count()
    return {
        "serverTime": now_utc().isoformat(),
        "gitSha": _debug_git_sha(),
        "signingKeyIds": _debug_signing_key_ids(),
        "modulesFlagsCount": modules_flags_count,
    }


# ---------------------------------------------------------------------
# Guest auth + profil
# ---------------------------------------------------------------------

@app.post("/auth/guest", response_model=GuestOut)
def auth_guest(payload: GuestIn):
    if engine.dialect.name == "sqlite":
        _ensure_orders_payment_columns()
        _ensure_market_tick_columns()
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
                "show_identity_to_staff": False,
                "visibility": "public",
                "show_identity_in_bar": False,
            },
        }
    finally:
        s.close()


@app.get("/auth/me")
def me(
    bar_id: Optional[int] = Query(default=None),
    user: AppUser = Depends(get_current_user),
):
    s = get_session()
    try:
        settings = s.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id == user.id).first()
        bar_settings = (
            s.query(BarPrivacySetting).filter(BarPrivacySetting.bar_id == bar_id).first()
            if bar_id is not None
            else None
        )
        active_sanction = _active_sanction_for_user(s, user.id)
        return {
            "id": user.id,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "address_text": user.address_text,
            "show_address": user.show_address,
            "show_avatar": user.show_avatar,
            "show_identity_to_staff": bool(settings and settings.show_identity_to_staff),
            "visibility": (settings.visibility if settings and settings.visibility else "public"),
            "show_identity_in_bar": bool(settings and (settings.show_identity_in_bar or settings.show_identity_to_staff)),
            "bar_show_identity_to_staff": (
                bool(bar_settings and bar_settings.staff_identity_consent_required)
                if bar_id is not None
                else None
            ),
            "warned": bool(active_sanction and active_sanction.type == "WARN"),
            "warning": (
                {"type": active_sanction.type, "endsAt": _serialize_dt(active_sanction.ends_at), "reason": active_sanction.reason}
                if active_sanction and active_sanction.type == "WARN"
                else None
            ),
        }
    finally:
        s.close()


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
        settings = s.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id == u.id).first()
        if payload.show_identity_to_staff is not None or payload.visibility is not None or payload.show_identity_in_bar is not None:
            if not settings:
                settings = AppUserPrivacySetting(user_id=u.id)
            if payload.show_identity_to_staff is not None:
                settings.show_identity_to_staff = payload.show_identity_to_staff
            if payload.visibility in {"public", "private"}:
                settings.visibility = payload.visibility
            if payload.show_identity_in_bar is not None:
                settings.show_identity_in_bar = payload.show_identity_in_bar
                settings.show_identity_to_staff = payload.show_identity_in_bar
            s.add(settings)

        s.add(u)

        write_audit_log(
            s,
            actor_partner_id=None,
            actor_role="user",
            action="user.privacy.update",
            entity_type="app_user",
            entity_id=str(u.id),
            event_id=None,
            bar_id=None,
            payload={
                "show_identity_to_staff": (
                    bool(payload.show_identity_to_staff)
                    if payload.show_identity_to_staff is not None
                    else None
                ),
                "show_address": payload.show_address,
                "show_avatar": payload.show_avatar,
                "visibility": payload.visibility,
                "show_identity_in_bar": payload.show_identity_in_bar,
            },
        )
        s.commit()

        refreshed_settings = s.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id == u.id).first()
        return {
            "id": u.id,
            "display_name": u.display_name,
            "avatar_url": u.avatar_url,
            "address_text": u.address_text,
            "show_address": u.show_address,
            "show_avatar": u.show_avatar,
            "show_identity_to_staff": bool(refreshed_settings and refreshed_settings.show_identity_to_staff),
            "visibility": (refreshed_settings.visibility if refreshed_settings and refreshed_settings.visibility else "public"),
            "show_identity_in_bar": bool(refreshed_settings and (refreshed_settings.show_identity_in_bar or refreshed_settings.show_identity_to_staff)),
        }
    finally:
        s.close()


class AdminSanctionIn(BaseModel):
    type: Literal["WARN", "SUSPEND", "BAN"]
    durationHours: Optional[int] = Field(default=None, ge=1)
    reason: str = Field(min_length=3, max_length=255)


class AdminSanctionRevokeIn(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


class AdminFlagUpdateIn(BaseModel):
    key: str = Field(min_length=2, max_length=64)
    enabled: bool
    reason: str = Field(min_length=3, max_length=255)


class AdminFreezeEventIn(BaseModel):
    reason: str = Field(min_length=3, max_length=180)


def _export_payload_for_user(db: Session, user: AppUser) -> dict[str, Any]:
    profile = {
        "id": user.id,
        "display_name": user.display_name,
        "email": user.email,
        "phone": user.phone,
        "show_address": user.show_address,
        "show_avatar": user.show_avatar,
        "is_deleted": bool(user.is_deleted),
        "created_at": _serialize_dt(user.created_at),
    }
    wallet_transfers = [
        {
            "id": row.id,
            "event_id": row.event_id,
            "from_user_id": row.from_user_id,
            "to_user_id": row.to_user_id,
            "amount": row.amount_tickets,
            "reason": row.reason,
            "created_at": _serialize_dt(row.created_at),
        }
        for row in db.query(WalletGift).filter((WalletGift.from_user_id == user.id) | (WalletGift.to_user_id == user.id)).order_by(WalletGift.id.desc()).limit(500).all()
    ]
    positions = [
        {
            "id": row.id,
            "bet_id": row.bet_id,
            "side": row.side,
            "shares": row.shares,
            "stake_tickets": row.stake_tickets,
            "created_at": _serialize_dt(row.created_at),
        }
        for row in db.query(BetPosition).filter(BetPosition.user_id == user.id).order_by(BetPosition.id.desc()).limit(500).all()
    ]
    committee_memberships = [
        {
            "committee_id": row.committee_id,
            "year_id": row.year_id,
            "role": row.role,
            "status": row.status,
            "created_at": _serialize_dt(row.created_at),
        }
        for row in db.query(CommitteeMembership).filter(CommitteeMembership.user_id == user.id).order_by(CommitteeMembership.id.desc()).all()
    ]
    safety_checkins = [
        {
            "event_id": row.event_id,
            "zone": row.zone,
            "state": row.state,
            "created_at": _serialize_dt(row.created_at),
        }
        for row in db.query(Checkin).filter(Checkin.user_id == user.id).order_by(Checkin.id.desc()).limit(500).all()
    ]
    order_summaries = [
        {
            "id": row.id,
            "event_id": row.event_id,
            "status": row.status,
            "total_tickets": row.total_tickets,
            "created_at": _serialize_dt(row.created_at),
        }
        for row in db.query(Order).filter(Order.user_id == user.id).order_by(Order.id.desc()).limit(500).all()
    ]
    return {
        "profile": profile,
        "walletTransfers": wallet_transfers,
        "polymarketPositions": positions,
        "committeeMemberships": committee_memberships,
        "safetyCheckins": safety_checkins,
        "orderSummaries": order_summaries,
    }


@app.get("/me/export.json")
def me_export_json(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _export_payload_for_user(db, user)


@app.get("/me/export.csv")
def me_export_csv(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    payload = _export_payload_for_user(db, user)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "field", "value"])
    for key, value in payload["profile"].items():
        writer.writerow(["profile", key, value])
    for section in ["walletTransfers", "polymarketPositions", "committeeMemberships", "safetyCheckins", "orderSummaries"]:
        for row in payload[section]:
            for key, value in row.items():
                writer.writerow([section, key, value])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=me-export.csv"})


@app.post("/me/delete")
def me_delete(
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    key = ensure_idempotency_key(idempotency_key)
    existing = db.query(UserPrivacyDeleteRequest).filter(UserPrivacyDeleteRequest.user_id == user.id, UserPrivacyDeleteRequest.idempotency_key == key).first()
    if existing:
        return {"status": existing.status, "effectiveAt": existing.effective_at.isoformat(), "idempotent": True}
    now = now_utc()
    effective_at = now + timedelta(days=_retention_days())
    req = UserPrivacyDeleteRequest(user_id=user.id, requested_at=now, effective_at=effective_at, status="PENDING", idempotency_key=key)
    db.add(req)
    target = db.get(AppUser, user.id)
    if target:
        _apply_user_anonymization(target)
        db.add(target)
    db.query(AppToken).filter(AppToken.user_id == user.id, AppToken.revoked_at.is_(None)).update({"revoked_at": now}, synchronize_session=False)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="user.delete.requested",
        entity_type="app_user",
        entity_id=user.id,
        event_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={"scope": "user", "reason": "RGPD_DELETE_REQUEST", "effective_at": effective_at.isoformat()},
    )
    db.commit()
    return {"status": req.status, "effectiveAt": req.effective_at.isoformat(), "idempotent": False}


@app.get("/me/delete/status")
def me_delete_status(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(UserPrivacyDeleteRequest).filter(UserPrivacyDeleteRequest.user_id == user.id).order_by(UserPrivacyDeleteRequest.id.desc()).first()
    if not row:
        return {"status": "NONE", "effectiveAt": None}
    return {"status": row.status, "effectiveAt": _serialize_dt(row.effective_at), "requestedAt": _serialize_dt(row.requested_at)}



def _bar_status_from_events(now: datetime, events: list[Event]) -> str | None:
    if not events:
        return None
    for event in events:
        if event.starts_at <= now <= event.ends_at:
            return "LIVE"
    for event in events:
        if event.starts_at > now:
            return "OPEN"
    return "CLOSED"


@app.get("/bars")
def list_bars(limit: int = Query(100, ge=1, le=300), db: Session = Depends(get_db)):
    now = now_utc()
    rows = db.query(Bar).order_by(Bar.id.asc()).limit(limit).all()
    output: list[dict[str, Any]] = []

    for row in rows:
        events = db.query(Event).filter(Event.bar_id == row.id).order_by(Event.starts_at.desc()).limit(8).all()
        last_event = events[0] if events else None
        status = _bar_status_from_events(now, events)
        ticker_line = None
        if last_event is not None:
            ticker_line = f"Last event: {last_event.name}"
            for event in events:
                if event.starts_at <= now <= event.ends_at:
                    ticker_line = f"Live now: {event.name}"
                    break

        output.append(
            {
                "id": row.id,
                "name": row.name,
                "city": row.city,
                "status": status,
                "location": {"city": row.city} if row.city else None,
                "ticker_line": ticker_line,
                "lastEvent": (
                    {
                        "id": last_event.id,
                        "name": last_event.name,
                        "starts_at": last_event.starts_at.isoformat(),
                    }
                    if last_event is not None
                    else None
                ),
            }
        )
    return output


@app.get("/bars/{bar_id}/events")
def list_bar_events(bar_id: int, db: Session = Depends(get_db)):
    bar = db.get(Bar, bar_id)
    if not bar:
        raise HTTPException(404, "Bar not found")
    now = now_utc()
    rows = db.query(Event).filter(Event.bar_id == bar_id).order_by(Event.starts_at.asc()).all()
    output: list[dict[str, Any]] = []
    for row in rows:
        runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == row.id).first()
        modules = db.query(EventModuleConfig).filter(EventModuleConfig.event_id == row.id).first()

        status = "ENDED"
        if row.starts_at <= now <= row.ends_at:
            status = "LIVE"
        elif row.starts_at > now:
            status = "UPCOMING"

        modules_on = None
        if modules is not None:
            modules_on = {
                "orders": bool(modules.orders_enabled),
                "market": bool(modules.market_enabled),
                "battles": bool(modules.battles_enabled),
                "hunt": bool(modules.hunt_enabled),
                "polymarket": bool(modules.polymarket_enabled),
                "entry": bool(modules.entry_enabled),
                "checkins": bool(modules.checkins_enabled),
                "wifi": bool(modules.wifi_enabled),
                "safety": bool(modules.safety_enabled),
            }

        output.append(
            {
                "id": row.id,
                "bar_id": row.bar_id,
                "name": row.name,
                "startAt": row.starts_at.isoformat(),
                "endAt": row.ends_at.isoformat(),
                "starts_at": row.starts_at.isoformat(),
                "ends_at": row.ends_at.isoformat(),
                "status": status,
                "venue": bar.name,
                "shortName": bar.name,
                "eventState": ((runtime.state if runtime else None) or "LIVE").upper(),
                "modulesOn": modules_on,
            }
        )

    return output


def _event_modules_on(db: Session, event_id: int) -> dict[str, bool]:
    event = db.get(Event, event_id)
    event_modules = (event.modules_on or {}) if event else {}
    cfg = db.query(EventModuleConfig).filter(EventModuleConfig.event_id == event_id).first()
    if cfg is None:
        return {
            "menu": True,
            "wallet": True,
            "ticker": True,
            "entry": False,
            "checkin": False,
            "battles": False,
            "hunt": False,
            "report": True,
            "polymarket": False,
            "polymarket_event": False,
            "classement": True,
            "music_vote": False,
            "broadcast": False,
            "map": bool(event_modules.get("map", False)),
        }
    polymarket_enabled = bool(getattr(cfg, "allow_user_bets", getattr(cfg, "polymarket_enabled", False)))
    menu_enabled = bool(getattr(cfg, "menu_enabled", True))
    wallet_enabled = bool(getattr(cfg, "wallet_enabled", True))
    return {
        "menu": menu_enabled,
        "wallet": wallet_enabled,
        "ticker": menu_enabled or wallet_enabled or polymarket_enabled,
        "entry": bool(cfg.entry_enabled),
        "checkin": bool(cfg.checkin_enabled),
        "battles": bool(cfg.battles_enabled),
        "hunt": bool(cfg.hunt_enabled),
        "report": bool(cfg.report_enabled),
        "polymarket": polymarket_enabled,
        "polymarket_event": polymarket_enabled,
        "classement": bool(cfg.report_enabled),
        "music_vote": False,
        "broadcast": False,
        "map": bool(event_modules.get("map", False)),
    }


def _event_state_last_updated(runtime: Optional[EventRuntimeState]) -> Optional[str]:
    if runtime is None or runtime.updated_at is None:
        return None
    return runtime.updated_at.isoformat()


RANKING_RULES_TEXT = (
    "Score v1 = tickets dépensés + (commandes × 10) + (gifts envoyés × 2) + volume bets. "
    "Objectif: valoriser l'activité sans mécanique toxique."
)


def _ranking_masked_name(user_id: str) -> str:
    return f"Anonymous-{hashlib.sha1(user_id.encode('utf-8')).hexdigest()[:6]}"


def _ranking_display_name(*, user_id: str, raw_name: Optional[str], visibility: str, requester_id: str) -> str:
    if user_id == requester_id:
        return (raw_name or "Player").strip() or "Player"
    if visibility == "private":
        return _ranking_masked_name(user_id)
    return (raw_name or "Player").strip() or "Player"


@app.get("/events/{event_id}/ranking")
def event_ranking(
    event_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Event not found")

    if not _event_modules_on(db, event_id).get("classement", False):
        raise HTTPException(status_code=403, detail={"reason": "MODULE_OFF", "message": "Module classement disabled"})

    joined_ids = {
        row[0]
        for row in db.query(EventJoin.user_id)
        .filter(EventJoin.event_id == event_id)
        .all()
        if row[0]
    }
    if not joined_ids:
        joined_ids.add(user.id)

    order_rows = (
        db.query(
            Order.user_id,
            func.count(Order.id).label("orders"),
            func.coalesce(func.sum(Order.total_tickets), 0).label("spent_tickets"),
        )
        .filter(Order.event_id == event_id, Order.user_id.isnot(None))
        .group_by(Order.user_id)
        .all()
    )
    transfer_sent_rows = (
        db.query(
            TicketTransfer.from_user_id,
            func.coalesce(func.sum(TicketTransfer.amount), 0).label("gifts_sent"),
        )
        .filter(TicketTransfer.event_id == event_id)
        .group_by(TicketTransfer.from_user_id)
        .all()
    )
    transfer_received_rows = (
        db.query(
            TicketTransfer.to_user_id,
            func.coalesce(func.sum(TicketTransfer.amount), 0).label("gifts_received"),
        )
        .filter(TicketTransfer.event_id == event_id)
        .group_by(TicketTransfer.to_user_id)
        .all()
    )
    bet_rows = (
        db.query(
            BetPosition.user_id,
            func.coalesce(func.sum(BetPosition.stake_tickets), 0).label("bets_volume"),
        )
        .join(Bet, Bet.id == BetPosition.bet_id)
        .filter(Bet.scope == "EVENT", Bet.event_id == event_id)
        .group_by(BetPosition.user_id)
        .all()
    )

    users_index: dict[str, dict[str, int | str | float]] = {
        user_id: {
            "user_id": user_id,
            "orders": 0,
            "spent_tickets": 0,
            "gifts_sent": 0,
            "gifts_received": 0,
            "bets_volume": 0,
            "score": 0,
        }
        for user_id in joined_ids
    }
    users_index.setdefault(
        user.id,
        {
            "user_id": user.id,
            "orders": 0,
            "spent_tickets": 0,
            "gifts_sent": 0,
            "gifts_received": 0,
            "bets_volume": 0,
            "score": 0,
        },
    )

    for row in order_rows:
        uid = row.user_id
        if not uid:
            continue
        entry = users_index.setdefault(uid, {"user_id": uid, "orders": 0, "spent_tickets": 0, "gifts_sent": 0, "gifts_received": 0, "bets_volume": 0, "score": 0})
        entry["orders"] = int(row.orders or 0)
        entry["spent_tickets"] = int(row.spent_tickets or 0)
    for row in transfer_sent_rows:
        uid = row.from_user_id
        if not uid:
            continue
        entry = users_index.setdefault(uid, {"user_id": uid, "orders": 0, "spent_tickets": 0, "gifts_sent": 0, "gifts_received": 0, "bets_volume": 0, "score": 0})
        entry["gifts_sent"] = int(row.gifts_sent or 0)
    for row in transfer_received_rows:
        uid = row.to_user_id
        if not uid:
            continue
        entry = users_index.setdefault(uid, {"user_id": uid, "orders": 0, "spent_tickets": 0, "gifts_sent": 0, "gifts_received": 0, "bets_volume": 0, "score": 0})
        entry["gifts_received"] = int(row.gifts_received or 0)
    for row in bet_rows:
        uid = row.user_id
        if not uid:
            continue
        entry = users_index.setdefault(uid, {"user_id": uid, "orders": 0, "spent_tickets": 0, "gifts_sent": 0, "gifts_received": 0, "bets_volume": 0, "score": 0})
        entry["bets_volume"] = int(row.bets_volume or 0)

    user_ids = list(users_index.keys())
    users = {
        u.id: u
        for u in db.query(AppUser).filter(AppUser.id.in_(user_ids)).all()
    }
    privacy = {
        p.user_id: (p.visibility or "public")
        for p in db.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id.in_(user_ids)).all()
    }

    ranked_rows: list[dict[str, Any]] = []
    for raw in users_index.values():
        spent_tickets = int(raw["spent_tickets"])
        orders = int(raw["orders"])
        gifts_sent = int(raw["gifts_sent"])
        gifts_received = int(raw["gifts_received"])
        bets_volume = int(raw["bets_volume"])
        score = spent_tickets + (orders * 10) + (gifts_sent * 2) + bets_volume
        raw["score"] = score
        ranked_rows.append(raw)

    ranked_rows.sort(
        key=lambda row: (-int(row["score"]), -int(row["spent_tickets"]), -int(row["orders"]), str(row["user_id"])),
    )

    output_rows: list[dict[str, Any]] = []
    me_row: Optional[dict[str, Any]] = None
    for idx, row in enumerate(ranked_rows, start=1):
        uid = str(row["user_id"])
        profile = users.get(uid)
        display_name = _ranking_display_name(
            user_id=uid,
            raw_name=profile.display_name if profile else None,
            visibility=(privacy.get(uid) or "public").lower(),
            requester_id=user.id,
        )
        payload = {
            "rank": idx,
            "displayName": display_name,
            "score": int(row["score"]),
            "stats": {
                "orders": int(row["orders"]),
                "spentTickets": int(row["spent_tickets"]),
                "giftsSent": int(row["gifts_sent"]),
                "giftsReceived": int(row["gifts_received"]),
                "bets": int(row["bets_volume"]),
            },
        }
        output_rows.append(payload)
        if uid == user.id:
            me_row = dict(payload)

    if me_row is None:
        me_row = {
            "rank": len(output_rows) + 1,
            "displayName": (user.display_name or "Player"),
            "score": 0,
            "stats": {"orders": 0, "spentTickets": 0, "giftsSent": 0, "giftsReceived": 0, "bets": 0},
        }

    top3 = output_rows[:3]
    for entry in top3:
        entry["badges"] = ["Top 3"]

    return {
        "eventId": event_id,
        "updatedAt": now_utc().isoformat(),
        "rulesText": RANKING_RULES_TEXT,
        "top3": top3,
        "list": output_rows[:200],
        "me": me_row,
    }


def _event_join_payload(db: Session, event: Event) -> dict[str, Any]:
    runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event.id).first()
    bar_name = None
    if event.bar_id is not None:
        bar = db.get(Bar, event.bar_id)
        bar_name = bar.name if bar else None
    return {
        "event": {
            "id": event.id,
            "bar_id": event.bar_id,
            "name": event.name,
            "starts_at": event.starts_at.isoformat(),
            "ends_at": event.ends_at.isoformat(),
            "venue": bar_name,
            "event_code": event.event_code,
        },
        "modulesOn": _event_modules_on(db, event.id),
        "eventState": ((runtime.state if runtime else None) or "LIVE").upper(),
        "lastUpdatedAt": _event_state_last_updated(runtime),
        "lastStateUpdatedAt": _event_state_last_updated(runtime),
        "flags": {
            "charterEnabled": bool(event.charter_enabled),
            "charterVersion": event.charter_version,
        },
    }


@app.get("/events/{event_id}/context")
def get_event_context(
    event_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event.id).first()
    payload = _event_join_payload(db, event)
    user_id: Optional[str] = None
    if authorization:
        token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization.strip()
        user_id = decode_user_token(token)
    can_manage_bets = False
    can_admin_music = False
    can_dj_music = False
    if user_id:
        staff = db.query(EventStaff).filter(EventStaff.event_id == event_id, EventStaff.user_id == user_id, EventStaff.is_active.is_(True)).first()
        role = (staff.role or "").lower() if staff else ""
        can_manage_bets = bool(role == "admin")
        can_admin_music = bool(role in {"admin", "manager", "owner"})
        can_dj_music = bool(role == "dj")
    payload["permissions"] = {
        "canCreateBets": can_manage_bets,
        "canResolveBets": can_manage_bets,
        "canAdminMusic": can_admin_music,
        "canDjMusic": can_dj_music,
    }
    payload["lastUpdatedAt"] = _event_state_last_updated(runtime)
    payload["lastStateUpdatedAt"] = _event_state_last_updated(runtime)
    return payload


@app.get("/events/{event_id}/state")
def get_event_state(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event.id).first()
    return {
        "eventId": event_id,
        "eventState": ((runtime.state if runtime else None) or "LIVE").upper(),
        "lastUpdatedAt": _event_state_last_updated(runtime),
        "lastStateUpdatedAt": _event_state_last_updated(runtime),
    }


def _ensure_event_join_allowed(db: Session, event: Event) -> None:
    runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event.id).first()
    runtime_state = ((runtime.state if runtime else None) or "LIVE").upper()
    if runtime_state in {"CLOSED", "FROZEN"}:
        raise HTTPException(status_code=403, detail={"reason": runtime_state.lower(), "message": "join_not_allowed"})


def _apply_event_join(
    db: Session,
    *,
    event: Event,
    user: AppUser,
    idempotency_key: str,
    accepted_charter_version: Optional[str],
) -> dict[str, Any]:
    _ensure_event_join_allowed(db, event)

    accepted_version = accepted_charter_version
    wrote = False
    if event.charter_enabled:
        if not event.charter_version:
            raise HTTPException(status_code=409, detail={"reason": "charter_version_missing"})
        acceptance = db.query(EventCharterAcceptance).filter(
            EventCharterAcceptance.event_id == event.id,
            EventCharterAcceptance.user_id == user.id,
            EventCharterAcceptance.charter_version == event.charter_version,
        ).first()
        if acceptance is None and accepted_charter_version != event.charter_version:
            raise HTTPException(
                status_code=403,
                detail={
                    "reason": "charter_acceptance_required",
                    "event_id": event.id,
                    "charter_version": event.charter_version,
                },
            )
        if acceptance is None:
            db.add(
                EventCharterAcceptance(
                    event_id=event.id,
                    user_id=user.id,
                    charter_version=event.charter_version,
                    accepted_at=now_utc(),
                )
            )
            wrote = True
        accepted_version = event.charter_version

    existing = db.query(EventJoin).filter(EventJoin.event_id == event.id, EventJoin.user_id == user.id).first()
    if existing is None:
        join = EventJoin(
            event_id=event.id,
            user_id=user.id,
            device_id=None,
            idempotency_key=idempotency_key,
            joined_at=now_utc(),
            accepted_charter_version=accepted_version,
        )
        db.add(join)
        wrote = True
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            wrote = False
    else:
        if existing.accepted_charter_version is None and accepted_version is not None:
            existing.accepted_charter_version = accepted_version
            db.add(existing)
            db.commit()
            wrote = True

    if wrote:
        write_audit_log(
            db,
            actor_partner_id=None,
            actor_user_id=user.id,
            actor_role="app_user",
            action="event.join",
            entity_type="event_join",
            entity_id=f"{event.id}:{user.id}",
            event_id=event.id,
            bar_id=event.bar_id,
            idempotency_key=idempotency_key,
            payload={"accepted_charter_version": accepted_version},
        )
        db.commit()

    return _event_join_payload(db, event)


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
            "event_code": e.event_code,
            "charter_enabled": e.charter_enabled,
            "charter_version": e.charter_version,
        }
    finally:
        s.close()


@app.get("/events/{event_id}/charter", response_model=EventCharterOut)
def get_event_charter(
    event_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    return {
        "event_id": event_id,
        "enabled": bool(event.charter_enabled),
        "version": event.charter_version,
        "text": event.charter_text,
    }


@app.post("/events/{event_id}/join")
def join_event(
    event_id: int,
    payload: JoinEventIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    key = ensure_idempotency_key(idempotency_key)
    return _apply_event_join(
        db,
        event=event,
        user=user,
        idempotency_key=key,
        accepted_charter_version=payload.accepted_charter_version,
    )


@app.post("/events/join_by_code")
def join_event_by_code(
    payload: JoinByCodeIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    code = payload.code.strip().upper()
    event = db.query(Event).filter(Event.event_code == code).first()
    if event is None:
        raise HTTPException(404, detail={"reason": "invalid_code"})
    key = ensure_idempotency_key(idempotency_key)
    return _apply_event_join(
        db,
        event=event,
        user=user,
        idempotency_key=key,
        accepted_charter_version=payload.accepted_charter_version,
    )




def _committee_module_enabled() -> bool:
    return _env_bool("TORE_MODULE_COMMITTEE_OS", default=True)


def _require_committee_module() -> None:
    if not _committee_module_enabled():
        raise HTTPException(status_code=404, detail={"reason": "module_off"})


def _committee_default_permissions(role: str) -> dict[str, bool]:
    role_norm = (role or "MEMBER").upper()
    mapping = {
        "OWNER": {
            "can_manage_members": True,
            "can_post_forum": True,
            "can_manage_finances": True,
            "can_manage_bapteme": True,
        },
        "ADMIN": {
            "can_manage_members": True,
            "can_post_forum": True,
            "can_manage_finances": True,
            "can_manage_bapteme": True,
        },
        "MOD": {
            "can_manage_members": False,
            "can_post_forum": True,
            "can_manage_finances": False,
            "can_manage_bapteme": False,
        },
        "MEMBER": {
            "can_manage_members": False,
            "can_post_forum": True,
            "can_manage_finances": False,
            "can_manage_bapteme": False,
        },
    }
    return mapping.get(role_norm, mapping["MEMBER"])


def _committee_permissions(db: Session, committee_id: int, role: str) -> dict[str, bool]:
    custom = db.query(CommitteeRolePermission).filter(
        CommitteeRolePermission.committee_id == committee_id,
        CommitteeRolePermission.role == role.upper(),
    ).first()
    if custom:
        return {
            "can_manage_members": bool(custom.permissions_json.get("can_manage_members")),
            "can_post_forum": bool(custom.permissions_json.get("can_post_forum")),
            "can_manage_finances": bool(custom.permissions_json.get("can_manage_finances")),
            "can_manage_bapteme": bool(custom.permissions_json.get("can_manage_bapteme")),
        }
    return _committee_default_permissions(role)


def _committee_active_year(db: Session, committee_id: int) -> Optional[CommitteeYear]:
    return db.query(CommitteeYear).filter(
        CommitteeYear.committee_id == committee_id,
        CommitteeYear.is_active.is_(True),
    ).order_by(CommitteeYear.id.desc()).first()


def _committee_membership(db: Session, committee_id: int, user_id: str) -> Optional[CommitteeMembership]:
    return db.query(CommitteeMembership).filter(
        CommitteeMembership.committee_id == committee_id,
        CommitteeMembership.user_id == user_id,
        CommitteeMembership.is_active.is_(True),
    ).first()


def _committee_me_payload(db: Session, committee_id: int, user: AppUser) -> dict[str, Any]:
    membership = _committee_membership(db, committee_id, user.id)
    active_year = _committee_active_year(db, committee_id)
    if membership is None:
        return {
            "committeeId": committee_id,
            "isMember": False,
            "membership": None,
            "permissions": _committee_default_permissions("MEMBER"),
            "canManageFinances": False,
            "canManageBapteme": False,
            "activeYear": active_year.year_label if active_year else None,
        }
    return {
        "committeeId": committee_id,
        "isMember": True,
        "membership": {
            "userId": membership.user_id,
            "role": membership.role,
            "joinedAt": membership.joined_at.isoformat(),
            "isActive": bool(membership.is_active),
        },
        "permissions": _committee_permissions(db, committee_id, membership.role),
        "canManageFinances": bool(_committee_permissions(db, committee_id, membership.role).get("can_manage_finances", False)),
        "canManageBapteme": bool(_committee_permissions(db, committee_id, membership.role).get("can_manage_bapteme", False)),
        "activeYear": active_year.year_label if active_year else None,
    }


def _require_committee_admin(db: Session, committee_id: int, user: AppUser) -> CommitteeMembership:
    membership = _committee_membership(db, committee_id, user.id)
    if membership is None:
        raise HTTPException(status_code=403, detail={"reason": "not_member"})
    perms = _committee_permissions(db, committee_id, membership.role)
    if not perms.get("can_manage_members", False):
        raise HTTPException(status_code=403, detail={"reason": "forbidden"})
    return membership


def _require_committee_member(db: Session, committee_id: int, user: AppUser) -> CommitteeMembership:
    membership = _committee_membership(db, committee_id, user.id)
    if membership is None:
        raise HTTPException(status_code=403, detail={"reason": "not_member"})
    return membership


def _require_idempotency(idempotency_key: Optional[str]) -> str:
    return ensure_idempotency_key(idempotency_key)


def _require_committee_finance_manager(db: Session, committee_id: int, user: AppUser) -> CommitteeMembership:
    membership = _committee_membership(db, committee_id, user.id)
    if membership is None:
        raise HTTPException(status_code=403, detail={"reason": "not_member"})
    perms = _committee_permissions(db, committee_id, membership.role)
    if not perms.get("can_manage_finances", False):
        raise HTTPException(status_code=403, detail={"reason": "forbidden"})
    return membership


def _require_committee_bapteme_manager(db: Session, committee_id: int, user: AppUser) -> CommitteeMembership:
    membership = _committee_membership(db, committee_id, user.id)
    if membership is None:
        raise HTTPException(status_code=403, detail={"reason": "not_member"})
    perms = _committee_permissions(db, committee_id, membership.role)
    if not perms.get("can_manage_bapteme", False):
        raise HTTPException(status_code=403, detail={"reason": "forbidden"})
    return membership


def _committee_year_or_404(db: Session, committee_id: int, year_id: int) -> CommitteeYear:
    year = db.get(CommitteeYear, year_id)
    if year is None or year.committee_id != committee_id:
        raise HTTPException(status_code=404, detail={"reason": "year_not_found"})
    return year


def _ledger_payload(row: CommitteeLedgerEntry) -> dict[str, Any]:
    return {
        "id": row.id,
        "committeeId": row.committee_id,
        "yearId": row.year_id,
        "type": row.entry_type,
        "amountCents": row.amount_cents,
        "currency": row.currency,
        "category": row.category,
        "occurredAt": row.occurred_at,
        "note": row.note,
        "attachmentUrl": row.attachment_url,
        "createdBy": row.created_by,
        "createdAt": row.created_at.isoformat(),
    }


def _forum_year_or_404(db: Session, committee_id: int, year_id: int) -> CommitteeYear:
    year = db.get(CommitteeYear, year_id)
    if year is None or year.committee_id != committee_id:
        raise HTTPException(status_code=404, detail={"reason": "year_not_found"})
    return year


def _forum_category_or_404(db: Session, committee_id: int, year_id: int, category_id: int) -> CommitteeForumCategory:
    category = db.get(CommitteeForumCategory, category_id)
    if category is None or category.committee_id != committee_id or category.year_id != year_id:
        raise HTTPException(status_code=404, detail={"reason": "category_not_found"})
    return category


def _forum_require_mod_or_admin(db: Session, committee_id: int, membership: CommitteeMembership) -> None:
    role = (membership.role or "MEMBER").upper()
    if role not in {"MOD", "ADMIN", "OWNER"}:
        raise HTTPException(status_code=403, detail={"reason": "forbidden"})


def _forum_require_admin_or_owner(membership: CommitteeMembership) -> None:
    if (membership.role or "MEMBER").upper() not in {"ADMIN", "OWNER"}:
        raise HTTPException(status_code=403, detail={"reason": "forbidden"})


def _forum_slug(value: str) -> str:
    return "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())[:120] or "category"


def _forum_post_payload(db: Session, row: CommitteeForumPost) -> dict[str, Any]:
    user = db.get(AppUser, row.created_by_user_id)
    return {
        "id": row.id,
        "committeeId": row.committee_id,
        "yearId": row.year_id,
        "categoryId": row.category_id,
        "title": row.title,
        "body": row.body,
        "createdByUserId": row.created_by_user_id,
        "createdByDisplayName": user.display_name if user else row.created_by_user_id,
        "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
        "isPinned": bool(row.is_pinned),
        "isLocked": bool(row.is_locked),
    }


def _folklore_glossary_module_enabled() -> bool:
    return _env_bool("TORE_MODULE_FOLKLORE_GLOSSARY", default=True)


def _require_folklore_glossary_module() -> None:
    if not _folklore_glossary_module_enabled():
        raise HTTPException(status_code=404, detail={"reason": "MODULE_OFF"})


def _committee_can_moderate_glossary(db: Session, committee_id: int, membership: CommitteeMembership) -> bool:
    role = (membership.role or "MEMBER").upper()
    if role in {"ADMIN", "MOD", "OWNER"}:
        return True
    perms = _committee_permissions(db, committee_id, membership.role)
    return bool(perms.get("canModerateForum"))


def _require_glossary_write_access(db: Session, committee_id: int, user: AppUser) -> CommitteeMembership:
    membership = _require_committee_member(db, committee_id, user)
    if not _committee_can_moderate_glossary(db, committee_id, membership):
        raise HTTPException(status_code=403, detail={"reason": "forbidden"})
    return membership


def _sanitize_glossary_tags(tags: Optional[List[str]]) -> List[str]:
    if not tags:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        val = (raw or "").strip()
        if not val:
            continue
        lowered = val.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(val[:40])
    return out[:25]


def _committee_glossary_settings(db: Session, committee_id: int) -> CommitteeGlossarySettings:
    row = db.query(CommitteeGlossarySettings).filter(CommitteeGlossarySettings.committee_id == committee_id).first()
    if row is None:
        row = CommitteeGlossarySettings(committee_id=committee_id, public_enabled=False, updated_at=now_utc(), updated_by="system")
        db.add(row)
        db.flush()
    return row


def _glossary_term_payload(row: CommitteeGlossaryTerm) -> dict[str, Any]:
    return {
        "id": row.id,
        "committeeId": row.committee_id,
        "yearId": row.year_id,
        "term": row.term,
        "definition": row.definition,
        "examples": row.examples,
        "tags": list(row.tags_json or []),
        "isOfficial": bool(row.is_official),
        "status": row.status,
        "source": {"type": "committee", "yearId": row.year_id},
        "createdAt": row.created_at.isoformat(),
        "createdBy": row.created_by,
        "updatedAt": row.updated_at.isoformat(),
        "updatedBy": row.updated_by,
    }


_glossary_rl_lock = threading.Lock()
_glossary_rl_store: dict[str, deque[float]] = defaultdict(deque)


def _enforce_glossary_write_rate_limit(committee_id: int, actor_user_id: str) -> None:
    now = time.monotonic()
    key = f"{committee_id}:{actor_user_id}"
    window_s = 600
    with _glossary_rl_lock:
        q = _glossary_rl_store[key]
        threshold = now - window_s
        while q and q[0] < threshold:
            q.popleft()
        if len(q) >= 10:
            raise HTTPException(status_code=429, detail={"reason": "rate_limited", "message": "Too many writes"})
        q.append(now)


def _glossary_filters(tags: Optional[str]) -> list[str]:
    if not tags:
        return []
    return [item.strip().lower() for item in tags.split(",") if item.strip()]


def _list_glossary_terms(
    db: Session,
    committee_id: int,
    query: Optional[str],
    tags: Optional[str],
    year: Optional[int],
    cursor: Optional[str],
    limit: int,
    include_archived: bool,
    include_deleted: bool,
) -> dict[str, Any]:
    q = db.query(CommitteeGlossaryTerm).filter(CommitteeGlossaryTerm.committee_id == committee_id)
    statuses = ["ACTIVE"]
    if include_archived:
        statuses.append("ARCHIVED")
    if include_deleted:
        statuses.append("DELETED")
    q = q.filter(CommitteeGlossaryTerm.status.in_(statuses))
    if year is not None:
        q = q.filter(CommitteeGlossaryTerm.year_id == year)
    if query:
        search = f"%{query.strip().lower()}%"
        q = q.filter(func.lower(CommitteeGlossaryTerm.term).like(search) | func.lower(CommitteeGlossaryTerm.definition).like(search))

    after_id = None
    if cursor:
        try:
            after_id = int(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail={"reason": "invalid_cursor"})
    if after_id is not None:
        q = q.filter(CommitteeGlossaryTerm.id > after_id)

    rows = q.order_by(CommitteeGlossaryTerm.id.asc()).limit(limit + 1).all()
    filtered_tags = _glossary_filters(tags)
    items = [_glossary_term_payload(row) for row in rows]
    if filtered_tags:
        items = [it for it in items if filtered_tags and set(filtered_tags).issubset({str(tag).lower() for tag in it.get("tags", [])})]
    has_more = len(items) > limit
    clipped = items[:limit]
    next_cursor = str(clipped[-1]["id"]) if has_more and clipped else None
    return {"items": clipped, "nextCursor": next_cursor, "serverTime": now_utc().isoformat()}


@app.get("/modules")
def app_modules_state(db: Session = Depends(get_db)):
    state = {"committee_os": _committee_module_enabled(), "folklore_glossary": _folklore_glossary_module_enabled()}
    flags = db.query(GlobalFeatureFlag).all()
    for flag in flags:
        if flag.key in state:
            state[flag.key] = bool(flag.enabled)
    return state


@app.get("/admin/audit")
def admin_audit(
    actor: Optional[str] = Query(default=None),
    user: Optional[str] = Query(default=None),
    event: Optional[int] = Query(default=None),
    committee: Optional[int] = Query(default=None),
    since: Optional[str] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_global_admin(identity)
    q = db.query(AuditLog)
    if actor:
        if actor.isdigit():
            q = q.filter((AuditLog.actor_user_id == actor) | (AuditLog.actor_partner_id == int(actor)))
        else:
            q = q.filter(AuditLog.actor_user_id == actor)
    if user:
        q = q.filter((AuditLog.actor_user_id == user) | (AuditLog.entity_id == user))
    if event is not None:
        q = q.filter(AuditLog.event_id == event)
    if committee is not None:
        q = q.filter(AuditLog.committee_id == committee)
    if since:
        try:
            q = q.filter(AuditLog.ts >= datetime.fromisoformat(since.replace("Z", "+00:00")))
        except ValueError:
            raise HTTPException(status_code=400, detail={"reason": "invalid_since"})
    if cursor:
        try:
            q = q.filter(AuditLog.id < int(cursor))
        except ValueError:
            raise HTTPException(status_code=400, detail={"reason": "invalid_cursor"})
    rows = q.order_by(AuditLog.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    clipped = rows[:limit]
    next_cursor = str(clipped[-1].id) if has_more and clipped else None
    return {
        "items": [
            {
                "id": row.id,
                "ts": row.ts.isoformat(),
                "actorUserId": row.actor_user_id,
                "actorPartnerId": row.actor_partner_id,
                "actorRole": row.actor_role,
                "action": row.action,
                "entityType": row.entity_type,
                "entityId": row.entity_id,
                "eventId": row.event_id,
                "committeeId": row.committee_id,
                "idempotencyKey": row.idempotency_key,
                "payload": row.payload_json,
            }
            for row in clipped
        ],
        "nextCursor": next_cursor,
    }


@app.get("/admin/users")
def admin_users(query: Optional[str] = Query(default=None), cursor: Optional[str] = Query(default=None), limit: int = Query(default=30, ge=1, le=100), identity=Depends(current_partner_identity), db: Session = Depends(get_db)):
    _require_global_admin(identity)
    q = db.query(AppUser)
    if query:
        like = f"%{query.strip().lower()}%"
        q = q.filter((func.lower(AppUser.id).like(like)) | (func.lower(AppUser.display_name).like(like)))
    if cursor:
        q = q.filter(AppUser.id > cursor)
    rows = q.order_by(AppUser.id.asc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    clipped = rows[:limit]
    return {
        "items": [{"id": row.id, "displayName": row.display_name, "isDeleted": bool(row.is_deleted), "createdAt": _serialize_dt(row.created_at)} for row in clipped],
        "nextCursor": (clipped[-1].id if has_more and clipped else None),
    }


@app.get("/admin/users/{user_id}/sanctions")
def admin_user_sanctions(user_id: str, identity=Depends(current_partner_identity), db: Session = Depends(get_db)):
    _require_global_admin(identity)
    rows = db.query(UserSanction).filter(UserSanction.user_id == user_id).order_by(UserSanction.id.desc()).all()
    return {"items": [{"id": row.id, "type": row.type, "status": row.status, "reason": row.reason, "startsAt": _serialize_dt(row.starts_at), "endsAt": _serialize_dt(row.ends_at), "createdAt": _serialize_dt(row.created_at), "revokedAt": _serialize_dt(row.revoked_at)} for row in rows]}


@app.post("/admin/users/{user_id}/sanctions")
def admin_create_sanction(user_id: str, payload: AdminSanctionIn, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"), identity=Depends(current_partner_identity), db: Session = Depends(get_db)):
    _require_global_admin(identity)
    key = ensure_idempotency_key(idempotency_key)
    existing = db.query(UserSanction).filter(UserSanction.user_id == user_id, UserSanction.reason == payload.reason, UserSanction.created_by == identity["user_id"], UserSanction.status == "ACTIVE").order_by(UserSanction.id.desc()).first()
    if existing and existing.type == payload.type:
        return {"id": existing.id, "type": existing.type, "status": existing.status, "idempotent": True}
    now = now_utc()
    ends_at = None
    if payload.type == "SUSPEND":
        hours = payload.durationHours or 24
        ends_at = now + timedelta(hours=hours)
    sanction = UserSanction(user_id=user_id, status="ACTIVE", type=payload.type, starts_at=now, ends_at=ends_at, reason=payload.reason, created_by=identity["user_id"])
    db.add(sanction)
    write_audit_log(db, actor_partner_id=identity["user_id"], actor_role=identity.get("role"), actor_user_id=user_id, action="admin.sanction.create", entity_type="user_sanction", entity_id=None, event_id=None, committee_id=None, bar_id=identity.get("bar_id"), idempotency_key=key, payload={"scope": "global_admin", "reason": payload.reason, "type": payload.type, "durationHours": payload.durationHours})
    db.commit()
    db.refresh(sanction)
    return {"id": sanction.id, "type": sanction.type, "status": sanction.status, "endsAt": _serialize_dt(sanction.ends_at), "idempotent": False}


@app.post("/admin/users/{user_id}/sanctions/{sanction_id}/revoke")
def admin_revoke_sanction(user_id: str, sanction_id: int, payload: AdminSanctionRevokeIn, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"), identity=Depends(current_partner_identity), db: Session = Depends(get_db)):
    _require_global_admin(identity)
    key = ensure_idempotency_key(idempotency_key)
    sanction = db.query(UserSanction).filter(UserSanction.id == sanction_id, UserSanction.user_id == user_id).first()
    if not sanction:
        raise HTTPException(status_code=404, detail="Sanction not found")
    if sanction.status == "REVOKED":
        return {"status": sanction.status, "idempotent": True}
    sanction.status = "REVOKED"
    sanction.revoked_by = identity["user_id"]
    sanction.revoked_at = now_utc()
    db.add(sanction)
    write_audit_log(db, actor_partner_id=identity["user_id"], actor_role=identity.get("role"), actor_user_id=user_id, action="admin.sanction.revoke", entity_type="user_sanction", entity_id=str(sanction.id), event_id=None, committee_id=None, bar_id=identity.get("bar_id"), idempotency_key=key, payload={"scope": "global_admin", "reason": payload.reason})
    db.commit()
    return {"status": sanction.status, "idempotent": False}


@app.post("/admin/events/{event_id}/freeze")
def admin_freeze_event(event_id: int, payload: AdminFreezeEventIn, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"), identity=Depends(current_partner_identity), db: Session = Depends(get_db)):
    _require_global_admin(identity)
    key = ensure_idempotency_key(idempotency_key)
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).first()
    if not runtime:
        runtime = EventRuntimeState(event_id=event_id)
    runtime.state = "FROZEN"
    runtime.reason = payload.reason
    runtime.updated_at = now_utc()
    runtime.updated_by_user_id = identity["user_id"]
    db.add(runtime)
    write_audit_log(db, actor_partner_id=identity["user_id"], actor_role=identity.get("role"), actor_user_id=None, action="admin.event.freeze", entity_type="event", entity_id=str(event_id), event_id=event_id, committee_id=None, bar_id=event.bar_id, idempotency_key=key, payload={"scope": "global_admin", "reason": payload.reason})
    db.commit()
    return {"status": runtime.state, "reason": runtime.reason}


@app.get("/admin/flags")
def admin_flags(identity=Depends(current_partner_identity), db: Session = Depends(get_db)):
    _require_global_admin(identity)
    rows = db.query(GlobalFeatureFlag).order_by(GlobalFeatureFlag.key.asc()).all()
    return {"items": [{"key": row.key, "enabled": row.enabled, "reason": row.reason, "updatedAt": _serialize_dt(row.updated_at)} for row in rows]}


@app.put("/admin/flags")
def admin_flags_update(payload: AdminFlagUpdateIn, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"), identity=Depends(current_partner_identity), db: Session = Depends(get_db)):
    _require_global_admin(identity)
    key = ensure_idempotency_key(idempotency_key)
    row = db.get(GlobalFeatureFlag, payload.key)
    if not row:
        row = GlobalFeatureFlag(key=payload.key)
    row.enabled = payload.enabled
    row.reason = payload.reason
    row.updated_at = now_utc()
    row.updated_by = identity["user_id"]
    db.add(row)
    write_audit_log(db, actor_partner_id=identity["user_id"], actor_role=identity.get("role"), actor_user_id=None, action="admin.flag.update", entity_type="global_feature_flag", entity_id=payload.key, event_id=None, committee_id=None, bar_id=identity.get("bar_id"), idempotency_key=key, payload={"scope": "global_admin", "reason": payload.reason, "enabled": payload.enabled})
    db.commit()
    return {"key": row.key, "enabled": row.enabled, "reason": row.reason}


@app.post("/admin/purge/run")
def admin_purge_run(idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"), identity=Depends(current_partner_identity), db: Session = Depends(get_db)):
    _require_global_admin(identity)
    key = ensure_idempotency_key(idempotency_key)
    now = now_utc()
    rows = db.query(UserPrivacyDeleteRequest).filter(UserPrivacyDeleteRequest.status == "PENDING", UserPrivacyDeleteRequest.effective_at < now).all()
    purged = 0
    for req in rows:
        user = db.get(AppUser, req.user_id)
        if user:
            _apply_user_anonymization(user)
            db.add(user)
            db.query(AppToken).filter(AppToken.user_id == user.id, AppToken.revoked_at.is_(None)).update({"revoked_at": now}, synchronize_session=False)
        req.status = "DONE"
        db.add(req)
        purged += 1
    write_audit_log(db, actor_partner_id=identity["user_id"], actor_role=identity.get("role"), actor_user_id=None, action="admin.purge.run", entity_type="privacy_delete", entity_id=None, event_id=None, committee_id=None, bar_id=identity.get("bar_id"), idempotency_key=key, payload={"scope": "global_admin", "reason": "RETENTION_PURGE", "purgedCount": purged})
    db.commit()
    return {"purgedCount": purged}


@app.get("/committees")
def committees_list(db: Session = Depends(get_db)):
    _require_committee_module()
    rows = db.query(Committee).order_by(Committee.name.asc()).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "slug": row.slug,
            "descriptionPublic": row.description_public,
            "logoUrl": row.logo_url,
            "createdAt": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.get("/committees/{committee_id}")
def committees_get(committee_id: int, db: Session = Depends(get_db)):
    _require_committee_module()
    row = db.get(Committee, committee_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Committee not found")
    active_year = _committee_active_year(db, committee_id)
    return {
        "id": row.id,
        "name": row.name,
        "slug": row.slug,
        "descriptionPublic": row.description_public,
        "logoUrl": row.logo_url,
        "createdAt": row.created_at.isoformat(),
        "activeYear": active_year.year_label if active_year else None,
    }


@app.get("/committees/{committee_id}/years")
def committees_years(committee_id: int, db: Session = Depends(get_db)):
    _require_committee_module()
    committee = db.get(Committee, committee_id)
    if committee is None:
        raise HTTPException(status_code=404, detail="Committee not found")
    rows = db.query(CommitteeYear).filter(CommitteeYear.committee_id == committee_id).order_by(CommitteeYear.year_label.desc()).all()
    return [
        {
            "id": row.id,
            "committeeId": row.committee_id,
            "yearLabel": row.year_label,
            "isActive": bool(row.is_active),
            "createdAt": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.post("/committees/{committee_id}/join_by_code")
def committees_join_by_code(
    committee_id: int,
    payload: CommitteeJoinByCodeIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency-Key required"})
    enforce_rate_limit("committee_join", f"{committee_id}:{user.id}")
    committee = db.get(Committee, committee_id)
    if committee is None:
        raise HTTPException(status_code=404, detail="Committee not found")

    idem = db.query(CommitteeAdminIdempotency).filter(
        CommitteeAdminIdempotency.committee_id == committee_id,
        CommitteeAdminIdempotency.action == "join_by_code",
        CommitteeAdminIdempotency.idempotency_key == idempotency_key,
    ).first()
    if idem is not None:
        return idem.response_json

    code = payload.code.strip().upper()
    invite = db.query(CommitteeInviteCode).filter(
        CommitteeInviteCode.committee_id == committee_id,
        CommitteeInviteCode.code == code,
    ).first()
    now = now_utc()
    if invite is None or (invite.expires_at is not None and invite.expires_at < now) or (invite.uses_left is not None and invite.uses_left <= 0):
        raise HTTPException(status_code=404, detail={"reason": "invalid_code"})

    membership = db.query(CommitteeMembership).filter(
        CommitteeMembership.committee_id == committee_id,
        CommitteeMembership.user_id == user.id,
    ).first()
    if membership is None:
        membership = CommitteeMembership(
            committee_id=committee_id,
            user_id=user.id,
            role="MEMBER",
            joined_at=now,
            is_active=True,
        )
        db.add(membership)
    else:
        membership.is_active = True
        if not membership.role:
            membership.role = "MEMBER"

    if invite.uses_left is not None:
        invite.uses_left = max(0, invite.uses_left - 1)

    db.flush()
    response = _committee_me_payload(db, committee_id, user)
    db.add(CommitteeAdminIdempotency(
        committee_id=committee_id,
        action="join_by_code",
        idempotency_key=idempotency_key,
        response_json=response,
    ))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_role="app_user",
        action="committee.join_by_code",
        entity_type="committee_membership",
        entity_id=f"{committee_id}:{user.id}",
        event_id=None,
        bar_id=None,
        payload={"committee_id": committee_id, "user_id": user.id, "code": code},
    )
    db.commit()
    return response


@app.get("/committees/{committee_id}/me")
def committees_me(
    committee_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    committee = db.get(Committee, committee_id)
    if committee is None:
        raise HTTPException(status_code=404, detail="Committee not found")
    return _committee_me_payload(db, committee_id, user)


@app.get("/committees/{committee_id}/members")
def committees_members(
    committee_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    committee = db.get(Committee, committee_id)
    if committee is None:
        raise HTTPException(status_code=404, detail="Committee not found")
    _require_committee_admin(db, committee_id, user)
    rows = db.query(CommitteeMembership).filter(
        CommitteeMembership.committee_id == committee_id,
        CommitteeMembership.is_active.is_(True),
    ).order_by(CommitteeMembership.joined_at.asc()).all()
    return {
        "items": [
            {
                "userId": row.user_id,
                "role": row.role,
                "joinedAt": row.joined_at.isoformat(),
                "isActive": bool(row.is_active),
            }
            for row in rows
        ]
    }


@app.post("/committees/{committee_id}/invite_codes")
def committees_invite_codes(
    committee_id: int,
    payload: CommitteeInviteCodeIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency-Key required"})
    committee = db.get(Committee, committee_id)
    if committee is None:
        raise HTTPException(status_code=404, detail="Committee not found")
    admin = _require_committee_admin(db, committee_id, user)

    idem = db.query(CommitteeAdminIdempotency).filter(
        CommitteeAdminIdempotency.committee_id == committee_id,
        CommitteeAdminIdempotency.action == "invite_code_create",
        CommitteeAdminIdempotency.idempotency_key == idempotency_key,
    ).first()
    if idem is not None:
        return idem.response_json

    code = random_code(8)
    invite = CommitteeInviteCode(
        committee_id=committee_id,
        code=code,
        expires_at=payload.expiresAt,
        created_by=user.id,
        uses_left=payload.usesLeft,
    )
    db.add(invite)
    response = {
        "committeeId": committee_id,
        "code": code,
        "expiresAt": payload.expiresAt.isoformat() if payload.expiresAt else None,
        "usesLeft": payload.usesLeft,
    }
    db.add(CommitteeAdminIdempotency(
        committee_id=committee_id,
        action="invite_code_create",
        idempotency_key=idempotency_key,
        response_json=response,
    ))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_role=admin.role,
        action="committee.invite_code.create",
        entity_type="committee_invite_code",
        entity_id=f"{committee_id}:{code}",
        event_id=None,
        bar_id=None,
        payload={"committee_id": committee_id, "expires_at": response["expiresAt"], "uses_left": payload.usesLeft},
    )
    db.commit()
    return response


@app.post("/committees/{committee_id}/members/{user_id}/role")
def committees_set_member_role(
    committee_id: int,
    user_id: str,
    payload: CommitteeSetRoleIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency-Key required"})
    committee = db.get(Committee, committee_id)
    if committee is None:
        raise HTTPException(status_code=404, detail="Committee not found")
    admin = _require_committee_admin(db, committee_id, user)

    idem = db.query(CommitteeAdminIdempotency).filter(
        CommitteeAdminIdempotency.committee_id == committee_id,
        CommitteeAdminIdempotency.action == "member_role_set",
        CommitteeAdminIdempotency.idempotency_key == idempotency_key,
    ).first()
    if idem is not None:
        return idem.response_json

    membership = db.query(CommitteeMembership).filter(
        CommitteeMembership.committee_id == committee_id,
        CommitteeMembership.user_id == user_id,
    ).first()
    if membership is None:
        raise HTTPException(status_code=404, detail={"reason": "member_not_found"})
    membership.role = payload.role
    membership.is_active = True
    response = {"committeeId": committee_id, "userId": user_id, "role": payload.role, "isActive": True}

    db.add(CommitteeAdminIdempotency(
        committee_id=committee_id,
        action="member_role_set",
        idempotency_key=idempotency_key,
        response_json=response,
    ))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_role=admin.role,
        action="committee.member.role_set",
        entity_type="committee_membership",
        entity_id=f"{committee_id}:{user_id}",
        event_id=None,
        bar_id=None,
        payload={"committee_id": committee_id, "user_id": user_id, "role": payload.role, "reason": payload.reason},
    )
    db.commit()
    return response


@app.post("/committees/{committee_id}/members/{user_id}/revoke")
def committees_revoke_member(
    committee_id: int,
    user_id: str,
    payload: CommitteeRevokeIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency-Key required"})
    committee = db.get(Committee, committee_id)
    if committee is None:
        raise HTTPException(status_code=404, detail="Committee not found")
    admin = _require_committee_admin(db, committee_id, user)

    idem = db.query(CommitteeAdminIdempotency).filter(
        CommitteeAdminIdempotency.committee_id == committee_id,
        CommitteeAdminIdempotency.action == "member_revoke",
        CommitteeAdminIdempotency.idempotency_key == idempotency_key,
    ).first()
    if idem is not None:
        return idem.response_json

    membership = db.query(CommitteeMembership).filter(
        CommitteeMembership.committee_id == committee_id,
        CommitteeMembership.user_id == user_id,
    ).first()
    if membership is None:
        raise HTTPException(status_code=404, detail={"reason": "member_not_found"})
    membership.is_active = False

    response = {"committeeId": committee_id, "userId": user_id, "revoked": True}
    db.add(CommitteeAdminIdempotency(
        committee_id=committee_id,
        action="member_revoke",
        idempotency_key=idempotency_key,
        response_json=response,
    ))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_role=admin.role,
        action="committee.member.revoke",
        entity_type="committee_membership",
        entity_id=f"{committee_id}:{user_id}",
        event_id=None,
        bar_id=None,
        payload={"committee_id": committee_id, "user_id": user_id, "reason": payload.reason},
    )
    db.commit()
    return response


@app.get("/committees/{committee_id}/finances/ledger")
def committee_finances_ledger(
    committee_id: int,
    year_id: int = Query(...),
    cursor: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_member(db, committee_id, user)
    _committee_year_or_404(db, committee_id, year_id)
    q = db.query(CommitteeLedgerEntry).filter(CommitteeLedgerEntry.committee_id == committee_id, CommitteeLedgerEntry.year_id == year_id)
    if cursor is not None:
        q = q.filter(CommitteeLedgerEntry.id < cursor)
    rows = q.order_by(CommitteeLedgerEntry.id.desc()).limit(limit + 1).all()
    page = rows[:limit]
    next_cursor = page[-1].id if len(rows) > limit and page else None
    return {"items": [_ledger_payload(r) for r in page], "next_cursor": next_cursor}


@app.post("/committees/{committee_id}/finances/ledger")
def committee_finances_create_ledger(
    committee_id: int,
    payload: CommitteeFinanceLedgerCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    _require_committee_finance_manager(db, committee_id, user)
    _committee_year_or_404(db, committee_id, payload.yearId)
    key = _require_idempotency(idempotency_key)
    existing = db.query(CommitteeLedgerIdempotency).filter(CommitteeLedgerIdempotency.committee_id == committee_id, CommitteeLedgerIdempotency.idempotency_key == key).first()
    if existing is not None:
        return existing.response_json
    entry = CommitteeLedgerEntry(
        committee_id=committee_id,
        year_id=payload.yearId,
        entry_type=payload.type,
        amount_cents=payload.amountCents,
        currency=payload.currency.upper(),
        category=payload.category.strip(),
        occurred_at=payload.occurredAt,
        note=payload.note,
        attachment_url=payload.attachmentUrl,
        created_by=user.id,
    )
    db.add(entry)
    db.flush()
    response = _ledger_payload(entry)
    db.add(CommitteeLedgerIdempotency(committee_id=committee_id, idempotency_key=key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role='app_user', action='committee.finances.ledger.create', entity_type='committee_ledger_entry', entity_id=str(entry.id), event_id=None, bar_id=None, payload={'committee_id': committee_id, 'year_id': payload.yearId, 'idempotency_key': key})
    db.commit()
    return response


@app.get("/committees/{committee_id}/finances/summary")
def committee_finances_summary(
    committee_id: int,
    year_id: int = Query(...),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_member(db, committee_id, user)
    _committee_year_or_404(db, committee_id, year_id)
    rows = db.query(CommitteeLedgerEntry).filter(CommitteeLedgerEntry.committee_id == committee_id, CommitteeLedgerEntry.year_id == year_id).all()
    income = sum(r.amount_cents for r in rows if r.entry_type == 'INCOME')
    expense = sum(r.amount_cents for r in rows if r.entry_type == 'EXPENSE')
    by_category: dict[str, dict[str, int]] = {}
    by_month: dict[str, dict[str, int]] = {}
    for r in rows:
        cat = by_category.setdefault(r.category, {'incomeCents': 0, 'expenseCents': 0})
        month = (r.occurred_at or '')[:7]
        mo = by_month.setdefault(month, {'incomeCents': 0, 'expenseCents': 0})
        if r.entry_type == 'INCOME':
            cat['incomeCents'] += r.amount_cents
            mo['incomeCents'] += r.amount_cents
        else:
            cat['expenseCents'] += r.amount_cents
            mo['expenseCents'] += r.amount_cents
    return {'yearId': year_id, 'incomeCents': income, 'expenseCents': expense, 'netCents': income - expense, 'byCategory': by_category, 'byMonth': by_month}


@app.get("/committees/{committee_id}/finances/export.csv")
def committee_finances_export_csv(
    committee_id: int,
    year_id: int = Query(...),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_member(db, committee_id, user)
    _committee_year_or_404(db, committee_id, year_id)
    rows = db.query(CommitteeLedgerEntry).filter(CommitteeLedgerEntry.committee_id == committee_id, CommitteeLedgerEntry.year_id == year_id).order_by(CommitteeLedgerEntry.occurred_at.asc(), CommitteeLedgerEntry.id.asc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['id', 'type', 'amount_cents', 'currency', 'category', 'occurred_at', 'note', 'attachment_url', 'created_by', 'created_at'])
    for r in rows:
        writer.writerow([r.id, r.entry_type, r.amount_cents, r.currency, r.category, r.occurred_at, r.note or '', r.attachment_url or '', r.created_by, r.created_at.isoformat()])
    return StreamingResponse(iter([buf.getvalue()]), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename=committee_{committee_id}_ledger_{year_id}.csv'})


@app.get("/committees/{committee_id}/finances/snapshot.json")
def committee_finances_snapshot_json(
    committee_id: int,
    year_id: int = Query(...),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_member(db, committee_id, user)
    summary = committee_finances_summary(committee_id=committee_id, year_id=year_id, user=user, db=db)
    ledger = committee_finances_ledger(committee_id=committee_id, year_id=year_id, cursor=None, limit=5000, user=user, db=db)
    return {'committeeId': committee_id, 'yearId': year_id, 'summary': summary, 'ledger': ledger['items'], 'generatedAt': now_utc().isoformat()}


@app.get("/committees/{committee_id}/finances/budgets")
def committee_finances_budgets(
    committee_id: int,
    year_id: int = Query(...),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_member(db, committee_id, user)
    _committee_year_or_404(db, committee_id, year_id)
    rows = db.query(CommitteeBudgetBucket).filter(CommitteeBudgetBucket.committee_id == committee_id, CommitteeBudgetBucket.year_id == year_id).order_by(CommitteeBudgetBucket.month.asc(), CommitteeBudgetBucket.category.asc()).all()
    return {'items': [{'id': r.id, 'month': r.month, 'category': r.category, 'budgetCents': r.budget_cents} for r in rows]}


@app.put("/committees/{committee_id}/finances/budgets")
def committee_finances_put_budgets(
    committee_id: int,
    year_id: int = Query(...),
    payload: list[CommitteeBudgetBucketIn] = [],
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    _require_committee_admin(db, committee_id, user)
    _committee_year_or_404(db, committee_id, year_id)
    key = _require_idempotency(idempotency_key)
    existing = db.query(CommitteeBaptemeIdempotency).filter(CommitteeBaptemeIdempotency.committee_id == committee_id, CommitteeBaptemeIdempotency.action == 'finances_budgets_put', CommitteeBaptemeIdempotency.idempotency_key == key).first()
    if existing is not None:
        return existing.response_json
    db.query(CommitteeBudgetBucket).filter(CommitteeBudgetBucket.committee_id == committee_id, CommitteeBudgetBucket.year_id == year_id).delete()
    for b in payload:
        db.add(CommitteeBudgetBucket(committee_id=committee_id, year_id=year_id, month=b.month, category=b.category, budget_cents=b.budgetCents))
    db.flush()
    response = committee_finances_budgets(committee_id=committee_id, year_id=year_id, user=user, db=db)
    db.add(CommitteeBaptemeIdempotency(committee_id=committee_id, action='finances_budgets_put', idempotency_key=key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role='app_user', action='committee.finances.budgets.put', entity_type='committee_budget_bucket', entity_id=str(committee_id), event_id=None, bar_id=None, payload={'committee_id': committee_id, 'year_id': year_id, 'count': len(payload), 'idempotency_key': key})
    db.commit()
    return response


def _committee_bapteme_campaign_payload(row: CommitteeBaptemeCampaign) -> dict[str, Any]:
    return {'id': row.id, 'committeeId': row.committee_id, 'yearId': row.year_id, 'name': row.name, 'isActive': bool(row.is_active), 'createdAt': row.created_at.isoformat()}


@app.get("/committees/{committee_id}/bapteme/campaign")
def committee_bapteme_campaign_get(
    committee_id: int,
    year_id: int = Query(...),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_bapteme_manager(db, committee_id, user)
    row = db.query(CommitteeBaptemeCampaign).filter(CommitteeBaptemeCampaign.committee_id == committee_id, CommitteeBaptemeCampaign.year_id == year_id).order_by(CommitteeBaptemeCampaign.id.desc()).first()
    return {'campaign': _committee_bapteme_campaign_payload(row) if row else None}


@app.post("/committees/{committee_id}/bapteme/campaign")
def committee_bapteme_campaign_create(
    committee_id: int,
    payload: CommitteeBaptemeCampaignIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    _require_committee_bapteme_manager(db, committee_id, user)
    _committee_year_or_404(db, committee_id, payload.yearId)
    key = _require_idempotency(idempotency_key)
    existing = db.query(CommitteeBaptemeIdempotency).filter(CommitteeBaptemeIdempotency.committee_id == committee_id, CommitteeBaptemeIdempotency.action == 'campaign_create', CommitteeBaptemeIdempotency.idempotency_key == key).first()
    if existing is not None:
        return existing.response_json
    db.query(CommitteeBaptemeCampaign).filter(CommitteeBaptemeCampaign.committee_id == committee_id, CommitteeBaptemeCampaign.year_id == payload.yearId).update({'is_active': False})
    row = CommitteeBaptemeCampaign(committee_id=committee_id, year_id=payload.yearId, name=payload.name, is_active=True)
    db.add(row)
    db.flush()
    response = _committee_bapteme_campaign_payload(row)
    db.add(CommitteeBaptemeIdempotency(committee_id=committee_id, action='campaign_create', idempotency_key=key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role='app_user', action='committee.bapteme.campaign.create', entity_type='committee_bapteme_campaign', entity_id=str(row.id), event_id=None, bar_id=None, payload={'committee_id': committee_id, 'idempotency_key': key})
    db.commit()
    return response


@app.post("/committees/{committee_id}/bapteme/invites")
def committee_bapteme_invite_create(
    committee_id: int,
    payload: CommitteeBaptemeInviteIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    _require_committee_bapteme_manager(db, committee_id, user)
    campaign = db.get(CommitteeBaptemeCampaign, payload.campaignId)
    if campaign is None or campaign.committee_id != committee_id:
        raise HTTPException(status_code=404, detail={'reason': 'campaign_not_found'})
    key = _require_idempotency(idempotency_key)
    existing = db.query(CommitteeBaptemeIdempotency).filter(CommitteeBaptemeIdempotency.committee_id == committee_id, CommitteeBaptemeIdempotency.action == 'invite_create', CommitteeBaptemeIdempotency.idempotency_key == key).first()
    if existing is not None:
        return existing.response_json
    invite_code = secrets.token_hex(4).upper()
    row = CommitteeBaptemeInvite(campaign_id=payload.campaignId, invite_code=invite_code, expires_at=payload.expiresAt, created_by=user.id, blue_display_name=payload.blueDisplayName, status='INVITED')
    db.add(row)
    db.flush()
    response = {'id': row.id, 'campaignId': row.campaign_id, 'inviteCode': row.invite_code, 'blueDisplayName': row.blue_display_name, 'status': row.status, 'expiresAt': row.expires_at.isoformat() if row.expires_at else None}
    db.add(CommitteeBaptemeIdempotency(committee_id=committee_id, action='invite_create', idempotency_key=key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role='app_user', action='committee.bapteme.invite.create', entity_type='committee_bapteme_invite', entity_id=str(row.id), event_id=None, bar_id=None, payload={'committee_id': committee_id, 'campaign_id': payload.campaignId, 'idempotency_key': key})
    db.commit()
    return response


@app.post("/committees/{committee_id}/bapteme/invites/accept")
def committee_bapteme_invite_accept(
    committee_id: int,
    payload: CommitteeBaptemeAcceptIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    key = _require_idempotency(idempotency_key)
    existing = db.query(CommitteeBaptemeIdempotency).filter(CommitteeBaptemeIdempotency.committee_id == committee_id, CommitteeBaptemeIdempotency.action == 'invite_accept', CommitteeBaptemeIdempotency.idempotency_key == key).first()
    if existing is not None:
        return existing.response_json
    invite = db.query(CommitteeBaptemeInvite).filter(CommitteeBaptemeInvite.invite_code == payload.inviteCode.strip().upper()).first()
    if invite is None:
        raise HTTPException(status_code=404, detail={'reason': 'invite_not_found'})
    campaign = db.get(CommitteeBaptemeCampaign, invite.campaign_id)
    if campaign is None or campaign.committee_id != committee_id:
        raise HTTPException(status_code=404, detail={'reason': 'invite_not_found'})
    if invite.expires_at and invite.expires_at < now_utc():
        raise HTTPException(status_code=400, detail={'reason': 'invite_expired'})
    invite.status = 'ACCEPTED'
    invite.accepted_at = now_utc()
    response = {'inviteId': invite.id, 'status': invite.status, 'acceptedAt': invite.accepted_at.isoformat()}
    db.add(CommitteeBaptemeIdempotency(committee_id=committee_id, action='invite_accept', idempotency_key=key, response_json=response))
    db.commit()
    return response


@app.get("/committees/{committee_id}/bapteme/invites")
def committee_bapteme_invites(
    committee_id: int,
    campaignId: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_bapteme_manager(db, committee_id, user)
    rows = db.query(CommitteeBaptemeInvite).filter(CommitteeBaptemeInvite.campaign_id == campaignId).order_by(CommitteeBaptemeInvite.id.desc()).all()
    return {'items': [{'id': r.id, 'campaignId': r.campaign_id, 'inviteCode': r.invite_code, 'blueDisplayName': r.blue_display_name, 'status': r.status, 'acceptedAt': r.accepted_at.isoformat() if r.accepted_at else None} for r in rows]}


@app.post("/committees/{committee_id}/bapteme/slots")
def committee_bapteme_create_slot(
    committee_id: int,
    payload: CommitteeBaptemeSlotIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    _require_committee_bapteme_manager(db, committee_id, user)
    key = _require_idempotency(idempotency_key)
    existing = db.query(CommitteeBaptemeIdempotency).filter(CommitteeBaptemeIdempotency.committee_id == committee_id, CommitteeBaptemeIdempotency.action == 'slot_create', CommitteeBaptemeIdempotency.idempotency_key == key).first()
    if existing is not None:
        return existing.response_json
    row = CommitteeBaptemeSlot(campaign_id=payload.campaignId, starts_at=payload.startsAt, ends_at=payload.endsAt, location=payload.location, description=payload.description)
    db.add(row)
    db.flush()
    response = {'id': row.id, 'campaignId': row.campaign_id, 'startsAt': row.starts_at.isoformat(), 'endsAt': row.ends_at.isoformat(), 'location': row.location, 'description': row.description}
    db.add(CommitteeBaptemeIdempotency(committee_id=committee_id, action='slot_create', idempotency_key=key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role='app_user', action='committee.bapteme.slot.create', entity_type='committee_bapteme_slot', entity_id=str(row.id), event_id=None, bar_id=None, payload={'committee_id': committee_id, 'idempotency_key': key})
    db.commit()
    return response


@app.post("/committees/{committee_id}/bapteme/assign")
def committee_bapteme_assign(
    committee_id: int,
    payload: CommitteeBaptemeAssignIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    _require_committee_bapteme_manager(db, committee_id, user)
    key = _require_idempotency(idempotency_key)
    existing = db.query(CommitteeBaptemeIdempotency).filter(CommitteeBaptemeIdempotency.committee_id == committee_id, CommitteeBaptemeIdempotency.action == 'assign_create', CommitteeBaptemeIdempotency.idempotency_key == key).first()
    if existing is not None:
        return existing.response_json
    invite = db.get(CommitteeBaptemeInvite, payload.inviteId)
    slot = db.get(CommitteeBaptemeSlot, payload.slotId)
    if invite is None or slot is None:
        raise HTTPException(status_code=404, detail={'reason': 'not_found'})
    row = CommitteeBaptemeAssignment(invite_id=payload.inviteId, slot_id=payload.slotId)
    db.add(row)
    db.flush()
    response = {'id': row.id, 'inviteId': row.invite_id, 'slotId': row.slot_id, 'assignedAt': row.assigned_at.isoformat()}
    db.add(CommitteeBaptemeIdempotency(committee_id=committee_id, action='assign_create', idempotency_key=key, response_json=response))
    db.commit()
    return response


@app.post("/committees/{committee_id}/bapteme/incidents")
def committee_bapteme_incident_create(
    committee_id: int,
    payload: CommitteeBaptemeIncidentIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    _require_committee_bapteme_manager(db, committee_id, user)
    key = _require_idempotency(idempotency_key)
    existing = db.query(CommitteeBaptemeIdempotency).filter(CommitteeBaptemeIdempotency.committee_id == committee_id, CommitteeBaptemeIdempotency.action == 'incident_create', CommitteeBaptemeIdempotency.idempotency_key == key).first()
    if existing is not None:
        return existing.response_json
    row = CommitteeBaptemeIncident(campaign_id=payload.campaignId, invite_id=payload.inviteId, incident_type=payload.type.upper(), note=payload.note, created_by=user.id)
    db.add(row)
    db.flush()
    response = {'id': row.id, 'campaignId': row.campaign_id, 'inviteId': row.invite_id, 'type': row.incident_type, 'note': row.note, 'createdAt': row.created_at.isoformat(), 'createdBy': row.created_by}
    db.add(CommitteeBaptemeIdempotency(committee_id=committee_id, action='incident_create', idempotency_key=key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role='app_user', action='committee.bapteme.incident.create', entity_type='committee_bapteme_incident', entity_id=str(row.id), event_id=None, bar_id=None, payload={'committee_id': committee_id, 'campaign_id': payload.campaignId, 'idempotency_key': key})
    db.commit()
    return response


@app.get("/committees/{committee_id}/bapteme/slots")
def committee_bapteme_slots(
    committee_id: int,
    campaignId: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_bapteme_manager(db, committee_id, user)
    rows = db.query(CommitteeBaptemeSlot).filter(CommitteeBaptemeSlot.campaign_id == campaignId).order_by(CommitteeBaptemeSlot.starts_at.asc()).all()
    return {'items': [{'id': r.id, 'campaignId': r.campaign_id, 'startsAt': r.starts_at.isoformat(), 'endsAt': r.ends_at.isoformat(), 'location': r.location, 'description': r.description} for r in rows]}


@app.get("/committees/{committee_id}/bapteme/export_invites.csv")
def committee_bapteme_export_invites_csv(
    committee_id: int,
    campaignId: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_bapteme_manager(db, committee_id, user)
    rows = db.query(CommitteeBaptemeInvite).filter(CommitteeBaptemeInvite.campaign_id == campaignId).order_by(CommitteeBaptemeInvite.id.asc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['id', 'invite_code', 'blue_display_name', 'status', 'accepted_at'])
    for r in rows:
        writer.writerow([r.id, r.invite_code, r.blue_display_name, r.status, r.accepted_at.isoformat() if r.accepted_at else ''])
    return StreamingResponse(iter([buf.getvalue()]), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename=committee_{committee_id}_bapteme_invites_{campaignId}.csv'})


@app.get("/committees/{committee_id}/bapteme/export_slots.csv")
def committee_bapteme_export_slots_csv(
    committee_id: int,
    campaignId: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_bapteme_manager(db, committee_id, user)
    rows = db.query(CommitteeBaptemeSlot).filter(CommitteeBaptemeSlot.campaign_id == campaignId).order_by(CommitteeBaptemeSlot.starts_at.asc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['id', 'starts_at', 'ends_at', 'location', 'description'])
    for r in rows:
        writer.writerow([r.id, r.starts_at.isoformat(), r.ends_at.isoformat(), r.location, r.description])
    return StreamingResponse(iter([buf.getvalue()]), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename=committee_{committee_id}_bapteme_slots_{campaignId}.csv'})


@app.get("/committees/{committee_id}/forum/categories")
def committee_forum_categories(
    committee_id: int,
    year_id: Optional[int] = Query(default=None),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_member(db, committee_id, user)
    if db.get(Committee, committee_id) is None:
        raise HTTPException(status_code=404, detail="Committee not found")
    year = _forum_year_or_404(db, committee_id, year_id or (_committee_active_year(db, committee_id).id if _committee_active_year(db, committee_id) else -1))
    rows = db.query(CommitteeForumCategory).filter(
        CommitteeForumCategory.committee_id == committee_id,
        CommitteeForumCategory.year_id == year.id,
    ).order_by(CommitteeForumCategory.order_index.asc(), CommitteeForumCategory.id.asc()).all()
    return [
        {
            "id": row.id,
            "committeeId": row.committee_id,
            "yearId": row.year_id,
            "name": row.name,
            "slug": row.slug,
            "orderIndex": row.order_index,
            "isArchived": bool(row.is_archived),
        }
        for row in rows
    ]


@app.get("/committees/{committee_id}/forum/posts")
def committee_forum_posts(
    committee_id: int,
    year_id: int = Query(alias="year_id"),
    category_id: int = Query(alias="category_id"),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    membership = _require_committee_member(db, committee_id, user)
    _forum_year_or_404(db, committee_id, year_id)
    _forum_category_or_404(db, committee_id, year_id, category_id)
    include_deleted = (membership.role or "").upper() in {"MOD", "ADMIN", "OWNER"}
    q = db.query(CommitteeForumPost).filter(
        CommitteeForumPost.committee_id == committee_id,
        CommitteeForumPost.year_id == year_id,
        CommitteeForumPost.category_id == category_id,
    )
    if not include_deleted:
        q = q.filter(CommitteeForumPost.is_deleted.is_(False))
    if cursor:
        try:
            ts_raw, id_raw = cursor.split("|", 1)
            ts = datetime.fromisoformat(ts_raw)
            post_id = int(id_raw)
        except Exception:
            raise HTTPException(status_code=400, detail={"reason": "invalid_cursor"})
        q = q.filter(
            (CommitteeForumPost.is_pinned.is_(True) & ((CommitteeForumPost.created_at < ts) | ((CommitteeForumPost.created_at == ts) & (CommitteeForumPost.id < post_id))))
            | (CommitteeForumPost.is_pinned.is_(False) & ((CommitteeForumPost.created_at < ts) | ((CommitteeForumPost.created_at == ts) & (CommitteeForumPost.id < post_id))))
        )
    rows = q.order_by(CommitteeForumPost.is_pinned.desc(), CommitteeForumPost.created_at.desc(), CommitteeForumPost.id.desc()).limit(limit + 1).all()
    items = rows[:limit]
    next_cursor = None
    if len(rows) > limit and items:
        tail = items[-1]
        next_cursor = f"{tail.created_at.isoformat()}|{tail.id}"
    return {"items": [_forum_post_payload(db, row) for row in items], "nextCursor": next_cursor}


@app.get("/committees/{committee_id}/forum/posts/{post_id}")
def committee_forum_post_detail(
    committee_id: int,
    post_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    membership = _require_committee_member(db, committee_id, user)
    row = db.get(CommitteeForumPost, post_id)
    if row is None or row.committee_id != committee_id:
        raise HTTPException(status_code=404, detail={"reason": "post_not_found"})
    if row.is_deleted and (membership.role or "").upper() not in {"MOD", "ADMIN", "OWNER"}:
        raise HTTPException(status_code=404, detail={"reason": "post_not_found"})
    return _forum_post_payload(db, row)


@app.post("/committees/{committee_id}/forum/posts")
def committee_forum_create_post(
    committee_id: int,
    payload: CommitteeForumCreatePostIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    idem_key = _require_idempotency(idempotency_key)
    membership = _require_committee_member(db, committee_id, user)
    perms = _committee_permissions(db, committee_id, membership.role)
    if not perms.get("can_post_forum", False):
        raise HTTPException(status_code=403, detail={"reason": "forbidden"})
    _forum_year_or_404(db, committee_id, payload.yearId)
    category = _forum_category_or_404(db, committee_id, payload.yearId, payload.categoryId)
    if category.is_archived:
        raise HTTPException(status_code=400, detail={"reason": "category_archived"})
    one_minute_ago = now_utc() - timedelta(minutes=1)
    recent_posts = db.query(CommitteeForumPost).filter(
        CommitteeForumPost.committee_id == committee_id,
        CommitteeForumPost.created_by_user_id == user.id,
        CommitteeForumPost.created_at >= one_minute_ago,
    ).count()
    if recent_posts >= 3:
        raise HTTPException(status_code=429, detail={"reason": "rate_limited", "message": "Too many posts"})

    idem = db.query(CommitteeAdminIdempotency).filter(
        CommitteeAdminIdempotency.committee_id == committee_id,
        CommitteeAdminIdempotency.action == "forum_post_create",
        CommitteeAdminIdempotency.idempotency_key == idem_key,
    ).first()
    if idem is not None:
        return idem.response_json
    row = CommitteeForumPost(
        committee_id=committee_id,
        year_id=payload.yearId,
        category_id=payload.categoryId,
        title=payload.title.strip(),
        body=payload.body.strip(),
        created_by_user_id=user.id,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(row)
    db.flush()
    response = _forum_post_payload(db, row)
    db.add(CommitteeAdminIdempotency(committee_id=committee_id, action="forum_post_create", idempotency_key=idem_key, response_json=response))
    db.commit()
    return response


@app.post("/committees/{committee_id}/forum/posts/{post_id}/pin")
def committee_forum_pin_post(
    committee_id: int,
    post_id: int,
    payload: CommitteeForumPinIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    idem_key = _require_idempotency(idempotency_key)
    membership = _require_committee_member(db, committee_id, user)
    _forum_require_mod_or_admin(db, committee_id, membership)
    idem = db.query(CommitteeAdminIdempotency).filter(
        CommitteeAdminIdempotency.committee_id == committee_id,
        CommitteeAdminIdempotency.action == "forum_post_pin",
        CommitteeAdminIdempotency.idempotency_key == idem_key,
    ).first()
    if idem is not None:
        return idem.response_json
    row = db.get(CommitteeForumPost, post_id)
    if row is None or row.committee_id != committee_id:
        raise HTTPException(status_code=404, detail={"reason": "post_not_found"})
    row.is_pinned = payload.pinned
    row.updated_at = now_utc()
    response = _forum_post_payload(db, row)
    db.add(CommitteeAdminIdempotency(committee_id=committee_id, action="forum_post_pin", idempotency_key=idem_key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role=membership.role, action="committee.forum.post.pin", entity_type="committee_forum_post", entity_id=str(post_id), event_id=None, bar_id=None, payload={"committee_id": committee_id, "post_id": post_id, "pinned": payload.pinned, "reason": payload.reason})
    db.commit()
    return response


@app.post("/committees/{committee_id}/forum/posts/{post_id}/lock")
def committee_forum_lock_post(
    committee_id: int,
    post_id: int,
    payload: CommitteeForumLockIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    idem_key = _require_idempotency(idempotency_key)
    membership = _require_committee_member(db, committee_id, user)
    _forum_require_mod_or_admin(db, committee_id, membership)
    idem = db.query(CommitteeAdminIdempotency).filter(
        CommitteeAdminIdempotency.committee_id == committee_id,
        CommitteeAdminIdempotency.action == "forum_post_lock",
        CommitteeAdminIdempotency.idempotency_key == idem_key,
    ).first()
    if idem is not None:
        return idem.response_json
    row = db.get(CommitteeForumPost, post_id)
    if row is None or row.committee_id != committee_id:
        raise HTTPException(status_code=404, detail={"reason": "post_not_found"})
    row.is_locked = payload.locked
    row.updated_at = now_utc()
    response = _forum_post_payload(db, row)
    db.add(CommitteeAdminIdempotency(committee_id=committee_id, action="forum_post_lock", idempotency_key=idem_key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role=membership.role, action="committee.forum.post.lock", entity_type="committee_forum_post", entity_id=str(post_id), event_id=None, bar_id=None, payload={"committee_id": committee_id, "post_id": post_id, "locked": payload.locked, "reason": payload.reason})
    db.commit()
    return response


@app.post("/committees/{committee_id}/forum/posts/{post_id}/delete")
def committee_forum_delete_post(
    committee_id: int,
    post_id: int,
    payload: CommitteeForumDeleteIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    idem_key = _require_idempotency(idempotency_key)
    membership = _require_committee_member(db, committee_id, user)
    _forum_require_mod_or_admin(db, committee_id, membership)
    idem = db.query(CommitteeAdminIdempotency).filter(
        CommitteeAdminIdempotency.committee_id == committee_id,
        CommitteeAdminIdempotency.action == "forum_post_delete",
        CommitteeAdminIdempotency.idempotency_key == idem_key,
    ).first()
    if idem is not None:
        return idem.response_json
    row = db.get(CommitteeForumPost, post_id)
    if row is None or row.committee_id != committee_id:
        raise HTTPException(status_code=404, detail={"reason": "post_not_found"})
    row.is_deleted = True
    row.deleted_at = now_utc()
    row.deleted_by = user.id
    row.updated_at = now_utc()
    response = {"postId": post_id, "deleted": True}
    db.add(CommitteeAdminIdempotency(committee_id=committee_id, action="forum_post_delete", idempotency_key=idem_key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role=membership.role, action="committee.forum.post.delete", entity_type="committee_forum_post", entity_id=str(post_id), event_id=None, bar_id=None, payload={"committee_id": committee_id, "post_id": post_id, "reason": payload.reason})
    db.commit()
    return response


@app.post("/committees/{committee_id}/forum/categories")
def committee_forum_create_category(
    committee_id: int,
    payload: CommitteeForumCreateCategoryIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    idem_key = _require_idempotency(idempotency_key)
    membership = _require_committee_member(db, committee_id, user)
    _forum_require_admin_or_owner(membership)
    _forum_year_or_404(db, committee_id, payload.yearId)
    idem = db.query(CommitteeAdminIdempotency).filter(
        CommitteeAdminIdempotency.committee_id == committee_id,
        CommitteeAdminIdempotency.action == "forum_category_create",
        CommitteeAdminIdempotency.idempotency_key == idem_key,
    ).first()
    if idem is not None:
        return idem.response_json
    slug = _forum_slug(payload.name)
    category = CommitteeForumCategory(
        committee_id=committee_id,
        year_id=payload.yearId,
        name=payload.name.strip(),
        slug=slug,
        order_index=payload.orderIndex or 0,
        is_archived=False,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(category)
    db.flush()
    response = {"id": category.id, "committeeId": committee_id, "yearId": payload.yearId, "name": category.name, "slug": category.slug, "orderIndex": category.order_index, "isArchived": False}
    db.add(CommitteeAdminIdempotency(committee_id=committee_id, action="forum_category_create", idempotency_key=idem_key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role=membership.role, action="committee.forum.category.create", entity_type="committee_forum_category", entity_id=str(category.id), event_id=None, bar_id=None, payload={"committee_id": committee_id, "year_id": payload.yearId, "name": payload.name})
    db.commit()
    return response


@app.put("/committees/{committee_id}/forum/categories/{category_id}")
def committee_forum_update_category(
    committee_id: int,
    category_id: int,
    payload: CommitteeForumUpdateCategoryIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_committee_module()
    idem_key = _require_idempotency(idempotency_key)
    membership = _require_committee_member(db, committee_id, user)
    _forum_require_admin_or_owner(membership)
    idem = db.query(CommitteeAdminIdempotency).filter(
        CommitteeAdminIdempotency.committee_id == committee_id,
        CommitteeAdminIdempotency.action == "forum_category_update",
        CommitteeAdminIdempotency.idempotency_key == idem_key,
    ).first()
    if idem is not None:
        return idem.response_json
    category = db.get(CommitteeForumCategory, category_id)
    if category is None or category.committee_id != committee_id:
        raise HTTPException(status_code=404, detail={"reason": "category_not_found"})
    if payload.name is not None:
        category.name = payload.name.strip()
        category.slug = _forum_slug(payload.name)
    if payload.orderIndex is not None:
        category.order_index = payload.orderIndex
    if payload.isArchived is not None:
        category.is_archived = payload.isArchived
    category.updated_at = now_utc()
    response = {"id": category.id, "committeeId": committee_id, "yearId": category.year_id, "name": category.name, "slug": category.slug, "orderIndex": category.order_index, "isArchived": category.is_archived}
    db.add(CommitteeAdminIdempotency(committee_id=committee_id, action="forum_category_update", idempotency_key=idem_key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role=membership.role, action="committee.forum.category.update", entity_type="committee_forum_category", entity_id=str(category.id), event_id=None, bar_id=None, payload={"committee_id": committee_id, "category_id": category.id, "name": payload.name, "order_index": payload.orderIndex, "is_archived": payload.isArchived})
    db.commit()
    return response


@app.get("/glossary/committees")
def glossary_public_committees(db: Session = Depends(get_db)):
    _require_folklore_glossary_module()
    rows = (
        db.query(Committee)
        .join(CommitteeGlossarySettings, CommitteeGlossarySettings.committee_id == Committee.id)
        .filter(CommitteeGlossarySettings.public_enabled.is_(True))
        .order_by(Committee.name.asc())
        .all()
    )
    return [{"id": row.id, "name": row.name, "slug": row.slug} for row in rows]


@app.get("/glossary/committees/{committee_id}/settings")
def glossary_public_settings(committee_id: int, db: Session = Depends(get_db)):
    _require_folklore_glossary_module()
    settings = db.query(CommitteeGlossarySettings).filter(CommitteeGlossarySettings.committee_id == committee_id).first()
    if settings is None or not settings.public_enabled:
        raise HTTPException(status_code=404, detail={"reason": "not_public"})
    tags = (
        db.query(CommitteeGlossaryTerm.tags_json)
        .filter(CommitteeGlossaryTerm.committee_id == committee_id, CommitteeGlossaryTerm.status != "DELETED")
        .all()
    )
    available = sorted({tag for row in tags for tag in (row[0] or [])})
    return {"public_enabled": True, "availableTags": available}


@app.get("/glossary/committees/{committee_id}/terms")
def glossary_public_terms(
    committee_id: int,
    query: Optional[str] = Query(default=None),
    tags: Optional[str] = Query(default=None),
    year: Optional[int] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    _require_folklore_glossary_module()
    settings = db.query(CommitteeGlossarySettings).filter(CommitteeGlossarySettings.committee_id == committee_id).first()
    if settings is None or not settings.public_enabled:
        raise HTTPException(status_code=404, detail={"reason": "not_public"})
    return _list_glossary_terms(db, committee_id, query, tags, year, cursor, limit, include_archived=False, include_deleted=False)


@app.get("/committees/{committee_id}/glossary/terms")
def glossary_private_terms(
    committee_id: int,
    query: Optional[str] = Query(default=None),
    tags: Optional[str] = Query(default=None),
    year: Optional[int] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_folklore_glossary_module()
    membership = _require_committee_member(db, committee_id, user)
    include_archived = _committee_can_moderate_glossary(db, committee_id, membership)
    return _list_glossary_terms(db, committee_id, query, tags, year, cursor, limit, include_archived=include_archived, include_deleted=include_archived)


@app.post("/committees/{committee_id}/glossary/terms")
def glossary_create_term(
    committee_id: int,
    payload: CommitteeGlossaryTermCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_folklore_glossary_module()
    key = _require_idempotency(idempotency_key)
    membership = _require_glossary_write_access(db, committee_id, user)
    _enforce_glossary_write_rate_limit(committee_id, user.id)
    if payload.yearId is not None:
        _committee_year_or_404(db, committee_id, payload.yearId)
    idem = db.query(CommitteeGlossaryIdempotency).filter(
        CommitteeGlossaryIdempotency.committee_id == committee_id,
        CommitteeGlossaryIdempotency.action == "term_create",
        CommitteeGlossaryIdempotency.idempotency_key == key,
    ).first()
    if idem is not None:
        return idem.response_json
    row = CommitteeGlossaryTerm(
        committee_id=committee_id,
        year_id=payload.yearId,
        term=payload.term.strip(),
        definition=payload.definition.strip(),
        examples=payload.examples.strip() if payload.examples else None,
        tags_json=_sanitize_glossary_tags(payload.tags),
        is_official=bool(payload.isOfficial),
        status="ACTIVE",
        created_by=user.id,
        updated_by=user.id,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(row)
    db.flush()
    response = _glossary_term_payload(row)
    db.add(CommitteeGlossaryIdempotency(committee_id=committee_id, action="term_create", idempotency_key=key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role=membership.role, action="committee.glossary.term.create", entity_type="committee_glossary_term", entity_id=str(row.id), event_id=None, bar_id=None, payload={"committee_id": committee_id, "term": row.term, "idempotency_key": key})
    db.commit()
    return response


@app.put("/committees/{committee_id}/glossary/terms/{term_id}")
def glossary_update_term(
    committee_id: int,
    term_id: int,
    payload: CommitteeGlossaryTermUpdateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_folklore_glossary_module()
    key = _require_idempotency(idempotency_key)
    membership = _require_glossary_write_access(db, committee_id, user)
    _enforce_glossary_write_rate_limit(committee_id, user.id)
    idem = db.query(CommitteeGlossaryIdempotency).filter(
        CommitteeGlossaryIdempotency.committee_id == committee_id,
        CommitteeGlossaryIdempotency.action == f"term_update:{term_id}",
        CommitteeGlossaryIdempotency.idempotency_key == key,
    ).first()
    if idem is not None:
        return idem.response_json
    row = db.get(CommitteeGlossaryTerm, term_id)
    if row is None or row.committee_id != committee_id:
        raise HTTPException(status_code=404, detail={"reason": "term_not_found"})
    if payload.definition is not None:
        row.definition = payload.definition.strip()
    if payload.examples is not None:
        row.examples = payload.examples.strip() if payload.examples else None
    if payload.tags is not None:
        row.tags_json = _sanitize_glossary_tags(payload.tags)
    if payload.isOfficial is not None:
        row.is_official = payload.isOfficial
    if payload.status is not None:
        row.status = payload.status
    row.updated_at = now_utc()
    row.updated_by = user.id
    response = _glossary_term_payload(row)
    db.add(CommitteeGlossaryIdempotency(committee_id=committee_id, action=f"term_update:{term_id}", idempotency_key=key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role=membership.role, action="committee.glossary.term.update", entity_type="committee_glossary_term", entity_id=str(row.id), event_id=None, bar_id=None, payload={"committee_id": committee_id, "term_id": term_id, "idempotency_key": key})
    db.commit()
    return response


@app.post("/committees/{committee_id}/glossary/terms/{term_id}/archive")
def glossary_archive_term(
    committee_id: int,
    term_id: int,
    payload: CommitteeGlossaryArchiveIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_folklore_glossary_module()
    key = _require_idempotency(idempotency_key)
    membership = _require_glossary_write_access(db, committee_id, user)
    _enforce_glossary_write_rate_limit(committee_id, user.id)
    idem = db.query(CommitteeGlossaryIdempotency).filter(
        CommitteeGlossaryIdempotency.committee_id == committee_id,
        CommitteeGlossaryIdempotency.action == f"term_archive:{term_id}",
        CommitteeGlossaryIdempotency.idempotency_key == key,
    ).first()
    if idem is not None:
        return idem.response_json
    row = db.get(CommitteeGlossaryTerm, term_id)
    if row is None or row.committee_id != committee_id:
        raise HTTPException(status_code=404, detail={"reason": "term_not_found"})
    row.status = "ARCHIVED"
    row.updated_at = now_utc()
    row.updated_by = user.id
    response = {"id": row.id, "status": row.status}
    db.add(CommitteeGlossaryIdempotency(committee_id=committee_id, action=f"term_archive:{term_id}", idempotency_key=key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role=membership.role, action="committee.glossary.term.archive", entity_type="committee_glossary_term", entity_id=str(row.id), event_id=None, bar_id=None, payload={"committee_id": committee_id, "term_id": term_id, "reason": payload.reason})
    db.commit()
    return response


@app.post("/committees/{committee_id}/glossary/terms/{term_id}/delete")
def glossary_delete_term(
    committee_id: int,
    term_id: int,
    payload: CommitteeGlossaryDeleteIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_folklore_glossary_module()
    key = _require_idempotency(idempotency_key)
    membership = _require_glossary_write_access(db, committee_id, user)
    _enforce_glossary_write_rate_limit(committee_id, user.id)
    idem = db.query(CommitteeGlossaryIdempotency).filter(
        CommitteeGlossaryIdempotency.committee_id == committee_id,
        CommitteeGlossaryIdempotency.action == f"term_delete:{term_id}",
        CommitteeGlossaryIdempotency.idempotency_key == key,
    ).first()
    if idem is not None:
        return idem.response_json
    row = db.get(CommitteeGlossaryTerm, term_id)
    if row is None or row.committee_id != committee_id:
        raise HTTPException(status_code=404, detail={"reason": "term_not_found"})
    row.status = "DELETED"
    row.updated_at = now_utc()
    row.updated_by = user.id
    response = {"id": row.id, "status": row.status}
    db.add(CommitteeGlossaryIdempotency(committee_id=committee_id, action=f"term_delete:{term_id}", idempotency_key=key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role=membership.role, action="committee.glossary.term.delete", entity_type="committee_glossary_term", entity_id=str(row.id), event_id=None, bar_id=None, payload={"committee_id": committee_id, "term_id": term_id, "reason": payload.reason})
    db.commit()
    return response


@app.get("/committees/{committee_id}/glossary/settings")
def glossary_get_settings(
    committee_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_folklore_glossary_module()
    _require_committee_member(db, committee_id, user)
    settings = _committee_glossary_settings(db, committee_id)
    membership = _committee_membership(db, committee_id, user.id)
    include_deleted = membership is not None and _committee_can_moderate_glossary(db, committee_id, membership)
    q = db.query(CommitteeGlossaryTerm.tags_json).filter(CommitteeGlossaryTerm.committee_id == committee_id)
    if not include_deleted:
        q = q.filter(CommitteeGlossaryTerm.status != "DELETED")
    tags = q.all()
    available = sorted({tag for row in tags for tag in (row[0] or [])})
    return {"public_enabled": bool(settings.public_enabled), "availableTags": available}


@app.put("/committees/{committee_id}/glossary/settings")
def glossary_put_settings(
    committee_id: int,
    payload: CommitteeGlossarySettingsIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_folklore_glossary_module()
    key = _require_idempotency(idempotency_key)
    membership = _require_glossary_write_access(db, committee_id, user)
    _enforce_glossary_write_rate_limit(committee_id, user.id)
    idem = db.query(CommitteeGlossaryIdempotency).filter(
        CommitteeGlossaryIdempotency.committee_id == committee_id,
        CommitteeGlossaryIdempotency.action == "settings_update",
        CommitteeGlossaryIdempotency.idempotency_key == key,
    ).first()
    if idem is not None:
        return idem.response_json
    settings = _committee_glossary_settings(db, committee_id)
    settings.public_enabled = payload.public_enabled
    settings.updated_at = now_utc()
    settings.updated_by = user.id
    response = {"committeeId": committee_id, "public_enabled": bool(settings.public_enabled), "updatedAt": settings.updated_at.isoformat()}
    db.add(CommitteeGlossaryIdempotency(committee_id=committee_id, action="settings_update", idempotency_key=key, response_json=response))
    write_audit_log(db, actor_partner_id=None, actor_role=membership.role, action="committee.glossary.settings.update", entity_type="committee_glossary_settings", entity_id=str(committee_id), event_id=None, bar_id=None, payload={"committee_id": committee_id, "public_enabled": payload.public_enabled})
    db.commit()
    return response


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
        event_code=random_code(6),
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
        "event_code": event.event_code,
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


def _build_event_report_payload(db: Session, event_id: int) -> Dict[str, Any]:
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
    return _build_event_report_payload(db, event_id)


@app.get("/events/{event_id}/exports/attendance.csv")
def export_attendance_csv(
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
        db.query(EntryScanLog)
        .filter(EntryScanLog.event_id == event_id)
        .order_by(EntryScanLog.created_at.desc(), EntryScanLog.id.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "ticket_id", "status", "reason", "staff_id", "scan_id"])
    for row in rows:
        status = "accepted" if row.decision == "ACCEPT" else ("duplicate" if row.reason == "already_used" else "denied")
        writer.writerow([
            row.created_at.isoformat(),
            row.token_id or "",
            status,
            row.reason,
            row.created_by_user_id or "",
            row.scan_id or "",
        ])

    log_event_action(db, event_id, user.id, "exports.attendance_download", {"rows": len(rows)})
    db.commit()
    payload = io.BytesIO(output.getvalue().encode("utf-8"))
    headers = {"Content-Disposition": f'attachment; filename="attendance_event_{event_id}.csv"'}
    return StreamingResponse(payload, media_type="text/csv", headers=headers)


@app.get("/events/{event_id}/costs/export.csv")
def export_costs_csv(
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
        .order_by(EventCost.created_at.desc(), EventCost.id.desc())
        .all()
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "label", "category", "amount_cents"])
    for row in rows:
        writer.writerow([
            row.created_at.isoformat() if row.created_at else "",
            row.label,
            row.category,
            row.amount_cents,
        ])
    payload = io.BytesIO(output.getvalue().encode("utf-8"))
    headers = {"Content-Disposition": f'attachment; filename="costs_event_{event_id}.csv"'}
    return StreamingResponse(payload, media_type="text/csv", headers=headers)


@app.get("/events/{event_id}/exports/report.pdf")
@app.post("/events/{event_id}/exports/report.pdf")
def export_report_pdf(
    event_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    require_role_for_event(db, user.id, event_id, "admin")
    require_feature(db, event_id, "report_enabled")

    report = _build_event_report_payload(db, event_id)

    lines = [
        f"TORE REPORT EVENT #{event_id}",
        f"Generated at: {report['generated_at']}",
        "",
        "SUMMARY",
        f"Total orders: {report['sales']['total_orders']}",
        f"Gross revenue (cents): {report['sales']['gross_revenue_cents']}",
        f"Gross profit (cents): {report['profit']['gross_profit_cents']}",
        "",
        "ATTENDANCE",
        f"Accepted scans: {int(db.query(func.count(EntryScanLog.id)).filter(EntryScanLog.event_id == event_id, EntryScanLog.decision == 'ACCEPT').scalar() or 0)}",
    ]

    if report["costs"]["lines"]:
        lines.extend([
            "",
            "COSTS",
            f"Total costs (cents): {report['costs']['total_cost_cents']}",
        ])
        for row in report["costs"]["lines"][:25]:
            lines.append(f"- {row['label']} ({row['category']}): {row['amount_cents']}")

    pdf_like = ("%PDF-1.4\n" + "\n".join(lines) + "\n%%EOF\n").encode("utf-8")
    log_event_action(db, event_id, user.id, "exports.report_generate", {"costs": len(report['costs']['lines'])})
    db.commit()

    payload = io.BytesIO(pdf_like)
    headers = {"Content-Disposition": f'attachment; filename="event_report_{event_id}.pdf"'}
    return StreamingResponse(payload, media_type="application/pdf", headers=headers)


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

        ticket_value = max(1, int(e.ticket_value_cents or 100))
        menu_items_by_name = {}
        menu_items = []
        if e.bar_id is not None:
            menu_items = s.scalars(
                select(MenuItem).where(MenuItem.bar_id == e.bar_id, MenuItem.is_active == True)
            ).all()
            menu_items_by_name = {item.name.strip().lower(): item for item in menu_items if item.name}

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
            linked = menu_items_by_name.get(d.name.strip().lower())
            out.append(
                {
                    "id": linked.id if linked else d.id,
                    "item_id": linked.id if linked else d.id,
                    "drink_id": d.id,
                    "name": d.name,
                    "type": d.type,
                    "base_price_cents": ed.base_price_cents,
                    "effective_price_cents": effective,
                    "priceTickets": int(round(effective / ticket_value)),
                    "available": linked.is_available if linked else None,
                    "stockStatus": linked.stock_status if linked else None,
                    "bar_id": e.bar_id,
                }
            )

        if out:
            return out

        if menu_items:
            return [
                {
                    "id": item.id,
                    "item_id": item.id,
                    "drink_id": item.id,
                    "name": item.name,
                    "type": "",
                    "base_price_cents": int(item.price_cents),
                    "effective_price_cents": int(item.price_cents),
                    "priceTickets": int(round(int(item.price_cents) / ticket_value)),
                    "available": item.is_available,
                    "stockStatus": item.stock_status,
                    "bar_id": item.bar_id,
                }
                for item in menu_items
            ]

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


@app.post("/events/{event_id}/entry/checkin", response_model=EntryCheckinOut)
def event_entry_checkin(
    event_id: int,
    payload: EntryCheckinIn,
    authorization: Optional[str] = Header(default=None),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency-Key required"})
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    state = (event.event_state or "LIVE").upper()
    if state in {"FROZEN", "CLOSED"}:
        raise HTTPException(status_code=403, detail={"reason": f"event_{state.lower()}"})

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

    raw_qr = (payload.ticket_qr_raw or payload.ticket_id or payload.user_id or "").strip()
    if not raw_qr:
        raise HTTPException(status_code=422, detail={"reason": "invalid", "message": "ticket_qr_raw|ticket_id|user_id required"})

    existing_idem = (
        db.query(EntryLog)
        .filter(EntryLog.event_id == event_id, EntryLog.idempotency_key == idempotency_key.strip())
        .first()
    )
    if existing_idem:
        return EntryCheckinOut(
            status=_entry_status_for_raw(db, event_id, raw_qr),
            entryCount=entry_count(db, event_id),
            userLabel=payload.user_id,
            timestamp=existing_idem.created_at,
        )

    status = _entry_status_for_raw(db, event_id, raw_qr)
    delta = 1 if status == "accepted" else 0
    log = EntryLog(
        event_id=event_id,
        created_at=payload.scanned_at or now_utc(),
        delta=delta,
        source="scan",
        staff_id=staff_id,
        device_id=payload.device_id,
        idempotency_key=idempotency_key.strip(),
        raw_qr=raw_qr,
    )
    db.add(log)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_role="entry_staff",
        action="entry.checkin",
        entity_type="entry_log",
        entity_id=None,
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"status": status, "device_id": payload.device_id, "idempotency_key": idempotency_key.strip(), "staff_id": staff_id},
    )
    db.commit()

    return EntryCheckinOut(
        status=status,
        entryCount=entry_count(db, event_id),
        userLabel=payload.user_id,
        timestamp=log.created_at,
    )


@app.get("/events/{event_id}/entry/count", response_model=EntryCountOut)
def get_event_entry_count(
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
    else:
        identity = _resolve_partner_identity_from_token(raw, db)
        if not identity:
            raise HTTPException(status_code=401, detail="Invalid token")
        if event.bar_id != identity["bar_id"]:
            raise HTTPException(status_code=403, detail="Forbidden")
        require_feature(db, event_id, "entry_enabled")

    return EntryCountOut(entryCount=entry_count(db, event_id), timestamp=now_utc())


@app.get("/events/{event_id}/entry/export.csv")
def export_event_entry_csv(
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
        require_role_for_event(db, user.id, event_id, "entry")
    else:
        identity = _resolve_partner_identity_from_token(raw, db)
        if not identity:
            raise HTTPException(status_code=401, detail="Invalid token")
        if event.bar_id != identity["bar_id"]:
            raise HTTPException(status_code=403, detail="Forbidden")
        _require_partner_roles(identity, {"entry", "manager"})

    rows = db.query(EntryLog).filter(EntryLog.event_id == event_id).order_by(EntryLog.created_at.desc(), EntryLog.id.desc()).all()
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["timestamp", "status", "ticket_or_user", "deviceId"])
    for row in rows:
        raw_qr = (row.raw_qr or "")
        masked = f"***{raw_qr[-6:]}" if raw_qr else ""
        writer.writerow([row.created_at.isoformat(), "accepted" if row.delta > 0 else "already_checked", masked, row.device_id or ""])

    payload = io.BytesIO(stream.getvalue().encode("utf-8"))
    headers = {"Content-Disposition": f'attachment; filename="entry_export_event_{event_id}.csv"'}
    return StreamingResponse(payload, media_type="text/csv", headers=headers)


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
# Battles / Affonds V1
# ---------------------------------------------------------------------


class PartnerBattleTeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: Optional[str] = Field(default=None, max_length=32)


class PartnerBattleCreateIn(BaseModel):
    event_id: int = Field(ge=1)
    title: str = Field(default="Battle", min_length=1, max_length=180)
    mode: str = Field(default="teams", max_length=16)
    is_active: bool = True
    teams: List[PartnerBattleTeamIn] = Field(default_factory=list)


class PartnerBattleUpdateIn(BaseModel):
    is_active: bool


class BattleActionIn(BaseModel):
    team_id: Optional[int] = Field(default=None, ge=1)
    kind: str = Field(default="AFFOND", max_length=16)
    delta: int = 1
    idempotency_key: Optional[str] = Field(default=None, max_length=120)


class BattleJoinIn(BaseModel):
    team_id: Optional[int] = Field(default=None, ge=1)


def _battle_to_dict(db: Session, battle: Battle) -> Dict[str, Any]:
    teams = db.scalars(
        select(BattleTeam).where(BattleTeam.battle_id == battle.id).order_by(BattleTeam.created_at.asc())
    ).all()
    scores = {team.id: 0 for team in teams}
    rows = db.execute(
        select(BattleAction.team_id, func.coalesce(func.sum(BattleAction.delta), 0))
        .where(BattleAction.battle_id == battle.id)
        .group_by(BattleAction.team_id)
    ).all()
    for team_id, total in rows:
        scores[team_id] = int(total or 0)
    return {
        "id": battle.id,
        "bar_id": battle.bar_id,
        "event_id": battle.event_id,
        "title": battle.title,
        "mode": battle.mode,
        "is_active": bool(battle.is_active),
        "created_at": battle.created_at.isoformat(),
        "teams": [
            {
                "id": team.id,
                "name": team.name,
                "color": team.color,
                "score": scores.get(team.id, 0),
            }
            for team in teams
        ],
    }


def _battle_stats(db: Session, battle_id: int, limit: int = 20) -> Dict[str, Any]:
    battle = db.get(Battle, battle_id)
    if not battle:
        raise HTTPException(404, "Battle not found")
    payload = _battle_to_dict(db, battle)
    actions = db.scalars(
        select(BattleAction)
        .where(BattleAction.battle_id == battle.id)
        .order_by(BattleAction.created_at.desc(), BattleAction.id.desc())
        .limit(limit)
    ).all()
    payload["recent_actions"] = [
        {
            "id": action.id,
            "team_id": action.team_id,
            "user_id": action.user_id,
            "kind": action.kind,
            "delta": action.delta,
            "idempotency_key": action.idempotency_key,
            "created_at": action.created_at.isoformat(),
        }
        for action in actions
    ]
    return payload


def _assert_partner_event_access(db: Session, identity: Dict[str, Any], event_id: int) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if event.bar_id != identity["bar_id"]:
        raise HTTPException(403, "Forbidden")
    return event


@app.post("/partner/portal/battles")
def partner_portal_create_battle(
    payload: PartnerBattleCreateIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    event = _assert_partner_event_access(db, identity, payload.event_id)
    battle = Battle(
        bar_id=event.bar_id,
        event_id=event.id,
        title=payload.title,
        mode=payload.mode,
        is_active=payload.is_active,
        created_at=now_utc(),
    )
    db.add(battle)
    db.flush()
    for team in payload.teams:
        db.add(BattleTeam(battle_id=battle.id, name=team.name, color=team.color, created_at=now_utc()))
    db.commit()
    return _battle_to_dict(db, battle)


@app.patch("/partner/portal/battles/{battle_id}")
def partner_portal_update_battle(
    battle_id: int,
    payload: PartnerBattleUpdateIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    battle = db.get(Battle, battle_id)
    if not battle:
        raise HTTPException(404, "Battle not found")
    _assert_partner_event_access(db, identity, battle.event_id)
    battle.is_active = payload.is_active
    db.add(battle)
    db.commit()
    return _battle_to_dict(db, battle)


@app.get("/partner/portal/battles")
def partner_portal_list_battles(
    event_id: int = Query(..., ge=1),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _assert_partner_event_access(db, identity, event_id)
    rows = db.scalars(
        select(Battle).where(Battle.event_id == event_id).order_by(Battle.created_at.desc(), Battle.id.desc())
    ).all()
    return [_battle_to_dict(db, row) for row in rows]


@app.post("/partner/portal/battles/{battle_id}/action")
def partner_portal_record_battle_action(
    battle_id: int,
    payload: BattleActionIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    battle = db.get(Battle, battle_id)
    if not battle:
        raise HTTPException(404, "Battle not found")
    _assert_partner_event_access(db, identity, battle.event_id)

    if payload.team_id is not None:
        team = db.get(BattleTeam, payload.team_id)
        if not team or team.battle_id != battle.id:
            raise HTTPException(400, "Invalid team_id")

    existing = None
    if payload.idempotency_key:
        existing = db.scalar(
            select(BattleAction).where(
                BattleAction.battle_id == battle.id,
                BattleAction.idempotency_key == payload.idempotency_key,
            )
        )
    if existing:
        return {"ok": True, "action_id": existing.id, "idempotent": True, "stats": _battle_stats(db, battle.id)}

    action = BattleAction(
        battle_id=battle.id,
        team_id=payload.team_id,
        user_id=str(identity.get("user_id")),
        kind=payload.kind,
        delta=payload.delta,
        idempotency_key=payload.idempotency_key,
        created_at=now_utc(),
    )
    db.add(action)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(BattleAction).where(
                BattleAction.battle_id == battle.id,
                BattleAction.idempotency_key == payload.idempotency_key,
            )
        )
        if existing:
            return {"ok": True, "action_id": existing.id, "idempotent": True, "stats": _battle_stats(db, battle.id)}
        raise
    return {"ok": True, "action_id": action.id, "idempotent": False, "stats": _battle_stats(db, battle.id)}


@app.get("/partner/portal/battles/{battle_id}/stats")
def partner_portal_battle_stats(
    battle_id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    battle = db.get(Battle, battle_id)
    if not battle:
        raise HTTPException(404, "Battle not found")
    _assert_partner_event_access(db, identity, battle.event_id)
    return _battle_stats(db, battle_id)


@app.get("/battles/{battle_id}")
def get_public_battle(battle_id: int, db: Session = Depends(get_db)):
    battle = db.get(Battle, battle_id)
    if not battle:
        raise HTTPException(404, "Battle not found")
    return _battle_stats(db, battle_id)


@app.get("/battles/event/{event_id}")
def list_public_battles(event_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Battle)
        .where(Battle.event_id == event_id, Battle.is_active.is_(True))
        .order_by(Battle.created_at.desc(), Battle.id.desc())
    ).all()
    return [_battle_to_dict(db, row) for row in rows]


@app.post("/battles/{battle_id}/join")
def join_battle(
    battle_id: int,
    payload: BattleJoinIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    battle = db.get(Battle, battle_id)
    if not battle or not battle.is_active:
        raise HTTPException(404, "Battle not found")
    if payload.team_id is not None:
        team = db.get(BattleTeam, payload.team_id)
        if not team or team.battle_id != battle.id:
            raise HTTPException(400, "Invalid team_id")

    existing = db.scalar(
        select(BattleJoin).where(BattleJoin.battle_id == battle.id, BattleJoin.user_id == user.id)
    )
    if existing:
        return {"ok": True, "join_id": existing.id, "idempotent": True}

    join = BattleJoin(
        battle_id=battle.id,
        team_id=payload.team_id,
        user_id=user.id,
        joined_at=now_utc(),
    )
    db.add(join)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(BattleJoin).where(BattleJoin.battle_id == battle.id, BattleJoin.user_id == user.id)
        )
        if existing:
            return {"ok": True, "join_id": existing.id, "idempotent": True}
        raise
    return {"ok": True, "join_id": join.id, "idempotent": False}


@app.get("/battles/{battle_id}/me")
def battle_me(
    battle_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    battle = db.get(Battle, battle_id)
    if not battle:
        raise HTTPException(404, "Battle not found")
    join = db.scalar(select(BattleJoin).where(BattleJoin.battle_id == battle.id, BattleJoin.user_id == user.id))
    stats = _battle_stats(db, battle_id)
    return {
        "battle_id": battle_id,
        "user_id": user.id,
        "team_id": join.team_id if join else None,
        "joined_at": join.joined_at.isoformat() if join else None,
        "score_snapshot": stats,
    }


class OrgaCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    description: Optional[str] = Field(default=None, max_length=2000)
    city: Optional[str] = Field(default=None, max_length=120)
    org_type: Optional[str] = Field(default=None, max_length=64)
    website_url: Optional[str] = Field(default=None, max_length=255)


class OrgaOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    city: Optional[str] = None
    org_type: Optional[str] = None
    website_url: Optional[str] = None


class OrgaMembershipOut(BaseModel):
    orga: OrgaOut
    role: Literal["OWNER", "MANAGER", "STAFF", "MEMBER"]


class JoinByCodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=16)


class OrgaInviteOut(BaseModel):
    org_id: int
    code: str
    deeplink: str
    qr_payload: str
    expires_at: Optional[str] = None


def _orga_to_out(row: Organization) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "slug": row.slug,
        "description": row.description,
        "city": row.city,
        "org_type": row.org_type,
        "website_url": row.website_url,
    }


def _slugify_orga_name(db: Session, base_name: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in base_name).strip("-")
    cleaned = "-".join([p for p in cleaned.split("-") if p])
    root = cleaned[:120] or f"orga-{secrets.token_hex(2)}"
    slug = root
    idx = 1
    while db.scalar(select(Organization.id).where(Organization.slug == slug)) is not None:
        idx += 1
        slug = f"{root}-{idx}"
    return slug


@app.post("/orgas", response_model=OrgaMembershipOut)
def create_organization(
    payload: OrgaCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    key = ensure_idempotency_key(idempotency_key)
    idem = db.query(OrganizationWriteIdempotency).filter(
        OrganizationWriteIdempotency.actor_user_id == user.id,
        OrganizationWriteIdempotency.action == "orga_create",
        OrganizationWriteIdempotency.idempotency_key == key,
    ).first()
    if idem:
        return idem.response_json

    org = Organization(
        name=payload.name.strip(),
        slug=_slugify_orga_name(db, payload.name.strip()),
        description=(payload.description or "").strip() or None,
        city=(payload.city or "").strip() or None,
        org_type=(payload.org_type or "").strip() or None,
        website_url=(payload.website_url or "").strip() or None,
        created_by_user_id=user.id,
        created_at=now_utc(),
    )
    db.add(org)
    db.flush()

    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role="OWNER",
        created_by_user_id=user.id,
        created_at=now_utc(),
    )
    db.add(membership)

    response = {"orga": _orga_to_out(org), "role": "OWNER"}
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action="orga_create", idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="OWNER",
        action="organization.create",
        entity_type="organization",
        entity_id=str(org.id),
        event_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={"name": org.name, "org_type": org.org_type, "city": org.city},
    )
    db.commit()
    return response


@app.get("/orgas")
def list_orgas(
    query: Optional[str] = None,
    city: Optional[str] = None,
    type: Optional[str] = Query(default=None, alias="type"),
    cursor: Optional[int] = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(Organization)
    if query:
        q = f"%{query.strip().lower()}%"
        stmt = stmt.where(func.lower(Organization.name).like(q))
    if city:
        stmt = stmt.where(func.lower(Organization.city) == city.strip().lower())
    if type:
        stmt = stmt.where(func.lower(Organization.org_type) == type.strip().lower())
    if cursor:
        stmt = stmt.where(Organization.id < cursor)
    rows = db.scalars(stmt.order_by(Organization.id.desc()).limit(limit + 1)).all()
    next_cursor = rows[-1].id if len(rows) > limit else None
    items = rows[:limit]
    return {"items": [_orga_to_out(row) for row in items], "next_cursor": next_cursor}


@app.get("/me/orgas", response_model=list[OrgaMembershipOut])
def my_orgas(
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(OrganizationMembership, Organization)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .where(OrganizationMembership.user_id == user.id)
        .order_by(Organization.name.asc())
    ).all()
    return [{"orga": _orga_to_out(org), "role": membership.role} for membership, org in rows]


@app.get("/orgas/{org_id}", response_model=OrgaOut)
def get_orga(org_id: int, db: Session = Depends(get_db)):
    row = db.get(Organization, org_id)
    if not row:
        raise HTTPException(404, "Organization not found")
    return _orga_to_out(row)


@app.post("/orgas/join_by_code")
def join_orga_by_code(
    payload: JoinByCodeIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    enforce_rate_limit("orga_join", user.id)
    key = ensure_idempotency_key(idempotency_key)

    idem = db.query(OrganizationWriteIdempotency).filter(
        OrganizationWriteIdempotency.actor_user_id == user.id,
        OrganizationWriteIdempotency.action == "orga_join_by_code",
        OrganizationWriteIdempotency.idempotency_key == key,
    ).first()
    if idem:
        return idem.response_json

    code = payload.code.strip().upper()
    invite = db.query(OrganizationInviteCode).filter(OrganizationInviteCode.code == code).first()
    now = now_utc()
    if not invite:
        raise HTTPException(status_code=404, detail={"reason": "INVALID_CODE", "message": "Invalid invite code"})
    if invite.expires_at and invite.expires_at < now:
        raise HTTPException(status_code=400, detail={"reason": "EXPIRED_CODE", "message": "Invite code expired"})
    if invite.used_count >= invite.max_uses:
        raise HTTPException(status_code=400, detail={"reason": "EXHAUSTED_CODE", "message": "Invite code exhausted"})

    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == invite.organization_id,
        OrganizationMembership.user_id == user.id,
    ).first()
    if membership:
        response = {"ok": True, "organization_id": invite.organization_id, "role": membership.role, "idempotent": True}
        db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action="orga_join_by_code", idempotency_key=key, response_json=response))
        db.commit()
        return response

    membership = OrganizationMembership(
        organization_id=invite.organization_id,
        user_id=user.id,
        role=invite.role,
        created_by_user_id=invite.created_by_user_id,
        created_at=now,
    )
    invite.used_count += 1
    db.add(membership)
    response = {"ok": True, "organization_id": invite.organization_id, "role": invite.role, "idempotent": False}
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action="orga_join_by_code", idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=invite.role,
        action="organization.join_by_code",
        entity_type="organization_membership",
        entity_id=f"{invite.organization_id}:{user.id}",
        event_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={"organization_id": invite.organization_id, "code": code},
    )
    db.commit()
    return response


@app.get("/orgas/{org_id}/invite", response_model=OrgaInviteOut)
def get_orga_invite(
    org_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == user.id,
    ).first()
    if not membership or membership.role not in {"OWNER", "MANAGER"}:
        raise HTTPException(403, "Forbidden")

    code = random_code(8)
    invite = OrganizationInviteCode(
        organization_id=org_id,
        code=code,
        role="MEMBER",
        max_uses=100,
        used_count=0,
        expires_at=now_utc() + timedelta(days=7),
        created_by_user_id=user.id,
        created_at=now_utc(),
    )
    db.add(invite)
    db.commit()

    deeplink = f"tore://orgas/join?code={code}&orgId={org_id}"
    return {
        "org_id": org_id,
        "code": code,
        "deeplink": deeplink,
        "qr_payload": deeplink,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
    }
