from __future__ import annotations

from typing import Iterator, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
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
from app.services import polymarket_service, rate_limit_service
from app.services.p3_common import ensure_event_action_allowed

router = APIRouter()


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


def _gate_bet_event_state(db: Session, bet_id: int, write: bool = True) -> None:
    bet = db.get(Bet, bet_id)
    if not bet:
        return
    if bet.event_id is not None:
        ensure_event_action_allowed(db, bet.event_id, "polymarket_enabled", write=write)


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


@router.get("/polymarket/markets")
def list_polymarket_markets(
    scope: Optional[str] = Query(default=None),
    event_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = polymarket_service.optional_current_user(authorization, db)
    rows, next_cursor = polymarket_service.list_markets_cursor(
        db,
        scope=scope,
        event_id=event_id,
        status=status,
        cursor=cursor,
        limit=limit,
        user_id=user.id if user else None,
    )
    return {"items": rows, "next_cursor": next_cursor}


@router.get("/polymarket/markets/{market_id}")
def polymarket_market_detail(
    market_id: int,
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    detail = polymarket_service.get_bet_detail(db, bet_id=market_id, authorization=None)
    history, next_cursor = polymarket_service.user_market_history(
        db,
        market_id=market_id,
        user_id=user.id,
        cursor=cursor,
        limit=limit,
    )
    return {"market": polymarket_service.market_snapshot_for_user(db, db.get(Bet, market_id), user.id), "detail": detail, "my_history": history, "next_cursor": next_cursor}


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
    if payload.scope.upper() == "EVENT" and payload.event_id is not None:
        ensure_event_action_allowed(db, payload.event_id, "polymarket_enabled", write=True)
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
    _gate_bet_event_state(db, bet_id, write=True)
    side = polymarket_service.ensure_bet_side(payload.side)
    res = polymarket_service.create_position(
        db,
        bet_id=bet_id,
        user_id=user.id,
        side=side,
        stake=payload.stake_tickets,
        idempotency_key=payload.idempotency_key.strip(),
    )
    bet = db.get(Bet, bet_id)
    polymarket_service.audit_polymarket(db, action="polymarket.position", user=user, bet=bet, payload={"side": side, "stake": payload.stake_tickets})
    db.commit()
    return res


@router.post("/polymarket/position")
def create_polymarket_position_ultra(
    payload: dict,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    market_id = int(payload.get("market_id") or 0)
    side = str(payload.get("side") or "").upper()
    amount = int(payload.get("amount_cents") or 0)
    key = (idempotency_key or payload.get("client_key") or "").strip()
    if not key:
        raise polymarket_service.polymarket_error(422, "invalid_market", "Missing idempotency key")
    _gate_bet_event_state(db, market_id, write=True)
    rate_limit_service.enforce_rate_limit("polymarket.position", user.id)
    try:
        res = polymarket_service.create_position(
            db,
            bet_id=market_id,
            user_id=user.id,
            side=polymarket_service.ensure_bet_side(side),
            stake=amount,
            idempotency_key=key,
        )
    except Exception as exc:
        from fastapi import HTTPException

        if isinstance(exc, HTTPException) and exc.status_code == 400 and isinstance(exc.detail, str) and "Insufficient wallet balance" in exc.detail:
            raise polymarket_service.polymarket_error(400, "insufficient_balance", "Insufficient wallet balance") from exc
        raise
    bet = db.get(Bet, market_id)
    me = polymarket_service.get_bet_me(db, bet_id=market_id, user=user, include_wallet_balance=True)
    polymarket_service.audit_polymarket(db, action="polymarket.position", user=user, bet=bet, payload={"side": side, "amount": amount})
    db.commit()
    return {
        "trade_id": res["position"]["id"],
        "new_balance": me["wallet_balance_tickets"],
        "market": polymarket_service.market_snapshot_for_user(db, bet, user.id),
    }


@router.get("/polymarket/positions")
def my_positions_ultra(
    scope: Optional[str] = Query(default=None),
    event_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, next_cursor = polymarket_service.list_my_positions_cursor(
        db,
        user_id=user.id,
        scope=scope,
        event_id=event_id,
        status=status,
        cursor=cursor,
        limit=limit,
    )
    return {"items": items, "next_cursor": next_cursor}


@router.get("/polymarket/markets/{market_id}/my-history")
def my_history_ultra(
    market_id: int,
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, next_cursor = polymarket_service.user_market_history(
        db,
        market_id=market_id,
        user_id=user.id,
        cursor=cursor,
        limit=limit,
    )
    return {"items": items, "next_cursor": next_cursor}


@router.post("/polymarket/bets/{bet_id}/resolve", response_model=BetOut)
def resolve_polymarket_bet(
    bet_id: int,
    payload: BetResolveIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _gate_bet_event_state(db, bet_id, write=True)
    outcome = polymarket_service.ensure_bet_side(payload.outcome)
    out = polymarket_service.resolve_bet(db, bet_id=bet_id, outcome=outcome, actor=user)
    polymarket_service.audit_polymarket(db, action="polymarket.resolve", user=user, bet=db.get(Bet, bet_id), payload={"outcome": outcome})
    db.commit()
    return out


@router.post("/polymarket/resolve")
def resolve_polymarket_ultra(
    payload: dict,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bet_id = int(payload.get("market_id") or 0)
    _gate_bet_event_state(db, bet_id, write=True)
    rate_limit_service.enforce_rate_limit("polymarket.resolve", user.id)
    outcome_raw = str(payload.get("outcome") or "").upper()
    if outcome_raw == "INVALID":
        out = polymarket_service.cancel_bet(db, bet_id=bet_id, actor=user)
    else:
        out = polymarket_service.resolve_bet(db, bet_id=bet_id, outcome=polymarket_service.ensure_bet_side(outcome_raw), actor=user)
    polymarket_service.audit_polymarket(db, action="polymarket.resolve", user=user, bet=db.get(Bet, bet_id), payload={"outcome": outcome_raw})
    db.commit()
    return {"market": polymarket_service.market_snapshot_for_user(db, db.get(Bet, bet_id), user.id), "result": out}


@router.post("/polymarket/bets/{bet_id}/finalize", response_model=BetFinalizeOut)
def finalize_polymarket_bet(
    bet_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        _gate_bet_event_state(db, bet_id, write=True)
    except HTTPException as exc:
        if isinstance(exc.detail, dict):
            raise HTTPException(status_code=exc.status_code, detail=str(exc.detail.get("message") or exc.detail.get("reason") or "Action blocked"))
        raise
    try:
        out = polymarket_service.finalize_bet(db, bet_id=bet_id, actor=user)
    except HTTPException as exc:
        if isinstance(exc.detail, dict):
            raise HTTPException(status_code=exc.status_code, detail=str(exc.detail.get("message") or exc.detail.get("reason") or "Action blocked"))
        raise
    polymarket_service.audit_polymarket(db, action="polymarket.finalize", user=user, bet=db.get(Bet, bet_id), payload={})
    db.commit()
    return out


@router.post("/polymarket/finalize")
def finalize_polymarket_ultra(
    payload: dict,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bet_id = int(payload.get("market_id") or 0)
    try:
        _gate_bet_event_state(db, bet_id, write=True)
    except HTTPException as exc:
        if isinstance(exc.detail, dict):
            raise HTTPException(status_code=exc.status_code, detail=str(exc.detail.get("message") or exc.detail.get("reason") or "Action blocked"))
        raise
    try:
        out = polymarket_service.finalize_bet(db, bet_id=bet_id, actor=user)
    except HTTPException as exc:
        if isinstance(exc.detail, dict):
            raise HTTPException(status_code=exc.status_code, detail=str(exc.detail.get("message") or exc.detail.get("reason") or "Action blocked"))
        raise
    polymarket_service.audit_polymarket(db, action="polymarket.finalize", user=user, bet=db.get(Bet, bet_id), payload={})
    db.commit()
    return out


@router.post("/polymarket/bets/{bet_id}/dispute", response_model=BetDisputeCreateOut)
def dispute_polymarket_bet(
    bet_id: int,
    payload: BetDisputeIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _gate_bet_event_state(db, bet_id, write=True)
    out = polymarket_service.create_dispute(db, bet_id=bet_id, user=user, reason=payload.reason)
    polymarket_service.audit_polymarket(db, action="polymarket.dispute", user=user, bet=db.get(Bet, bet_id), payload={"reason": payload.reason})
    db.commit()
    return out


@router.post("/polymarket/dispute")
def dispute_polymarket_ultra(
    payload: dict,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bet_id = int(payload.get("market_id") or 0)
    _gate_bet_event_state(db, bet_id, write=True)
    note = str(payload.get("note") or "")
    out = polymarket_service.create_dispute(db, bet_id=bet_id, user=user, reason=note)
    polymarket_service.audit_polymarket(db, action="polymarket.dispute", user=user, bet=db.get(Bet, bet_id), payload={"note": note})
    db.commit()
    return out


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
    _gate_bet_event_state(db, bet_id, write=True)
    out = polymarket_service.cancel_bet(db, bet_id=bet_id, actor=user)
    polymarket_service.audit_polymarket(db, action="polymarket.cancel", user=user, bet=db.get(Bet, bet_id), payload={})
    db.commit()
    return out


@router.post("/polymarket/cancel")
def cancel_polymarket_ultra(
    payload: dict,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bet_id = int(payload.get("market_id") or 0)
    _gate_bet_event_state(db, bet_id, write=True)
    out = polymarket_service.cancel_bet(db, bet_id=bet_id, actor=user)
    polymarket_service.audit_polymarket(db, action="polymarket.cancel", user=user, bet=db.get(Bet, bet_id), payload={"reason": payload.get("reason")})
    db.commit()
    return out


@router.get("/polymarket/exports/markets.csv")
def export_polymarket_markets(
    scope: Optional[str] = Query(default=None),
    event_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    csv_text = polymarket_service.export_markets_csv(db, scope=scope, event_id=event_id, status=status)
    polymarket_service.audit_polymarket(db, action="polymarket.export.markets", user=user, bet=None, payload={"scope": scope, "event_id": event_id, "status": status})
    db.commit()
    return StreamingResponse(iter([csv_text]), media_type="text/csv")


@router.get("/polymarket/exports/positions.csv")
def export_polymarket_positions(
    scope: Optional[str] = Query(default=None),
    event_id: Optional[int] = Query(default=None),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    csv_text = polymarket_service.export_positions_csv(db, user_id=None, scope=scope, event_id=event_id)
    polymarket_service.audit_polymarket(db, action="polymarket.export.positions", user=user, bet=None, payload={"scope": scope, "event_id": event_id})
    db.commit()
    return StreamingResponse(iter([csv_text]), media_type="text/csv")


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
        raise polymarket_service.polymarket_error(status_code=404, reason="invalid_market", message="Bet not found")
    return polymarket_service.get_polymarket_share_payload(bet_id)
