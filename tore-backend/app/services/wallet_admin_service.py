from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from models import AppUser, TicketBalance, WalletLedgerEntry
from app.services.wallet_service import apply_wallet_tx, get_or_create_wallet


def get_ticket_balance(db: Session, event_id: int, user_id: str) -> TicketBalance:
    row = (
        db.query(TicketBalance)
        .filter(TicketBalance.event_id == event_id, TicketBalance.user_id == user_id)
        .first()
    )
    if row:
        return row
    row = TicketBalance(event_id=event_id, user_id=user_id, balance=0)
    db.add(row)
    db.flush()
    return row


def admin_topup(
    db: Session,
    *,
    event_id: int,
    user_id: str,
    amount_tickets: int,
    reason: str,
    idempotency_key: str,
    actor_user_id: int,
) -> tuple[WalletLedgerEntry, bool]:
    user = db.get(AppUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        db.query(WalletLedgerEntry)
        .filter(
            WalletLedgerEntry.event_id == event_id,
            WalletLedgerEntry.idempotency_key == idempotency_key,
        )
        .first()
    )
    if existing:
        return existing, True

    wallet = get_or_create_wallet(db, user_id)
    ticket_balance = get_ticket_balance(db, event_id, user_id)

    apply_wallet_tx(
        db,
        user_id=user_id,
        amount_tickets=amount_tickets,
        kind="CREDIT",
        ref_type="ADMIN_TOPUP",
        ref_id=f"event:{event_id}",
        created_by_user_id=actor_user_id,
        idempotency_key=f"admin:{event_id}:{idempotency_key}",
    )
    ticket_balance.balance = int(ticket_balance.balance or 0) + amount_tickets

    ledger = WalletLedgerEntry(
        event_id=event_id,
        user_id=user_id,
        amount_tickets=amount_tickets,
        reason=reason,
        idempotency_key=idempotency_key,
        created_by_user_id=actor_user_id,
    )
    db.add(ledger)
    db.add(wallet)
    db.add(ticket_balance)
    db.flush()
    return ledger, False


def parse_cursor(raw: Optional[str]) -> tuple[Optional[datetime], Optional[int]]:
    if not raw:
        return None, None
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw.encode("utf-8")).decode("utf-8"))
        return datetime.fromisoformat(payload["ts"]), int(payload["id"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


def make_cursor(ts: datetime, row_id: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"ts": ts.isoformat(), "id": row_id}).encode("utf-8")).decode("utf-8")


def list_wallet_admin_logs(
    db: Session,
    *,
    event_id: int,
    user_id: Optional[str],
    after: Optional[datetime],
    before: Optional[datetime],
    min_delta: Optional[int],
    max_delta: Optional[int],
    idempotency_key: Optional[str],
    cursor: Optional[str],
    limit: int,
) -> tuple[list[WalletLedgerEntry], Optional[str]]:
    q = db.query(WalletLedgerEntry).filter(WalletLedgerEntry.event_id == event_id)
    if user_id:
        q = q.filter(WalletLedgerEntry.user_id == user_id)
    if after:
        q = q.filter(WalletLedgerEntry.created_at >= after)
    if before:
        q = q.filter(WalletLedgerEntry.created_at <= before)
    if min_delta is not None:
        q = q.filter(WalletLedgerEntry.amount_tickets >= min_delta)
    if max_delta is not None:
        q = q.filter(WalletLedgerEntry.amount_tickets <= max_delta)
    if idempotency_key:
        q = q.filter(WalletLedgerEntry.idempotency_key == idempotency_key)

    cursor_ts, cursor_id = parse_cursor(cursor)
    if cursor_ts and cursor_id:
        q = q.filter(
            or_(
                WalletLedgerEntry.created_at < cursor_ts,
                and_(WalletLedgerEntry.created_at == cursor_ts, WalletLedgerEntry.id < cursor_id),
            )
        )

    rows = q.order_by(WalletLedgerEntry.created_at.desc(), WalletLedgerEntry.id.desc()).limit(limit + 1).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = make_cursor(last.created_at, last.id)
        rows = rows[:limit]
    return rows, next_cursor
