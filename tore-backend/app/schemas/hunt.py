from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class HuntCreateIn(BaseModel):
    event_id: int
    name: str = Field(min_length=1, max_length=180)
    reward_tickets: int = Field(default=0, ge=0, le=1_000_000)


class HuntPatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=180)
    is_active: Optional[bool] = None
    reward_tickets: Optional[int] = Field(default=None, ge=0, le=1_000_000)


class HuntPointCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    hint: Optional[str] = None
    sort_order: int = 0


class HuntPointPatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=180)
    hint: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class HuntPointOut(BaseModel):
    id: int
    hunt_id: int
    name: str
    hint: Optional[str] = None
    sort_order: int
    is_active: bool
    secret_code: str
    qr_payload: str
    route_front: str


class HuntOut(BaseModel):
    id: int
    bar_id: int
    event_id: int
    name: str
    is_active: bool
    reward_tickets: int
    created_at: datetime


class HuntPointPublicOut(BaseModel):
    id: int
    name: str
    hint: Optional[str] = None
    sort_order: int
    is_active: bool
    scanned: bool


class HuntEventOut(BaseModel):
    hunt: HuntOut
    points: List[HuntPointPublicOut]
    completion: float
    completed: bool
    reward_granted: bool


class HuntScanIn(BaseModel):
    event_id: int
    code: str = Field(min_length=3, max_length=120)
    device_id: Optional[str] = Field(default=None, max_length=120)
    idempotency_key: Optional[str] = Field(default=None, max_length=120)


class HuntScanOut(BaseModel):
    hunt_id: int
    point_id: int
    already_scanned: bool
    completion: float
    completed: bool
    reward_granted: bool
    reward_tickets: int


class HuntStatsPointOut(BaseModel):
    point_id: int
    name: str
    scans: int


class HuntStatsOut(BaseModel):
    participants: int
    scans_total: int
    completion_count: int
    top_points: List[HuntStatsPointOut]
