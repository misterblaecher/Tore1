from __future__ import annotations

import hashlib
import threading
import time
from typing import Iterator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from db import now_utc
from models import AppToken, AppUser, WalletGift, WalletTx
from partner_auth import current_identity as current_partner_identity
from app.schemas.wallet import (
    WalletGiftIn,
    WalletGiftOut,
    WalletGiftPageOut,
    WalletGiftRowOut,
    WalletLedgerPageOut,
    WalletLedgerRowOut,
    WalletMeOut,
    WalletTopupFromQrIn,
    WalletTopupIn,
    WalletTxOut,
)
from app.services.audit_service import write_audit_log
from app.services.p3_common import decode_cursor, encode_cursor, ensure_event_action_allowed
from app.services.rate_limit_service import enforce_rate_limit
from app.services.wallet_service import apply_wallet_tx, get_or_create_wallet, require_wallet_staff, wallet_tx_exists, wallet_tx_out

router = APIRouter()
security = HTTPBearer(auto_error=False)
_gift_lock = threading.Lock()
_gift_store: dict[str, list[float]] = {}


def _enforce_gift_per_minute(user_id: str, max_per_minute: int = 20) -> None:
    now = time.monotonic()
    with _gift_lock:
        arr = _gift_store.setdefault(user_id, [])
        threshold = now - 60.0
        arr[:] = [ts for ts in arr if ts >= threshold]
        if len(arr) >= max_per_minute:
            raise HTTPException(status_code=429, detail={"reason": "rate_limited", "message": "Too many requests"})
        arr.append(now)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _required_idempotency(header_key: Optional[str], fallback: Optional[str]) -> str:
    value = (header_key or fallback or "").strip()
    if len(value) < 1:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency key required"})
    return value[:128]


def _wallet_ledger_type(tx: WalletTx) -> str:
    mapping = {
        "ADMIN_TOPUP": "topup",
        "GIFT_OUT": "gift_out",
        "GIFT_IN": "gift_in",
        "ORDER_DEBIT": "order_debit",
        "POLYMARKET_DEBIT": "polymarket_debit",
        "POLYMARKET_PAYOUT": "polymarket_payout",
        "REFUND": "refund",
        "ADMIN_ADJUST": "admin_adjust",
        "TOPUP_QR": "topup",
    }
    return mapping.get((tx.ref_type or "").upper(), "admin_adjust")


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


@router.get("/wallet/me/ledger", response_model=WalletLedgerPageOut)
def wallet_me_ledger(
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cursor_ts, cursor_id = decode_cursor(cursor)
    q = db.query(WalletTx).filter(WalletTx.user_id == user.id)
    if cursor_ts and cursor_id:
        q = q.filter(or_(WalletTx.created_at < cursor_ts, and_(WalletTx.created_at == cursor_ts, WalletTx.id < cursor_id)))
    rows = q.order_by(WalletTx.created_at.desc(), WalletTx.id.desc()).limit(limit + 1).all()

    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(last.created_at, last.id)
        rows = rows[:limit]
    return WalletLedgerPageOut(
        items=[
            WalletLedgerRowOut(
                id=tx.id,
                ts=tx.created_at,
                type=_wallet_ledger_type(tx),
                amount=tx.amount_tickets,
                ref_id=tx.ref_id,
                note=None,
            )
            for tx in rows
        ],
        next_cursor=next_cursor,
    )


@router.post("/wallet/gift", response_model=WalletGiftOut)
def wallet_gift(
    payload: WalletGiftIn,
    idempotency_header: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.amount_cents < 1:
        raise HTTPException(status_code=400, detail={"reason": "invalid_amount", "message": "Amount must be >= 1"})
    if payload.to_user_id == user.id:
        raise HTTPException(status_code=400, detail={"reason": "invalid_target", "message": "Cannot gift yourself"})

    idem = _required_idempotency(idempotency_header, payload.client_key)
    enforce_rate_limit("wallet_gift", f"{user.id}:{idem}")
    _enforce_gift_per_minute(user.id)
    recipient = db.get(AppUser, payload.to_user_id)
    if not recipient:
        raise HTTPException(status_code=404, detail={"reason": "user_not_found", "message": "Target user not found"})

    if payload.event_id is not None:
        ensure_event_action_allowed(db, payload.event_id, "wallet_enabled", write=True)

    existing = db.query(WalletGift).filter(WalletGift.from_user_id == user.id, WalletGift.idempotency_key == idem).first()
    if existing:
        sender = get_or_create_wallet(db, user.id)
        return WalletGiftOut(gift_id=existing.id, new_balance_sender=sender.balance_tickets)

    sender = get_or_create_wallet(db, user.id)
    receiver = get_or_create_wallet(db, payload.to_user_id)
    if int(sender.balance_tickets or 0) < payload.amount_cents:
        raise HTTPException(status_code=409, detail={"reason": "insufficient_balance", "message": "Insufficient balance"})

    sender.balance_tickets -= payload.amount_cents
    sender.updated_at = now_utc()
    receiver.balance_tickets += payload.amount_cents
    receiver.updated_at = now_utc()

    out_tx = WalletTx(
        user_id=user.id,
        kind="DEBIT",
        amount_tickets=-payload.amount_cents,
        ref_type="GIFT_OUT",
        ref_id=payload.to_user_id,
        idempotency_key=f"gift:out:{idem}",
    )
    in_tx = WalletTx(
        user_id=payload.to_user_id,
        kind="CREDIT",
        amount_tickets=payload.amount_cents,
        ref_type="GIFT_IN",
        ref_id=user.id,
        idempotency_key=f"gift:in:{idem}",
    )
    gift = WalletGift(
        event_id=payload.event_id,
        from_user_id=user.id,
        to_user_id=payload.to_user_id,
        amount_tickets=payload.amount_cents,
        message=payload.message,
        idempotency_key=idem,
    )
    db.add_all([sender, receiver, out_tx, in_tx, gift])
    db.flush()
    out_tx.ref_id = f"gift:{gift.id}"
    in_tx.ref_id = f"gift:{gift.id}"
    db.add_all([out_tx, in_tx])

    write_audit_log(
        db,
        actor_partner_id=None,
        actor_role="guest",
        action="wallet.gift",
        entity_type="wallet_gift",
        entity_id=str(gift.id),
        event_id=payload.event_id,
        bar_id=None,
        payload={"from_user_id": user.id, "to_user_id": payload.to_user_id, "amount": payload.amount_cents},
    )
    db.commit()
    return WalletGiftOut(gift_id=gift.id, new_balance_sender=sender.balance_tickets)


@router.get("/wallet/gifts", response_model=WalletGiftPageOut)
def wallet_gifts(
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cursor_ts, cursor_id = decode_cursor(cursor)
    q = db.query(WalletGift).filter(or_(WalletGift.from_user_id == user.id, WalletGift.to_user_id == user.id))
    if cursor_ts and cursor_id:
        q = q.filter(or_(WalletGift.created_at < cursor_ts, and_(WalletGift.created_at == cursor_ts, WalletGift.id < cursor_id)))
    rows = q.order_by(WalletGift.created_at.desc(), WalletGift.id.desc()).limit(limit + 1).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(last.created_at, last.id)
        rows = rows[:limit]

    items: list[WalletGiftRowOut] = []
    for row in rows:
        outgoing = row.from_user_id == user.id
        items.append(
            WalletGiftRowOut(
                id=row.id,
                ts=row.created_at,
                direction="out" if outgoing else "in",
                amount=-row.amount_tickets if outgoing else row.amount_tickets,
                counterparty_user_id=row.to_user_id if outgoing else row.from_user_id,
                message=row.message,
            )
        )
    return WalletGiftPageOut(items=items, next_cursor=next_cursor)


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
    from app.services.qr_service import resolve_qr_payload

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
