from __future__ import annotations

import csv
import io
import os
import json
from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import now_utc
from models import AppUser, Bet, BetDispute, BetPosition, BetResolutionLog, Event
from app.services.audit_service import write_audit_log
from app.services.p3_common import decode_cursor, encode_cursor


POLYMARKET_TIMELINE_MAX_POINTS = 200


def polymarket_error(status_code: int, reason: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"reason": reason, "message": message})


def _normalize_upper(value: Optional[str]) -> str:
    return (value or "").strip().upper()


def ensure_bet_scope(scope: str) -> str:
    scope = _normalize_upper(scope)
    if scope not in {"GLOBAL", "EVENT"}:
        raise HTTPException(status_code=422, detail="Invalid scope")
    return scope


def ensure_bet_kind(kind: str) -> str:
    kind = _normalize_upper(kind)
    if kind not in {"OBJECTIVE", "SUBJECTIVE"}:
        raise HTTPException(status_code=422, detail="Invalid kind")
    return kind


def ensure_bet_side(side: str) -> str:
    side = _normalize_upper(side)
    if side not in {"YES", "NO"}:
        raise HTTPException(status_code=422, detail="Invalid side")
    return side


def polymarket_global_creators() -> set[str]:
    raw = os.getenv("POLYMARKET_GLOBAL_CREATORS", "")
    creators = {item.strip() for item in raw.split(",") if item.strip()}
    if not creators:
        return set()
    return creators


def polymarket_global_enabled() -> bool:
    raw = os.getenv("POLYMARKET_GLOBAL_ENABLED")
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_polymarket_admin(user_id: str) -> bool:
    allowlist = polymarket_global_creators()
    return user_id in allowlist if user_id else False


def wallet_tx_key(prefix: str, bet_id: int, user_id: str) -> str:
    return f"{prefix}:{bet_id}:{user_id}"


def bet_total_pool(bet: Bet) -> int:
    return int(bet.pool_yes_tickets or 0) + int(bet.pool_no_tickets or 0)


def bet_pct_yes(bet: Bet) -> float:
    total = bet_total_pool(bet)
    if total <= 0:
        return 0.5
    return float(bet.pool_yes_tickets or 0) / float(total)


def bet_out(bet: Bet) -> Dict[str, Any]:
    total = bet_total_pool(bet)
    pct_yes = bet_pct_yes(bet)
    return {
        "id": bet.id,
        "scope": bet.scope,
        "event_id": bet.event_id,
        "question": bet.question,
        "kind": bet.kind,
        "status": bet.status,
        "deadline_at": bet.deadline_at.isoformat() if bet.deadline_at else None,
        "resolver_user_id": bet.resolver_user_id,
        "rules_text": bet.rules_text,
        "dispute_window_minutes": bet.dispute_window_minutes,
        "created_by_user_id": bet.created_by_user_id,
        "created_at": bet.created_at.isoformat() if bet.created_at else None,
        "resolved_at": bet.resolved_at.isoformat() if bet.resolved_at else None,
        "finalized_at": bet.finalized_at.isoformat() if bet.finalized_at else None,
        "resolved_outcome": bet.resolved_outcome,
        "pool_yes_tickets": bet.pool_yes_tickets,
        "pool_no_tickets": bet.pool_no_tickets,
        "total_pool_tickets": total,
        "pct_yes": pct_yes,
        "pct_no": 1.0 - pct_yes if total > 0 else 0.5,
    }


def optional_current_user(authorization: Optional[str], db: Session) -> Optional[AppUser]:
    from app.legacy.monolith import _extract_bearer_token, _resolve_app_user_from_token

    raw = _extract_bearer_token(authorization)
    if not raw:
        return None
    return _resolve_app_user_from_token(raw, db)


def get_polymarket_share_payload(bet_id: int) -> Dict[str, str]:
    deep_link = f"tore://polymarket?bet_id={bet_id}"
    portal_base = os.getenv("TORE_PORTAL_BASE_URL", "https://tore1.onrender.com").strip() or "https://tore1.onrender.com"
    web_url = f"{portal_base.rstrip('/')}/polymarket/bets/{bet_id}"
    return {
        "deep_link": deep_link,
        "web_url": web_url,
        "qr_payload": deep_link,
    }


def create_position(
    db: Session,
    *,
    bet_id: int,
    user_id: str,
    side: str,
    stake: int,
    idempotency_key: str,
) -> Dict[str, Any]:
    from app.legacy.monolith import _apply_wallet_tx, get_or_create_wallet

    try:
        bet = db.execute(select(Bet).where(Bet.id == bet_id).with_for_update()).scalar_one_or_none()
        if not bet:
            raise polymarket_error(404, "invalid_market", "Bet not found")
        if bet.status != "LIVE":
            if bet.status in {"RESOLVED_PENDING", "FINALIZED"}:
                raise polymarket_error(409, "already_resolved", "Bet already resolved")
            raise polymarket_error(409, "invalid_market", "Bet not live")
        if bet.deadline_at and now_utc() > bet.deadline_at:
            raise polymarket_error(409, "invalid_market", "Bet closed")

        wallet = get_or_create_wallet(db, user_id)
        if wallet.balance_tickets < stake:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient wallet balance: required {stake}, available {wallet.balance_tickets}",
            )

        position = BetPosition(
            bet_id=bet_id,
            user_id=user_id,
            side=side,
            stake_tickets=stake,
            idempotency_key=idempotency_key,
            created_at=now_utc(),
        )
        db.add(position)
        db.flush()
        _apply_wallet_tx(
            db,
            user_id=user_id,
            amount_tickets=-stake,
            kind="BET_STAKE",
            ref_type="BET",
            ref_id=str(bet_id),
            idempotency_key=idempotency_key,
        )
        if side == "YES":
            bet.pool_yes_tickets += stake
        else:
            bet.pool_no_tickets += stake
        db.add(bet)
        db.add(
            BetResolutionLog(
                bet_id=bet.id,
                actor_user_id=user_id,
                action="position",
                outcome=side,
                notes=json.dumps({"stake_tickets": stake, "idempotency_key": idempotency_key}),
            )
        )
        db.commit()
        db.refresh(position)
        return {
            "bet": bet_out(bet),
            "position": {
                "id": position.id,
                "bet_id": position.bet_id,
                "user_id": position.user_id,
                "side": position.side,
                "stake_tickets": position.stake_tickets,
                "created_at": position.created_at.isoformat() if position.created_at else None,
            },
        }
    except IntegrityError:
        db.rollback()
        existing = db.query(BetPosition).filter(
            BetPosition.bet_id == bet_id,
            BetPosition.user_id == user_id,
            BetPosition.idempotency_key == idempotency_key,
        ).first()
        if not existing:
            raise
        bet = db.get(Bet, bet_id)
        if not bet:
            raise polymarket_error(404, "invalid_market", "Bet not found")
        return {
            "bet": bet_out(bet),
            "position": {
                "id": existing.id,
                "bet_id": existing.bet_id,
                "user_id": existing.user_id,
                "side": existing.side,
                "stake_tickets": existing.stake_tickets,
                "created_at": existing.created_at.isoformat() if existing.created_at else None,
            },
        }


def resolve_bet(db: Session, *, bet_id: int, outcome: str, actor: AppUser) -> Dict[str, Any]:
    from app.legacy.monolith import _role_rank, resolve_event_role

    bet = db.execute(select(Bet).where(Bet.id == bet_id).with_for_update()).scalar_one_or_none()
    if not bet:
        raise polymarket_error(404, "invalid_market", "Bet not found")
    if bet.status == "FINALIZED":
        return bet_out(bet)
    if bet.status == "RESOLVED_PENDING" and bet.resolved_outcome == outcome:
        return bet_out(bet)
    if bet.status != "LIVE":
        raise polymarket_error(409, "already_resolved", "Bet not live")

    is_admin = is_polymarket_admin(actor.id)
    if bet.scope == "EVENT" and bet.event_id is not None:
        role = resolve_event_role(db, actor.id, bet.event_id)
        if _role_rank(role) >= _role_rank("admin"):
            is_admin = True

    if bet.kind == "SUBJECTIVE":
        if actor.id != bet.resolver_user_id and not is_admin:
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Forbidden")

    bet.status = "RESOLVED_PENDING"
    bet.resolved_outcome = outcome
    bet.resolved_at = now_utc()
    db.add(bet)

    db.add(
        BetResolutionLog(
            bet_id=bet.id,
            actor_user_id=actor.id,
            action="resolve",
            outcome=outcome,
            notes="proposed_outcome",
        )
    )
    db.commit()
    return bet_out(bet)


def finalize_bet(db: Session, *, bet_id: int, actor: AppUser) -> Dict[str, Any]:
    from app.legacy.monolith import _apply_wallet_tx, _role_rank, resolve_event_role

    bet = db.execute(select(Bet).where(Bet.id == bet_id).with_for_update()).scalar_one_or_none()
    if not bet:
        raise polymarket_error(404, "invalid_market", "Bet not found")
    if bet.status == "FINALIZED":
        return bet_out(bet)
    if bet.status != "RESOLVED_PENDING":
        raise polymarket_error(409, "invalid_market", "Bet not pending resolution")

    is_admin = is_polymarket_admin(actor.id)
    if bet.scope == "EVENT" and bet.event_id is not None:
        role = resolve_event_role(db, actor.id, bet.event_id)
        if _role_rank(role) >= _role_rank("admin"):
            is_admin = True

    if bet.kind == "SUBJECTIVE":
        if actor.id != bet.resolver_user_id and not is_admin:
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Forbidden")

    if not bet.resolved_at:
        raise polymarket_error(400, "invalid_market", "Bet has no resolved_at")

    lock_at = bet.resolved_at + timedelta(minutes=int(bet.dispute_window_minutes or 0))
    if now_utc() < lock_at:
        raise polymarket_error(400, "invalid_market", "Dispute window not expired")

    disputes_count = db.scalar(select(func.count()).select_from(BetDispute).where(BetDispute.bet_id == bet.id)) or 0
    if disputes_count > 0:
        raise polymarket_error(403, "forbidden", "Bet has disputes")

    outcome = bet.resolved_outcome
    if outcome not in {"YES", "NO"}:
        raise polymarket_error(400, "invalid_market", "Invalid resolved outcome")

    positions = db.scalars(select(BetPosition).where(BetPosition.bet_id == bet_id)).all()
    total_pool = bet_total_pool(bet)
    winning_pool = bet.pool_yes_tickets if outcome == "YES" else bet.pool_no_tickets
    if winning_pool > 0 and total_pool > 0:
        payouts_by_user: Dict[str, int] = {}
        for pos in positions:
            if pos.side != outcome:
                continue
            payout = int(round(pos.stake_tickets * total_pool / winning_pool))
            payouts_by_user[pos.user_id] = payouts_by_user.get(pos.user_id, 0) + payout

        for winner_user_id, payout in payouts_by_user.items():
            if payout <= 0:
                continue
            _apply_wallet_tx(
                db,
                user_id=winner_user_id,
                amount_tickets=payout,
                kind="BET_PAYOUT",
                ref_type="BET",
                ref_id=str(bet_id),
                idempotency_key=wallet_tx_key("BET_PAYOUT", bet_id, winner_user_id),
            )

    bet.status = "FINALIZED"
    bet.finalized_at = now_utc()
    db.add(bet)
    db.add(
        BetResolutionLog(
            bet_id=bet.id,
            actor_user_id=actor.id,
            action="finalize",
            outcome=outcome,
            notes="payout_locked",
        )
    )
    db.commit()
    return bet_out(bet)


def cancel_bet(db: Session, *, bet_id: int, actor: AppUser) -> Dict[str, Any]:
    from app.legacy.monolith import _apply_wallet_tx, _role_rank, resolve_event_role

    bet = db.execute(select(Bet).where(Bet.id == bet_id).with_for_update()).scalar_one_or_none()
    if not bet:
        raise polymarket_error(404, "invalid_market", "Bet not found")
    if bet.status == "CANCELLED":
        return bet_out(bet)
    if bet.status not in {"LIVE", "RESOLVED_PENDING"}:
        raise polymarket_error(409, "invalid_market", "Bet not live")

    is_admin = is_polymarket_admin(actor.id)
    if bet.scope == "EVENT" and bet.event_id is not None:
        role = resolve_event_role(db, actor.id, bet.event_id)
        if _role_rank(role) >= _role_rank("admin"):
            is_admin = True
    if not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    bet.status = "CANCELLED"
    bet.resolved_at = now_utc()
    bet.resolved_outcome = None
    db.add(bet)

    positions = db.scalars(select(BetPosition).where(BetPosition.bet_id == bet_id)).all()
    refunds_by_user: Dict[str, int] = {}
    for pos in positions:
        refunds_by_user[pos.user_id] = refunds_by_user.get(pos.user_id, 0) + pos.stake_tickets

    for user_id, refund in refunds_by_user.items():
        if refund <= 0:
            continue
        _apply_wallet_tx(
            db,
            user_id=user_id,
            amount_tickets=refund,
            kind="REFUND",
            ref_type="BET",
            ref_id=str(bet_id),
            idempotency_key=wallet_tx_key("BET_REFUND", bet_id, user_id),
        )

    db.add(
        BetResolutionLog(
            bet_id=bet.id,
            actor_user_id=actor.id,
            action="cancel",
            outcome=None,
            notes=None,
        )
    )
    db.commit()
    return bet_out(bet)


def list_bets(
    db: Session,
    *,
    scope: Optional[str],
    event_id: Optional[int],
    status: Optional[str],
    kind: Optional[str],
    limit: int,
    offset: int,
) -> list[Dict[str, Any]]:
    q = select(Bet)
    if scope:
        q = q.where(Bet.scope == ensure_bet_scope(scope))
    if event_id is not None:
        q = q.where(Bet.event_id == event_id)
    if status:
        status_norm = _normalize_upper(status)
        if status_norm not in {"LIVE", "RESOLVED", "RESOLVED_PENDING", "FINALIZED", "CANCELLED"}:
            raise HTTPException(status_code=422, detail="Invalid status")
        if status_norm == "RESOLVED":
            status_norm = "FINALIZED"
        q = q.where(Bet.status == status_norm)
    if kind:
        q = q.where(Bet.kind == ensure_bet_kind(kind))

    rows = db.scalars(q.order_by(Bet.created_at.desc()).limit(limit).offset(offset)).all()
    return [bet_out(row) for row in rows]


def create_bet(db: Session, *, payload, user: AppUser) -> Dict[str, Any]:
    from app.legacy.monolith import get_or_create_event_config, require_role_for_event

    scope = ensure_bet_scope(payload.scope)
    kind = ensure_bet_kind(payload.kind)
    if scope == "GLOBAL":
        if not polymarket_global_enabled() or not is_polymarket_admin(user.id):
            raise HTTPException(status_code=403, detail="Forbidden")
    if scope == "EVENT":
        if payload.event_id is None:
            raise HTTPException(status_code=422, detail="event_id required")
        event = db.get(Event, payload.event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        cfg = get_or_create_event_config(db, payload.event_id, commit=True)
        if not cfg.allow_user_bets:
            require_role_for_event(db, user.id, payload.event_id, "admin")

    resolver_user_id = payload.resolver_user_id
    if kind == "SUBJECTIVE" and not resolver_user_id:
        raise HTTPException(status_code=422, detail="resolver_user_id required")

    bet = Bet(
        scope=scope,
        event_id=payload.event_id if scope == "EVENT" else None,
        question=payload.question.strip(),
        kind=kind,
        status="LIVE",
        deadline_at=payload.deadline_at,
        resolver_user_id=resolver_user_id,
        rules_text=payload.rules_text,
        dispute_window_minutes=payload.dispute_window_minutes,
        created_by_user_id=user.id,
        created_at=now_utc(),
        resolved_outcome=None,
        pool_yes_tickets=0,
        pool_no_tickets=0,
    )
    db.add(bet)
    db.flush()
    db.add(
        BetResolutionLog(
            bet_id=bet.id,
            actor_user_id=user.id,
            action="create",
            outcome=None,
            notes=None,
        )
    )
    db.commit()
    db.refresh(bet)
    return bet_out(bet)


def get_bet_detail(db: Session, *, bet_id: int, authorization: Optional[str]) -> Dict[str, Any]:
    bet = db.get(Bet, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    data = bet_out(bet)
    positions_count = db.scalar(select(func.count()).select_from(BetPosition).where(BetPosition.bet_id == bet_id))

    user = optional_current_user(authorization, db)
    user_position = None
    if user:
        rows = db.scalars(select(BetPosition).where(BetPosition.bet_id == bet_id, BetPosition.user_id == user.id)).all()
        yes_total = sum(r.stake_tickets for r in rows if r.side == "YES")
        no_total = sum(r.stake_tickets for r in rows if r.side == "NO")
        total_pool = bet_total_pool(bet)
        payout_yes = ((yes_total * total_pool / bet.pool_yes_tickets) if bet.pool_yes_tickets > 0 and yes_total > 0 else 0)
        payout_no = ((no_total * total_pool / bet.pool_no_tickets) if bet.pool_no_tickets > 0 and no_total > 0 else 0)
        user_position = {
            "stake_yes": yes_total,
            "stake_no": no_total,
            "stake_total": yes_total + no_total,
            "payout_yes": payout_yes,
            "payout_no": payout_no,
        }

    return {**data, "positions_count": positions_count or 0, "user_position": user_position}


def get_bet_me(db: Session, *, bet_id: int, user: AppUser, include_wallet_balance: bool) -> Dict[str, Any]:
    from app.legacy.monolith import get_or_create_wallet

    bet = db.get(Bet, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")

    rows = db.scalars(select(BetPosition).where(BetPosition.bet_id == bet_id, BetPosition.user_id == user.id)).all()
    yes_total = sum(r.stake_tickets for r in rows if r.side == "YES")
    no_total = sum(r.stake_tickets for r in rows if r.side == "NO")
    total_pool = bet_total_pool(bet)

    payout_yes = ((yes_total * total_pool / bet.pool_yes_tickets) if bet.pool_yes_tickets > 0 and yes_total > 0 else 0)
    payout_no = ((no_total * total_pool / bet.pool_no_tickets) if bet.pool_no_tickets > 0 and no_total > 0 else 0)

    wallet_balance: Optional[int] = None
    if include_wallet_balance:
        wallet_balance = get_or_create_wallet(db, user.id).balance_tickets
        db.commit()

    return {
        "bet_id": bet_id,
        "user_id": user.id,
        "stake_yes": yes_total,
        "stake_no": no_total,
        "stake_total": yes_total + no_total,
        "payout_yes": payout_yes,
        "payout_no": payout_no,
        "wallet_balance_tickets": wallet_balance,
    }


def bet_timeline(db: Session, *, bet_id: int) -> list[Dict[str, Any]]:
    bet = db.get(Bet, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")

    positions = db.scalars(select(BetPosition).where(BetPosition.bet_id == bet_id).order_by(BetPosition.created_at.asc())).all()

    points: list[Dict[str, Any]] = []
    yes_pool = 0
    no_pool = 0
    for pos in positions:
        if pos.side == "YES":
            yes_pool += pos.stake_tickets
        else:
            no_pool += pos.stake_tickets
        total = yes_pool + no_pool
        pct_yes = yes_pool / total if total > 0 else 0.5
        points.append(
            {
                "timestamp": pos.created_at.isoformat() if pos.created_at else now_utc().isoformat(),
                "pct_yes": pct_yes,
                "total_pool_tickets": total,
            }
        )

    if len(points) > POLYMARKET_TIMELINE_MAX_POINTS:
        step = max(1, len(points) // POLYMARKET_TIMELINE_MAX_POINTS)
        trimmed = points[::step]
        if trimmed[-1] != points[-1]:
            trimmed.append(points[-1])
        points = trimmed

    return points


def create_dispute(db: Session, *, bet_id: int, user: AppUser, reason: str) -> Dict[str, Any]:
    bet = db.execute(select(Bet).where(Bet.id == bet_id).with_for_update()).scalar_one_or_none()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    if bet.status != "RESOLVED_PENDING":
        raise HTTPException(status_code=409, detail="Bet not pending resolution")
    if not bet.resolved_at:
        raise HTTPException(status_code=400, detail="Bet has no resolved_at")

    lock_at = bet.resolved_at + timedelta(minutes=int(bet.dispute_window_minutes or 0))
    if now_utc() >= lock_at:
        raise HTTPException(status_code=400, detail="Dispute window expired")

    try:
        db.add(BetDispute(bet_id=bet_id, user_id=user.id, reason=reason.strip(), created_at=now_utc()))
        db.flush()
    except IntegrityError:
        db.rollback()

    bet = db.execute(select(Bet).where(Bet.id == bet_id).with_for_update()).scalar_one_or_none()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    disputes_count = db.scalar(select(func.count()).select_from(BetDispute).where(BetDispute.bet_id == bet_id)) or 0
    db.add(
        BetResolutionLog(
            bet_id=bet.id,
            actor_user_id=user.id,
            action="dispute",
            outcome=bet.resolved_outcome,
            notes=reason.strip(),
        )
    )
    db.commit()
    return {"ok": True, "disputes_count": disputes_count, "status": bet.status}


def get_bet_logs(db: Session, *, bet_id: int) -> Dict[str, Any]:
    bet = db.get(Bet, bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")

    actions = db.scalars(
        select(BetResolutionLog).where(BetResolutionLog.bet_id == bet_id).order_by(BetResolutionLog.created_at.asc())
    ).all()
    disputes = db.scalars(select(BetDispute).where(BetDispute.bet_id == bet_id).order_by(BetDispute.created_at.asc())).all()

    positions = db.scalars(select(BetPosition).where(BetPosition.bet_id == bet_id)).all()
    positions_summary = {
        "positions_count": len(positions),
        "staked_yes": sum(pos.stake_tickets for pos in positions if pos.side == "YES"),
        "staked_no": sum(pos.stake_tickets for pos in positions if pos.side == "NO"),
        "total_pool_tickets": bet_total_pool(bet),
    }

    return {
        "bet": {
            "id": bet.id,
            "status": bet.status,
            "resolved_at": bet.resolved_at.isoformat() if bet.resolved_at else None,
            "finalized_at": bet.finalized_at.isoformat() if bet.finalized_at else None,
            "dispute_window_minutes": bet.dispute_window_minutes,
            "resolved_outcome": bet.resolved_outcome,
        },
        "actions": [
            {
                "id": row.id,
                "kind": row.action.upper(),
                "actor_user_id": row.actor_user_id,
                "payload": row.notes,
                "outcome": row.outcome,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in actions
        ],
        "disputes": [
            {
                "id": row.id,
                "bet_id": row.bet_id,
                "user_id": row.user_id,
                "reason": row.reason,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in disputes
        ],
        "positions_summary": positions_summary,
    }


def audit_polymarket(
    db: Session,
    *,
    action: str,
    user: Optional[AppUser],
    bet: Optional[Bet],
    payload: Dict[str, Any],
) -> None:
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_role="user",
        action=action,
        entity_type="polymarket",
        entity_id=str(bet.id) if bet else None,
        event_id=bet.event_id if bet else None,
        bar_id=None,
        payload=payload,
    )


def map_scope(scope: Optional[str]) -> Optional[str]:
    if scope is None:
        return None
    s = scope.strip().upper()
    if s in {"GLOBAL", "EVENT"}:
        return s
    raise polymarket_error(422, "invalid_market", "Invalid scope")


def map_status(status: Optional[str]) -> Optional[str]:
    if status is None:
        return None
    s = status.strip().lower()
    allowed = {"live", "resolved", "cancelled", "open"}
    if s not in allowed:
        raise polymarket_error(422, "invalid_market", "Invalid status")
    return s


def market_snapshot_for_user(db: Session, bet: Bet, user_id: Optional[str]) -> Dict[str, Any]:
    total = bet_total_pool(bet)
    yes_price = bet_pct_yes(bet)
    no_price = 1.0 - yes_price if total > 0 else 0.5
    my_yes = 0
    my_no = 0
    if user_id:
        rows = db.scalars(select(BetPosition).where(BetPosition.bet_id == bet.id, BetPosition.user_id == user_id)).all()
        my_yes = sum(r.stake_tickets for r in rows if r.side == "YES")
        my_no = sum(r.stake_tickets for r in rows if r.side == "NO")
    return {
        "id": bet.id,
        "question": bet.question,
        "scope": bet.scope.lower(),
        "event_id": bet.event_id,
        "status": ("resolved" if bet.status in {"FINALIZED", "RESOLVED_PENDING"} else bet.status.lower()),
        "yes_price": yes_price,
        "no_price": no_price,
        "volume": total,
        "liquidity": total,
        "closes_at": bet.deadline_at.isoformat() if bet.deadline_at else None,
        "resolves_at": bet.resolved_at.isoformat() if bet.resolved_at else None,
        "my_position_yes": my_yes,
        "my_position_no": my_no,
        "my_total": my_yes + my_no,
        "resolved_outcome": (bet.resolved_outcome or "").lower() or None,
    }


def list_markets_cursor(
    db: Session,
    *,
    scope: Optional[str],
    event_id: Optional[int],
    status: Optional[str],
    cursor: Optional[str],
    limit: int,
    user_id: Optional[str],
) -> Tuple[list[Dict[str, Any]], Optional[str]]:
    scope_norm = map_scope(scope)
    status_norm = map_status(status)
    after_ts, after_id = decode_cursor(cursor)

    q = select(Bet)
    if scope_norm:
        q = q.where(Bet.scope == scope_norm)
    if event_id is not None:
        q = q.where(Bet.event_id == event_id)
    if status_norm == "live":
        q = q.where(Bet.status == "LIVE")
    elif status_norm == "resolved":
        q = q.where(Bet.status.in_(["FINALIZED", "RESOLVED_PENDING"]))
    elif status_norm == "cancelled":
        q = q.where(Bet.status == "CANCELLED")

    if after_ts is not None and after_id is not None:
        q = q.where(or_(Bet.created_at < after_ts, (Bet.created_at == after_ts) & (Bet.id < after_id)))

    rows = db.scalars(q.order_by(Bet.created_at.desc(), Bet.id.desc()).limit(limit + 1)).all()
    page_rows = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page_rows:
        tail = page_rows[-1]
        next_cursor = encode_cursor(tail.created_at, tail.id)

    return [market_snapshot_for_user(db, row, user_id) for row in page_rows], next_cursor


def list_my_positions_cursor(
    db: Session,
    *,
    user_id: str,
    scope: Optional[str],
    event_id: Optional[int],
    status: Optional[str],
    cursor: Optional[str],
    limit: int,
) -> Tuple[list[Dict[str, Any]], Optional[str]]:
    scope_norm = map_scope(scope)
    status_norm = map_status(status)
    after_ts, after_id = decode_cursor(cursor)

    q = select(BetPosition, Bet).join(Bet, Bet.id == BetPosition.bet_id).where(BetPosition.user_id == user_id)
    if scope_norm:
        q = q.where(Bet.scope == scope_norm)
    if event_id is not None:
        q = q.where(Bet.event_id == event_id)
    if status_norm == "open":
        q = q.where(Bet.status == "LIVE")
    elif status_norm == "resolved":
        q = q.where(Bet.status.in_(["FINALIZED", "RESOLVED_PENDING", "CANCELLED"]))

    if after_ts is not None and after_id is not None:
        q = q.where(or_(BetPosition.created_at < after_ts, (BetPosition.created_at == after_ts) & (BetPosition.id < after_id)))

    rows = db.execute(q.order_by(BetPosition.created_at.desc(), BetPosition.id.desc()).limit(limit + 1)).all()
    page_rows = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page_rows:
        tail = page_rows[-1][0]
        next_cursor = encode_cursor(tail.created_at, tail.id)

    items = []
    for pos, bet in page_rows:
        mine = db.scalars(select(BetPosition).where(BetPosition.bet_id == bet.id, BetPosition.user_id == user_id)).all()
        yes_total = sum(p.stake_tickets for p in mine if p.side == "YES")
        no_total = sum(p.stake_tickets for p in mine if p.side == "NO")
        items.append(
            {
                "market_id": bet.id,
                "question": bet.question,
                "side_totals": {"yes": yes_total, "no": no_total},
                "avg_price": None,
                "pnl": None,
                "status": ("resolved" if bet.status in {"FINALIZED", "RESOLVED_PENDING"} else bet.status.lower()),
                "resolved_outcome": (bet.resolved_outcome or "").lower() or None,
            }
        )
    return items, next_cursor


def user_market_history(
    db: Session,
    *,
    market_id: int,
    user_id: str,
    cursor: Optional[str],
    limit: int,
) -> Tuple[list[Dict[str, Any]], Optional[str]]:
    after_ts, after_id = decode_cursor(cursor)
    q = select(BetPosition).where(BetPosition.bet_id == market_id, BetPosition.user_id == user_id)
    if after_ts is not None and after_id is not None:
        q = q.where(or_(BetPosition.created_at < after_ts, (BetPosition.created_at == after_ts) & (BetPosition.id < after_id)))
    rows = db.scalars(q.order_by(BetPosition.created_at.desc(), BetPosition.id.desc()).limit(limit + 1)).all()
    page_rows = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page_rows:
        tail = page_rows[-1]
        next_cursor = encode_cursor(tail.created_at, tail.id)
    items = [
        {
            "trade_id": row.id,
            "side": row.side.lower(),
            "amount_cents": row.stake_tickets,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in page_rows
    ]
    return items, next_cursor


def export_markets_csv(db: Session, *, scope: Optional[str], event_id: Optional[int], status: Optional[str]) -> str:
    markets, _ = list_markets_cursor(
        db,
        scope=scope,
        event_id=event_id,
        status=status,
        cursor=None,
        limit=1000,
        user_id=None,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "question", "scope", "event_id", "status", "yes_price", "no_price", "volume", "resolved_outcome"])
    for row in markets:
        writer.writerow([
            row["id"],
            row["question"],
            row["scope"],
            row["event_id"],
            row["status"],
            row["yes_price"],
            row["no_price"],
            row["volume"],
            row.get("resolved_outcome") or "",
        ])
    return output.getvalue()


def export_positions_csv(db: Session, *, user_id: Optional[str], scope: Optional[str], event_id: Optional[int]) -> str:
    q = select(BetPosition, Bet).join(Bet, Bet.id == BetPosition.bet_id)
    scope_norm = map_scope(scope)
    if scope_norm:
        q = q.where(Bet.scope == scope_norm)
    if event_id is not None:
        q = q.where(Bet.event_id == event_id)
    if user_id:
        q = q.where(BetPosition.user_id == user_id)
    rows = db.execute(q.order_by(BetPosition.created_at.desc())).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["position_id", "market_id", "question", "user_id", "side", "stake_tickets", "created_at"])
    for pos, bet in rows:
        writer.writerow([pos.id, bet.id, bet.question, pos.user_id, pos.side, pos.stake_tickets, pos.created_at.isoformat() if pos.created_at else ""])
    return output.getvalue()
