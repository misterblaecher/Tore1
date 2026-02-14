from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException


def _secret() -> bytes:
    return (os.getenv("ORDER_QR_SECRET") or os.getenv("TORE_SECRET") or "dev-order-qr-secret").encode("utf-8")


def issue_order_client_token(order_id: int, user_id: str, ttl_seconds: int = 90) -> dict[str, Any]:
    exp = datetime.utcnow() + timedelta(seconds=max(20, min(ttl_seconds, 180)))
    payload = {
        "oid": int(order_id),
        "uid": str(user_id),
        "exp": int(exp.timestamp()),
        "nonce": secrets.token_urlsafe(8),
    }
    payload_raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_raw).decode("utf-8").rstrip("=")
    sig = hmac.new(_secret(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "token": f"{payload_b64}.{sig}",
        "expires_at": exp,
    }


def decode_order_client_token(token: str) -> dict[str, Any]:
    raw = (token or "").strip()
    if "." not in raw:
        raise HTTPException(400, "Invalid order client QR")
    payload_b64, sig = raw.split(".", 1)
    expected = hmac.new(_secret(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(400, "Invalid order client QR")
    padding = "=" * ((4 - (len(payload_b64) % 4)) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(400, "Invalid order client QR") from exc

    exp = int(payload.get("exp") or 0)
    if exp <= int(datetime.utcnow().timestamp()):
        raise HTTPException(410, "Order QR expired")
    oid = int(payload.get("oid") or 0)
    uid = str(payload.get("uid") or "")
    if oid <= 0 or not uid:
        raise HTTPException(400, "Invalid order client QR")
    return payload
