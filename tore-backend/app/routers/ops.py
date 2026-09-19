from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import now_utc
from models import Bar, EntryScanLog, Event, EventModuleConfig, Order
from partner_auth import current_identity
from app.services.authz_service import ensure_partner_role
from app.services.entry_service import get_owned_event_or_403
from app.services.p3_common import effective_module_state, get_event_runtime_state
from app.services.rate_limit_service import metrics_lite

router = APIRouter(tags=["ops"])


_MOBILE_MODULE_FIELDS = {
    "user_menu": "orders_enabled",
    "user_orders_lifecycle": "orders_enabled",
    "bar_orders_live": "orders_enabled",
    "orga_entry_mode": "entry_enabled",
    "user_battles": "battles_enabled",
    "orga_battle_admin": "battles_enabled",
    "user_hunts": "hunt_enabled",
    "orga_hunt_admin": "hunt_enabled",
    "user_polymarket_event": "polymarket_enabled",
    "orga_polymarket_admin": "polymarket_enabled",
    "user_wifi": "wifi_enabled",
    "user_safe_kit": "safety_enabled",
    "orga_urgency_actions": "safety_enabled",
}


from app.deps.db import get_db


def _health_payload() -> dict:
    return {"ok": True, "ts": now_utc().isoformat(), "version": "mvp-mega", "db_ok": True}


@router.get('/healthz')
def healthz():
    return _health_payload()


@router.get('/api/healthz')
def api_healthz():
    return _health_payload()


@router.get("/mobile/remote-config")
def mobile_remote_config():
    return {
        "modules_defaults": {},
        "disable_writes_global": False,
        "disable_writes_message": "Writes are temporarily frozen.",
        "min_supported_build": None,
        "min_supported_version": None,
        "diagnostics_enabled": True,
        "server_time": now_utc().isoformat(),
    }


def _select_mobile_bootstrap_event(db: Session) -> tuple[Event | None, str]:
    now = now_utc()
    active = (
        db.query(Event)
        .filter(Event.starts_at <= now, Event.ends_at >= now)
        .order_by(Event.starts_at.desc(), Event.id.desc())
        .first()
    )
    if active is not None:
        return active, "active"

    upcoming = (
        db.query(Event)
        .filter(Event.starts_at > now)
        .order_by(Event.starts_at.asc(), Event.id.asc())
        .first()
    )
    if upcoming is not None:
        return upcoming, "upcoming"

    latest = db.query(Event).order_by(Event.starts_at.desc(), Event.id.desc()).first()
    if latest is not None:
        return latest, "latest"
    return None, "empty"


@router.get("/mobile/bootstrap")
def mobile_bootstrap(db: Session = Depends(get_db)):
    now = now_utc()
    event, source = _select_mobile_bootstrap_event(db)
    if event is None:
        return {
            "barId": None,
            "bar_id": None,
            "barName": None,
            "eventId": "event_42",
            "event_id": 42,
            "eventApiId": "42",
            "eventName": None,
            "eventState": "DRAFT",
            "source": source,
            "server_time": now.isoformat(),
        }

    bar = db.get(Bar, event.bar_id) if event.bar_id is not None else None
    return {
        "barId": str(event.bar_id) if event.bar_id is not None else None,
        "bar_id": event.bar_id,
        "barName": getattr(bar, "name", None),
        "eventId": f"event_{event.id}",
        "event_id": event.id,
        "eventApiId": str(event.id),
        "eventName": event.name,
        "eventState": get_event_runtime_state(db, event.id),
        "source": source,
        "server_time": now.isoformat(),
    }


def _mobile_module_state(db: Session, event_id: int, module_field: str | None) -> str:
    state, _ = effective_module_state(db, event_id, module_field)
    return {
        "ON": "on",
        "OFF": "off",
        "READ_ONLY": "readOnly",
        "FROZEN": "frozen",
    }.get(state, "off")


def _parse_mobile_event_id(raw: str) -> int | None:
    normalized = raw.strip()
    if normalized.startswith("event_"):
        normalized = normalized.removeprefix("event_")
    try:
        return int(normalized)
    except ValueError:
        return None


@router.get("/mobile/events/{event_id}/context")
def mobile_event_context(event_id: str, db: Session = Depends(get_db)):
    now = now_utc()
    numeric_event_id = _parse_mobile_event_id(event_id)
    event = db.get(Event, numeric_event_id) if numeric_event_id is not None else None
    if event is None:
        return {
            "eventId": event_id,
            "event_id": numeric_event_id,
            "eventState": "DRAFT",
            "event_state": "DRAFT",
            "moduleStates": {},
            "module_states": {},
            "exists": False,
            "lastUpdatedAt": now.isoformat(),
            "last_updated_at": now.isoformat(),
            "syncedAt": now.isoformat(),
        }

    event_state = get_event_runtime_state(db, event.id)
    module_states = {
        key: _mobile_module_state(db, event.id, field)
        for key, field in _MOBILE_MODULE_FIELDS.items()
    }
    module_states.update(
        {
            "user_event_hub": "on",
            "orga_event_control_hub": "on",
            "user_join": "on",
            "user_wallet": "on",
            "user_ticker": "on",
            "user_polymarket_global": "on",
            "user_forum": "on",
            "user_calendar": "on",
            "user_glossary": "on",
            "user_ranking": "on",
            "orga_menu_admin": "on",
            "orga_music_admin": "on",
            "orga_finance_admin": "on",
            "orga_forum_moderation": "on",
            "bar_dashboard": "on",
            "bar_full_menu_admin": "on",
            "bar_zones_qr": "on",
            "bar_analytics": "on",
        }
    )
    updated_at = getattr(event, "last_updated_at", None) or getattr(
        event, "last_state_updated_at", None
    ) or now

    return {
        "eventId": event_id,
        "event_id": event.id,
        "eventState": event_state,
        "event_state": event_state,
        "moduleStates": module_states,
        "module_states": module_states,
        "exists": True,
        "lastUpdatedAt": updated_at.isoformat(),
        "last_updated_at": updated_at.isoformat(),
        "syncedAt": now.isoformat(),
    }


@router.get('/ops/metrics-lite')
def ops_metrics(identity=Depends(current_identity)):
    ensure_partner_role(identity, {"manager"})
    payload = metrics_lite()
    payload["ts"] = now_utc().isoformat()
    return payload


@router.get('/events/{event_id}/ops/snapshot')
def event_ops_snapshot(
    event_id: int,
    identity=Depends(current_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager"})
    get_owned_event_or_403(db, event_id, identity["bar_id"])

    pending = int(db.query(func.count(Order.id)).filter(Order.event_id == event_id, Order.status == 'NEW').scalar() or 0)
    accepted = int(db.query(func.count(Order.id)).filter(Order.event_id == event_id, Order.status == 'IN_PROGRESS').scalar() or 0)
    entry_total = int(db.query(func.count(EntryScanLog.id)).filter(EntryScanLog.event_id == event_id, EntryScanLog.decision == 'ACCEPT').scalar() or 0)
    denied = (
        db.query(EntryScanLog.reason, func.count(EntryScanLog.id))
        .filter(EntryScanLog.event_id == event_id, EntryScanLog.decision == 'DENY')
        .group_by(EntryScanLog.reason)
        .order_by(func.count(EntryScanLog.id).desc())
        .limit(5)
        .all()
    )

    cfg = db.query(EventModuleConfig).filter(EventModuleConfig.event_id == event_id).first()
    modules = {}
    warnings = []
    for field in ["orders_enabled", "entry_enabled", "checkins_enabled", "wifi_enabled", "safety_enabled"]:
        configured = bool(getattr(cfg, field, False)) if cfg else False
        state, reason = effective_module_state(db, event_id, field)
        modules[field] = {"configured_enabled": configured, "effective_state": state, "reason": reason}
        if state != 'ON':
            warnings.append(f"{field}:{reason}")

    return {
        "event_id": event_id,
        "runtime_state": get_event_runtime_state(db, event_id),
        "modules": modules,
        "counts": {
            "orders_pending": pending,
            "orders_accepted": accepted,
            "entry_total": entry_total,
            "denied_reasons_top": [{"reason": r or "unknown", "count": int(c or 0)} for r, c in denied],
        },
        "warnings": warnings,
        "ts": now_utc().isoformat(),
    }
