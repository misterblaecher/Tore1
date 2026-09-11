from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import now_utc
from models import Wallet, WalletTx
from app.schemas.wallet import WalletTxOut


def get_or_create_wallet(s: Session, user_id: str) -> Wallet:
    query = select(Wallet).where(Wallet.user_id == user_id).with_for_update().execution_options(populate_existing=True)
    wallet = s.execute(query).scalar_one_or_none()
    if wallet:
        return wallet
    wallet = Wallet(user_id=user_id, balance_tickets=0, updated_at=now_utc())
    try:
        with s.begin_nested():
            s.add(wallet)
            s.flush()
    except IntegrityError:
        wallet = s.execute(query).scalar_one()
    return wallet


def lock_wallets(s: Session, *user_ids: str) -> dict[str, Wallet]:
    """Acquire transfer locks consistently to avoid reciprocal-transfer deadlocks."""
    return {user_id: get_or_create_wallet(s, user_id) for user_id in sorted(set(user_ids))}


def wallet_tx_out(tx: WalletTx) -> WalletTxOut:
    return WalletTxOut(
        id=tx.id,
        user_id=tx.user_id,
        kind=tx.kind,
        amount_tickets=tx.amount_tickets,
        ref_type=tx.ref_type,
        ref_id=tx.ref_id,
        created_by_user_id=tx.created_by_user_id,
        created_at=tx.created_at,
        idempotency_key=tx.idempotency_key,
    )


def wallet_tx_exists(s: Session, user_id: str, idempotency_key: str) -> Optional[WalletTx]:
    return (
        s.query(WalletTx)
        .filter(
            WalletTx.user_id == user_id,
            WalletTx.idempotency_key == idempotency_key,
        )
        .first()
    )


def apply_wallet_tx(
    s: Session,
    *,
    user_id: str,
    amount_tickets: int,
    kind: str,
    ref_type: str,
    ref_id: Optional[str],
    idempotency_key: str,
    created_by_user_id: Optional[int] = None,
) -> tuple[Wallet, WalletTx, bool]:
    wallet = get_or_create_wallet(s, user_id)
    existing = wallet_tx_exists(s, user_id, idempotency_key)
    if existing:
        if (existing.amount_tickets, existing.kind, existing.ref_type, existing.ref_id) != (amount_tickets, kind, ref_type, ref_id):
            raise HTTPException(status_code=409, detail={"reason": "idempotency_conflict", "message": "Key already used for a different movement"})
        return wallet, existing, False

    changed_at = now_utc()
    result = s.execute(update(Wallet).where(
        Wallet.user_id == user_id,
        Wallet.balance_tickets + amount_tickets >= 0,
    ).values(balance_tickets=Wallet.balance_tickets + amount_tickets, updated_at=changed_at).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        raise HTTPException(status_code=409, detail={"reason": "insufficient_balance", "message": "Insufficient balance"})
    s.refresh(wallet)
    tx = WalletTx(
        user_id=user_id,
        kind=kind,
        amount_tickets=amount_tickets,
        ref_type=ref_type,
        ref_id=ref_id,
        created_by_user_id=created_by_user_id,
        idempotency_key=idempotency_key,
    )
    s.add_all([wallet, tx])
    s.flush()
    return wallet, tx, True


def require_wallet_staff(identity: Dict[str, Any]) -> None:
    if identity.get("role") not in {"manager", "cashier", "wallet"}:
        raise HTTPException(status_code=403, detail="Forbidden")
