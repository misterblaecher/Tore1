from __future__ import annotations

from datetime import datetime
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import EntryScanLog, EntryToken
from partner_auth import current_identity as current_partner_identity
from app.schemas.entry import (
    EntryScanIn,
    EntryScanLogOut,
    EntryScanLogPageOut,
    EntryScanOut,
    EntryTokenIssueIn,
    EntryTokenIssueOut,
    EntryTokenIssuedOut,
    EntryTokenRevokeIn,
    EntryTokenRevokeOut,
    EntryTokenStatsOut,
)
from app.services.audit_service import write_audit_log
from app.services.p3_common import ensure_event_action_allowed
from app.services.entry_service import (
    filter_entry_logs,
    get_owned_event_or_403,
    issue_tokens,
    require_partner_manager,
    require_partner_staff,
    revoke_tokens,
    scan_entry,
)

router = APIRouter()


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


@router.post("/entry/tokens/issue", response_model=EntryTokenIssueOut)
def issue_entry_tokens(
    payload: EntryTokenIssueIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_partner_manager(identity)
    event = get_owned_event_or_403(db, payload.event_id, identity["bar_id"])
    ensure_event_action_allowed(db, payload.event_id, "entry_enabled", write=True)
    issued = issue_tokens(
        db,
        event_id=payload.event_id,
        count=payload.count,
        expires_in_minutes=payload.expires_in_minutes,
        user_id=payload.user_id,
        metadata=payload.metadata,
    )
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="entry_token.issue",
        entity_type="event",
        entity_id=str(payload.event_id),
        event_id=payload.event_id,
        bar_id=event.bar_id,
        payload={"count": len(issued), "expires_in_minutes": payload.expires_in_minutes},
    )
    db.commit()
    return EntryTokenIssueOut(
        event_id=payload.event_id,
        issued=[
            EntryTokenIssuedOut(token_id=row.id, token=raw, expires_at=row.expires_at)
            for row, raw in issued
        ],
    )


@router.post("/entry/tokens/revoke", response_model=EntryTokenRevokeOut)
def revoke_entry_tokens(
    payload: EntryTokenRevokeIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_partner_manager(identity)
    event = get_owned_event_or_403(db, payload.event_id, identity["bar_id"])
    ensure_event_action_allowed(db, payload.event_id, "entry_enabled", write=True)
    revoked = revoke_tokens(db, event_id=payload.event_id, token_ids=payload.token_ids)
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="entry_token.revoke",
        entity_type="event",
        entity_id=str(payload.event_id),
        event_id=payload.event_id,
        bar_id=event.bar_id,
        payload={"token_ids": payload.token_ids, "revoked_count": revoked},
    )
    db.commit()
    return EntryTokenRevokeOut(event_id=payload.event_id, revoked_count=revoked)


@router.post("/entry/scan", response_model=EntryScanOut)
def entry_scan(
    payload: EntryScanIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_partner_staff(identity)
    event = get_owned_event_or_403(db, payload.event_id, identity["bar_id"])
    ensure_event_action_allowed(db, payload.event_id, "entry_enabled", write=True)
    log, idempotent = scan_entry(
        db,
        event_id=payload.event_id,
        token=payload.token,
        scan_id=payload.scan_id,
        actor_user_id=identity["user_id"],
    )
    if not idempotent:
        write_audit_log(
            db,
            actor_partner_id=identity["user_id"],
            actor_role=identity["role"],
            action="entry_token.use",
            entity_type="entry_token",
            entity_id=str(log.token_id) if log.token_id else None,
            event_id=payload.event_id,
            bar_id=event.bar_id,
            payload={"scan_id": payload.scan_id, "decision": log.decision, "reason": log.reason},
        )
        db.commit()
    return EntryScanOut(
        log_id=log.id,
        event_id=log.event_id,
        decision=log.decision,
        reason=log.reason,
        user_id=log.user_id,
        token_id=log.token_id,
        created_at=log.created_at,
        idempotent=idempotent,
    )


@router.get("/entry/tokens/stats", response_model=EntryTokenStatsOut)
def entry_token_stats(
    event_id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_partner_manager(identity)
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    ensure_event_action_allowed(db, event_id, "entry_enabled", write=False)

    rows = (
        db.query(EntryToken.status, func.count(EntryToken.id))
        .filter(EntryToken.event_id == event_id)
        .group_by(EntryToken.status)
        .all()
    )
    counts = {"ACTIVE": 0, "USED": 0, "EXPIRED": 0, "REVOKED": 0}
    counts.update({status: int(count or 0) for status, count in rows})

    recent = (
        db.query(EntryScanLog)
        .filter(EntryScanLog.event_id == event_id, EntryScanLog.decision == "ACCEPT")
        .order_by(EntryScanLog.created_at.desc(), EntryScanLog.id.desc())
        .limit(50)
        .all()
    )
    return EntryTokenStatsOut(
        event_id=event_id,
        counts=counts,
        recent_uses=[EntryScanLogOut(id=row.id, event_id=row.event_id, scan_id=row.scan_id, payload_raw=row.payload_raw, user_id=row.user_id, token_id=row.token_id, decision=row.decision, reason=row.reason, created_at=row.created_at) for row in recent],
    )


@router.get("/entry/logs", response_model=EntryScanLogPageOut)
def entry_logs(
    event_id: int,
    status: Optional[str] = Query(default=None),
    staff_id: Optional[int] = Query(default=None),
    after: Optional[datetime] = Query(default=None),
    before: Optional[datetime] = Query(default=None),
    search: Optional[str] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=300),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_partner_manager(identity)
    get_owned_event_or_403(db, event_id, identity["bar_id"])

    rows, next_cursor = filter_entry_logs(
        db,
        event_id=event_id,
        status=status,
        staff_id=staff_id,
        after=after,
        before=before,
        search=search,
        cursor=cursor,
        limit=limit,
    )
    return EntryScanLogPageOut(items=[EntryScanLogOut(id=r.id, event_id=r.event_id, scan_id=r.scan_id, payload_raw=r.payload_raw, user_id=r.user_id, token_id=r.token_id, decision=r.decision, reason=r.reason, created_at=r.created_at) for r in rows], next_cursor=next_cursor)
