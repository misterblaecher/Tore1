from __future__ import annotations

from typing import Optional

from fastapi import HTTPException


def ensure_idempotency_key(idempotency_key: Optional[str]) -> str:
    key = (idempotency_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail={"reason": "IDEMPOTENCY_REQUIRED", "message": "Idempotency-Key required"})
    return key
