from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CreateBattleIn(BaseModel):
    user_id: str
    title: str = "Battle"
    mode: str = "1v1"
    event_id: Optional[int] = None


class JoinBattleIn(BaseModel):
    user_id: str
    join_code: str
    display_name: str = "Player"


class WinnerIn(BaseModel):
    user_id: str
    winner_user_id: str
