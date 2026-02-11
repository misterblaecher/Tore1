from __future__ import annotations

import hashlib
from typing import Iterator, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from models import AppToken, AppUser, WalletTx
from partner_auth import current_identity as current_partner_identity
from app.schemas.wallet import WalletMeOut, WalletTopupFromQrIn, WalletTopupIn, WalletTxOut
from app.services.wallet_service import (
    apply_wallet_tx,
    get_or_create_wallet,
    require_wallet_staff,
    wallet_tx_exists,
    wallet_tx_out,
)

router = APIRouter()
security = HTTPBearer(auto_error=False)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> AppUser:
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing token")

    raw = (credentials.credentials or "").strip().strip('"').strip("'").strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()

    token_hash = _hash_token(raw)
    tok = (
        db.query(AppToken)
        .filter(AppToken.token_hash == token_hash, AppToken.revoked_at.is_(None))
        .first()
    )
    if not tok:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.get(AppUser, tok.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.get("/wallet/me", response_model=WalletMeOut)
def wallet_me(
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet = get_or_create_wallet(db, user.id)
    rows = (
        db.query(WalletTx)
        .filter(WalletTx.user_id == user.id)
        .order_by(WalletTx.created_at.desc())
        .limit(20)
        .all()
    )
    db.commit()
    return WalletMeOut(
        user_id=user.id,
        balance_tickets=wallet.balance_tickets,
        updated_at=wallet.updated_at,
        transactions=[wallet_tx_out(tx) for tx in rows],
    )


@router.post("/wallet/topup", response_model=WalletMeOut)
def wallet_topup(
    payload: WalletTopupIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_wallet_staff(identity)
    user = db.get(AppUser, payload.user_id)
    if not user:
        raise HTTPException(404, "User not found")

    wallet = get_or_create_wallet(db, payload.user_id)
    existing = wallet_tx_exists(db, payload.user_id, payload.idempotency_key)
    if existing:
        rows = (
            db.query(WalletTx)
            .filter(WalletTx.user_id == payload.user_id)
            .order_by(WalletTx.created_at.desc())
            .limit(20)
            .all()
        )
        db.commit()
        return WalletMeOut(
            user_id=payload.user_id,
            balance_tickets=wallet.balance_tickets,
            updated_at=wallet.updated_at,
            transactions=[wallet_tx_out(tx) for tx in rows],
        )

    apply_wallet_tx(
        db,
        user_id=payload.user_id,
        amount_tickets=payload.amount_tickets,
        kind="CREDIT",
        ref_type="TOPUP_QR",
        ref_id=payload.raw_qr,
        created_by_user_id=identity["user_id"],
        idempotency_key=payload.idempotency_key,
    )
    db.commit()

    rows = (
        db.query(WalletTx)
        .filter(WalletTx.user_id == payload.user_id)
        .order_by(WalletTx.created_at.desc())
        .limit(20)
        .all()
    )
    return WalletMeOut(
        user_id=payload.user_id,
        balance_tickets=wallet.balance_tickets,
        updated_at=wallet.updated_at,
        transactions=[wallet_tx_out(tx) for tx in rows],
    )


@router.post("/wallet/topup/from_qr", response_model=WalletMeOut)
def wallet_topup_from_qr(
    payload: WalletTopupFromQrIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    from main import resolve_qr_payload

    require_wallet_staff(identity)
    resolved = resolve_qr_payload(payload.raw_qr)
    if not resolved.get("valid") or resolved.get("type") != "wallet_topup":
        raise HTTPException(400, "Invalid wallet topup QR")

    topup_payload = WalletTopupIn(
        user_id=resolved["user_id"],
        amount_tickets=resolved["amount_tickets"],
        idempotency_key=resolved["idempotency_key"],
        raw_qr=payload.raw_qr,
    )
    return wallet_topup(topup_payload, identity=identity, db=db)


@router.get("/wallet/{user_id}/history", response_model=List[WalletTxOut])
def wallet_user_history(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_wallet_staff(identity)
    rows = (
        db.query(WalletTx)
        .filter(WalletTx.user_id == user_id)
        .order_by(WalletTx.created_at.desc())
        .limit(limit)
        .all()
    )
    return [wallet_tx_out(tx) for tx in rows]
