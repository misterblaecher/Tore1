import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, EventModuleConfig, EventRuntimeState


def _seed_bar_with_events():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Bar {suffix}", city="Liege", partner_code=f"BAR{suffix}")
        s.add(bar)
        s.flush()

        live = Event(
            bar_id=bar.id,
            name="Live Event",
            starts_at=now_utc() - timedelta(hours=1),
            ends_at=now_utc() + timedelta(hours=1),
            visibility="PUBLIC",
            publication_status="PUBLISHED",
        )
        upcoming = Event(
            bar_id=bar.id,
            name="Upcoming Event",
            starts_at=now_utc() + timedelta(hours=2),
            ends_at=now_utc() + timedelta(hours=5),
            visibility="PUBLIC",
            publication_status="PUBLISHED",
        )
        ended = Event(
            bar_id=bar.id,
            name="Ended Event",
            starts_at=now_utc() - timedelta(hours=8),
            ends_at=now_utc() - timedelta(hours=4),
            visibility="PUBLIC",
            publication_status="PUBLISHED",
        )
        private = Event(
            bar_id=bar.id,
            name="Private Event",
            starts_at=now_utc() + timedelta(hours=3),
            ends_at=now_utc() + timedelta(hours=6),
            visibility="PRIVATE",
            publication_status="PUBLISHED",
        )
        s.add_all([live, upcoming, ended, private])
        s.flush()

        s.add(EventRuntimeState(event_id=live.id, state="PAUSE"))
        s.add(EventModuleConfig(event_id=live.id, orders_enabled=True, wifi_enabled=True))
        s.commit()
        return bar.id
    finally:
        s.close()


def test_list_bar_events_returns_enriched_fields():
    bar_id = _seed_bar_with_events()
    client = TestClient(app)

    res = client.get(f"/bars/{bar_id}/events")

    assert res.status_code == 200
    payload = res.json()
    assert len(payload) == 2

    statuses = {item["name"]: item["status"] for item in payload}
    assert statuses["Live Event"] == "LIVE"
    assert statuses["Upcoming Event"] == "UPCOMING"
    assert "Ended Event" not in statuses
    assert "Private Event" not in statuses

    live = next(item for item in payload if item["name"] == "Live Event")
    assert live["startAt"] == live["starts_at"]
    assert live["endAt"] == live["ends_at"]
    assert live["venue"]
    assert live["shortName"]
    assert live["eventState"] == "PAUSE"
    assert live["modulesOn"]["orders"] is True
    assert live["modulesOn"]["wifi"] is True
