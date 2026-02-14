from __future__ import annotations

import hashlib
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import EntryScanLog, Event
from app.services.qr_service import resolve_qr_payload


def require_partner_staff(identity: dict) -> None:
    if identity.get("role") not in {"manager", "bartender"}:
        raise HTTPException(status_code=403, detail="Forbidden")


def require_partner_manager(identity: dict) -> None:
    if identity.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")


def get_owned_event_or_403(db: Session, event_id: int, bar_id: int) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.bar_id != bar_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return event


def _payload_hash(raw_payload: str) -> str:
    return hashlib.sha256(raw_payload.strip().encode("utf-8")).hexdigest()


def _decide_scan(event_id: int, raw_payload: str) -> tuple[str, str, Optional[str]]:
    trimmed = raw_payload.strip()
    user_id = None
    if trimmed.startswith("user:"):
        user_id = trimmed.split(":", 1)[1].strip() or None
        return "ALLOW", "manual_user", user_id

    resolved = resolve_qr_payload(trimmed)
    if not resolved.get("valid"):
        return "DENY", "invalid_payload", None

    qr_type = resolved.get("type")
    if qr_type != "entry":
        return "DENY", f"unsupported_type:{qr_type}", None

    qr_event_id = resolved.get("event_id")
    if qr_event_id != event_id:
        return "DENY", "wrong_event", None

    return "ALLOW", "entry_qr", None


def scan_entry(
    db: Session,
    *,
    event_id: int,
    raw_payload: str,
    scan_id: Optional[str],
    actor_user_id: int,
) -> tuple[EntryScanLog, bool]:
    payload_hash = _payload_hash(raw_payload)

    if scan_id:
        existing = (
            db.query(EntryScanLog)
            .filter(EntryScanLog.event_id == event_id, EntryScanLog.scan_id == scan_id)
            .first()
        )
        if existing:
            return existing, True

    existing = (
        db.query(EntryScanLog)
        .filter(EntryScanLog.event_id == event_id, EntryScanLog.payload_hash == payload_hash)
        .first()
    )
    if existing:
        return existing, True

    decision, reason, user_id = _decide_scan(event_id, raw_payload)
    log = EntryScanLog(
        event_id=event_id,
        scan_id=scan_id,
        payload_raw=raw_payload.strip(),
        payload_hash=payload_hash,
        user_id=user_id,
        decision=decision,
        reason=reason,
        created_by_user_id=actor_user_id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log, False
