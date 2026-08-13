from datetime import timedelta

from fastapi.testclient import TestClient

import secrets

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, PartnerUser, PartnerMembership
from partner_auth import _make_token


def _seed_partner_user(role: str = "manager"):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(
            name=f"Portal Bar {suffix}",
            city="Test City",
            partner_code=f"PORTAL{suffix}",
        )
        s.add(bar)
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
        return bar.id, token
    finally:
        s.close()


def _create_event(bar_id: int, name: str = "Event") -> int:
    s = get_session()
    try:
        event = Event(
            bar_id=bar_id,
            name=name,
            starts_at=now_utc(),
            ends_at=now_utc() + timedelta(hours=4),
            entry_price_cents=500,
            ticket_mode=True,
        )
        s.add(event)
        s.commit()
        s.refresh(event)
        return event.id
    finally:
        s.close()


def test_partner_portal_event_create_requires_token():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    res = client.post("/partner/portal/events", json={"name": "Event"})
    assert res.status_code == 401


def test_partner_portal_event_create_rejects_non_manager():
    _, token = _seed_partner_user(role="bartender")
    client = TestClient(app)
    res = client.post(
        "/partner/portal/events",
        json={"name": "Event"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_partner_portal_event_create_and_list():
    bar_id, token = _seed_partner_user(role="manager")
    client = TestClient(app)

    starts_at = now_utc()
    ends_at = starts_at + timedelta(hours=2)
    res = client.post(
        "/partner/portal/events",
        json={
            "name": "Launch Night",
            "start_at": starts_at.isoformat(),
            "end_at": ends_at.isoformat(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["id"]
    assert payload["bar_id"] == bar_id
    assert payload["name"] == "Launch Night"

    s = get_session()
    try:
        event = s.get(Event, payload["id"])
        assert event is not None
        assert event.bar_id == bar_id
    finally:
        s.close()

    list_res = client.get(
        "/partner/portal/events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_res.status_code == 200
    events = list_res.json()
    assert any(event_row["id"] == payload["id"] for event_row in events)


def test_partner_portal_event_patch_requires_token():
    bar_id, _ = _seed_partner_user(role="manager")
    event_id = _create_event(bar_id)
    client = TestClient(app)
    res = client.patch(f"/partner/portal/events/{event_id}", json={"name": "New"})
    assert res.status_code == 401


def test_partner_portal_event_patch_rejects_non_manager():
    bar_id, token = _seed_partner_user(role="bartender")
    event_id = _create_event(bar_id)
    client = TestClient(app)
    res = client.patch(
        f"/partner/portal/events/{event_id}",
        json={"name": "New"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_partner_portal_event_patch_rejects_other_bar():
    bar_id, _ = _seed_partner_user(role="manager")
    other_bar_id, other_token = _seed_partner_user(role="manager")
    event_id = _create_event(bar_id)
    client = TestClient(app)
    res = client.patch(
        f"/partner/portal/events/{event_id}",
        json={"name": "New"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert res.status_code == 403
    assert bar_id != other_bar_id


def test_partner_portal_event_patch_ok():
    bar_id, token = _seed_partner_user(role="manager")
    event_id = _create_event(bar_id)
    client = TestClient(app)
    res = client.patch(
        f"/partner/portal/events/{event_id}",
        json={
            "name": "After Party",
            "entry_price_cents": 900,
            "tickets_enabled": False,
            "entry_enabled": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["name"] == "After Party"
    assert payload["entry_price_cents"] == 900
    assert payload["tickets_enabled"] is False
    assert payload["entry_enabled"] is True

    s = get_session()
    try:
        event = s.get(Event, event_id)
        assert event is not None
        assert event.name == "After Party"
        assert event.entry_price_cents == 900
        assert event.ticket_mode is False
    finally:
        s.close()


def test_partner_portal_event_patch_partial():
    bar_id, token = _seed_partner_user(role="manager")
    event_id = _create_event(bar_id, name="Original")
    client = TestClient(app)
    res = client.patch(
        f"/partner/portal/events/{event_id}",
        json={"name": "Renamed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["name"] == "Renamed"

    s = get_session()
    try:
        event = s.get(Event, event_id)
        assert event is not None
        assert event.name == "Renamed"
        assert event.entry_price_cents == 500
        assert event.ticket_mode is True
    finally:
        s.close()


def test_partner_manager_writes_public_bar_and_event_content():
    bar_id, token = _seed_partner_user(role="manager")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    bar_response = client.patch(
        "/partner/portal/bar",
        json={
            "public_description": "Un lieu ouvert à tous.",
            "logo_url": "https://cdn.tore.be/bar-logo.png",
            "banner_url": "https://cdn.tore.be/bar-banner.jpg",
            "primary_color": "#ba1733",
            "secondary_color": "#f4c430",
            "address": "12 quai TORÈ",
            "public_modules": {"menu": True, "wallet": False},
        },
        headers=headers,
    )
    assert bar_response.status_code == 200
    assert bar_response.json()["primary_color"] == "#BA1733"

    event_response = client.post(
        "/partner/portal/events",
        json={
            "name": "Nuit publique",
            "public_description": "Description complète et réelle.",
            "short_description": "Une nuit à découvrir.",
            "banner_url": "https://cdn.tore.be/event.jpg",
            "event_type": "soirée",
            "capacity": 450,
            "access_type": "TICKET",
            "currency": "eur",
            "city": "Liège",
        },
        headers=headers,
    )
    assert event_response.status_code == 200
    event_payload = event_response.json()
    assert event_payload["capacity"] == 450
    assert event_payload["currency"] == "EUR"

    invalid = client.patch(
        "/partner/portal/bar",
        json={"primary_color": "ruby", "logo_url": "javascript:alert(1)"},
        headers=headers,
    )
    assert invalid.status_code == 422

    public_bar = client.get(f"/bars/{bar_id}/public")
    assert public_bar.status_code == 200
    assert public_bar.json()["modules"] == ["menu"]


def test_partner_public_content_writes_reject_non_manager():
    _, token = _seed_partner_user(role="bartender")
    response = TestClient(app).patch(
        "/partner/portal/bar",
        json={"public_description": "interdit"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
