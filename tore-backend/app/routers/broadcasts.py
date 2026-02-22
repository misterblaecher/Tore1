from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import now_utc
from models import Event, EventBroadcast
from partner_auth import current_identity
from app.services.audit_service import write_audit_log
from app.services.entry_service import get_owned_event_or_403

router = APIRouter(tags=["broadcasts"])

_lock = threading.Lock()
_cooldowns: dict[str, float] = {}
_bursts: dict[str, deque[float]] = defaultdict(deque)


class BroadcastIn(BaseModel):
    message: str = Field(min_length=1, max_length=240)
    level: str = Field(default="info")
    expiresAt: Optional[datetime] = None


def get_db() -> Iterator[Session]:
    from app.legacy.monolith import get_db as _get_db

    yield from _get_db()


def _is_broadcast_enabled(event: Event) -> bool:
    return bool((event.modules_on or {}).get("broadcast"))


def _enforce_broadcast_rate_limit(*, event_id: int, author_id: int) -> None:
    now = time.monotonic()
    key = f"{event_id}:{author_id}"
    with _lock:
        cooldown_until = _cooldowns.get(key, 0.0)
        if now < cooldown_until:
            remaining = max(1, int(cooldown_until - now))
            raise HTTPException(
                status_code=429,
                detail={
                    "reason": "broadcast_cooldown",
                    "message": f"Cooldown actif ({remaining}s)",
                    "retry_after_seconds": remaining,
                },
            )

        q = _bursts[key]
        threshold = now - 120
        while q and q[0] < threshold:
            q.popleft()
        if len(q) >= 3:
            retry_after = max(1, int(120 - (now - q[0])))
            raise HTTPException(
                status_code=429,
                detail={
                    "reason": "broadcast_burst_limited",
                    "message": "Trop de broadcasts sur 2 minutes",
                    "retry_after_seconds": retry_after,
                },
            )

        q.append(now)
        _cooldowns[key] = now + 20


@router.post("/partner/portal/orga/events/{event_id}/broadcast")
def create_event_broadcast(
    event_id: int,
    payload: BroadcastIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(current_identity),
    db: Session = Depends(get_db),
):
    if identity.get("role") not in {"manager", "owner"}:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=422, detail={"reason": "idempotency_required", "message": "Idempotency-Key required"})

    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    if not _is_broadcast_enabled(event):
        raise HTTPException(status_code=409, detail={"reason": "module_off", "message": "Broadcast module disabled"})

    idem = idempotency_key.strip()[:120]
    existing = (
        db.query(EventBroadcast)
        .filter(
            EventBroadcast.event_id == event_id,
            EventBroadcast.author_id == identity["user_id"],
            EventBroadcast.idempotency_key == idem,
        )
        .first()
    )
    if existing:
        return _serialize_broadcast(existing)

    _enforce_broadcast_rate_limit(event_id=event_id, author_id=identity["user_id"])

    level = (payload.level or "info").lower().strip()
    if level not in {"info", "warn", "urgent"}:
        raise HTTPException(status_code=422, detail={"reason": "invalid_level", "message": "Invalid broadcast level"})

    row = EventBroadcast(
        event_id=event_id,
        author_id=identity["user_id"],
        message=payload.message.strip(),
        level=level,
        expires_at=payload.expiresAt,
        idempotency_key=idem,
    )
    db.add(row)
    db.flush()
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="event_broadcast.create",
        entity_type="event_broadcast",
        entity_id=str(row.id),
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"message": row.message, "level": row.level, "expires_at": row.expires_at.isoformat() if row.expires_at else None},
    )
    db.commit()
    db.refresh(row)
    return _serialize_broadcast(row)


@router.get("/events/{event_id}/broadcasts")
def list_event_broadcasts(
    event_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not _is_broadcast_enabled(event):
        return {"items": []}

    now = now_utc()
    rows = (
        db.query(EventBroadcast)
        .filter(EventBroadcast.event_id == event_id)
        .order_by(EventBroadcast.created_at.desc(), EventBroadcast.id.desc())
        .limit(limit)
        .all()
    )
    items = [
        _serialize_broadcast(row)
        for row in rows
        if row.expires_at is None or row.expires_at > now
    ]
    return {"items": items}


def _serialize_broadcast(row: EventBroadcast) -> dict:
    return {
        "id": row.id,
        "event_id": row.event_id,
        "author_id": row.author_id,
        "message": row.message,
        "level": row.level,
        "expires_at": row.expires_at,
        "created_at": row.created_at,
    }
