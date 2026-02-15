from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProfitabilityCostsOut(BaseModel):
    costsTickets: int = 0
    notes: Optional[str] = None
    breakdown: dict = Field(default_factory=dict)
    updatedBy: Optional[str] = None
    updatedAt: Optional[datetime] = None


class ProfitabilityOut(BaseModel):
    ordersCount: int
    itemsCount: int
    grossRevenueTickets: int
    grossRevenueEuro: Optional[float] = None
    avgOrderValueTickets: float
    lastUpdatedAt: datetime
    costs: ProfitabilityCostsOut
    netEstimateTickets: int


class ProfitabilityCostsIn(BaseModel):
    costsTickets: int = Field(ge=0)
    notes: Optional[str] = Field(default=None, max_length=2000)
    breakdown: Optional[dict] = None
