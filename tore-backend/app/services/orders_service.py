from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import now_utc
from models import Bar, Event, MenuItem, MenuItemVariant, Order, OrderItem
from app.schemas.orders import OrderItemOut, OrderOut
from app.services.wallet_service import apply_wallet_tx, get_or_create_wallet


def order_out(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        bar_id=order.bar_id,
        event_id=order.event_id,
        user_id=order.user_id,
        status=order.status,
        payment_status=order.payment_status,
        total_cents=order.total_cents,
        total_tickets=order.total_tickets,
        note=order.note,
        source=order.source,
        idempotency_key=order.idempotency_key,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=[
            OrderItemOut(
                id=item.id,
                menu_item_id=item.menu_item_id,
                variant_id=item.variant_id,
                name_snapshot=item.name_snapshot,
                price_cents_snapshot=item.price_cents_snapshot,
                qty=item.qty,
                line_total_cents=item.line_total_cents,
            )
            for item in order.items
        ],
    )


def create_order(
    db: Session,
    *,
    bar_id: int,
    event_id: Optional[int],
    user_id: Optional[str],
    device_id: Optional[str],
    items: list[Any],
    note: Optional[str],
    payment_mode: str,
    idempotency_key: str,
) -> Order:
    bar = db.get(Bar, bar_id)
    if not bar:
        raise HTTPException(404, "Bar not found")

    event: Optional[Event] = None
    if event_id is not None:
        event = db.get(Event, event_id)
        if not event:
            raise HTTPException(404, "Event not found")
        if event.bar_id != bar_id:
            raise HTTPException(403, "Event does not belong to bar")

    dedupe_query = db.query(Order).filter(
        Order.bar_id == bar_id,
        Order.idempotency_key == idempotency_key,
    )
    if user_id:
        dedupe_query = dedupe_query.filter(Order.user_id == user_id)
    else:
        dedupe_query = dedupe_query.filter(Order.device_id == device_id)

    existing = dedupe_query.first()
    if existing:
        return existing

    if not items:
        raise HTTPException(400, "Empty order")

    total_cents = 0
    order_items: list[dict[str, Any]] = []
    for row in items:
        menu_item = db.get(MenuItem, row.item_id)
        if not menu_item or menu_item.bar_id != bar_id or not menu_item.is_active or not menu_item.is_available:
            raise HTTPException(404, f"Menu item {row.item_id} not found")

        variant = None
        unit_price = menu_item.price_cents
        name_snapshot = menu_item.name

        if row.variant_id is not None:
            variant = db.get(MenuItemVariant, row.variant_id)
            if not variant or variant.item_id != menu_item.id or not variant.is_active:
                raise HTTPException(404, f"Variant {row.variant_id} not found")
            unit_price = menu_item.price_cents + variant.price_delta_cents
            name_snapshot = f"{menu_item.name} — {variant.name}"

        line_total = unit_price * row.qty
        total_cents += line_total
        order_items.append(
            {
                "menu_item_id": menu_item.id,
                "variant_id": variant.id if variant else None,
                "name_snapshot": name_snapshot,
                "price_cents_snapshot": unit_price,
                "qty": row.qty,
                "line_total_cents": line_total,
                "unit_price_cents": unit_price,
            }
        )

    payment_status = "UNPAID"
    total_tickets = 0
    pay_mode = "PAY_LATER"
    if payment_mode == "tickets":
        if not user_id:
            raise HTTPException(400, "User is required for ticket payments")
        ticket_value_cents = max(1, int(event.ticket_value_cents if event else 200))
        total_tickets = (total_cents + ticket_value_cents - 1) // ticket_value_cents
        wallet = get_or_create_wallet(db, user_id)
        if wallet.balance_tickets < total_tickets:
            raise HTTPException(
                400,
                f"Insufficient wallet balance: required {total_tickets}, available {wallet.balance_tickets}",
            )
        payment_status = "PAID"
        pay_mode = "PAY_WITH_TICKETS"

    order = Order(
        bar_id=bar_id,
        event_id=event_id,
        user_id=user_id,
        status="NEW",
        payment_status=payment_status,
        note=note,
        source="menu_qr",
        idempotency_key=idempotency_key,
        device_id=device_id,
        created_at=now_utc(),
        updated_at=now_utc(),
        total_cents=total_cents,
        total_tickets=total_tickets,
        pay_mode=pay_mode,
    )
    db.add(order)
    db.flush()

    for item in order_items:
        db.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=item["menu_item_id"],
                variant_id=item["variant_id"],
                name_snapshot=item["name_snapshot"],
                price_cents_snapshot=item["price_cents_snapshot"],
                qty=item["qty"],
                line_total_cents=item["line_total_cents"],
                drink_id=None,
                unit_price_cents=item["unit_price_cents"],
            )
        )

    if payment_mode == "tickets":
        apply_wallet_tx(
            db,
            user_id=user_id,
            amount_tickets=-total_tickets,
            kind="ORDER_PAYMENT",
            ref_type="ORDER",
            ref_id=str(order.id),
            idempotency_key=f"order-payment:{bar_id}:{idempotency_key}",
            created_by_user_id=None,
        )

    order.updated_at = now_utc()
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def patch_order_status(db: Session, *, order_id: int, bar_id: int, status: str) -> Order:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    if order.bar_id != bar_id:
        raise HTTPException(403, "Forbidden")

    valid_flow = {
        "NEW": {"IN_PROGRESS", "CANCELLED"},
        "IN_PROGRESS": {"READY", "CANCELLED"},
        "READY": {"SERVED", "CANCELLED"},
        "SERVED": set(),
        "CANCELLED": set(),
    }
    next_status = status.upper()
    if next_status not in valid_flow:
        raise HTTPException(400, "Invalid status")
    if next_status not in valid_flow.get(order.status, set()):
        raise HTTPException(400, "Invalid transition")

    order.status = next_status
    order.updated_at = now_utc()
    db.add(order)
    db.commit()
    db.refresh(order)
    return order
