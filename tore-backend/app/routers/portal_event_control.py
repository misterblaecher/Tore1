from __future__ import annotations

from datetime import datetime
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from sqlalchemy import func
from models import Bet, BetDispute
from partner_auth import require_role
from app.schemas.event_modules import EventModulesOut, EventModulesUpdateIn
from app.schemas.wallet_admin import WalletAdminLogOut, WalletAdminLogPageOut, WalletAdminTopupIn, WalletAdminTopupOut
from app.services.audit_service import write_audit_log
from app.services.entry_service import get_owned_event_or_403
from app.services.event_modules_service import get_or_create_event_modules, update_event_modules
from app.services.wallet_admin_service import admin_topup, list_wallet_admin_logs
from app.services.wallet_service import get_or_create_wallet

router = APIRouter(prefix="/partner/portal", tags=["portal-event-control"])


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


@router.get("/event/{event_id}/modules", response_model=EventModulesOut)
def get_event_modules(
    event_id: int,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    cfg = get_or_create_event_modules(db, event_id)
    return cfg


@router.post("/event/{event_id}/modules", response_model=EventModulesOut)
def update_modules(
    event_id: int,
    payload: EventModulesUpdateIn,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    cfg = get_or_create_event_modules(db, event_id)
    before = {
        k: getattr(cfg, k)
        for k in ["orders_enabled", "market_enabled", "battles_enabled", "hunt_enabled", "polymarket_enabled", "entry_enabled", "checkins_enabled", "wifi_enabled", "safety_enabled"]
    }
    cfg = update_event_modules(db, cfg, payload.model_dump(), identity["user_id"])
    after = {
        k: getattr(cfg, k)
        for k in ["orders_enabled", "market_enabled", "battles_enabled", "hunt_enabled", "polymarket_enabled", "entry_enabled", "checkins_enabled", "wifi_enabled", "safety_enabled"]
    }
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


@router.post("/wallet/admin/topup", response_model=WalletAdminTopupOut)
def wallet_admin_topup(
    payload: WalletAdminTopupIn,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, payload.event_id, identity["bar_id"])
    ledger, idempotent = admin_topup(
        db,
        event_id=payload.event_id,
        user_id=payload.user_id,
        amount_tickets=payload.amount_tickets,
        reason=payload.reason,
        idempotency_key=payload.idempotency_key,
        actor_user_id=identity["user_id"],
    )
    if not idempotent:
        write_audit_log(
            db,
            actor_partner_id=identity["user_id"],
            actor_role=identity["role"],
            action="wallet_admin.topup",
            entity_type="wallet_ledger_entry",
            entity_id=str(ledger.id),
            event_id=payload.event_id,
            bar_id=event.bar_id,
            payload={"user_id": payload.user_id, "amount_tickets": payload.amount_tickets, "reason": payload.reason},
        )
    db.commit()
    wallet = get_or_create_wallet(db, payload.user_id)
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


@router.get("/wallet/admin/logs", response_model=WalletAdminLogPageOut)
def wallet_admin_logs(
    event_id: int,
    user_id: Optional[str] = Query(default=None),
    after: Optional[datetime] = Query(default=None),
    before: Optional[datetime] = Query(default=None),
    min_delta: Optional[int] = Query(default=None),
    max_delta: Optional[int] = Query(default=None),
    idempotency_key: Optional[str] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    rows, next_cursor = list_wallet_admin_logs(
        db,
        event_id=event.id,
        user_id=user_id,
        after=after,
        before=before,
        min_delta=min_delta,
        max_delta=max_delta,
        idempotency_key=idempotency_key,
        cursor=cursor,
        limit=limit,
    )
    return WalletAdminLogPageOut(
        items=[WalletAdminLogOut(id=r.id, event_id=r.event_id, user_id=r.user_id, amount_tickets=r.amount_tickets, reason=r.reason, idempotency_key=r.idempotency_key, created_at=r.created_at) for r in rows],
        next_cursor=next_cursor,
    )


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
