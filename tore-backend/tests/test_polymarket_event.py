from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AuditLog, Bet, EventConfig, EventRuntimeState
from tests.test_polymarket import _create_event, _create_guest, _seed_event_admin, _seed_wallet_manager, _topup_wallet


def _enable_event_bets(event_id: int) -> None:
    s = get_session()
    try:
        cfg = s.query(EventConfig).filter(EventConfig.event_id == event_id).first()
        if not cfg:
            cfg = EventConfig(event_id=event_id, allow_user_bets=True)
        else:
            cfg.allow_user_bets = True
        s.add(cfg)
        s.commit()
    finally:
        s.close()


def test_module_off_blocks_event_polymarket_writes_and_list():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    token, _ = _create_guest(client)
    event_id = _create_event()

    list_res = client.get(f"/events/{event_id}/polymarket", headers={"Authorization": f"Bearer {token}"})
    assert list_res.status_code == 403
    assert list_res.json()["detail"]["reason"] == "module_off"

    create_res = client.post(
        f"/events/{event_id}/polymarket",
        json={"question": "Will this fail?", "type": "objective"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "off-1"},
    )
    assert create_res.status_code == 403


def test_event_create_idempotency_and_rate_limit():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    token, user_id = _create_guest(client)
    event_id = _create_event()
    _enable_event_bets(event_id)
    _seed_event_admin(event_id, user_id)

    payload = {"question": "Will DJ play after 1am?", "type": "objective"}
    first = client.post(
        f"/events/{event_id}/polymarket",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "event-create-1"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/events/{event_id}/polymarket",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "event-create-1"},
    )
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]

    limited = client.post(
        f"/events/{event_id}/polymarket",
        json={"question": "Second create should rate limit", "type": "objective"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "event-create-2"},
    )
    assert limited.status_code == 429


def test_resolve_requires_reason_and_sets_outcome_with_audit():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    token, user_id = _create_guest(client)
    event_id = _create_event()
    _enable_event_bets(event_id)
    _seed_event_admin(event_id, user_id)

    created = client.post(
        f"/events/{event_id}/polymarket",
        json={"question": "Will venue close on time?", "type": "objective"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "resolve-create-1"},
    )
    market_id = created.json()["id"]

    missing_reason = client.post(
        f"/events/{event_id}/polymarket/{market_id}/resolve",
        json={"outcome": "YES"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "resolve-1"},
    )
    assert missing_reason.status_code == 422

    resolved = client.post(
        f"/events/{event_id}/polymarket/{market_id}/resolve",
        json={"outcome": "YES", "reason": "Official result"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "resolve-2"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["market"]["resolved_outcome"] == "YES"

    s = get_session()
    try:
        logs = s.query(AuditLog).filter(AuditLog.action.in_(["polymarket.event.create", "polymarket.event.resolve"])).all()
        assert logs
    finally:
        s.close()


def test_buy_blocked_when_paused_or_frozen():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    token, user_id = _create_guest(client)
    event_id = _create_event()
    _enable_event_bets(event_id)
    _seed_event_admin(event_id, user_id)
    manager_token = _seed_wallet_manager()
    _topup_wallet(client, manager_token, user_id, 50)

    created = client.post(
        f"/events/{event_id}/polymarket",
        json={"question": "Will this market be tradable?", "type": "objective"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "buy-create-1"},
    )
    market_id = created.json()["id"]

    s = get_session()
    try:
        s.add(EventRuntimeState(event_id=event_id, state="PAUSE", updated_at=now_utc() - timedelta(minutes=1)))
        s.commit()
    finally:
        s.close()

    paused = client.post(
        f"/events/{event_id}/polymarket/{market_id}/buy",
        json={"side": "YES", "amountTickets": 10},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "buy-1"},
    )
    assert paused.status_code == 423
    assert paused.json()["detail"]["reason"] == "event_paused"

    s = get_session()
    try:
        runtime = s.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).first()
        runtime.state = "FROZEN"
        s.add(runtime)
        s.commit()
    finally:
        s.close()

    frozen = client.post(
        f"/events/{event_id}/polymarket/{market_id}/buy",
        json={"side": "YES", "amountTickets": 10},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "buy-2"},
    )
    assert frozen.status_code == 423


def test_buy_blocked_when_event_ended():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    token, user_id = _create_guest(client)
    event_id = _create_event()
    _enable_event_bets(event_id)
    _seed_event_admin(event_id, user_id)
    manager_token = _seed_wallet_manager()
    _topup_wallet(client, manager_token, user_id, 50)

    created = client.post(
        f"/events/{event_id}/polymarket",
        json={"question": "Will this market end?", "type": "objective"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "buy-ended-create-1"},
    )
    market_id = created.json()["id"]

    s = get_session()
    try:
        s.add(EventRuntimeState(event_id=event_id, state="ENDED", updated_at=now_utc() - timedelta(minutes=1)))
        s.commit()
    finally:
        s.close()

    ended = client.post(
        f"/events/{event_id}/polymarket/{market_id}/buy",
        json={"side": "YES", "amountTickets": 10},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "buy-ended-1"},
    )
    assert ended.status_code == 423
    assert ended.json()["detail"]["reason"] == "ended"
