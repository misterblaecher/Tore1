from __future__ import annotations

from fastapi import HTTPException
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
    db.commit()
    db.refresh(ledger)
    return ledger, False
