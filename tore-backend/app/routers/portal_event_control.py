from __future__ import annotations

from types import SimpleNamespace
from typing import Iterator, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from sqlalchemy import func
from models import Bet, BetDispute, WalletLedgerEntry
from app.schemas.polymarket import BetFinalizeOut, BetOut, BetResolveIn
from partner_auth import require_role
from app.schemas.event_modules import EventModulesOut, EventModulesUpdateIn
from app.schemas.wallet_admin import WalletAdminLogOut, WalletAdminTopupIn, WalletAdminTopupOut
from app.services.entry_service import get_owned_event_or_403
from app.services.event_modules_service import get_or_create_event_modules, update_event_modules
from app.services.wallet_admin_service import admin_topup
from app.services.wallet_service import get_or_create_wallet
from app.services import polymarket_service

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
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    cfg = get_or_create_event_modules(db, event_id)
    cfg = update_event_modules(db, cfg, payload.model_dump(), identity["user_id"])
    return cfg


@router.post("/wallet/admin/topup", response_model=WalletAdminTopupOut)
def wallet_admin_topup(
    payload: WalletAdminTopupIn,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    get_owned_event_or_403(db, payload.event_id, identity["bar_id"])
    ledger, idempotent = admin_topup(
        db,
        event_id=payload.event_id,
        user_id=payload.user_id,
        amount_tickets=payload.amount_tickets,
        reason=payload.reason,
        idempotency_key=payload.idempotency_key,
        actor_user_id=identity["user_id"],
    )
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


@router.get("/wallet/admin/logs", response_model=List[WalletAdminLogOut])
def wallet_admin_logs(
    event_id: int,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    rows = (
        db.query(WalletLedgerEntry)
        .filter(WalletLedgerEntry.event_id == event.id)
        .order_by(WalletLedgerEntry.created_at.desc())
        .limit(100)
        .all()
    )
    return rows


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


@router.post("/polymarket/bets/{bet_id}/resolve", response_model=BetOut)
def portal_resolve_polymarket_bet(
    bet_id: int,
    payload: BetResolveIn,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    bet = db.get(Bet, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    if bet.scope != "EVENT" or bet.event_id is None:
        raise HTTPException(status_code=403, detail="Forbidden")

    get_owned_event_or_403(db, bet.event_id, identity["bar_id"])
    actor = SimpleNamespace(id=f"partner:{identity['user_id']}")

    outcome = polymarket_service.ensure_bet_side(payload.outcome)
    return polymarket_service.resolve_bet(
        db,
        bet_id=bet_id,
        outcome=outcome,
        actor=actor,
        force_admin=True,
    )


@router.post("/polymarket/bets/{bet_id}/finalize", response_model=BetFinalizeOut)
def portal_finalize_polymarket_bet(
    bet_id: int,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    bet = db.get(Bet, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    if bet.scope != "EVENT" or bet.event_id is None:
        raise HTTPException(status_code=403, detail="Forbidden")

    get_owned_event_or_403(db, bet.event_id, identity["bar_id"])
    actor = SimpleNamespace(id=f"partner:{identity['user_id']}")

    return polymarket_service.finalize_bet(db, bet_id=bet_id, actor=actor, force_admin=True)
