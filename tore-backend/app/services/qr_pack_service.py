from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from db import now_utc
from models import Event, EventQrToken

QR_SIGNING_SECRET = os.getenv("TORE_QR_SIGNING_SECRET", os.getenv("TORE_JWT_SECRET", "dev-secret-change-me"))

QR_TYPES = {
    "JOIN_EVENT": "join_event",
    "ENTRY_STAFF": "entry_staff",
    "BAR_STAFF": "bar_staff",
    "MENU": "menu",
}


def _build_payload(qr_type: str, event_id: int, issued_at_iso: str, expires_at_iso: str, token_id: str, nonce: str, signature: str) -> str:
    params = {
        "event_id": event_id,
        "issued_at": issued_at_iso,
        "expires_at": expires_at_iso,
        "token_id": token_id,
        "nonce": nonce,
        "sig": signature,
    }
    return f"tore://{qr_type}?{urlencode(params)}"


def _sign_payload(qr_type: str, event_id: int, issued_at_iso: str, expires_at_iso: str, token_id: str, nonce: str) -> str:
    payload = f"{qr_type}|{event_id}|{issued_at_iso}|{expires_at_iso}|{token_id}|{nonce}"
    return hmac.new(QR_SIGNING_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_qr_pack(db, *, event: Event, actor_user_id: int | None = None) -> list[dict]:
    issued_at = now_utc()
    expires_at = (event.ends_at or issued_at) + timedelta(hours=6)
    issued_at_iso = issued_at.replace(microsecond=0).isoformat() + "Z"
    expires_at_iso = expires_at.replace(microsecond=0).isoformat() + "Z"

    items: list[dict] = []
    for label, qr_type in QR_TYPES.items():
        token_id = secrets.token_urlsafe(16)
        nonce = secrets.token_urlsafe(12)
        signature = _sign_payload(qr_type, event.id, issued_at_iso, expires_at_iso, token_id, nonce)
        payload = _build_payload(qr_type, event.id, issued_at_iso, expires_at_iso, token_id, nonce, signature)

        row = EventQrToken(
            event_id=event.id,
            qr_type=label,
            token_id=token_id,
            nonce=nonce,
            payload=payload,
            signature=signature,
            issued_at=issued_at,
            expires_at=expires_at,
            created_by_user_id=actor_user_id,
        )
        db.add(row)

        items.append(
            {
                "type": label,
                "payload": payload,
                "expiresAt": expires_at_iso,
                "tokenId": token_id,
                "signature": signature,
            }
        )
    return items
