from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from db import engine
from models import AuthOtpCode

_LOGGER = logging.getLogger(__name__)
_MIGRATION_LOCK = threading.Lock()
_MIGRATIONS_EXECUTED = False
_RETRY_BACKOFF_SECONDS = (1, 2, 4, 8, 16)
_TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUTHY_VALUES


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_alembic_config() -> Config:
    root = _project_root()
    alembic_ini = root / "alembic.ini"
    if not alembic_ini.exists():
        raise FileNotFoundError(f"Alembic config not found: {alembic_ini}")

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(root / "alembic"))
    return cfg


def _is_connection_error(exc: Exception) -> bool:
    current: Exception | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if isinstance(current, (OperationalError, InterfaceError)):
            return True
        if isinstance(current, DBAPIError) and bool(getattr(current, "connection_invalidated", False)):
            return True
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return False


def _run_alembic_upgrade_head() -> None:
    config = _build_alembic_config()
    command.upgrade(config, "head")


def _apply_otp_migrations() -> None:
    AuthOtpCode.__table__.create(bind=engine, checkfirst=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_otp_email_created_at ON auth_otp_codes (email, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_otp_email_used_at ON auth_otp_codes (email, used_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_otp_expires_at ON auth_otp_codes (expires_at)"))


def run_migrations_on_startup() -> None:
    global _MIGRATIONS_EXECUTED

    if not _env_bool("RUN_MIGRATIONS", default=True):
        _LOGGER.info("RUN_MIGRATIONS=0, skipping migrations")
        return

    with _MIGRATION_LOCK:
        if _MIGRATIONS_EXECUTED:
            _LOGGER.info("Migrations already applied in this process, skipping")
            return

        fatal = _env_bool("MIGRATIONS_FATAL", default=True)
        _LOGGER.info("Running migrations (RUN_MIGRATIONS=1, MIGRATIONS_FATAL=%s)", int(fatal))

        try:
            for attempt, delay in enumerate(_RETRY_BACKOFF_SECONDS, start=1):
                try:
                    _run_alembic_upgrade_head()
                    _apply_otp_migrations()
                    _LOGGER.info("Migrations applied successfully")
                    _LOGGER.info("OTP migrations applied (RUN_MIGRATIONS=1)")
                    _MIGRATIONS_EXECUTED = True
                    return
                except Exception as exc:  # pragma: no cover - retry branch split for clarity
                    if not _is_connection_error(exc):
                        raise
                    if attempt == len(_RETRY_BACKOFF_SECONDS):
                        raise
                    _LOGGER.warning("Migration attempt %s failed due to DB connection issue, retrying in %ss", attempt, delay)
                    time.sleep(delay)
        except Exception as exc:
            _LOGGER.error("Migration failed: %s", exc)
            if fatal:
                raise RuntimeError("Database migrations failed") from exc
            _LOGGER.warning("MIGRATIONS_FATAL=0, continuing startup despite migration failure")
