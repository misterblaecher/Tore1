import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import (
    Bar,
    DrinkMarketConfig,
    DrinkMarketItem,
    DrinkPriceTick,
    Event,
    MenuCategory,
    MenuItem,
    Order,
    PartnerMembership,
    PartnerUser,
)
from partner_auth import _make_token


def _seed_partner(role: str = "manager") -> tuple[int, str]:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Market V2 Bar {suffix}", city="Liège", partner_code=f"MKTV2{suffix}")
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name=f"{role} user", pin_hash="hash")
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role=role, display_name=f"{role} user"))
        s.commit()
        return bar.id, _make_token(user.id, bar.id, role, f"{role} user")
    finally:
        s.close()


def _seed_menu_item(bar_id: int, name: str = "Spritz") -> int:
    s = get_session()
    try:
        category = MenuCategory(bar_id=bar_id, name="Cocktails", sort_order=1)
        s.add(category)
        s.flush()
        item = MenuItem(bar_id=bar_id, category_id=category.id, name=name, description="Aperitivo", price_cents=900)
        s.add(item)
        s.commit()
        return item.id
    finally:
        s.close()


def _seed_event(bar_id: int) -> int:
    s = get_session()
    try:
        event = Event(bar_id=bar_id, name="Market V2 Event")
        s.add(event)
        s.commit()
        return event.id
    finally:
        s.close()


def _seed_market(bar_id: int, event_id: int | None, *, is_live: bool, item_name: str) -> tuple[int, int]:
    s = get_session()
    try:
        config = DrinkMarketConfig(
            bar_id=bar_id,
            event_id=event_id,
            is_live=is_live,
            price_floor_cents=100,
            price_cap_cents=1000,
            step_cents=50,
        )
        s.add(config)
        s.flush()
        item = DrinkMarketItem(
            config_id=config.id,
            name=item_name,
            is_active=True,
            base_price_cents=200,
            current_price_cents=200,
            unit="unit",
            sort_order=0,
        )
        s.add(item)
        s.commit()
        return config.id, item.id
    finally:
        s.close()


def _mark_order_paid(order_id: int) -> None:
    s = get_session()
    try:
        order = s.get(Order, order_id)
        assert order is not None
        order.payment_status = "PAID"
        s.commit()
    finally:
        s.close()


def _patch_to_served(client: TestClient, token: str, order_id: int):
    for status in ("IN_PROGRESS", "READY", "SERVED"):
        res = client.patch(
            f"/partner/portal/orders/{order_id}/status",
            json={"status": status},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200


def test_served_paid_order_updates_market_and_is_idempotent():
    bar_id, token = _seed_partner()
    event_id = _seed_event(bar_id)
    item_id = _seed_menu_item(bar_id, name="Spritz")
    _, market_item_id = _seed_market(bar_id, event_id, is_live=True, item_name="Spritz")
    client = TestClient(app)

    created = client.post(
        "/orders",
        json={
            "bar_id": bar_id,
            "event_id": event_id,
            "items": [{"item_id": item_id, "qty": 1}],
            "device_id": "device-market-v2",
            "idempotency_key": "idem-market-v2-live",
        },
    )
    assert created.status_code == 200
    order_id = created.json()["id"]
    _mark_order_paid(order_id)

    _patch_to_served(client, token, order_id)

    again = client.patch(
        f"/partner/portal/orders/{order_id}/status",
        json={"status": "SERVED"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert again.status_code == 200

    s = get_session()
    try:
        market_item = s.get(DrinkMarketItem, market_item_id)
        assert market_item is not None
        assert market_item.current_price_cents == 250
        order_ticks = (
            s.query(DrinkPriceTick)
            .filter(DrinkPriceTick.item_id == market_item.id, DrinkPriceTick.source == "order")
            .all()
        )
        assert len(order_ticks) == 1
        assert order_ticks[0].ref_order_id == order_id
    finally:
        s.close()


def test_served_order_does_not_tick_market_when_config_not_live():
    bar_id, token = _seed_partner()
    event_id = _seed_event(bar_id)
    item_id = _seed_menu_item(bar_id, name="Mojito")
    _, market_item_id = _seed_market(bar_id, event_id, is_live=False, item_name="Mojito")
    client = TestClient(app)

    created = client.post(
        "/orders",
        json={
            "bar_id": bar_id,
            "event_id": event_id,
            "items": [{"item_id": item_id, "qty": 1}],
            "device_id": "device-market-v2-not-live",
            "idempotency_key": "idem-market-v2-not-live",
        },
    )
    assert created.status_code == 200
    order_id = created.json()["id"]
    _mark_order_paid(order_id)

    _patch_to_served(client, token, order_id)

    s = get_session()
    try:
        market_item = s.get(DrinkMarketItem, market_item_id)
        assert market_item is not None
        assert market_item.current_price_cents == 200
        ticks = (
            s.query(DrinkPriceTick)
            .filter(DrinkPriceTick.item_id == market_item.id, DrinkPriceTick.source == "order")
            .count()
        )
        assert ticks == 0
    finally:
        s.close()


def test_served_order_scales_market_impact_by_line_quantity():
    bar_id, token = _seed_partner()
    event_id = _seed_event(bar_id)
    item_id = _seed_menu_item(bar_id, name="Negroni")
    _, market_item_id = _seed_market(bar_id, event_id, is_live=True, item_name="Negroni")
    client = TestClient(app)

    created = client.post(
        "/orders",
        json={
            "bar_id": bar_id,
            "event_id": event_id,
            "items": [{"item_id": item_id, "qty": 3}],
            "device_id": "device-market-v2-qty",
            "idempotency_key": "idem-market-v2-qty",
        },
    )
    assert created.status_code == 200
    order_id = created.json()["id"]
    _mark_order_paid(order_id)

    _patch_to_served(client, token, order_id)

    s = get_session()
    try:
        market_item = s.get(DrinkMarketItem, market_item_id)
        assert market_item is not None
        assert market_item.current_price_cents == 350
        order_ticks = (
            s.query(DrinkPriceTick)
            .filter(DrinkPriceTick.item_id == market_item.id, DrinkPriceTick.source == "order")
            .all()
        )
        assert len(order_ticks) == 1
        assert order_ticks[0].price_cents == 350
        assert order_ticks[0].ref_order_id == order_id
    finally:
        s.close()
