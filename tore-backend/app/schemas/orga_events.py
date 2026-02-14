from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EventTemplateOut(BaseModel):
    id: str
    name: str
    defaultModulesOn: dict[str, bool]
    defaultRules: dict[str, Any]
    durationPreset: str


class OrgaEventCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    venue: str = Field(min_length=2, max_length=180)
    startAt: datetime
    endAt: datetime
    timezone: str = Field(default="Europe/Brussels", min_length=2, max_length=64)
    modulesOn: dict[str, bool] = Field(default_factory=dict)
    rulesFlags: dict[str, Any] = Field(default_factory=dict)
    templateId: str | None = Field(default=None, max_length=64)


class OrgaEventOut(BaseModel):
    id: int
    name: str
    venue: str | None = None
    startAt: datetime
    endAt: datetime
    timezone: str
    eventState: str
    modulesOn: dict[str, bool]
    rulesFlags: dict[str, Any]
    createdBy: str | None = None
    lastStateUpdatedAt: datetime
    lastUpdatedAt: datetime


class QrPackItemOut(BaseModel):
    type: str
    payload: str
    expiresAt: datetime
    tokenId: str
    signature: str


class QrPackOut(BaseModel):
    eventId: int
    items: list[QrPackItemOut]
