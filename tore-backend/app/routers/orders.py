from __future__ import annotations

from datetime import timedelta
from typing import Any, Iterator, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from db import now_utc
from models import AppUserPrivacySetting, BarPrivacySetting, Event, Order, OrderClientQrScan, OrderItem, OrderStatusTransitionIdempotency, Zone
from partner_auth import current_identity as current_partner_identity
from app.schemas.orders import (
    CreateOrderIn,
    OrderClientQrOut,
    OrderClientQrScanIn,
    OrderClientQrScanOut,
    OrderOut,
    BarDashboardOut,
    BarLiveOrdersOut,
    BarOrderAcceptIn,
    BarOrderCancelIn,
    OrdersLiveOut,
    OrderStatusPatchIn,
)
from app.services.audit_service import write_audit_log
from app.services.order_client_qr_service import decode_order_client_token, issue_order_client_token
from app.services.orders_service import create_order, order_out, patch_order_status
from app.services.authz_service import ensure_partner_role
from app.services.rate_limit_service import enforce_rate_limit
from app.services.p3_common import decode_cursor, encode_cursor, get_event_runtime_state
from app.services.p3_common import ensure_event_action_allowed

router = APIRouter()

LIVE_STATUS_MAP = {
    "pending": "NEW",
    "accepted": "IN_PROGRESS",
    "ready": "READY",
    "completed": "SERVED",
    "cancelled": "CANCELLED",
}

BAR_LIVE_STATUS_MAP = {
    "pending": "NEW",
    "preparing": "IN_PROGRESS",
    "ready": "READY",
    "claimed": "SERVED",
    "canceled": "CANCELLED",
}

ORDER_STATUS_TO_LIVE = {
    "NEW": "pending",
    "IN_PROGRESS": "preparing",
    "READY": "ready",
    "SERVED": "claimed",
    "CANCELLED": "canceled",
}


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


def _extract_client_qr_token(raw: str) -> str:
    from app.services.qr_service import resolve_qr_payload

    payload = resolve_qr_payload(raw)
    if not payload.get("valid") or payload.get("type") != "order_client":
        raise HTTPException(400, "Invalid order client QR")
    token = str(payload.get("token") or "")
    if not token:
        raise HTTPException(400, "Invalid order client QR")
    return token


def _resolve_scan_token(payload: OrderClientQrScanIn) -> str:
    if payload.ot:
        return payload.ot.strip()
    if payload.raw:
        return _extract_client_qr_token(payload.raw)
    raise HTTPException(400, "Missing client QR token")


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
    # Keep rate-limit actor key based on trusted identity only.
    # `payload.user_id` is caller-controlled and can rotate per request, which weakens throttling.
    actor_key = token_user_id or payload.device_id or (request.client.host if request.client else "anon")
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
        zone_id=payload.zone_id,
    )
    return order_out(order)


@router.post("/orders/{order_id}/client-qr", response_model=OrderClientQrOut)
def issue_client_order_qr(
    order_id: int,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    from main import _extract_bearer_token, _resolve_app_user_from_token

    raw = _extract_bearer_token(authorization)
    if not raw:
        raise HTTPException(401, "Missing token")
    app_user = _resolve_app_user_from_token(raw, db)
    if not app_user:
        raise HTTPException(401, "Invalid token")

    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    if order.user_id != app_user.id:
        raise HTTPException(403, "Forbidden")

    issued = issue_order_client_token(order_id=order.id, user_id=app_user.id)
    qr_raw = f"tore://order?ot={issued['token']}"
    return {"order_id": order.id, "qr_raw": qr_raw, "expires_at": issued["expires_at"]}


@router.post("/partner/portal/orders/scan-client-qr", response_model=OrderClientQrScanOut)
def scan_client_order_qr(
    payload: OrderClientQrScanIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager", "bartender"})
    idem_key = payload.idempotency_key.strip()
    existing = (
        db.query(OrderClientQrScan)
        .filter(OrderClientQrScan.bar_id == identity["bar_id"], OrderClientQrScan.idempotency_key == idem_key)
        .first()
    )
    if existing:
        order = db.get(Order, existing.order_id)
        if not order:
            raise HTTPException(404, "Order not found")
        bar_settings = db.query(BarPrivacySetting).filter(BarPrivacySetting.bar_id == order.bar_id).first() if order.bar_id else None
        user_settings = db.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id == order.user_id).first() if order.user_id else None
        visible = bool(bar_settings and user_settings and bar_settings.staff_identity_consent_required and user_settings.show_identity_to_staff)
        return {
            "idempotent": True,
            "order": order_out(order),
            "user_visible_to_staff": visible,
            "identity_visible": visible,
        }

    decoded = decode_order_client_token(_resolve_scan_token(payload))
    order = db.get(Order, int(decoded["oid"]))
    if not order:
        raise HTTPException(404, "Order not found")
    if order.bar_id != identity["bar_id"]:
        raise HTTPException(403, "Forbidden")
    if order.user_id != decoded["uid"]:
        raise HTTPException(400, "Order QR does not match owner")
    if order.event_id is not None:
        ensure_event_action_allowed(db, order.event_id, "orders_enabled", write=True)

    if order.status == "NEW":
        order.status = "IN_PROGRESS"

    stamp = OrderClientQrScan(
        bar_id=identity["bar_id"],
        order_id=order.id,
        event_id=order.event_id,
        staff_user_id=identity.get("user_id"),
        idempotency_key=idem_key,
    )
    db.add(stamp)
    db.add(order)

    write_audit_log(
        db,
        actor_partner_id=identity.get("user_id"),
        actor_role=identity.get("role"),
        action="orders.client_qr.scan",
        entity_type="order",
        entity_id=str(order.id),
        event_id=order.event_id,
        bar_id=identity.get("bar_id"),
        payload={"idempotency_key": idem_key},
    )
    db.commit()
    db.refresh(order)

    bar_settings = db.query(BarPrivacySetting).filter(BarPrivacySetting.bar_id == order.bar_id).first() if order.bar_id else None
    user_settings = db.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id == order.user_id).first() if order.user_id else None
    visible = bool(bar_settings and user_settings and bar_settings.staff_identity_consent_required and user_settings.show_identity_to_staff)
    return {
        "idempotent": False,
        "order": order_out(order),
        "user_visible_to_staff": visible,
        "identity_visible": visible,
    }


@router.get("/orders/live", response_model=OrdersLiveOut)
def get_orders_live(
    event_id: int = Query(...),
    status: Optional[str] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    c_ts, c_id = decode_cursor(cursor)
    query = (
        db.query(Order, Zone.name.label("zone_name"))
        .outerjoin(Zone, Zone.id == Order.zone_id)
        .options(selectinload(Order.items))
        .filter(Order.event_id == event_id)
    )
    runtime_status = get_event_runtime_state(db, event_id)
    if status:
        mapped = LIVE_STATUS_MAP.get(status.lower(), status.upper())
        query = query.filter(Order.status == mapped)
    if c_ts and c_id:
        query = query.filter(or_(Order.created_at < c_ts, and_(Order.created_at == c_ts, Order.id < c_id)))

    rows = query.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit + 1).all()
    next_cursor = None
    if len(rows) > limit:
        last_order, _ = rows[limit - 1]
        next_cursor = encode_cursor(last_order.created_at, last_order.id)
        rows = rows[:limit]

    payload = [order_out(order, zone_name=zone_name).model_dump() for order, zone_name in rows]
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


def _compact_items_summary(order: Order) -> str:
    chunks = [f"{it.qty}x {it.name_snapshot}" for it in order.items[:3]]
    text = ", ".join(chunks)
    if len(order.items) > 3:
        text = f"{text}, +{len(order.items) - 3}"
    return text[:220]


def _masked_customer_label(user_id: Optional[str], order_id: int) -> str:
    if user_id:
        tail = user_id[-4:] if len(user_id) >= 4 else user_id
        return f"U***{tail}"
    return f"Guest-{order_id % 1000:03d}"


def _order_live_payload(order: Order) -> dict[str, Any]:
    return {
        "id": order.id,
        "createdAt": order.created_at,
        "status": ORDER_STATUS_TO_LIVE.get(order.status, "pending"),
        "totalTickets": int(order.total_tickets or 0),
        "itemsSummary": _compact_items_summary(order),
        "customerLabel": _masked_customer_label(order.user_id, order.id),
        "expiresAt": None,
    }


def _assert_bar_event_access(db: Session, event_id: int, identity: dict) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if event.bar_id != identity["bar_id"]:
        raise HTTPException(403, "Forbidden")
    return event


def _assert_order_bar_access(db: Session, order_id: int, identity: dict) -> Order:
    order = db.query(Order).options(selectinload(Order.items)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.bar_id != identity["bar_id"]:
        raise HTTPException(403, "Forbidden")
    return order


def _ensure_runtime_transition_allowed(runtime_state: str, action: str) -> None:
    state = (runtime_state or "LIVE").upper()
    if state in {"FROZEN", "CLOSED"}:
        raise HTTPException(status_code=403, detail={"code": "EVENT_WRITE_BLOCKED", "current_state": state})
    if state in {"PAUSE", "MENU_ONLY"} and action in {"accept", "ready", "cancel"}:
        raise HTTPException(status_code=403, detail={"code": "EVENT_WRITE_BLOCKED", "current_state": state})
    if state == "DEGRADED" and action in {"accept", "cancel"}:
        raise HTTPException(status_code=403, detail={"code": "EVENT_DEGRADED_WRITE_BLOCKED", "current_state": state})


def _transition_order_status(
    db: Session,
    *,
    order: Order,
    action: str,
    expected_from: set[str],
    next_status: str,
    idempotency_key: str,
    identity: dict,
    reason: Optional[str] = None,
) -> dict[str, Any]:
    existing = (
        db.query(OrderStatusTransitionIdempotency)
        .filter(
            OrderStatusTransitionIdempotency.order_id == order.id,
            OrderStatusTransitionIdempotency.action == action,
            OrderStatusTransitionIdempotency.idempotency_key == idempotency_key,
        )
        .first()
    )
    if existing:
        payload = dict(existing.response_json or {})
        payload["idempotent"] = True
        return payload

    if order.status not in expected_from:
        raise HTTPException(
            status_code=409,
            detail={"code": "ORDER_STATE_CONFLICT", "current_status": ORDER_STATUS_TO_LIVE.get(order.status, order.status.lower())},
        )

    previous = order.status
    order.status = next_status
    order.updated_at = now_utc()
    db.add(order)

    response = {
        "id": order.id,
        "status": ORDER_STATUS_TO_LIVE.get(order.status, order.status.lower()),
        "previousStatus": ORDER_STATUS_TO_LIVE.get(previous, previous.lower()),
        "idempotent": False,
    }
    stamp = OrderStatusTransitionIdempotency(
        order_id=order.id,
        action=action,
        idempotency_key=idempotency_key,
        from_status=previous,
        to_status=next_status,
        response_json=response,
    )
    db.add(stamp)

    write_audit_log(
        db,
        actor_partner_id=identity.get("user_id"),
        actor_role=identity.get("role"),
        action=f"orders.live.{action}",
        entity_type="order",
        entity_id=str(order.id),
        event_id=order.event_id,
        bar_id=order.bar_id,
        payload={
            "from": previous,
            "to": next_status,
            "idempotency_key": idempotency_key,
            "reason": reason,
        },
    )
    db.commit()
    return response


@router.get("/partner/portal/bar/events/{event_id}/orders/live", response_model=BarLiveOrdersOut)
def partner_portal_bar_orders_live(
    event_id: int,
    status: str = Query(default="all"),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager", "bartender"})
    _assert_bar_event_access(db, event_id, identity)
    query = db.query(Order).options(selectinload(Order.items)).filter(Order.event_id == event_id, Order.bar_id == identity["bar_id"])
    normalized = (status or "all").lower()
    if normalized != "all":
        mapped = BAR_LIVE_STATUS_MAP.get(normalized)
        if not mapped:
            raise HTTPException(400, "Invalid status filter")
        query = query.filter(Order.status == mapped)
    rows = query.order_by(Order.created_at.desc(), Order.id.desc()).limit(300).all()
    return {"items": [_order_live_payload(row) for row in rows]}


@router.post("/partner/portal/bar/orders/{order_id}/accept")
def partner_portal_bar_order_accept(
    order_id: int,
    payload: Optional[BarOrderAcceptIn] = None,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager", "bartender"})
    key = (idempotency_key or "").strip()
    if not key:
        raise HTTPException(400, "Idempotency-Key required")
    order = _assert_order_bar_access(db, order_id, identity)
    runtime_state = get_event_runtime_state(db, order.event_id) if order.event_id else "LIVE"
    _ensure_runtime_transition_allowed(runtime_state, "accept")
    return _transition_order_status(
        db,
        order=order,
        action="accept",
        expected_from={"NEW"},
        next_status="IN_PROGRESS",
        idempotency_key=key,
        identity=identity,
        reason=payload.reason if payload else None,
    )


@router.post("/partner/portal/bar/orders/{order_id}/ready")
def partner_portal_bar_order_ready(
    order_id: int,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager", "bartender"})
    key = (idempotency_key or "").strip()
    if not key:
        raise HTTPException(400, "Idempotency-Key required")
    order = _assert_order_bar_access(db, order_id, identity)
    runtime_state = get_event_runtime_state(db, order.event_id) if order.event_id else "LIVE"
    _ensure_runtime_transition_allowed(runtime_state, "ready")
    return _transition_order_status(
        db,
        order=order,
        action="ready",
        expected_from={"IN_PROGRESS"},
        next_status="READY",
        idempotency_key=key,
        identity=identity,
    )


@router.post("/partner/portal/bar/orders/{order_id}/claim")
def partner_portal_bar_order_claim(
    order_id: int,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager", "bartender"})
    key = (idempotency_key or "").strip()
    if not key:
        raise HTTPException(400, "Idempotency-Key required")
    order = _assert_order_bar_access(db, order_id, identity)
    runtime_state = get_event_runtime_state(db, order.event_id) if order.event_id else "LIVE"
    _ensure_runtime_transition_allowed(runtime_state, "claim")
    return _transition_order_status(
        db,
        order=order,
        action="claim",
        expected_from={"READY"},
        next_status="SERVED",
        idempotency_key=key,
        identity=identity,
    )


@router.post("/partner/portal/bar/orders/{order_id}/cancel")
def partner_portal_bar_order_cancel(
    order_id: int,
    payload: BarOrderCancelIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager", "bartender"})
    key = (idempotency_key or "").strip()
    if not key:
        raise HTTPException(400, "Idempotency-Key required")
    order = _assert_order_bar_access(db, order_id, identity)
    runtime_state = get_event_runtime_state(db, order.event_id) if order.event_id else "LIVE"
    _ensure_runtime_transition_allowed(runtime_state, "cancel")
    return _transition_order_status(
        db,
        order=order,
        action="cancel",
        expected_from={"NEW", "IN_PROGRESS"},
        next_status="CANCELLED",
        idempotency_key=key,
        identity=identity,
        reason=payload.reason,
    )


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


@router.get("/partner/portal/bar/events/{event_id}/dashboard", response_model=BarDashboardOut)
def partner_portal_bar_dashboard(
    event_id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager", "bartender", "owner"})
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if event.bar_id != identity["bar_id"]:
        raise HTTPException(403, "Forbidden")

    now = now_utc()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    rows = (
        db.query(Order.status, func.count(Order.id))
        .filter(Order.event_id == event_id, Order.created_at >= day_start, Order.created_at < day_end)
        .group_by(Order.status)
        .all()
    )
    counts = {status: int(total) for status, total in rows}

    orders_pending = counts.get("NEW", 0)
    orders_preparing = counts.get("IN_PROGRESS", 0)
    orders_ready = counts.get("READY", 0)
    orders_total_today = sum(counts.values())

    revenue_tickets_today = (
        db.query(func.coalesce(func.sum(Order.total_tickets), 0))
        .filter(Order.event_id == event_id, Order.created_at >= day_start, Order.created_at < day_end)
        .scalar()
        or 0
    )

    items_sold_today = (
        db.query(func.coalesce(func.sum(OrderItem.qty), 0))
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.event_id == event_id, Order.created_at >= day_start, Order.created_at < day_end)
        .scalar()
        or 0
    )

    prep_rows = (
        db.query(Order.created_at, Order.updated_at)
        .filter(
            Order.event_id == event_id,
            Order.status.in_(["READY", "SERVED"]),
            Order.created_at >= day_start,
            Order.created_at < day_end,
        )
        .all()
    )
    avg_prep_seconds = None
    if prep_rows:
        total_seconds = sum(max(0.0, (updated - created).total_seconds()) for created, updated in prep_rows)
        avg_prep_seconds = total_seconds / len(prep_rows)

    return {
        "event": {
            "eventState": (event.event_state or "LIVE").upper(),
            "lastUpdatedAt": event.last_updated_at or now,
        },
        "ordersPending": orders_pending,
        "ordersPreparing": orders_preparing,
        "ordersReady": orders_ready,
        "ordersTotalToday": orders_total_today,
        "itemsSoldToday": int(items_sold_today),
        "revenueTicketsToday": int(revenue_tickets_today),
        "avgPrepTime": float(avg_prep_seconds) if avg_prep_seconds is not None else None,
        "inventoryAlerts": [],
        "lastUpdatedAt": now,
    }


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
