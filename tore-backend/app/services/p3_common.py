from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import now_utc
from models import Event, EventConfig, EventModuleConfig, EventRuntimeState


def decode_cursor(raw: Optional[str]) -> tuple[Optional[datetime], Optional[int]]:
    if not raw:
        return None, None
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw.encode("utf-8")).decode("utf-8"))
        return datetime.fromisoformat(payload["ts"]), int(payload["id"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


def encode_cursor(ts: datetime, row_id: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"ts": ts.isoformat(), "id": row_id}).encode("utf-8")).decode("utf-8")


def is_event_live(db: Session, event_id: int) -> bool:
    event = db.get(Event, event_id)
    if not event:
        return False
    now = now_utc()
    return event.starts_at <= now <= event.ends_at


def get_event_runtime_state(db: Session, event_id: int) -> str:
    event = db.get(Event, event_id)
    if not event:
        return "UNKNOWN"
    now = now_utc()
    if event.ends_at and now >= event.ends_at:
        return "CLOSED"
    if event.starts_at and now < event.starts_at:
        return "SCHEDULED"
    runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).first()
    return (runtime.state if runtime else "LIVE") or "LIVE"


def effective_module_state(db: Session, event_id: int, module_field: Optional[str]) -> tuple[str, str]:
    event_state = get_event_runtime_state(db, event_id)
    if event_state == "CLOSED":
        return "OFF", "event_closed"
    if event_state == "PAUSE":
        return "READ_ONLY", "event_paused"
    if event_state == "MENU_ONLY":
        if module_field == "orders_enabled":
            return "ON", "menu_only_orders_allowed"
        return "OFF", "menu_only_restriction"

    if module_field is None:
        return "ON", "live"

    if module_field == "wallet_enabled":
        cfg = db.query(EventConfig).filter(EventConfig.event_id == event_id).first()
        enabled = True if cfg is None else bool(cfg.wallet_enabled)
    else:
        cfg = db.query(EventModuleConfig).filter(EventModuleConfig.event_id == event_id).first()
        enabled = True if cfg is None else bool(getattr(cfg, module_field, False))
    if not enabled:
        return "OFF", "module_off"
    return "ON", "live"


def ensure_event_action_allowed(db: Session, event_id: int, module_field: Optional[str], write: bool = True) -> None:
    state, reason = effective_module_state(db, event_id, module_field)
    if state == "ON":
        return
    if state == "READ_ONLY" and not write:
        return
    code_map = {
        "event_closed": "EVENT_CLOSED",
        "event_paused": "EVENT_PAUSED",
        "menu_only_restriction": "EVENT_MENU_ONLY",
        "module_off": "MODULE_OFF",
    }
    msg_map = {
        "event_closed": "Event is closed",
        "event_paused": "Event is paused",
        "menu_only_restriction": "Event is in menu-only mode",
        "module_off": "Module is disabled",
    }
    status = 409 if reason == "module_off" else 423
    raise HTTPException(
        status_code=status,
        detail={
            "code": code_map.get(reason, "ACTION_BLOCKED"),
            "message": msg_map.get(reason, "Action blocked"),
            "reason": reason,
        },
    )


def ensure_event_module_enabled(db: Session, event_id: int, field: str) -> None:
    # Backward-compatible alias for existing call sites.
    ensure_event_action_allowed(db, event_id, field, write=True)
