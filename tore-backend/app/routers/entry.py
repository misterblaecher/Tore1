from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import EntryScanLog, EntryToken
from partner_auth import current_identity as current_partner_identity
from app.schemas.entry import (
    EntryScanIn,
    EntryScanLogOut,
    EntryScanLogPageOut,
    EntryScanOut,
    EntryStatsOut,
    EntryTokenIssueIn,
    EntryTokenIssueOut,
    EntryTokenIssuedOut,
    EntryTokenRevokeIn,
    EntryTokenRevokeOut,
    EntryTokenStatsOut,
)
from app.services.audit_service import write_audit_log
from app.services.authz_service import ensure_partner_role
from app.services.rate_limit_service import enforce_rate_limit
from app.services.p3_common import effective_module_state, ensure_event_action_allowed, get_event_runtime_state
from app.services.entry_service import (
    accepted_count,
    accepted_last_10_min,
    create_denied_scan_log,
    filter_entry_logs,
    get_owned_event_or_403,
    issue_tokens,
    revoke_tokens,
    scan_entry,
)

router = APIRouter()


def get_db() -> Iterator[Session]:
    from app.legacy.monolith import get_db as _get_db

    yield from _get_db()


def _scan_status_from_log(log: EntryScanLog, *, idempotent: bool) -> str:
    if idempotent or log.reason == "already_used":
        return "duplicate"
    if log.decision == "ACCEPT":
        return "accepted"
    return "denied"


def _entry_log_out(row: EntryScanLog) -> EntryScanLogOut:
    return EntryScanLogOut(
        id=row.id,
        event_id=row.event_id,
        scan_id=row.scan_id,
        payload_raw=row.payload_raw,
        user_id=row.user_id,
        token_id=row.token_id,
        decision=row.decision,
        reason=row.reason,
        created_at=row.created_at,
        staff_id=row.created_by_user_id,
    )


@router.post("/entry/tokens/issue", response_model=EntryTokenIssueOut)
def issue_entry_tokens(
    payload: EntryTokenIssueIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager"})
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
    ensure_partner_role(identity, {"manager"})
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
    request: Request,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager", "bartender"})
    enforce_rate_limit("entry_scan", str(identity.get("user_id") or (request.client.host if request.client else "anon")))
    event = get_owned_event_or_403(db, payload.event_id, identity["bar_id"])

    blocked_reason = None
    try:
        ensure_event_action_allowed(db, payload.event_id, "entry_enabled", write=True)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        blocked_reason = str(detail.get("reason") or "event_blocked")

    if blocked_reason is not None:
        log = create_denied_scan_log(
            db,
            event_id=payload.event_id,
            token=payload.token,
            scan_id=payload.scan_id,
            actor_user_id=identity["user_id"],
            reason=blocked_reason,
        )
        status_label = _scan_status_from_log(log, idempotent=False)
        write_audit_log(
            db,
            actor_partner_id=identity["user_id"],
            actor_role=identity["role"],
            action="entry.scan",
            entity_type="entry_scan_log",
            entity_id=str(log.id),
            event_id=payload.event_id,
            bar_id=event.bar_id,
            payload={"scan_id": payload.scan_id, "status": status_label, "reason": log.reason},
        )
        db.commit()
        total = accepted_count(db, payload.event_id)
        return EntryScanOut(
            log_id=log.id,
            event_id=log.event_id,
            decision=log.decision,
            reason=log.reason,
            user_id=log.user_id,
            token_id=log.token_id,
            created_at=log.created_at,
            idempotent=False,
            ok=False,
            status="denied",
            entry_count=total,
            last_scan=log.created_at,
        )

    log, idempotent = scan_entry(
        db,
        event_id=payload.event_id,
        token=payload.token,
        scan_id=payload.scan_id,
        actor_user_id=identity["user_id"],
    )

    status_label = _scan_status_from_log(log, idempotent=idempotent)
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="entry.scan",
        entity_type="entry_scan_log",
        entity_id=str(log.id),
        event_id=payload.event_id,
        bar_id=event.bar_id,
        payload={
            "scan_id": payload.scan_id,
            "decision": log.decision,
            "status": status_label,
            "reason": log.reason,
            "idempotent": idempotent,
        },
    )
    if (not idempotent) and log.decision == "ACCEPT":
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

    total = accepted_count(db, payload.event_id)
    return EntryScanOut(
        log_id=log.id,
        event_id=log.event_id,
        decision=log.decision,
        reason=log.reason,
        user_id=log.user_id,
        token_id=log.token_id,
        created_at=log.created_at,
        idempotent=idempotent,
        ok=status_label == "accepted",
        status=status_label,
        entry_count=total,
        last_scan=log.created_at,
    )


@router.get("/entry/stats", response_model=EntryStatsOut)
def entry_stats(
    event_id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager", "bartender"})
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])

    effective_state, runtime_reason = effective_module_state(db, event_id, "entry_enabled")
    runtime_status = get_event_runtime_state(db, event_id)
    total = accepted_count(db, event_id)
    delta_10 = accepted_last_10_min(db, event_id)
    cap = None
    cap_percent = None

    return EntryStatsOut(
        event_id=event_id,
        entry_count=total,
        accepted_last_10_min=delta_10,
        cap=cap,
        cap_percent=cap_percent,
        runtime_status=runtime_status if effective_state != "OFF" else "MODULE_OFF",
        runtime_reason=runtime_reason,
    )


@router.get("/entry/logs/export")
def entry_logs_export(
    event_id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager"})
    get_owned_event_or_403(db, event_id, identity["bar_id"])

    rows = (
        db.query(EntryScanLog)
        .filter(EntryScanLog.event_id == event_id)
        .order_by(EntryScanLog.created_at.desc(), EntryScanLog.id.desc())
        .all()
    )

    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["timestamp", "ticket_id", "status", "reason", "staff_id", "scan_id"])
    for row in rows:
        status = "accepted" if row.decision == "ACCEPT" else ("duplicate" if row.reason == "already_used" else "denied")
        writer.writerow([
            row.created_at.isoformat(),
            row.token_id or "",
            status,
            row.reason,
            row.created_by_user_id or "",
            row.scan_id or "",
        ])

    payload = io.BytesIO(stream.getvalue().encode("utf-8"))
    headers = {"Content-Disposition": f'attachment; filename="entry_logs_event_{event_id}.csv"'}
    return StreamingResponse(payload, media_type="text/csv", headers=headers)


@router.get("/entry/tokens/stats", response_model=EntryTokenStatsOut)
def entry_token_stats(
    event_id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager"})
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
        recent_uses=[_entry_log_out(row) for row in recent],
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
    ensure_partner_role(identity, {"manager", "bartender"})
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
    return EntryScanLogPageOut(items=[_entry_log_out(r) for r in rows], next_cursor=next_cursor)
