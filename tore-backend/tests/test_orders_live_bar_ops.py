from fastapi.testclient import TestClient

import secrets

from db import Base, engine, get_session
from main import app
from models import AuditLog, Bar, Event, EventRuntimeState, MenuCategory, MenuItem, Order, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_partner(role: str = "manager"):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Bar Ops {suffix}", city="Paris", partner_code=f"BO{suffix}")
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name="Staff", pin_hash="hash")
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role=role, display_name="Staff"))
        s.commit()
        return bar.id, _make_token(user.id, bar.id, role, "Staff")
    finally:
        s.close()


def _seed_item(bar_id: int) -> int:
    s = get_session()
    try:
        cat = MenuCategory(bar_id=bar_id, name="Drinks", sort_order=1)
        s.add(cat)
        s.flush()
        item = MenuItem(bar_id=bar_id, category_id=cat.id, name="IPA", price_cents=600)
        s.add(item)
        s.commit()
        return item.id
    finally:
        s.close()


def _seed_event(bar_id: int) -> int:
    s = get_session()
    try:
        event = Event(bar_id=bar_id, name="Night")
        s.add(event)
        s.commit()
        return event.id
    finally:
        s.close()


def _make_order(client: TestClient, bar_id: int, event_id: int, item_id: int, idem: str) -> int:
    res = client.post(
        "/orders",
        json={
            "bar_id": bar_id,
            "event_id": event_id,
            "items": [{"item_id": item_id, "qty": 1}],
            "device_id": f"dev-{idem}",
            "idempotency_key": idem,
        },
    )
    assert res.status_code == 200
    return res.json()["id"]


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


def test_orders_live_list_and_bar_ops_flow():
    bar_id, token = _seed_partner(role="bartender")
    item_id = _seed_item(bar_id)
    event_id = _seed_event(bar_id)
    client = TestClient(app)

    order_id = _make_order(client, bar_id, event_id, item_id, "live-flow-1")

    listed = client.get(
        f"/partner/portal/bar/events/{event_id}/orders/live?status=pending",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    assert any(row["id"] == order_id and row["status"] == "pending" for row in listed.json()["items"])

    accept = client.post(
        f"/partner/portal/bar/orders/{order_id}/accept",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-accept-1"},
        json={"reason": "start"},
    )
    assert accept.status_code == 200
    assert accept.json()["status"] == "preparing"

    ready = client.post(
        f"/partner/portal/bar/orders/{order_id}/ready",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-ready-1"},
    )
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"

    claim = client.post(
        f"/partner/portal/bar/orders/{order_id}/claim",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-claim-1"},
    )
    assert claim.status_code == 200
    assert claim.json()["status"] == "claimed"


def test_accept_idempotent_and_conflict_409():
    bar_id, token = _seed_partner(role="manager")
    item_id = _seed_item(bar_id)
    event_id = _seed_event(bar_id)
    client = TestClient(app)

    order_id = _make_order(client, bar_id, event_id, item_id, "live-idem-1")

    first = client.post(
        f"/partner/portal/bar/orders/{order_id}/accept",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-accept-same"},
        json={},
    )
    second = client.post(
        f"/partner/portal/bar/orders/{order_id}/accept",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-accept-same"},
        json={},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == second.json()["status"]

    conflict = client.post(
        f"/partner/portal/bar/orders/{order_id}/accept",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-accept-other"},
        json={},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "ORDER_STATE_CONFLICT"


def test_cancel_requires_reason_permissions_and_runtime_guards():
    bar_id, token = _seed_partner(role="bartender")
    item_id = _seed_item(bar_id)
    event_id = _seed_event(bar_id)
    client = TestClient(app)

    order_id = _make_order(client, bar_id, event_id, item_id, "cancel-1")

    missing_reason = client.post(
        f"/partner/portal/bar/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-cancel-1"},
        json={},
    )
    assert missing_reason.status_code == 422

    _set_runtime_state(event_id, "DEGRADED")
    blocked = client.post(
        f"/partner/portal/bar/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-cancel-2"},
        json={"reason": "no stock"},
    )
    assert blocked.status_code == 403

    _set_runtime_state(event_id, "LIVE")
    canceled = client.post(
        f"/partner/portal/bar/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-cancel-3"},
        json={"reason": "no stock"},
    )
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"

    viewer_bar_id, viewer_token = _seed_partner(role="bartender")
    assert viewer_bar_id != bar_id
    forbidden = client.get(
        f"/partner/portal/bar/events/{event_id}/orders/live?status=all",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert forbidden.status_code == 403

    s = get_session()
    try:
        audits = s.query(AuditLog).filter(AuditLog.entity_id == str(order_id), AuditLog.action.like("orders.live.%")).count()
        assert audits >= 1
        row = s.get(Order, order_id)
        assert row is not None
        assert row.status == "CANCELLED"
    finally:
        s.close()
