from __future__ import annotations

import hashlib
import logging
import math
import os
import threading
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from db import engine as _engine


class RateLimitExceeded(Exception):
    def __init__(self, scope: str, retry_after_seconds: int):
        self.scope = scope
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit exceeded for scope={scope} retry_after={retry_after_seconds}s")


class RateLimitBackendUnavailable(RuntimeError):
    pass


_RATE_LIMIT_MAX = int(os.getenv("TORE_RATE_LIMIT_MAX", "25"))
_RATE_LIMIT_WINDOW_S = int(os.getenv("TORE_RATE_LIMIT_WINDOW_S", "5"))
_SCOPE_LIMITS: dict[str, tuple[int, int]] = {
    "partner_pin_login": (5, 300),
    "partner_pin_login_ip": (30, 300),
    # Keep /orders throttling deterministic in CI/tests even if global env knobs change.
    "orders_create": (
        int(os.getenv("TORE_ORDERS_CREATE_RATE_LIMIT_MAX", "29")),
        int(os.getenv("TORE_ORDERS_CREATE_RATE_LIMIT_WINDOW_S", "60")),
    ),
    "staff_backup_join": (
        int(os.getenv("TORE_STAFF_BACKUP_JOIN_RATE_LIMIT_MAX", "10")),
        int(os.getenv("TORE_STAFF_BACKUP_JOIN_RATE_LIMIT_WINDOW_S", "60")),
    ),
    "orga_invite_join": (
        int(os.getenv("TORE_ORGA_INVITE_JOIN_RATE_LIMIT_MAX", "10")),
        int(os.getenv("TORE_ORGA_INVITE_JOIN_RATE_LIMIT_WINDOW_S", "60")),
    ),
    "codes_preview": (
        int(os.getenv("TORE_CODES_PREVIEW_RATE_LIMIT_MAX", "40")),
        int(os.getenv("TORE_CODES_PREVIEW_RATE_LIMIT_WINDOW_S", "60")),
    ),
    "shortlinks_create_user": (
        int(os.getenv("TORE_SHORTLINKS_CREATE_USER_RATE_LIMIT_MAX", "30")),
        int(os.getenv("TORE_SHORTLINKS_CREATE_USER_RATE_LIMIT_WINDOW_S", "600")),
    ),
    "auth_email_request_otp_email": (
        int(os.getenv("TORE_EMAIL_OTP_RATE_LIMIT", os.getenv("TORE_AUTH_EMAIL_OTP_PER_EMAIL_MAX", "3"))),
        int(os.getenv("TORE_EMAIL_OTP_WINDOW_SECONDS", os.getenv("TORE_AUTH_EMAIL_OTP_PER_EMAIL_WINDOW_S", "60"))),
    ),
    "auth_email_request_otp_ip": (
        int(os.getenv("TORE_AUTH_EMAIL_OTP_PER_IP_MAX", "15")),
        int(os.getenv("TORE_AUTH_EMAIL_OTP_PER_IP_WINDOW_S", "600")),
    ),
    "auth_email_verify_otp": (
        int(os.getenv("TORE_AUTH_EMAIL_OTP_VERIFY_MAX", "10")),
        int(os.getenv("TORE_AUTH_EMAIL_OTP_VERIFY_WINDOW_S", "600")),
    ),
}
_DEFAULT_SCOPE_LIMITS = dict(_SCOPE_LIMITS)

_lock = threading.Lock()
_store: dict[str, Deque[float]] = defaultdict(deque)


def _otp_scope_limit(scope: str) -> tuple[int, int] | None:
    if scope == "auth_email_request_otp_email":
        return (
            int(os.getenv("TORE_EMAIL_OTP_RATE_LIMIT", os.getenv("TORE_AUTH_EMAIL_OTP_PER_EMAIL_MAX", "3"))),
            int(os.getenv("TORE_EMAIL_OTP_WINDOW_SECONDS", os.getenv("TORE_AUTH_EMAIL_OTP_PER_EMAIL_WINDOW_S", "60"))),
        )
    if scope == "auth_email_request_otp_ip":
        return (
            int(os.getenv("TORE_AUTH_EMAIL_OTP_PER_IP_MAX", "15")),
            int(os.getenv("TORE_AUTH_EMAIL_OTP_PER_IP_WINDOW_S", "600")),
        )
    return None


_metrics = {
    "requests_total": 0,
    "rate_limited_total": 0,
    "backend_errors_total": 0,
    "http_4xx_total": 0,
    "http_5xx_total": 0,
}


def _resolved_env_name() -> str:
    raw = (
        os.getenv("TORE_ENV")
        or os.getenv("APP_ENV")
        or os.getenv("ENV")
        or "DEV"
    ).strip().upper()
    return "PROD" if raw in {"PROD", "PRODUCTION"} else "DEV" if raw in {"DEV", "DEVELOPMENT", "TEST"} else raw


def _backend_name() -> str:
    configured = (os.getenv("TORE_RATE_LIMIT_BACKEND") or "").strip().lower()
    aliases = {"db": "database", "postgres": "database", "postgresql": "database"}
    configured = aliases.get(configured, configured)
    if configured and configured not in {"memory", "database"}:
        raise RateLimitBackendUnavailable(f"Unsupported TORE_RATE_LIMIT_BACKEND={configured!r}")

    is_prod = _resolved_env_name() == "PROD"
    backend = configured or ("database" if is_prod else "memory")
    if is_prod and backend == "memory":
        raise RateLimitBackendUnavailable("In-memory rate limiting is disabled in PROD")
    if is_prod and backend == "database" and _database_store.engine.dialect.name != "postgresql":
        raise RateLimitBackendUnavailable("PROD distributed rate limiting requires PostgreSQL")
    return backend


def _scope_limit(scope: str) -> tuple[int, int]:
    max_requests, window_s = _SCOPE_LIMITS.get(scope, (_RATE_LIMIT_MAX, _RATE_LIMIT_WINDOW_S))
    otp_limit = _otp_scope_limit(scope)
    if otp_limit is not None and _SCOPE_LIMITS.get(scope) == _DEFAULT_SCOPE_LIMITS.get(scope):
        max_requests, window_s = otp_limit
    return max(1, int(max_requests)), max(1, int(window_s))


def _prune(q: Deque[float], now: float, window_s: int) -> None:
    threshold = now - window_s
    while q and q[0] < threshold:
        q.popleft()


def _memory_consume(key: str, max_requests: int, window_s: int) -> int | None:
    now = time.monotonic()
    with _lock:
        q = _store[key]
        _prune(q, now, window_s)
        if len(q) >= max_requests:
            return max(1, int(math.ceil(window_s - (now - q[0])))) if q else window_s
        q.append(now)
    return None


def _distributed_key(scope: str, actor_key: str) -> str:
    # Do not persist raw emails, IPs or user identifiers in the rate-limit table.
    digest = hashlib.sha256(actor_key.encode("utf-8")).hexdigest()
    return f"{scope}:{digest}"


class DatabaseRateLimitStore:
    """Atomic fixed-window limiter backed by a shared SQL database."""

    _UPSERT = text(
        """
        INSERT INTO rate_limit_buckets (
            bucket_key,
            window_started_at_ms,
            request_count,
            updated_at_ms
        )
        VALUES (
            :bucket_key,
            :now_ms,
            1,
            :now_ms
        )
        ON CONFLICT (bucket_key) DO UPDATE SET
            window_started_at_ms = CASE
                WHEN (:now_ms - rate_limit_buckets.window_started_at_ms) >= :window_ms
                    THEN :now_ms
                ELSE rate_limit_buckets.window_started_at_ms
            END,
            request_count = CASE
                WHEN (:now_ms - rate_limit_buckets.window_started_at_ms) >= :window_ms
                    THEN 1
                WHEN rate_limit_buckets.request_count < :blocked_count
                    THEN rate_limit_buckets.request_count + 1
                ELSE rate_limit_buckets.request_count
            END,
            updated_at_ms = :now_ms
        RETURNING request_count, window_started_at_ms
        """
    )

    def __init__(self, engine: Engine):
        self.engine = engine

    def _database_now_ms(self, connection) -> int:
        if self.engine.dialect.name == "postgresql":
            value = connection.execute(
                text("SELECT CAST(EXTRACT(EPOCH FROM clock_timestamp()) * 1000 AS BIGINT)")
            ).scalar_one()
            return int(value)
        return int(time.time() * 1000)

    def consume(
        self,
        key: str,
        max_requests: int,
        window_s: int,
        *,
        now_ms: int | None = None,
    ) -> int | None:
        window_ms = max(1, int(window_s)) * 1000
        max_requests = max(1, int(max_requests))
        with self.engine.begin() as connection:
            current_ms = int(now_ms) if now_ms is not None else self._database_now_ms(connection)
            row = connection.execute(
                self._UPSERT,
                {
                    "bucket_key": key,
                    "now_ms": current_ms,
                    "window_ms": window_ms,
                    "blocked_count": max_requests + 1,
                },
            ).mappings().one()

        count = int(row["request_count"])
        if count <= max_requests:
            return None

        started_ms = int(row["window_started_at_ms"])
        remaining_ms = max(1, started_ms + window_ms - current_ms)
        return max(1, int(math.ceil(remaining_ms / 1000)))


_database_store = DatabaseRateLimitStore(_engine)


def _rate_limit_backend_unavailable(scope: str) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "detail": "Rate limit protection unavailable",
            "reason": "rate_limit_backend_unavailable",
            "code": "rate_limit_backend_unavailable",
            "scope": scope,
        },
        headers={"Retry-After": "5"},
    )


def enforce_rate_limit(scope: str, actor_key: str) -> None:
    max_requests, window_s = _scope_limit(scope)
    with _lock:
        _metrics["requests_total"] += 1

    try:
        backend = _backend_name()
        if backend == "memory":
            retry_after_seconds = _memory_consume(
                f"{scope}:{actor_key}",
                max_requests,
                window_s,
            )
        else:
            retry_after_seconds = _database_store.consume(
                _distributed_key(scope, actor_key),
                max_requests,
                window_s,
            )
    except (RateLimitBackendUnavailable, SQLAlchemyError, OSError) as exc:
        logging.exception("rate_limit.backend_unavailable scope=%s backend=%s", scope, os.getenv("TORE_RATE_LIMIT_BACKEND", "auto"))
        with _lock:
            _metrics["backend_errors_total"] += 1
        raise _rate_limit_backend_unavailable(scope) from exc

    if retry_after_seconds is not None:
        with _lock:
            _metrics["rate_limited_total"] += 1
        raise RateLimitExceeded(scope=scope, retry_after_seconds=retry_after_seconds)


def standard_rate_limit_http_exception(scope: str, retry_after_seconds: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={
            "detail": "Too many requests",
            "reason": "rate_limited",
            "code": "rate_limited",
            "retry_after_seconds": int(retry_after_seconds),
            "scope": scope,
        },
        headers={"Retry-After": str(int(retry_after_seconds))},
    )


def email_otp_rate_limit_http_exception(retry_after_seconds: int) -> HTTPException:
    retry_after = int(retry_after_seconds)
    return HTTPException(
        status_code=429,
        detail={
            "code": "rate_limited",
            "retry_after_seconds": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


def record_status_code(code: int) -> None:
    with _lock:
        if 400 <= code < 500:
            _metrics["http_4xx_total"] += 1
        elif code >= 500:
            _metrics["http_5xx_total"] += 1


def metrics_lite() -> dict:
    try:
        backend = _backend_name()
    except RateLimitBackendUnavailable:
        backend = "unavailable"
    with _lock:
        return {
            "window_seconds": _RATE_LIMIT_WINDOW_S,
            "rate_limit_max": _RATE_LIMIT_MAX,
            "backend": backend,
            "requests_total": int(_metrics["requests_total"]),
            "rate_limited_total": int(_metrics["rate_limited_total"]),
            "backend_errors_total": int(_metrics["backend_errors_total"]),
            "http_4xx_total": int(_metrics["http_4xx_total"]),
            "http_5xx_total": int(_metrics["http_5xx_total"]),
        }
