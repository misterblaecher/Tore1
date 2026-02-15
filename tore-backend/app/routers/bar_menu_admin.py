from __future__ import annotations

import csv
import io
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db, now_utc
from models import Event, EventRuntimeState, MenuAdminIdempotency, MenuCategory, MenuItem, PartnerMembership
from partner_auth import current_identity as current_partner_identity
from app.services.audit_service import write_audit_log
from app.services.authz_service import ensure_partner_role

router = APIRouter(tags=["bar-menu-admin"])


class BarMenuItemOut(BaseModel):
    id: int
    name: str
    category: str
    priceTickets: int
    available: bool
    stockStatus: str
    lastPriceChangeAt: Optional[str] = None
    version: int


class BarMenuItemUpdateIn(BaseModel):
    priceTickets: Optional[int] = Field(default=None, ge=0)
    available: Optional[bool] = None
    stockStatus: Optional[str] = None
    expectedVersion: Optional[int] = Field(default=None, ge=1)


class BarMenuBulkOperationIn(BaseModel):
    setAvailable: Optional[bool] = None
    setStockStatus: Optional[str] = None
    setPriceTickets: Optional[int] = Field(default=None, ge=0)
    priceDeltaPct: Optional[float] = Field(default=None, ge=-90, le=500)


class BarMenuBulkIn(BaseModel):
    itemIds: list[int] = Field(min_length=1)
    op: BarMenuBulkOperationIn


def _event_for_bar(db: Session, *, event_id: int, identity: dict[str, Any]) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.bar_id != identity.get("bar_id"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return event


def _runtime_state(db: Session, event_id: int) -> str:
    row = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).first()
    return ((row.state if row else None) or "LIVE").upper()


def _validate_write_gate(db: Session, event_id: int, *, has_price_change: bool) -> str:
    state = _runtime_state(db, event_id)
    if state in {"FROZEN", "CLOSED"}:
        raise HTTPException(status_code=403, detail={"code": "EVENT_WRITE_BLOCKED", "state": state})
    if state == "DEGRADED" and has_price_change:
        raise HTTPException(status_code=403, detail={"code": "EVENT_DEGRADED_PRICE_BLOCKED", "state": state})
    return state


def _idempotency_or_400(idempotency_key: Optional[str]) -> str:
    key = (idempotency_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency-Key required"})
    return key[:120]


def _as_item_out(item: MenuItem, category_name: str, ticket_value_cents: int) -> BarMenuItemOut:
    tickets = int(round((item.price_cents or 0) / max(1, ticket_value_cents)))
    return BarMenuItemOut(
        id=item.id,
        name=item.name,
        category=category_name,
        priceTickets=tickets,
        available=bool(item.is_available),
        stockStatus=(item.stock_status or "IN").upper(),
        lastPriceChangeAt=item.last_price_change_at.isoformat() if item.last_price_change_at else None,
        version=max(1, int(item.version or 1)),
    )


def _normalize_stock_status(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    status = value.strip().upper()
    if status not in {"IN", "LOW", "OUT"}:
        raise HTTPException(status_code=422, detail={"reason": "invalid_stock_status"})
    return status


@router.get("/partner/portal/bar/events/{event_id}/menu")
def partner_portal_bar_menu(event_id: int, identity=Depends(current_partner_identity), db: Session = Depends(get_db)):
    ensure_partner_role(identity, {"manager", "bartender"})
    event = _event_for_bar(db, event_id=event_id, identity=identity)
    membership = (
        db.query(PartnerMembership)
        .filter(PartnerMembership.user_id == identity["user_id"], PartnerMembership.bar_id == identity["bar_id"])
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Forbidden")

    ticket_value = max(1, int(event.ticket_value_cents or 100))
    rows = (
        db.query(MenuItem, MenuCategory.name)
        .join(MenuCategory, MenuCategory.id == MenuItem.category_id)
        .filter(MenuItem.bar_id == identity["bar_id"], MenuItem.is_active.is_(True), MenuCategory.is_active.is_(True))
        .order_by(MenuCategory.sort_order.asc(), MenuItem.name.asc(), MenuItem.id.asc())
        .all()
    )
    return {
        "eventId": event_id,
        "eventState": _runtime_state(db, event_id),
        "items": [_as_item_out(item, category_name, ticket_value).model_dump(mode="json") for item, category_name in rows],
    }


@router.put("/partner/portal/bar/events/{event_id}/menu/items/{item_id}")
def partner_portal_bar_menu_item_put(
    event_id: int,
    item_id: int,
    payload: BarMenuItemUpdateIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager", "bartender"})
    event = _event_for_bar(db, event_id=event_id, identity=identity)
    key = _idempotency_or_400(idempotency_key)

    cached = (
        db.query(MenuAdminIdempotency)
        .filter(MenuAdminIdempotency.event_id == event_id, MenuAdminIdempotency.idempotency_key == key)
        .first()
    )
    if cached:
        return cached.response_json

    item = db.get(MenuItem, item_id)
    if not item or item.bar_id != identity["bar_id"]:
        raise HTTPException(status_code=404, detail="Item not found")

    next_stock = _normalize_stock_status(payload.stockStatus)
    has_price_change = payload.priceTickets is not None
    state = _validate_write_gate(db, event_id, has_price_change=has_price_change)

    current_version = max(1, int(item.version or 1))
    if payload.expectedVersion is not None and payload.expectedVersion != current_version:
        raise HTTPException(status_code=409, detail={"reason": "version_mismatch", "currentVersion": current_version})

    before = {
        "price_cents": item.price_cents,
        "is_available": item.is_available,
        "stock_status": item.stock_status or "IN",
        "version": current_version,
    }

    if payload.available is not None:
        item.is_available = payload.available
    if next_stock is not None:
        item.stock_status = next_stock
    if payload.priceTickets is not None:
        item.price_cents = int(payload.priceTickets) * max(1, int(event.ticket_value_cents or 100))
        item.last_price_change_at = now_utc()

    item.version = current_version + 1
    item.updated_at = now_utc()
    db.add(item)

    after = {
        "price_cents": item.price_cents,
        "is_available": item.is_available,
        "stock_status": item.stock_status or "IN",
        "version": item.version,
    }
    response = {
        "ok": True,
        "item": _as_item_out(item, item.category.name if item.category else "", max(1, int(event.ticket_value_cents or 100))).model_dump(mode="json"),
        "eventState": state,
    }

    db.add(MenuAdminIdempotency(event_id=event_id, idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=identity.get("user_id"),
        actor_role=identity.get("role"),
        action="bar.menu.item.update",
        entity_type="menu_item",
        entity_id=str(item.id),
        event_id=event_id,
        bar_id=identity.get("bar_id"),
        payload={"before": before, "after": after, "idempotency_key": key},
    )
    db.commit()
    return response


@router.post("/partner/portal/bar/events/{event_id}/menu/bulk")
def partner_portal_bar_menu_bulk(
    event_id: int,
    payload: BarMenuBulkIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager", "bartender"})
    event = _event_for_bar(db, event_id=event_id, identity=identity)
    key = _idempotency_or_400(idempotency_key)

    cached = (
        db.query(MenuAdminIdempotency)
        .filter(MenuAdminIdempotency.event_id == event_id, MenuAdminIdempotency.idempotency_key == key)
        .first()
    )
    if cached:
        return cached.response_json

    stock_status = _normalize_stock_status(payload.op.setStockStatus)
    has_price_change = payload.op.setPriceTickets is not None or payload.op.priceDeltaPct is not None
    _validate_write_gate(db, event_id, has_price_change=has_price_change)

    rows = (
        db.query(MenuItem)
        .filter(MenuItem.bar_id == identity["bar_id"], MenuItem.id.in_(payload.itemIds), MenuItem.is_active.is_(True))
        .all()
    )
    by_id = {row.id: row for row in rows}
    updated_items: list[dict[str, Any]] = []
    ticket_value = max(1, int(event.ticket_value_cents or 100))

    for item_id in payload.itemIds:
        item = by_id.get(item_id)
        if item is None:
            continue
        before = {
            "price_cents": item.price_cents,
            "is_available": item.is_available,
            "stock_status": item.stock_status or "IN",
            "version": max(1, int(item.version or 1)),
        }
        if payload.op.setAvailable is not None:
            item.is_available = payload.op.setAvailable
        if stock_status is not None:
            item.stock_status = stock_status
        if payload.op.setPriceTickets is not None:
            item.price_cents = int(payload.op.setPriceTickets) * ticket_value
            item.last_price_change_at = now_utc()
        elif payload.op.priceDeltaPct is not None:
            updated = int(round((item.price_cents or 0) * (1.0 + (payload.op.priceDeltaPct / 100.0))))
            item.price_cents = max(0, updated)
            item.last_price_change_at = now_utc()

        item.version = max(1, int(item.version or 1)) + 1
        item.updated_at = now_utc()
        db.add(item)

        after = {
            "price_cents": item.price_cents,
            "is_available": item.is_available,
            "stock_status": item.stock_status or "IN",
            "version": item.version,
        }
        write_audit_log(
            db,
            actor_partner_id=identity.get("user_id"),
            actor_role=identity.get("role"),
            action="bar.menu.bulk.update",
            entity_type="menu_item",
            entity_id=str(item.id),
            event_id=event_id,
            bar_id=identity.get("bar_id"),
            payload={"before": before, "after": after, "idempotency_key": key, "operation": payload.op.model_dump(mode="json")},
        )
        updated_items.append({"id": item.id, "version": item.version})

    response = {"ok": True, "updatedCount": len(updated_items), "items": updated_items}
    db.add(MenuAdminIdempotency(event_id=event_id, idempotency_key=key, response_json=response))
    db.commit()
    return response


@router.get("/partner/portal/bar/events/{event_id}/menu/export.csv")
def partner_portal_bar_menu_export_csv(
    event_id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    ensure_partner_role(identity, {"manager", "bartender"})
    event = _event_for_bar(db, event_id=event_id, identity=identity)

    rows = (
        db.query(MenuItem, MenuCategory.name)
        .join(MenuCategory, MenuCategory.id == MenuItem.category_id)
        .filter(MenuItem.bar_id == identity["bar_id"], MenuItem.is_active.is_(True))
        .order_by(MenuCategory.sort_order.asc(), MenuItem.name.asc(), MenuItem.id.asc())
        .all()
    )

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["id", "name", "category", "priceTickets", "available", "stockStatus", "lastPriceChangeAt", "version"])
    ticket_value = max(1, int(event.ticket_value_cents or 100))
    for item, category_name in rows:
        payload = _as_item_out(item, category_name, ticket_value)
        writer.writerow([
            payload.id,
            payload.name,
            payload.category,
            payload.priceTickets,
            "1" if payload.available else "0",
            payload.stockStatus,
            payload.lastPriceChangeAt or "",
            payload.version,
        ])

    data = out.getvalue().encode("utf-8")
    filename = f"bar-menu-{event_id}.csv"
    return StreamingResponse(
        iter([data]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
