from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EntryScanIn(BaseModel):
    event_id: int
    raw_payload: str = Field(min_length=1, max_length=4096)
    scan_id: Optional[str] = Field(default=None, max_length=120)


class EntryScanOut(BaseModel):
    log_id: int
    event_id: int
    decision: str
    reason: str
    user_id: Optional[str] = None
    created_at: datetime
    idempotent: bool = False


class EntryScanLogOut(BaseModel):
    id: int
    event_id: int
    scan_id: Optional[str] = None
    payload_raw: str
    user_id: Optional[str] = None
    decision: str
    reason: str
    created_at: datetime
