"""Autonomous startup/bootstrap helpers."""

from __future__ import annotations

import logging

from app.core.dev_bootstrap import ensure_seed
from app.core.environment import _env_bool
from app.core.settings import (
    _cors_origins,
    _validate_qr_signing_keys_format,
    validate_env_or_warn,
)
from app.utils.migrations import run_migrations_on_startup
from db import engine


def _startup_sanity_checks() -> None:
    ok, msg = _validate_qr_signing_keys_format()
    if ok:
        logging.info("startup.sanity.qr_signing_keys=%s", msg)
    else:
        logging.warning("startup.sanity.qr_signing_keys=%s", msg)

    cors = _cors_origins()
    if cors:
        logging.info("startup.sanity.cors=%s", cors)
    else:
        logging.warning("startup.sanity.cors=EMPTY_ALLOWLIST")


def _should_bootstrap_on_startup() -> bool:
    if engine.dialect.name == "sqlite":
        return True
    return _env_bool("TORE_AUTO_DB_BOOTSTRAP", default=False)


def _startup() -> None:
    run_migrations_on_startup()
    validate_env_or_warn()
    _startup_sanity_checks()
    if _should_bootstrap_on_startup():
        ensure_seed()
    else:
        logging.info(
            "Startup bootstrap disabled "
            "(expected in Postgres prod with Alembic migrations)."
        )


def run_startup(app) -> None:
    """Compatibility hook until the fresh app factory owns lifespan startup.

    The current legacy FastAPI app already has a startup event registered. Root
    compatibility wiring points that event's globals at the functions exported
    here. A later app-factory PR will register this function directly.
    """
    _ = app


__all__ = [
    "_startup",
    "_startup_sanity_checks",
    "_should_bootstrap_on_startup",
    "run_migrations_on_startup",
    "ensure_seed",
    "run_startup",
]
