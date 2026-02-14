from __future__ import annotations

from sqlalchemy.orm import Session

from db import now_utc
from models import EventModuleConfig


def get_or_create_event_modules(db: Session, event_id: int) -> EventModuleConfig:
    cfg = db.query(EventModuleConfig).filter(EventModuleConfig.event_id == event_id).first()
    if cfg:
        return cfg
    cfg = EventModuleConfig(event_id=event_id)
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def update_event_modules(db: Session, cfg: EventModuleConfig, payload: dict, actor_user_id: int) -> EventModuleConfig:
    changed = False
    for field in [
        "orders_enabled",
        "market_enabled",
        "battles_enabled",
        "hunt_enabled",
        "polymarket_enabled",
        "entry_enabled",
    ]:
        value = payload.get(field)
        if value is None:
            continue
        if getattr(cfg, field) != value:
            setattr(cfg, field, value)
            changed = True
    if changed:
        cfg.updated_at = now_utc()
        cfg.updated_by_user_id = actor_user_id
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg
