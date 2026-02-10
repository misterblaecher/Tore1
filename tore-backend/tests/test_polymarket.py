from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Event, EventStaff, EventConfig


def _create_guest(client: TestClient) -> tuple[str, str]:
    res = client.post("/auth/guest", json={"display_name": "Tester"})
    assert res.status_code == 200
    data = res.json()
    return data["token"], data["user"]["id"]


def _create_event() -> int:
    s = get_session()
    try:
        event = Event(
            name="Polymarket Event",
            starts_at=now_utc(),
            ends_at=now_utc() + timedelta(hours=4),
            entry_price_cents=0,
            ticket_mode=True,
        )
        s.add(event)
        s.commit()
        s.refresh(event)
        return event.id
    finally:
        s.close()


def _seed_event_admin(event_id: int, user_id: str) -> None:
    s = get_session()
    try:
        staff = EventStaff(
            event_id=event_id,
            user_id=user_id,
            role="admin",
            is_active=True,
        )
        s.add(staff)
        s.commit()
    finally:
        s.close()


def _set_event_allow_user_bets(event_id: int, allow: bool) -> None:
    s = get_session()
    try:
        cfg = s.query(EventConfig).filter(EventConfig.event_id == event_id).first()
        if not cfg:
            cfg = EventConfig(event_id=event_id, allow_user_bets=allow)
        else:
            cfg.allow_user_bets = allow
        s.add(cfg)
        s.commit()
    finally:
        s.close()


def test_create_global_bet_permissions(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    token, user_id = _create_guest(client)

    monkeypatch.setenv("POLYMARKET_GLOBAL_ENABLED", "true")
    monkeypatch.setenv("POLYMARKET_GLOBAL_CREATORS", user_id)

    res = client.post(
        "/polymarket/bets",
        json={
            "scope": "GLOBAL",
            "question": "Will it rain?",
            "kind": "OBJECTIVE",
            "deadline_at": (now_utc() + timedelta(hours=2)).isoformat(),
            "rules_text": "Météo officielle.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    monkeypatch.setenv("POLYMARKET_GLOBAL_CREATORS", "someone-else")
    res_forbidden = client.post(
        "/polymarket/bets",
        json={
            "scope": "GLOBAL",
            "question": "Another bet?",
            "kind": "OBJECTIVE",
            "deadline_at": (now_utc() + timedelta(hours=2)).isoformat(),
            "rules_text": "Test.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_forbidden.status_code == 403


def test_create_event_bet_permissions(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    token, user_id = _create_guest(client)
    event_id = _create_event()

    monkeypatch.setenv("POLYMARKET_GLOBAL_ENABLED", "false")

    res_forbidden = client.post(
        "/polymarket/bets",
        json={
            "scope": "EVENT",
            "event_id": event_id,
            "question": "Event bet?",
            "kind": "OBJECTIVE",
            "deadline_at": (now_utc() + timedelta(hours=1)).isoformat(),
            "rules_text": "Test.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_forbidden.status_code == 403

    _seed_event_admin(event_id, user_id)

    res = client.post(
        "/polymarket/bets",
        json={
            "scope": "EVENT",
            "event_id": event_id,
            "question": "Event bet?",
            "kind": "OBJECTIVE",
            "deadline_at": (now_utc() + timedelta(hours=1)).isoformat(),
            "rules_text": "Test.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    _set_event_allow_user_bets(event_id, True)
    token2, _ = _create_guest(client)
    res_allowed = client.post(
        "/polymarket/bets",
        json={
            "scope": "EVENT",
            "event_id": event_id,
            "question": "User bet?",
            "kind": "OBJECTIVE",
            "deadline_at": (now_utc() + timedelta(hours=1)).isoformat(),
            "rules_text": "Test.",
        },
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert res_allowed.status_code == 200


def test_position_idempotency_and_timeline(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    token, user_id = _create_guest(client)

    monkeypatch.setenv("POLYMARKET_GLOBAL_ENABLED", "true")
    monkeypatch.setenv("POLYMARKET_GLOBAL_CREATORS", user_id)

    create_res = client.post(
        "/polymarket/bets",
        json={
            "scope": "GLOBAL",
            "question": "Idempotency?",
            "kind": "OBJECTIVE",
            "deadline_at": (now_utc() + timedelta(hours=2)).isoformat(),
            "rules_text": "Test.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    bet_id = create_res.json()["id"]

    pos_res = client.post(
        f"/polymarket/bets/{bet_id}/positions",
        json={"side": "YES", "stake_tickets": 10, "idempotency_key": "idem-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pos_res.status_code == 200

    pos_res_dup = client.post(
        f"/polymarket/bets/{bet_id}/positions",
        json={"side": "YES", "stake_tickets": 10, "idempotency_key": "idem-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pos_res_dup.status_code == 200
    assert pos_res_dup.json()["bet"]["pool_yes_tickets"] == 10

    token2, _ = _create_guest(client)
    pos_res2 = client.post(
        f"/polymarket/bets/{bet_id}/positions",
        json={"side": "NO", "stake_tickets": 5, "idempotency_key": "idem-2"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert pos_res2.status_code == 200

    timeline_res = client.get(f"/polymarket/bets/{bet_id}/timeline")
    assert timeline_res.status_code == 200
    assert len(timeline_res.json()) >= 2


def test_resolve_permissions(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    token, user_id = _create_guest(client)

    event_id = _create_event()
    _seed_event_admin(event_id, user_id)

    res_create = client.post(
        "/polymarket/bets",
        json={
            "scope": "EVENT",
            "event_id": event_id,
            "question": "Subjective?",
            "kind": "SUBJECTIVE",
            "resolver_user_id": user_id,
            "deadline_at": (now_utc() + timedelta(hours=1)).isoformat(),
            "rules_text": "Test.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    bet_id = res_create.json()["id"]

    token2, _ = _create_guest(client)
    res_forbidden = client.post(
        f"/polymarket/bets/{bet_id}/resolve",
        json={"outcome": "YES"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert res_forbidden.status_code == 403

    res_ok = client.post(
        f"/polymarket/bets/{bet_id}/resolve",
        json={"outcome": "YES"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["resolved_outcome"] == "YES"
