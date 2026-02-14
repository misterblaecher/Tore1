from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class EntryTokenIssueIn(BaseModel):
    event_id: int
    count: int = Field(default=1, ge=1, le=500)
    expires_in_minutes: int = Field(default=240, ge=1, le=60 * 24 * 30)
    user_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntryTokenIssuedOut(BaseModel):
    token_id: int
    token: str
    expires_at: datetime


class EntryTokenIssueOut(BaseModel):
    event_id: int
    issued: list[EntryTokenIssuedOut]


class EntryTokenRevokeIn(BaseModel):
    event_id: int
    token_ids: list[int] = Field(min_length=1, max_length=500)


class EntryTokenRevokeOut(BaseModel):
    event_id: int
    revoked_count: int


class EntryScanIn(BaseModel):
    event_id: int
    token: str = Field(min_length=1, max_length=4096)
    scan_id: str = Field(min_length=3, max_length=120)


class EntryScanOut(BaseModel):
    log_id: int
    event_id: int
    decision: str
    reason: str
    user_id: Optional[str] = None
    token_id: Optional[int] = None
    created_at: datetime
    idempotent: bool = False


class EntryScanLogOut(BaseModel):
    id: int
    event_id: int
    scan_id: Optional[str] = None
    payload_raw: str
    user_id: Optional[str] = None
    token_id: Optional[int] = None
    decision: str
    reason: str
    created_at: datetime


class EntryScanLogPageOut(BaseModel):
    items: list[EntryScanLogOut]
    next_cursor: Optional[str] = None


class EntryTokenStatsOut(BaseModel):
    event_id: int
    counts: dict[str, int]
    recent_uses: list[EntryScanLogOut]
