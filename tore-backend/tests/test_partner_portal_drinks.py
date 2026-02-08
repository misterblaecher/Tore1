from fastapi.testclient import TestClient

import secrets

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, Drink, EventDrink, PartnerUser, PartnerMembership
from partner_auth import _make_token


def _seed_partner_event(role: str = "manager"):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(
            name=f"Test Bar {suffix}",
            city="Test City",
            partner_code=f"TEST{suffix}",
        )
        s.add(bar)
        s.flush()

        event = Event(bar_id=bar.id, name="Test Event")
        s.add(event)
        s.flush()

        user = PartnerUser(display_name="Partner User", pin_hash="hash")
        s.add(user)
        s.flush()

        membership = PartnerMembership(
            user_id=user.id,
            bar_id=bar.id,
            role=role,
            display_name="Partner User",
        )
        s.add(membership)
        s.commit()

        token = _make_token(user.id, bar.id, role, "Partner User")
        return event.id, bar.id, token
    finally:
        s.close()


def test_partner_portal_requires_token():
    event_id, _, _ = _seed_partner_event()
    client = TestClient(app)
    res = client.get(f"/partner/portal/events/{event_id}/drinks")
    assert res.status_code == 401


def test_partner_portal_rejects_bar_mismatch():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar_a = Bar(
            name="Bar A",
            city="City A",
            partner_code=f"TESTA{suffix}",
        )
        bar_b = Bar(
            name="Bar B",
            city="City B",
            partner_code=f"TESTB{suffix}",
        )
        s.add_all([bar_a, bar_b])
        s.flush()

        event = Event(bar_id=bar_a.id, name="Event A")
        s.add(event)
        s.flush()

        user = PartnerUser(display_name="Other User", pin_hash="hash")
        s.add(user)
        s.flush()

        membership = PartnerMembership(
            user_id=user.id,
            bar_id=bar_b.id,
            role="manager",
            display_name="Other User",
        )
        s.add(membership)
        s.commit()

        token = _make_token(user.id, bar_b.id, "manager", "Other User")
        event_id = event.id
    finally:
        s.close()

    client = TestClient(app)
    res = client.get(
        f"/partner/portal/events/{event_id}/drinks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_manager_can_post_and_delete_drink():
    event_id, _, token = _seed_partner_event(role="manager")
    client = TestClient(app)

    create_res = client.post(
        f"/partner/portal/events/{event_id}/drinks",
        json={
            "name": "Test Drink",
            "type": "beer",
            "base_price_cents": 300,
            "override_price_cents": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_res.status_code == 200
    drink_id = create_res.json()["drink_id"]

    delete_res = client.delete(
        f"/partner/portal/events/{event_id}/drinks/{drink_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_res.status_code == 200
    assert delete_res.json()["ok"] is True


def test_get_drinks_returns_expected_list():
    event_id, _, token = _seed_partner_event()
    s = get_session()
    try:
        drink = Drink(name="Cola", type="soft")
        s.add(drink)
        s.flush()
        s.add(
            EventDrink(
                event_id=event_id,
                drink_id=drink.id,
                base_price_cents=200,
                current_price_cents=200,
                override_price_cents=None,
                last_price_update=now_utc(),
            )
        )
        s.commit()
    finally:
        s.close()

    client = TestClient(app)
    res = client.get(
        f"/partner/portal/events/{event_id}/drinks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    payload = res.json()
    assert len(payload) == 1
    assert payload[0] == {
        "drink_id": payload[0]["drink_id"],
        "name": "Cola",
        "type": "soft",
        "base_price_cents": 200,
        "current_price_cents": 200,
        "override_price_cents": None,
    }
