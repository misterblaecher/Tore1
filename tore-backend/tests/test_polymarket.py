import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, EventConfig, EventStaff, PartnerMembership, PartnerUser, WalletTx
from partner_auth import _make_token


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


def _seed_wallet_manager() -> str:
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Wallet Bar {suffix}", city="Test City", partner_code=f"POLY{suffix}")
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
        return _make_token(user.id, bar.id, "manager", "Manager")
    finally:
        s.close()


def _topup_wallet(client: TestClient, manager_token: str, user_id: str, amount_tickets: int) -> None:
    res = client.post(
        "/wallet/topup",
        json={
            "user_id": user_id,
            "amount_tickets": amount_tickets,
            "idempotency_key": secrets.token_hex(8),
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert res.status_code == 200


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


def _create_global_bet(client: TestClient, token: str, user_id: str, monkeypatch) -> int:
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
    assert create_res.status_code == 200
    return create_res.json()["id"]


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
    manager_token = _seed_wallet_manager()

    bet_id = _create_global_bet(client, token, user_id, monkeypatch)
    _topup_wallet(client, manager_token, user_id, 20)

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

    token2, user2 = _create_guest(client)
    _topup_wallet(client, manager_token, user2, 10)
    pos_res2 = client.post(
        f"/polymarket/bets/{bet_id}/positions",
        json={"side": "NO", "stake_tickets": 5, "idempotency_key": "idem-2"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert pos_res2.status_code == 200

    timeline_res = client.get(f"/polymarket/bets/{bet_id}/timeline")
    assert timeline_res.status_code == 200
    assert len(timeline_res.json()) >= 2


def test_position_requires_sufficient_wallet_balance(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    token, user_id = _create_guest(client)

    bet_id = _create_global_bet(client, token, user_id, monkeypatch)

    res = client.post(
        f"/polymarket/bets/{bet_id}/positions",
        json={"side": "YES", "stake_tickets": 10, "idempotency_key": "insufficient-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "Insufficient wallet balance" in res.json()["detail"]


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


def test_resolve_pays_winner_and_is_idempotent(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    manager_token = _seed_wallet_manager()
    creator_token, creator_id = _create_guest(client)
    winner_token, winner_id = _create_guest(client)
    loser_token, loser_id = _create_guest(client)

    bet_id = _create_global_bet(client, creator_token, creator_id, monkeypatch)
    _topup_wallet(client, manager_token, winner_id, 50)
    _topup_wallet(client, manager_token, loser_id, 50)

    yes_res = client.post(
        f"/polymarket/bets/{bet_id}/positions",
        json={"side": "YES", "stake_tickets": 20, "idempotency_key": "resolve-yes"},
        headers={"Authorization": f"Bearer {winner_token}"},
    )
    assert yes_res.status_code == 200

    no_res = client.post(
        f"/polymarket/bets/{bet_id}/positions",
        json={"side": "NO", "stake_tickets": 10, "idempotency_key": "resolve-no"},
        headers={"Authorization": f"Bearer {loser_token}"},
    )
    assert no_res.status_code == 200

    resolve_res = client.post(
        f"/polymarket/bets/{bet_id}/resolve",
        json={"outcome": "YES"},
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert resolve_res.status_code == 200

    winner_wallet = client.get("/wallet/me", headers={"Authorization": f"Bearer {winner_token}"})
    assert winner_wallet.status_code == 200
    assert winner_wallet.json()["balance_tickets"] == 60
    payout_txs = [
        tx
        for tx in winner_wallet.json()["transactions"]
        if tx["kind"] == "BET_PAYOUT" and tx["ref_type"] == "BET" and tx["ref_id"] == str(bet_id)
    ]
    assert len(payout_txs) == 1

    resolve_res_dup = client.post(
        f"/polymarket/bets/{bet_id}/resolve",
        json={"outcome": "YES"},
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert resolve_res_dup.status_code == 200

    s = get_session()
    try:
        payout_count = (
            s.query(WalletTx)
            .filter(
                WalletTx.user_id == winner_id,
                WalletTx.kind == "BET_PAYOUT",
                WalletTx.ref_id == str(bet_id),
            )
            .count()
        )
        assert payout_count == 1
    finally:
        s.close()


def test_cancel_refunds_positions(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    manager_token = _seed_wallet_manager()
    creator_token, creator_id = _create_guest(client)
    user_token, user_id = _create_guest(client)

    bet_id = _create_global_bet(client, creator_token, creator_id, monkeypatch)
    _topup_wallet(client, manager_token, user_id, 30)

    pos_res = client.post(
        f"/polymarket/bets/{bet_id}/positions",
        json={"side": "NO", "stake_tickets": 12, "idempotency_key": "cancel-no"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert pos_res.status_code == 200

    cancel_res = client.post(
        f"/polymarket/bets/{bet_id}/cancel",
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert cancel_res.status_code == 200

    me = client.get("/wallet/me", headers={"Authorization": f"Bearer {user_token}"})
    assert me.status_code == 200
    assert me.json()["balance_tickets"] == 30
    refund_txs = [
        tx
        for tx in me.json()["transactions"]
        if tx["kind"] == "REFUND" and tx["ref_type"] == "BET" and tx["ref_id"] == str(bet_id)
    ]
    assert len(refund_txs) == 1


def test_polymarket_bet_me_endpoint(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    manager_token = _seed_wallet_manager()
    creator_token, creator_id = _create_guest(client)
    user_token, user_id = _create_guest(client)

    bet_id = _create_global_bet(client, creator_token, creator_id, monkeypatch)
    _topup_wallet(client, manager_token, user_id, 15)

    pos_res = client.post(
        f"/polymarket/bets/{bet_id}/positions",
        json={"side": "YES", "stake_tickets": 6, "idempotency_key": "me-endpoint"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert pos_res.status_code == 200

    me_res = client.get(
        f"/polymarket/bets/{bet_id}/me",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert me_res.status_code == 200
    payload = me_res.json()
    assert payload["stake_yes"] == 6
    assert payload["stake_total"] == 6
    assert payload["wallet_balance_tickets"] == 9
