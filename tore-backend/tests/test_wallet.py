import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import Bar, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager() -> str:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(
            name=f"Wallet Bar {suffix}",
            city="Test City",
            partner_code=f"WALLET{suffix}",
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
        return _make_token(user.id, bar.id, "manager", "Manager")
    finally:
        s.close()


def _create_guest_user(client: TestClient) -> tuple[str, str]:
    res = client.post("/auth/guest", json={"display_name": "Wallet Guest"})
    assert res.status_code == 200
    payload = res.json()
    return payload["user"]["id"], payload["token"]


def test_wallet_topup_requires_auth():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    user_id, _token = _create_guest_user(client)

    res = client.post(
        "/wallet/topup",
        json={
            "user_id": user_id,
            "amount_tickets": 10,
            "idempotency_key": secrets.token_hex(8),
        },
    )
    assert res.status_code == 401


def test_wallet_topup_idempotent():
    manager_token = _seed_manager()
    client = TestClient(app)
    user_id, user_token = _create_guest_user(client)
    idempotency_key = secrets.token_hex(8)

    first = client.post(
        "/wallet/topup",
        json={
            "user_id": user_id,
            "amount_tickets": 12,
            "idempotency_key": idempotency_key,
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert first.status_code == 200
    assert first.json()["balance_tickets"] == 12

    second = client.post(
        "/wallet/topup",
        json={
            "user_id": user_id,
            "amount_tickets": 12,
            "idempotency_key": idempotency_key,
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert second.status_code == 200
    assert second.json()["balance_tickets"] == 12

    me = client.get("/wallet/me", headers={"Authorization": f"Bearer {user_token}"})
    assert me.status_code == 200
    payload = me.json()
    assert payload["balance_tickets"] == 12
    assert len(payload["transactions"]) == 1
