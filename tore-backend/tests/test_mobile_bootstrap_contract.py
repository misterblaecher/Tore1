from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, EventModuleConfig, EventRuntimeState


def test_mobile_remote_config_contract():
    client = TestClient(app)

    res = client.get("/mobile/remote-config")

    assert res.status_code == 200
    payload = res.json()
    assert payload["disable_writes_global"] is False
    assert payload["modules_defaults"] == {}
    assert payload["diagnostics_enabled"] is True
    assert "server_time" in payload


def test_mobile_bootstrap_selects_active_event_contract():
    Base.metadata.create_all(engine)
    session = get_session()
    try:
        suffix = str(int(now_utc().timestamp() * 1000))[-8:]
        bar = Bar(name="Mobile Active", city="Liege", partner_code=f"MA{suffix}")
        session.add(bar)
        session.flush()
        boot_now = now_utc()
        event = Event(
            bar_id=bar.id,
            name="Mobile Active Event",
            starts_at=boot_now,
            ends_at=boot_now + timedelta(hours=2),
        )
        session.add(event)
        session.flush()
        session.add(EventRuntimeState(event_id=event.id, state="LIVE"))
        session.commit()
        expected_bar_id = bar.id
        expected_event_id = event.id

        res = TestClient(app).get("/mobile/bootstrap")
    finally:
        session.close()

    assert res.status_code == 200
    payload = res.json()
    assert payload["barId"] == str(expected_bar_id)
    assert payload["eventId"] == f"event_{expected_event_id}"
    assert payload["eventApiId"] == str(expected_event_id)
    assert payload["eventState"] == "LIVE"
    assert payload["source"] == "active"


def test_mobile_event_context_contract_for_existing_event():
    Base.metadata.create_all(engine)
    session = get_session()
    try:
        suffix = str(int(now_utc().timestamp() * 1000))[-8:]
        bar = Bar(name="Mobile Boot", city="Liege", partner_code=f"MB{suffix}")
        session.add(bar)
        session.flush()
        event = Event(
            bar_id=bar.id,
            name="Mobile Boot Event",
            starts_at=now_utc() - timedelta(minutes=5),
            ends_at=now_utc() + timedelta(hours=2),
        )
        session.add(event)
        session.flush()
        session.add(
            EventModuleConfig(
                event_id=event.id,
                orders_enabled=True,
                entry_enabled=False,
                safety_enabled=True,
            )
        )
        session.add(EventRuntimeState(event_id=event.id, state="LIVE"))
        session.commit()

        res = TestClient(app).get(f"/mobile/events/event_{event.id}/context")
    finally:
        session.close()

    assert res.status_code == 200
    payload = res.json()
    assert payload["eventId"] == f"event_{event.id}"
    assert payload["eventState"] == "LIVE"
    assert payload["exists"] is True
    assert payload["moduleStates"]["user_orders_lifecycle"] == "on"
    assert payload["moduleStates"]["orga_entry_mode"] == "off"
    assert payload["moduleStates"]["user_safe_kit"] == "on"


def test_mobile_event_context_contract_for_missing_event_is_boot_safe():
    res = TestClient(app).get("/mobile/events/event_424242/context")

    assert res.status_code == 200
    payload = res.json()
    assert payload["eventId"] == "event_424242"
    assert payload["eventState"] == "DRAFT"
    assert payload["moduleStates"] == {}
    assert payload["exists"] is False


def test_mobile_event_context_contract_for_unparseable_event_is_boot_safe():
    res = TestClient(app).get("/mobile/events/current/context")

    assert res.status_code == 200
    payload = res.json()
    assert payload["eventId"] == "current"
    assert payload["event_id"] is None
    assert payload["eventState"] == "DRAFT"
