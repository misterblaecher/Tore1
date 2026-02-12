from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import now_utc
from models import Battle, BattleJoin, Event
from app.schemas.battles import CreateBattleIn, JoinBattleIn, WinnerIn


def create_battle(db: Session, payload: CreateBattleIn) -> dict:
    from main import require_feature

    if payload.event_id is None:
        raise HTTPException(422, "event_id required")

    require_feature(db, payload.event_id, "battles_enabled")
    event = db.get(Event, payload.event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    battle = Battle(
        bar_id=event.bar_id,
        event_id=payload.event_id,
        title=payload.title,
        mode=payload.mode,
        is_active=True,
        created_at=now_utc(),
    )
    db.add(battle)
    db.commit()
    return {"id": battle.id, "join_code": str(battle.id)}


def join_battle(db: Session, payload: JoinBattleIn) -> dict:
    from main import require_feature

    try:
        battle_id = int(payload.join_code)
    except (TypeError, ValueError):
        raise HTTPException(404, "Battle not found")

    battle = db.get(Battle, battle_id)
    if not battle:
        raise HTTPException(404, "Battle not found")

    require_feature(db, battle.event_id, "battles_enabled")

    exists = db.scalar(
        select(BattleJoin).where(
            BattleJoin.battle_id == battle.id,
            BattleJoin.user_id == payload.user_id,
        )
    )
    if exists:
        return {"ok": True, "battle_id": battle.id}

    participant = BattleJoin(
        battle_id=battle.id,
        user_id=payload.user_id,
        joined_at=now_utc(),
    )
    db.add(participant)
    db.commit()
    return {"ok": True, "battle_id": battle.id}


def set_winner(db: Session, battle_id: int, payload: WinnerIn) -> dict:
    battle = db.get(Battle, battle_id)
    if not battle:
        raise HTTPException(404, "Battle not found")

    battle.is_active = False
    db.add(battle)
    db.commit()
    return {"ok": True, "winner_user_id": payload.winner_user_id}
