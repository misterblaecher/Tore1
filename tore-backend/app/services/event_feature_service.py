"""Event feature/config helpers independent from the legacy runtime."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import now_utc
from models import EventConfig


def default_event_config_payload() -> dict[str, Any]:
    return {
        "menu_enabled": True,
        "wallet_enabled": True,
        "entry_enabled": False,
        "checkin_enabled": False,
        "battles_enabled": False,
        "hunt_enabled": False,
        "report_enabled": True,
        "allow_user_bets": False,
    }


def get_or_create_event_config(
    db: Session,
    event_id: int,
    commit: bool = False,
) -> EventConfig:
    cfg = db.query(EventConfig).filter(EventConfig.event_id == event_id).first()
    if cfg:
        return cfg
    cfg = EventConfig(
        event_id=event_id,
        **default_event_config_payload(),
        updated_at=now_utc(),
    )
    db.add(cfg)
    db.flush()
    if commit:
        db.commit()
    return cfg


def require_feature(db: Session, event_id: int, feature: str) -> EventConfig:
    cfg = get_or_create_event_config(db, event_id, commit=True)
    if getattr(cfg, feature, None) is not True:
        raise HTTPException(
            status_code=403,
            detail={"error": "feature_disabled", "feature": feature},
        )
    return cfg


__all__ = [
    "default_event_config_payload",
    "get_or_create_event_config",
    "require_feature",
]
