from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from sqlalchemy.orm import Session

from app.services.qr_signing_service import verify_payload_signature
from models import EventQrToken, EventWifiToken

SENSITIVE_QR_TYPES = {
    "join",
    "join_event",
    "entry_staff",
    "staff_entry",
    "staff",
    "bar_staff",
    "menu",
    "gift_receive",
    "wifi_token",
}


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def validate_signed_qr(raw: str, *, qr_type: str, event_id: int | None, db: Session) -> tuple[bool, str | None, str | None, datetime | None]:
    normalized_qr_type = "entry_staff" if qr_type == "staff_entry" else qr_type
    if normalized_qr_type not in SENSITIVE_QR_TYPES:
        return True, None, None, None
    if normalized_qr_type == "menu" and event_id is None:
        return True, None, None, None

    parsed = urlparse(raw.strip())
    params = parse_qs(parsed.query)
    token_id = (params.get("token_id") or [None])[0]
    issued_at = (params.get("issued_at") or [None])[0]
    expires_at = (params.get("expires_at") or [None])[0]
    nonce = (params.get("nonce") or [None])[0]
    signature = (params.get("sig") or [None])[0]
    raw_token = (params.get("token") or [None])[0]

    # Explicit legacy escape hatch for historical static QR payloads.
    legacy_allowed = ((params.get("legacy") or [""])[0] == "1")
    if legacy_allowed and not signature:
        return True, None, None, None

    if not token_id or not issued_at or not expires_at or not nonce or not signature or event_id is None:
        return False, "invalid", token_id, None

    if not verify_payload_signature(
        signature,
        qr_type=normalized_qr_type,
        event_id=event_id,
        issued_at_iso=issued_at,
        expires_at_iso=expires_at,
        token_id=token_id,
        nonce=nonce,
    ):
        return False, "invalid", token_id, None

    expires_at_dt = _parse_iso(expires_at)
    if expires_at_dt is None:
        return False, "invalid", token_id, None
    if expires_at_dt <= datetime.now(timezone.utc):
        return False, "expired", token_id, expires_at_dt

    if normalized_qr_type == "wifi_token":
        wifi_token = db.query(EventWifiToken).filter(EventWifiToken.token_id == token_id).first()
        if not wifi_token or wifi_token.event_id != event_id or not raw_token:
            return False, "invalid", token_id, expires_at_dt
        if wifi_token.token_hash != hashlib.sha256(raw_token.encode("utf-8")).hexdigest():
            return False, "invalid", token_id, wifi_token.expires_at
        if wifi_token.revoked_at is not None:
            return False, "revoked", token_id, wifi_token.expires_at
        if wifi_token.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
            return False, "expired", token_id, wifi_token.expires_at
        return True, None, token_id, wifi_token.expires_at

    token_row = db.query(EventQrToken).filter(EventQrToken.token_id == token_id).first()
    if not token_row or token_row.event_id != event_id:
        return False, "invalid", token_id, expires_at_dt
    if token_row.revoked_at is not None:
        return False, "revoked", token_id, token_row.expires_at
    if token_row.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
        return False, "expired", token_id, token_row.expires_at
    return True, None, token_id, token_row.expires_at
