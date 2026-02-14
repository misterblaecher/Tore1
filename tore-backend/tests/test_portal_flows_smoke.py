import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AppUser, Bar, DrinkMarketConfig, DrinkMarketItem, EventStaff, MenuCategory, MenuItem, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Smoke {suffix}", city="City", partner_code=f"SMK{suffix}")
        s.add(bar)
        s.flush()
        manager = PartnerUser(display_name="Manager", pin_hash="hash")
        s.add(manager)
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role="manager", display_name="Manager"))
        s.commit()
        return bar.id, _make_token(manager.id, bar.id, "manager", "Manager")
    finally:
        s.close()


def test_portal_critical_flow_smoke():
    bar_id, manager_token = _seed_manager()
    client = TestClient(app)

    create_event = client.post(
        "/partner/portal/events",
        json={
            "name": "Smoke Event",
            "starts_at": now_utc().isoformat(),
            "ends_at": (now_utc() + timedelta(hours=6)).isoformat(),
            "entry_price_cents": 0,
            "ticket_mode": True,
            "ticket_value_cents": 100,
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert create_event.status_code == 200
    event_id = create_event.json()["id"]

    modules = client.post(
        f"/partner/portal/event/{event_id}/modules",
        json={"entry_enabled": True, "orders_enabled": True, "market_enabled": True, "polymarket_enabled": True},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert modules.status_code == 200

    guest = client.post("/auth/guest", json={"display_name": "Flow User"})
    user_id = guest.json()["user"]["id"]
    user_token = guest.json()["token"]

    s = get_session()
    try:
        category = MenuCategory(bar_id=bar_id, name="Beer")
        s.add(category)
        s.flush()
        menu = MenuItem(bar_id=bar_id, category_id=category.id, name="Pils", price_cents=200, is_active=True, is_available=True)

        s.add(EventStaff(event_id=event_id, user_id=user_id, role="admin"))
        s.add(menu)
        s.flush()
        cfg = DrinkMarketConfig(bar_id=bar_id, event_id=event_id, is_live=True, ticket_value_cents=100)
        s.add(cfg)
        s.flush()
        market_item = DrinkMarketItem(config_id=cfg.id, name="Pils", is_active=True, base_price_cents=200, current_price_cents=200)
        s.add(market_item)
        s.commit()
        menu_id = menu.id
        market_item_id = market_item.id
    finally:
        s.close()

    issue = client.post(
        "/entry/tokens/issue",
        json={"event_id": event_id, "count": 1, "user_id": user_id},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    token = issue.json()["issued"][0]["token"]

    scan = client.post(
        "/entry/scan",
        json={"event_id": event_id, "token": token, "scan_id": "smoke-scan"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert scan.status_code == 200
    assert scan.json()["decision"] == "ACCEPT"

    topup = client.post(
        "/partner/portal/wallet/admin/topup",
        json={"event_id": event_id, "user_id": user_id, "amount_tickets": 20, "reason": "smoke", "idempotency_key": "smoke-topup"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert topup.status_code == 200

    order = client.post(
        "/orders",
        json={
            "bar_id": bar_id,
            "event_id": event_id,
            "user_id": user_id,
            "items": [{"item_id": menu_id, "qty": 1, "market_item_id": market_item_id}],
            "payment_mode": "tickets",
            "idempotency_key": "smoke-order",
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert order.status_code == 200
    order_id = order.json()["id"]

    for status in ["IN_PROGRESS", "READY", "SERVED"]:
        step = client.patch(
            f"/partner/portal/orders/{order_id}/status",
            json={"status": status},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert step.status_code == 200

    ticks = client.get(f"/market/public/items/{market_item_id}")
    assert ticks.status_code == 200
    assert len(ticks.json()["history"]) >= 1

    bet = client.post(
        "/polymarket/bets",
        json={
            "scope": "EVENT",
            "event_id": event_id,
            "question": "Smoke?",
            "kind": "OBJECTIVE",
            "deadline_at": (now_utc() + timedelta(minutes=20)).isoformat(),
            "resolver_user_id": user_id,
            "rules_text": "rules",
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert bet.status_code == 200
    bet_id = bet.json()["id"]

    resolve = client.post(
        f"/polymarket/bets/{bet_id}/resolve",
        json={"outcome": "YES", "reason": "done"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resolve.status_code == 200

    disputer = client.post("/auth/guest", json={"display_name": "Disputer"})
    dispute = client.post(
        f"/polymarket/bets/{bet_id}/dispute",
        json={"reason": "challenge"},
        headers={"Authorization": f"Bearer {disputer.json()['token']}"},
    )
    assert dispute.status_code == 200

    finalize = client.post(
        f"/polymarket/bets/{bet_id}/finalize",
        json={},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert finalize.status_code in {400, 403}
    assert "dispute" in finalize.json().get("detail", "").lower()
