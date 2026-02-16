from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

from db import now_utc
from models import Event, EventModuleConfig, EventQrToken, EventWifiSettings, EventWifiToken
from app.services.qr_signing_service import sign_payload

QR_TYPES = {
    "JOIN_EVENT": "join_event",
    "ENTRY_STAFF": "entry_staff",
    "BAR_STAFF": "bar_staff",
    "MENU": "menu",
}


def _iso_z(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat() + "Z"


def _build_payload(qr_type: str, event_id: int, issued_at_iso: str, expires_at_iso: str, token_id: str, nonce: str, signature: str, role: str | None = None) -> str:
    params = {
        "event_id": event_id,
        "issued_at": issued_at_iso,
        "expires_at": expires_at_iso,
        "token_id": token_id,
        "nonce": nonce,
        "sig": signature,
    }
    if role:
        params["role"] = role.lower()
    return f"tore://{qr_type}?{urlencode(params)}"


def create_staff_qr_token(
    db,
    *,
    event: Event,
    staff_role: str,
    created_by_user_id: int,
    assignment_id: int | None,
    expires_at: datetime,
    qr_type: str | None = None,
) -> dict:
    role = (staff_role or "").upper()
    qr_payload_type = qr_type or {
        "ENTRY": "entry_staff",
        "BAR": "bar_staff",
        "MANAGER": "bar_staff",
    }.get(role, "staff")
    issued_at = now_utc()
    issued_at_iso = _iso_z(issued_at)
    expires_at_iso = _iso_z(expires_at)
    token_id = secrets.token_urlsafe(16)
    nonce = secrets.token_urlsafe(12)
    signature = sign_payload(qr_payload_type, event.id, issued_at_iso, expires_at_iso, token_id, nonce)
    payload = _build_payload(qr_payload_type, event.id, issued_at_iso, expires_at_iso, token_id, nonce, signature, role=role)

    qr_type_label = {
        "ENTRY": "ENTRY_STAFF",
        "BAR": "BAR_STAFF",
        "MANAGER": "MANAGER",
    }.get(role, role)

    row = EventQrToken(
        event_id=event.id,
        qr_type=qr_type_label,
        role=role,
        assignment_id=assignment_id,
        token_id=token_id,
        nonce=nonce,
        payload=payload,
        signature=signature,
        issued_at=issued_at,
        expires_at=expires_at,
        created_by_user_id=created_by_user_id,
    )
    db.add(row)

    return {
        "type": qr_type_label,
        "payload": payload,
        "expiresAt": expires_at_iso,
        "tokenId": token_id,
        "signature": signature,
        "role": role,
    }


def _wifi_enabled(db, event_id: int) -> bool:
    cfg = db.query(EventModuleConfig).filter(EventModuleConfig.event_id == event_id).first()
    if not cfg or not cfg.wifi_enabled:
        return False
    settings = db.query(EventWifiSettings).filter(EventWifiSettings.event_id == event_id).first()
    return bool(settings and settings.enabled and settings.ssid and settings.password)


def create_wifi_token_qr(db, *, event: Event, created_by_user_id: int | None, ttl_seconds: int = 21600) -> dict:
    issued_at = now_utc()
    expires_at = issued_at + timedelta(seconds=max(300, min(86400, ttl_seconds)))
    issued_at_iso = _iso_z(issued_at)
    expires_at_iso = _iso_z(expires_at)
    token_id = secrets.token_urlsafe(12)
    token = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(12)
    signature = sign_payload("wifi_token", event.id, issued_at_iso, expires_at_iso, token_id, nonce)

    payload = f"tore://qr?{urlencode({'type': 'wifi_token', 'event_id': event.id, 'token_id': token_id, 'token': token, 'issued_at': issued_at_iso, 'expires_at': expires_at_iso, 'nonce': nonce, 'sig': signature})}"

    db.add(EventWifiToken(event_id=event.id, token_id=token_id, token_hash=hashlib.sha256(token.encode('utf-8')).hexdigest(), created_at=issued_at, expires_at=expires_at))

    return {
        "type": "WIFI_TOKEN",
        "payload": payload,
        "expiresAt": expires_at_iso,
        "tokenId": token_id,
        "signature": signature,
    }


def generate_qr_pack(db, *, event: Event, actor_user_id: int | None = None) -> list[dict]:
    issued_at = now_utc()
    expires_at = (event.ends_at or issued_at) + timedelta(hours=6)
    issued_at_iso = _iso_z(issued_at)
    expires_at_iso = _iso_z(expires_at)

    items: list[dict] = []
    for label, qr_type in QR_TYPES.items():
        token_id = secrets.token_urlsafe(16)
        nonce = secrets.token_urlsafe(12)
        signature = sign_payload(qr_type, event.id, issued_at_iso, expires_at_iso, token_id, nonce)
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

    if _wifi_enabled(db, event.id):
        items.append(create_wifi_token_qr(db, event=event, created_by_user_id=actor_user_id, ttl_seconds=21600))
    return items
