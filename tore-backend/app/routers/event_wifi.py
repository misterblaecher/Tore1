from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from db import now_utc
from models import (
    Event,
    EventModuleConfig,
    EventWifiIdempotency,
    EventWifiSettings,
    EventWifiToken,
)
from partner_auth import current_identity
from app.services.authz_service import ensure_partner_role
from app.services.audit_service import write_audit_log
from app.services.p3_common import effective_module_state
from app.services.qr_signing_service import sign_payload
from app.services.rate_limit_service import enforce_rate_limit

router = APIRouter(tags=["event-wifi"])


def get_db():
    from main import get_db as _get_db

    yield from _get_db()


def _require_orga_manager_identity(identity=Depends(current_identity)):
    ensure_partner_role(identity, {"manager", "owner"})
    return identity


def _event_for_identity(db: Session, event_id: int, identity: dict) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail={"reason": "event_not_found"})
    if event.bar_id != identity.get("bar_id"):
        raise HTTPException(status_code=403, detail={"reason": "forbidden"})
    return event


def _get_or_create_wifi_settings(db: Session, event_id: int) -> EventWifiSettings:
    row = db.query(EventWifiSettings).filter(EventWifiSettings.event_id == event_id).first()
    if row:
        return row
    row = EventWifiSettings(event_id=event_id, enabled=False, ssid="", password="")
    db.add(row)
    db.flush()
    return row


def _module_enabled(db: Session, event_id: int) -> bool:
    cfg = db.query(EventModuleConfig).filter(EventModuleConfig.event_id == event_id).first()
    return bool(cfg and cfg.wifi_enabled)


def _token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _token_status(row: EventWifiToken) -> str:
    now = now_utc()
    if row.revoked_at is not None:
        return "revoked"
    if row.expires_at <= now:
        return "expired"
    return "active"


def _wifi_stats(db: Session, event_id: int) -> dict:
    rows = db.query(EventWifiToken).filter(EventWifiToken.event_id == event_id).all()
    counts = {"active": 0, "revoked": 0, "expired": 0}
    for row in rows:
        counts[_token_status(row)] += 1
    return counts


def _require_idempotency(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency-Key required"})
    key = idempotency_key.strip()
    if len(key) < 4:
        raise HTTPException(status_code=400, detail={"reason": "invalid_idempotency"})
    return key


def _iso_z(value: datetime) -> str:
    normalized = value.replace(microsecond=0)
    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=timezone.utc)
    else:
        normalized = normalized.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


def _build_wifi_qr_payload(*, event_id: int, token_id: str, token: str, issued_at: datetime, expires_at: datetime) -> tuple[str, str]:
    qr_type = "wifi_token"
    issued_at_iso = _iso_z(issued_at)
    expires_at_iso = _iso_z(expires_at)
    nonce = secrets.token_urlsafe(12)
    signature = sign_payload(qr_type, event_id, issued_at_iso, expires_at_iso, token_id, nonce)
    params = {
        "type": qr_type,
        "event_id": event_id,
        "token_id": token_id,
        "token": token,
        "issued_at": issued_at_iso,
        "expires_at": expires_at_iso,
        "nonce": nonce,
        "sig": signature,
    }
    return f"tore://qr?{urlencode(params)}", signature


@router.get("/partner/portal/orga/events/{event_id}/wifi")
def orga_get_event_wifi(
    event_id: int,
    identity=Depends(_require_orga_manager_identity),
    db: Session = Depends(get_db),
):
    _event_for_identity(db, event_id, identity)
    settings = _get_or_create_wifi_settings(db, event_id)
    token_rows = (
        db.query(EventWifiToken)
        .filter(EventWifiToken.event_id == event_id)
        .order_by(EventWifiToken.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "enabled": bool(settings.enabled),
        "ssid": settings.ssid or "",
        "hasPassword": bool(settings.password),
        "instructions": settings.instructions,
        "tokenStats": _wifi_stats(db, event_id),
        "tokens": [
            {
                "id": row.id,
                "tokenId": row.token_id,
                "createdAt": row.created_at,
                "expiresAt": row.expires_at,
                "revokedAt": row.revoked_at.isoformat() if row.revoked_at else None,
                "revokeReason": row.revoke_reason,
                "status": _token_status(row),
                "issuedToUserId": row.issued_to_user_id,
            }
            for row in token_rows
        ],
    }


@router.put("/partner/portal/orga/events/{event_id}/wifi")
def orga_put_event_wifi(
    event_id: int,
    payload: dict,
    identity=Depends(_require_orga_manager_identity),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = _require_idempotency(idempotency_key)
    _event_for_identity(db, event_id, identity)

    existing = (
        db.query(EventWifiIdempotency)
        .filter(
            EventWifiIdempotency.event_id == event_id,
            EventWifiIdempotency.action == "wifi_put",
            EventWifiIdempotency.idempotency_key == key,
        )
        .first()
    )
    if existing:
        return existing.response_json

    settings = _get_or_create_wifi_settings(db, event_id)
    settings.enabled = bool(payload.get("enabled", settings.enabled))
    if "ssid" in payload and payload.get("ssid") is not None:
        settings.ssid = str(payload.get("ssid") or "")
    if "password" in payload and payload.get("password") is not None:
        settings.password = str(payload.get("password") or "")
    if "instructions" in payload:
        settings.instructions = payload.get("instructions")
    settings.updated_at = now_utc()
    settings.updated_by = identity.get("user_id")
    db.add(settings)

    response = {
        "enabled": bool(settings.enabled),
        "ssid": settings.ssid or "",
        "hasPassword": bool(settings.password),
        "instructions": settings.instructions,
        "tokenStats": _wifi_stats(db, event_id),
    }
    db.add(EventWifiIdempotency(event_id=event_id, action="wifi_put", idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=identity.get("user_id"),
        actor_role=identity.get("role"),
        action="orga.wifi.settings.update",
        entity_type="event_wifi_settings",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=identity.get("bar_id"),
        payload={"enabled": settings.enabled, "ssid": settings.ssid, "has_password": bool(settings.password), "instructions": settings.instructions},
    )
    db.commit()
    return response


@router.post("/partner/portal/orga/events/{event_id}/wifi/tokens")
def orga_create_wifi_token(
    event_id: int,
    payload: dict,
    identity=Depends(_require_orga_manager_identity),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = _require_idempotency(idempotency_key)
    _event_for_identity(db, event_id, identity)

    existing = (
        db.query(EventWifiIdempotency)
        .filter(
            EventWifiIdempotency.event_id == event_id,
            EventWifiIdempotency.action == "wifi_token_create",
            EventWifiIdempotency.idempotency_key == key,
        )
        .first()
    )
    if existing:
        return existing.response_json

    state, reason = effective_module_state(db, event_id, "wifi_enabled")
    if state == "OFF":
        raise HTTPException(status_code=404, detail={"reason": reason or "module_off"})
    if state == "READ_ONLY":
        raise HTTPException(status_code=409, detail={"reason": reason or "read_only"})

    ttl = int(payload.get("ttlSeconds") or 3600)
    ttl = max(300, min(86400, ttl))

    settings = _get_or_create_wifi_settings(db, event_id)
    if not settings.enabled:
        raise HTTPException(status_code=404, detail={"reason": "module_off"})

    token_raw = secrets.token_urlsafe(24)
    token_id = secrets.token_urlsafe(12)
    created_at = now_utc()
    expires_at = created_at + timedelta(seconds=ttl)

    token_row = EventWifiToken(
        event_id=event_id,
        token_id=token_id,
        token_hash=_token_hash(token_raw),
        created_at=created_at,
        expires_at=expires_at,
        issued_to_user_id=payload.get("issuedToUserId"),
    )
    db.add(token_row)
    db.flush()

    qr_payload, _signature = _build_wifi_qr_payload(event_id=event_id, token_id=token_id, token=token_raw, issued_at=created_at, expires_at=expires_at)
    response = {
        "tokenId": token_id,
        "token": token_raw,
        "expiresAt": expires_at.isoformat(),
        "qr": {
            "type": "WIFI_TOKEN",
            "raw": qr_payload,
        },
    }
    db.add(EventWifiIdempotency(event_id=event_id, action="wifi_token_create", idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=identity.get("user_id"),
        actor_role=identity.get("role"),
        action="orga.wifi.token.create",
        entity_type="event_wifi_token",
        entity_id=str(token_row.id),
        event_id=event_id,
        bar_id=identity.get("bar_id"),
        payload={"token_id": token_id, "expires_at": expires_at.isoformat()},
    )
    db.commit()
    return response


@router.post("/partner/portal/orga/events/{event_id}/wifi/tokens/{token_id}/revoke")
def orga_revoke_wifi_token(
    event_id: int,
    token_id: str,
    payload: dict,
    identity=Depends(_require_orga_manager_identity),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = _require_idempotency(idempotency_key)
    _event_for_identity(db, event_id, identity)

    existing = (
        db.query(EventWifiIdempotency)
        .filter(
            EventWifiIdempotency.event_id == event_id,
            EventWifiIdempotency.action == f"wifi_token_revoke:{token_id}",
            EventWifiIdempotency.idempotency_key == key,
        )
        .first()
    )
    if existing:
        return existing.response_json

    row = db.query(EventWifiToken).filter(EventWifiToken.event_id == event_id, EventWifiToken.token_id == token_id).first()
    if not row and token_id.isdigit():
        row = db.query(EventWifiToken).filter(EventWifiToken.event_id == event_id, EventWifiToken.id == int(token_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail={"reason": "token_not_found"})
    if row.revoked_at is None:
        row.revoked_at = now_utc()
        row.revoked_by = identity.get("user_id")
        row.revoke_reason = payload.get("reason")
        db.add(row)

    response = {
        "tokenId": token_id,
        "revokedAt": row.revoked_at.isoformat() if row.revoked_at else None,
        "status": _token_status(row),
    }
    db.add(EventWifiIdempotency(event_id=event_id, action=f"wifi_token_revoke:{token_id}", idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=identity.get("user_id"),
        actor_role=identity.get("role"),
        action="orga.wifi.token.revoke",
        entity_type="event_wifi_token",
        entity_id=str(row.id),
        event_id=event_id,
        bar_id=identity.get("bar_id"),
        payload={"token_id": token_id, "reason": payload.get("reason")},
    )
    db.commit()
    return response


@router.get("/events/{event_id}/wifi/claim")
def event_wifi_claim(
    event_id: int,
    token: str = Query(..., min_length=8),
    db: Session = Depends(get_db),
):
    enforce_rate_limit("wifi_claim", f"{event_id}:{hashlib.md5(token.encode('utf-8')).hexdigest()[:12]}")

    state, reason = effective_module_state(db, event_id, "wifi_enabled")
    if state == "OFF":
        raise HTTPException(status_code=404, detail={"reason": reason or "module_off"})

    settings = db.query(EventWifiSettings).filter(EventWifiSettings.event_id == event_id).first()
    if not settings or not settings.enabled:
        raise HTTPException(status_code=404, detail={"reason": "module_off"})

    row = db.query(EventWifiToken).filter(EventWifiToken.event_id == event_id, EventWifiToken.token_hash == _token_hash(token)).first()
    if not row:
        raise HTTPException(status_code=404, detail={"reason": "invalid_token"})
    if row.revoked_at is not None:
        raise HTTPException(status_code=403, detail={"reason": "revoked"})
    if row.expires_at <= now_utc():
        raise HTTPException(status_code=403, detail={"reason": "expired"})

    return {
        "ssid": settings.ssid,
        "password": settings.password,
        "instructions": settings.instructions,
        "expiresAt": row.expires_at,
    }
