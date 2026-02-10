from fastapi.testclient import TestClient

import secrets

from db import Base, engine, get_session
from main import app
from models import Bar, Event, MenuCategory, MenuItem, Order, PartnerMembership, PartnerUser, WalletTx
from partner_auth import _make_token


def _seed_partner_user(role: str = "manager"):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Orders Bar {suffix}", city="Test City", partner_code=f"ORD{suffix}")
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name="Orders User", pin_hash="hash")
        s.add(user)
        s.flush()
        membership = PartnerMembership(user_id=user.id, bar_id=bar.id, role=role, display_name="Orders User")
        s.add(membership)
        s.commit()
        token = _make_token(user.id, bar.id, role, "Orders User")
        return bar.id, token
    finally:
        s.close()


def _seed_menu_item(bar_id: int):
    s = get_session()
    try:
        category = MenuCategory(bar_id=bar_id, name="Cocktails", sort_order=1)
        s.add(category)
        s.flush()
        item = MenuItem(bar_id=bar_id, category_id=category.id, name="Spritz", description="Aperitivo", price_cents=900)
        s.add(item)
        s.commit()
        return item.id
    finally:
        s.close()




def _seed_event(bar_id: int, ticket_value_cents: int = 100):
    s = get_session()
    try:
        event = Event(bar_id=bar_id, name="Order Event", ticket_value_cents=ticket_value_cents)
        s.add(event)
        s.commit()
        return event.id
    finally:
        s.close()


def _create_guest_user(client: TestClient) -> tuple[str, str]:
    res = client.post("/auth/guest", json={"display_name": "Order Guest"})
    assert res.status_code == 200
    payload = res.json()
    return payload["user"]["id"], payload["token"]


def _topup_wallet(client: TestClient, manager_token: str, user_id: str, amount_tickets: int):
    res = client.post(
        "/wallet/topup",
        json={
            "user_id": user_id,
            "amount_tickets": amount_tickets,
            "idempotency_key": secrets.token_hex(8),
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert res.status_code == 200

def test_create_order_ok_and_snapshot():
    bar_id, _ = _seed_partner_user()
    item_id = _seed_menu_item(bar_id)
    client = TestClient(app)

    res = client.post(
        "/orders",
        json={
            "bar_id": bar_id,
            "items": [{"item_id": item_id, "qty": 2}],
            "note": "Sans glace",
            "device_id": "device-a",
            "idempotency_key": "idem-1",
        },
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "NEW"
    assert payload["items"][0]["name_snapshot"] == "Spritz"
    assert payload["items"][0]["price_cents_snapshot"] == 900
    assert payload["items"][0]["line_total_cents"] == 1800

    fetched = client.get(f"/orders/{payload['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == payload["id"]


def test_idempotency_prevents_duplicates():
    bar_id, token = _seed_partner_user()
    item_id = _seed_menu_item(bar_id)
    client = TestClient(app)

    body = {
        "bar_id": bar_id,
        "items": [{"item_id": item_id, "qty": 1}],
        "device_id": "device-same",
        "idempotency_key": "idem-dup",
    }
    first = client.post("/orders", json=body, headers={"Authorization": f"Bearer {token}"})
    second = client.post("/orders", json=body, headers={"Authorization": f"Bearer {token}"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    s = get_session()
    try:
        count = s.query(Order).filter(Order.bar_id == bar_id, Order.idempotency_key == "idem-dup").count()
        assert count == 1
    finally:
        s.close()


def test_staff_can_update_status_and_unauthorized_blocked():
    bar_id, token = _seed_partner_user(role="bartender")
    item_id = _seed_menu_item(bar_id)
    _, other_token = _seed_partner_user(role="manager")
    client = TestClient(app)

    created = client.post(
        "/orders",
        json={
            "bar_id": bar_id,
            "items": [{"item_id": item_id, "qty": 1}],
            "device_id": "device-status",
            "idempotency_key": "idem-status",
        },
    )
    order_id = created.json()["id"]

    unauthorized = client.patch(f"/partner/portal/orders/{order_id}/status", json={"status": "IN_PROGRESS"})
    assert unauthorized.status_code == 401

    forbidden = client.patch(
        f"/partner/portal/orders/{order_id}/status",
        json={"status": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden.status_code == 403

    ok_1 = client.patch(
        f"/partner/portal/orders/{order_id}/status",
        json={"status": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok_1.status_code == 200
    assert ok_1.json()["status"] == "IN_PROGRESS"

    ok_2 = client.patch(
        f"/partner/portal/orders/{order_id}/status",
        json={"status": "READY"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok_2.status_code == 200
    assert ok_2.json()["status"] == "READY"


def test_create_order_tickets_debits_wallet_and_creates_tx():
    bar_id, manager_token = _seed_partner_user()
    item_id = _seed_menu_item(bar_id)
    event_id = _seed_event(bar_id, ticket_value_cents=100)
    client = TestClient(app)
    user_id, user_token = _create_guest_user(client)
    _topup_wallet(client, manager_token, user_id, amount_tickets=30)

    res = client.post(
        "/orders",
        json={
            "bar_id": bar_id,
            "event_id": event_id,
            "items": [{"item_id": item_id, "qty": 2}],
            "payment_mode": "tickets",
            "idempotency_key": "idem-ticket-paid",
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["payment_status"] == "PAID"
    assert payload["total_cents"] == 1800
    assert payload["total_tickets"] == 18

    me = client.get("/wallet/me", headers={"Authorization": f"Bearer {user_token}"})
    assert me.status_code == 200
    wallet = me.json()
    assert wallet["balance_tickets"] == 12
    assert any(tx["kind"] == "ORDER_PAYMENT" and tx["amount_tickets"] == -18 for tx in wallet["transactions"])

    s = get_session()
    try:
        tx = (
            s.query(WalletTx)
            .filter(WalletTx.user_id == user_id, WalletTx.kind == "ORDER_PAYMENT", WalletTx.ref_id == str(payload["id"]))
            .first()
        )
        assert tx is not None
    finally:
        s.close()


def test_create_order_tickets_insufficient_balance_returns_400():
    bar_id, manager_token = _seed_partner_user()
    item_id = _seed_menu_item(bar_id)
    event_id = _seed_event(bar_id, ticket_value_cents=100)
    client = TestClient(app)
    user_id, user_token = _create_guest_user(client)
    _topup_wallet(client, manager_token, user_id, amount_tickets=5)

    res = client.post(
        "/orders",
        json={
            "bar_id": bar_id,
            "event_id": event_id,
            "items": [{"item_id": item_id, "qty": 1}],
            "payment_mode": "tickets",
            "idempotency_key": "idem-ticket-insufficient",
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert res.status_code == 400
    assert "Insufficient wallet balance" in res.json()["detail"]


def test_create_order_pay_later_sets_unpaid():
    bar_id, _ = _seed_partner_user()
    item_id = _seed_menu_item(bar_id)
    client = TestClient(app)

    res = client.post(
        "/orders",
        json={
            "bar_id": bar_id,
            "items": [{"item_id": item_id, "qty": 1}],
            "payment_mode": "pay_later",
            "device_id": "device-pay-later",
            "idempotency_key": "idem-pay-later",
        },
    )
    assert res.status_code == 200
    assert res.json()["payment_status"] == "UNPAID"
