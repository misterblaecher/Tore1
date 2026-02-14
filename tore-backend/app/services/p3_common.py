from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import now_utc
from models import Event, EventModuleConfig


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


def ensure_event_module_enabled(db: Session, event_id: int, field: str) -> None:
    cfg = db.query(EventModuleConfig).filter(EventModuleConfig.event_id == event_id).first()
    if cfg is None:
        return
    if getattr(cfg, field, False) is not True:
        raise HTTPException(status_code=409, detail="module disabled")
