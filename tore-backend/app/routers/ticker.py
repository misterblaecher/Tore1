from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime
from typing import Any, Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from db import now_utc
from models import AppToken, AppUser, AuditLog, Event, EventBroadcast, Order, WalletGift, WalletTx

router = APIRouter(tags=["ticker"])
security = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


def _hash_token(raw: str) -> str:
    import hashlib

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> AppUser:
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing token")
    raw = (credentials.credentials or "").strip().strip('"').strip("'").strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    tok = db.query(AppToken).filter(AppToken.token_hash == _hash_token(raw), AppToken.revoked_at.is_(None)).first()
    if not tok:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.get(AppUser, tok.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _encode_cursor(ts: datetime, item_id: str) -> str:
    raw = json.dumps({"ts": ts.isoformat(), "id": item_id}).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _decode_cursor(cursor: Optional[str]) -> tuple[Optional[datetime], Optional[str]]:
    if not cursor:
        return None, None
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8"))
        return datetime.fromisoformat(data["ts"]), str(data["id"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


def _ticker_rows(db: Session, event_id: int, user_id: str, scan_limit: int = 200) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    orders = (
        db.query(Order)
        .filter(Order.event_id == event_id, Order.user_id == user_id)
        .order_by(Order.updated_at.desc(), Order.id.desc())
        .limit(scan_limit)
        .all()
    )
    for order in orders:
        rows.append(
            {
                "id": f"order:{order.id}:{order.updated_at.isoformat()}",
                "ts": order.updated_at,
                "type": "order_status",
                "title": f"Commande #{order.id}",
                "body": f"Statut: {order.status}",
                "severity": "info",
                "ref_kind": "order",
                "ref_id": str(order.id),
            }
        )

    topups = (
        db.query(WalletTx)
        .filter(
            WalletTx.user_id == user_id,
            WalletTx.kind == "CREDIT",
            WalletTx.ref_type.in_(["TOPUP_QR", "ADMIN_TOPUP"]),
        )
        .order_by(WalletTx.created_at.desc(), WalletTx.id.desc())
        .limit(scan_limit)
        .all()
    )
    for tx in topups:
        rows.append(
            {
                "id": f"wallet_topup:{tx.id}",
                "ts": tx.created_at,
                "type": "wallet_topup",
                "title": "Top-up wallet",
                "body": f"+{tx.amount_tickets} tickets",
                "severity": "success",
                "ref_kind": "wallet_tx",
                "ref_id": str(tx.id),
            }
        )

    gifts = (
        db.query(WalletGift)
        .filter(
            and_(
                WalletGift.event_id == event_id,
                or_(WalletGift.from_user_id == user_id, WalletGift.to_user_id == user_id),
            )
        )
        .order_by(WalletGift.created_at.desc(), WalletGift.id.desc())
        .limit(scan_limit)
        .all()
    )
    for gift in gifts:
        incoming = gift.to_user_id == user_id
        rows.append(
            {
                "id": f"gift:{gift.id}",
                "ts": gift.created_at,
                "type": "gift_in" if incoming else "gift_out",
                "title": "Cadeau reçu" if incoming else "Cadeau envoyé",
                "body": f"{gift.amount_tickets} tickets",
                "severity": "info",
                "ref_kind": "wallet_gift",
                "ref_id": str(gift.id),
            }
        )

    audits = (
        db.query(AuditLog)
        .filter(
            AuditLog.event_id == event_id,
            AuditLog.action.in_([
                "event_state.update",
                "event_modules.update",
                "polymarket.create",
                "polymarket.position",
                "polymarket.resolve",
                "polymarket.finalize",
                "polymarket.cancel",
            ]),
        )
        .order_by(AuditLog.ts.desc(), AuditLog.id.desc())
        .limit(scan_limit)
        .all()
    )
    for row in audits:
        if row.action == "event_state.update":
            kind = "event_state_change"
            title = "Etat event mis à jour"
            severity = "warning"
        elif row.action == "event_modules.update":
            kind = "module_toggle"
            title = "Modules event mis à jour"
            severity = "warning"
        else:
            kind = "polymarket_market_update"
            title = "Polymarket mis à jour"
            severity = "info"
        rows.append(
            {
                "id": f"audit:{row.id}",
                "ts": row.ts,
                "type": kind,
                "title": title,
                "body": row.action,
                "severity": severity,
                "ref_kind": row.entity_type,
                "ref_id": row.entity_id,
            }
        )

    event = db.get(Event, event_id)
    if event and bool((event.modules_on or {}).get("broadcast")):
        broadcasts = (
            db.query(EventBroadcast)
            .filter(EventBroadcast.event_id == event_id)
            .order_by(EventBroadcast.created_at.desc(), EventBroadcast.id.desc())
            .limit(scan_limit)
            .all()
        )
        now = now_utc()
        for row in broadcasts:
            if row.expires_at and row.expires_at <= now:
                continue
            rows.append(
                {
                    "id": f"broadcast:{row.id}",
                    "ts": row.created_at,
                    "type": "broadcast",
                    "title": "Broadcast event",
                    "body": row.message,
                    "severity": "error" if row.level == "urgent" else ("warning" if row.level == "warn" else "info"),
                    "ref_kind": "broadcast",
                    "ref_id": str(row.id),
                }
            )

    rows.sort(key=lambda x: (x["ts"], x["id"]), reverse=True)
    return rows


@router.get("/events/{event_id}/ticker")
def get_ticker_feed(
    event_id: int,
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    cursor_ts, cursor_id = _decode_cursor(cursor)
    rows = _ticker_rows(db, event_id=event_id, user_id=user.id)
    if cursor_ts is not None and cursor_id is not None:
        rows = [r for r in rows if (r["ts"], r["id"]) < (cursor_ts, cursor_id)]

    items = rows[:limit]
    next_cursor = _encode_cursor(items[-1]["ts"], items[-1]["id"]) if len(rows) > limit and items else None
    return {"items": items, "next_cursor": next_cursor}


@router.get("/events/{event_id}/ticker/stream")
async def stream_ticker_feed(
    request: Request,
    event_id: int,
    cursor: Optional[str] = Query(default=None),
    once: bool = Query(default=False),
    user: AppUser = Depends(get_current_user),
):
    session = get_db().__next__()
    try:
        event = session.get(Event, event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
    finally:
        session.close()

    last_ts, last_id = _decode_cursor(cursor)

    async def ticker_stream():
        nonlocal last_ts, last_id
        try:
            while True:
                if await request.is_disconnected():
                    break
                s = get_db().__next__()
                try:
                    rows = _ticker_rows(s, event_id=event_id, user_id=user.id, scan_limit=60)
                finally:
                    s.close()

                emitted = 0
                for item in rows:
                    if last_ts is not None and last_id is not None and (item["ts"], item["id"]) <= (last_ts, last_id):
                        continue
                    payload = dict(item)
                    payload["ts"] = item["ts"].isoformat()
                    yield f"event: ticker\ndata: {json.dumps(payload)}\n\n"
                    emitted += 1
                if emitted:
                    newest = rows[0]
                    last_ts, last_id = newest["ts"], newest["id"]
                else:
                    yield ": keepalive\n\n"
                if once:
                    break
                await asyncio.sleep(2)
        except GeneratorExit:
            return

    return StreamingResponse(
        ticker_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
