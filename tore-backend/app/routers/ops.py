from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import now_utc
from models import EntryScanLog, EventModuleConfig, Order
from partner_auth import current_identity
from app.services.authz_service import ensure_partner_role
from app.services.entry_service import get_owned_event_or_403
from app.services.p3_common import effective_module_state, get_event_runtime_state
from app.services.rate_limit_service import metrics_lite

router = APIRouter(tags=["ops"])


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


def _health_payload() -> dict:
    return {"ok": True, "ts": now_utc().isoformat(), "version": "mvp-mega", "db_ok": True}


@router.get('/healthz')
def healthz():
    return _health_payload()


@router.get('/api/healthz')
def api_healthz():
    return _health_payload()


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
