from __future__ import annotations

from typing import Iterator, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from models import EntryScanLog
from partner_auth import current_identity as current_partner_identity
from app.schemas.entry import EntryScanIn, EntryScanLogOut, EntryScanOut
from app.services.entry_service import (
    get_owned_event_or_403,
    require_partner_manager,
    require_partner_staff,
    scan_entry,
)

router = APIRouter()


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


@router.post("/entry/scan", response_model=EntryScanOut)
def entry_scan(
    payload: EntryScanIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_partner_staff(identity)
    get_owned_event_or_403(db, payload.event_id, identity["bar_id"])
    log, idempotent = scan_entry(
        db,
        event_id=payload.event_id,
        raw_payload=payload.raw_payload,
        scan_id=payload.scan_id,
        actor_user_id=identity["user_id"],
    )
    return EntryScanOut(
        log_id=log.id,
        event_id=log.event_id,
        decision=log.decision,
        reason=log.reason,
        user_id=log.user_id,
        created_at=log.created_at,
        idempotent=idempotent,
    )


@router.get("/entry/logs", response_model=List[EntryScanLogOut])
def entry_logs(
    event_id: int,
    decision: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=300),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_partner_manager(identity)
    get_owned_event_or_403(db, event_id, identity["bar_id"])

    q = db.query(EntryScanLog).filter(EntryScanLog.event_id == event_id)
    if decision:
        q = q.filter(EntryScanLog.decision == decision.upper())
    rows = q.order_by(EntryScanLog.created_at.desc()).limit(limit).all()
    return rows
