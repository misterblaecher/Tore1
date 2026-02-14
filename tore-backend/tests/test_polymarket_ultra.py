from datetime import timedelta

from fastapi.testclient import TestClient

from app.services import rate_limit_service
from db import Base, engine, get_session, now_utc
from main import app
from models import EventRuntimeState
from tests.test_polymarket import _create_event, _create_guest, _create_global_bet, _seed_event_admin, _seed_wallet_manager, _topup_wallet


def test_markets_positions_and_exports_ultra(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    manager_token = _seed_wallet_manager()
    user_token, user_id = _create_guest(client)
    bet_id = _create_global_bet(client, user_token, user_id, monkeypatch)
    _topup_wallet(client, manager_token, user_id, 100)

    pos = client.post(
        "/polymarket/position",
        json={"market_id": bet_id, "side": "yes", "amount_cents": 25, "client_key": "ultra-k1"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert pos.status_code == 200
    trade_id = pos.json()["trade_id"]

    pos_dup = client.post(
        "/polymarket/position",
        json={"market_id": bet_id, "side": "yes", "amount_cents": 25, "client_key": "ultra-k1"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert pos_dup.status_code == 200
    assert pos_dup.json()["trade_id"] == trade_id

    markets = client.get("/polymarket/markets?scope=global&status=live", headers={"Authorization": f"Bearer {user_token}"})
    assert markets.status_code == 200
    assert markets.json()["items"]

    my_pos = client.get("/polymarket/positions?scope=global&status=open", headers={"Authorization": f"Bearer {user_token}"})
    assert my_pos.status_code == 200
    assert my_pos.json()["items"]

    history = client.get(f"/polymarket/markets/{bet_id}/my-history", headers={"Authorization": f"Bearer {user_token}"})
    assert history.status_code == 200
    assert history.json()["items"]

    m_csv = client.get("/polymarket/exports/markets.csv", headers={"Authorization": f"Bearer {user_token}"})
    assert m_csv.status_code == 200
    assert "text/csv" in m_csv.headers["content-type"]
    assert "question" in m_csv.text

    p_csv = client.get("/polymarket/exports/positions.csv", headers={"Authorization": f"Bearer {user_token}"})
    assert p_csv.status_code == 200
    assert "text/csv" in p_csv.headers["content-type"]
    assert "position_id" in p_csv.text


def test_runtime_and_balance_reason_codes_ultra(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    token, user_id = _create_guest(client)
    event_id = _create_event()
    _seed_event_admin(event_id, user_id)

    create = client.post(
        "/polymarket/bets",
        json={
            "scope": "EVENT",
            "event_id": event_id,
            "question": "Paused check",
            "kind": "OBJECTIVE",
            "deadline_at": (now_utc() + timedelta(hours=1)).isoformat(),
            "rules_text": "rule",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    bet_id = create.json()["id"]

    s = get_session()
    try:
        s.add(EventRuntimeState(event_id=event_id, state="PAUSE", reason="test"))
        s.commit()
    finally:
        s.close()

    denied = client.post(
        "/polymarket/position",
        json={"market_id": bet_id, "side": "yes", "amount_cents": 10, "client_key": "pause-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert denied.status_code in {409, 423}
    assert denied.json()["detail"]["reason"] == "event_paused"

    monkeypatch.setenv("POLYMARKET_GLOBAL_ENABLED", "true")
    monkeypatch.setenv("POLYMARKET_GLOBAL_CREATORS", user_id)
    global_bet = _create_global_bet(client, token, user_id, monkeypatch)

    insufficient = client.post(
        "/polymarket/position",
        json={"market_id": global_bet, "side": "yes", "amount_cents": 9999, "client_key": "bal-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert insufficient.status_code == 400
    assert insufficient.json()["detail"]["reason"] == "insufficient_balance"


def test_rate_limit_position_and_resolve_ultra(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    manager_token = _seed_wallet_manager()
    token, user_id = _create_guest(client)
    bet_id = _create_global_bet(client, token, user_id, monkeypatch)
    _topup_wallet(client, manager_token, user_id, 100)

    rate_limit_service._RATE_LIMIT_MAX = 1
    rate_limit_service._RATE_LIMIT_WINDOW_S = 100
    rate_limit_service._store.clear()

    first = client.post(
        "/polymarket/position",
        json={"market_id": bet_id, "side": "yes", "amount_cents": 10, "client_key": "rl-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 200

    second = client.post(
        "/polymarket/position",
        json={"market_id": bet_id, "side": "no", "amount_cents": 10, "client_key": "rl-2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second.status_code == 429
    assert second.json()["detail"]["reason"] == "rate_limited"

    rate_limit_service._store.clear()
    resolve_ok = client.post(
        "/polymarket/resolve",
        json={"market_id": bet_id, "outcome": "yes"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resolve_ok.status_code == 200

    resolve_limited = client.post(
        "/polymarket/resolve",
        json={"market_id": bet_id, "outcome": "yes"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resolve_limited.status_code == 429
    assert resolve_limited.json()["detail"]["reason"] == "rate_limited"
