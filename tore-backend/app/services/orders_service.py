from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import now_utc
from models import Bar, Event, MenuItem, MenuItemVariant, Order, OrderItem, Zone
from app.schemas.orders import OrderItemOut, OrderOut
from app.services.audit_service import write_audit_log
from app.services.market_service import apply_order_market_impact
from app.services.p3_common import ensure_event_action_allowed
from app.services.wallet_service import apply_wallet_tx, get_or_create_wallet

STATUS_INPUT_MAP = {
    "PENDING": "NEW",
    "ACCEPTED": "IN_PROGRESS",
    "COMPLETED": "SERVED",
    "NEW": "NEW",
    "IN_PROGRESS": "IN_PROGRESS",
    "READY": "READY",
    "SERVED": "SERVED",
    "CANCELLED": "CANCELLED",
}


def _status_alias(status: str) -> str:
    return {
        "NEW": "pending",
        "IN_PROGRESS": "accepted",
        "READY": "ready",
        "SERVED": "completed",
        "CANCELLED": "cancelled",
    }.get(status.upper(), status.lower())


def order_out(order: Order, *, zone_name: Optional[str] = None) -> OrderOut:
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
        zone_id=order.zone_id,
        zone_name=zone_name,
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
                market_item_id=item.market_item_id,
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
    zone_id: Optional[int] = None,
    actor_user_id: Optional[str] = None,
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
        ensure_event_action_allowed(db, event_id, "orders_enabled", write=True)

    dedupe_query = db.query(Order).filter(
        Order.bar_id == bar_id,
        Order.idempotency_key == idempotency_key,
    )
    if user_id:
        dedupe_query = dedupe_query.filter(Order.user_id == user_id)
    else:
        dedupe_query = dedupe_query.filter(Order.device_id == device_id)


    zone: Optional[Zone] = None
    if zone_id is not None:
        zone = db.get(Zone, zone_id)
        if not zone:
            raise HTTPException(404, "Zone not found")
        if zone.bar_id != bar_id:
            raise HTTPException(403, "Zone does not belong to bar")

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
                "market_item_id": row.market_item_id,
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
        zone_id=zone.id if zone else None,
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
                market_item_id=item["market_item_id"],
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

    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=actor_user_id or user_id,
        actor_role="user",
        action="orders.create",
        entity_type="order",
        entity_id=str(order.id),
        event_id=event_id,
        bar_id=bar_id,
        idempotency_key=idempotency_key,
        payload={"status": "NEW", "items_count": len(items), "zone_id": zone.id if zone else None},
    )

    order.updated_at = now_utc()
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def patch_order_status(
    db: Session,
    *,
    order_id: int,
    bar_id: int,
    status: str,
    actor_partner_id: Optional[int] = None,
    actor_role: Optional[str] = None,
) -> Order:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    if order.bar_id != bar_id:
        raise HTTPException(403, "Forbidden")
    if order.event_id is not None:
        ensure_event_action_allowed(db, order.event_id, "orders_enabled", write=True)

    valid_flow = {
        "NEW": {"IN_PROGRESS", "CANCELLED"},
        "IN_PROGRESS": {"READY", "CANCELLED"},
        "READY": {"SERVED", "CANCELLED"},
        "SERVED": set(),
        "CANCELLED": set(),
    }
    next_status = STATUS_INPUT_MAP.get(status.upper(), "")
    if next_status not in valid_flow:
        raise HTTPException(400, "Invalid status")
    if next_status == order.status:
        return order
    if next_status not in valid_flow.get(order.status, set()):
        raise HTTPException(400, "Invalid transition")

    prev = order.status
    order.status = next_status
    order.updated_at = now_utc()
    if next_status == "SERVED" and (order.payment_status == "PAID" or (order.pay_mode or "") == "PAY_WITH_TICKETS"):
        apply_order_market_impact(db, order=order)
    write_audit_log(
        db,
        actor_partner_id=actor_partner_id,
        actor_role=actor_role,
        action="orders.status_update",
        entity_type="order",
        entity_id=str(order.id),
        event_id=order.event_id,
        bar_id=order.bar_id,
        payload={"from": prev, "to": next_status, "to_alias": _status_alias(next_status)},
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order
