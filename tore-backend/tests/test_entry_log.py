from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app, get_current_user
from models import Bar, Event, EventConfig, EventStaff, AppUser


def _seed_event():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        bar = Bar(
            name="Test Bar",
            city="Test City",
            partner_code=f"TEST{int(now_utc().timestamp())}",
        )
        s.add(bar)
        s.flush()
        event = Event(bar_id=bar.id, name="Test Event")
        s.add(event)
        s.flush()
        config = EventConfig(event_id=event.id, entry_enabled=True)
        s.add(config)
        user = AppUser(id=f"user_{event.id}", display_name="Tester")
        s.add(user)
        staff = EventStaff(event_id=event.id, user_id=user.id, role="entry")
        s.add(staff)
        s.commit()
        return event.id, user
    finally:
        s.close()


def test_idempotency_same_key_counts_once():
    event_id, user = _seed_event()

    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)

    payload = {
        "delta": 1,
        "source": "scan",
        "device_id": "device-1",
        "idempotency_key": "same-key",
        "raw_qr": "tore://entry?event_id=1",
    }
    first = client.post(f"/events/{event_id}/entry/scans", json=payload)
    assert first.status_code == 200
    assert first.json()["total"] == 1

    second = client.post(f"/events/{event_id}/entry/scans", json=payload)
    assert second.status_code == 200
    assert second.json()["total"] == 1

    app.dependency_overrides.clear()


def test_delta_negative_decrements():
    event_id, user = _seed_event()

    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)

    client.post(
        f"/events/{event_id}/entry/scans",
        json={
            "delta": 1,
            "source": "manual",
            "device_id": "device-2",
            "idempotency_key": "k1",
        },
    )
    client.post(
        f"/events/{event_id}/entry/scans",
        json={
            "delta": -1,
            "source": "manual",
            "device_id": "device-2",
            "idempotency_key": "k2",
        },
    )

    stats = client.get(f"/events/{event_id}/entry/stats")
    assert stats.status_code == 200
    assert stats.json()["total"] == 0

    app.dependency_overrides.clear()
