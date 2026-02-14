from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BattleCreateIn(BaseModel):
    event_id: Optional[int] = None
    bar_id: Optional[int] = None
    mode: str = Field(default="1v1")


class BattleJoinIn(BaseModel):
    battle_code: Optional[str] = None
    qr_token: Optional[str] = None


class BattleSubmitIn(BaseModel):
    scan_id: str
    points: int = 1
    target_user_id: Optional[str] = None


class BattleValidateIn(BaseModel):
    submit_id: int


class CheckinIn(BaseModel):
    drink_id: Optional[int] = None
    free_text_name: Optional[str] = None
    rating: Optional[int] = None
    comment: Optional[str] = None
    event_id: Optional[int] = None
    bar_id: Optional[int] = None


class WifiSetIn(BaseModel):
    bar_id: int
    event_id: Optional[int] = None
    ssid: str
    password: str
    note: Optional[str] = None


class BuddyStartIn(BaseModel):
    buddy_user_id: str
    expires_minutes: int = 60
    event_id: Optional[int] = None


class BuddyPingIn(BaseModel):
    session_id: int


class BuddyEndIn(BaseModel):
    session_id: int


class CursorPageOut(BaseModel):
    items: list
    next_cursor: Optional[str] = None


class AuditLogOut(BaseModel):
    id: int
    ts: datetime
    actor_partner_id: Optional[int] = None
    action: str
    event_id: Optional[int] = None
    bar_id: Optional[int] = None
    payload_json: dict
