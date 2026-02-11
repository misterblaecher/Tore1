from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import now_utc
from models import Wallet, WalletTx
from app.schemas.wallet import WalletTxOut


def get_or_create_wallet(s: Session, user_id: str) -> Wallet:
    wallet = s.get(Wallet, user_id)
    if wallet:
        return wallet
    wallet = Wallet(user_id=user_id, balance_tickets=0, updated_at=now_utc())
    s.add(wallet)
    s.flush()
    return wallet


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
        return wallet, existing, False

    wallet.balance_tickets += amount_tickets
    wallet.updated_at = now_utc()
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
