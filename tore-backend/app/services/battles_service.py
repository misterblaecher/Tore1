from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import now_utc
from models import Battle, BattleParticipant
from app.schemas.battles import CreateBattleIn, JoinBattleIn, WinnerIn


def create_battle(db: Session, payload: CreateBattleIn) -> dict:
    from main import random_code, require_feature

    if payload.event_id:
        require_feature(db, payload.event_id, "battles_enabled")

    battle = Battle(
        event_id=payload.event_id,
        created_by_user_id=payload.user_id,
        title=payload.title,
        mode=payload.mode,
        join_code=random_code(6),
        created_at=now_utc(),
    )
    db.add(battle)
    db.commit()
    return {"id": battle.id, "join_code": battle.join_code}


def join_battle(db: Session, payload: JoinBattleIn) -> dict:
    from main import require_feature

    battle = db.scalar(select(Battle).where(Battle.join_code == payload.join_code))
    if not battle:
        raise HTTPException(404, "Battle not found")

    if battle.event_id:
        require_feature(db, battle.event_id, "battles_enabled")

    exists = db.scalar(
        select(BattleParticipant).where(
            BattleParticipant.battle_id == battle.id,
            BattleParticipant.user_id == payload.user_id,
        )
    )
    if exists:
        return {"ok": True, "battle_id": battle.id}

    participant = BattleParticipant(
        battle_id=battle.id,
        user_id=payload.user_id,
        display_name=payload.display_name,
        joined_at=now_utc(),
    )
    db.add(participant)
    db.commit()
    return {"ok": True, "battle_id": battle.id}


def set_winner(db: Session, battle_id: int, payload: WinnerIn) -> dict:
    battle = db.get(Battle, battle_id)
    if not battle:
        raise HTTPException(404, "Battle not found")

    battle.winner_user_id = payload.winner_user_id
    battle.ended_at = now_utc()
    db.add(battle)
    db.commit()
    return {"ok": True}
