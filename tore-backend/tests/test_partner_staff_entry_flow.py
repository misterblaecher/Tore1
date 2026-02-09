from datetime import timedelta

from fastapi.testclient import TestClient

import secrets

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, EventConfig, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager() -> tuple[int, str]:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(
            name=f"Staff Bar {suffix}",
            city="Test City",
            partner_code=f"STAFF{suffix}",
        )
        s.add(bar)
        s.flush()

        user = PartnerUser(display_name="Manager", pin_hash="hash")
        s.add(user)
        s.flush()

        membership = PartnerMembership(
            user_id=user.id,
            bar_id=bar.id,
            role="manager",
            display_name="Manager",
        )
        s.add(membership)
        s.commit()

        token = _make_token(user.id, bar.id, "manager", "Manager")
        return bar.id, token
    finally:
        s.close()


def _create_entry_event(bar_id: int) -> int:
    s = get_session()
    try:
        event = Event(
            bar_id=bar_id,
            name="Entry Event",
            starts_at=now_utc(),
            ends_at=now_utc() + timedelta(hours=4),
            entry_price_cents=0,
            ticket_mode=False,
        )
        s.add(event)
        s.flush()

        config = EventConfig(event_id=event.id, entry_enabled=True)
        s.add(config)
        s.commit()
        return event.id
    finally:
        s.close()


def test_staff_entry_flow():
    bar_id, manager_token = _seed_manager()
    event_id = _create_entry_event(bar_id)
    client = TestClient(app)

    invite_res = client.post(
        "/partner/auth/invites",
        json={"role": "entry", "max_uses": 2, "expires_days": 10},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert invite_res.status_code == 200
    invite_payload = invite_res.json()
    assert invite_payload["code"]
    assert invite_payload["role"] == "entry"

    join_res = client.post(
        "/partner/auth/staff/join",
        json={
            "invite_code": invite_payload["code"],
            "display_name": "Entry Staff",
            "pin": "1234",
        },
    )
    assert join_res.status_code == 200
    join_payload = join_res.json()
    assert join_payload["role"] == "entry"
    staff_token = join_payload["token"]

    stats_before = client.get(
        f"/events/{event_id}/entry/stats",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert stats_before.status_code == 200
    total_before = stats_before.json()["total"]

    scan_res = client.post(
        f"/events/{event_id}/entry/scans",
        json={
            "delta": 1,
            "source": "manual",
            "device_id": "pytest-device",
            "idempotency_key": secrets.token_hex(8),
        },
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert scan_res.status_code == 200

    stats_after = client.get(
        f"/events/{event_id}/entry/stats",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert stats_after.status_code == 200
    assert stats_after.json()["total"] == total_before + 1
