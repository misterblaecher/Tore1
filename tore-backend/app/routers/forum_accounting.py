"""Treasury-only accounting reads for the Structures Forum.

Operational attendance statistics stay on the existing ``/stats`` surface.
This router deliberately exposes financial values through a separate endpoint
which requires a treasury-level server-side role.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import AppUser, Event, EventCost, Order
from app.legacy.monolith import get_current_user, get_db
from app.routers.forum import _require_role, _structure_or_404


router = APIRouter(prefix="/forum", tags=["forum-accounting"])


def _event_accounting(db: Session, event: Event) -> dict:
    revenue = int(db.scalar(
        select(func.coalesce(func.sum(Order.total_cents), 0)).where(Order.event_id == event.id)
    ) or 0)
    costs = int(db.scalar(
        select(func.coalesce(func.sum(EventCost.amount_cents), 0)).where(EventCost.event_id == event.id)
    ) or 0)
    return {
        "event": {
            "id": event.id,
            "name": event.name,
            "startsAt": event.starts_at.isoformat() if event.starts_at else None,
            "endsAt": event.ends_at.isoformat() if event.ends_at else None,
            "venue": event.venue,
        },
        "revenueCents": revenue,
        "costsCents": costs,
        "resultCents": revenue - costs,
    }


@router.get("/structures/{slug}/accounting-summary")
def get_accounting_summary(
    slug: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    membership = _require_role(db, org.id, user, "TREASURER")
    events = db.query(Event).filter(
        Event.host_type == "orga",
        Event.host_id == str(org.id),
    ).order_by(Event.starts_at.desc(), Event.id.desc()).limit(24).all()
    rows = [_event_accounting(db, event) for event in events]
    totals = {
        "revenueCents": sum(row["revenueCents"] for row in rows),
        "costsCents": sum(row["costsCents"] for row in rows),
        "resultCents": sum(row["resultCents"] for row in rows),
    }
    return {
        "role": membership.role,
        "currency": "EUR",
        "privateByDefault": True,
        "latest": rows[0] if rows else None,
        "history": rows,
        "totals": totals,
    }
