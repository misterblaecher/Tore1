from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.battles import CreateBattleIn, JoinBattleIn, WinnerIn
from app.services.battles_service import create_battle, join_battle, set_winner

router = APIRouter()


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


@router.post("/battles")
def create_battle_route(payload: CreateBattleIn, db: Session = Depends(get_db)):
    return create_battle(db, payload)


@router.post("/battles/join")
def join_battle_route(payload: JoinBattleIn, db: Session = Depends(get_db)):
    return join_battle(db, payload)


@router.post("/battles/{battle_id}/winner")
def set_winner_route(battle_id: int, payload: WinnerIn, db: Session = Depends(get_db)):
    return set_winner(db, battle_id, payload)
