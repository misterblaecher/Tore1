from __future__ import annotations

from datetime import datetime
import csv
import io
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from sqlalchemy import func
from db import now_utc
from models import Bet, BetDispute, Event, EventRuntimeState
from partner_auth import require_role
from app.schemas.event_modules import EventModulesOut, EventModulesUpdateIn
from app.schemas.wallet_admin import WalletAdminLogOut, WalletAdminLogPageOut, WalletAdminTopupIn, WalletAdminTopupOut
from app.services.audit_service import write_audit_log
from app.services.entry_service import get_owned_event_or_403
from app.services.event_modules_service import get_or_create_event_modules, update_event_modules
from app.services.wallet_admin_service import admin_topup, list_wallet_admin_logs
from app.services.rate_limit_service import enforce_rate_limit
from app.services.wallet_service import get_or_create_wallet
from app.services.p3_common import effective_module_state, ensure_event_action_allowed, get_event_runtime_state, is_event_live

router = APIRouter(prefix="/partner/portal", tags=["portal-event-control"])

MODULE_FIELDS = [
    "orders_enabled",
    "market_enabled",
    "battles_enabled",
    "hunt_enabled",
    "polymarket_enabled",
    "entry_enabled",
    "checkins_enabled",
    "wifi_enabled",
    "safety_enabled",
]


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


def _get_or_create_runtime_state(db: Session, event_id: int) -> EventRuntimeState:
    row = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).first()
    if row:
        return row
    row = EventRuntimeState(event_id=event_id, state="LIVE")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row



@router.get("/event/{event_id}/modules", response_model=EventModulesOut)
def get_event_modules(
    event_id: int,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    cfg = get_or_create_event_modules(db, event_id)
    return cfg


@router.get("/event/{event_id}/status")
def get_event_status(
    event_id: int,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    cfg = get_or_create_event_modules(db, event_id)
    return {
        "event_id": event_id,
        "live": is_event_live(db, event_id),
        "modules": {field: getattr(cfg, field) for field in MODULE_FIELDS},
    }


@router.get("/event/{event_id}/state-snapshot")
def event_state_snapshot(
    event_id: int,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    cfg = get_or_create_event_modules(db, event_id)
    runtime = _get_or_create_runtime_state(db, event_id)
    event_state = get_event_runtime_state(db, event_id)
    modules = {}
    warnings = []
    for field in MODULE_FIELDS:
        effective, reason = effective_module_state(db, event_id, field)
        enabled = bool(getattr(cfg, field))
        modules[field] = {"configured_enabled": enabled, "effective_state": effective, "reason": reason}
        if effective in {"READ_ONLY", "OFF"}:
            warnings.append(f"{field}:{effective}:{reason}")
    return {
        "event_id": event_id,
        "event_state": event_state,
        "runtime_reason": runtime.reason,
        "modules": modules,
        "warnings": warnings,
        "priority_rule": "event_state_overrides_module_toggle",
    }


@router.post("/event/{event_id}/state")
def set_event_runtime_state(
    event_id: int,
    payload: dict,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    state = str(payload.get("state") or "").upper()
    if state not in {"LIVE", "PAUSE", "MENU_ONLY", "CLOSED"}:
        return {"ok": False, "code": "INVALID_STATE", "message": "Etat event invalide."}
    runtime = _get_or_create_runtime_state(db, event_id)
    before = {"state": runtime.state, "reason": runtime.reason}
    runtime.state = state
    runtime.reason = (payload.get("reason") or "")[:180] or None
    runtime.updated_by_user_id = identity["user_id"]
    runtime.updated_at = now_utc()
    db.add(runtime)
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="event_state.update",
        entity_type="event",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"before": before, "after": {"state": runtime.state, "reason": runtime.reason}},
    )
    db.commit()
    return {"ok": True, "event_id": event_id, "state": runtime.state, "reason": runtime.reason}


@router.post("/event/{event_id}/modules", response_model=EventModulesOut)
def update_modules(
    event_id: int,
    payload: EventModulesUpdateIn,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    cfg = get_or_create_event_modules(db, event_id)
    before = {k: getattr(cfg, k) for k in MODULE_FIELDS}
    cfg = update_event_modules(db, cfg, payload.model_dump(), identity["user_id"])
    after = {k: getattr(cfg, k) for k in MODULE_FIELDS}
    if before != after:
        write_audit_log(
            db,
            actor_partner_id=identity["user_id"],
            actor_role=identity["role"],
            action="event_modules.update",
            entity_type="event",
            entity_id=str(event_id),
            event_id=event_id,
            bar_id=event.bar_id,
            payload={"before": before, "after": after},
        )
        db.commit()
    return cfg


@router.post("/wallet/topup", response_model=WalletAdminTopupOut)
@router.post("/wallet/admin/topup", response_model=WalletAdminTopupOut)
def wallet_admin_topup(
    payload: WalletAdminTopupIn,
    idempotency_header: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, payload.event_id, identity["bar_id"])
    ensure_event_action_allowed(db, payload.event_id, "wallet_enabled", write=True)
    target_user_id = (payload.target_user_id or payload.user_id or "").strip()
    if not target_user_id:
        raise HTTPException(status_code=400, detail={"reason": "invalid_target", "message": "target_user_id is required"})
    amount = payload.amount_cents if payload.amount_cents is not None else payload.amount_tickets
    if amount is None or amount < 1:
        raise HTTPException(status_code=400, detail={"reason": "invalid_amount", "message": "amount must be >= 1"})
    reason = payload.note or payload.reason or "admin_topup"
    idempotency_key = (idempotency_header or payload.client_key or payload.idempotency_key or "").strip()
    if len(idempotency_key) < 1:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency key required"})
    enforce_rate_limit("wallet_topup", f"{identity['user_id']}:{idempotency_key}")
    ledger, idempotent = admin_topup(
        db,
        event_id=payload.event_id,
        user_id=target_user_id,
        amount_tickets=amount,
        reason=reason,
        idempotency_key=idempotency_key,
        actor_user_id=identity["user_id"],
    )
    if not idempotent:
        write_audit_log(
            db,
            actor_partner_id=identity["user_id"],
            actor_role=identity["role"],
            action="wallet.topup",
            entity_type="wallet_ledger_entry",
            entity_id=str(ledger.id),
            event_id=payload.event_id,
            bar_id=event.bar_id,
            payload={"user_id": target_user_id, "amount_tickets": amount, "reason": reason},
        )
        write_audit_log(
            db,
            actor_partner_id=identity["user_id"],
            actor_role=identity["role"],
            action="wallet_admin.topup",
            entity_type="wallet_ledger_entry",
            entity_id=str(ledger.id),
            event_id=payload.event_id,
            bar_id=event.bar_id,
            payload={"user_id": target_user_id, "amount_tickets": amount, "reason": reason},
        )
    db.commit()
    wallet = get_or_create_wallet(db, target_user_id)
    return WalletAdminTopupOut(
        ledger_id=ledger.id,
        event_id=ledger.event_id,
        user_id=ledger.user_id,
        amount_tickets=ledger.amount_tickets,
        reason=ledger.reason,
        balance_tickets=wallet.balance_tickets,
        idempotent=idempotent,
        created_at=ledger.created_at,
    )


@router.get("/wallet/logs", response_model=WalletAdminLogPageOut)
@router.get("/wallet/admin/logs", response_model=WalletAdminLogPageOut)
def wallet_admin_logs(
    event_id: int,
    user_id: Optional[str] = Query(default=None),
    after: Optional[datetime] = Query(default=None),
    before: Optional[datetime] = Query(default=None),
    min_delta: Optional[int] = Query(default=None),
    max_delta: Optional[int] = Query(default=None),
    idempotency_key: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    ensure_event_action_allowed(db, event_id, "wallet_enabled", write=False)
    rows, next_cursor = list_wallet_admin_logs(
        db,
        event_id=event.id,
        user_id=user_id,
        after=after,
        before=before,
        min_delta=min_delta,
        max_delta=max_delta,
        idempotency_key=idempotency_key,
        query=q,
        tx_type=type,
        cursor=cursor,
        limit=limit,
    )
    return WalletAdminLogPageOut(
        items=[WalletAdminLogOut(id=r.id, event_id=r.event_id, user_id=r.user_id, amount_tickets=r.amount_tickets, reason=r.reason, idempotency_key=r.idempotency_key, created_at=r.created_at) for r in rows],
        next_cursor=next_cursor,
    )


@router.get("/wallet/logs/export.csv")
def wallet_admin_logs_export(
    event_id: int,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    ensure_event_action_allowed(db, event_id, "wallet_enabled", write=False)
    rows, _ = list_wallet_admin_logs(
        db,
        event_id=event.id,
        user_id=None,
        after=None,
        before=None,
        min_delta=None,
        max_delta=None,
        idempotency_key=None,
        query=None,
        tx_type=None,
        cursor=None,
        limit=10000,
    )
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="wallet.export",
        entity_type="wallet_ledger_entry",
        entity_id=None,
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"rows": len(rows)},
    )
    db.commit()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ts", "user_id", "type", "amount", "note", "ref_id"])
    for row in rows:
        writer.writerow([row.created_at.isoformat(), row.user_id, "topup", row.amount_tickets, row.reason, row.idempotency_key])

    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=wallet_logs_event_{event_id}.csv"})


@router.get("/polymarket/event/{event_id}")
def portal_polymarket_event_view(
    event_id: int,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    from app.services.polymarket_service import list_bets

    get_owned_event_or_403(db, event_id, identity["bar_id"])
    bets = list_bets(db, scope="EVENT", event_id=event_id, status=None, kind=None, limit=200, offset=0)
    dispute_rows = (
        db.query(BetDispute.bet_id, func.count(BetDispute.id))
        .join(Bet, Bet.id == BetDispute.bet_id)
        .filter(Bet.event_id == event_id)
        .group_by(BetDispute.bet_id)
        .all()
    )
    dispute_map = {bet_id: int(count or 0) for bet_id, count in dispute_rows}
    for bet in bets:
        status = bet.get("status")
        bet["status_compat"] = "RESOLVED" if status == "FINALIZED" else status
        bet["disputes_count"] = dispute_map.get(bet.get("id"), 0)
    return {"event_id": event_id, "bets": bets}
