from fastapi.testclient import TestClient

import secrets

from db import Base, engine, get_session
from main import app
from models import AuditLog, Bar, Event, EventRuntimeState, MenuCategory, MenuItem, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_partner(role: str = "manager"):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Bar Menu {suffix}", city="Liège", partner_code=f"BM{suffix}")
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name="Menu Staff", pin_hash="hash")
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role=role, display_name="Menu Staff"))
        event = Event(bar_id=bar.id, name="Menu Event", ticket_value_cents=100)
        s.add(event)
        s.flush()
        category = MenuCategory(bar_id=bar.id, name="Drinks", sort_order=1)
        s.add(category)
        s.flush()
        item_a = MenuItem(bar_id=bar.id, category_id=category.id, name="IPA", price_cents=600, is_available=True)
        item_b = MenuItem(bar_id=bar.id, category_id=category.id, name="Cola", price_cents=300, is_available=True)
        s.add_all([item_a, item_b])
        s.commit()
        return {
            "bar_id": bar.id,
            "event_id": event.id,
            "token": _make_token(user.id, bar.id, role, "Menu Staff"),
            "item_a": item_a.id,
            "item_b": item_b.id,
        }
    finally:
        s.close()


def _set_runtime_state(event_id: int, state: str):
    s = get_session()
    try:
        row = s.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).first()
        if row is None:
            row = EventRuntimeState(event_id=event_id, state=state)
            s.add(row)
        else:
            row.state = state
            s.add(row)
        s.commit()
    finally:
        s.close()


def test_list_returns_items():
    seed = _seed_partner(role="bartender")
    client = TestClient(app)

    res = client.get(
        f"/partner/portal/bar/events/{seed['event_id']}/menu",
        headers={"Authorization": f"Bearer {seed['token']}"},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["eventId"] == seed["event_id"]
    assert len(payload["items"]) >= 2
    assert {row["name"] for row in payload["items"]} >= {"IPA", "Cola"}


def test_update_price_idempotent_and_audited():
    seed = _seed_partner(role="manager")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {seed['token']}", "Idempotency-Key": "menu-put-1"}

    first = client.put(
        f"/partner/portal/bar/events/{seed['event_id']}/menu/items/{seed['item_a']}",
        headers=headers,
        json={"priceTickets": 9, "expectedVersion": 1},
    )
    second = client.put(
        f"/partner/portal/bar/events/{seed['event_id']}/menu/items/{seed['item_a']}",
        headers=headers,
        json={"priceTickets": 9, "expectedVersion": 1},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["item"]["priceTickets"] == 9
    assert second.json()["item"]["priceTickets"] == 9

    s = get_session()
    try:
        item = s.get(MenuItem, seed["item_a"])
        assert item is not None
        assert item.price_cents == 900
        assert item.version >= 2
        audits = s.query(AuditLog).filter(AuditLog.action == "bar.menu.item.update", AuditLog.entity_id == str(seed["item_a"])).count()
        assert audits >= 1
    finally:
        s.close()


def test_degraded_blocks_price_changes():
    seed = _seed_partner(role="manager")
    client = TestClient(app)
    _set_runtime_state(seed["event_id"], "DEGRADED")

    blocked = client.put(
        f"/partner/portal/bar/events/{seed['event_id']}/menu/items/{seed['item_a']}",
        headers={"Authorization": f"Bearer {seed['token']}", "Idempotency-Key": "menu-put-degraded"},
        json={"priceTickets": 10},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "EVENT_DEGRADED_PRICE_BLOCKED"


def test_bulk_availability_works():
    seed = _seed_partner(role="bartender")
    client = TestClient(app)

    res = client.post(
        f"/partner/portal/bar/events/{seed['event_id']}/menu/bulk",
        headers={"Authorization": f"Bearer {seed['token']}", "Idempotency-Key": "menu-bulk-avail"},
        json={"itemIds": [seed["item_a"], seed["item_b"]], "op": {"setAvailable": False, "setStockStatus": "OUT"}},
    )
    assert res.status_code == 200
    assert res.json()["updatedCount"] == 2

    s = get_session()
    try:
        first = s.get(MenuItem, seed["item_a"])
        second = s.get(MenuItem, seed["item_b"])
        assert first is not None and second is not None
        assert first.is_available is False and second.is_available is False
        assert first.stock_status == "OUT" and second.stock_status == "OUT"
    finally:
        s.close()


def test_export_csv_columns_present():
    seed = _seed_partner(role="manager")
    client = TestClient(app)

    res = client.get(
        f"/partner/portal/bar/events/{seed['event_id']}/menu/export.csv",
        headers={"Authorization": f"Bearer {seed['token']}"},
    )
    assert res.status_code == 200
    body = res.text.splitlines()
    assert body
    assert body[0] == "id,name,category,priceTickets,available,stockStatus,lastPriceChangeAt,version"


def test_user_event_menu_exposes_stock_fields():
    seed = _seed_partner(role="manager")
    client = TestClient(app)

    res = client.get(f"/events/{seed['event_id']}/menu")
    assert res.status_code == 200
    payload = res.json()
    assert len(payload) >= 1

    row = payload[0]
    assert 'priceTickets' in row
    assert 'available' in row
    assert 'stockStatus' in row
