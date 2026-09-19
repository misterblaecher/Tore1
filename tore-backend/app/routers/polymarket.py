from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterator, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from db import now_utc
from models import AppUser, Bet, BetResolutionLog, EventConfig, EventRuntimeState, EventStaff, PolymarketEventIdempotency
from app.core.security.user_auth import get_current_user
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
_EVENT_CREATE_RATE_LIMIT: dict[str, list] = {}


def _runtime_write_guard_for_event(db: Session, event_id: int) -> None:
    runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).first()
    state = ((runtime.state if runtime else None) or "RUNNING").upper()
    normalized = "RUNNING" if state == "LIVE" else "PAUSED" if state == "PAUSE" else "ENDED" if state == "CLOSED" else state
    blocked = {
        "PAUSED": "EVENT_PAUSED",
        "MENU_ONLY": "EVENT_MENU_ONLY",
        "DEGRADED": "EVENT_DEGRADED",
        "FROZEN": "EVENT_FROZEN",
        "ENDED": "EVENT_CLOSED",
    }
    if normalized in blocked:
        reason = "event_paused" if normalized == "PAUSED" else normalized.lower()
        raise HTTPException(status_code=423, detail={"reason": reason, "code": blocked[normalized], "message": "Action blocked"})


def _ensure_event_polymarket_enabled(db: Session, event_id: int) -> None:
    cfg = db.query(EventConfig).filter(EventConfig.event_id == event_id).first()
    if not cfg or not bool(cfg.allow_user_bets):
        raise HTTPException(status_code=403, detail={"reason": "module_off", "message": "Module polymarket_event disabled"})


def _event_market_row(bet: Bet, snapshot: dict) -> dict:
    row = _global_market_row(bet, snapshot)
    row["scope"] = "event"
    row["eventId"] = bet.event_id
    return row


def _assert_market_in_event(db: Session, event_id: int, market_id: int) -> Bet:
    bet = db.get(Bet, market_id)
    if not bet or bet.event_id != event_id:
        raise polymarket_service.polymarket_error(404, "invalid_market", "Market not found for this event")
    return bet


def _assert_event_polymarket_write_allowed(db: Session, event_id: int) -> None:
    _ensure_event_polymarket_enabled(db, event_id)
    _runtime_write_guard_for_event(db, event_id)


def _can_create_or_resolve(db: Session, event_id: int, user_id: str) -> bool:
    staff = db.query(EventStaff).filter(EventStaff.event_id == event_id, EventStaff.user_id == user_id, EventStaff.is_active.is_(True)).first()
    role = (staff.role if staff else "").lower()
    return role == "admin"


def _rate_limit_event_create(user_id: str) -> None:
    now = now_utc()
    key = f"{user_id}:create"
    q = _EVENT_CREATE_RATE_LIMIT.setdefault(key, [])
    q[:] = [ts for ts in q if now - ts <= timedelta(minutes=2)]
    if len(q) >= 1:
        raise HTTPException(status_code=429, detail={"reason": "rate_limited", "message": "Create limited to 1/2min"})
    q.append(now)


from app.deps.db import get_db


def _gate_bet_event_state(db: Session, bet_id: int, write: bool = True) -> None:
    bet = db.get(Bet, bet_id)
    if not bet:
        return
    if bet.event_id is not None:
        ensure_event_action_allowed(db, bet.event_id, "polymarket_enabled", write=write)


def _global_market_row(bet: Bet, snapshot: dict) -> dict:
    total_pool = int(snapshot.get("liquidity") or 0)
    return {
        "id": bet.id,
        "question": bet.question,
        "status": "resolved" if bet.status in {"FINALIZED", "RESOLVED_PENDING"} else bet.status.lower(),
        "type": (bet.kind or "OBJECTIVE").lower(),
        "yesPrice": float(snapshot.get("yes_price") or 0.5),
        "noPrice": float(snapshot.get("no_price") or 0.5),
        "yesPct": float(snapshot.get("yes_price") or 0.5),
        "poolTickets": total_pool,
        "volumeTickets": int(snapshot.get("volume") or total_pool),
        "createdAt": bet.created_at.isoformat() if bet.created_at else None,
        "resolvesAt": bet.deadline_at.isoformat() if bet.deadline_at else None,
    }


def _global_market_detail(bet: Bet, snapshot: dict, detail: dict, me: dict | None) -> dict:
    return {
        "id": bet.id,
        "question": bet.question,
        "description": detail.get("rules_text"),
        "status": "resolved" if bet.status in {"FINALIZED", "RESOLVED_PENDING"} else bet.status.lower(),
        "type": (bet.kind or "OBJECTIVE").lower(),
        "yesPct": float(snapshot.get("yes_price") or 0.5),
        "noPct": float(snapshot.get("no_price") or 0.5),
        "poolTickets": int(snapshot.get("liquidity") or 0),
        "volumeTickets": int(snapshot.get("volume") or 0),
        "outcome": (bet.resolved_outcome or "").upper() or None,
        "rules": detail.get("rules_text"),
        "orderbook": {
            "yesPrice": float(snapshot.get("yes_price") or 0.5),
            "noPrice": float(snapshot.get("no_price") or 0.5),
        },
        "position": {
            "yesShares": int(me.get("stake_yes") or 0) if me else 0,
            "noShares": int(me.get("stake_no") or 0) if me else 0,
            "totalShares": int(me.get("stake_total") or 0) if me else 0,
            "avgPrice": None,
            "pnl": None,
            "isWinner": None,
        },
    }


@router.get("/polymarket/global")
def list_polymarket_global(
    status: str = Query(default="all"),
    type: str = Query(default="all"),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = polymarket_service.optional_current_user(authorization, db)
    status_norm = (status or "all").strip().lower()
    if status_norm not in {"all", "live", "resolved"}:
        raise polymarket_service.polymarket_error(422, "invalid_market", "Invalid status")
    type_norm = (type or "all").strip().lower()
    if type_norm not in {"all", "objective", "subjective"}:
        raise polymarket_service.polymarket_error(422, "invalid_market", "Invalid type")

    mapped_status = None if status_norm == "all" else status_norm
    rows, next_cursor = polymarket_service.list_markets_cursor(
        db,
        scope="global",
        event_id=None,
        status=mapped_status,
        cursor=cursor,
        limit=limit,
        user_id=user.id if user else None,
    )

    ids = [int(r["id"]) for r in rows]
    bets = db.query(Bet).filter(Bet.id.in_(ids)).all() if ids else []
    by_id = {b.id: b for b in bets}
    items = []
    for row in rows:
        bet = by_id.get(int(row["id"]))
        if not bet:
            continue
        if type_norm != "all" and (bet.kind or "").lower() != type_norm:
            continue
        items.append(_global_market_row(bet, row))

    return {"items": items, "next_cursor": next_cursor}


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
    _gate_bet_event_state(db, market_id, write=False)
    bet = db.get(Bet, market_id)
    if not bet:
        raise polymarket_service.polymarket_error(404, "invalid_market", "Bet not found")
    detail = polymarket_service.get_bet_detail(db, bet_id=market_id, authorization=None)
    history, next_cursor = polymarket_service.user_market_history(
        db,
        market_id=market_id,
        user_id=user.id,
        cursor=cursor,
        limit=limit,
    )
    market_snapshot = polymarket_service.market_snapshot_for_user(db, bet, user.id)
    me = polymarket_service.get_bet_me(db, bet_id=market_id, user=user, include_wallet_balance=False)
    return {
        "market": _global_market_detail(bet, market_snapshot, detail, me),
        "detail": detail,
        "my_history": history,
        "next_cursor": next_cursor,
    }


@router.post("/polymarket/markets/{market_id}/buy")
def buy_polymarket_market(
    market_id: int,
    payload: dict,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    key = (idempotency_key or "").strip()
    if not key:
        raise polymarket_service.polymarket_error(422, "idempotency_required", "Idempotency-Key required")

    _gate_bet_event_state(db, market_id, write=True)
    rate_limit_service.enforce_rate_limit("polymarket.position", user.id)
    side = polymarket_service.ensure_bet_side(str(payload.get("side") or ""))
    amount = int(payload.get("amountTickets") or 0)
    if amount <= 0:
        raise polymarket_service.polymarket_error(422, "invalid_amount", "amountTickets must be >= 1")

    try:
        res = polymarket_service.create_position(
            db,
            bet_id=market_id,
            user_id=user.id,
            side=side,
            stake=amount,
            idempotency_key=key,
        )
    except HTTPException as exc:
        if exc.status_code == 400 and isinstance(exc.detail, str) and "Insufficient wallet balance" in exc.detail:
            raise polymarket_service.polymarket_error(400, "insufficient_balance", "Insufficient wallet balance") from exc
        raise

    bet = db.get(Bet, market_id)
    me = polymarket_service.get_bet_me(db, bet_id=market_id, user=user, include_wallet_balance=False)
    polymarket_service.audit_polymarket(db, action="polymarket.position", user=user, bet=bet, payload={"side": side, "amountTickets": amount, "idempotency_key": key})
    db.commit()
    return {
        "market": _global_market_row(bet, polymarket_service.market_snapshot_for_user(db, bet, user.id)),
        "userPosition": {
            "yesShares": int(me.get("stake_yes") or 0),
            "noShares": int(me.get("stake_no") or 0),
            "totalShares": int(me.get("stake_total") or 0),
        },
        "position": res.get("position"),
    }


@router.get("/polymarket/markets/{market_id}/position")
def get_polymarket_market_position(
    market_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _gate_bet_event_state(db, market_id, write=False)
    me = polymarket_service.get_bet_me(db, bet_id=market_id, user=user, include_wallet_balance=False)
    return {
        "marketId": market_id,
        "shares": {
            "yes": int(me.get("stake_yes") or 0),
            "no": int(me.get("stake_no") or 0),
            "total": int(me.get("stake_total") or 0),
        },
        "avgPrice": None,
        "pnl": None,
    }


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


@router.get("/events/{event_id}/polymarket")
def list_event_polymarket_markets(
    event_id: int,
    status: str = Query(default="all"),
    type: str = Query(default="all"),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _ensure_event_polymarket_enabled(db, event_id)
    _runtime_write_guard_for_event(db, event_id)
    user = polymarket_service.optional_current_user(authorization, db)

    status_norm = (status or "all").strip().lower()
    if status_norm not in {"all", "live", "resolved"}:
        raise polymarket_service.polymarket_error(422, "invalid_market", "Invalid status")
    type_norm = (type or "all").strip().lower()
    if type_norm not in {"all", "objective", "subjective"}:
        raise polymarket_service.polymarket_error(422, "invalid_market", "Invalid type")

    rows, next_cursor = polymarket_service.list_markets_cursor(
        db,
        scope="event",
        event_id=event_id,
        status=None if status_norm == "all" else status_norm,
        cursor=cursor,
        limit=limit,
        user_id=user.id if user else None,
    )
    items = []
    ids = [int(r["id"]) for r in rows]
    by_id = {b.id: b for b in db.query(Bet).filter(Bet.id.in_(ids)).all()} if ids else {}
    for row in rows:
        bet = by_id.get(int(row["id"]))
        if not bet:
            continue
        if type_norm != "all" and (bet.kind or "").lower() != type_norm:
            continue
        items.append(_event_market_row(bet, row))

    return {"items": items, "next_cursor": next_cursor}


@router.post("/events/{event_id}/polymarket")
def create_event_polymarket_market(
    event_id: int,
    payload: dict,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    idem = (idempotency_key or "").strip()
    if not idem:
        raise polymarket_service.polymarket_error(422, "idempotency_required", "Idempotency-Key required")
    _assert_event_polymarket_write_allowed(db, event_id)
    if not _can_create_or_resolve(db, event_id, user.id):
        raise HTTPException(status_code=403, detail={"reason": "forbidden", "message": "Missing permission"})

    existing = db.query(PolymarketEventIdempotency).filter(
        PolymarketEventIdempotency.event_id == event_id,
        PolymarketEventIdempotency.action == "create",
        PolymarketEventIdempotency.idempotency_key == idem,
    ).first()
    if existing:
        return existing.response_json

    _rate_limit_event_create(user.id)

    question = str(payload.get("question") or "").strip()
    if len(question) < 6:
        raise polymarket_service.polymarket_error(422, "invalid_market", "Question too short")
    market_type = str(payload.get("type") or "objective").strip().upper()
    if market_type not in {"OBJECTIVE", "SUBJECTIVE"}:
        raise polymarket_service.polymarket_error(422, "invalid_market", "Invalid type")
    raw_resolves_at = payload.get("resolvesAt")
    resolves_at = now_utc() + timedelta(hours=2)
    if raw_resolves_at:
        parsed = datetime.fromisoformat(str(raw_resolves_at))
        resolves_at = parsed if parsed.tzinfo is None else parsed.astimezone(timezone.utc).replace(tzinfo=None)
    rules = str(payload.get("rules") or payload.get("description") or "").strip() or "Event polymarket market"

    bet_payload = BetCreateIn(
        scope="EVENT",
        event_id=event_id,
        question=question,
        kind=market_type,
        deadline_at=resolves_at,
        rules_text=rules,
        dispute_window_minutes=60,
    )
    created = polymarket_service.create_bet(db, payload=bet_payload, user=user)
    bet = db.get(Bet, int(created["id"]))
    response = _event_market_row(bet, polymarket_service.market_snapshot_for_user(db, bet, user.id))
    db.add(PolymarketEventIdempotency(event_id=event_id, market_id=bet.id, action="create", actor_user_id=user.id, idempotency_key=idem, response_json=response))
    polymarket_service.audit_polymarket(db, action="polymarket.event.create", user=user, bet=bet, payload={"idempotency_key": idem, "type": market_type})
    db.commit()
    return response


@router.post("/events/{event_id}/polymarket/{market_id}/resolve")
def resolve_event_polymarket_market(
    event_id: int,
    market_id: int,
    payload: dict,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    idem = (idempotency_key or "").strip()
    if not idem:
        raise polymarket_service.polymarket_error(422, "idempotency_required", "Idempotency-Key required")
    _assert_event_polymarket_write_allowed(db, event_id)
    bet = _assert_market_in_event(db, event_id, market_id)
    if not _can_create_or_resolve(db, event_id, user.id):
        raise HTTPException(status_code=403, detail={"reason": "forbidden", "message": "Missing permission"})

    existing = db.query(PolymarketEventIdempotency).filter(
        PolymarketEventIdempotency.event_id == event_id,
        PolymarketEventIdempotency.action == "resolve",
        PolymarketEventIdempotency.idempotency_key == idem,
    ).first()
    if existing:
        return existing.response_json

    outcome = str(payload.get("outcome") or "").strip().upper()
    if outcome not in {"YES", "NO", "VOID"}:
        raise polymarket_service.polymarket_error(422, "invalid_market", "Invalid outcome")
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 3:
        raise polymarket_service.polymarket_error(422, "reason_required", "reason required")

    if outcome == "VOID":
        if bet.status == "FINALIZED":
            raise polymarket_service.polymarket_error(409, "already_resolved", "Bet already resolved")
        bet.status = "RESOLVED_PENDING"
        bet.resolved_outcome = "VOID"
        bet.resolved_at = now_utc()
        db.add(bet)
        db.add(BetResolutionLog(bet_id=bet.id, actor_user_id=user.id, action="resolve", outcome="VOID", notes=reason))
        resolved = polymarket_service.bet_out(bet)
    else:
        resolved = polymarket_service.resolve_bet(db, bet_id=market_id, outcome=outcome, actor=user)
        db.add(BetResolutionLog(bet_id=bet.id, actor_user_id=user.id, action="resolve_reason", outcome=outcome, notes=reason))

    response = {"market": resolved, "payouts": None}
    db.add(PolymarketEventIdempotency(event_id=event_id, market_id=market_id, action="resolve", actor_user_id=user.id, idempotency_key=idem, response_json=response))
    polymarket_service.audit_polymarket(db, action="polymarket.event.resolve", user=user, bet=bet, payload={"outcome": outcome, "reason": reason, "idempotency_key": idem})
    db.commit()
    return response


@router.post("/events/{event_id}/polymarket/{market_id}/buy")
def buy_event_polymarket_market(
    event_id: int,
    market_id: int,
    payload: dict,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_event_polymarket_write_allowed(db, event_id)
    _assert_market_in_event(db, event_id, market_id)
    return buy_polymarket_market(market_id=market_id, payload=payload, idempotency_key=idempotency_key, user=user, db=db)


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
