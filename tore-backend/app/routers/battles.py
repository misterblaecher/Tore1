from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.routers.wallet import get_current_user
from app.services.audit_service import write_audit_log
from app.services.authz_service import ensure_partner_role
from app.services.idempotency_service import ensure_idempotency_key
from app.services.p3_common import effective_module_state, get_event_runtime_state
from db import now_utc
from models import (
    AppUser,
    AppUserPrivacySetting,
    Event,
    EventBattleIdempotency,
    EventBattleRound,
    EventBattleScore,
    EventBattleVote,
)
from partner_auth import current_identity as current_partner_identity

router = APIRouter()


class RoundStartIn(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    kind: str = Field(default="PARTICIPATION")
    durationSeconds: int = Field(ge=10, le=1800)
    optionALabel: Optional[str] = Field(default=None, max_length=120)
    optionBLabel: Optional[str] = Field(default=None, max_length=120)


class VoteIn(BaseModel):
    roundId: int
    choice: str


class RoundLockIn(BaseModel):
    roundId: int


class RoundForceWinnerIn(BaseModel):
    roundId: int
    winner: str
    reason: str = Field(min_length=3, max_length=240)


class BattleClearIn(BaseModel):
    reason: str = Field(min_length=3, max_length=240)


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


def _battles_guard(db: Session, event_id: int, *, write: bool) -> None:
    state, reason = effective_module_state(db, event_id, "battles_enabled")
    if state == "OFF":
        raise HTTPException(status_code=404, detail={"reason": "MODULE_OFF", "message": "Battles module off"})
    if write:
        runtime = get_event_runtime_state(db, event_id)
        if runtime in {"PAUSE", "MENU_ONLY", "DEGRADED", "FROZEN", "CLOSED"}:
            raise HTTPException(status_code=423, detail={"reason": f"event_{runtime.lower()}", "message": "Battle write blocked"})
        if state == "READ_ONLY":
            raise HTTPException(status_code=423, detail={"reason": reason or "read_only", "message": "Battle write blocked"})


def _event_for_partner(db: Session, event_id: int, identity: dict) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail={"reason": "event_not_found"})
    if event.bar_id != identity.get("bar_id"):
        raise HTTPException(status_code=403, detail={"reason": "forbidden"})
    return event


def _choice_counts(db: Session, round_id: int) -> tuple[int, int, int]:
    rows = db.query(EventBattleVote.choice, func.count(EventBattleVote.id)).filter(EventBattleVote.round_id == round_id).group_by(EventBattleVote.choice).all()
    mapping = {choice: int(count) for choice, count in rows}
    return mapping.get("A", 0), mapping.get("B", 0), mapping.get("PARTICIPATE", 0)


def _score_row(db: Session, event_id: int, user_id: str) -> EventBattleScore:
    row = db.query(EventBattleScore).filter(EventBattleScore.event_id == event_id, EventBattleScore.user_id == user_id).first()
    if row:
        return row
    row = EventBattleScore(event_id=event_id, user_id=user_id, score=0, last_updated_at=now_utc())
    db.add(row)
    db.flush()
    return row


def _private(db: Session, user_id: str) -> bool:
    row = db.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id == user_id).first()
    return bool(row and (row.visibility or "").lower() == "private")


def _anon(user_id: str) -> str:
    return f"Anonymous-{hashlib.sha1(user_id.encode('utf-8')).hexdigest()[:4]}"


def _upsert_idem(db: Session, *, event_id: int, action: str, actor_id: str, key: str, response: dict) -> None:
    db.add(EventBattleIdempotency(event_id=event_id, action_type=action, actor_id=actor_id, idempotency_key=key, response_json=response))


def _load_idem(db: Session, *, event_id: int, action: str, actor_id: str, key: str) -> Optional[dict]:
    row = db.query(EventBattleIdempotency).filter(
        EventBattleIdempotency.event_id == event_id,
        EventBattleIdempotency.action_type == action,
        EventBattleIdempotency.actor_id == actor_id,
        EventBattleIdempotency.idempotency_key == key,
    ).first()
    return row.response_json if row else None


def _apply_round_scores(db: Session, round_row: EventBattleRound) -> None:
    votes = db.query(EventBattleVote).filter(EventBattleVote.round_id == round_row.id).all()
    for vote in votes:
        points = 1
        if round_row.kind == "DUEL":
            if round_row.winner in {"A", "B"} and vote.choice == round_row.winner:
                points += 3
            elif vote.choice in {"A", "B"} and round_row.winner in {"A", "B"}:
                points += 0
        score_row = _score_row(db, round_row.event_id, vote.user_id)
        score_row.score = int(score_row.score or 0) + points
        score_row.last_updated_at = now_utc()
        db.add(score_row)


@router.get("/events/{event_id}/battles/state")
def battles_state(event_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _battles_guard(db, event_id, write=False)
    now = now_utc()
    current = db.query(EventBattleRound).filter(EventBattleRound.event_id == event_id).order_by(EventBattleRound.id.desc()).first()
    if not current:
        return {"serverTime": now.isoformat(), "round": None, "myChoice": None, "counts": {"A": 0, "B": 0, "PARTICIPATE": 0}, "status": "IDLE"}

    counts_a, counts_b, counts_p = _choice_counts(db, current.id)
    my_vote = db.query(EventBattleVote).filter(EventBattleVote.round_id == current.id, EventBattleVote.user_id == user.id).first()
    return {
        "serverTime": now.isoformat(),
        "round": {
            "id": current.id,
            "title": current.title,
            "kind": current.kind,
            "status": current.status,
            "optionALabel": current.optionA_label,
            "optionBLabel": current.optionB_label,
            "endsAt": current.ends_at.isoformat() if current.ends_at else None,
            "winner": current.winner,
        },
        "myChoice": my_vote.choice if my_vote else None,
        "counts": {"A": counts_a, "B": counts_b, "PARTICIPATE": counts_p},
        "status": current.status,
        "endsAt": current.ends_at.isoformat() if current.ends_at else None,
    }


@router.post("/events/{event_id}/battles/vote")
def battle_vote(
    event_id: int,
    payload: VoteIn,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    _battles_guard(db, event_id, write=True)
    key = ensure_idempotency_key(idempotency_key)
    actor = user.id
    existing = _load_idem(db, event_id=event_id, action="vote", actor_id=actor, key=key)
    if existing:
        return existing
    round_row = db.get(EventBattleRound, payload.roundId)
    if not round_row or round_row.event_id != event_id:
        raise HTTPException(status_code=404, detail={"reason": "round_not_found"})
    now = now_utc()
    if round_row.status != "OPEN" or now >= round_row.ends_at:
        raise HTTPException(status_code=409, detail={"reason": "round_not_open"})
    choice = (payload.choice or "").upper()
    allowed = {"PARTICIPATE"} if round_row.kind != "DUEL" else {"A", "B"}
    if choice not in allowed:
        raise HTTPException(status_code=400, detail={"reason": "invalid_choice"})

    vote = db.query(EventBattleVote).filter(EventBattleVote.round_id == round_row.id, EventBattleVote.user_id == actor).first()
    if vote:
        vote.choice = choice
    else:
        db.add(EventBattleVote(round_id=round_row.id, user_id=actor, choice=choice, created_at=now))
    db.flush()
    counts_a, counts_b, counts_p = _choice_counts(db, round_row.id)
    response = {"ok": True, "myChoice": choice, "countsA": counts_a, "countsB": counts_b, "countsParticipate": counts_p, "status": round_row.status}
    _upsert_idem(db, event_id=event_id, action="vote", actor_id=actor, key=key, response=response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=actor, actor_role="app_user", action="battle.vote", entity_type="event_battle_round", entity_id=str(round_row.id), event_id=event_id, bar_id=None, payload={"choice": choice}, idempotency_key=key)
    db.commit()
    return response


@router.get("/events/{event_id}/battles/leaderboard")
def battles_leaderboard(event_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _battles_guard(db, event_id, write=False)
    rows = db.query(EventBattleScore).filter(EventBattleScore.event_id == event_id).order_by(EventBattleScore.score.desc(), EventBattleScore.last_updated_at.asc(), EventBattleScore.user_id.asc()).all()
    out = []
    me = {"rank": None, "userId": user.id, "name": "Me", "score": 0}
    for idx, row in enumerate(rows, start=1):
        name_row = db.get(AppUser, row.user_id)
        name = (name_row.display_name if name_row else row.user_id) if (not _private(db, row.user_id) or row.user_id == user.id) else _anon(row.user_id)
        item = {"rank": idx, "userId": row.user_id, "name": name, "score": int(row.score or 0), "private": bool(_private(db, row.user_id))}
        out.append(item)
        if row.user_id == user.id:
            me = {"rank": idx, "userId": row.user_id, "name": name, "score": int(row.score or 0)}
    return {"top3": out[:3], "list": out, "me": me, "rulesText": "+1 participation, +2 correct winner, +1 winning side bonus", "ducDeLAffond": out[0] if out else None}


def _require_orga(identity=Depends(current_partner_identity)):
    ensure_partner_role(identity, {"manager", "owner"})
    return identity


@router.post("/partner/portal/orga/events/{event_id}/battles/rounds/start")
def start_round(event_id: int, payload: RoundStartIn, identity=Depends(_require_orga), db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    _event_for_partner(db, event_id, identity)
    _battles_guard(db, event_id, write=True)
    key = ensure_idempotency_key(idempotency_key)
    actor = str(identity.get("user_id"))
    existing = _load_idem(db, event_id=event_id, action="start", actor_id=actor, key=key)
    if existing:
        return existing

    open_rounds = db.query(EventBattleRound).filter(EventBattleRound.event_id == event_id, EventBattleRound.status == "OPEN").all()
    for row in open_rounds:
        row.status = "LOCKED"
        row.locked_at = now_utc()
        db.add(row)

    now = now_utc()
    kind = payload.kind.upper()
    if kind not in {"PARTICIPATION", "DUEL"}:
        raise HTTPException(status_code=400, detail={"reason": "invalid_kind"})
    round_row = EventBattleRound(
        event_id=event_id,
        title=payload.title,
        kind=kind,
        optionA_label=payload.optionALabel if kind == "DUEL" else None,
        optionB_label=payload.optionBLabel if kind == "DUEL" else None,
        status="OPEN",
        starts_at=now,
        ends_at=now + timedelta(seconds=payload.durationSeconds),
        created_by=actor,
        winner="NONE",
    )
    db.add(round_row)
    db.flush()
    response = {"ok": True, "roundId": round_row.id, "status": round_row.status, "endsAt": round_row.ends_at.isoformat()}
    _upsert_idem(db, event_id=event_id, action="start", actor_id=actor, key=key, response=response)
    write_audit_log(db, actor_partner_id=identity.get("user_id"), actor_role=identity.get("role"), action="orga.battles.round.start", entity_type="event_battle_round", entity_id=str(round_row.id), event_id=event_id, bar_id=identity.get("bar_id"), payload={"kind": kind, "title": payload.title}, idempotency_key=key)
    db.commit()
    return response


def _lock_round(db: Session, round_row: EventBattleRound) -> dict:
    counts_a, counts_b, counts_p = _choice_counts(db, round_row.id)
    round_row.status = "LOCKED"
    round_row.locked_at = now_utc()
    round_row.winner_count_a = counts_a
    round_row.winner_count_b = counts_b
    if round_row.kind == "DUEL":
        round_row.winner = "A" if counts_a > counts_b else "B" if counts_b > counts_a else "NONE"
    else:
        round_row.winner = "NONE"
    db.add(round_row)
    _apply_round_scores(db, round_row)
    return {"ok": True, "roundId": round_row.id, "status": round_row.status, "winner": round_row.winner, "countsA": counts_a, "countsB": counts_b, "countsParticipate": counts_p}


@router.post("/partner/portal/orga/events/{event_id}/battles/rounds/lock")
def lock_round(event_id: int, payload: RoundLockIn, identity=Depends(_require_orga), db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    _event_for_partner(db, event_id, identity)
    _battles_guard(db, event_id, write=True)
    key = ensure_idempotency_key(idempotency_key)
    actor = str(identity.get("user_id"))
    existing = _load_idem(db, event_id=event_id, action="lock", actor_id=actor, key=key)
    if existing:
        return existing
    round_row = db.get(EventBattleRound, payload.roundId)
    if not round_row or round_row.event_id != event_id:
        raise HTTPException(status_code=404, detail={"reason": "round_not_found"})
    response = _lock_round(db, round_row)
    _upsert_idem(db, event_id=event_id, action="lock", actor_id=actor, key=key, response=response)
    write_audit_log(db, actor_partner_id=identity.get("user_id"), actor_role=identity.get("role"), action="orga.battles.round.lock", entity_type="event_battle_round", entity_id=str(round_row.id), event_id=event_id, bar_id=identity.get("bar_id"), payload={"winner": round_row.winner}, idempotency_key=key)
    db.commit()
    return response


@router.post("/partner/portal/orga/events/{event_id}/battles/rounds/force_winner")
def force_winner(event_id: int, payload: RoundForceWinnerIn, identity=Depends(_require_orga), db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    _event_for_partner(db, event_id, identity)
    _battles_guard(db, event_id, write=True)
    key = ensure_idempotency_key(idempotency_key)
    actor = str(identity.get("user_id"))
    existing = _load_idem(db, event_id=event_id, action="force_winner", actor_id=actor, key=key)
    if existing:
        return existing

    round_row = db.get(EventBattleRound, payload.roundId)
    if not round_row or round_row.event_id != event_id:
        raise HTTPException(status_code=404, detail={"reason": "round_not_found"})
    winner = payload.winner.upper()
    if winner not in {"A", "B", "NONE"}:
        raise HTTPException(status_code=400, detail={"reason": "invalid_winner"})
    if round_row.status != "LOCKED":
        _lock_round(db, round_row)
    round_row.winner = winner
    db.add(round_row)
    response = {"ok": True, "roundId": round_row.id, "winner": round_row.winner, "status": round_row.status}
    _upsert_idem(db, event_id=event_id, action="force_winner", actor_id=actor, key=key, response=response)
    write_audit_log(db, actor_partner_id=identity.get("user_id"), actor_role=identity.get("role"), action="orga.battles.round.force_winner", entity_type="event_battle_round", entity_id=str(round_row.id), event_id=event_id, bar_id=identity.get("bar_id"), payload={"winner": winner, "reason": payload.reason}, idempotency_key=key)
    db.commit()
    return response


@router.get("/partner/portal/orga/events/{event_id}/battles/history")
def battles_history(event_id: int, limit: int = Query(default=20, ge=1, le=100), identity=Depends(_require_orga), db: Session = Depends(get_db)):
    _event_for_partner(db, event_id, identity)
    _battles_guard(db, event_id, write=False)
    rounds = db.query(EventBattleRound).filter(EventBattleRound.event_id == event_id).order_by(EventBattleRound.id.desc()).limit(limit).all()
    return [{"id": r.id, "title": r.title, "kind": r.kind, "status": r.status, "winner": r.winner, "countsA": r.winner_count_a, "countsB": r.winner_count_b, "endsAt": r.ends_at.isoformat() if r.ends_at else None} for r in rounds]


@router.post("/partner/portal/orga/events/{event_id}/battles/clear")
def clear_battles(event_id: int, payload: BattleClearIn, identity=Depends(_require_orga), db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    _event_for_partner(db, event_id, identity)
    _battles_guard(db, event_id, write=True)
    key = ensure_idempotency_key(idempotency_key)
    actor = str(identity.get("user_id"))
    existing = _load_idem(db, event_id=event_id, action="clear", actor_id=actor, key=key)
    if existing:
        return existing

    current = db.query(EventBattleRound).filter(EventBattleRound.event_id == event_id).order_by(EventBattleRound.id.desc()).first()
    if current:
        db.query(EventBattleVote).filter(EventBattleVote.round_id == current.id).delete(synchronize_session=False)
        current.status = "IDLE"
        db.add(current)
    response = {"ok": True, "roundId": current.id if current else None, "status": current.status if current else "IDLE"}
    _upsert_idem(db, event_id=event_id, action="clear", actor_id=actor, key=key, response=response)
    write_audit_log(db, actor_partner_id=identity.get("user_id"), actor_role=identity.get("role"), action="orga.battles.clear", entity_type="event_battles", entity_id=str(event_id), event_id=event_id, bar_id=identity.get("bar_id"), payload={"reason": payload.reason}, idempotency_key=key)
    db.commit()
    return response
