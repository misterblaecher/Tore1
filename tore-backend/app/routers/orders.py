from __future__ import annotations

from typing import Iterator, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from models import Order
from partner_auth import current_identity as current_partner_identity
from app.schemas.orders import CreateOrderIn, OrderOut, OrdersLiveOut, OrderStatusPatchIn
from app.services.orders_service import create_order, order_out, patch_order_status
from app.services.authz_service import ensure_partner_role
from app.services.rate_limit_service import enforce_rate_limit
from app.services.p3_common import decode_cursor, encode_cursor, get_event_runtime_state

router = APIRouter()

LIVE_STATUS_MAP = {
    "pending": "NEW",
    "accepted": "IN_PROGRESS",
    "ready": "READY",
    "completed": "SERVED",
    "cancelled": "CANCELLED",
}


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


@router.post("/orders", response_model=OrderOut)
def create_order_route(
    payload: CreateOrderIn,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    idempotency_header: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    from main import _extract_bearer_token, _resolve_app_user_from_token

    token_user_id: Optional[str] = None
    raw = _extract_bearer_token(authorization)
    if raw:
        app_user = _resolve_app_user_from_token(raw, db)
        if app_user:
            token_user_id = app_user.id

    resolved_user_id = payload.user_id or token_user_id
    actor_key = resolved_user_id or payload.device_id or (request.client.host if request.client else "anon")
    enforce_rate_limit("orders_create", actor_key)
    if token_user_id and payload.user_id and payload.user_id != token_user_id:
        raise HTTPException(403, "Forbidden")

    idem_key = (idempotency_header or payload.idempotency_key or "").strip()
    if len(idem_key) < 4:
        raise HTTPException(400, "Missing idempotency key")

    order = create_order(
        db,
        bar_id=payload.bar_id,
        event_id=payload.event_id,
        user_id=resolved_user_id,
        device_id=payload.device_id,
        items=payload.items,
        note=payload.note,
        payment_mode=payload.payment_mode,
        idempotency_key=idem_key,
    )
    return order_out(order)


@router.get("/orders/live", response_model=OrdersLiveOut)
def get_orders_live(
    event_id: int = Query(...),
    status: Optional[str] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    c_ts, c_id = decode_cursor(cursor)
    query = db.query(Order).filter(Order.event_id == event_id)
    runtime_status = get_event_runtime_state(db, event_id)
    if status:
        mapped = LIVE_STATUS_MAP.get(status.lower(), status.upper())
        query = query.filter(Order.status == mapped)
    if c_ts and c_id:
        query = query.filter(or_(Order.created_at < c_ts, and_(Order.created_at == c_ts, Order.id < c_id)))

    rows = query.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit + 1).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(last.created_at, last.id)
        rows = rows[:limit]

    payload = [order_out(r).model_dump() for r in rows]
    for row in payload:
        row["status_alias"] = {
            "NEW": "pending",
            "IN_PROGRESS": "accepted",
            "READY": "ready",
            "SERVED": "completed",
            "CANCELLED": "cancelled",
        }.get(row["status"], row["status"].lower())
        row["runtime_status"] = runtime_status
    return {"items": payload, "next_cursor": next_cursor}


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    return order_out(order)


@router.get("/partner/portal/orders", response_model=List[OrderOut])
def partner_portal_orders(
    status: Optional[str] = Query(default=None),
    payment_status: Optional[str] = Query(default=None),
    event_id: Optional[int] = Query(default=None),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    query = db.query(Order).filter(Order.bar_id == identity["bar_id"])
    if status:
        query = query.filter(Order.status == status)
    if payment_status:
        query = query.filter(Order.payment_status == payment_status.upper())
    if event_id is not None:
        query = query.filter(Order.event_id == event_id)
    rows = query.order_by(Order.created_at.desc()).limit(300).all()
    return [order_out(row) for row in rows]


@router.patch("/partner/portal/orders/{order_id}/status", response_model=OrderOut)
def partner_portal_order_status_patch(
    order_id: int,
    payload: OrderStatusPatchIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager", "bartender"})
    enforce_rate_limit("orders_status", str(identity.get("user_id")))
    order = patch_order_status(
        db,
        order_id=order_id,
        bar_id=identity["bar_id"],
        status=payload.status,
        actor_partner_id=identity.get("user_id"),
        actor_role=identity.get("role"),
    )
    return order_out(order)


@router.patch("/orders/{order_id}/status", response_model=OrderOut)
def orders_status_patch(
    order_id: int,
    payload: OrderStatusPatchIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager", "bartender"})
    enforce_rate_limit("orders_status", str(identity.get("user_id")))
    order = patch_order_status(
        db,
        order_id=order_id,
        bar_id=identity["bar_id"],
        status=payload.status,
        actor_partner_id=identity.get("user_id"),
        actor_role=identity.get("role"),
    )
    return order_out(order)
