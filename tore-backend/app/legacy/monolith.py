from __future__ import annotations

# Routes refactor map: Orders -> app/routers/orders.py, Wallet -> app/routers/wallet.py, Polymarket -> app/routers/polymarket.py.

import os
import logging
import csv
import io
import base64
import smtplib
import secrets
import string
import hashlib
import hmac
import json
import subprocess
import threading
import time
import re
import uuid
from dataclasses import asdict, dataclass
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Literal
from zoneinfo import ZoneInfo
from urllib.parse import parse_qs, urlencode, urlparse
from email.message import EmailMessage

import jwt
from passlib.context import CryptContext
from fastapi import FastAPI, HTTPException, Query, Depends, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, case, text, or_, and_, Integer, String, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session, Mapped, mapped_column

from db import Base, engine, get_session, now_utc, DATABASE_URL
from app.services.rate_limit_service import (
    metrics_lite,
    record_status_code,
    enforce_rate_limit,
    RateLimitExceeded,
    standard_rate_limit_http_exception,
    email_otp_rate_limit_http_exception,
)
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
    RefreshToken,
    AuthMagicLink,
    AuthOtpCode,
    PartnerUser,
    PartnerBarAccess,
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
    EventAppWriteIdempotency,
    EventStaffInviteCode,
    EventStaffInviteIdempotency,
    EventStaffBackupCode,
    EventStaffBackupIdempotency,
    ShortLink,
    ShortLinkIdempotency,
    TicketTransfer,
    Committee,
    CommitteeYear,
    CommitteeMembership,
    CommitteeInviteCode,
    CommitteeRolePermission,
    CommitteeAdminIdempotency,
    CommitteeForumCategory,
    CommitteeForumPost,
    CommitteePost,
    CommitteeCalendarItem,
    CommitteeExpense,
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
    OrganizationInviteLink,
    OrganizationInviteIdempotency,
    OrganizationWriteIdempotency,
    OrgaPost,
    AuditLog,
    UserPrivacyDeleteRequest,
    UserSanction,
    GlobalFeatureFlag,
    AccountRequest,
    RoleUpgradeRequest,
)



# Backward-compatible import guard for deployments where this model may be missing
# from the models module (e.g. stale image or partial rollout).
import models as _models_module

ALLOWED_ACCOUNT_MODES = {"user", "organizer", "team"}

CodeConsumeIdempotency = getattr(_models_module, "CodeConsumeIdempotency", None)
if CodeConsumeIdempotency is None:
    class CodeConsumeIdempotency(Base):
        __tablename__ = "code_consume_idempotency"
        __table_args__ = (
            UniqueConstraint("actor_user_id", "idempotency_key", name="uq_code_consume_idem"),
            {"extend_existing": True},
        )

        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        actor_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
        idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
        kind: Mapped[str] = mapped_column(String(32), index=True)
        code_suffix_hash: Mapped[str] = mapped_column(String(64), index=True)
        response_json: Mapped[dict] = mapped_column(JSON, default=dict)
        created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)

from partner_auth import router as partner_auth_router, current_identity as current_partner_identity
from app.db.sqlite_compat import ensure_sqlite_compat
from app.services.audit_service import write_audit_log
from app.services.idempotency_service import ensure_idempotency_key
from app.utils.migrations import ensure_otp_schema, otp_schema_ready, run_migrations_on_startup


# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------

JWT_SECRET = os.getenv("TORE_JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
ACCESS_TOKEN_TTL_MIN = int(os.getenv("TORE_AUTH_ACCESS_TTL_MIN", "60"))
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("TORE_AUTH_REFRESH_TTL_DAYS", "30"))
MAGIC_LINK_TTL_MIN = int(os.getenv("TORE_AUTH_MAGIC_LINK_TTL_MIN", "10"))
MAGIC_LINK_RATE_SCOPE = "auth_email_request_link"
EMAIL_OTP_TTL_MIN = int(os.getenv("TORE_AUTH_EMAIL_OTP_TTL_MIN", "10"))
EMAIL_OTP_SCOPE_EMAIL = "auth_email_request_otp_email"
EMAIL_OTP_SCOPE_IP = "auth_email_request_otp_ip"
EMAIL_OTP_VERIFY_SCOPE = "auth_email_verify_otp"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
ENABLE_SMS_OTP = (os.getenv("ENABLE_SMS_OTP") or "false").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_WHATSAPP_OTP = (os.getenv("ENABLE_WHATSAPP_OTP") or "false").strip().lower() in {"1", "true", "yes", "on"}
ORGA_CODE = (os.getenv("ORGA_CODE") or "").strip()
TEAM_CODE = (os.getenv("TEAM_CODE") or "").strip()
ADMIN_API_KEY = (os.getenv("ADMIN_API_KEY") or "").strip()
PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
    return (os.getenv("TORE_ENV") or os.getenv("ENV") or "").strip().upper() in {"DEV", "DEVELOPMENT", "TEST"}


def _otp_dev_mode_enabled() -> bool:
    return _resolved_env_name() != "PROD" and _env_bool("TORE_EMAIL_OTP_DEV_MODE", default=_strict_dev_env_enabled())


def _otp_dry_run_enabled() -> bool:
    return _resolved_env_name() != "PROD" and _env_bool("TORE_EMAIL_OTP_DRY_RUN", default=False)


def _otp_exp_minutes() -> int:
    try:
        return max(1, int(os.getenv("TORE_EMAIL_OTP_EXP_MINUTES", str(EMAIL_OTP_TTL_MIN))))
    except ValueError:
        return EMAIL_OTP_TTL_MIN


def _otp_max_attempts() -> int:
    try:
        return max(1, int(os.getenv("TORE_EMAIL_OTP_MAX_ATTEMPTS", "5")))
    except ValueError:
        return 5


def _otp_request_rate_limit() -> int:
    try:
        return max(1, int(os.getenv("TORE_EMAIL_OTP_RATE_LIMIT", "3")))
    except ValueError:
        return 3


@dataclass
class EnvReport:
    env: str
    missing: list[str]
    warnings: list[str]


def _resolved_env_name() -> str:
    raw = (os.getenv("TORE_ENV") or os.getenv("ENV") or "DEV").strip().upper()
    if raw in {"PRODUCTION", "PROD"}:
        return "PROD"
    if raw in {"DEVELOPMENT", "DEV", "TEST"}:
        return "DEV"
    return raw or "DEV"


def validate_env_or_warn() -> EnvReport:
    env_name = _resolved_env_name()
    is_prod = env_name == "PROD"
    missing: list[str] = []
    warnings: list[str] = []

    if env_name not in {"DEV", "PROD", "TEST"}:
        warnings.append(f"ENV has unexpected value '{env_name}'")

    if is_prod:
        for key in ("TORE_JWT_SECRET", "ADMIN_API_KEY"):
            value = (os.getenv(key) or "").strip()
            if len(value) < 32 or value.lower().startswith(("dev-", "change-me", "replace-")):
                missing.append(f"{key} must be a unique secret of at least 32 characters")
        for key in ("TORE_EMAIL_OTP_DEV_MODE", "TORE_EMAIL_OTP_DRY_RUN", "ALLOW_DEV_OTP"):
            if _env_bool(key, False):
                missing.append(f"{key} must be disabled in PROD")
        if (os.getenv("MAIL_OVERRIDE_TO") or "").strip():
            missing.append("MAIL_OVERRIDE_TO must be unset in PROD")
        for key in ("SMTP_HOST", "SMTP_FROM"):
            if not (os.getenv(key) or "").strip():
                missing.append(key)

    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if not db_url:
        if is_prod:
            missing.append("DATABASE_URL")
        else:
            warnings.append("DATABASE_URL missing: sqlite dev fallback will be used")
    elif is_prod and db_url.lower().startswith("sqlite"):
        missing.append("DATABASE_URL must target Postgres in PROD")

    public_url = (os.getenv("PUBLIC_URL") or "").strip()
    base_url = (os.getenv("BASE_URL") or "").strip()
    if not (public_url or base_url):
        if is_prod:
            missing.append("PUBLIC_URL/BASE_URL")
        else:
            warnings.append("PUBLIC_URL/BASE_URL missing: using TORE_PUBLIC_APP_URL/default")

    qr_ring = (os.getenv("TORE_QR_SIGNING_KEYS") or "").strip()
    if not qr_ring:
        if is_prod:
            missing.append("TORE_QR_SIGNING_KEYS")
        else:
            warnings.append("TORE_QR_SIGNING_KEYS missing: fallback secret strategy in use")
    else:
        ok, msg = _validate_qr_signing_keys_format()
        if not ok:
            missing.append(f"TORE_QR_SIGNING_KEYS ({msg})")
        else:
            parsed = [item.strip() for item in qr_ring.split(",") if item.strip()]
            if len(parsed) < 2:
                warnings.append("TORE_QR_SIGNING_KEYS rotation looks weak (<2 keys)")

    cors_raw = (os.getenv("TORE_CORS_ORIGINS") or "").strip()
    if is_prod:
        if not cors_raw:
            missing.append("TORE_CORS_ORIGINS")
        elif "*" in [origin.strip() for origin in cors_raw.split(",")]:
            missing.append("TORE_CORS_ORIGINS cannot be '*' in PROD")
    elif not cors_raw:
        warnings.append("TORE_CORS_ORIGINS missing: localhost defaults are enabled")

    google_enabled = _env_bool("TORE_AUTH_GOOGLE_ENABLED") or _env_bool("GOOGLE_AUTH_ENABLED")
    if google_enabled and not (os.getenv("GOOGLE_CLIENT_ID") or "").strip():
        missing.append("GOOGLE_CLIENT_ID")

    retention_raw = (os.getenv("RETENTION_DAYS") or os.getenv("TORE_PRIVACY_RETENTION_DAYS") or "").strip()
    if not retention_raw:
        warnings.append("RETENTION_DAYS/TORE_PRIVACY_RETENTION_DAYS missing: default retention=30")
    else:
        try:
            if int(retention_raw) < 1:
                missing.append("RETENTION_DAYS must be >= 1")
        except ValueError:
            missing.append("RETENTION_DAYS must be an integer")

    report = EnvReport(env=env_name, missing=missing, warnings=warnings)

    for warning in warnings:
        logging.warning(f"startup.env.warning={warning}")

    if is_prod and missing:
        raise RuntimeError(f"Critical environment configuration is missing: {', '.join(missing)}")

    if missing:
        for item in missing:
            logging.warning(f"startup.env.missing={item}")

    return report


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

    def _normalize(items: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in items:
            value = item.strip().rstrip("/")
            if not value or value == "*":
                continue
            if value not in seen:
                seen.add(value)
                normalized.append(value)
        return normalized

    if raw:
        values = [v.strip() for v in raw.split(",") if v.strip()]
        return _normalize(values)

    site_url = (os.getenv("TORE_SITE_URL") or os.getenv("PUBLIC_URL") or "").strip()
    defaults = [
        "https://tore-site.onrender.com",
        "https://tore.onrender.com",
        "https://tore1.onrender.com",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    if site_url:
        defaults.append(site_url)
    return _normalize(defaults)


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
        if "account_mode" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN account_mode VARCHAR(16) DEFAULT 'user'"))
        if "first_name" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN first_name VARCHAR(120)"))
        if "last_name" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN last_name VARCHAR(120)"))
        if "nickname" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN nickname VARCHAR(120)"))
        if "password_hash" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN password_hash VARCHAR(255)"))
        s.execute(text("UPDATE app_users SET account_mode='user' WHERE account_mode IS NULL OR account_mode = ''"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_app_users_account_mode ON app_users (account_mode)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_app_users_deleted_at ON app_users (deleted_at)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_app_users_anonymized_at ON app_users (anonymized_at)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_user_ts ON audit_logs (actor_user_id, ts)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_committee_ts ON audit_logs (committee_id, ts)"))
        s.commit()
    finally:
        s.close()




def _ensure_auth_otp_columns() -> None:
    s = get_session()
    try:
        if engine.dialect.name == "sqlite":
            columns = {row[1] for row in s.execute(text("PRAGMA table_info(auth_otp_codes)")).fetchall()}
            if "last_attempt_at" not in columns:
                s.execute(text("ALTER TABLE auth_otp_codes ADD COLUMN last_attempt_at DATETIME"))
            if "request_id" not in columns:
                s.execute(text("ALTER TABLE auth_otp_codes ADD COLUMN request_id VARCHAR(120)"))
            if "user_id" not in columns:
                s.execute(text("ALTER TABLE auth_otp_codes ADD COLUMN user_id VARCHAR"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_otp_email_created_at ON auth_otp_codes (email, created_at DESC)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_otp_email_used_at ON auth_otp_codes (email, used_at)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_otp_expires_at ON auth_otp_codes (expires_at)"))
        s.commit()
    finally:
        s.close()



def _ensure_role_upgrade_requests_table() -> None:
    if engine.dialect.name != "sqlite":
        return
    s = get_session()
    try:
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS role_upgrade_requests (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                requested_mode VARCHAR(16) NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                created_at DATETIME,
                reviewed_at DATETIME,
                reviewed_by VARCHAR(120),
                note TEXT
            )
        """))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_role_upgrade_requests_user_id ON role_upgrade_requests (user_id)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_role_upgrade_requests_status ON role_upgrade_requests (status)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_role_upgrade_requests_mode ON role_upgrade_requests (requested_mode)"))
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
    _ensure_auth_otp_columns()
    _ensure_role_upgrade_requests_table()
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


def _otp_hash_code(email: str, code: str, created_at: datetime) -> str:
    secret = (os.getenv("TORE_SECRET") or JWT_SECRET or "dev-secret-change-me").encode("utf-8")
    payload = f"{code}:{email}:{int(created_at.timestamp())}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _is_safe_public_url(value: str) -> bool:
    try:
        parsed = urlparse((value or "").strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _mask_email_target(email: str) -> str:
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local[:1]}***@{domain}"
    return f"{local[:2]}***@{domain}"


def _build_magic_redirect_url(redirect_url: Optional[str], email: str, code: str) -> Optional[str]:
    candidate = (redirect_url or '').strip()
    if not candidate:
        return None

    parsed = urlparse(candidate)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return None

    allowed_origins = [item.strip().rstrip('/') for item in (os.getenv('TORE_CORS_ORIGINS') or '').split(',') if item.strip()]
    origin = f"{parsed.scheme}://{parsed.netloc}".rstrip('/')
    if allowed_origins and origin not in allowed_origins:
        return None

    q = parse_qs(parsed.query, keep_blank_values=True)
    q['email'] = [email]
    q['token'] = [code]
    query = urlencode(q, doseq=True)
    return parsed._replace(query=query).geturl()


def _send_email(subject: str, body: str, to_email: str, reply_to: Optional[str] = None) -> None:
    host = (os.getenv("SMTP_HOST") or "").strip()
    if not host:
        if _resolved_env_name() == "PROD":
            raise HTTPException(status_code=503, detail={"code": "email_provider_missing"})
        logging.info("email.skip.no_smtp subject=%s to=%s", subject, to_email)
        return

    port = int((os.getenv("SMTP_PORT") or "587").strip())
    username = (os.getenv("SMTP_USERNAME") or "").strip()
    password = (os.getenv("SMTP_PASSWORD") or "").strip()
    sender = (os.getenv("SMTP_FROM") or "toreguindaille@gmail.com").strip()
    override_to = (os.getenv("MAIL_OVERRIDE_TO") or "").strip()
    target = override_to or to_email

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = target
    if reply_to and "@" in reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
    except Exception:
        logging.exception("email.send.failed subject=%s to=%s", subject, target)
        if _strict_dev_env_enabled():
            logging.info("email.send.dev_dry_run subject=%s to=%s", subject, to_email)
            return
        raise


def _send_otp_email(target_email: str, code: str, magic_link: Optional[str] = None) -> None:
    body = (
        "Ton code TORÈ : "
        f"{code}\n\n"
        "Il expire dans 10 minutes."
    )
    if magic_link:
        body += f"\n\nLien de connexion : {magic_link}"
    _send_email(subject="Ton code TORÈ", body=body, to_email=target_email)


def _send_welcome_email(target_email: str) -> None:
    body = (
        "Bienvenue dans TORÈ.\n"
        "Ton compte est actif.\n"
        "Tu peux maintenant rejoindre des events, scanner des QR et compléter ton profil.\n"
        "🐂 À bientôt sous le Toré.\n"
        "L’équipe TORÈ"
    )
    _send_email(subject="Bienvenue dans TORÈ 🐂", body=body, to_email=target_email)


def _user_snapshot(db: Session, user: AppUser) -> Dict[str, Any]:
    settings = db.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id == user.id).first()
    return {
        "id": user.id,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "address_text": user.address_text,
        "show_address": user.show_address,
        "show_avatar": user.show_avatar,
        "bio": user.bio or "",
        "oripeaux": user.oripeaux or "",
        "username": user.username,
        "city": user.city,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "nickname": user.nickname,
        "phone": user.phone,
        "instagram_handle": user.instagram_handle,
        "show_identity_to_staff": bool(settings and settings.show_identity_to_staff),
        "visibility": (settings.visibility if settings and settings.visibility else "public"),
        "show_identity_in_bar": bool(settings and (settings.show_identity_in_bar or settings.show_identity_to_staff)),
        "email": user.email,
        "account_mode": (user.account_mode if user.account_mode in ALLOWED_ACCOUNT_MODES else "user"),
    }


def _issue_auth_tokens(db: Session, user: AppUser) -> Dict[str, str]:
    _enforce_user_sanctions(db, user)

    access_raw = secrets.token_urlsafe(32)
    db.add(AppToken(user_id=user.id, token_hash=_hash_token(access_raw)))

    refresh_raw = secrets.token_urlsafe(48)
    expires_at = now_utc() + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    db.add(RefreshToken(user_id=user.id, token_hash=_hash_token(refresh_raw), expires_at=expires_at))

    return {"access_token": access_raw, "refresh_token": refresh_raw}


def _verify_google_id_token(id_token: str) -> Dict[str, Any]:
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    if not client_id:
        raise HTTPException(status_code=503, detail={"reason": "google_client_id_missing"})

    try:
        signing_key = jwt.PyJWKClient(GOOGLE_JWKS_URL).get_signing_key_from_jwt(id_token).key
        payload = jwt.decode(
            id_token,
            signing_key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=list(GOOGLE_ISSUERS),
        )
    except Exception:
        raise HTTPException(status_code=401, detail={"reason": "invalid_google_token"})

    email = _normalize_email(str(payload.get("email") or ""))
    if not email:
        raise HTTPException(status_code=400, detail={"reason": "email_missing"})
    if payload.get("email_verified") is False:
        raise HTTPException(status_code=400, detail={"reason": "email_not_verified"})
    return payload


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
    status = (getattr(user, "account_status", None) or "ACTIVE").upper()
    if status not in {"ACTIVE", "LEGACY"}:
        raise HTTPException(status_code=403, detail={"reason": "ACCOUNT_INACTIVE", "status": status})
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


def _require_admin_api_key(x_admin_api_key: Optional[str] = Header(default=None, alias="X-Admin-Api-Key")) -> str:
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail={"reason": "admin_key_not_configured"})
    provided = (x_admin_api_key or "").strip()
    if not provided or provided != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail={"reason": "invalid_admin_api_key"})
    return "admin"


def _serialize_role_upgrade_request(row: RoleUpgradeRequest) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "requested_mode": row.requested_mode,
        "status": row.status,
        "created_at": _serialize_dt(row.created_at),
        "reviewed_at": _serialize_dt(row.reviewed_at),
        "reviewed_by": row.reviewed_by,
        "note": row.note,
    }


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
    user = db.get(AppUser, tok.user_id)
    if user is None:
        return None
    try:
        _enforce_user_sanctions(db, user)
    except HTTPException:
        return None
    return user


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

    now = now_utc()
    if not bool(getattr(user, "is_guest", False)) and tok.created_at and tok.created_at <= now - timedelta(minutes=ACCESS_TOKEN_TTL_MIN):
        tok.revoked_at = now
        db.add(tok)
        db.commit()
        raise HTTPException(status_code=401, detail={"reason": "access_token_expired"})

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
    from app.services.wallet_service import get_or_create_wallet as wallet_for_user
    return wallet_for_user(s, user_id)


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
    from app.services.wallet_service import apply_wallet_tx
    return apply_wallet_tx(
        s,
        user_id=user_id,
        kind=kind,
        amount_tickets=amount_tickets,
        ref_type=ref_type,
        ref_id=ref_id,
        created_by_user_id=created_by_user_id,
        idempotency_key=idempotency_key,
    )



def _role_rank(role: str) -> int:
    if role == "admin":
        return 3
    if role == "entry":
        return 2
    return 1


def resolve_event_role(db: Session, user_id: str, event_id: int) -> str:
    event = db.get(Event, event_id)
    if event is None or (event.ends_at is not None and event.ends_at <= now_utc()):
        return "guest"
    if event.host_type == "user" and event.host_id == user_id:
        return "admin"
    if event.host_type == "orga" and str(event.host_id or "").isdigit():
        membership = _membership_for(db, org_id=int(event.host_id), user_id=user_id)
        if membership is not None and (membership.role or "").upper() in _STRUCTURE_AUTH_ROLES:
            return "admin"
    staff = (
        db.query(EventStaff)
        .filter(EventStaff.event_id == event_id, EventStaff.user_id == user_id)
        .first()
    )
    if (
        not staff
        or staff.is_active is False
        or staff.revoked_at is not None
        or (staff.expires_at is not None and staff.expires_at <= now_utc())
    ):
        return "guest"
    role = (staff.role or "").lower()
    if role in {"admin", "manager"}:
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


class GoogleAuthIn(BaseModel):
    idToken: str


class MagicLinkRequestIn(BaseModel):
    email: str
    device: Optional[str] = None
    redirect_url: Optional[str] = None


class MagicLinkVerifyIn(BaseModel):
    email: str
    token: str


class EmailOtpRequestIn(BaseModel):
    email: str
    redirect_url: Optional[str] = None


class EmailOtpVerifyIn(BaseModel):
    email: str
    code: str = Field(min_length=6, max_length=6)


class PasswordRegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    nickname: str = Field(min_length=1, max_length=120)


class PasswordLoginIn(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class RefreshIn(BaseModel):
    refreshToken: str


class UpgradeGuestIn(BaseModel):
    guest_device_id: str
    merge_policy: str = "keep"


class SmsOtpProvider:
    def request_otp(self, phone: str) -> None:
        raise NotImplementedError("SMS OTP provider not enabled")


class WhatsAppOtpProvider:
    def request_otp(self, phone: str) -> None:
        raise NotImplementedError("WhatsApp OTP provider not enabled")


class PatchMeIn(BaseModel):
    model_config = {"extra": "forbid"}

    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    address_text: Optional[str] = None
    show_address: Optional[bool] = None
    show_avatar: Optional[bool] = None
    show_identity_to_staff: Optional[bool] = None
    bio: Optional[str] = None
    visibility: Optional[str] = None
    show_identity_in_bar: Optional[bool] = None
    account_mode: Optional[Literal["user", "organizer", "team"]] = None


class ProfilePatchIn(BaseModel):
    model_config = {"extra": "forbid"}

    username: Optional[str] = Field(default=None, min_length=3, max_length=40)
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    avatar_url: Optional[str] = Field(default=None, max_length=512)
    bio: Optional[str] = Field(default=None, max_length=280)
    city: Optional[str] = Field(default=None, max_length=120)
    oripeaux: Optional[str] = Field(default=None, max_length=500)


class ProfilePrivacyPatchIn(BaseModel):
    model_config = {"extra": "forbid"}

    profile: Optional[Literal["PUBLIC", "TORE_USERS", "PRIVATE"]] = None
    photo: Optional[Literal["PUBLIC", "TORE_USERS", "PRIVATE"]] = None
    bio: Optional[Literal["PUBLIC", "TORE_USERS", "PRIVATE"]] = None
    affiliations: Optional[Literal["PUBLIC", "TORE_USERS", "PRIVATE"]] = None
    badges: Optional[Literal["PUBLIC", "TORE_USERS", "PRIVATE"]] = None
    event_history: Optional[Literal["PUBLIC", "TORE_USERS", "PRIVATE"]] = None
    participations: Optional[Literal["PUBLIC", "TORE_USERS", "PRIVATE"]] = None
    gamification: Optional[Literal["PUBLIC", "TORE_USERS", "PRIVATE"]] = None
    event_history_opt_in: Optional[bool] = None
    participations_opt_in: Optional[bool] = None
    gamification_opt_in: Optional[bool] = None


class AffiliationRevokeIn(BaseModel):
    model_config = {"extra": "forbid"}

    reason: str = Field(min_length=1, max_length=280)


class RoleUpgradeRequestIn(BaseModel):
    requested_mode: Literal["user", "organizer", "team"]
    code: str = Field(min_length=1, max_length=120)


class RoleUpgradeReviewIn(BaseModel):
    action: Literal["approve", "reject"]
    note: Optional[str] = Field(default=None, max_length=500)


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

class EntryManualIncrementIn(BaseModel):
    delta: int = Field(default=1, ge=1, le=20)
    reason: str = Field(min_length=3)
    note: Optional[str] = None


class EntryManualIncrementOut(BaseModel):
    count: int
    deltaApplied: int
    serverTime: datetime


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


class StaffInviteCodeIn(BaseModel):
    role: str
    expiresInHours: int = Field(default=12, ge=1, le=168)
    label: Optional[str] = Field(default=None, max_length=120)


class StaffInviteRevokeIn(BaseModel):
    reason: str = Field(min_length=1, max_length=280)


class StaffInviteRotateIn(BaseModel):
    role: str
    expiresInMinutes: Optional[int] = Field(default=None, ge=5, le=10080)


class StaffJoinByInviteIn(BaseModel):
    code: str


class StaffBackupGenerateIn(BaseModel):
    role: str
    count: int = Field(default=12, ge=1, le=64)
    expiresInHours: int = Field(default=12, ge=1, le=168)


class StaffBackupJoinIn(BaseModel):
    code: str


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


class EventVenueIn(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class CreateEventIn(BaseModel):
    name: str
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    startAt: Optional[datetime] = None
    endAt: Optional[datetime] = None
    bar_id: Optional[int] = None
    city: Optional[str] = None
    venue: Optional[EventVenueIn] = None
    visibility: str = "PRIVATE"
    host_type: str = "user"
    host_id: Optional[str] = None
    modulesOn: Optional[dict] = None
    rulesFlags: Optional[dict] = None
    public_description: Optional[str] = Field(default=None, max_length=10000)
    short_description: Optional[str] = Field(default=None, max_length=280)
    banner_url: Optional[str] = Field(default=None, max_length=512, pattern=r"^https?://")
    thumbnail_url: Optional[str] = Field(default=None, max_length=512, pattern=r"^https?://")
    event_type: Optional[str] = Field(default=None, max_length=64)
    capacity: Optional[int] = Field(default=None, ge=1)
    access_type: Optional[Literal["OPEN", "TICKET", "INVITE", "APPROVAL"]] = None
    currency: str = Field(default="EUR", min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    address: Optional[str] = Field(default=None, max_length=255)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    entry_price_cents: int = Field(default=0, ge=0)


class EventPublicContentPatchIn(BaseModel):
    public_description: Optional[str] = Field(default=None, max_length=10000)
    short_description: Optional[str] = Field(default=None, max_length=280)
    banner_url: Optional[str] = Field(default=None, max_length=512, pattern=r"^https?://")
    thumbnail_url: Optional[str] = Field(default=None, max_length=512, pattern=r"^https?://")
    event_type: Optional[str] = Field(default=None, max_length=64)
    capacity: Optional[int] = Field(default=None, ge=1)
    access_type: Optional[Literal["OPEN", "TICKET", "INVITE", "APPROVAL"]] = None
    entry_price_cents: Optional[int] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    address: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)


class EventRuntimeOut(BaseModel):
    eventState: str
    lastUpdatedAt: Optional[str] = None


class EventShareOut(BaseModel):
    webUrl: Optional[str] = None
    deeplink: str
    qrPayload: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    https_link: str
    qr_payload_join: str
    event_code: Optional[str] = None
    staff_invite: Optional[dict] = None




class OpenLinkOut(BaseModel):
    ok: bool
    type: str
    target: Dict[str, Any]
    deeplink: str
    webFallback: str
    expiresAt: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None


class JoinCodePreviewOut(BaseModel):
    exists: bool
    requiresAuth: bool
    titleHint: Optional[str] = None
    startAtHint: Optional[str] = None
    hostHint: Optional[str] = None
    public: Optional[dict[str, Any]] = None



class CodesPreviewOut(BaseModel):
    kind: Literal["join", "staff_invite", "staff_backup", "orga_invite", "event_public", "unknown"]
    requiresAuth: bool
    status: str
    normalizedCode: Optional[str] = None
    displaySuffix: Optional[str] = None
    copyValue: Optional[str] = None
    copyHint: Optional[str] = None
    deeplink: Optional[str] = None
    actionHint: Literal["OPEN_APP", "LOGIN_REQUIRED", "ENTER_CODE"] = "ENTER_CODE"
    expiresAt: Optional[str] = None
    titleHint: Optional[str] = None
    orgHint: Optional[str] = None
    eventHint: Optional[str] = None
    openUrl: Optional[str] = None
    shareText: Optional[str] = None


class ShortLinkCreateIn(BaseModel):
    kind: Literal["event_share", "orga_share", "open_url"]
    event_id: Optional[int] = None
    orga_id: Optional[int] = None
    open_type: Optional[str] = None
    open_id: Optional[int] = None
    open_code: Optional[str] = None
    expiresInSeconds: Optional[int] = None


class ShortLinkCreateOut(BaseModel):
    shortUrl: str
    openUrl: str
    fallbackOpenUrl: str
    expiresAt: Optional[str] = None
    slug: str


class ShortLinkRevokeIn(BaseModel):
    reason: Optional[str] = None


class CodesConsumeIn(BaseModel):
    code: str


class CreateEventOut(BaseModel):
    event_id: int
    name: str
    starts_at: str
    ends_at: str
    bar_id: Optional[int] = None
    event_code: Optional[str] = None
    modulesOn: dict = Field(default_factory=dict)
    runtime: EventRuntimeOut
    publicationStatus: str
    visibility: str
    share: EventShareOut


class EventPublishOut(BaseModel):
    event_id: int
    publicationStatus: str


class MyEventSummaryOut(BaseModel):
    id: int
    name: str
    startAt: str
    endAt: str
    venue: Optional[str] = None
    visibility: str
    status: str
    modulesOn: dict = Field(default_factory=dict)
    host_type: str
    host_id: Optional[str] = None
    roleForMe: Literal["OWNER", "MANAGER", "STAFF", "MEMBER", "FOLLOWER"]
    canManage: bool
    joined: bool


class EventManageSnapshotOut(BaseModel):
    eventId: int
    publicationStatus: str
    visibility: str
    runtime: EventRuntimeOut
    share: EventShareOut
    qrPackAvailable: bool
    staffInviteCodeCurrent: Optional[str] = None


class EventSummaryOut(BaseModel):
    id: int
    bar_id: Optional[int] = None
    name: str
    starts_at: datetime
    ends_at: datetime
    entry_price_cents: int
    ticket_mode: bool
    ticket_value_cents: int
    status: str
    eventState: str
    venue: Optional[str] = None
    barName: Optional[str] = None
    city: Optional[str] = None
    host: dict[str, Any]
    modulesOn: list[str]
    visibility: str
    publicationStatus: str
    shortDescription: Optional[str] = None
    bannerUrl: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    eventType: Optional[str] = None
    capacity: Optional[int] = None
    accessType: Optional[str] = None
    currency: str = "EUR"
    address: Optional[str] = None
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)


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


class CommitteeSpacePostIn(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    body: str = Field(min_length=1, max_length=4000)
    pinned: bool = False


class CommitteeSpaceCalendarIn(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    date: str = Field(min_length=10, max_length=10)
    location: Optional[str] = Field(default=None, max_length=180)
    notes: Optional[str] = Field(default=None, max_length=4000)


class CommitteeSpaceExpenseIn(BaseModel):
    amountCents: int = Field(gt=0, le=50_000_000)
    label: str = Field(min_length=1, max_length=180)
    category: str = Field(min_length=1, max_length=120)
    date: str = Field(min_length=10, max_length=10)


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
    public_description: Optional[str] = Field(default=None, max_length=10000)
    short_description: Optional[str] = Field(default=None, max_length=280)
    banner_url: Optional[str] = Field(default=None, max_length=512, pattern=r"^https?://")
    thumbnail_url: Optional[str] = Field(default=None, max_length=512, pattern=r"^https?://")
    event_type: Optional[str] = Field(default=None, max_length=64)
    capacity: Optional[int] = Field(default=None, ge=1)
    access_type: Optional[Literal["OPEN", "TICKET", "INVITE", "APPROVAL"]] = None
    currency: str = Field(default="EUR", min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    address: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)


class PartnerEventUpdateIn(BaseModel):
    name: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    entry_price_cents: Optional[int] = Field(default=None, ge=0)
    tickets_enabled: Optional[bool] = None
    entry_enabled: Optional[bool] = None
    public_description: Optional[str] = Field(default=None, max_length=10000)
    short_description: Optional[str] = Field(default=None, max_length=280)
    banner_url: Optional[str] = Field(default=None, max_length=512, pattern=r"^https?://")
    thumbnail_url: Optional[str] = Field(default=None, max_length=512, pattern=r"^https?://")
    event_type: Optional[str] = Field(default=None, max_length=64)
    capacity: Optional[int] = Field(default=None, ge=1)
    access_type: Optional[Literal["OPEN", "TICKET", "INVITE", "APPROVAL"]] = None
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    address: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)


class PartnerEventOut(BaseModel):
    id: int
    bar_id: Optional[int] = None
    name: str
    starts_at: datetime
    ends_at: datetime
    entry_price_cents: int
    tickets_enabled: bool
    entry_enabled: bool
    public_description: Optional[str] = None
    short_description: Optional[str] = None
    banner_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    event_type: Optional[str] = None
    capacity: Optional[int] = None
    access_type: Optional[str] = None
    currency: str = "EUR"
    address: Optional[str] = None
    city: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


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
    public_description: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    address: Optional[str] = None
    practical_info: Optional[str] = None
    map_url: Optional[str] = None
    public_modules: dict[str, bool] = Field(default_factory=dict)
    partner_status: str = "ACTIVE"
    public_visibility: str = "PUBLIC"


class PartnerBarPatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=180)
    city: Optional[str] = Field(default=None, max_length=120)
    public_description: Optional[str] = Field(default=None, max_length=10000)
    logo_url: Optional[str] = Field(default=None, max_length=512, pattern=r"^https?://")
    banner_url: Optional[str] = Field(default=None, max_length=512, pattern=r"^https?://")
    primary_color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    address: Optional[str] = Field(default=None, max_length=255)
    practical_info: Optional[str] = Field(default=None, max_length=10000)
    map_url: Optional[str] = Field(default=None, max_length=512, pattern=r"^https?://")
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    public_modules: Optional[dict[str, bool]] = None
    partner_status: Optional[Literal["ACTIVE", "INACTIVE"]] = None
    public_visibility: Optional[Literal["PUBLIC", "HIDDEN"]] = None


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
logging.info("BOOT commit=%s", os.getenv("RENDER_GIT_COMMIT"))




@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    payload_detail: Any
    if isinstance(detail, dict):
        payload_detail = dict(detail)
    else:
        payload_detail = str(detail)

    if exc.status_code == 429 and isinstance(payload_detail, dict):
        retry_after_raw = None
        if exc.headers:
            retry_after_raw = exc.headers.get('Retry-After') or exc.headers.get('retry-after')
        if retry_after_raw is None:
            retry_after_raw = request.headers.get('retry-after')
        retry_after_seconds = int(retry_after_raw) if (retry_after_raw and retry_after_raw.isdigit()) else None
        body_retry = payload_detail.get('retry_after_seconds')
        if retry_after_seconds is None and isinstance(body_retry, int):
            retry_after_seconds = body_retry
        if retry_after_seconds is not None:
            payload_detail['retry_after_seconds'] = retry_after_seconds

    if isinstance(payload_detail, dict) and 'code' not in payload_detail and isinstance(payload_detail.get('reason'), str):
        payload_detail['code'] = payload_detail['reason']

    return JSONResponse(
        status_code=exc.status_code,
        content={'detail': payload_detail},
        headers=exc.headers,
    )


def _request_id_from_request(request: Request) -> Optional[str]:
    return (
        request.headers.get("x-request-id")
        or request.headers.get("x-render-request-id")
        or request.headers.get("x-correlation-id")
    )


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    http_exc = standard_rate_limit_http_exception(
        scope=exc.scope,
        retry_after_seconds=exc.retry_after_seconds,
    )
    return await _http_exception_handler(request, http_exc)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    request_id = _request_id_from_request(request)
    logging.exception("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    payload: Dict[str, Any] = {
        "detail": "Internal Server Error",
        "code": "internal_error",
        "request_id": request_id,
    }
    return JSONResponse(status_code=500, content=payload)


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
from app.routers.account_request import router as account_request_router
from app.routers.operational_access import router as operational_access_router
from app.routers.forum import router as forum_router
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
app.include_router(account_request_router)
app.include_router(operational_access_router)
app.include_router(forum_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=r"^https://.*\.onrender\.com$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    run_migrations_on_startup()
    validate_env_or_warn()
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
    return _partner_bar_out(bar)


@app.patch("/partner/portal/bar", response_model=PartnerBarOut)
def partner_portal_bar_update(
    payload: PartnerBarPatchIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    _require_partner_role(identity, "manager")
    bar = db.get(Bar, identity["bar_id"])
    if not bar:
        raise HTTPException(404, "Bar not found")
    for field in payload.model_fields_set:
        value = getattr(payload, field)
        if field in {"primary_color", "secondary_color", "partner_status", "public_visibility"} and value is not None:
            value = value.upper()
        setattr(bar, field, value)
    db.add(bar)
    db.commit()
    db.refresh(bar)
    return _partner_bar_out(bar)


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
        public_description=payload.public_description,
        short_description=payload.short_description,
        banner_url=payload.banner_url,
        thumbnail_url=payload.thumbnail_url,
        event_type=payload.event_type,
        capacity=payload.capacity,
        access_type=payload.access_type,
        currency=payload.currency.upper(),
        address=payload.address,
        city=payload.city or bar.city,
        lat=payload.lat,
        lng=payload.lng,
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
        public_description=event.public_description,
        short_description=event.short_description,
        banner_url=event.banner_url,
        thumbnail_url=event.thumbnail_url,
        event_type=event.event_type,
        capacity=event.capacity,
        access_type=event.access_type,
        currency=(event.currency or "EUR").upper(),
        address=event.address,
        city=event.city,
        lat=event.lat,
        lng=event.lng,
    )


_EVENT_PUBLIC_CONTENT_FIELDS = {
    "public_description", "short_description", "banner_url", "thumbnail_url",
    "event_type", "capacity", "access_type", "entry_price_cents", "currency",
    "address", "city", "lat", "lng",
}


def _apply_event_public_content(event: Event, payload: BaseModel) -> None:
    fields_set = payload.model_fields_set
    for field in _EVENT_PUBLIC_CONTENT_FIELDS.intersection(fields_set):
        value = getattr(payload, field)
        if field in {"access_type", "currency"} and value is not None:
            value = value.upper()
        setattr(event, field, value)
    event.last_updated_at = now_utc()


def _partner_bar_out(bar: Bar) -> PartnerBarOut:
    return PartnerBarOut(
        id=bar.id,
        name=bar.name,
        city=bar.city,
        lat=bar.lat,
        lng=bar.lng,
        public_description=bar.public_description,
        logo_url=bar.logo_url,
        banner_url=bar.banner_url,
        primary_color=bar.primary_color,
        secondary_color=bar.secondary_color,
        address=bar.address,
        practical_info=bar.practical_info,
        map_url=bar.map_url,
        public_modules=bar.public_modules or {},
        partner_status=(bar.partner_status or "ACTIVE").upper(),
        public_visibility=(bar.public_visibility or "PUBLIC").upper(),
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
    _apply_event_public_content(event, payload)

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


@app.get("/debug/health-ui")
def debug_health_ui(db: Session = Depends(get_db)):
    if not _strict_dev_env_enabled():
        raise HTTPException(404, "Not found")

    env_report = validate_env_or_warn()
    modules_flags = db.query(GlobalFeatureFlag).all()
    flags_enabled = sorted([flag.key for flag in modules_flags if bool(flag.enabled)])

    route_signatures = {(getattr(route, "path", None), tuple(sorted(getattr(route, "methods", set()) or set()))) for route in app.routes}

    def _route_exists(path: str, method: str) -> bool:
        return (path, tuple(sorted({method}))) in route_signatures or any(
            route_path == path and method in methods for route_path, methods in route_signatures
        )

    return {
        "serverTime": now_utc().isoformat(),
        "gitSha": _debug_git_sha(),
        "env": env_report.env,
        "publicUrl": (os.getenv("PUBLIC_URL") or "").strip() or None,
        "baseUrl": _public_app_base_url(),
        "signingKeyIds": _debug_signing_key_ids(),
        "modulesFlagsCount": len(modules_flags),
        "flagsEnabled": flags_enabled,
        "recentRateLimitHits": metrics_lite(),
        "routesEnabled": {
            "open": _route_exists("/open", "GET"),
            "shortlinks": _route_exists("/shortlinks", "POST"),
            "codes_preview": _route_exists("/codes/preview", "GET"),
            "codes_consume": _route_exists("/codes/consume", "POST"),
        },
        "envReport": asdict(env_report),
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
            is_guest=True,
        )
        s.add(u)
        s.flush()

        access_raw = _issue_auth_tokens(s, u)["access_token"]
        s.commit()

        return {"token": access_raw, "user": _user_snapshot(s, u)}
    finally:
        s.close()


@app.post("/auth/google")
def auth_google(payload: GoogleAuthIn, db: Session = Depends(get_db)):
    claims = _verify_google_id_token(payload.idToken)
    email = _normalize_email(str(claims.get("email") or ""))

    user = db.query(AppUser).filter(func.lower(AppUser.email) == email).first()
    if not user:
        user = AppUser(
            id=secrets.token_hex(16),
            display_name=(claims.get("name") or claims.get("given_name") or email.split("@")[0])[:120],
            email=email,
            show_address=False,
            show_avatar=True,
            is_guest=False,
        )
        db.add(user)
        db.flush()

    tokens = _issue_auth_tokens(db, user)
    db.commit()
    return {**tokens, "user": _user_snapshot(db, user)}


@app.get("/auth/providers")
def auth_providers_status():
    return {
        "email_otp": True,
        "sms_otp": ENABLE_SMS_OTP,
        "whatsapp_otp": ENABLE_WHATSAPP_OTP,
    }


@app.post("/auth/email/request_otp")
def auth_email_request_otp(payload: EmailOtpRequestIn, request: Request, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail={"reason": "invalid_email"})

    actor_ip = request.client.host if request.client else "unknown"
    request_id = _request_id_from_request(request)

    try:
        enforce_rate_limit(EMAIL_OTP_SCOPE_EMAIL, email)
        enforce_rate_limit(EMAIL_OTP_SCOPE_IP, actor_ip)
    except RateLimitExceeded as exc:
        raise email_otp_rate_limit_http_exception(retry_after_seconds=exc.retry_after_seconds)

    if not otp_schema_ready():
        try:
            ensure_otp_schema(engine)
        except Exception:
            logging.exception("OTP schema unavailable during /auth/email/request_otp")
            raise HTTPException(status_code=503, detail={"reason": "otp_schema_unavailable", "code": "otp_schema_unavailable"})

    now = now_utc()
    raw_code = f"{secrets.randbelow(1000000):06d}"
    otp_row = AuthOtpCode(
        email=email,
        code_hash=_otp_hash_code(email, raw_code, now),
        expires_at=now + timedelta(minutes=_otp_exp_minutes()),
        request_ip=actor_ip,
        request_id=request_id,
        max_attempts=_otp_max_attempts(),
    )
    existing_user = db.query(AppUser).filter(func.lower(AppUser.email) == email).first()
    if existing_user:
        otp_row.user_id = existing_user.id
    db.add(otp_row)
    db.commit()

    smtp_host = (os.getenv("SMTP_HOST") or "").strip()
    dev_mode = _otp_dev_mode_enabled() or (_resolved_env_name() != "PROD" and _env_bool("ALLOW_DEV_OTP", False))
    if not smtp_host:
        if _otp_dry_run_enabled():
            logging.info("OTP_DEBUG email=%s code=%s", email, raw_code)
            return {"ok": True, "devToken": raw_code}
        if dev_mode:
            logging.info("DEV OTP for %s: %s", email, raw_code)
            return {"ok": True, "sent": False, "otp_debug": raw_code, "reason": "dev_mode"}
        raise HTTPException(status_code=503, detail={"code": "email_provider_missing"})

    out: Dict[str, Any] = {"ok": True, "sent": True}
    if dev_mode:
        logging.info("DEV OTP for %s: %s", email, raw_code)
        out.update({"sent": False, "otp_debug": raw_code, "reason": "dev_mode"})
        return out

    magic_link = _build_magic_redirect_url(payload.redirect_url, email, raw_code)
    _send_otp_email(email, raw_code, magic_link=magic_link)
    return out


@app.post("/auth/email/verify_otp")
def auth_email_verify_otp(payload: EmailOtpVerifyIn, request: Request, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    code = (payload.code or "").strip()
    now = now_utc()
    actor_ip = request.client.host if request.client else "unknown"
    enforce_rate_limit(EMAIL_OTP_VERIFY_SCOPE, f"{actor_ip}:{email}")

    latest = (
        db.query(AuthOtpCode)
        .filter(AuthOtpCode.email == email)
        .order_by(AuthOtpCode.created_at.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status_code=400, detail={"reason": "invalid_code"})

    if latest.used_at is not None:
        raise HTTPException(status_code=400, detail={"reason": "already_used"})

    if latest.expires_at <= now:
        raise HTTPException(status_code=400, detail={"reason": "expired_code"})

    if latest.attempts >= latest.max_attempts:
        raise HTTPException(status_code=429, detail={"reason": "too_many_attempts"})

    expected_hash = _otp_hash_code(email, code, latest.created_at)
    if latest.code_hash != expected_hash:
        latest.attempts += 1
        latest.last_attempt_at = now
        db.add(latest)
        db.commit()
        raise HTTPException(status_code=400, detail={"reason": "invalid_code"})

    latest.used_at = now
    latest.last_attempt_at = now

    created = False
    user = db.query(AppUser).filter(func.lower(AppUser.email) == email).first()
    if not user:
        created = True
        suffix = secrets.token_hex(2)
        user = AppUser(id=secrets.token_hex(16), display_name=f"User-{suffix}", email=email, is_guest=False)
        db.add(user)
        db.flush()

    latest.user_id = user.id
    tokens = _issue_auth_tokens(db, user)
    db.add(latest)
    db.commit()

    if created:
        _send_welcome_email(email)

    return {"token": tokens["access_token"], **tokens, "user": _user_snapshot(db, user), "created": created}


@app.post("/auth/email/request_link")
def auth_email_request_link(payload: MagicLinkRequestIn, request: Request, db: Session = Depends(get_db)):
    return auth_email_request_otp(EmailOtpRequestIn(email=payload.email, redirect_url=payload.redirect_url), request, db)


@app.post("/auth/email/verify_link")
def auth_email_verify_link(payload: MagicLinkVerifyIn, request: Request, db: Session = Depends(get_db)):
    token = (payload.token or "").strip()
    if len(token) != 6 or not token.isdigit():
        raise HTTPException(status_code=400, detail={"reason": "otp_required"})
    return auth_email_verify_otp(EmailOtpVerifyIn(email=payload.email, code=token), request, db)


@app.post("/auth/password/register")
def auth_password_register(payload: PasswordRegisterIn, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    existing = db.query(AppUser).filter(func.lower(AppUser.email) == email).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail={"reason": "email_already_registered"})

    nickname = payload.nickname.strip()
    display_name = nickname or f"{payload.first_name.strip()} {payload.last_name.strip()}".strip()
    password_hash = PWD_CONTEXT.hash(payload.password)
    user = AppUser(
        id=secrets.token_hex(16),
        display_name=display_name[:120],
        email=email,
        first_name=payload.first_name.strip()[:120],
        last_name=payload.last_name.strip()[:120],
        nickname=nickname[:120],
        password_hash=password_hash,
        is_guest=False,
    )
    db.add(user)
    db.flush()

    tokens = _issue_auth_tokens(db, user)
    db.commit()
    return {"created": True, **tokens, "user": _user_snapshot(db, user)}


@app.post("/auth/password/login")
def auth_password_login(payload: PasswordLoginIn, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    user = db.query(AppUser).filter(func.lower(AppUser.email) == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail={"reason": "invalid_credentials"})

    password_hash = (getattr(user, "password_hash", None) or "").strip()
    if not password_hash or not PWD_CONTEXT.verify(payload.password, password_hash):
        raise HTTPException(status_code=401, detail={"reason": "invalid_credentials"})

    tokens = _issue_auth_tokens(db, user)
    db.commit()
    return {**tokens, "user": _user_snapshot(db, user)}


@app.post("/auth/refresh")
def auth_refresh(payload: RefreshIn, db: Session = Depends(get_db)):
    token_hash = _hash_token((payload.refreshToken or "").strip())
    now = now_utc()

    row = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=401, detail={"reason": "invalid_refresh_token"})

    user = db.get(AppUser, row.user_id)
    if not user:
        row.revoked_at = now
        db.add(row)
        db.commit()
        raise HTTPException(status_code=401, detail={"reason": "user_not_found"})

    _enforce_user_sanctions(db, user)

    row.revoked_at = now
    db.add(row)
    tokens = _issue_auth_tokens(db, user)
    db.commit()
    return {**tokens, "user": _user_snapshot(db, user)}


@app.post("/auth/upgrade_guest")
def auth_upgrade_guest(payload: UpgradeGuestIn, user: AppUser = Depends(get_current_user)):
    return {
        "ok": True,
        "guest_device_id": payload.guest_device_id,
        "merge_policy": payload.merge_policy or "keep",
        "upgraded_user_id": user.id,
    }


@app.get("/auth/me")
def me(
    request: Request,
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
        pending_role_request = None
        try:
            pending_role_request = (
                s.query(RoleUpgradeRequest)
                .filter(RoleUpgradeRequest.user_id == user.id, RoleUpgradeRequest.status == "pending")
                .order_by(RoleUpgradeRequest.created_at.desc())
                .first()
            )
        except (OperationalError, ProgrammingError):
            logging.warning("role_upgrade_requests table missing or incompatible; fallback role_request_pending=null")
        return {
            "id": user.id,
            "display_name": user.display_name,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "address_text": user.address_text,
            "show_address": user.show_address,
            "show_avatar": user.show_avatar,
            "show_identity_to_staff": bool(settings and settings.show_identity_to_staff),
            "bio": user.bio,
            "oripeaux": user.oripeaux,
            "username": user.username,
            "city": user.city,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "nickname": user.nickname,
            "phone": user.phone,
            "instagram_handle": user.instagram_handle,
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
            "account_mode": (user.account_mode if user.account_mode in ALLOWED_ACCOUNT_MODES else "user"),
            "role_request_pending": (_serialize_role_upgrade_request(pending_role_request) if pending_role_request else None),
        }
    except Exception as exc:
        req_id = _request_id_from_request(request) if request else None
        logging.exception("Unhandled /auth/me failure for user_id=%s", getattr(user, "id", None), exc_info=exc)
        raise HTTPException(
            status_code=500,
            detail={
                "detail": "Internal Server Error",
                "code": "internal_error",
                "request_id": req_id,
            },
        )
    finally:
        s.close()


@app.patch("/auth/me")
def patch_me(payload: PatchMeIn, user: AppUser = Depends(get_current_user)):
    if user.is_guest:
        raise HTTPException(status_code=403, detail={"reason": "registered_account_required"})
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
        if payload.bio is not None:
            u.bio = payload.bio[:280]
        if payload.account_mode is not None:
            if payload.account_mode not in ALLOWED_ACCOUNT_MODES:
                raise HTTPException(status_code=422, detail={"detail": "Invalid account_mode", "code": "invalid_account_mode"})
            if payload.account_mode != "user":
                raise HTTPException(status_code=403, detail={"reason": "role_upgrade_requires_approval"})
            u.account_mode = payload.account_mode
        settings = s.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id == u.id).first()
        if payload.show_identity_to_staff is not None or payload.visibility is not None or payload.show_identity_in_bar is not None:
            if not settings:
                settings = AppUserPrivacySetting(user_id=u.id)
            if payload.show_identity_to_staff is not None:
                settings.show_identity_to_staff = payload.show_identity_to_staff
            if payload.visibility in {"public", "tore_users", "private"}:
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
            "bio": u.bio or "",
            "show_identity_to_staff": bool(refreshed_settings and refreshed_settings.show_identity_to_staff),
            "visibility": (refreshed_settings.visibility if refreshed_settings and refreshed_settings.visibility else "public"),
            "show_identity_in_bar": bool(refreshed_settings and (refreshed_settings.show_identity_in_bar or refreshed_settings.show_identity_to_staff)),
            "account_mode": (u.account_mode if u.account_mode in ALLOWED_ACCOUNT_MODES else "user"),
        }
    finally:
        s.close()


@app.post("/auth/role/request-upgrade")
def auth_role_request_upgrade(payload: RoleUpgradeRequestIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    requested_mode = payload.requested_mode
    if requested_mode == "user":
        raise HTTPException(status_code=400, detail={"reason": "user_mode_does_not_require_request"})

    expected_code = ORGA_CODE if requested_mode == "organizer" else TEAM_CODE
    provided_code = (payload.code or "").strip()
    if not expected_code or provided_code != expected_code:
        raise HTTPException(status_code=403, detail={"reason": "invalid_role_code"})

    existing_pending = (
        db.query(RoleUpgradeRequest)
        .filter(
            RoleUpgradeRequest.user_id == user.id,
            RoleUpgradeRequest.requested_mode == requested_mode,
            RoleUpgradeRequest.status == "pending",
        )
        .order_by(RoleUpgradeRequest.created_at.desc())
        .first()
    )
    if existing_pending:
        return {"request": _serialize_role_upgrade_request(existing_pending), "idempotent": True}

    row = RoleUpgradeRequest(user_id=user.id, requested_mode=requested_mode, status="pending")
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"request": _serialize_role_upgrade_request(row), "idempotent": False}


@app.get("/admin/role-requests")
def admin_role_requests(
    status: str = Query(default="pending"),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[int] = Query(default=None),
    _: str = Depends(_require_admin_api_key),
    db: Session = Depends(get_db),
):
    normalized = (status or "pending").strip().lower()
    if normalized not in {"pending", "approved", "rejected"}:
        raise HTTPException(status_code=422, detail={"reason": "invalid_status"})

    q = db.query(RoleUpgradeRequest).filter(RoleUpgradeRequest.status == normalized)
    if cursor is not None:
        q = q.filter(RoleUpgradeRequest.id < cursor)
    rows = q.order_by(RoleUpgradeRequest.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    clipped = rows[:limit]
    next_cursor = clipped[-1].id if has_more and clipped else None
    return {"items": [_serialize_role_upgrade_request(row) for row in clipped], "next_cursor": next_cursor}


@app.patch("/admin/role-requests/{request_id}")
def admin_role_requests_review(
    request_id: int,
    payload: RoleUpgradeReviewIn,
    _: str = Depends(_require_admin_api_key),
    db: Session = Depends(get_db),
):
    row = db.get(RoleUpgradeRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail={"reason": "request_not_found"})
    if row.status != "pending":
        return {"request": _serialize_role_upgrade_request(row), "idempotent": True}

    row.reviewed_at = now_utc()
    row.reviewed_by = "admin"
    row.note = payload.note
    if payload.action == "approve":
        user = db.get(AppUser, row.user_id)
        if not user:
            raise HTTPException(status_code=404, detail={"reason": "user_not_found"})
        user.account_mode = row.requested_mode
        db.add(user)
        row.status = "approved"
    else:
        row.status = "rejected"
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"request": _serialize_role_upgrade_request(row), "idempotent": False}


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


def _is_public_event_available(event: Event, *, now: Optional[datetime] = None) -> bool:
    current = now or now_utc()
    return (
        (event.visibility or "PRIVATE").upper() == "PUBLIC"
        and (event.publication_status or "DRAFT").upper() == "PUBLISHED"
        and (event.ends_at is None or event.ends_at >= current)
    )


@app.get("/bars")
def list_bars(limit: int = Query(100, ge=1, le=300), db: Session = Depends(get_db)):
    now = now_utc()
    rows = (
        db.query(Bar)
        .filter(
            func.upper(Bar.partner_status) == "ACTIVE",
            func.upper(Bar.public_visibility) == "PUBLIC",
        )
        .order_by(Bar.id.asc())
        .limit(limit)
        .all()
    )
    output: list[dict[str, Any]] = []

    for row in rows:
        events = (
            db.query(Event)
            .filter(
                Event.bar_id == row.id,
                func.upper(Event.visibility) == "PUBLIC",
                func.upper(Event.publication_status) == "PUBLISHED",
                Event.ends_at >= now,
            )
            .order_by(Event.starts_at.desc())
            .limit(8)
            .all()
        )
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
                "description": row.public_description,
                "logoUrl": row.logo_url,
                "bannerUrl": row.banner_url,
                "primaryColor": row.primary_color,
                "secondaryColor": row.secondary_color,
                "address": row.address,
                "practicalInfo": row.practical_info,
                "mapUrl": row.map_url,
                "lat": row.lat,
                "lng": row.lng,
                "modules": sorted([key for key, enabled in (row.public_modules or {}).items() if enabled]),
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
    rows = (
        db.query(Event)
        .filter(
            Event.bar_id == bar_id,
            func.upper(Event.visibility) == "PUBLIC",
            func.upper(Event.publication_status) == "PUBLISHED",
            Event.ends_at >= now,
        )
        .order_by(Event.starts_at.asc())
        .all()
    )
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
                "shortDescription": row.short_description,
                "bannerUrl": row.banner_url,
                "thumbnailUrl": row.thumbnail_url,
                "eventType": row.event_type,
                "capacity": row.capacity,
                "accessType": row.access_type,
                "priceCents": row.entry_price_cents,
                "currency": (row.currency or "EUR").upper(),
                "address": row.address or bar.address,
                "city": row.city or bar.city,
                "lat": row.lat if row.lat is not None else bar.lat,
                "lng": row.lng if row.lng is not None else bar.lng,
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
        "checkin": bool(getattr(cfg, "checkin_enabled", cfg.checkins_enabled)),
        "battles": bool(cfg.battles_enabled),
        "hunt": bool(cfg.hunt_enabled),
        "report": bool(getattr(cfg, "report_enabled", cfg.safety_enabled)),
        "polymarket": polymarket_enabled,
        "polymarket_event": polymarket_enabled,
        "classement": bool(getattr(cfg, "report_enabled", cfg.safety_enabled)),
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
        "serverTime": now_utc().isoformat(),
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
    query: Optional[str] = Query(default=None, max_length=120),
    status: Optional[Literal["LIVE", "TONIGHT", "UPCOMING"]] = None,
    city: Optional[str] = Query(default=None, max_length=120),
    bar_id: Optional[int] = Query(default=None, ge=1),
    structure_id: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
):
    now = now_utc()
    request = db.query(Event).filter(
        func.upper(Event.visibility) == "PUBLIC",
        func.upper(Event.publication_status) == "PUBLISHED",
        Event.ends_at >= now,
    )
    if bar_id is not None:
        request = request.filter(Event.bar_id == bar_id)
    normalized_city = (city or "").strip()
    if normalized_city:
        matching_city_bar_ids = select(Bar.id).where(
            func.lower(func.replace(Bar.city, "è", "e"))
            == normalized_city.lower().replace("è", "e")
        )
        request = request.filter(Event.bar_id.in_(matching_city_bar_ids))
    if structure_id is not None:
        request = request.filter(
            func.lower(Event.host_type) == "orga",
            Event.host_id == str(structure_id),
        )
    normalized_query = (query or "").strip()
    if normalized_query:
        like = f"%{normalized_query}%"
        matching_bar_ids = select(Bar.id).where(
            or_(Bar.name.ilike(like), Bar.city.ilike(like))
        )
        matching_org_ids = select(func.cast(Organization.id, String)).where(
            or_(
                Organization.name.ilike(like),
                Organization.description.ilike(like),
                Organization.city.ilike(like),
            )
        )
        request = request.filter(
            or_(
                Event.name.ilike(like),
                Event.venue.ilike(like),
                Event.host_display_name.ilike(like),
                Event.bar_id.in_(matching_bar_ids),
                and_(
                    func.lower(Event.host_type) == "orga",
                    Event.host_id.in_(matching_org_ids),
                ),
            )
        )

    if status == "LIVE":
        request = request.filter(Event.starts_at <= now, Event.ends_at >= now)
    elif status == "TONIGHT":
        aware_now = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        local_now = aware_now.astimezone(ZoneInfo("Europe/Brussels"))
        local_end = (local_now + timedelta(days=1)).replace(
            hour=7, minute=0, second=0, microsecond=0
        )
        if local_now.hour < 7:
            local_start = (local_now - timedelta(days=1)).replace(
                hour=17, minute=0, second=0, microsecond=0
            )
        else:
            local_start = local_now.replace(hour=17, minute=0, second=0, microsecond=0)
        start_utc = local_start.astimezone(timezone.utc).replace(tzinfo=None)
        end_utc = local_end.astimezone(timezone.utc).replace(tzinfo=None)
        request = request.filter(
            Event.starts_at < end_utc,
            Event.ends_at > start_utc,
        )
    elif status == "UPCOMING":
        request = request.filter(Event.starts_at > now)

    rows = request.order_by(Event.starts_at.asc()).limit(limit).all()
    bar_ids = {row.bar_id for row in rows if row.bar_id is not None}
    bars_by_id = (
        {bar.id: bar for bar in db.query(Bar).filter(Bar.id.in_(bar_ids)).all()}
        if bar_ids
        else {}
    )
    output: list[EventSummaryOut] = []
    for row in rows:
        runtime = db.query(EventRuntimeState).filter(
            EventRuntimeState.event_id == row.id
        ).first()
        runtime_state = (
            (runtime.state if runtime else None) or row.event_state or "LIVE"
        ).upper()
        timing_status = "LIVE" if row.starts_at <= now <= row.ends_at else "UPCOMING"
        bar = bars_by_id.get(row.bar_id)
        output.append(
            EventSummaryOut(
                id=row.id,
                bar_id=row.bar_id,
                name=row.name,
                starts_at=row.starts_at,
                ends_at=row.ends_at,
                entry_price_cents=row.entry_price_cents,
                ticket_mode=row.ticket_mode,
                ticket_value_cents=row.ticket_value_cents,
                status=timing_status,
                eventState=runtime_state,
                venue=row.venue or (bar.name if bar else None),
                barName=bar.name if bar else None,
                city=bar.city if bar else None,
                host=_event_public_host_summary(db, row),
                modulesOn=_compact_public_modules(db, row.id),
                visibility=(row.visibility or "PRIVATE").upper(),
                publicationStatus=(row.publication_status or "DRAFT").upper(),
                shortDescription=row.short_description,
                bannerUrl=row.banner_url,
                thumbnailUrl=row.thumbnail_url,
                eventType=row.event_type,
                capacity=row.capacity,
                accessType=row.access_type,
                currency=(row.currency or "EUR").upper(),
                address=row.address or (bar.address if bar else None),
                lat=row.lat if row.lat is not None else (bar.lat if bar else None),
                lng=row.lng if row.lng is not None else (bar.lng if bar else None),
            )
        )
    return output


def _public_bar_payload(bar: Bar) -> dict[str, Any]:
    return {
        "id": bar.id,
        "name": bar.name,
        "city": bar.city,
        "description": bar.public_description,
        "logoUrl": bar.logo_url,
        "bannerUrl": bar.banner_url,
        "primaryColor": bar.primary_color,
        "secondaryColor": bar.secondary_color,
        "address": bar.address,
        "practicalInfo": bar.practical_info,
        "mapUrl": bar.map_url,
        "lat": bar.lat,
        "lng": bar.lng,
        "modules": sorted([key for key, enabled in (bar.public_modules or {}).items() if enabled]),
    }


@app.get("/bars/{bar_id}/public")
def get_bar_public(bar_id: int, db: Session = Depends(get_db)):
    bar = db.get(Bar, bar_id)
    if (
        bar is None
        or (bar.partner_status or "ACTIVE").upper() != "ACTIVE"
        or (bar.public_visibility or "PUBLIC").upper() != "PUBLIC"
    ):
        raise HTTPException(404, "Bar not found")
    return _public_bar_payload(bar)


@app.get("/events/{event_id}")
def get_event(event_id: int, _user: AppUser = Depends(get_current_user)):
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


def _event_public_host_summary(db: Session, event: Event) -> dict[str, Any]:
    host_name = event.host_display_name
    instagram: Optional[str] = None
    host_type = (event.host_type or "user").lower()
    host_id = (event.host_id or "").strip()
    if host_type == "orga" and host_id.isdigit():
        org = db.get(Organization, int(host_id))
        if org is not None:
            host_name = host_name or org.name
            instagram = org.instagram_handle
    elif host_type == "user" and host_id:
        user = db.get(AppUser, host_id)
        if user is not None:
            host_name = host_name or user.display_name
            instagram = user.instagram_handle
    return {
        "type": host_type,
        "name": host_name,
        "instagram": instagram,
    }


def _compact_public_modules(db: Session, event_id: int) -> list[str]:
    modules = _event_modules_on(db, event_id)
    return sorted([key for key, enabled in modules.items() if enabled])


def _event_public_payload(db: Session, event: Event) -> dict[str, Any]:
    runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event.id).first()
    runtime_state = ((runtime.state if runtime else None) or "LIVE").upper()
    public_base = _public_app_base_url()
    bar = db.get(Bar, event.bar_id) if event.bar_id else None
    return {
        "id": event.id,
        "name": event.name,
        "startAt": event.starts_at.isoformat() if event.starts_at else None,
        "endAt": event.ends_at.isoformat() if event.ends_at else None,
        "venue": {
            "name": event.venue or (bar.name if bar else None),
            "barName": (bar.name if bar else None),
            "barId": (bar.id if bar else None),
            "address": event.address or (bar.address if bar else None),
            "city": event.city or (bar.city if bar else None),
            "lat": event.lat if event.lat is not None else (bar.lat if bar else None),
            "lng": event.lng if event.lng is not None else (bar.lng if bar else None),
            "mapUrl": (bar.map_url if bar else None),
        },
        "host": _event_public_host_summary(db, event),
        "modulesOn": _compact_public_modules(db, event.id),
        "eventState": runtime_state,
        "pricing": {
            "entryPriceCents": event.entry_price_cents,
            "isFree": event.entry_price_cents <= 0,
            "currency": (event.currency or "EUR").upper(),
        },
        "accessPolicy": {
            "visibility": (event.visibility or "PRIVATE").upper(),
            "type": (event.access_type or ("TICKET" if event.ticket_mode else "OPEN")).upper(),
            "charterRequired": bool(event.charter_enabled),
            "charterVersion": event.charter_version,
        },
        "description": event.public_description,
        "shortDescription": event.short_description,
        "bannerUrl": event.banner_url,
        "thumbnailUrl": event.thumbnail_url,
        "eventType": event.event_type,
        "capacity": event.capacity,
        "links": {
            "webUrl": f"{public_base}/event/{event.id}",
            "openUrl": f"{public_base}/open?type=event&id={event.id}",
            "deeplink": f"tore://open?type=event&id={event.id}",
        },
        "flags": {
            "canJoin": runtime_state not in {"CLOSED", "FROZEN"},
        },
    }


def _join_code_private_preview(event: Event) -> dict[str, Any]:
    start_hint = None
    if event.starts_at is not None:
        start_hint = event.starts_at.replace(minute=0, second=0, microsecond=0).isoformat()
    host_hint = None
    if (event.host_type or "").strip():
        host_hint = f"Host {event.host_type.strip().lower()}"
    return {
        "exists": True,
        "requiresAuth": True,
        "titleHint": "Event privé TORÈ",
        "startAtHint": start_hint,
        "hostHint": host_hint,
    }


@app.get("/events/{event_id}/public")
def get_event_public(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if not _is_public_event_available(event):
        raise HTTPException(status_code=404, detail={"reason": "public_event_not_available"})
    return _event_public_payload(db, event)


@app.get("/events/join_code/preview", response_model=JoinCodePreviewOut)
def preview_join_code(code: str, db: Session = Depends(get_db)):
    normalized = (code or "").strip().upper()
    if not normalized:
        raise HTTPException(status_code=404, detail={"reason": "invalid_code"})
    event = db.query(Event).filter(Event.event_code == normalized).first()
    if event is None:
        raise HTTPException(status_code=404, detail={"reason": "invalid_code"})
    if (event.visibility or "PRIVATE").upper() == "PRIVATE":
        return _join_code_private_preview(event)
    if not _is_public_event_available(event):
        raise HTTPException(status_code=404, detail={"reason": "invalid_code"})
    return {
        "exists": True,
        "requiresAuth": False,
        "public": _event_public_payload(db, event),
    }


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


@app.post("/events/{event_id}/join_public")
def join_event_public(
    event_id: int,
    payload: JoinEventIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if not _is_public_event_available(event):
        raise HTTPException(status_code=404, detail={"reason": "public_event_not_available"})
    key = ensure_idempotency_key(idempotency_key)
    if event.charter_enabled and payload.accepted_charter_version != event.charter_version:
        return {
            "charter_required": True,
            "charter_version": event.charter_version,
            "event_id": event.id,
            "eventState": _event_public_payload(db, event)["eventState"],
            "modulesOn": _compact_public_modules(db, event.id),
        }
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
    code = canonicalize_manual_code(payload.code)
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


def _committee_space_mod_or_owner(membership: CommitteeMembership) -> None:
    if (membership.role or "MEMBER").upper() not in {"OWNER", "ADMIN", "MOD"}:
        raise HTTPException(status_code=403, detail={"reason": "forbidden"})


def _committee_post_payload(db: Session, row: CommitteePost) -> dict[str, Any]:
    actor = db.get(AppUser, row.created_by)
    return {
        "id": row.id,
        "committeeId": row.committee_id,
        "title": row.title,
        "body": row.body,
        "isPinned": bool(row.is_pinned),
        "createdBy": row.created_by,
        "createdByDisplayName": actor.display_name if actor else row.created_by,
        "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
    }


def _committee_calendar_payload(row: CommitteeCalendarItem) -> dict[str, Any]:
    return {
        "id": row.id,
        "committeeId": row.committee_id,
        "title": row.title,
        "date": row.date,
        "location": row.location,
        "notes": row.notes,
        "createdBy": row.created_by,
        "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
    }


def _committee_expense_payload(row: CommitteeExpense) -> dict[str, Any]:
    return {
        "id": row.id,
        "committeeId": row.committee_id,
        "amountCents": row.amount_cents,
        "label": row.label,
        "category": row.category,
        "date": row.date,
        "createdBy": row.created_by,
        "createdAt": row.created_at.isoformat(),
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


@app.get("/committees/{committee_id}/space")
def committee_space_me(
    committee_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    membership = _require_committee_member(db, committee_id, user)
    return {
        "committeeId": committee_id,
        "membership": {
            "userId": membership.user_id,
            "role": membership.role,
        },
        "sections": ["feed", "calendar", "expenses"],
    }


@app.get("/committees/{committee_id}/feed/posts")
def committee_feed_posts(
    committee_id: int,
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_member(db, committee_id, user)
    q = db.query(CommitteePost).filter(CommitteePost.committee_id == committee_id, CommitteePost.is_deleted.is_(False))
    if cursor:
        try:
            ts_iso, raw_id = cursor.split("|", 1)
            ts = datetime.fromisoformat(ts_iso)
            post_id = int(raw_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail={"reason": "bad_cursor"}) from exc
        q = q.filter(
            (CommitteePost.is_pinned.is_(True) & ((CommitteePost.created_at < ts) | ((CommitteePost.created_at == ts) & (CommitteePost.id < post_id))))
            | (CommitteePost.is_pinned.is_(False) & ((CommitteePost.created_at < ts) | ((CommitteePost.created_at == ts) & (CommitteePost.id < post_id))))
        )
    rows = q.order_by(CommitteePost.is_pinned.desc(), CommitteePost.created_at.desc(), CommitteePost.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = None
    if has_more and page:
        last = page[-1]
        next_cursor = f"{last.created_at.isoformat()}|{last.id}"
    return {"items": [_committee_post_payload(db, row) for row in page], "nextCursor": next_cursor}


@app.post("/committees/{committee_id}/feed/posts")
def committee_feed_create_post(
    committee_id: int,
    payload: CommitteeSpacePostIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    membership = _require_committee_member(db, committee_id, user)
    _committee_space_mod_or_owner(membership)
    row = CommitteePost(
        committee_id=committee_id,
        title=payload.title.strip(),
        body=payload.body.strip(),
        is_pinned=bool(payload.pinned),
        created_by=user.id,
        updated_at=now_utc(),
    )
    db.add(row)
    db.flush()
    response = _committee_post_payload(db, row)
    write_audit_log(db, actor_partner_id=None, actor_role='app_user', action='committee.space.feed.create', entity_type='committee_post', entity_id=str(row.id), event_id=None, bar_id=None, committee_id=committee_id, payload={'committee_id': committee_id})
    db.commit()
    return response


@app.put("/committees/{committee_id}/feed/posts/{post_id}")
def committee_feed_update_post(
    committee_id: int,
    post_id: int,
    payload: CommitteeSpacePostIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    membership = _require_committee_member(db, committee_id, user)
    _committee_space_mod_or_owner(membership)
    row = db.get(CommitteePost, post_id)
    if row is None or row.committee_id != committee_id or row.is_deleted:
        raise HTTPException(status_code=404, detail={"reason": "post_not_found"})
    row.title = payload.title.strip()
    row.body = payload.body.strip()
    row.is_pinned = bool(payload.pinned)
    row.updated_at = now_utc()
    db.add(row)
    response = _committee_post_payload(db, row)
    write_audit_log(db, actor_partner_id=None, actor_role='app_user', action='committee.space.feed.update', entity_type='committee_post', entity_id=str(row.id), event_id=None, bar_id=None, committee_id=committee_id, payload={'committee_id': committee_id})
    db.commit()
    return response


@app.delete("/committees/{committee_id}/feed/posts/{post_id}")
def committee_feed_delete_post(
    committee_id: int,
    post_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    membership = _require_committee_member(db, committee_id, user)
    _committee_space_mod_or_owner(membership)
    row = db.get(CommitteePost, post_id)
    if row is None or row.committee_id != committee_id or row.is_deleted:
        raise HTTPException(status_code=404, detail={"reason": "post_not_found"})
    row.is_deleted = True
    row.updated_at = now_utc()
    db.add(row)
    write_audit_log(db, actor_partner_id=None, actor_role='app_user', action='committee.space.feed.delete', entity_type='committee_post', entity_id=str(row.id), event_id=None, bar_id=None, committee_id=committee_id, payload={'committee_id': committee_id})
    db.commit()
    return {"ok": True}


@app.get("/committees/{committee_id}/calendar/items")
def committee_calendar_items(
    committee_id: int,
    month: Optional[str] = Query(default=None, min_length=7, max_length=7),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_member(db, committee_id, user)
    q = db.query(CommitteeCalendarItem).filter(CommitteeCalendarItem.committee_id == committee_id)
    if month:
        q = q.filter(CommitteeCalendarItem.date.like(f"{month}%"))
    rows = q.order_by(CommitteeCalendarItem.date.asc(), CommitteeCalendarItem.id.asc()).all()
    return {"items": [_committee_calendar_payload(row) for row in rows], "month": month}


@app.post("/committees/{committee_id}/calendar/items")
def committee_calendar_create_item(
    committee_id: int,
    payload: CommitteeSpaceCalendarIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    membership = _require_committee_member(db, committee_id, user)
    _committee_space_mod_or_owner(membership)
    row = CommitteeCalendarItem(
        committee_id=committee_id,
        title=payload.title.strip(),
        date=payload.date,
        location=(payload.location or '').strip() or None,
        notes=(payload.notes or '').strip() or None,
        created_by=user.id,
        updated_at=now_utc(),
    )
    db.add(row)
    db.flush()
    response = _committee_calendar_payload(row)
    write_audit_log(db, actor_partner_id=None, actor_role='app_user', action='committee.space.calendar.create', entity_type='committee_calendar_item', entity_id=str(row.id), event_id=None, bar_id=None, committee_id=committee_id, payload={'committee_id': committee_id})
    db.commit()
    return response


@app.put("/committees/{committee_id}/calendar/items/{item_id}")
def committee_calendar_update_item(
    committee_id: int,
    item_id: int,
    payload: CommitteeSpaceCalendarIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    membership = _require_committee_member(db, committee_id, user)
    _committee_space_mod_or_owner(membership)
    row = db.get(CommitteeCalendarItem, item_id)
    if row is None or row.committee_id != committee_id:
        raise HTTPException(status_code=404, detail={"reason": "calendar_item_not_found"})
    row.title = payload.title.strip()
    row.date = payload.date
    row.location = (payload.location or '').strip() or None
    row.notes = (payload.notes or '').strip() or None
    row.updated_at = now_utc()
    db.add(row)
    response = _committee_calendar_payload(row)
    write_audit_log(db, actor_partner_id=None, actor_role='app_user', action='committee.space.calendar.update', entity_type='committee_calendar_item', entity_id=str(row.id), event_id=None, bar_id=None, committee_id=committee_id, payload={'committee_id': committee_id})
    db.commit()
    return response


@app.delete("/committees/{committee_id}/calendar/items/{item_id}")
def committee_calendar_delete_item(
    committee_id: int,
    item_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    membership = _require_committee_member(db, committee_id, user)
    _committee_space_mod_or_owner(membership)
    row = db.get(CommitteeCalendarItem, item_id)
    if row is None or row.committee_id != committee_id:
        raise HTTPException(status_code=404, detail={"reason": "calendar_item_not_found"})
    db.delete(row)
    write_audit_log(db, actor_partner_id=None, actor_role='app_user', action='committee.space.calendar.delete', entity_type='committee_calendar_item', entity_id=str(row.id), event_id=None, bar_id=None, committee_id=committee_id, payload={'committee_id': committee_id})
    db.commit()
    return {"ok": True}


@app.get("/committees/{committee_id}/expenses")
def committee_expenses(
    committee_id: int,
    month: Optional[str] = Query(default=None, min_length=7, max_length=7),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_member(db, committee_id, user)
    q = db.query(CommitteeExpense).filter(CommitteeExpense.committee_id == committee_id)
    if month:
        q = q.filter(CommitteeExpense.date.like(f"{month}%"))
    if cursor:
        try:
            d, raw_id = cursor.split("|", 1)
            expense_id = int(raw_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail={"reason": "bad_cursor"}) from exc
        q = q.filter((CommitteeExpense.date < d) | ((CommitteeExpense.date == d) & (CommitteeExpense.id < expense_id)))
    rows = q.order_by(CommitteeExpense.date.desc(), CommitteeExpense.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = None
    if has_more and page:
        last = page[-1]
        next_cursor = f"{last.date}|{last.id}"
    totals: dict[str, int] = {}
    if month:
        grouped = db.query(CommitteeExpense.category, func.sum(CommitteeExpense.amount_cents)).filter(
            CommitteeExpense.committee_id == committee_id,
            CommitteeExpense.date.like(f"{month}%"),
        ).group_by(CommitteeExpense.category).all()
        totals = {category: int(total or 0) for category, total in grouped}
    return {"items": [_committee_expense_payload(row) for row in page], "nextCursor": next_cursor, "totalsByCategory": totals}


@app.post("/committees/{committee_id}/expenses")
def committee_expenses_create(
    committee_id: int,
    payload: CommitteeSpaceExpenseIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    membership = _require_committee_member(db, committee_id, user)
    _committee_space_mod_or_owner(membership)
    row = CommitteeExpense(
        committee_id=committee_id,
        amount_cents=payload.amountCents,
        label=payload.label.strip(),
        category=payload.category.strip(),
        date=payload.date,
        created_by=user.id,
        updated_at=now_utc(),
    )
    db.add(row)
    db.flush()
    response = _committee_expense_payload(row)
    write_audit_log(db, actor_partner_id=None, actor_role='app_user', action='committee.space.expense.create', entity_type='committee_expense', entity_id=str(row.id), event_id=None, bar_id=None, committee_id=committee_id, payload={'committee_id': committee_id})
    db.commit()
    return response


@app.get("/committees/{committee_id}/expenses/export.json")
def committee_expenses_export_json(
    committee_id: int,
    month: Optional[str] = Query(default=None, min_length=7, max_length=7),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_committee_module()
    _require_committee_member(db, committee_id, user)
    q = db.query(CommitteeExpense).filter(CommitteeExpense.committee_id == committee_id)
    if month:
        q = q.filter(CommitteeExpense.date.like(f"{month}%"))
    rows = q.order_by(CommitteeExpense.date.asc(), CommitteeExpense.id.asc()).all()
    total = sum(row.amount_cents for row in rows)
    return {
        "committeeId": committee_id,
        "month": month,
        "count": len(rows),
        "totalCents": total,
        "items": [_committee_expense_payload(row) for row in rows],
        "generatedAt": now_utc().isoformat(),
    }


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


def _app_event_runtime_payload(db: Session, event: Event) -> dict:
    runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event.id).first()
    state = ((runtime.state if runtime else None) or (event.event_state or "LIVE")).upper()
    updated = runtime.updated_at if runtime and runtime.updated_at else event.last_state_updated_at
    return {"eventState": state, "lastUpdatedAt": updated.isoformat() if updated else None}


def _public_app_base_url() -> str:
    return (
        os.getenv("PUBLIC_URL")
        or os.getenv("BASE_URL")
        or os.getenv("TORE_PUBLIC_APP_URL")
        or "https://app.tore.be"
    ).rstrip("/")


def _app_event_share_payload(event: Event, public_base_url: str | None = None, include_staff: bool = False) -> dict:
    public_base_url = (public_base_url or _public_app_base_url()).rstrip("/")
    event_code = event.event_code
    deeplink = f"tore://open?type=event&id={event.id}"
    web_url = f"{public_base_url}/open?type=event&id={event.id}"
    payload = {
        "webUrl": web_url,
        "deeplink": deeplink,
        "qrPayload": f"tore://join_event?event_id={event.id}",
        "title": event.name,
        "description": f"Ouvrir {event.name} dans TORÈ",
        "https_link": web_url,
        "qr_payload_join": f"tore://join_event?event_id={event.id}",
        "event_code": event_code,
    }
    if include_staff:
        payload["staff_invite"] = {
            "deeplink": f"tore://event/staff_invite?event_id={event.id}",
            "qr_payload": f"tore://staff_invite?event_id={event.id}",
        }
    return payload




def _staff_invite_status(invite: EventStaffInviteCode) -> str:
    now = now_utc()
    if invite.status == "REVOKED" or invite.revoked_at is not None:
        return "REVOKED"
    if invite.expires_at and now > invite.expires_at:
        return "EXPIRED"
    return "ACTIVE"


def _event_runtime_state(db: Session, event_id: int) -> str:
    runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).first()
    return ((runtime.state if runtime else None) or "LIVE").upper()


def _guard_event_write_runtime(db: Session, event_id: int, *, critical_write: bool = False) -> str:
    state = _event_runtime_state(db, event_id)
    if state in {"CLOSED", "FROZEN"}:
        raise HTTPException(status_code=423, detail={"reason": f"event_{state.lower()}", "eventState": state})
    if critical_write and state == "DEGRADED":
        raise HTTPException(status_code=423, detail={"reason": "event_degraded_write_blocked", "eventState": state})
    return state


def _staff_invite_public_payload(invite: EventStaffInviteCode, *, public_base_url: str | None = None) -> dict[str, Any]:
    public_base_url = (public_base_url or _public_app_base_url()).rstrip("/")
    code = (invite.code or "").upper()
    return {
        "role": (invite.role or "").upper(),
        "code": code,
        "expiresAt": invite.expires_at.isoformat() if invite.expires_at else None,
        "status": _staff_invite_status(invite),
        "webUrl": f"{public_base_url}/open?type=staff_invite&code={code}",
        "deeplink": f"tore://open?type=staff_invite&code={code}",
        "qrPayload": f"tore://open?type=staff_invite&code={code}",
    }


_BACKUP_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _normalize_backup_code(raw: str | None) -> str:
    return "".join(ch for ch in (raw or "").strip().upper() if ch in _BACKUP_CODE_ALPHABET)


def _normalize_manual_code(raw: str | None) -> str:
    value = (raw or '').strip().upper()
    compact = re.sub(r'[\s-]+', '', value)
    if compact and not re.fullmatch(r'[A-Z0-9:]+', compact):
        return ''
    return compact


def canonicalize_manual_code(raw: str | None) -> str:
    return _normalize_manual_code(raw)


def _manual_code_suffix_hash(code: str) -> str:
    suffix = (code or "")[-4:]
    return hashlib.sha256(suffix.encode("utf-8")).hexdigest()[:16]



def _generate_backup_code(length: int = 8) -> str:
    return "".join(secrets.choice(_BACKUP_CODE_ALPHABET) for _ in range(length))


def _hash_staff_backup_code(event_id: int, code: str) -> str:
    material = f"{event_id}:{_normalize_backup_code(code)}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _staff_backup_status(item: EventStaffBackupCode) -> str:
    now = now_utc()
    if item.used_at is not None:
        return "USED"
    if item.status == "REVOKED" or item.revoked_at is not None:
        return "REVOKED"
    if item.expires_at and now > item.expires_at:
        return "EXPIRED"
    return "ACTIVE"


def _staff_backup_admin_payload(item: EventStaffBackupCode) -> dict[str, Any]:
    return {
        "id": item.id,
        "role": (item.role or "").upper(),
        "status": _staff_backup_status(item),
        "expiresAt": item.expires_at.isoformat() if item.expires_at else None,
        "suffix4": item.suffix4,
        "usedAt": item.used_at.isoformat() if item.used_at else None,
        "revokedAt": item.revoked_at.isoformat() if item.revoked_at else None,
    }


def _staff_backup_open_payload(event_id: int, code: str, *, public_base_url: str | None = None) -> dict[str, str]:
    public_base_url = (public_base_url or _public_app_base_url()).rstrip("/")
    normalized = _normalize_backup_code(code)
    return {
        "webUrl": f"{public_base_url}/open?type=staff_backup&eventId={event_id}&code={normalized}",
        "deeplink": f"tore://open?type=staff_backup&eventId={event_id}&code={normalized}",
        "qrPayload": f"tore://open?type=staff_backup&eventId={event_id}&code={normalized}",
    }


def _staff_invite_current_role_payload(invite: EventStaffInviteCode | None, *, public_base_url: str | None = None) -> dict[str, Any] | None:
    if invite is None:
        return None
    payload = _staff_invite_public_payload(invite, public_base_url=public_base_url)
    return {
        "code": payload["code"],
        "status": payload["status"],
        "expiresAt": payload["expiresAt"],
        "openUrl": payload["webUrl"],
        "webUrl": payload["webUrl"],
    }


def _event_share_pack_payload(db: Session, event: Event, *, include_staff: bool) -> dict[str, Any]:
    public_base = _public_app_base_url()
    share = _app_event_share_payload(event, public_base_url=public_base, include_staff=include_staff)
    module_cfg = db.query(EventModuleConfig).filter(EventModuleConfig.event_id == event.id).first()

    links: dict[str, Any] = {
        "publicShare": {"webUrl": share["webUrl"], "deeplink": share["deeplink"]},
        "joinPublic": {
            "webUrl": f"{public_base}/open?type=join&code={(event.event_code or '').upper()}",
            "deeplink": f"tore://open?type=join&code={(event.event_code or '').upper()}",
        } if event.event_code else None,
    }
    if include_staff:
        invites = (
            db.query(EventStaffInviteCode)
            .filter(EventStaffInviteCode.event_id == event.id)
            .order_by(EventStaffInviteCode.created_at.desc())
            .all()
        )
        links["staffInvites"] = [_staff_invite_public_payload(item, public_base_url=public_base) for item in invites]
        links["staffBackupPrintUrl"] = f"{public_base}/orga/events/{event.id}/staff-backup/print"
    if module_cfg and module_cfg.hunt_enabled:
        links["hunts"] = {"webUrl": f"{public_base}/events/{event.id}/hunt", "deeplink": f"tore://open?type=event&id={event.id}&module=hunts"}
    if module_cfg and module_cfg.battles_enabled:
        links["battles"] = {"webUrl": f"{public_base}/events/{event.id}/battles", "deeplink": f"tore://open?type=event&id={event.id}&module=battles"}

    if module_cfg and module_cfg.entry_enabled:
        entry_invite = (
            db.query(EventStaffInviteCode)
            .filter(EventStaffInviteCode.event_id == event.id, EventStaffInviteCode.role == "ENTRY")
            .order_by(EventStaffInviteCode.created_at.desc())
            .first()
        )
    else:
        entry_invite = None
    bar_invite = (
        db.query(EventStaffInviteCode)
        .filter(EventStaffInviteCode.event_id == event.id, EventStaffInviteCode.role == "BAR")
        .order_by(EventStaffInviteCode.created_at.desc())
        .first()
    ) if module_cfg and module_cfg.orders_enabled else None

    qr = {
        "join": f"tore://join_event?event_id={event.id}",
        "entryStaff": f"tore://open?type=staff_invite&code={(entry_invite.code if entry_invite else '')}" if entry_invite else None,
        "barStaff": f"tore://open?type=staff_invite&code={(bar_invite.code if bar_invite else '')}" if bar_invite else None,
    }

    return {
        "serverTime": now_utc().isoformat(),
        "event": {
            "id": event.id,
            "name": event.name,
            "visibility": (event.visibility or "PRIVATE").upper(),
            "publicationStatus": (event.publication_status or "DRAFT").upper(),
            "host": {"type": event.host_type, "id": event.host_id, "name": event.host_display_name},
            "startsAt": event.starts_at.isoformat() if event.starts_at else None,
            "venue": event.venue,
        },
        "links": {k: v for k, v in links.items() if v is not None},
        "qr": {k: v for k, v in qr.items() if v is not None},
    }


def _public_event_share_pack_payload(db: Session, event: Event) -> dict[str, Any]:
    base_pack = _event_share_pack_payload(db, event, include_staff=False)
    public_base = _public_app_base_url()
    open_url = f"{public_base}/open?type=event&id={event.id}"
    links = base_pack.get("links", {})
    public_links = {
        "publicShare": links.get("publicShare"),
        "joinPublic": links.get("joinPublic"),
        "open": {"webUrl": open_url, "deeplink": f"tore://open?type=event&id={event.id}"},
    }
    return {
        "event": {
            "id": event.id,
            "name": event.name,
            "visibility": (event.visibility or "PRIVATE").upper(),
            "publicationStatus": (event.publication_status or "DRAFT").upper(),
            "startsAt": event.starts_at.isoformat() if event.starts_at else None,
            "venue": event.venue,
        },
        "metadata": {
            "title": event.name,
            "description": f"Ouvrir {event.name} dans TORÈ",
        },
        "links": {k: v for k, v in public_links.items() if v is not None},
        "openUrl": open_url,
        "printPackUrl": f"{public_base}/share/event/{event.id}/print",
    }


def _require_event_host_write_perms(db: Session, event: Event, user: AppUser) -> None:
    host_type = (event.host_type or "user").lower()
    host_id = (event.host_id or "").strip()
    if host_type == "user":
        if host_id and host_id != user.id:
            raise HTTPException(status_code=403, detail={"reason": "forbidden_host_user"})
        return
    if host_type == "orga":
        org_id = int(host_id or "0")
        membership = _membership_for(db, org_id=org_id, user_id=user.id)
        if membership is None or (membership.role or "").upper() not in {"OWNER", "PRESIDENT", "MANAGER", "BUREAU", "TRESORIER"}:
            raise HTTPException(status_code=403, detail={"reason": "forbidden_host_orga"})
        return
    raise HTTPException(status_code=400, detail={"reason": "invalid_host_type"})


@app.post("/events", response_model=CreateEventOut)
def create_event(
    payload: CreateEventIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    key = ensure_idempotency_key(idempotency_key)
    existing = db.query(EventAppWriteIdempotency).filter(
        EventAppWriteIdempotency.actor_user_id == user.id,
        EventAppWriteIdempotency.action == "event_create",
        EventAppWriteIdempotency.idempotency_key == key,
    ).first()
    if existing is not None:
        return existing.response_json

    starts_at = payload.startAt or payload.starts_at
    ends_at = payload.endAt or payload.ends_at
    if starts_at is None or ends_at is None or ends_at <= starts_at:
        raise HTTPException(status_code=400, detail={"reason": "invalid_dates"})

    host_type = (payload.host_type or "user").strip().lower()
    if host_type not in {"user", "orga"}:
        raise HTTPException(status_code=400, detail={"reason": "invalid_host_type"})
    host_id = (payload.host_id or user.id).strip()
    if host_type == "user":
        host_id = user.id
    else:
        org_id = int(host_id or "0")
        membership = db.query(OrganizationMembership).filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user.id,
        ).first()
        if membership is None or (membership.role or "").upper() not in {"OWNER", "MANAGER"}:
            raise HTTPException(status_code=403, detail={"reason": "forbidden_host_orga"})

    visibility = (payload.visibility or "PRIVATE").upper()
    if visibility not in {"PUBLIC", "PRIVATE"}:
        raise HTTPException(status_code=400, detail={"reason": "invalid_visibility"})

    venue_parts = []
    if payload.venue:
        if payload.venue.name:
            venue_parts.append(payload.venue.name.strip())
        if payload.venue.address:
            venue_parts.append(payload.venue.address.strip())
    venue = " · ".join([v for v in venue_parts if v]) or None
    now = now_utc()
    event = Event(
        bar_id=payload.bar_id,
        name=payload.name,
        starts_at=starts_at,
        ends_at=ends_at,
        event_code=random_code(6),
        venue=venue,
        event_state="LIVE",
        modules_on=payload.modulesOn or {},
        rules_flags=payload.rulesFlags or {},
        created_by=f"app:{user.id}",
        last_state_updated_at=now,
        last_updated_at=now,
        host_type=host_type,
        host_id=host_id,
        host_display_name=user.display_name,
        visibility=visibility,
        publication_status="DRAFT",
        public_description=payload.public_description,
        short_description=payload.short_description,
        banner_url=payload.banner_url,
        thumbnail_url=payload.thumbnail_url,
        event_type=payload.event_type,
        capacity=payload.capacity,
        access_type=payload.access_type,
        entry_price_cents=payload.entry_price_cents,
        currency=payload.currency.upper(),
        address=payload.address or (payload.venue.address if payload.venue else None),
        city=payload.city,
        lat=payload.lat if payload.lat is not None else (payload.venue.lat if payload.venue else None),
        lng=payload.lng if payload.lng is not None else (payload.venue.lng if payload.venue else None),
    )
    db.add(event)
    db.flush()
    get_or_create_event_config(db, event.id)
    db.add(EventRuntimeState(event_id=event.id, state="LIVE", updated_by_user_id=None, updated_at=now))
    db.add(EventStaff(event_id=event.id, user_id=user.id, role="admin", is_active=True, created_at=now_utc(), created_by_user_id=user.id))

    response = {
        "event_id": event.id,
        "name": event.name,
        "starts_at": event.starts_at.isoformat(),
        "ends_at": event.ends_at.isoformat(),
        "bar_id": event.bar_id,
        "event_code": event.event_code,
        "modulesOn": event.modules_on or {},
        "runtime": _app_event_runtime_payload(db, event),
        "publicationStatus": event.publication_status,
        "visibility": event.visibility,
        "share": _app_event_share_payload(event),
    }
    db.add(EventAppWriteIdempotency(actor_user_id=user.id, action="event_create", idempotency_key=key, event_id=event.id, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="event.create",
        entity_type="event",
        entity_id=str(event.id),
        event_id=event.id,
        bar_id=event.bar_id,
        idempotency_key=key,
        payload={"host_type": host_type, "host_id": host_id, "scope": f"{host_type}:{host_id}"},
    )
    db.commit()
    return response


@app.patch("/events/{event_id}/public-content")
def update_event_public_content(
    event_id: int,
    payload: EventPublicContentPatchIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_host_write_perms(db, event, user)
    _apply_event_public_content(event, payload)
    db.add(event)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="event.public_content.update",
        entity_type="event",
        entity_id=str(event.id),
        event_id=event.id,
        bar_id=event.bar_id,
        idempotency_key=None,
        payload={"fields": sorted(payload.model_fields_set)},
    )
    db.commit()
    db.refresh(event)
    return _event_public_payload(db, event)


@app.post("/events/{event_id}/publish", response_model=EventPublishOut)
def publish_event(
    event_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    key = ensure_idempotency_key(idempotency_key)
    existing = db.query(EventAppWriteIdempotency).filter(
        EventAppWriteIdempotency.actor_user_id == user.id,
        EventAppWriteIdempotency.action == f"event_publish:{event_id}",
        EventAppWriteIdempotency.idempotency_key == key,
    ).first()
    if existing is not None:
        return existing.response_json
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_host_write_perms(db, event, user)
    event.publication_status = "PUBLISHED"
    event.last_updated_at = now_utc()
    response = {"event_id": event.id, "publicationStatus": event.publication_status}
    db.add(EventAppWriteIdempotency(actor_user_id=user.id, action=f"event_publish:{event_id}", idempotency_key=key, event_id=event.id, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="event.publish",
        entity_type="event",
        entity_id=str(event.id),
        event_id=event.id,
        bar_id=event.bar_id,
        idempotency_key=key,
        payload={"scope": f"{event.host_type}:{event.host_id}"},
    )
    db.commit()
    return response


@app.get("/events/{event_id}/share", response_model=EventShareOut)
def get_event_share(
    event_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    user = None
    raw = _extract_bearer_token(authorization)
    if raw:
        user = _resolve_app_user_from_token(raw, db)
    include_staff = False
    if user is not None:
        try:
            _require_event_host_write_perms(db, event, user)
            include_staff = True
        except HTTPException:
            if not _is_public_event_available(event):
                raise HTTPException(status_code=404, detail={"reason": "public_event_not_available"})
    if user is None and not _is_public_event_available(event):
        raise HTTPException(status_code=404, detail={"reason": "public_event_not_available"})
    return _app_event_share_payload(event, include_staff=include_staff)




def _orga_share_payload(org: Organization, public_base_url: str | None = None) -> dict[str, Any]:
    public_base_url = (public_base_url or _public_app_base_url()).rstrip("/")
    web_url = f"{public_base_url}/open?type=orga&id={org.id}"
    return {
        "webUrl": web_url,
        "deeplink": f"tore://open?type=orga&id={org.id}",
        "qrPayload": f"tore://open?type=orga&id={org.id}",
        "title": org.name,
        "description": f"Ouvrir {org.name} dans TORÈ",
    }


_SHORTLINK_SLUG_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"


def _shortlink_slug() -> str:
    return "".join(secrets.choice(_SHORTLINK_SLUG_ALPHABET) for _ in range(9))


def _safe_open_url(*, kind: str, event_id: int | None = None, orga_id: int | None = None, open_type: str | None = None, open_id: int | None = None, open_code: str | None = None) -> tuple[str, dict[str, Any], str]:
    public_base = _public_app_base_url().rstrip("/")
    if kind == "event_share":
        if event_id is None:
            raise HTTPException(status_code=400, detail={"reason": "event_id_required"})
        params = {"type": "event", "id": event_id}
        return f"{public_base}/open?{urlencode(params)}", {"event_id": event_id}, "event_share"
    if kind == "orga_share":
        if orga_id is None:
            raise HTTPException(status_code=400, detail={"reason": "orga_id_required"})
        params = {"type": "orga", "id": orga_id}
        return f"{public_base}/open?{urlencode(params)}", {"orga_id": orga_id}, "orga_share"
    if kind == "open_url":
        type_normalized = (open_type or "").strip().lower()
        if type_normalized not in {"event", "orga", "join", "staff_invite", "staff_backup", "orga_invite"}:
            raise HTTPException(status_code=400, detail={"reason": "invalid_open_type"})
        params: dict[str, Any] = {"type": type_normalized}
        payload: dict[str, Any] = {"type": type_normalized}
        if type_normalized in {"event", "orga"}:
            if open_id is None:
                raise HTTPException(status_code=400, detail={"reason": "open_id_required"})
            params["id"] = open_id
            payload["id"] = open_id
        elif type_normalized == "staff_backup":
            if open_id is None:
                raise HTTPException(status_code=400, detail={"reason": "open_id_required"})
            params["eventId"] = open_id
            payload["eventId"] = open_id
            # Never expose raw backup code in short links V1.
        elif type_normalized in {"join", "staff_invite", "orga_invite"}:
            normalized = canonicalize_manual_code(open_code)
            if not normalized:
                raise HTTPException(status_code=400, detail={"reason": "open_code_required"})
            params["code"] = normalized
            payload["code_suffix_hash"] = _manual_code_suffix_hash(normalized)
        return f"{public_base}/open?{urlencode(params)}", payload, "open_url"
    raise HTTPException(status_code=400, detail={"reason": "invalid_kind"})


def _hash_request_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@app.post("/shortlinks", response_model=ShortLinkCreateOut)
def create_shortlink(
    payload: ShortLinkCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    key = ensure_idempotency_key(idempotency_key)
    enforce_rate_limit("shortlinks_create_user", str(user.id))
    client_ip = (request.client.host if request and request.client else "anon")
    enforce_rate_limit("shortlinks_create_user", f"ip:{client_ip}")

    expires_in = payload.expiresInSeconds if payload.expiresInSeconds is not None else (24 * 60 * 60)
    expires_in = max(3600, min(expires_in, 30 * 24 * 60 * 60))
    expires_at = now_utc() + timedelta(seconds=expires_in)

    open_url, target_payload, target_type = _safe_open_url(
        kind=payload.kind,
        event_id=payload.event_id,
        orga_id=payload.orga_id,
        open_type=payload.open_type,
        open_id=payload.open_id,
        open_code=payload.open_code,
    )

    if payload.kind == "event_share":
        event = db.get(Event, payload.event_id)
        if event is None:
            raise HTTPException(status_code=404, detail={"reason": "event_not_found"})
        _require_event_host_write_perms(db, event, user)
    if payload.kind == "orga_share":
        org = db.get(Organization, payload.orga_id)
        if org is None:
            raise HTTPException(status_code=404, detail={"reason": "orga_not_found"})
        membership = _membership_for(db, org_id=org.id, user_id=user.id)
        if membership is None or (membership.role or "").upper() not in {"OWNER", "MANAGER"}:
            raise HTTPException(status_code=403, detail={"reason": "forbidden"})

    request_payload = {
        "kind": payload.kind,
        "event_id": payload.event_id,
        "orga_id": payload.orga_id,
        "open_type": payload.open_type,
        "open_id": payload.open_id,
        "open_code_suffix_hash": _manual_code_suffix_hash(canonicalize_manual_code(payload.open_code or "")) if payload.open_code else None,
        "expires_in": expires_in,
    }
    request_hash = _hash_request_payload(request_payload)
    idem = db.query(ShortLinkIdempotency).filter(
        ShortLinkIdempotency.idempotency_key == key,
        ShortLinkIdempotency.actor_user_id == user.id,
    ).first()
    if idem is not None:
        if idem.request_hash != request_hash:
            raise HTTPException(status_code=409, detail={"reason": "idempotency_conflict"})
        return idem.response_json

    short = None
    for _ in range(8):
        candidate = _shortlink_slug()
        exists = db.query(ShortLink.id).filter(ShortLink.slug == candidate).first()
        if exists is None:
            short = candidate
            break
    if short is None:
        raise HTTPException(status_code=503, detail={"reason": "slug_generation_failed"})

    public_base = _public_app_base_url().rstrip("/")
    response = {
        "shortUrl": f"{public_base}/s/{short}",
        "openUrl": open_url,
        "fallbackOpenUrl": open_url,
        "expiresAt": _serialize_dt(expires_at),
        "slug": short,
    }
    db.add(ShortLink(id=str(uuid.uuid4()), slug=short, target_type=target_type, target_payload_json=target_payload, status="ACTIVE", expires_at=expires_at, created_at=now_utc(), created_by_user_id=user.id))
    db.add(ShortLinkIdempotency(idempotency_key=key, actor_user_id=user.id, request_hash=request_hash, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="shortlink_created",
        entity_type="short_link",
        event_id=None,
        bar_id=None,
        entity_id=short,
        idempotency_key=key,
        payload={"kind": payload.kind, "slug": short, "target_type": target_type, "target_payload": target_payload},
    )
    db.commit()
    return response


@app.get("/s/{slug}")
def resolve_shortlink(slug: str, db: Session = Depends(get_db)):
    row = db.query(ShortLink).filter(ShortLink.slug == slug).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"reason": "not_found"})
    if (row.status or "ACTIVE").upper() != "ACTIVE":
        raise HTTPException(status_code=404, detail={"reason": "not_found"})
    if row.expires_at is not None and row.expires_at <= now_utc():
        raise HTTPException(status_code=404, detail={"reason": "not_found"})

    public_base = _public_app_base_url().rstrip("/")
    payload = dict(row.target_payload_json or {})
    params: dict[str, Any]
    target_type = (row.target_type or "").lower()
    if target_type == "event_share":
        params = {"type": "event", "id": payload.get("event_id")}
    elif target_type == "orga_share":
        params = {"type": "orga", "id": payload.get("orga_id")}
    elif target_type == "open_url":
        params = {"type": payload.get("type")}
        if payload.get("id") is not None:
            params["id"] = payload.get("id")
        if payload.get("eventId") is not None:
            params["eventId"] = payload.get("eventId")
    else:
        raise HTTPException(status_code=404, detail={"reason": "not_found"})
    params = {k: v for k, v in params.items() if v is not None and str(v) != ""}
    if "type" not in params:
        raise HTTPException(status_code=404, detail={"reason": "not_found"})
    return RedirectResponse(url=f"{public_base}/open?{urlencode(params)}", status_code=302)


@app.post("/shortlinks/{slug}/revoke")
def revoke_shortlink(
    slug: str,
    payload: ShortLinkRevokeIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    key = ensure_idempotency_key(idempotency_key)
    row = db.query(ShortLink).filter(ShortLink.slug == slug).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"reason": "not_found"})
    actor_ok = row.created_by_user_id == user.id
    if not actor_ok:
        raise HTTPException(status_code=403, detail={"reason": "forbidden"})
    if (row.status or "ACTIVE").upper() != "REVOKED":
        row.status = "REVOKED"
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="shortlink_revoked",
        entity_type="short_link",
        event_id=None,
        bar_id=None,
        entity_id=slug,
        idempotency_key=key,
        payload={"reason": payload.reason or "", "slug": slug},
    )
    db.commit()
    return {"ok": True, "slug": slug, "status": row.status}


@app.get("/open", response_model=OpenLinkOut)
def resolve_open_link(
    type: str,
    id: Optional[int] = None,
    event_id: Optional[int] = None,
    eventId: Optional[int] = Query(default=None),
    org_id: Optional[int] = None,
    code: Optional[str] = None,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    user = None
    raw = _extract_bearer_token(authorization)
    if raw:
        user = _resolve_app_user_from_token(raw, db)

    type_normalized = (type or "").strip().lower()
    target_id = id or event_id or eventId or org_id
    if type_normalized == "event":
        if target_id is None:
            raise HTTPException(status_code=400, detail={"reason": "missing_id"})
        event = db.get(Event, target_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        if not _is_public_event_available(event):
            if user is None:
                raise HTTPException(status_code=404, detail={"reason": "public_event_not_available"})
            try:
                _require_event_host_write_perms(db, event, user)
            except HTTPException:
                raise HTTPException(status_code=404, detail={"reason": "public_event_not_available"})
        deeplink = f"tore://open?type=event&id={event.id}"
        web_fallback = f"{_public_app_base_url()}/open?type=event&id={event.id}"
        target = {"event_id": event.id, "name": event.name}
    elif type_normalized == "orga":
        if target_id is None:
            raise HTTPException(status_code=400, detail={"reason": "missing_id"})
        org = db.get(Organization, target_id)
        if org is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        if (org.visibility or "PUBLIC").upper() != "PUBLIC" and user is None:
            raise HTTPException(status_code=403, detail={"reason": "forbidden"})
        deeplink = f"tore://open?type=orga&id={org.id}"
        web_fallback = f"{_public_app_base_url()}/open?type=orga&id={org.id}"
        target = {"org_id": org.id, "name": org.name}
    elif type_normalized == "join":
        if not code:
            raise HTTPException(status_code=400, detail={"reason": "missing_code"})
        normalized = canonicalize_manual_code(code)
        deeplink = f"tore://open?type=join&code={normalized}"
        web_fallback = f"{_public_app_base_url()}/open?type=join&code={normalized}"
        target = {"code": normalized}
        event = db.query(Event).filter(Event.event_code == normalized).first()
        if event is not None:
            target["event_id"] = event.id
            target["visibility"] = (event.visibility or "PRIVATE").upper()
    elif type_normalized == "staff_invite":
        if not code:
            raise HTTPException(status_code=400, detail={"reason": "missing_code"})
        normalized = canonicalize_manual_code(code)
        invite = db.query(EventStaffInviteCode).filter(EventStaffInviteCode.code == normalized).order_by(EventStaffInviteCode.created_at.desc()).first()
        if invite is None:
            raise HTTPException(status_code=404, detail={"reason": "invite_not_found"})
        deeplink = f"tore://open?type=staff_invite&code={normalized}"
        web_fallback = f"{_public_app_base_url()}/open?type=staff_invite&code={normalized}"
        target = {"code": normalized, "event_id": invite.event_id, "role": (invite.role or "").upper()}
    elif type_normalized == "staff_backup":
        if not code:
            raise HTTPException(status_code=400, detail={"reason": "missing_code"})
        event_id_param = event_id or target_id
        if event_id_param is None:
            raise HTTPException(status_code=400, detail={"reason": "missing_event_id"})
        normalized = _normalize_backup_code(code)
        deeplink = f"tore://open?type=staff_backup&eventId={event_id_param}&code={normalized}"
        web_fallback = f"{_public_app_base_url()}/open?type=staff_backup&eventId={event_id_param}&code={normalized}"
        target = {"code": normalized, "event_id": int(event_id_param)}
    elif type_normalized == "orga_invite":
        if not code:
            raise HTTPException(status_code=400, detail={"reason": "missing_code"})
        normalized = canonicalize_manual_code(code)
        deeplink = f"tore://open?type=orga_invite&code={normalized}"
        web_fallback = f"{_public_app_base_url()}/open?type=orga_invite&code={normalized}"
        target = {"code": normalized}
        invite = db.query(OrganizationInviteLink).filter(OrganizationInviteLink.code_hash == _orga_invite_code_hash(normalized)).first()
        if invite is not None:
            target["inviteType"] = (invite.invite_type or "MEMBER").upper()
    else:
        raise HTTPException(status_code=400, detail={"reason": "unsupported_type"})

    payload = {
        "ok": True,
        "type": type_normalized,
        "target": target,
        "deeplink": deeplink,
        "webFallback": web_fallback,
    }
    if type_normalized == "staff_invite":
        payload["title"] = "Invitation staff"
        payload["description"] = "Rejoins le staff dans TORÈ"
    elif type_normalized == "join":
        visibility = (payload["target"].get("visibility") or "PRIVATE").upper()
        if visibility == "PRIVATE":
            payload["title"] = "Rejoindre un event privé"
            payload["description"] = "Connecte-toi dans TORÈ puis entre le code pour rejoindre l’event."
        else:
            payload["title"] = "Rejoindre un event"
            payload["description"] = "Ouvre TORÈ pour rejoindre cet event avec ton code."
    elif type_normalized == "orga_invite":
        role = payload["target"].get("inviteType", "MEMBER")
        payload["title"] = f"Invitation Orga: {role.title()}"
        payload["description"] = "Rejoins une organisation dans TORÈ"
    return payload



@app.get("/codes/preview", response_model=CodesPreviewOut)
def codes_preview(code: str, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else 'anon'
    enforce_rate_limit('codes_preview', f'ip:{client_ip}')
    raw = (code or '').strip()
    uri = None
    try:
        uri = urlparse(raw)
    except Exception:
        uri = None

    linked_type = ''
    linked_code = ''
    linked_event_id: Optional[int] = None
    if uri and ((uri.scheme == 'tore' and uri.netloc == 'open') or (uri.scheme == 'https' and uri.netloc == 'app.tore.be' and uri.path == '/open')):
        qp = parse_qs(uri.query)
        linked_type = (qp.get('type', [''])[0] or '').strip().lower()
        linked_code = canonicalize_manual_code((qp.get('code', [''])[0] or ''))
        raw_event_id = (qp.get('eventId', [''])[0] or qp.get('id', [''])[0] or '').strip()
        linked_event_id = int(raw_event_id) if raw_event_id.isdigit() else None

    normalized = linked_code if linked_code else canonicalize_manual_code(raw)
    backup_event_id = linked_event_id
    backup_code = normalized
    if ':' in normalized:
        left, right = normalized.split(':', 1)
        if left.isdigit() and right:
            backup_event_id = int(left)
            backup_code = _normalize_backup_code(right)
    now = now_utc()
    public_base = _public_app_base_url()

    if not normalized:
        return {
            'kind': 'unknown',
            'requiresAuth': False,
            'status': 'invalid',
            'actionHint': 'ENTER_CODE',
            'openUrl': f"{public_base}/open?type=join",
        }

    def _format_display_suffix(value: Optional[str]) -> Optional[str]:
        token = (value or '').strip().upper()
        if not token:
            return None
        compact = ''.join(ch for ch in token if ch.isalnum())
        if not compact:
            return None
        if len(compact) <= 8:
            return compact
        return f"…{compact[-6:]}"

    safe_suffix = _format_display_suffix(normalized)

    def _build(kind: str, *, requires_auth: bool, status: str = 'ok', open_url: Optional[str] = None, deeplink: Optional[str] = None, expires_at: Optional[datetime] = None, copy_value: Optional[str] = None, copy_hint: Optional[str] = None, normalized_code: Optional[str] = None, display_suffix: Optional[str] = None, **extra: Any) -> dict[str, Any]:
        action_hint = 'LOGIN_REQUIRED' if requires_auth else 'OPEN_APP'
        return {
            'kind': kind,
            'requiresAuth': requires_auth,
            'status': status,
            'normalizedCode': normalized if normalized_code is None else normalized_code,
            'displaySuffix': safe_suffix if display_suffix is None else display_suffix,
            'copyValue': copy_value,
            'copyHint': copy_hint,
            'openUrl': open_url,
            'deeplink': deeplink,
            'actionHint': action_hint,
            'expiresAt': _serialize_dt(expires_at),
            'shareText': extra.pop('shareText', None),
            **extra,
        }

    event = db.query(Event).filter(Event.event_code == normalized).first()
    if event is not None and linked_type in {'', 'join'}:
        is_public = (event.visibility or 'PRIVATE').upper() == 'PUBLIC' and (event.publication_status or 'DRAFT').upper() == 'PUBLISHED'
        if is_public:
            return _build(
                'event_public',
                requires_auth=False,
                open_url=f"{public_base}/open?type=event&id={event.id}",
                deeplink=f"tore://open?type=event&id={event.id}",
                copy_value=normalized,
                copy_hint='Colle dans TORÈ → Entrer un code',
                titleHint=event.name,
                eventHint=event.name,
            )
        return _build(
            'join',
            requires_auth=True,
            open_url=f"{public_base}/open?type=join&code={normalized}",
            deeplink=f"tore://open?type=join&code={normalized}",
            copy_value=normalized,
            copy_hint='Connexion requise',
            titleHint='Event privé TORÈ',
        )

    invite = db.query(EventStaffInviteCode).filter(EventStaffInviteCode.code == normalized).order_by(EventStaffInviteCode.created_at.desc()).first()
    if invite is not None and linked_type in {'', 'staff_invite'}:
        status = _staff_invite_status(invite).lower()
        mapped = 'ok' if status == 'active' else ('expired' if status == 'expired' else 'revoked')
        return _build(
            'staff_invite',
            requires_auth=True,
            status=mapped,
            open_url=f"{public_base}/open?type=staff_invite&code={normalized}",
            deeplink=f"tore://open?type=staff_invite&code={normalized}",
            expires_at=invite.expires_at,
            copy_value=normalized,
            copy_hint='Colle dans TORÈ → Entrer un code',
            titleHint='Invitation staff TORÈ',
        )

    if backup_event_id is not None and backup_code:
        event_ref = db.get(Event, backup_event_id)
        return _build(
            'staff_backup',
            requires_auth=True,
            open_url=f"{public_base}/open?type=staff_backup&eventId={backup_event_id}",
            deeplink=f"tore://open?type=staff_backup&eventId={backup_event_id}",
            copy_value=None,
            copy_hint='Ouvre TORÈ → Entrer un code',
            normalized_code=f"{backup_event_id}:REDACTED",
            display_suffix=(f'…{backup_code[-4:]}' if backup_code else None),
            titleHint='Backup staff TORÈ',
            expiresAt=None if event_ref is None else None,
        )

    org_invite = db.query(OrganizationInviteLink).filter(OrganizationInviteLink.code_hash == _orga_invite_code_hash(normalized)).first()
    if org_invite is not None and linked_type in {'', 'orga_invite'}:
        org = db.get(Organization, org_invite.org_id)
        status = (org_invite.status or 'ACTIVE').upper()
        if status == 'REVOKED':
            return _build('orga_invite', requires_auth=True, status='revoked')
        if org_invite.expires_at is not None and org_invite.expires_at <= now:
            return _build('orga_invite', requires_auth=True, status='expired', expires_at=org_invite.expires_at)
        public = org is not None and (org.visibility or 'PUBLIC').upper() == 'PUBLIC'
        return _build(
            'orga_invite',
            requires_auth=not public,
            open_url=f"{public_base}/open?type=orga_invite&code={normalized}",
            deeplink=f"tore://open?type=orga_invite&code={normalized}",
            expires_at=org_invite.expires_at,
            copy_value=normalized,
            copy_hint='Colle dans TORÈ → Entrer un code',
            orgHint=(org.name if public and org else None),
        )

    return {
        'kind': 'unknown',
        'requiresAuth': False,
        'status': 'invalid',
        'normalizedCode': normalized,
        'displaySuffix': safe_suffix,
        'copyValue': None,
        'copyHint': 'Ouvre TORÈ → Entrer un code',
        'actionHint': 'ENTER_CODE',
        'openUrl': f"{public_base}/open?type=join",
    }


@app.post('/codes/consume')
def consume_code(
    payload: CodesConsumeIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias='Idempotency-Key'),
):
    key = ensure_idempotency_key(idempotency_key)
    existing = db.query(CodeConsumeIdempotency).filter(
        CodeConsumeIdempotency.actor_user_id == user.id,
        CodeConsumeIdempotency.idempotency_key == key,
    ).first()
    if existing is not None:
        return existing.response_json

    normalized = canonicalize_manual_code(payload.code)
    if not normalized:
        raise HTTPException(status_code=400, detail={'reason': 'invalid_code'})

    backup_event_id: Optional[int] = None
    backup_code = ''
    if ':' in normalized:
        left, right = normalized.split(':', 1)
        if left.isdigit() and right:
            backup_event_id = int(left)
            backup_code = _normalize_backup_code(right)

    public_base = _public_app_base_url()
    response: dict[str, Any]
    kind = 'unknown'
    event_for_guard: Optional[int] = None

    event = db.query(Event).filter(Event.event_code == normalized).first()
    if event is not None:
        kind = 'event_public' if ((event.visibility or 'PRIVATE').upper() == 'PUBLIC' and (event.publication_status or 'DRAFT').upper() == 'PUBLISHED') else 'join'
        if kind == 'event_public':
            event_for_guard = event.id
        response = {
            'ok': True,
            'kind': kind,
            'result': _apply_event_join(db, event=event, user=user, idempotency_key=key, accepted_charter_version=None),
            'openUrl': f"{public_base}/open?type={'event&id='+str(event.id) if kind == 'event_public' else 'join&code='+normalized}",
            'status': 'consumed',
        }
    elif backup_event_id is not None and backup_code:
        kind = 'staff_backup'
        event_for_guard = backup_event_id
        event = db.get(Event, backup_event_id)
        if event is None:
            raise HTTPException(status_code=404, detail={'reason': 'event_not_found'})
        _guard_event_write_runtime(db, backup_event_id, critical_write=True)
        code_hash = _hash_staff_backup_code(backup_event_id, backup_code)
        row = db.query(EventStaffBackupCode).filter(EventStaffBackupCode.event_id == backup_event_id, EventStaffBackupCode.code_hash == code_hash).order_by(EventStaffBackupCode.created_at.desc()).first()
        if row is None:
            raise HTTPException(status_code=404, detail={'reason': 'backup_not_found'})
        if _staff_backup_status(row) != 'ACTIVE':
            response = {'ok': True, 'kind': kind, 'status': 'already-consumed'}
        else:
            role = (row.role or 'HELPER').lower()
            staff = db.query(EventStaff).filter(EventStaff.event_id == backup_event_id, EventStaff.user_id == user.id).first()
            if staff is None:
                db.add(EventStaff(event_id=backup_event_id, user_id=user.id, role=role, is_active=True, created_at=now_utc(), created_by_user_id=row.created_by))
            else:
                staff.role = role
                staff.is_active = True
                staff.revoked_at = None
                staff.revoked_by_user_id = None
            row.used_at = now_utc()
            row.used_by = user.id
            row.status = 'USED'
            response = {'ok': True, 'kind': kind, 'status': 'consumed', 'eventId': backup_event_id, 'role': (row.role or role).upper()}
    else:
        invite = db.query(EventStaffInviteCode).filter(EventStaffInviteCode.code == normalized).order_by(EventStaffInviteCode.created_at.desc()).first()
        if invite is not None:
            kind = 'staff_invite'
            event_for_guard = invite.event_id
            _guard_event_write_runtime(db, invite.event_id, critical_write=True)
            if _staff_invite_status(invite) != 'ACTIVE':
                response = {'ok': True, 'kind': kind, 'status': 'already-consumed'}
            else:
                role = (invite.role or 'HELPER').lower()
                staff = db.query(EventStaff).filter(EventStaff.event_id == invite.event_id, EventStaff.user_id == user.id).first()
                if staff is None:
                    db.add(EventStaff(event_id=invite.event_id, user_id=user.id, role=role, is_active=True, created_at=now_utc(), created_by_user_id=invite.created_by))
                else:
                    staff.role = role
                    staff.is_active = True
                    staff.revoked_at = None
                    staff.revoked_by_user_id = None
                response = {'ok': True, 'kind': kind, 'status': 'consumed', 'eventId': invite.event_id, 'role': (invite.role or role).upper()}
        else:
            org_invite = db.query(OrganizationInviteLink).filter(OrganizationInviteLink.code_hash == _orga_invite_code_hash(normalized)).first()
            if org_invite is not None:
                kind = 'orga_invite'
                now = now_utc()
                if org_invite.status != 'ACTIVE' or (org_invite.expires_at and org_invite.expires_at < now):
                    response = {'ok': True, 'kind': kind, 'status': 'already-consumed'}
                else:
                    target_role = _orga_invite_target_role(org_invite.invite_type)
                    membership = db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org_invite.org_id, OrganizationMembership.user_id == user.id).first()
                    already = membership is not None and membership.status == 'ACTIVE' and _ORGA_ROLE_RANK.get((membership.role or 'FOLLOWER').upper(), 0) >= _ORGA_ROLE_RANK.get(target_role, 0)
                    if membership is None:
                        membership = OrganizationMembership(organization_id=org_invite.org_id, user_id=user.id, role=target_role, status='ACTIVE', joined_at=now, starts_at=now, updated_at=now, created_by_user_id=org_invite.created_by_user_id, validation_source='INVITE', validated_by_user_id=org_invite.created_by_user_id, validated_at=now, created_at=now)
                        db.add(membership)
                    elif not already:
                        membership.role = target_role
                        membership.status = 'ACTIVE'
                        membership.validation_source = 'INVITE'
                        membership.validated_by_user_id = org_invite.created_by_user_id
                        membership.validated_at = now
                        membership.revoked_at = None
                        membership.updated_at = now
                    response = {'ok': True, 'kind': kind, 'status': ('already-consumed' if already else 'consumed'), 'organization_id': org_invite.org_id, 'role': membership.role}
            else:
                response = {'ok': True, 'kind': 'unknown', 'status': 'pending', 'normalizedCode': normalized}

    db.add(CodeConsumeIdempotency(actor_user_id=user.id, idempotency_key=key, kind=kind, code_suffix_hash=_manual_code_suffix_hash(normalized), response_json=response))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role='app_user',
        action='code_consumed',
        entity_type='manual_code',
        entity_id=(kind or 'unknown'),
        event_id=event_for_guard,
        bar_id=None,
        idempotency_key=key,
        payload={'kind': kind, 'status': response.get('status'), 'suffixHash': _manual_code_suffix_hash(normalized)},
    )
    db.commit()
    return response


@app.post("/events/{event_id}/staff_invite_code")
def create_event_staff_invite_code(
    event_id: int,
    payload: StaffInviteCodeIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    key = ensure_idempotency_key(idempotency_key)
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_host_write_perms(db, event, user)

    existing = db.query(EventStaffInviteIdempotency).filter(
        EventStaffInviteIdempotency.event_id == event_id,
        EventStaffInviteIdempotency.action == "create",
        EventStaffInviteIdempotency.actor_user_id == user.id,
        EventStaffInviteIdempotency.idempotency_key == key,
    ).first()
    if existing is not None:
        return existing.response_json

    role = (payload.role or "").upper().strip()
    if role not in {"ENTRY", "BAR", "MANAGER", "HELPER"}:
        raise HTTPException(status_code=400, detail={"reason": "invalid_role"})

    expires_at = now_utc() + timedelta(hours=payload.expiresInHours or 12)
    code = random_code(8).upper()
    invite = EventStaffInviteCode(
        event_id=event.id,
        role=role,
        code=code,
        label=(payload.label or None),
        expires_at=expires_at,
        created_by=user.id,
        status="ACTIVE",
    )
    db.add(invite)
    db.flush()

    response = _staff_invite_public_payload(invite)
    db.add(EventStaffInviteIdempotency(
        event_id=event.id,
        action="create",
        actor_user_id=user.id,
        idempotency_key=key,
        invite_id=invite.id,
        response_json=response,
    ))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="event.staff_invite.create",
        entity_type="event_staff_invite_code",
        entity_id=str(invite.id),
        event_id=event.id,
        bar_id=event.bar_id,
        idempotency_key=key,
        payload={"role": role, "expiresAt": response.get("expiresAt"), "label": payload.label},
    )
    db.commit()
    return response


@app.post("/events/{event_id}/staff_invites/{code}/revoke")
def revoke_event_staff_invite_code(
    event_id: int,
    code: str,
    payload: StaffInviteRevokeIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    key = ensure_idempotency_key(idempotency_key)
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_host_write_perms(db, event, user)

    existing = db.query(EventStaffInviteIdempotency).filter(
        EventStaffInviteIdempotency.event_id == event_id,
        EventStaffInviteIdempotency.action == f"revoke:{code.upper()}",
        EventStaffInviteIdempotency.actor_user_id == user.id,
        EventStaffInviteIdempotency.idempotency_key == key,
    ).first()
    if existing is not None:
        return existing.response_json

    normalized = (code or "").strip().upper()
    invite = db.query(EventStaffInviteCode).filter(
        EventStaffInviteCode.event_id == event_id,
        EventStaffInviteCode.code == normalized,
    ).first()
    if invite is None:
        raise HTTPException(status_code=404, detail={"reason": "invite_not_found"})

    invite.status = "REVOKED"
    invite.revoked_at = now_utc()
    invite.revoked_reason = payload.reason.strip()
    response = {"ok": True, "status": "REVOKED", "code": normalized}
    db.add(EventStaffInviteIdempotency(
        event_id=event.id,
        action=f"revoke:{normalized}",
        actor_user_id=user.id,
        idempotency_key=key,
        invite_id=invite.id,
        response_json=response,
    ))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="event.staff_invite.revoke",
        entity_type="event_staff_invite_code",
        entity_id=str(invite.id),
        event_id=event.id,
        bar_id=event.bar_id,
        idempotency_key=key,
        payload={"code": normalized, "reason": invite.revoked_reason},
    )
    db.commit()
    return response


@app.post("/events/{event_id}/staff_invites/rotate")
def rotate_event_staff_invite_code(
    event_id: int,
    payload: StaffInviteRotateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    key = ensure_idempotency_key(idempotency_key)
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_host_write_perms(db, event, user)
    _guard_event_write_runtime(db, event_id, critical_write=True)

    role = (payload.role or "").upper().strip()
    if role not in {"ENTRY", "BAR", "MANAGER", "HELPER"}:
        raise HTTPException(status_code=400, detail={"reason": "invalid_role"})

    existing = db.query(EventStaffInviteIdempotency).filter(
        EventStaffInviteIdempotency.event_id == event_id,
        EventStaffInviteIdempotency.action == f"rotate:{role}",
        EventStaffInviteIdempotency.actor_user_id == user.id,
        EventStaffInviteIdempotency.idempotency_key == key,
    ).first()
    if existing is not None:
        return existing.response_json

    now = now_utc()
    active = db.query(EventStaffInviteCode).filter(
        EventStaffInviteCode.event_id == event_id,
        EventStaffInviteCode.role == role,
        EventStaffInviteCode.status == "ACTIVE",
        EventStaffInviteCode.revoked_at.is_(None),
    ).order_by(EventStaffInviteCode.created_at.desc()).all()
    revoked_codes: list[str] = []
    for invite in active:
        if invite.expires_at and invite.expires_at <= now:
            continue
        invite.status = "REVOKED"
        invite.revoked_at = now
        invite.revoked_reason = "ROTATED"
        revoked_codes.append((invite.code or "").upper())

    expires_in_minutes = payload.expiresInMinutes or (12 * 60)
    expires_at = now + timedelta(minutes=expires_in_minutes)
    invite = EventStaffInviteCode(
        event_id=event.id,
        role=role,
        code=random_code(8).upper(),
        expires_at=expires_at,
        created_by=user.id,
        status="ACTIVE",
    )
    db.add(invite)
    db.flush()

    response = _staff_invite_public_payload(invite)
    db.add(EventStaffInviteIdempotency(
        event_id=event.id,
        action=f"rotate:{role}",
        actor_user_id=user.id,
        idempotency_key=key,
        invite_id=invite.id,
        response_json=response,
    ))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="staff_invite_rotated",
        entity_type="event_staff_invite_code",
        entity_id=str(invite.id),
        event_id=event.id,
        bar_id=event.bar_id,
        idempotency_key=key,
        payload={"role": role, "newCode": response.get("code"), "revokedCodes": revoked_codes, "expiresAt": response.get("expiresAt")},
    )
    db.commit()
    return response


@app.get("/events/{event_id}/staff_invites/current")
def get_event_staff_invites_current(
    event_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_host_write_perms(db, event, user)

    now = now_utc()
    roles: dict[str, Any] = {}
    for role in ("ENTRY", "BAR", "MANAGER", "HELPER"):
        invite = db.query(EventStaffInviteCode).filter(
            EventStaffInviteCode.event_id == event_id,
            EventStaffInviteCode.role == role,
            EventStaffInviteCode.status == "ACTIVE",
            EventStaffInviteCode.revoked_at.is_(None),
        ).order_by(EventStaffInviteCode.created_at.desc()).first()
        if invite is not None and invite.expires_at and invite.expires_at <= now:
            invite = None
        roles[role] = _staff_invite_current_role_payload(invite)

    payload = {
        "roles": roles,
        "serverTime": now.isoformat(),
    }
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="event.staff_invites.current.read",
        entity_type="event",
        entity_id=str(event.id),
        event_id=event.id,
        bar_id=event.bar_id,
        payload={"scope": "staff_invites_current"},
    )
    db.commit()
    return payload


@app.post("/events/{event_id}/staff/join_by_invite")
def join_staff_by_invite(
    event_id: int,
    payload: StaffJoinByInviteIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    key = ensure_idempotency_key(idempotency_key)
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    existing = db.query(EventStaffInviteIdempotency).filter(
        EventStaffInviteIdempotency.event_id == event_id,
        EventStaffInviteIdempotency.action == "join",
        EventStaffInviteIdempotency.actor_user_id == user.id,
        EventStaffInviteIdempotency.idempotency_key == key,
    ).first()
    if existing is not None:
        return existing.response_json

    _guard_event_write_runtime(db, event_id, critical_write=True)

    normalized = (payload.code or "").strip().upper()
    invite = db.query(EventStaffInviteCode).filter(
        EventStaffInviteCode.event_id == event_id,
        EventStaffInviteCode.code == normalized,
    ).order_by(EventStaffInviteCode.created_at.desc()).first()
    if invite is None:
        raise HTTPException(status_code=404, detail={"reason": "invite_not_found"})
    if _staff_invite_status(invite) != "ACTIVE":
        raise HTTPException(status_code=409, detail={"reason": "invite_not_active", "status": _staff_invite_status(invite)})

    role = (invite.role or "HELPER").lower()
    staff = db.query(EventStaff).filter(EventStaff.event_id == event_id, EventStaff.user_id == user.id).first()
    if staff is None:
        staff = EventStaff(event_id=event_id, user_id=user.id, role=role, is_active=True, created_at=now_utc(), created_by_user_id=invite.created_by)
        db.add(staff)
    else:
        staff.role = role
        staff.is_active = True
        staff.revoked_at = None
        staff.revoked_by_user_id = None

    response = {"ok": True, "eventId": event_id, "role": (invite.role or role).upper(), "expiresAt": invite.expires_at.isoformat() if invite.expires_at else None}
    db.add(EventStaffInviteIdempotency(
        event_id=event_id,
        action="join",
        actor_user_id=user.id,
        idempotency_key=key,
        invite_id=invite.id,
        response_json=response,
    ))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="event.staff_invite.join",
        entity_type="event_staff",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=event.bar_id,
        idempotency_key=key,
        payload={"code": normalized, "role": response["role"]},
    )
    db.commit()
    return response


@app.post("/events/{event_id}/staff_backup_codes/generate")
def generate_staff_backup_codes(
    event_id: int,
    payload: StaffBackupGenerateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    key = ensure_idempotency_key(idempotency_key)
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_host_write_perms(db, event, user)

    action = f"generate:{(payload.role or '').upper()}"
    existing = db.query(EventStaffBackupIdempotency).filter(
        EventStaffBackupIdempotency.event_id == event_id,
        EventStaffBackupIdempotency.action == action,
        EventStaffBackupIdempotency.actor_user_id == user.id,
        EventStaffBackupIdempotency.idempotency_key == key,
    ).first()
    if existing is not None:
        return existing.response_json

    _guard_event_write_runtime(db, event_id, critical_write=True)

    role = (payload.role or "").upper().strip()
    if role not in {"ENTRY", "BAR", "MANAGER", "HELPER"}:
        raise HTTPException(status_code=400, detail={"reason": "invalid_role"})

    active = db.query(EventStaffBackupCode).filter(
        EventStaffBackupCode.event_id == event_id,
        EventStaffBackupCode.role == role,
        EventStaffBackupCode.status == "ACTIVE",
        EventStaffBackupCode.revoked_at.is_(None),
        EventStaffBackupCode.used_at.is_(None),
    ).all()
    now = now_utc()
    for item in active:
        item.status = "REVOKED"
        item.revoked_at = now
        item.revoked_reason = "REGENERATED"

    expires_at = now + timedelta(hours=payload.expiresInHours or 12)
    generated: list[dict[str, Any]] = []
    for _ in range(payload.count or 12):
        plain = _generate_backup_code(8)
        code_hash = _hash_staff_backup_code(event_id, plain)
        row = EventStaffBackupCode(
            event_id=event_id,
            role=role,
            code_hash=code_hash,
            suffix4=plain[-4:],
            expires_at=expires_at,
            status="ACTIVE",
            created_by=user.id,
        )
        db.add(row)
        generated.append({"code": plain, "suffix4": plain[-4:], "expiresAt": expires_at.isoformat(), **_staff_backup_open_payload(event_id, plain)})

    response = {"ok": True, "eventId": event_id, "role": role, "count": len(generated), "expiresAt": expires_at.isoformat(), "codes": generated}
    db.add(EventStaffBackupIdempotency(event_id=event_id, action=action, actor_user_id=user.id, idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="staff_backup_generated",
        entity_type="event_staff_backup_code",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=event.bar_id,
        idempotency_key=key,
        payload={"role": role, "count": len(generated), "expiresAt": expires_at.isoformat()},
    )
    db.commit()
    return response


@app.get("/events/{event_id}/staff_backup_codes")
def list_staff_backup_codes(
    event_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_host_write_perms(db, event, user)

    rows = db.query(EventStaffBackupCode).filter(EventStaffBackupCode.event_id == event_id).order_by(EventStaffBackupCode.created_at.desc()).all()
    by_role: dict[str, list[dict[str, Any]]] = {"ENTRY": [], "BAR": [], "MANAGER": [], "HELPER": []}
    for row in rows:
        by_role.setdefault((row.role or "").upper(), []).append(_staff_backup_admin_payload(row))

    payload = {"eventId": event_id, "roles": by_role}
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="event.staff_backup.read",
        entity_type="event",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"scope": "staff_backup_list"},
    )
    db.commit()
    return payload


@app.post("/events/{event_id}/staff/join_by_backup_code")
def join_staff_by_backup_code(
    event_id: int,
    payload: StaffBackupJoinIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    key = ensure_idempotency_key(idempotency_key)
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    existing = db.query(EventStaffBackupIdempotency).filter(
        EventStaffBackupIdempotency.event_id == event_id,
        EventStaffBackupIdempotency.action == "consume",
        EventStaffBackupIdempotency.actor_user_id == user.id,
        EventStaffBackupIdempotency.idempotency_key == key,
    ).first()
    if existing is not None:
        return existing.response_json

    _guard_event_write_runtime(db, event_id, critical_write=True)
    enforce_rate_limit("staff_backup_join", f"{user.id}:{event_id}")

    normalized = _normalize_backup_code(payload.code)
    if len(normalized) < 8:
        raise HTTPException(status_code=400, detail={"reason": "invalid_code"})
    code_hash = _hash_staff_backup_code(event_id, normalized)
    row = db.query(EventStaffBackupCode).filter(
        EventStaffBackupCode.event_id == event_id,
        EventStaffBackupCode.code_hash == code_hash,
    ).order_by(EventStaffBackupCode.created_at.desc()).first()

    if row is None:
        raise HTTPException(status_code=404, detail={"reason": "backup_not_found"})

    status = _staff_backup_status(row)
    if status != "ACTIVE":
        raise HTTPException(status_code=409, detail={"reason": "backup_not_active", "status": status})

    role = (row.role or "HELPER").lower()
    staff = db.query(EventStaff).filter(EventStaff.event_id == event_id, EventStaff.user_id == user.id).first()
    if staff is None:
        staff = EventStaff(event_id=event_id, user_id=user.id, role=role, is_active=True, created_at=now_utc(), created_by_user_id=row.created_by)
        db.add(staff)
    else:
        staff.role = role
        staff.is_active = True
        staff.revoked_at = None
        staff.revoked_by_user_id = None

    row.used_at = now_utc()
    row.used_by = user.id
    row.status = "USED"

    response = {"ok": True, "eventId": event_id, "role": (row.role or role).upper(), "expiresAt": row.expires_at.isoformat() if row.expires_at else None, "tokenId": f"staff-backup:{row.id}"}
    db.add(EventStaffBackupIdempotency(event_id=event_id, action="consume", actor_user_id=user.id, idempotency_key=key, code_id=row.id, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="staff_backup_consumed",
        entity_type="event_staff_backup_code",
        entity_id=str(row.id),
        event_id=event_id,
        bar_id=event.bar_id,
        idempotency_key=key,
        payload={"role": response["role"], "suffix4": row.suffix4},
    )
    db.commit()
    return response



@app.get("/events/{event_id}/share_pack")
def get_event_share_pack(
    event_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    user = None
    raw = _extract_bearer_token(authorization)
    if raw:
        user = _resolve_app_user_from_token(raw, db)

    include_staff = False
    if user is not None:
        try:
            _require_event_host_write_perms(db, event, user)
            include_staff = True
        except HTTPException:
            if not _is_public_event_available(event):
                raise HTTPException(status_code=404, detail={"reason": "public_event_not_available"})
    elif not _is_public_event_available(event):
        raise HTTPException(status_code=401, detail={"reason": "auth_required"})

    payload = _event_share_pack_payload(db, event, include_staff=include_staff)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=(user.id if user else None),
        actor_role="app_user" if user else "anonymous",
        action="event.share_pack.read",
        entity_type="event",
        entity_id=str(event.id),
        event_id=event.id,
        bar_id=event.bar_id,
        payload={"includeStaff": include_staff},
    )
    db.commit()
    return payload


@app.get("/share/event/{event_id}")
def get_public_event_share_pack(
    event_id: int,
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if not _is_public_event_available(event):
        raise HTTPException(status_code=404, detail={"reason": "public_share_pack_not_available"})

    payload = _public_event_share_pack_payload(db, event)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=None,
        actor_role="anonymous",
        action="event.public_share_pack.read",
        entity_type="event",
        entity_id=str(event.id),
        event_id=event.id,
        bar_id=event.bar_id,
        payload={"scope": "public_share_pack"},
    )
    db.commit()
    return payload


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


@app.post("/events/{event_id}/entry/manual_increment", response_model=EntryManualIncrementOut)
def event_entry_manual_increment(
    event_id: int,
    payload: EntryManualIncrementIn,
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
    allow_degraded = bool((event.rules_flags or {}).get("entry_manual_allow_degraded", False))
    if state in {"FROZEN", "CLOSED"} or (state == "DEGRADED" and not allow_degraded):
        raise HTTPException(status_code=403, detail={"reason": "runtime_blocked", "state": state})

    raw = _extract_bearer_token(authorization)
    if not raw:
        raise HTTPException(status_code=401, detail="Missing token")

    actor_staff = None
    actor_partner = None
    actor_role = "entry_staff"
    user = _resolve_app_user_from_token(raw, db)
    if user:
        require_feature(db, event_id, "entry_enabled")
        require_role_for_event(db, user.id, event_id, "entry")
        actor_staff = user.id
    else:
        identity = _resolve_partner_identity_from_token(raw, db)
        if not identity:
            raise HTTPException(status_code=401, detail="Invalid token")
        if event.bar_id != identity["bar_id"]:
            raise HTTPException(status_code=403, detail="Forbidden")
        require_feature(db, event_id, "entry_enabled")
        _require_partner_roles(identity, {"entry", "manager"})
        actor_staff = str(identity["user_id"])
        actor_partner = identity["user_id"]
        actor_role = identity.get("role") or "entry"

    key = idempotency_key.strip()
    existing_idem = db.query(EntryLog).filter(EntryLog.event_id == event_id, EntryLog.idempotency_key == key).first()
    if existing_idem:
        return EntryManualIncrementOut(count=entry_count(db, event_id), deltaApplied=existing_idem.delta, serverTime=existing_idem.created_at)

    since = now_utc() - timedelta(minutes=10)
    recent_manual = db.query(func.count(EntryLog.id)).filter(
        EntryLog.event_id == event_id,
        EntryLog.source == "manual",
        EntryLog.staff_id == actor_staff,
        EntryLog.created_at >= since,
    ).scalar() or 0
    if int(recent_manual) >= 60:
        raise HTTPException(status_code=429, detail={"reason": "rate_limited", "message": "Too many manual increments"})

    delta = int(payload.delta)
    note = (payload.note or "").strip()
    reason = payload.reason.strip()
    log = EntryLog(
        event_id=event_id,
        created_at=now_utc(),
        delta=delta,
        source="manual",
        staff_id=actor_staff,
        device_id="orga-mobile",
        idempotency_key=key,
        raw_qr=f"reason={reason};note={note}" if note else f"reason={reason}",
    )
    db.add(log)
    write_audit_log(
        db,
        actor_partner_id=actor_partner,
        actor_role=actor_role,
        action="entry_manual_increment",
        entity_type="entry_log",
        entity_id=None,
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"delta": delta, "reason": reason, "note": note, "staff_id": actor_staff, "idempotency_key": key},
    )
    db.commit()
    return EntryManualIncrementOut(count=entry_count(db, event_id), deltaApplied=delta, serverTime=log.created_at)


@app.get("/events/{event_id}/entry/manual_increments")
def event_entry_manual_increments(
    event_id: int,
    authorization: Optional[str] = Header(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    raw = _extract_bearer_token(authorization)
    if not raw:
        raise HTTPException(status_code=401, detail="Missing token")
    identity = _resolve_partner_identity_from_token(raw, db)
    if not identity:
        raise HTTPException(status_code=401, detail="Invalid token")
    if event.bar_id != identity["bar_id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    rows = db.query(EntryLog).filter(EntryLog.event_id == event_id, EntryLog.source == "manual").order_by(EntryLog.created_at.desc(), EntryLog.id.desc()).limit(limit).all()
    items = []
    for row in rows:
        raw_text = row.raw_qr or ""
        reason = "manual"
        if raw_text.startswith("reason="):
            reason = raw_text.split(";", 1)[0].replace("reason=", "")
        items.append({"id": row.id, "delta": row.delta, "reason": reason, "time": row.created_at.isoformat()})
    return {"items": items}


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
    writer.writerow(["timestamp", "status", "source", "delta", "reason", "actor", "deviceId"])
    for row in rows:
        raw_qr = (row.raw_qr or "")
        reason = "scan"
        if row.source == "manual" and raw_qr.startswith("reason="):
            reason = raw_qr.split(";", 1)[0].replace("reason=", "")
        actor = f"staff:{(row.staff_id or '')[-6:]}" if row.staff_id else "staff"
        writer.writerow([
            row.created_at.isoformat(),
            "accepted" if row.delta > 0 else "already_checked",
            "MANUAL" if row.source == "manual" else "QR",
            row.delta,
            reason,
            actor,
            row.device_id or "",
        ])

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
    instagram_handle: Optional[str] = Field(default=None, max_length=64)
    visibility: Literal["PUBLIC", "PRIVATE"] = "PUBLIC"
    join_mode: Literal["FOLLOW_ONLY", "OPEN_MEMBERSHIP", "REQUEST_TO_JOIN"] = "OPEN_MEMBERSHIP"


class OrgaOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    city: Optional[str] = None
    org_type: Optional[str] = None
    website_url: Optional[str] = None
    instagram_handle: Optional[str] = None
    visibility: str = "PUBLIC"
    join_mode: str = "OPEN_MEMBERSHIP"


class OrgaMembershipOut(BaseModel):
    orga: OrgaOut
    role: Literal["OWNER", "MANAGER", "STAFF", "MEMBER", "FOLLOWER"]
    status: Literal["ACTIVE", "PENDING", "REJECTED", "LEFT"] = "ACTIVE"


class JoinByCodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=16)


class OrgaMemberUpsertIn(BaseModel):
    user_id: str = Field(min_length=3, max_length=64)
    role: Literal["OWNER", "MANAGER", "STAFF", "MEMBER", "FOLLOWER"] = "MEMBER"


class MembershipDecisionIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=280)


class MembershipRejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=280)


class OrgaUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=140)
    city: Optional[str] = Field(default=None, max_length=120)
    type: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = Field(default=None, max_length=4000)
    instagram: Optional[str] = Field(default=None, max_length=64)
    logoUrl: Optional[str] = Field(default=None, max_length=512)
    visibility: Optional[Literal["PUBLIC", "PRIVATE"]] = None
    join_mode: Optional[Literal["FOLLOW_ONLY", "OPEN_MEMBERSHIP", "REQUEST_TO_JOIN"]] = None


class MembershipSetRoleIn(BaseModel):
    role: Literal["OWNER", "MANAGER", "STAFF", "MEMBER", "FOLLOWER"]
    reason: str = Field(min_length=1, max_length=280)


class MembershipRemoveIn(BaseModel):
    reason: str = Field(min_length=1, max_length=280)


class OrgaPostCreateIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    image_url: Optional[str] = Field(default=None, max_length=512)


class MeProfilePutIn(BaseModel):
    model_config = {"extra": "forbid"}

    display_name: str = Field(min_length=1, max_length=120)
    photo_url: Optional[str] = Field(default=None, max_length=512)
    bio: Optional[str] = Field(default=None, max_length=2000)
    instagram_handle: Optional[str] = Field(default=None, max_length=64)
    oripeaux: Optional[str] = Field(default=None, max_length=500)
    visibility: Literal["PUBLIC", "PRIVATE"] = "PUBLIC"




class OrgaInviteCreateIn(BaseModel):
    inviteType: Literal["MEMBER", "MANAGER", "STAFF", "FOLLOWER"] = "MEMBER"
    expiresInHours: Optional[int] = Field(default=None, ge=1, le=24 * 90)


class OrgaInviteRevokeIn(BaseModel):
    reason: str = Field(min_length=1, max_length=280)


class OrgaJoinByInviteIn(BaseModel):
    code: str = Field(min_length=4, max_length=64)

class OrgaInviteOut(BaseModel):
    org_id: int
    invite_code: str
    code: Optional[str] = None
    deeplink: str
    https_link: str
    qr_payload: str
    expires_at: Optional[str] = None


class OrgaShareOut(BaseModel):
    webUrl: str
    deeplink: str
    qrPayload: Optional[str] = None
    title: str
    description: str



def _orga_to_out(row: Organization) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "slug": row.slug,
        "description": row.description,
        "city": row.city,
        "org_type": row.org_type,
        "website_url": row.website_url,
        "instagram_handle": row.instagram_handle,
        "visibility": row.visibility,
        "join_mode": (row.join_mode or "OPEN_MEMBERSHIP").upper(),
    }


def _membership_snapshot(row: Optional[OrganizationMembership]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    return {
        "organization_id": row.organization_id,
        "user_id": row.user_id,
        "role": (row.role or "MEMBER").upper(),
        "status": (row.status or "ACTIVE").upper(),
        "created_at": _serialize_dt(row.created_at),
        "updated_at": _serialize_dt(row.updated_at),
        "joined_at": _serialize_dt(row.joined_at),
    }


def _get_orga_or_404(db: Session, org_id: int) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(404, "Organization not found")
    return org


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


_ORGA_ROLE_RANK = {
    "FOLLOWER": 0,
    "ALUMNI": 1,
    "MEMBER": 1,
    "STAFF": 2,
    "TRESORIER": 3,
    "BUREAU": 3,
    "PRESIDENT": 4,
    "MANAGER": 4,
    "OWNER": 5,
}
_ORGA_INVITE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_ORGA_INVITE_TYPES = {"MEMBER", "MANAGER", "STAFF", "FOLLOWER"}


def _orga_invite_code_hash(code: str) -> str:
    normalized = (code or "").strip().upper()
    return hashlib.sha256(f"orga-invite:{normalized}".encode("utf-8")).hexdigest()


def _generate_orga_invite_code(length: int = 10) -> str:
    return "".join(secrets.choice(_ORGA_INVITE_CODE_ALPHABET) for _ in range(length))


def _orga_invite_target_role(invite_type: str) -> str:
    normalized = (invite_type or "MEMBER").strip().upper()
    if normalized not in _ORGA_INVITE_TYPES:
        raise HTTPException(status_code=400, detail={"reason": "invalid_invite_type"})
    return normalized


def _membership_for(db: Session, *, org_id: int, user_id: str) -> Optional[OrganizationMembership]:
    now = now_utc()
    return db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.status == "ACTIVE",
        OrganizationMembership.revoked_at.is_(None),
        or_(OrganizationMembership.starts_at.is_(None), OrganizationMembership.starts_at <= now),
        or_(OrganizationMembership.ends_at.is_(None), OrganizationMembership.ends_at > now),
    ).first()


def _membership_any_status(db: Session, *, org_id: int, user_id: str) -> Optional[OrganizationMembership]:
    return db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == user_id,
    ).first()


def _require_membership_role(db: Session, *, org_id: int, user_id: str, min_role: str) -> OrganizationMembership:
    membership = _membership_for(db, org_id=org_id, user_id=user_id)
    if not membership:
        raise HTTPException(403, "Forbidden")
    if _ORGA_ROLE_RANK.get(membership.role, -1) < _ORGA_ROLE_RANK.get(min_role, 999):
        raise HTTPException(403, "Forbidden")
    return membership


def _orga_write_idem(db: Session, *, actor_user_id: str, action: str, idempotency_key: str) -> Optional[OrganizationWriteIdempotency]:
    return db.query(OrganizationWriteIdempotency).filter(
        OrganizationWriteIdempotency.actor_user_id == actor_user_id,
        OrganizationWriteIdempotency.action == action,
        OrganizationWriteIdempotency.idempotency_key == idempotency_key,
    ).first()


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
        instagram_handle=(payload.instagram_handle or "").strip() or None,
        visibility=(payload.visibility or "PUBLIC").upper(),
        join_mode=(payload.join_mode or "OPEN_MEMBERSHIP").upper(),
        created_by_user_id=user.id,
        created_at=now_utc(),
    )
    db.add(org)
    db.flush()

    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role="OWNER",
        status="ACTIVE",
        joined_at=now_utc(),
        starts_at=now_utc(),
        validation_source="OWNER_CREATION",
        validated_by_user_id=user.id,
        validated_at=now_utc(),
        updated_at=now_utc(),
        created_by_user_id=user.id,
        created_at=now_utc(),
    )
    db.add(membership)

    response = {"orga": _orga_to_out(org), "role": "OWNER", "status": "ACTIVE"}
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
    q: Optional[str] = None,
    city: Optional[str] = None,
    type: Optional[str] = Query(default=None, alias="type"),
    join_mode: Optional[str] = None,
    sort: str = Query(default="recent"),
    cursor: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    normalized_search = (q or query or "").strip().lower()
    followers_count = (
        select(func.count(OrganizationMembership.id))
        .where(
            OrganizationMembership.organization_id == Organization.id,
            OrganizationMembership.status == "ACTIVE",
            OrganizationMembership.role.in_(["FOLLOWER", "MEMBER", "MANAGER", "OWNER"]),
        )
        .correlate(Organization)
        .scalar_subquery()
    )
    last_post_at = (
        select(func.max(OrgaPost.created_at))
        .where(OrgaPost.organization_id == Organization.id, OrgaPost.deleted_at.is_(None))
        .correlate(Organization)
        .scalar_subquery()
    )
    last_member_at = (
        select(func.max(OrganizationMembership.joined_at))
        .where(OrganizationMembership.organization_id == Organization.id, OrganizationMembership.status == "ACTIVE")
        .correlate(Organization)
        .scalar_subquery()
    )
    last_active_at = case(
        (last_post_at.is_(None), last_member_at),
        (last_member_at.is_(None), last_post_at),
        else_=func.max(last_post_at, last_member_at),
    )

    stmt = select(Organization, followers_count.label("followers_count"), last_active_at.label("last_active_at")).where(
        func.upper(Organization.visibility) == "PUBLIC"
    )
    if normalized_search:
        search_like = f"%{normalized_search}%"
        stmt = stmt.where(
            or_(
                func.lower(Organization.name).like(search_like),
                func.lower(func.coalesce(Organization.city, "")).like(search_like),
                func.lower(func.coalesce(Organization.instagram_handle, "")).like(search_like),
            )
        )
    if city:
        city_norm = city.strip().lower()
        stmt = stmt.where(or_(func.lower(Organization.city) == city_norm, func.lower(Organization.city).like(f"{city_norm}%")))
    if type:
        stmt = stmt.where(func.lower(Organization.org_type) == type.strip().lower())
    if join_mode:
        stmt = stmt.where(func.upper(Organization.join_mode) == join_mode.strip().upper())

    sort_key = (sort or "recent").strip().lower()
    if sort_key not in {"recent", "popular"}:
        raise HTTPException(status_code=400, detail={"reason": "invalid_sort"})

    if cursor:
        try:
            cursor_payload = json.loads(base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail={"reason": "invalid_cursor"}) from exc
        if sort_key == "popular":
            c_followers = int(cursor_payload.get("followersCount", 0))
            c_id = int(cursor_payload.get("id", 0))
            stmt = stmt.where(or_(followers_count < c_followers, and_(followers_count == c_followers, Organization.id < c_id)))
        else:
            c_null_rank = int(cursor_payload.get("nullRank", 0))
            c_id = int(cursor_payload.get("id", 0))
            c_last_raw = cursor_payload.get("lastActiveAt")
            c_last = datetime.fromisoformat(c_last_raw) if c_last_raw else None
            recent_clause = and_(last_active_at.is_not(None), or_(last_active_at < c_last, and_(last_active_at == c_last, Organization.id < c_id))) if c_last else (last_active_at.is_not(None) & (Organization.id < c_id))
            stmt = stmt.where(
                or_(
                    case((last_active_at.is_(None), 1), else_=0) > c_null_rank,
                    and_(case((last_active_at.is_(None), 1), else_=0) == c_null_rank, recent_clause if c_null_rank == 0 else Organization.id < c_id),
                )
            )

    if sort_key == "popular":
        stmt = stmt.order_by(desc(followers_count), Organization.id.desc())
    else:
        stmt = stmt.order_by(case((last_active_at.is_(None), 1), else_=0).asc(), desc(last_active_at), Organization.id.desc())

    rows = db.execute(stmt.limit(limit + 1)).all()
    items = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        org_row, followers_row, active_row = rows[limit - 1]
        if sort_key == "popular":
            payload = {"followersCount": int(followers_row or 0), "id": org_row.id}
        else:
            payload = {
                "nullRank": 1 if active_row is None else 0,
                "lastActiveAt": active_row.isoformat() if active_row is not None else None,
                "id": org_row.id,
            }
        next_cursor = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

    out_items = []
    for row, followers, active_at in items:
        out_items.append({
            **_orga_to_out(row),
            "type": row.org_type,
            "joinMode": row.join_mode,
            "followersCount": int(followers or 0),
            "lastActiveAt": active_at.isoformat() if active_at is not None else None,
        })
    return {"items": out_items, "nextCursor": next_cursor, "next_cursor": next_cursor}


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
    return [{"orga": _orga_to_out(org), "role": membership.role, "status": (membership.status or "ACTIVE")} for membership, org in rows]


@app.get("/orgas/{org_id}", response_model=OrgaOut)
def get_orga(org_id: int, db: Session = Depends(get_db)):
    row = db.get(Organization, org_id)
    if not row:
        raise HTTPException(404, "Organization not found")
    return _orga_to_out(row)


@app.put("/orgas/{org_id}", response_model=OrgaOut)
def update_orga(
    org_id: int,
    payload: OrgaUpdateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    actor = _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_update:{org_id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem:
        return idem.response_json

    org = _get_orga_or_404(db, org_id)
    if payload.name is not None:
        cleaned_name = payload.name.strip()
        if not cleaned_name:
            raise HTTPException(status_code=400, detail={"reason": "invalid_name"})
        org.name = cleaned_name
    if payload.city is not None:
        org.city = payload.city.strip() or None
    if payload.type is not None:
        org.org_type = payload.type.strip() or None
    if payload.description is not None:
        org.description = payload.description.strip() or None
    if payload.instagram is not None:
        org.instagram_handle = payload.instagram.strip() or None
    if payload.logoUrl is not None:
        org.website_url = payload.logoUrl.strip() or None
    if payload.visibility is not None:
        org.visibility = payload.visibility.upper()
    if payload.join_mode is not None:
        org.join_mode = payload.join_mode.upper()

    response = _orga_to_out(org)
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_user_id=user.id,
        actor_partner_id=None,
        actor_role=actor.role,
        action="orga_updated",
        entity_type="organization",
        entity_id=str(org_id),
        event_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={"scope": f"orga:{org_id}"},
    )
    db.commit()
    return response


def _event_role_for_user(db: Session, *, event: Event, user_id: str) -> tuple[str, bool]:
    host_type = (event.host_type or "user").lower()
    host_id = (event.host_id or "").strip()
    if host_type == "user" and host_id and host_id == user_id:
        return "OWNER", True

    orga_role = None
    if host_type == "orga" and host_id:
        try:
            org_id = int(host_id)
        except ValueError:
            org_id = 0
        membership = _membership_for(db, org_id=org_id, user_id=user_id)
        if membership is not None:
            role = (membership.role or "MEMBER").upper()
            if role in _ORGA_ROLE_RANK:
                orga_role = role
            else:
                orga_role = "MEMBER"

    staff = db.query(EventStaff).filter(
        EventStaff.event_id == event.id,
        EventStaff.user_id == user_id,
        EventStaff.is_active == True,  # noqa: E712
        EventStaff.revoked_at.is_(None),
        or_(EventStaff.expires_at.is_(None), EventStaff.expires_at > now_utc()),
    ).first()
    staff_role = None
    if staff is not None:
        raw = (staff.role or "").lower()
        staff_role = "MANAGER" if raw == "admin" else "STAFF"

    if orga_role in {"OWNER", "PRESIDENT"}:
        return "OWNER", True
    if orga_role in {"MANAGER", "BUREAU", "TRESORIER"}:
        return "MANAGER", True
    if staff_role == "MANAGER":
        return "MANAGER", True
    if orga_role == "STAFF" or staff_role == "STAFF":
        return "STAFF", False
    if orga_role == "FOLLOWER":
        return "FOLLOWER", False
    if orga_role == "MEMBER":
        return "MEMBER", False
    return "MEMBER", False


def _event_bucket(row: Event, now: datetime) -> str:
    now = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    starts_at = row.starts_at if row.starts_at.tzinfo is not None else row.starts_at.replace(tzinfo=timezone.utc)
    ends_at = row.ends_at if row.ends_at.tzinfo is not None else row.ends_at.replace(tzinfo=timezone.utc)
    if starts_at <= now <= ends_at:
        return "LIVE"
    tz_name = (row.timezone or "Europe/Brussels").strip() or "Europe/Brussels"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
    local_now = now.astimezone(tz)
    local_start = starts_at.astimezone(tz)
    if local_start.date() == local_now.date() and starts_at > now:
        return "TODAY"
    if starts_at > now:
        return "UPCOMING"
    return "PAST"


def _event_summary_payload(db: Session, *, row: Event, user_id: str, joined_ids: set[int], runtime_map: dict[int, EventRuntimeState]) -> dict[str, Any]:
    role_for_me, can_manage = _event_role_for_user(db, event=row, user_id=user_id)
    runtime = runtime_map.get(row.id)
    status = ((runtime.state if runtime else None) or row.event_state or "LIVE").upper()
    return {
        "id": row.id,
        "name": row.name,
        "startAt": row.starts_at.isoformat(),
        "endAt": row.ends_at.isoformat(),
        "venue": row.venue,
        "publicationStatus": (row.publication_status or "DRAFT").upper(),
        "visibility": (row.visibility or "PRIVATE").upper(),
        "status": status,
        "eventState": status,
        "modulesOn": row.modules_on or {},
        "host_type": (row.host_type or "user").lower(),
        "host_id": row.host_id,
        "roleForMe": role_for_me,
        "canManage": can_manage,
        "joined": row.id in joined_ids,
    }


@app.get("/me/events")
def my_events(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    now = now_utc()
    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.status == "ACTIVE",
        OrganizationMembership.revoked_at.is_(None),
        or_(OrganizationMembership.starts_at.is_(None), OrganizationMembership.starts_at <= now),
        or_(OrganizationMembership.ends_at.is_(None), OrganizationMembership.ends_at > now),
    ).all()
    org_ids = [str(m.organization_id) for m in memberships]

    staff_event_ids = [row[0] for row in db.query(EventStaff.event_id).filter(
        EventStaff.user_id == user.id,
        EventStaff.is_active == True,  # noqa: E712
        EventStaff.revoked_at.is_(None),
        or_(EventStaff.expires_at.is_(None), EventStaff.expires_at > now),
    ).all()]

    filters = [
        ((Event.host_type == "user") & (Event.host_id == user.id)),
    ]
    if org_ids:
        filters.append((Event.host_type == "orga") & (Event.host_id.in_(org_ids)))
    if staff_event_ids:
        filters.append(Event.id.in_(staff_event_ids))

    rows = db.query(Event).filter(or_(*filters)).order_by(Event.starts_at.asc(), Event.id.asc()).all()
    event_ids = [row.id for row in rows]
    runtime_rows = db.query(EventRuntimeState).filter(EventRuntimeState.event_id.in_(event_ids)).all() if event_ids else []
    runtime_map = {row.event_id: row for row in runtime_rows}
    joined_ids = {
        row.event_id
        for row in db.query(EventJoin.event_id).filter(EventJoin.user_id == user.id, EventJoin.event_id.in_(event_ids)).all()
    } if event_ids else set()

    payload = {"LIVE": [], "TODAY": [], "UPCOMING": [], "PAST": []}
    for row in rows:
        bucket = _event_bucket(row, now)
        payload[bucket].append(_event_summary_payload(db, row=row, user_id=user.id, joined_ids=joined_ids, runtime_map=runtime_map))

    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="event.list.me",
        entity_type="app_user",
        entity_id=user.id,
        event_id=None,
        bar_id=None,
        payload={"total": len(rows)},
    )
    db.commit()
    return payload




@app.post("/events/{event_id}/checkin")
def app_event_team_checkin(event_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event introuvable")
    role, can_manage = _event_role_for_user(db, event=event, user_id=user.id)
    if not can_manage and role != "STAFF":
        raise HTTPException(status_code=403, detail="Non autorisé")

    already = db.query(EventSafetyCheckin).filter(
        EventSafetyCheckin.event_id == event_id,
        EventSafetyCheckin.user_id == user.id,
        EventSafetyCheckin.type == "TEAM_CHECKIN",
    ).first()
    if already:
        return {"status": "duplicate", "message": "Déjà check-in"}

    row = EventSafetyCheckin(
        event_id=event_id,
        user_id=user.id,
        type="TEAM_CHECKIN",
        created_at=now_utc(),
    )
    db.add(row)
    db.commit()
    return {"status": "ok", "message": "Check-in validé"}

@app.get("/orgas/{org_id}/events/private")
def list_orga_private_events(
    org_id: int,
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=50),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    now = now_utc()
    q = db.query(Event).filter(
        Event.host_type == "orga",
        Event.host_id == str(org_id),
    )
    if cursor:
        try:
            q = q.filter(Event.id > int(cursor))
        except ValueError:
            raise HTTPException(status_code=400, detail={"reason": "invalid_cursor"})
    rows = q.order_by(Event.id.asc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    clipped = rows[:limit]
    event_ids = [row.id for row in clipped]
    runtime_rows = db.query(EventRuntimeState).filter(EventRuntimeState.event_id.in_(event_ids)).all() if event_ids else []
    runtime_map = {row.event_id: row for row in runtime_rows}
    joined_ids = {
        row.event_id
        for row in db.query(EventJoin.event_id).filter(EventJoin.user_id == user.id, EventJoin.event_id.in_(event_ids)).all()
    } if event_ids else set()
    payload = {"LIVE": [], "TODAY": [], "UPCOMING": [], "PAST": []}
    for row in clipped:
        bucket = _event_bucket(row, now)
        payload[bucket].append(_event_summary_payload(db, row=row, user_id=user.id, joined_ids=joined_ids, runtime_map=runtime_map))
    payload["nextCursor"] = str(clipped[-1].id) if has_more and clipped else None
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="event.list.orga.private",
        entity_type="organization",
        entity_id=str(org_id),
        event_id=None,
        bar_id=None,
        payload={"total": len(clipped), "cursor": cursor, "nextCursor": payload["nextCursor"]},
    )
    db.commit()
    return payload


@app.get("/events/{event_id}/manage_snapshot", response_model=EventManageSnapshotOut)
def event_manage_snapshot(event_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_host_write_perms(db, event, user)
    current = db.query(StaffInviteToken).filter(
        StaffInviteToken.event_id == event_id,
        StaffInviteToken.is_revoked == False,  # noqa: E712
    ).order_by(StaffInviteToken.created_at.desc()).first()
    payload = {
        "eventId": event.id,
        "publicationStatus": (event.publication_status or "DRAFT").upper(),
        "visibility": (event.visibility or "PRIVATE").upper(),
        "runtime": _app_event_runtime_payload(db, event),
        "share": _app_event_share_payload(event, include_staff=True),
        "qrPackAvailable": True,
        "staffInviteCodeCurrent": current.token if current is not None else None,
    }
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="app_user",
        action="event.manage_snapshot.get",
        entity_type="event",
        entity_id=str(event.id),
        event_id=event.id,
        bar_id=event.bar_id,
        payload={"scope": f"{event.host_type}:{event.host_id}"},
    )
    db.commit()
    return payload


@app.get("/orgas/{org_id}/events")
def list_orga_public_events(org_id: int, db: Session = Depends(get_db)):
    now = now_utc()
    rows = db.query(Event).filter(
        Event.host_type == "orga",
        Event.host_id == str(org_id),
        Event.visibility == "PUBLIC",
        Event.publication_status == "PUBLISHED",
    ).order_by(Event.starts_at.asc()).all()
    event_ids = [row.id for row in rows]
    runtime_rows = db.query(EventRuntimeState).filter(EventRuntimeState.event_id.in_(event_ids)).all() if event_ids else []
    runtime_map = {row.event_id: row for row in runtime_rows}
    items = []
    for row in rows:
        summary = _event_summary_payload(db, row=row, user_id="", joined_ids=set(), runtime_map=runtime_map)
        items.append({
            **summary,
            "bucket": _event_bucket(row, now),
            "event_code": row.event_code,
        })
    return {"items": items}


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

    code = canonicalize_manual_code(payload.code)
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
        response = {"ok": True, "organization_id": invite.organization_id, "role": membership.role, "status": membership.status, "idempotent": True}
        db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action="orga_join_by_code", idempotency_key=key, response_json=response))
        db.commit()
        return response

    membership = OrganizationMembership(
        organization_id=invite.organization_id,
        user_id=user.id,
        role=invite.role,
        status="ACTIVE",
        joined_at=now,
        starts_at=now,
        validation_source="INVITE",
        validated_by_user_id=invite.created_by_user_id,
        validated_at=now,
        updated_at=now,
        created_by_user_id=invite.created_by_user_id,
        created_at=now,
    )
    invite.used_count += 1
    db.add(membership)
    response = {"ok": True, "organization_id": invite.organization_id, "role": invite.role, "status": "ACTIVE", "idempotent": False}
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


@app.post("/orgas/{org_id}/invites")
def create_orga_invite(
    org_id: int,
    payload: OrgaInviteCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    actor = _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    key = ensure_idempotency_key(idempotency_key)
    action = "orga_invite_create"
    idem = db.query(OrganizationInviteIdempotency).filter(
        OrganizationInviteIdempotency.org_id == org_id,
        OrganizationInviteIdempotency.action == action,
        OrganizationInviteIdempotency.idempotency_key == key,
    ).first()
    if idem:
        return idem.response_json

    invite_type = _orga_invite_target_role(payload.inviteType)
    expires_at = None
    if payload.expiresInHours is not None:
        expires_at = now_utc() + timedelta(hours=int(payload.expiresInHours))

    while True:
        code = _generate_orga_invite_code()
        code_hash = _orga_invite_code_hash(code)
        exists = db.query(OrganizationInviteLink.id).filter(OrganizationInviteLink.code_hash == code_hash).first()
        if not exists:
            break

    invite = OrganizationInviteLink(
        org_id=org_id,
        code_short=code[-4:],
        code_hash=code_hash,
        invite_type=invite_type,
        status="ACTIVE",
        expires_at=expires_at,
        created_by_user_id=user.id,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(invite)
    db.flush()

    response = {
        "id": invite.id,
        "org_id": org_id,
        "inviteType": invite_type,
        "status": "ACTIVE",
        "expiresAt": _serialize_dt(expires_at),
        "code": code,
        "suffix": invite.code_short,
        "deeplink": f"tore://open?type=orga_invite&code={code}",
        "webUrl": f"{_public_app_base_url()}/open?type=orga_invite&code={code}",
        "qrPayload": f"tore://open?type=orga_invite&code={code}",
    }
    db.add(OrganizationInviteIdempotency(org_id=org_id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="orga_invite_created",
        entity_type="orga_invite",
        entity_id=str(invite.id),
        event_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={"org_id": org_id, "invite_type": invite_type, "expires_at": _serialize_dt(expires_at)},
    )
    db.commit()
    return response


@app.get("/orgas/{org_id}/invites")
def list_orga_invites(
    org_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actor = _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    rows = db.query(OrganizationInviteLink).filter(OrganizationInviteLink.org_id == org_id).order_by(OrganizationInviteLink.id.desc()).all()
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="orga_invites_listed",
        entity_type="organization",
        entity_id=str(org_id),
        event_id=None,
        bar_id=None,
        payload={"count": len(rows)},
    )
    db.commit()
    return {
        "items": [
            {
                "id": row.id,
                "inviteType": (row.invite_type or "MEMBER").upper(),
                "status": (row.status or "ACTIVE").upper(),
                "suffix": row.code_short,
                "expiresAt": _serialize_dt(row.expires_at),
                "revokedAt": _serialize_dt(row.revoked_at),
                "createdAt": _serialize_dt(row.created_at),
            }
            for row in rows
        ]
    }


@app.post("/orgas/{org_id}/invites/{invite_id}/revoke")
def revoke_orga_invite(
    org_id: int,
    invite_id: int,
    payload: OrgaInviteRevokeIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    actor = _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_invite_revoke:{invite_id}"
    idem = db.query(OrganizationInviteIdempotency).filter(
        OrganizationInviteIdempotency.org_id == org_id,
        OrganizationInviteIdempotency.action == action,
        OrganizationInviteIdempotency.idempotency_key == key,
    ).first()
    if idem:
        return idem.response_json

    invite = db.query(OrganizationInviteLink).filter(OrganizationInviteLink.id == invite_id, OrganizationInviteLink.org_id == org_id).first()
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")

    invite.status = "REVOKED"
    invite.revoked_at = now_utc()
    invite.revoked_reason = payload.reason.strip()
    invite.updated_at = now_utc()
    response = {"ok": True, "id": invite.id, "status": invite.status, "revokedAt": _serialize_dt(invite.revoked_at)}
    db.add(OrganizationInviteIdempotency(org_id=org_id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="orga_invite_revoked",
        entity_type="orga_invite",
        entity_id=str(invite.id),
        event_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={"reason": payload.reason.strip()},
    )
    db.commit()
    return response


@app.post("/orgas/join_by_invite")
def join_orga_by_invite(
    payload: OrgaJoinByInviteIn,
    request: Request,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    key = ensure_idempotency_key(idempotency_key)
    idem = db.query(OrganizationWriteIdempotency).filter(
        OrganizationWriteIdempotency.actor_user_id == user.id,
        OrganizationWriteIdempotency.action == "orga_join_by_invite",
        OrganizationWriteIdempotency.idempotency_key == key,
    ).first()
    if idem:
        return idem.response_json

    client_ip = (request.client.host if request.client else "unknown")
    enforce_rate_limit("orga_invite_join", f"{user.id}:{client_ip}")

    normalized = canonicalize_manual_code(payload.code)
    code_hash = _orga_invite_code_hash(normalized)
    invite = db.query(OrganizationInviteLink).filter(OrganizationInviteLink.code_hash == code_hash).first()
    now = now_utc()
    if invite is None:
        raise HTTPException(status_code=404, detail={"reason": "INVALID_CODE"})
    if invite.status != "ACTIVE":
        raise HTTPException(status_code=400, detail={"reason": "INVITE_NOT_ACTIVE"})
    if invite.expires_at and invite.expires_at < now:
        invite.status = "EXPIRED"
        invite.updated_at = now
        db.commit()
        raise HTTPException(status_code=400, detail={"reason": "EXPIRED_CODE"})

    target_role = _orga_invite_target_role(invite.invite_type)
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == invite.org_id,
        OrganizationMembership.user_id == user.id,
    ).first()
    idempotent = False
    if membership:
        current_rank = _ORGA_ROLE_RANK.get((membership.role or "FOLLOWER").upper(), 0)
        target_rank = _ORGA_ROLE_RANK.get(target_role, 0)
        if membership.status == "ACTIVE" and current_rank >= target_rank:
            idempotent = True
        else:
            membership.role = target_role if target_rank >= current_rank else membership.role
            membership.status = "ACTIVE"
            membership.updated_at = now
            if membership.joined_at is None:
                membership.joined_at = now
    else:
        membership = OrganizationMembership(
            organization_id=invite.org_id,
            user_id=user.id,
            role=target_role,
            status="ACTIVE",
            joined_at=now,
            starts_at=now,
            validation_source="INVITE",
            validated_by_user_id=invite.created_by_user_id,
            validated_at=now,
            updated_at=now,
            created_by_user_id=invite.created_by_user_id,
            created_at=now,
        )
        db.add(membership)

    response = {
        "ok": True,
        "organization_id": invite.org_id,
        "role": membership.role,
        "status": membership.status,
        "idempotent": idempotent,
    }
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action="orga_join_by_invite", idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=membership.role,
        action="orga_join_by_invite",
        entity_type="organization_membership",
        entity_id=f"{invite.org_id}:{user.id}",
        event_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={"invite_id": invite.id, "invite_type": invite.invite_type},
    )
    db.commit()
    return response


@app.get("/orgas/invites/{code}/preview")
def orga_invite_preview(code: str, db: Session = Depends(get_db)):
    normalized = (code or "").strip().upper()
    invite = db.query(OrganizationInviteLink).filter(OrganizationInviteLink.code_hash == _orga_invite_code_hash(normalized)).first()
    if invite is None:
        raise HTTPException(status_code=404, detail={"reason": "not_found"})
    org = db.get(Organization, invite.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail={"reason": "not_found"})
    if (org.visibility or "PUBLIC").upper() != "PUBLIC":
        raise HTTPException(status_code=404, detail={"reason": "not_found"})
    return {
        "org": {"name": org.name, "city": org.city},
        "inviteType": invite.invite_type,
        "status": invite.status,
        "expiresAt": _serialize_dt(invite.expires_at),
    }


@app.get("/orgas/{org_id}/share", response_model=OrgaShareOut)
def get_orga_share(
    org_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    user = None
    raw = _extract_bearer_token(authorization)
    if raw:
        user = _resolve_app_user_from_token(raw, db)
    if (org.visibility or "PUBLIC").upper() != "PUBLIC":
        if user is None:
            raise HTTPException(status_code=403, detail={"reason": "auth_required"})
        membership = _membership_for(db, org_id=org_id, user_id=user.id)
        if membership is None:
            raise HTTPException(status_code=403, detail={"reason": "forbidden"})
    return _orga_share_payload(org)


@app.get("/orgas/{org_id}/invite", response_model=OrgaInviteOut)
def get_orga_invite(
    org_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = create_orga_invite(
        org_id=org_id,
        payload=OrgaInviteCreateIn(inviteType="MEMBER", expiresInHours=24 * 7),
        user=user,
        db=db,
        idempotency_key=f"legacy-orga-invite-{org_id}-{user.id}",
    )

    code = payload["code"]
    return {
        "org_id": org_id,
        "invite_code": code,
        "code": code,
        "deeplink": payload["deeplink"],
        "https_link": payload["webUrl"],
        "qr_payload": payload["qrPayload"],
        "expires_at": payload["expiresAt"],
    }


@app.get("/orgas/{org_id}/members")
def list_orga_members(org_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    rows = db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org_id).order_by(OrganizationMembership.joined_at.asc()).all()
    return {"items": [{"id": r.id, "user_id": r.user_id, "role": r.role, "status": r.status, "joined_at": _serialize_dt(r.joined_at)} for r in rows]}


@app.post("/orgas/{org_id}/members")
def upsert_orga_member(org_id: int, payload: OrgaMemberUpsertIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    actor = _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_members_upsert:{org_id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem:
        return idem.response_json
    row = db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org_id, OrganizationMembership.user_id == payload.user_id).first()
    target_role = payload.role.upper()
    if target_role == "OWNER" and (actor.role or "").upper() != "OWNER":
        raise HTTPException(status_code=403, detail={"reason": "owner_only"})
    if payload.user_id == user.id and _ORGA_ROLE_RANK.get(target_role, -1) > _ORGA_ROLE_RANK.get((actor.role or "MEMBER").upper(), -1):
        raise HTTPException(status_code=403, detail={"reason": "cannot_self_promote"})
    if row:
        row.role = target_role
        row.status = "ACTIVE"
        row.validation_source = "AUTHORIZED_APPROVAL"
        row.validated_by_user_id = user.id
        row.validated_at = now_utc()
        row.revoked_at = None
        row.updated_at = now_utc()
    else:
        row = OrganizationMembership(organization_id=org_id, user_id=payload.user_id, role=target_role, status="ACTIVE", joined_at=now_utc(), starts_at=now_utc(), updated_at=now_utc(), created_by_user_id=user.id, validation_source="AUTHORIZED_APPROVAL", validated_by_user_id=user.id, validated_at=now_utc(), created_at=now_utc())
        db.add(row)
    response = {"ok": True, "idempotent": False, "organization_id": org_id, "user_id": payload.user_id, "role": row.role}
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(db, actor_user_id=user.id, actor_partner_id=None, actor_role=actor.role, action="organization.membership.upsert", entity_type="organization_membership", entity_id=f"{org_id}:{payload.user_id}", event_id=None, bar_id=None, idempotency_key=key, payload={"scope": f"orga:{org_id}", "role": row.role})
    db.commit()
    return response


@app.get("/orgas/{org_id}/memberships/me")
def orga_my_membership(org_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_orga_or_404(db, org_id)
    row = _membership_any_status(db, org_id=org_id, user_id=user.id)
    return {"membership": _membership_snapshot(row)}


@app.get("/orgas/{org_id}/memberships")
def list_orga_memberships(org_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_orga_or_404(db, org_id)
    _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    rows = db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org_id).order_by(OrganizationMembership.created_at.asc()).all()
    return {"items": [_membership_snapshot(r) for r in rows]}


@app.post("/orgas/{org_id}/join")
def join_orga(org_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _get_orga_or_404(db, org_id)
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_join:{org_id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem:
        return idem.response_json

    now = now_utc()
    join_mode = (org.join_mode or "OPEN_MEMBERSHIP").upper()
    target_role = "FOLLOWER" if join_mode == "FOLLOW_ONLY" else "MEMBER"
    target_status = "PENDING" if join_mode == "REQUEST_TO_JOIN" else "ACTIVE"

    row = _membership_any_status(db, org_id=org_id, user_id=user.id)
    if row is not None and ((row.status or "").upper() == "REVOKED" or row.revoked_at is not None):
        raise HTTPException(status_code=403, detail={"reason": "affiliation_revoked"})
    idempotent = False
    if row is None:
        row = OrganizationMembership(organization_id=org_id, user_id=user.id, role=target_role, status=target_status, joined_at=now, starts_at=now, updated_at=now, created_by_user_id=user.id, validation_source=("SELF_REQUEST" if target_status == "PENDING" else "JOIN_POLICY"), validated_at=(None if target_status == "PENDING" else now), created_at=now)
        db.add(row)
        db.flush()
    else:
        if row.role == target_role and row.status == target_status:
            idempotent = True
        else:
            row.role = target_role
            row.status = target_status
            row.updated_at = now

    response = {"ok": True, "idempotent": idempotent, "organization_id": org_id, "join_mode": join_mode, "membership": _membership_snapshot(row)}
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(db, actor_user_id=user.id, actor_partner_id=None, actor_role=target_role, action="organization.membership.join", entity_type="organization_membership", entity_id=f"{org_id}:{user.id}", event_id=None, bar_id=None, idempotency_key=key, payload={"scope": f"orga:{org_id}", "join_mode": join_mode, "status": target_status})
    db.commit()
    return response


@app.post("/orgas/{org_id}/leave")
def leave_orga(org_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    _get_orga_or_404(db, org_id)
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_leave:{org_id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem:
        return idem.response_json
    row = _membership_any_status(db, org_id=org_id, user_id=user.id)
    if not row or row.status == "LEFT":
        response = {"ok": True, "idempotent": True, "organization_id": org_id}
    else:
        row.status = "LEFT"
        row.ends_at = row.ends_at or now_utc()
        row.updated_at = now_utc()
        response = {"ok": True, "idempotent": False, "organization_id": org_id, "membership": _membership_snapshot(row)}
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(db, actor_user_id=user.id, actor_partner_id=None, actor_role=(row.role if row else "MEMBER"), action="organization.membership.leave", entity_type="organization_membership", entity_id=f"{org_id}:{user.id}", event_id=None, bar_id=None, idempotency_key=key, payload={"scope": f"orga:{org_id}"})
    db.commit()
    return response


@app.post("/orgas/{org_id}/memberships/{member_user_id}/approve")
def approve_orga_membership(org_id: int, member_user_id: str, payload: MembershipDecisionIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    actor = _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_approve:{org_id}:{member_user_id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem:
        return idem.response_json

    row = _membership_any_status(db, org_id=org_id, user_id=member_user_id)
    if row is None:
        raise HTTPException(404, "Membership not found")
    if row.status == "ACTIVE":
        idempotent = True
    else:
        row.status = "ACTIVE"
        row.starts_at = row.starts_at or now_utc()
        row.validation_source = "AUTHORIZED_APPROVAL"
        row.validated_by_user_id = user.id
        row.validated_at = now_utc()
        row.revoked_at = None
        row.updated_at = now_utc()
        idempotent = False
    response = {"ok": True, "idempotent": idempotent, "organization_id": org_id, "membership": _membership_snapshot(row)}
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(db, actor_user_id=user.id, actor_partner_id=None, actor_role=actor.role, action="organization.membership.approve", entity_type="organization_membership", entity_id=f"{org_id}:{member_user_id}", event_id=None, bar_id=None, idempotency_key=key, payload={"scope": f"orga:{org_id}", "reason": (payload.reason or "").strip() or None})
    db.commit()
    return response


@app.post("/orgas/{org_id}/memberships/{member_user_id}/reject")
def reject_orga_membership(org_id: int, member_user_id: str, payload: MembershipRejectIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    actor = _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_reject:{org_id}:{member_user_id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem:
        return idem.response_json

    row = _membership_any_status(db, org_id=org_id, user_id=member_user_id)
    if row is None:
        raise HTTPException(404, "Membership not found")
    if row.status == "REJECTED":
        idempotent = True
    else:
        row.status = "REJECTED"
        row.updated_at = now_utc()
        idempotent = False
    response = {"ok": True, "idempotent": idempotent, "organization_id": org_id, "membership": _membership_snapshot(row)}
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(db, actor_user_id=user.id, actor_partner_id=None, actor_role=actor.role, action="organization.membership.reject", entity_type="organization_membership", entity_id=f"{org_id}:{member_user_id}", event_id=None, bar_id=None, idempotency_key=key, payload={"scope": f"orga:{org_id}", "reason": payload.reason.strip()})
    db.commit()
    return response


@app.post("/orgas/{org_id}/memberships/{member_user_id}/set_role")
def set_orga_membership_role(
    org_id: int,
    member_user_id: str,
    payload: MembershipSetRoleIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    actor = _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_role_set:{org_id}:{member_user_id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem:
        return idem.response_json

    row = _membership_any_status(db, org_id=org_id, user_id=member_user_id)
    if row is None:
        raise HTTPException(404, "Membership not found")
    target_role = payload.role.upper()
    if target_role == "OWNER" and actor.role != "OWNER":
        raise HTTPException(status_code=403, detail={"reason": "owner_only"})
    if actor.role == "MANAGER" and (row.role or "MEMBER").upper() == "OWNER":
        raise HTTPException(status_code=403, detail={"reason": "forbidden_target"})
    if row.user_id == user.id and (row.role or "MEMBER").upper() == "OWNER" and target_role != "OWNER":
        raise HTTPException(status_code=400, detail={"reason": "cannot_demote_self_owner"})

    idempotent = (row.role or "").upper() == target_role and (row.status or "ACTIVE").upper() == "ACTIVE"
    row.role = target_role
    row.status = "ACTIVE"
    row.validation_source = "AUTHORIZED_APPROVAL"
    row.validated_by_user_id = user.id
    row.validated_at = now_utc()
    row.revoked_at = None
    row.updated_at = now_utc()

    response = {"ok": True, "idempotent": idempotent, "organization_id": org_id, "membership": _membership_snapshot(row)}
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_user_id=user.id,
        actor_partner_id=None,
        actor_role=actor.role,
        action="orga_member_role_changed",
        entity_type="organization_membership",
        entity_id=f"{org_id}:{member_user_id}",
        event_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={"scope": f"orga:{org_id}", "reason": payload.reason.strip(), "role": target_role},
    )
    db.commit()
    return response


@app.post("/orgas/{org_id}/memberships/{member_user_id}/remove")
def remove_orga_membership(
    org_id: int,
    member_user_id: str,
    payload: MembershipRemoveIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    actor = _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_member_remove:{org_id}:{member_user_id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem:
        return idem.response_json

    row = _membership_any_status(db, org_id=org_id, user_id=member_user_id)
    if row is None:
        raise HTTPException(404, "Membership not found")
    if (row.role or "MEMBER").upper() == "OWNER":
        raise HTTPException(status_code=400, detail={"reason": "cannot_remove_owner"})

    idempotent = (row.status or "ACTIVE").upper() == "LEFT"
    row.status = "LEFT"
    row.ends_at = row.ends_at or now_utc()
    row.updated_at = now_utc()

    response = {"ok": True, "idempotent": idempotent, "organization_id": org_id, "membership": _membership_snapshot(row)}
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_user_id=user.id,
        actor_partner_id=None,
        actor_role=actor.role,
        action="orga_member_removed",
        entity_type="organization_membership",
        entity_id=f"{org_id}:{member_user_id}",
        event_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={"scope": f"orga:{org_id}", "reason": payload.reason.strip()},
    )
    db.commit()
    return response


@app.post("/orgas/{org_id}/follow")
def follow_orga(org_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    _get_orga_or_404(db, org_id)
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_follow:{org_id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem:
        return idem.response_json
    row = _membership_any_status(db, org_id=org_id, user_id=user.id)
    if row and row.role == "FOLLOWER" and row.status == "ACTIVE":
        response = {"ok": True, "idempotent": True, "organization_id": org_id, "role": "FOLLOWER"}
    else:
        if not row:
            row = OrganizationMembership(organization_id=org_id, user_id=user.id, role="FOLLOWER", status="ACTIVE", joined_at=now_utc(), starts_at=now_utc(), updated_at=now_utc(), created_by_user_id=user.id, validation_source="FOLLOW_POLICY", validated_at=now_utc(), created_at=now_utc())
            db.add(row)
        else:
            row.role = "FOLLOWER"
            row.status = "ACTIVE"
            row.updated_at = now_utc()
        response = {"ok": True, "idempotent": False, "organization_id": org_id, "role": "FOLLOWER"}
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(db, actor_user_id=user.id, actor_partner_id=None, actor_role="FOLLOWER", action="organization.follow", entity_type="organization_membership", entity_id=f"{org_id}:{user.id}", event_id=None, bar_id=None, idempotency_key=key, payload={"scope": f"orga:{org_id}"})
    db.commit()
    return response


@app.post("/orgas/{org_id}/unfollow")
def unfollow_orga(org_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    _get_orga_or_404(db, org_id)
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_unfollow:{org_id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem:
        return idem.response_json
    row = db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org_id, OrganizationMembership.user_id == user.id, OrganizationMembership.role == "FOLLOWER").first()
    if row and row.status != "LEFT":
        row.status = "LEFT"
        row.updated_at = now_utc()
        response = {"ok": True, "idempotent": False, "organization_id": org_id}
    else:
        response = {"ok": True, "idempotent": True, "organization_id": org_id}
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(db, actor_user_id=user.id, actor_partner_id=None, actor_role="FOLLOWER", action="organization.unfollow", entity_type="organization_membership", entity_id=f"{org_id}:{user.id}", event_id=None, bar_id=None, idempotency_key=key, payload={"scope": f"orga:{org_id}"})
    db.commit()
    return response


@app.get("/orgas/{org_id}/posts")
def list_orga_posts(org_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    if org.visibility == "PRIVATE":
        if not user or not _membership_for(db, org_id=org_id, user_id=user.id):
            raise HTTPException(403, "Forbidden")
    rows = db.query(OrgaPost).filter(OrgaPost.organization_id == org_id, OrgaPost.deleted_at.is_(None)).order_by(OrgaPost.pinned.desc(), OrgaPost.created_at.desc()).all()
    return {"items": [{"id": r.id, "organization_id": r.organization_id, "author_user_id": r.author_user_id, "text": r.text, "image_url": r.image_url, "pinned": bool(r.pinned), "created_at": _serialize_dt(r.created_at)} for r in rows]}


@app.post("/orgas/{org_id}/posts")
def create_orga_post(org_id: int, payload: OrgaPostCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    membership = _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MEMBER")
    enforce_rate_limit("orga_posts_create", f"{org_id}:{user.id}")
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_post_create:{org_id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem:
        return idem.response_json
    row = OrgaPost(organization_id=org_id, author_user_id=user.id, text=payload.text.strip(), image_url=(payload.image_url or "").strip() or None, pinned=False, created_at=now_utc())
    db.add(row)
    db.flush()
    response = {"id": row.id, "organization_id": org_id, "author_user_id": user.id, "text": row.text, "image_url": row.image_url, "pinned": False, "created_at": _serialize_dt(row.created_at)}
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(db, actor_user_id=user.id, actor_partner_id=None, actor_role=membership.role, action="organization.post.create", entity_type="organization_post", entity_id=str(row.id), event_id=None, bar_id=None, idempotency_key=key, payload={"scope": f"orga:{org_id}"})
    db.commit()
    return response


@app.post("/orgas/{org_id}/posts/{post_id}/pin")
def pin_orga_post(org_id: int, post_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    membership = _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_post_pin:{post_id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem:
        return idem.response_json
    row = db.get(OrgaPost, post_id)
    if not row or row.organization_id != org_id:
        raise HTTPException(404, "Post not found")
    row.pinned = True
    response = {"ok": True, "post_id": post_id, "pinned": True}
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(db, actor_user_id=user.id, actor_partner_id=None, actor_role=membership.role, action="organization.post.pin", entity_type="organization_post", entity_id=str(post_id), event_id=None, bar_id=None, idempotency_key=key, payload={"scope": f"orga:{org_id}"})
    db.commit()
    return response


@app.post("/orgas/{org_id}/posts/{post_id}/delete")
def delete_orga_post(org_id: int, post_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    membership = _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_post_delete:{post_id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem:
        return idem.response_json
    row = db.get(OrgaPost, post_id)
    if not row or row.organization_id != org_id:
        raise HTTPException(404, "Post not found")
    row.deleted_at = now_utc()
    response = {"ok": True, "post_id": post_id, "deleted": True}
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(db, actor_user_id=user.id, actor_partner_id=None, actor_role=membership.role, action="organization.post.delete", entity_type="organization_post", entity_id=str(post_id), event_id=None, bar_id=None, idempotency_key=key, payload={"scope": f"orga:{org_id}"})
    db.commit()
    return response


_PROFILE_VISIBILITIES = {"PUBLIC", "TORE_USERS", "PRIVATE"}
_STRUCTURE_AUTH_ROLES = {"OWNER", "PRESIDENT", "BUREAU", "TRESORIER", "MANAGER", "STAFF"}


def _normalized_visibility(value: Optional[str]) -> str:
    normalized = (value or "PRIVATE").upper()
    return normalized if normalized in _PROFILE_VISIBILITIES else "PRIVATE"


def _profile_privacy(db: Session, user_id: str) -> AppUserPrivacySetting:
    row = db.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id == user_id).first()
    if row is None:
        row = AppUserPrivacySetting(user_id=user_id)
    return row


def _optional_app_user(authorization: Optional[str], db: Session) -> Optional[AppUser]:
    raw = _extract_bearer_token(authorization)
    return _resolve_app_user_from_token(raw, db) if raw else None


def _viewer_kind(*, target: AppUser, viewer: Optional[AppUser], forced: Optional[str] = None) -> str:
    if forced:
        return forced
    if viewer and viewer.id == target.id:
        return "OWNER"
    if viewer and (viewer.global_role or "USER").upper() in {"ADMIN", "SUPPORT"}:
        return "ADMIN"
    if viewer and not bool(viewer.is_guest):
        return "TORE_USER"
    return "PUBLIC"


def _can_see(level: Optional[str], viewer_kind: str) -> bool:
    if viewer_kind in {"OWNER", "ADMIN"}:
        return True
    normalized = _normalized_visibility(level)
    if normalized == "PUBLIC":
        return True
    return normalized == "TORE_USERS" and viewer_kind == "TORE_USER"


def _affiliation_payload(row: OrganizationMembership, org: Organization) -> dict[str, Any]:
    status = (row.status or "PENDING").upper()
    if row.revoked_at is not None:
        status = "REVOKED"
    elif row.ends_at is not None and row.ends_at <= now_utc():
        status = "ENDED"
    elif status == "LEFT":
        status = "ENDED"
    return {
        "id": row.id,
        "structure": {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "city": org.city,
            "public_path": f"/orgas/{org.id}",
        },
        "role": (row.role or "MEMBER").upper(),
        "status": status,
        "starts_at": _serialize_dt(row.starts_at or row.joined_at),
        "ends_at": _serialize_dt(row.ends_at),
        "mandate": row.mandate_label,
        "visibility": _normalized_visibility(row.visibility),
        "validation_source": row.validation_source or "LEGACY",
        "revoked_at": _serialize_dt(row.revoked_at),
    }


def _profile_affiliations(db: Session, user_id: str) -> list[tuple[OrganizationMembership, Organization]]:
    return db.execute(
        select(OrganizationMembership, Organization)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .where(OrganizationMembership.user_id == user_id)
        .order_by(OrganizationMembership.starts_at.desc(), OrganizationMembership.id.desc())
    ).all()


def _serialize_profile(
    db: Session,
    *,
    target: AppUser,
    viewer: Optional[AppUser],
    forced_viewer_kind: Optional[str] = None,
) -> dict[str, Any]:
    privacy = _profile_privacy(db, target.id)
    kind = _viewer_kind(target=target, viewer=viewer, forced=forced_viewer_kind)
    if not _can_see(privacy.visibility, kind):
        raise HTTPException(status_code=403, detail={"reason": "profile_private"})

    result: dict[str, Any] = {
        "id": target.id,
        "username": target.username,
        "display_name": target.display_name,
        "city": target.city,
        "created_at": _serialize_dt(target.created_at),
        "updated_at": _serialize_dt(target.updated_at),
        "viewer_context": kind,
    }
    if kind == "OWNER":
        result.update({
            "email": target.email,
            "first_name": target.first_name,
            "last_name": target.last_name,
            "nickname": target.nickname,
            "phone": target.phone,
            "instagram_handle": target.instagram_handle,
            "address_text": target.address_text,
            "oripeaux": target.oripeaux or "",
        })
    if _can_see(privacy.photo_visibility, kind):
        result["avatar_url"] = target.avatar_url
    if _can_see(privacy.bio_visibility, kind):
        result["bio"] = target.bio or ""

    if _can_see(privacy.affiliations_visibility, kind):
        affiliations = []
        for membership, org in _profile_affiliations(db, target.id):
            if kind not in {"OWNER", "ADMIN"}:
                if (membership.status or "").upper() != "ACTIVE" or membership.revoked_at is not None:
                    continue
                if not _can_see(membership.visibility, kind):
                    continue
            affiliations.append(_affiliation_payload(membership, org))
        result["affiliations"] = affiliations

    if privacy.event_history_opt_in and _can_see(privacy.event_history_visibility, kind):
        joined = db.execute(
            select(EventJoin, Event)
            .join(Event, Event.id == EventJoin.event_id)
            .where(EventJoin.user_id == target.id)
            .order_by(Event.starts_at.desc())
            .limit(25)
        ).all()
        result["event_history"] = [
            {"id": event.id, "name": event.name, "starts_at": _serialize_dt(event.starts_at)}
            for _, event in joined
            if kind in {"OWNER", "ADMIN"}
            or ((event.visibility or "PRIVATE").upper() == "PUBLIC" and (event.publication_status or "DRAFT").upper() == "PUBLISHED")
        ]

    # Badges and gamification are intentionally absent until backed by real data.
    return result


def _owner_profile(db: Session, user: AppUser) -> dict[str, Any]:
    privacy = _profile_privacy(db, user.id)
    return {
        **_serialize_profile(db, target=user, viewer=user),
        "account_status": (user.account_status or "ACTIVE").upper(),
        "privacy": {
            "profile": _normalized_visibility(privacy.visibility),
            "photo": _normalized_visibility(privacy.photo_visibility),
            "bio": _normalized_visibility(privacy.bio_visibility),
            "affiliations": _normalized_visibility(privacy.affiliations_visibility),
            "badges": _normalized_visibility(privacy.badges_visibility),
            "event_history": _normalized_visibility(privacy.event_history_visibility),
            "participations": _normalized_visibility(privacy.participations_visibility),
            "gamification": _normalized_visibility(privacy.gamification_visibility),
            "event_history_opt_in": bool(privacy.event_history_opt_in),
            "participations_opt_in": bool(privacy.participations_opt_in),
            "gamification_opt_in": bool(privacy.gamification_opt_in),
        },
    }


def _effective_capabilities(db: Session, user: AppUser) -> dict[str, Any]:
    from app.services.operational_access_service import effective_capabilities_payload

    return effective_capabilities_payload(db, user)


@app.get("/profiles/{user_id}")
def get_contextual_user_profile(
    user_id: str,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    target = db.get(AppUser, user_id)
    if target is None or target.is_deleted:
        raise HTTPException(404, "User not found")
    viewer = _optional_app_user(authorization, db)
    return _serialize_profile(db, target=target, viewer=viewer)


@app.get("/users/{user_id}")
def get_public_user_profile(user_id: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    target = db.get(AppUser, user_id)
    if target is None or target.is_deleted:
        raise HTTPException(404, "User not found")
    return _serialize_profile(db, target=target, viewer=user)


@app.get("/me/profile")
def me_profile(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.is_guest:
        raise HTTPException(status_code=403, detail={"reason": "registered_account_required"})
    return _owner_profile(db, user)


@app.patch("/me/profile")
def patch_me_profile(payload: ProfilePatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.is_guest:
        raise HTTPException(status_code=403, detail={"reason": "registered_account_required"})
    row = db.get(AppUser, user.id)
    if row is None:
        raise HTTPException(404, "User not found")
    if payload.username is not None:
        username = payload.username.strip().lower()
        if not re.fullmatch(r"[a-z0-9._]{3,40}", username):
            raise HTTPException(status_code=422, detail={"reason": "invalid_username"})
        conflict = db.query(AppUser.id).filter(func.lower(AppUser.username) == username, AppUser.id != row.id).first()
        if conflict:
            raise HTTPException(status_code=409, detail={"reason": "username_already_used"})
        row.username = username
    if payload.display_name is not None:
        display_name = payload.display_name.strip()
        if not display_name:
            raise HTTPException(status_code=422, detail={"reason": "invalid_display_name"})
        row.display_name = display_name
    if payload.avatar_url is not None:
        value = payload.avatar_url.strip()
        if value and not _is_safe_public_url(value):
            raise HTTPException(status_code=422, detail={"reason": "invalid_avatar_url"})
        row.avatar_url = value or None
    if payload.bio is not None:
        row.bio = payload.bio.strip() or None
    if payload.city is not None:
        row.city = payload.city.strip() or None
    if payload.oripeaux is not None:
        row.oripeaux = payload.oripeaux.strip() or None
    row.updated_at = now_utc()
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role="USER", action="user.profile.update", entity_type="app_user", entity_id=user.id, event_id=None, bar_id=None, payload={"fields": sorted(payload.model_fields_set)})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"reason": "username_already_used"})
    db.refresh(row)
    return _owner_profile(db, row)


@app.patch("/me/privacy")
def patch_me_privacy(payload: ProfilePrivacyPatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.is_guest:
        raise HTTPException(status_code=403, detail={"reason": "registered_account_required"})
    privacy = _profile_privacy(db, user.id)
    db.add(privacy)
    mapping = {
        "profile": "visibility", "photo": "photo_visibility", "bio": "bio_visibility",
        "affiliations": "affiliations_visibility", "badges": "badges_visibility",
        "event_history": "event_history_visibility", "participations": "participations_visibility",
        "gamification": "gamification_visibility", "event_history_opt_in": "event_history_opt_in",
        "participations_opt_in": "participations_opt_in", "gamification_opt_in": "gamification_opt_in",
    }
    for field in payload.model_fields_set:
        value = getattr(payload, field)
        if value is None:
            raise HTTPException(status_code=422, detail={"reason": "null_privacy_value", "field": field})
        setattr(privacy, mapping[field], value)
    privacy.updated_at = now_utc()
    user.updated_at = now_utc()
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role="USER", action="user.privacy.update", entity_type="app_user_privacy", entity_id=user.id, event_id=None, bar_id=None, payload={"fields": sorted(payload.model_fields_set)})
    db.commit()
    return _owner_profile(db, user)


@app.get("/me/affiliations")
def my_affiliations(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.is_guest:
        raise HTTPException(status_code=403, detail={"reason": "registered_account_required"})
    return {"items": [_affiliation_payload(row, org) for row, org in _profile_affiliations(db, user.id)]}


@app.get("/me/capabilities")
def my_capabilities(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.is_guest:
        return {"user_id": user.id, "global_roles": [], "structures": [], "events": [], "bars": [], "capabilities": [], "modes": {"organizer": False, "bar": False}, "evaluated_at": _serialize_dt(now_utc()), "cache_ttl_seconds": 0}
    return _effective_capabilities(db, user)


@app.get("/me/profile/preview")
def preview_my_profile(
    as_viewer: Literal["PUBLIC", "TORE_USER", "OWNER"] = Query(default="PUBLIC", alias="as"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.is_guest:
        raise HTTPException(status_code=403, detail={"reason": "registered_account_required"})
    try:
        return {"visible": True, "profile": _serialize_profile(db, target=user, viewer=user, forced_viewer_kind=as_viewer)}
    except HTTPException as exc:
        if exc.status_code == 403:
            return {"visible": False, "profile": None, "viewer_context": as_viewer}
        raise


@app.post("/affiliations/{affiliation_id}/revoke")
def revoke_affiliation(
    affiliation_id: int,
    payload: AffiliationRevokeIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.get(OrganizationMembership, affiliation_id)
    if row is None:
        raise HTTPException(404, "Affiliation not found")
    actor = _membership_for(db, org_id=row.organization_id, user_id=user.id)
    global_role = (user.global_role or "USER").upper()
    if global_role not in {"ADMIN", "SUPPORT"}:
        if actor is None or (actor.role or "MEMBER").upper() not in {"OWNER", "PRESIDENT", "MANAGER"}:
            raise HTTPException(status_code=403, detail={"reason": "forbidden"})
        if (row.role or "MEMBER").upper() == "OWNER":
            raise HTTPException(status_code=400, detail={"reason": "cannot_revoke_owner"})
    now = now_utc()
    row.status = "REVOKED"
    row.revoked_at = now
    row.revoked_by_user_id = user.id
    row.revoke_reason = payload.reason.strip()
    row.ends_at = row.ends_at or now
    row.updated_at = now
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=global_role, action="organization.affiliation.revoke", entity_type="organization_membership", entity_id=str(row.id), event_id=None, bar_id=None, payload={"organization_id": row.organization_id, "reason": payload.reason.strip()})
    db.commit()
    return {"affiliation": _affiliation_payload(row, db.get(Organization, row.organization_id)), "capabilities_effective_immediately": True}


@app.put("/me/profile")
def put_me_profile(payload: MeProfilePutIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    if user.is_guest:
        raise HTTPException(status_code=403, detail={"reason": "registered_account_required"})
    key = ensure_idempotency_key(idempotency_key)
    action = "me_profile_put"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem:
        return idem.response_json
    if not payload.display_name.strip():
        raise HTTPException(status_code=422, detail={"reason": "DISPLAY_NAME_REQUIRED", "message": "display_name required"})
    row = db.get(AppUser, user.id)
    if not row:
        raise HTTPException(404, "User not found")
    row.display_name = payload.display_name.strip()
    row.avatar_url = (payload.photo_url or "").strip() or None
    row.bio = (payload.bio or "").strip() or None
    row.instagram_handle = (payload.instagram_handle or "").strip() or None
    if payload.oripeaux is not None:
        row.oripeaux = payload.oripeaux.strip() or None
    row.profile_visibility = payload.visibility
    response = {
        "id": row.id,
        "display_name": row.display_name,
        "photo_url": row.avatar_url,
        "bio": row.bio,
        "instagram_handle": row.instagram_handle,
        "oripeaux": row.oripeaux,
        "visibility": row.profile_visibility,
    }
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))
    write_audit_log(db, actor_user_id=user.id, actor_partner_id=None, actor_role="user", action="user.profile.update", entity_type="app_user", entity_id=row.id, event_id=None, bar_id=None, idempotency_key=key, payload={"scope": f"user:{row.id}", "visibility": row.profile_visibility})
    db.commit()
    return response
