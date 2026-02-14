import json
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import Bar, Event, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_partner(role: str = "manager"):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Market Bar {suffix}", city="Liège", partner_code=f"MKT{suffix}")
        s.add(bar)
        s.flush()
        event = Event(bar_id=bar.id, name="Market Event")
        s.add(event)
        s.flush()
        user = PartnerUser(display_name=f"{role} user", pin_hash="hash")
        s.add(user)
        s.flush()
        s.add(
            PartnerMembership(
                user_id=user.id,
                bar_id=bar.id,
                role=role,
                display_name=f"{role} user",
            )
        )
        s.commit()
        token = _make_token(user.id, bar.id, role, f"{role} user")
        return bar.id, event.id, token
    finally:
        s.close()


def _add_member(bar_id: int, role: str):
    s = get_session()
    try:
        user = PartnerUser(display_name=f"{role} user", pin_hash="hash")
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar_id, role=role, display_name=f"{role} user"))
        s.commit()
        return _make_token(user.id, bar_id, role, f"{role} user")
    finally:
        s.close()


def test_manager_create_config_item_and_set_price():
    bar_id, event_id, token = _seed_partner("manager")
    client = TestClient(app)

    cfg = client.post(
        "/partner/portal/market/config",
        json={"event_id": event_id, "is_live": True, "price_floor_cents": 100, "price_cap_cents": 1000, "step_cents": 50},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cfg.status_code == 200
    assert cfg.json()["is_live"] is True

    item = client.post(
        "/partner/portal/market/items",
        json={"event_id": event_id, "name": "Jupiler", "base_price_cents": 255, "unit": "beer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert item.status_code == 200
    item_id = item.json()["id"]

    tick = client.post(
        f"/partner/portal/market/items/{item_id}/price",
        json={"price_cents": 410},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert tick.status_code == 200
    assert tick.json()["item"]["current_price_cents"] == 400

    public = client.get(f"/market/public?bar_id={bar_id}&event_id={event_id}")
    assert public.status_code == 200
    assert len(public.json()["items"]) == 1


def test_staff_can_set_price_but_cannot_create_config_or_items():
    bar_id, _, manager_token = _seed_partner("manager")
    staff_token = _add_member(bar_id, "staff")
    client = TestClient(app)

    cfg = client.post(
        "/partner/portal/market/config",
        json={"is_live": True},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert cfg.status_code == 403

    manager_cfg = client.post(
        "/partner/portal/market/config",
        json={"is_live": True},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert manager_cfg.status_code == 200

    create_by_staff = client.post(
        "/partner/portal/market/items",
        json={"name": "Shot vodka", "base_price_cents": 300},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert create_by_staff.status_code == 403

    manager_item = client.post(
        "/partner/portal/market/items",
        json={"name": "Shot vodka", "base_price_cents": 300},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert manager_item.status_code == 200
    item_id = manager_item.json()["id"]

    set_price = client.post(
        f"/partner/portal/market/items/{item_id}/price",
        json={"price_cents": 360},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert set_price.status_code == 200

    set_by_staff = client.post(
        f"/partner/portal/market/items/{item_id}/price",
        json={"price_cents": 390},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert set_by_staff.status_code == 200

    public = client.get(f"/market/public?bar_id={bar_id}")
    assert public.status_code == 200


def test_bar_mismatch_returns_403():
    _, _, manager_token = _seed_partner("manager")
    _, _, other_manager = _seed_partner("manager")
    client = TestClient(app)

    manager_cfg = client.post(
        "/partner/portal/market/config",
        json={"is_live": True},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert manager_cfg.status_code == 200
    manager_item = client.post(
        "/partner/portal/market/items",
        json={"name": "IPA", "base_price_cents": 280},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert manager_item.status_code == 200
    item_id = manager_item.json()["id"]

    denied = client.post(
        f"/partner/portal/market/items/{item_id}/price",
        json={"price_cents": 300},
        headers={"Authorization": f"Bearer {other_manager}"},
    )
    assert denied.status_code == 403


def test_public_history_and_idempotency():
    bar_id, _, token = _seed_partner("manager")
    client = TestClient(app)

    cfg = client.post(
        "/partner/portal/market/config",
        json={"is_live": True, "price_floor_cents": 100, "price_cap_cents": 1000, "step_cents": 50},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cfg.status_code == 200

    item = client.post(
        "/partner/portal/market/items",
        json={"name": "Soft", "base_price_cents": 200},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert item.status_code == 200
    item_id = item.json()["id"]

    one = client.post(
        f"/partner/portal/market/items/{item_id}/price",
        json={"price_cents": 370, "idempotency_key": "same-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    two = client.post(
        f"/partner/portal/market/items/{item_id}/price",
        json={"price_cents": 370, "idempotency_key": "same-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert one.status_code == 200
    assert two.status_code == 200
    assert one.json()["tick"]["id"] == two.json()["tick"]["id"]

    market = client.get(f"/market/public?bar_id={bar_id}")
    assert market.status_code == 200
    assert len(market.json()["items"]) == 1
    assert len(market.json()["ticker"]) >= 1

    history = client.get(f"/market/public/items/{item_id}")
    assert history.status_code == 200
    assert len(history.json()["history"]) >= 2


def test_public_stream_endpoint_exists_and_content_type():
    bar_id, _, token = _seed_partner("manager")
    client = TestClient(app)

    cfg = client.post(
        "/partner/portal/market/config",
        json={"is_live": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cfg.status_code == 200
    item = client.post(
        "/partner/portal/market/items",
        json={"name": "Pils", "base_price_cents": 200},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert item.status_code == 200

    with client.stream("GET", f"/market/public/stream?bar_id={bar_id}&once=true") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")


def test_public_stream_emits_tick():
    bar_id, _, token = _seed_partner("manager")
    client = TestClient(app)

    cfg = client.post(
        "/partner/portal/market/config",
        json={"is_live": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cfg.status_code == 200
    item = client.post(
        "/partner/portal/market/items",
        json={"name": "Mate", "base_price_cents": 250},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert item.status_code == 200

    set_price = client.post(
        f"/partner/portal/market/items/{item.json()['id']}/price",
        json={"price_cents": 310},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert set_price.status_code == 200

    with client.stream("GET", f"/market/public/stream?bar_id={bar_id}&once=true") as response:
        assert response.status_code == 200
        prices = []
        current_event = ""
        for line in response.iter_lines():
            if not line:
                continue
            if line.startswith("event: "):
                current_event = line.removeprefix("event: ")
                continue
            if line.startswith("data: ") and current_event == "tick":
                payload = json.loads(line.removeprefix("data: "))
                if payload["item_id"] == item.json()["id"]:
                    prices.append(payload["price_cents"])

        assert set_price.json()["item"]["current_price_cents"] in prices
