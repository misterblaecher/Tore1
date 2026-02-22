from __future__ import annotations

import os
import threading
import time
import math
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException


class RateLimitExceeded(Exception):
    def __init__(self, scope: str, retry_after_seconds: int):
        self.scope = scope
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit exceeded for scope={scope} retry_after={retry_after_seconds}s")

_RATE_LIMIT_MAX = int(os.getenv("TORE_RATE_LIMIT_MAX", "25"))
_RATE_LIMIT_WINDOW_S = int(os.getenv("TORE_RATE_LIMIT_WINDOW_S", "5"))
_SCOPE_LIMITS: dict[str, tuple[int, int]] = {
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
        int(os.getenv("TORE_AUTH_EMAIL_OTP_PER_EMAIL_MAX", "4")),
        int(os.getenv("TORE_AUTH_EMAIL_OTP_PER_EMAIL_WINDOW_S", "600")),
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

_lock = threading.Lock()
_store: dict[str, Deque[float]] = defaultdict(deque)
_metrics = {
    "requests_total": 0,
    "rate_limited_total": 0,
    "http_4xx_total": 0,
    "http_5xx_total": 0,
}


def _prune(q: Deque[float], now: float, window_s: int) -> None:
    threshold = now - window_s
    while q and q[0] < threshold:
        q.popleft()


def enforce_rate_limit(scope: str, actor_key: str) -> None:
    key = f"{scope}:{actor_key}"
    now = time.monotonic()
    max_requests, window_s = _SCOPE_LIMITS.get(scope, (_RATE_LIMIT_MAX, _RATE_LIMIT_WINDOW_S))
    with _lock:
        _metrics["requests_total"] += 1
        q = _store[key]
        _prune(q, now, window_s)
        if len(q) >= max_requests:
            _metrics["rate_limited_total"] += 1
            retry_after_seconds = max(1, int(math.ceil(window_s - (now - q[0])))) if q else window_s
            raise RateLimitExceeded(scope=scope, retry_after_seconds=retry_after_seconds)
        q.append(now)


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


def record_status_code(code: int) -> None:
    with _lock:
        if 400 <= code < 500:
            _metrics["http_4xx_total"] += 1
        elif code >= 500:
            _metrics["http_5xx_total"] += 1


def metrics_lite() -> dict:
    with _lock:
        return {
            "window_seconds": _RATE_LIMIT_WINDOW_S,
            "rate_limit_max": _RATE_LIMIT_MAX,
            "requests_total": int(_metrics["requests_total"]),
            "rate_limited_total": int(_metrics["rate_limited_total"]),
            "http_4xx_total": int(_metrics["http_4xx_total"]),
            "http_5xx_total": int(_metrics["http_5xx_total"]),
        }
