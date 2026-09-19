"""Canonical runtime environment helpers with no legacy dependency."""

from __future__ import annotations

import os


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolved_env_name() -> str:
    raw = (
        os.getenv("TORE_ENV")
        or os.getenv("APP_ENV")
        or os.getenv("ENV")
        or "DEV"
    ).strip().upper()
    if raw in {"PRODUCTION", "PROD"}:
        return "PROD"
    if raw in {"DEVELOPMENT", "DEV", "TEST"}:
        return "DEV"
    return raw or "DEV"


def _strict_dev_env_enabled() -> bool:
    return _resolved_env_name() == "DEV"


__all__ = ["_env_bool", "_resolved_env_name", "_strict_dev_env_enabled"]
