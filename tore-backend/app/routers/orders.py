from __future__ import annotations

from typing import Iterator, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from models import Order
from partner_auth import current_identity as current_partner_identity
from app.schemas.orders import CreateOrderIn, OrderOut, OrderStatusPatchIn
from app.services.orders_service import create_order, order_out, patch_order_status

router = APIRouter()

def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


@router.post("/orders", response_model=OrderOut)
def create_order_route(
    payload: CreateOrderIn,
    authorization: Optional[str] = Header(default=None),
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
    if token_user_id and payload.user_id and payload.user_id != token_user_id:
        raise HTTPException(403, "Forbidden")

    order = create_order(
        db,
        bar_id=payload.bar_id,
        event_id=payload.event_id,
        user_id=resolved_user_id,
        device_id=payload.device_id,
        items=payload.items,
        note=payload.note,
        payment_mode=payload.payment_mode,
        idempotency_key=payload.idempotency_key,
    )
    return order_out(order)


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
    order = patch_order_status(db, order_id=order_id, bar_id=identity["bar_id"], status=payload.status)
    return order_out(order)
