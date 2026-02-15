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
    return (os.getenv("GIFT_QR_SECRET") or os.getenv("TORE_SECRET") or "dev-gift-qr-secret").encode("utf-8")


def issue_receive_gift_token(user_id: str, event_id: int | None = None, ttl_seconds: int = 300) -> dict[str, Any]:
    exp = datetime.utcnow() + timedelta(seconds=max(30, min(ttl_seconds, 900)))
    payload = {
        "uid": str(user_id),
        "eid": int(event_id) if event_id is not None else None,
        "exp": int(exp.timestamp()),
        "nonce": secrets.token_urlsafe(8),
    }
    payload_raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_raw).decode("utf-8").rstrip("=")
    sig = hmac.new(_secret(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"token": f"{payload_b64}.{sig}", "expires_at": exp}


def decode_receive_gift_token(token: str) -> dict[str, Any]:
    raw = (token or "").strip()
    if "." not in raw:
        raise HTTPException(400, detail={"reason": "invalid_qr", "message": "Invalid receive QR"})
    payload_b64, sig = raw.split(".", 1)
    expected = hmac.new(_secret(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(400, detail={"reason": "invalid_qr", "message": "Invalid receive QR"})
    padding = "=" * ((4 - (len(payload_b64) % 4)) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(400, detail={"reason": "invalid_qr", "message": "Invalid receive QR"}) from exc

    exp = int(payload.get("exp") or 0)
    if exp <= int(datetime.utcnow().timestamp()):
        raise HTTPException(410, detail={"reason": "expired_qr", "message": "Receive QR expired"})
    uid = str(payload.get("uid") or "")
    if not uid:
        raise HTTPException(400, detail={"reason": "invalid_qr", "message": "Invalid receive QR"})
    return payload
