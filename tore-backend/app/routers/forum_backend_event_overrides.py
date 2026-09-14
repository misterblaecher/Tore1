"""Final event-lifecycle compatibility overrides for Forum v2."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from models import AppUser
from app.legacy.monolith import get_current_user, get_db
from app.schemas.forum_backend import EventTransitionIn
from app.routers.forum_backend import _ctx, _event_scoped, _idem, _organization, _save_idem
from app.services.forum_domain import EventLifecycleService


router = APIRouter(prefix="/forum/v2", tags=["forum-v2"])


@router.post("/structures/{slug}/events/{event_id}/transition")
def transition_event(
    slug: str,
    event_id: int,
    payload: EventTransitionIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transition an event while keeping public publication state coherent.

    ARCHIVED is intentionally not publicly published: both the public event list
    and the public stats-summary endpoint already require publication_status to
    be PUBLISHED. Clearing that status here prevents archived events from
    remaining discoverable through either public surface.
    """
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "events.publish")
    event = _event_scoped(db, org.id, event_id)
    action = f"forum_v2_event_transition:{org.id}:{event.id}:{payload.target}"
    key, previous = _idem(db, user, action, idempotency_key)
    if previous:
        return previous

    lifecycle = EventLifecycleService.transition(db, ctx=ctx, event=event, target=payload.target)
    if lifecycle.status == "ARCHIVED":
        event.publication_status = "ARCHIVED"

    response = {"eventId": event.id, "status": lifecycle.status}
    _save_idem(db, user, action, key, response)
    db.commit()
    return response
