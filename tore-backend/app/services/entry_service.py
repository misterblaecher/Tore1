from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from db import now_utc
from models import EntryLog, EntryScanLog, EntryToken, Event


def require_partner_staff(identity: dict) -> None:
    if identity.get("role") not in {"manager", "bartender"}:
        raise HTTPException(status_code=403, detail="Forbidden")


def require_partner_manager(identity: dict) -> None:
    if identity.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")


def get_owned_event_or_403(db: Session, event_id: int, bar_id: int) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.bar_id != bar_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return event


def _token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def issue_tokens(
    db: Session,
    *,
    event_id: int,
    count: int,
    expires_in_minutes: int,
    user_id: Optional[str],
    metadata: dict,
) -> list[tuple[EntryToken, str]]:
    out: list[tuple[EntryToken, str]] = []
    expires_at = now_utc() + timedelta(minutes=expires_in_minutes)
    for _ in range(count):
        token = secrets.token_urlsafe(24)
        row = EntryToken(
            event_id=event_id,
            user_id=user_id,
            token_hash=_token_hash(token),
            expires_at=expires_at,
            metadata_json=metadata or {},
            status="ACTIVE",
        )
        db.add(row)
        db.flush()
        out.append((row, token))
    return out


def revoke_tokens(db: Session, *, event_id: int, token_ids: list[int]) -> int:
    rows = (
        db.query(EntryToken)
        .filter(EntryToken.event_id == event_id, EntryToken.id.in_(token_ids))
        .all()
    )
    count = 0
    for row in rows:
        if row.status in {"ACTIVE", "EXPIRED"}:
            row.status = "REVOKED"
            db.add(row)
            count += 1
    return count


def create_denied_scan_log(
    db: Session,
    *,
    event_id: int,
    token: str,
    scan_id: str,
    actor_user_id: int,
    reason: str,
) -> EntryScanLog:
    token_hash = _token_hash(token)
    existing_by_scan = (
        db.query(EntryScanLog)
        .filter(EntryScanLog.event_id == event_id, EntryScanLog.scan_id == scan_id)
        .first()
    )
    if existing_by_scan:
        return existing_by_scan

    payload_hash = _token_hash(f"{token.strip()}::{scan_id}")

    log = EntryScanLog(
        event_id=event_id,
        scan_id=scan_id,
        payload_raw=token.strip(),
        payload_hash=payload_hash,
        token_hash=token_hash,
        token_id=None,
        user_id=None,
        decision="DENY",
        reason=reason,
        created_by_user_id=actor_user_id,
    )
    db.add(log)
    db.flush()
    return log


def scan_entry(
    db: Session,
    *,
    event_id: int,
    token: str,
    scan_id: str,
    actor_user_id: int,
) -> tuple[EntryScanLog, bool]:
    existing_scan = (
        db.query(EntryScanLog)
        .filter(EntryScanLog.event_id == event_id, EntryScanLog.scan_id == scan_id)
        .first()
    )
    if existing_scan:
        return existing_scan, True

    now = now_utc()
    token_hash = _token_hash(token)

    recent_attempts = (
        db.query(EntryScanLog)
        .filter(
            EntryScanLog.event_id == event_id,
            EntryScanLog.created_by_user_id == actor_user_id,
            EntryScanLog.created_at >= now - timedelta(seconds=60),
        )
        .count()
    )
    if recent_attempts >= 120:
        raise HTTPException(status_code=429, detail={"reason": "rate_limited", "message": "Too many scans, slow down"})

    entry_token = (
        db.query(EntryToken)
        .filter(EntryToken.event_id == event_id, EntryToken.token_hash == token_hash)
        .with_for_update()
        .first()
    )

    decision = "DENY"
    reason = "invalid_token"
    user_id = None
    token_id = None

    if entry_token:
        user_id = entry_token.user_id
        token_id = entry_token.id
        if entry_token.status == "REVOKED":
            reason = "revoked"
        elif entry_token.status == "USED":
            reason = "already_used"
        elif entry_token.expires_at <= now:
            entry_token.status = "EXPIRED"
            db.add(entry_token)
            reason = "expired"
        elif entry_token.status == "ACTIVE":
            updated = (
                db.query(EntryToken)
                .filter(
                    EntryToken.id == entry_token.id,
                    EntryToken.status == "ACTIVE",
                    EntryToken.used_at.is_(None),
                    EntryToken.expires_at > now,
                )
                .update(
                    {
                        EntryToken.status: "USED",
                        EntryToken.used_at: now,
                        EntryToken.used_by_partner_id: actor_user_id,
                        EntryToken.used_scan_id: scan_id,
                    },
                    synchronize_session=False,
                )
            )
            if updated == 1:
                decision = "ACCEPT"
                reason = "ok"
            else:
                reason = "already_used"

    payload_hash = _token_hash(f"{token.strip()}::{scan_id}")

    log = EntryScanLog(
        event_id=event_id,
        scan_id=scan_id,
        payload_raw=token.strip(),
        payload_hash=payload_hash,
        token_hash=token_hash,
        token_id=token_id,
        user_id=user_id,
        decision=decision,
        reason=reason,
        created_by_user_id=actor_user_id,
    )
    db.add(log)
    db.flush()
    return log, False


def entry_delta_count(db: Session, event_id: int) -> int:
    """Historical operational counter: sum EntryLog.delta for one event."""
    return int(
        db.scalar(
            select(func.coalesce(func.sum(EntryLog.delta), 0)).where(
                EntryLog.event_id == event_id
            )
        )
        or 0
    )


def accepted_count(db: Session, event_id: int) -> int:
    return int(
        db.query(func.count(EntryScanLog.id))
        .filter(EntryScanLog.event_id == event_id, EntryScanLog.decision == "ACCEPT")
        .scalar()
        or 0
    )


def accepted_last_10_min(db: Session, event_id: int) -> int:
    since = now_utc() - timedelta(minutes=10)
    return int(
        db.query(func.count(EntryScanLog.id))
        .filter(
            EntryScanLog.event_id == event_id,
            EntryScanLog.decision == "ACCEPT",
            EntryScanLog.created_at >= since,
        )
        .scalar()
        or 0
    )


def parse_cursor(raw: Optional[str]) -> tuple[Optional[datetime], Optional[int]]:
    if not raw:
        return None, None
    try:
        decoded = base64.urlsafe_b64decode(raw.encode("utf-8")).decode("utf-8")
        payload = json.loads(decoded)
        ts = datetime.fromisoformat(payload["ts"])
        return ts, int(payload["id"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


def make_cursor(ts: datetime, row_id: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"ts": ts.isoformat(), "id": row_id}).encode("utf-8")).decode("utf-8")


def filter_entry_logs(
    db: Session,
    *,
    event_id: int,
    status: Optional[str],
    staff_id: Optional[int],
    after: Optional[datetime],
    before: Optional[datetime],
    search: Optional[str],
    cursor: Optional[str],
    limit: int,
) -> tuple[list[EntryScanLog], Optional[str]]:
    q = db.query(EntryScanLog).filter(EntryScanLog.event_id == event_id)
    if status:
        q = q.filter(EntryScanLog.decision == status.upper())
    if staff_id:
        q = q.filter(EntryScanLog.created_by_user_id == staff_id)
    if after:
        q = q.filter(EntryScanLog.created_at >= after)
    if before:
        q = q.filter(EntryScanLog.created_at <= before)
    if search:
        needle = search.strip()
        conds = [EntryScanLog.scan_id == needle]
        if needle.isdigit():
            conds.append(EntryScanLog.token_id == int(needle))
        q = q.filter(or_(*conds))

    cursor_ts, cursor_id = parse_cursor(cursor)
    if cursor_ts and cursor_id:
        q = q.filter(
            or_(
                EntryScanLog.created_at < cursor_ts,
                and_(EntryScanLog.created_at == cursor_ts, EntryScanLog.id < cursor_id),
            )
        )

    rows = q.order_by(EntryScanLog.created_at.desc(), EntryScanLog.id.desc()).limit(limit + 1).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = make_cursor(last.created_at, last.id)
        rows = rows[:limit]
    return rows, next_cursor
