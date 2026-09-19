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
from models import (
    AppToken,
    AppUser,
    AppUserPrivacySetting,
    BarPrivacySetting,
    Drink,
    Event,
    EventBroadcast,
    Order,
    PriceHistory,
    TicketTransfer,
)

router = APIRouter(tags=["ticker"])
security = HTTPBearer(auto_error=False)

_ALLOWED_TYPES = {"broadcast", "order", "price", "gift", "battles", "hunt", "bets", "alerts", "crash"}


from app.deps.db import get_db


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


def _parse_since(since: Optional[str]) -> Optional[datetime]:
    if not since:
        return None
    try:
        return datetime.fromisoformat(since)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid since") from exc


def _parse_types(raw: Optional[str]) -> Optional[set[str]]:
    if not raw:
        return None
    values = {chunk.strip().lower() for chunk in raw.split(",") if chunk.strip()}
    unknown = sorted(values.difference(_ALLOWED_TYPES))
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown ticker type(s): {', '.join(unknown)}")
    return values


def _module_enabled(event: Event, module_keys: list[str], default_value: bool = True) -> bool:
    modules = event.modules_on or {}
    for key in module_keys:
        if key in modules:
            return bool(modules.get(key))
    return default_value


def _masked_label(user_id: Optional[str], fallback_id: int) -> str:
    if user_id:
        tail = user_id[-4:] if len(user_id) >= 4 else user_id
        return f"U***{tail}"
    return f"Guest-{fallback_id % 1000:03d}"


def _can_show_identity_in_bar(db: Session, event: Event, user_id: Optional[str]) -> bool:
    if not user_id or not event.bar_id:
        return False
    bar_settings = db.query(BarPrivacySetting).filter(BarPrivacySetting.bar_id == event.bar_id).first()
    user_settings = db.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id == user_id).first()
    visibility = (user_settings.visibility if user_settings and user_settings.visibility else "public").lower()
    if visibility == "private":
        return False
    if not (bar_settings and bar_settings.staff_identity_consent_required):
        return False
    return bool(user_settings and (user_settings.show_identity_in_bar or user_settings.show_identity_to_staff))


def _user_label(db: Session, event: Event, user_id: Optional[str], fallback_id: int) -> str:
    if user_id and _can_show_identity_in_bar(db, event, user_id):
        app_user = db.get(AppUser, user_id)
        if app_user and app_user.display_name:
            return app_user.display_name
    return _masked_label(user_id, fallback_id)


def _ticker_rows(db: Session, event: Event, scan_limit: int = 200) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    event_id = event.id

    if _module_enabled(event, ["menu", "orders_enabled"], default_value=True):
        orders = (
            db.query(Order)
            .filter(Order.event_id == event_id)
            .order_by(Order.updated_at.desc(), Order.id.desc())
            .limit(scan_limit)
            .all()
        )
        for order in orders:
            label = _user_label(db, event, order.user_id, order.id)
            rows.append(
                {
                    "id": f"order:{order.id}:created:{order.created_at.isoformat()}",
                    "ts": order.created_at,
                    "type": "order",
                    "severity": "info",
                    "moduleKey": "menu",
                    "payloadCompact": {
                        "kind": "order_created",
                        "orderId": str(order.id),
                        "status": "created",
                        "totalTickets": int(order.total_tickets or 0),
                        "userLabel": label,
                    },
                }
            )
            if order.updated_at and order.updated_at > order.created_at:
                rows.append(
                    {
                        "id": f"order:{order.id}:{order.status}:{order.updated_at.isoformat()}",
                        "ts": order.updated_at,
                        "type": "order",
                        "severity": "info",
                        "moduleKey": "menu",
                        "payloadCompact": {
                            "kind": "status_changed",
                            "orderId": str(order.id),
                            "status": (order.status or "").lower(),
                            "totalTickets": int(order.total_tickets or 0),
                            "userLabel": label,
                        },
                    }
                )

    if _module_enabled(event, ["ticker", "market", "prices_enabled"], default_value=True):
        history = (
            db.query(PriceHistory, Drink.name)
            .join(Drink, Drink.id == PriceHistory.drink_id)
            .filter(PriceHistory.event_id == event_id)
            .order_by(PriceHistory.ts.asc(), PriceHistory.id.asc())
            .limit(scan_limit)
            .all()
        )
        previous_price_by_drink: dict[int, int] = {}
        for row, drink_name in history:
            prev = previous_price_by_drink.get(row.drink_id)
            if prev is not None and prev != row.price_cents:
                rows.append(
                    {
                        "id": f"price:{row.id}",
                        "ts": row.ts,
                        "type": "price",
                        "severity": "info",
                        "moduleKey": "ticker",
                        "payloadCompact": {
                            "drinkName": drink_name,
                            "fromPrice": prev,
                            "toPrice": row.price_cents,
                            "direction": "up" if row.price_cents > prev else "down",
                            "ts": row.ts.isoformat(),
                        },
                    }
                )
            previous_price_by_drink[row.drink_id] = row.price_cents

    if _module_enabled(event, ["gifts_enabled", "gifts", "wallet"], default_value=True):
        gifts = (
            db.query(TicketTransfer)
            .filter(TicketTransfer.event_id == event_id)
            .order_by(TicketTransfer.created_at.desc(), TicketTransfer.id.desc())
            .limit(scan_limit)
            .all()
        )
        for gift in gifts:
            rows.append(
                {
                    "id": f"gift:{gift.id}",
                    "ts": gift.created_at,
                    "type": "gift",
                    "severity": "info",
                    "moduleKey": "gifts",
                    "payloadCompact": {
                        "amount": int(gift.amount or 0),
                        "fromLabel": _user_label(db, event, gift.from_user_id, gift.id),
                        "toLabel": _user_label(db, event, gift.to_user_id, gift.id),
                        "ts": gift.created_at.isoformat(),
                    },
                }
            )

    if _module_enabled(event, ["broadcast"], default_value=False):
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
            sev = "error" if row.level == "urgent" else ("warning" if row.level == "warn" else "info")
            rows.append(
                {
                    "id": f"broadcast:{row.id}",
                    "ts": row.created_at,
                    "type": "broadcast",
                    "severity": sev,
                    "moduleKey": "broadcast",
                    "payloadCompact": {
                        "level": row.level,
                        "message": row.message,
                    },
                }
            )

    rows.sort(key=lambda x: (x["ts"], x["id"]), reverse=True)
    return rows


@router.get("/events/{event_id}/ticker")
def get_ticker_feed(
    event_id: int,
    cursor: Optional[str] = Query(default=None),
    since: Optional[str] = Query(default=None),
    types: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    cursor_ts, cursor_id = _decode_cursor(cursor)
    since_ts = _parse_since(since)
    type_filters = _parse_types(types)

    rows = _ticker_rows(db, event=event)
    if type_filters is not None:
        rows = [r for r in rows if r["type"] in type_filters]
    if since_ts is not None:
        rows = [r for r in rows if r["ts"] > since_ts]
    if cursor_ts is not None and cursor_id is not None:
        rows = [r for r in rows if (r["ts"], r["id"]) < (cursor_ts, cursor_id)]

    items = rows[:limit]
    next_cursor = _encode_cursor(items[-1]["ts"], items[-1]["id"]) if len(rows) > limit and items else None
    wire_items = [
        {
            "id": item["id"],
            "type": item["type"],
            "ts": item["ts"].isoformat(),
            "payloadCompact": item["payloadCompact"],
            "severity": item.get("severity"),
            "moduleKey": item.get("moduleKey"),
        }
        for item in items
    ]
    return {
        "items": wire_items,
        "nextCursor": next_cursor,
        "next_cursor": next_cursor,
        "serverTime": now_utc().isoformat(),
    }


@router.get("/events/{event_id}/ticker/stream")
async def stream_ticker_feed(
    request: Request,
    event_id: int,
    cursor: Optional[str] = Query(default=None),
    once: bool = Query(default=False),
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
                    event_row = s.get(Event, event_id)
                    rows = _ticker_rows(s, event=event_row, scan_limit=60) if event_row else []
                finally:
                    s.close()

                emitted = 0
                for item in rows:
                    if last_ts is not None and last_id is not None and (item["ts"], item["id"]) <= (last_ts, last_id):
                        continue
                    payload = {
                        "id": item["id"],
                        "type": item["type"],
                        "ts": item["ts"].isoformat(),
                        "payloadCompact": item["payloadCompact"],
                        "severity": item.get("severity"),
                        "moduleKey": item.get("moduleKey"),
                    }
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
