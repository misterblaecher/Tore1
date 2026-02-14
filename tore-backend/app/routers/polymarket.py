from __future__ import annotations

from typing import Iterator, List, Optional

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from models import AppUser, Bet
from main import get_current_user
from app.schemas.polymarket import (
    BetCreateIn,
    BetDetailOut,
    BetDisputeCreateOut,
    BetDisputeIn,
    BetFinalizeOut,
    BetLogsOut,
    BetMeOut,
    BetOut,
    BetPositionCreateIn,
    BetPositionResponseOut,
    BetResolveIn,
    BetShareOut,
    BetTimelinePointOut,
)
from app.services import polymarket_service

router = APIRouter()


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


@router.get("/polymarket/bets", response_model=List[BetOut])
def list_polymarket_bets(
    scope: Optional[str] = Query(default=None),
    event_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return polymarket_service.list_bets(
        db,
        scope=scope,
        event_id=event_id,
        status=status,
        kind=kind,
        limit=limit,
        offset=offset,
    )




@router.get("/polymarket/event/{event_id}")
def list_polymarket_event_view(
    event_id: int,
    db: Session = Depends(get_db),
):
    bets = polymarket_service.list_bets(
        db,
        scope="EVENT",
        event_id=event_id,
        status=None,
        kind=None,
        limit=200,
        offset=0,
    )
    for bet in bets:
        status = bet.get("status")
        bet["status_compat"] = "RESOLVED" if status == "FINALIZED" else status
    return {"event_id": event_id, "bets": bets}
@router.post("/polymarket/bets", response_model=BetOut)
def create_polymarket_bet(
    payload: BetCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return polymarket_service.create_bet(db, payload=payload, user=user)


@router.get("/polymarket/bets/{bet_id}", response_model=BetDetailOut)
def get_polymarket_bet(
    bet_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    return polymarket_service.get_bet_detail(db, bet_id=bet_id, authorization=authorization)


@router.get("/polymarket/bets/{bet_id}/me", response_model=BetMeOut)
def get_polymarket_bet_me(
    bet_id: int,
    include_wallet_balance: bool = Query(default=True),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return polymarket_service.get_bet_me(
        db,
        bet_id=bet_id,
        user=user,
        include_wallet_balance=include_wallet_balance,
    )


@router.post("/polymarket/bets/{bet_id}/positions", response_model=BetPositionResponseOut)
def create_polymarket_position(
    bet_id: int,
    payload: BetPositionCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    side = polymarket_service.ensure_bet_side(payload.side)
    return polymarket_service.create_position(
        db,
        bet_id=bet_id,
        user_id=user.id,
        side=side,
        stake=payload.stake_tickets,
        idempotency_key=payload.idempotency_key.strip(),
    )


@router.post("/polymarket/bets/{bet_id}/resolve", response_model=BetOut)
def resolve_polymarket_bet(
    bet_id: int,
    payload: BetResolveIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    outcome = polymarket_service.ensure_bet_side(payload.outcome)
    return polymarket_service.resolve_bet(db, bet_id=bet_id, outcome=outcome, actor=user)




@router.post("/polymarket/bets/{bet_id}/finalize", response_model=BetFinalizeOut)
def finalize_polymarket_bet(
    bet_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return polymarket_service.finalize_bet(db, bet_id=bet_id, actor=user)


@router.post("/polymarket/bets/{bet_id}/dispute", response_model=BetDisputeCreateOut)
def dispute_polymarket_bet(
    bet_id: int,
    payload: BetDisputeIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return polymarket_service.create_dispute(db, bet_id=bet_id, user=user, reason=payload.reason)


@router.get("/polymarket/bets/{bet_id}/logs", response_model=BetLogsOut)
def get_polymarket_bet_logs(
    bet_id: int,
    db: Session = Depends(get_db),
):
    return polymarket_service.get_bet_logs(db, bet_id=bet_id)


@router.post("/polymarket/bets/{bet_id}/cancel", response_model=BetOut)
def cancel_polymarket_bet(
    bet_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return polymarket_service.cancel_bet(db, bet_id=bet_id, actor=user)


@router.get("/polymarket/bets/{bet_id}/timeline", response_model=List[BetTimelinePointOut])
def polymarket_bet_timeline(
    bet_id: int,
    db: Session = Depends(get_db),
):
    return polymarket_service.bet_timeline(db, bet_id=bet_id)


@router.get("/polymarket/bets/{bet_id}/share", response_model=BetShareOut)
def get_polymarket_bet_share(
    bet_id: int,
    db: Session = Depends(get_db),
):
    bet = db.get(Bet, bet_id)
    if not bet:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Bet not found")
    return polymarket_service.get_polymarket_share_payload(bet_id)
