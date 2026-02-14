from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException

_RATE_LIMIT_MAX = int(os.getenv("TORE_RATE_LIMIT_MAX", "25"))
_RATE_LIMIT_WINDOW_S = int(os.getenv("TORE_RATE_LIMIT_WINDOW_S", "5"))

_lock = threading.Lock()
_store: dict[str, Deque[float]] = defaultdict(deque)
_metrics = {
    "requests_total": 0,
    "rate_limited_total": 0,
    "http_4xx_total": 0,
    "http_5xx_total": 0,
}


def _prune(q: Deque[float], now: float) -> None:
    threshold = now - _RATE_LIMIT_WINDOW_S
    while q and q[0] < threshold:
        q.popleft()


def enforce_rate_limit(scope: str, actor_key: str) -> None:
    key = f"{scope}:{actor_key}"
    now = time.monotonic()
    with _lock:
        _metrics["requests_total"] += 1
        q = _store[key]
        _prune(q, now)
        if len(q) >= _RATE_LIMIT_MAX:
            _metrics["rate_limited_total"] += 1
            raise HTTPException(status_code=429, detail={"reason": "rate_limited", "message": "Too many requests"})
        q.append(now)


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
