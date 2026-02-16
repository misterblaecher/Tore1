from __future__ import annotations

import hashlib
import hmac
import os


def _secrets() -> list[str]:
    ring = (os.getenv("TORE_QR_SIGNING_KEYS") or "").strip()
    if ring:
        values = [item.strip() for item in ring.split(",") if item.strip()]
        if values:
            return values
    single = (os.getenv("TORE_QR_SIGNING_SECRET") or os.getenv("TORE_JWT_SECRET") or "dev-secret-change-me").strip()
    return [single]


def sign_payload(qr_type: str, event_id: int, issued_at_iso: str, expires_at_iso: str, token_id: str, nonce: str) -> str:
    payload = f"{qr_type}|{event_id}|{issued_at_iso}|{expires_at_iso}|{token_id}|{nonce}"
    key = _secrets()[0]
    return hmac.new(key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_payload_signature(signature: str, *, qr_type: str, event_id: int, issued_at_iso: str, expires_at_iso: str, token_id: str, nonce: str) -> bool:
    if not signature:
        return False
    payload = f"{qr_type}|{event_id}|{issued_at_iso}|{expires_at_iso}|{token_id}|{nonce}"
    for secret in _secrets():
        expected = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, signature):
            return True
    return False
