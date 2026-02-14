import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AppUser, AuditLog, Bar, Event, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager_event():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"WU Bar {suffix}", city="City", partner_code=f"WU{suffix}")
        s.add(bar)
        s.flush()
        manager = PartnerUser(display_name="Manager", pin_hash="hash")
        s.add(manager)
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role="manager", display_name="Manager"))
        event = Event(bar_id=bar.id, name="Wallet Ultra", starts_at=now_utc(), ends_at=now_utc() + timedelta(hours=2))
        s.add(event)
        s.commit()
        return bar.id, event.id, _make_token(manager.id, bar.id, "manager", "Manager"), manager.id
    finally:
        s.close()


def _guest(client: TestClient, name: str) -> tuple[str, str]:
    r = client.post("/auth/guest", json={"display_name": name})
    assert r.status_code == 200
    p = r.json()
    return p["user"]["id"], p["token"]


def test_wallet_me_and_ledger_pagination():
    client = TestClient(app)
    _, event_id, manager_token, _ = _seed_manager_event()
    user_id, token = _guest(client, "u1")
    for idx in range(3):
        top = client.post(
            "/partner/portal/wallet/topup",
            json={"event_id": event_id, "target_user_id": user_id, "amount_cents": 5 + idx, "note": "seed", "client_key": f"k-{idx}"},
            headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": f"hdr-{idx}"},
        )
        assert top.status_code == 200

    me = client.get("/wallet/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["balance_tickets"] == 18

    page1 = client.get("/wallet/me/ledger?limit=2", headers={"Authorization": f"Bearer {token}"})
    assert page1.status_code == 200
    assert len(page1.json()["items"]) == 2
    assert page1.json()["next_cursor"]

    page2 = client.get(f"/wallet/me/ledger?limit=2&cursor={page1.json()['next_cursor']}", headers={"Authorization": f"Bearer {token}"})
    assert page2.status_code == 200
    ids1 = {row["id"] for row in page1.json()["items"]}
    ids2 = {row["id"] for row in page2.json()["items"]}
    assert ids1.isdisjoint(ids2)


def test_wallet_topup_idempotent_and_export_csv_and_audit():
    client = TestClient(app)
    _, event_id, manager_token, manager_id = _seed_manager_event()
    user_id, _ = _guest(client, "u2")
    body = {"event_id": event_id, "target_user_id": user_id, "amount_cents": 9, "note": "admin", "client_key": "ck-1"}

    first = client.post("/partner/portal/wallet/topup", json=body, headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "idem-1"})
    second = client.post("/partner/portal/wallet/topup", json=body, headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "idem-1"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["idempotent"] is True

    export = client.get(f"/partner/portal/wallet/logs/export.csv?event_id={event_id}", headers={"Authorization": f"Bearer {manager_token}"})
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert "user_id" in export.text

    s = get_session()
    try:
        actions = {r.action for r in s.query(AuditLog).filter(AuditLog.actor_partner_id == manager_id).all()}
        assert "wallet.topup" in actions
        assert "wallet.export" in actions
    finally:
        s.close()


def test_wallet_gift_validations_idempotence_and_rate_limit():
    client = TestClient(app)
    _, event_id, manager_token, _ = _seed_manager_event()
    sender_id, sender_token = _guest(client, "sender")
    recv_id, _ = _guest(client, "recv")

    credit = client.post(
        "/partner/portal/wallet/topup",
        json={"event_id": event_id, "target_user_id": sender_id, "amount_cents": 3, "note": "seed", "client_key": "seed-1"},
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "seed-hdr-1"},
    )
    assert credit.status_code == 200

    invalid = client.post(
        "/wallet/gift",
        json={"event_id": event_id, "to_user_id": recv_id, "amount_cents": 0, "client_key": "g0"},
        headers={"Authorization": f"Bearer {sender_token}", "Idempotency-Key": "g0"},
    )
    assert invalid.status_code == 400

    low = client.post(
        "/wallet/gift",
        json={"event_id": event_id, "to_user_id": recv_id, "amount_cents": 99, "client_key": "g1"},
        headers={"Authorization": f"Bearer {sender_token}", "Idempotency-Key": "g1"},
    )
    assert low.status_code == 409
    assert low.json()["detail"]["reason"] == "insufficient_balance"

    ok1 = client.post(
        "/wallet/gift",
        json={"event_id": event_id, "to_user_id": recv_id, "amount_cents": 2, "client_key": "g2"},
        headers={"Authorization": f"Bearer {sender_token}", "Idempotency-Key": "g2"},
    )
    ok2 = client.post(
        "/wallet/gift",
        json={"event_id": event_id, "to_user_id": recv_id, "amount_cents": 2, "client_key": "g2"},
        headers={"Authorization": f"Bearer {sender_token}", "Idempotency-Key": "g2"},
    )
    assert ok1.status_code == 200
    assert ok2.status_code == 200
    assert ok1.json()["gift_id"] == ok2.json()["gift_id"]

    sender_ledger = client.get("/wallet/me/ledger", headers={"Authorization": f"Bearer {sender_token}"})
    assert sender_ledger.status_code == 200
    types = {row["type"] for row in sender_ledger.json()["items"]}
    assert "gift_out" in types

    rate_limited = None
    for idx in range(50):
        res = client.post(
            "/wallet/gift",
            json={"event_id": event_id, "to_user_id": recv_id, "amount_cents": 1, "client_key": f"rl-{idx}"},
            headers={"Authorization": f"Bearer {sender_token}", "Idempotency-Key": f"rl-{idx}"},
        )
        if res.status_code == 429:
            rate_limited = res
            break
    assert rate_limited is not None
    assert rate_limited.json()["detail"]["reason"] == "rate_limited"
