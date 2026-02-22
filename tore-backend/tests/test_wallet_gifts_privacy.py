import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AppUserPrivacySetting, AuditLog, Bar, BarPrivacySetting, Event, Order, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager_event():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"P41 Bar {suffix}", city="Liège", partner_code=f"P41{suffix}")
        s.add(bar)
        s.flush()
        manager = PartnerUser(display_name="Manager", pin_hash="hash")
        s.add(manager)
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role="manager", display_name="Manager"))
        event = Event(bar_id=bar.id, name="P4.1", starts_at=now_utc(), ends_at=now_utc() + timedelta(hours=3))
        s.add(event)
        s.commit()
        return bar.id, event.id, _make_token(manager.id, bar.id, "manager", "Manager")
    finally:
        s.close()


def _guest(client: TestClient, name: str) -> tuple[str, str]:
    response = client.post("/auth/guest", json={"display_name": name})
    assert response.status_code == 200
    payload = response.json()
    return payload["user"]["id"], payload["token"]


def _topup(client: TestClient, manager_token: str, event_id: int, user_id: str, amount: int, key: str) -> None:
    res = client.post(
        "/partner/portal/wallet/topup",
        json={"event_id": event_id, "target_user_id": user_id, "amount_cents": amount, "note": "seed", "client_key": key},
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": key},
    )
    assert res.status_code == 200


def test_wallet_transfer_success_and_idempotent_replay():
    client = TestClient(app)
    _, event_id, manager_token = _seed_manager_event()
    sender_id, sender_token = _guest(client, "sender")
    receiver_id, _ = _guest(client, "receiver")
    _topup(client, manager_token, event_id, sender_id, 15, "top-seed-1")

    idem = "trf-1"
    first = client.post(
        "/wallet/transfers",
        json={"event_id": event_id, "to_user_id": receiver_id, "amount": 4, "reason": "gift"},
        headers={"Authorization": f"Bearer {sender_token}", "Idempotency-Key": idem},
    )
    assert first.status_code == 200
    assert first.json()["idempotent"] is False

    replay = client.post(
        "/wallet/transfers",
        json={"event_id": event_id, "to_user_id": receiver_id, "amount": 4, "reason": "gift"},
        headers={"Authorization": f"Bearer {sender_token}", "Idempotency-Key": idem},
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent"] is True
    assert replay.json()["transfer_id"] == first.json()["transfer_id"]

    sender_wallet = client.get("/wallet/me", headers={"Authorization": f"Bearer {sender_token}"})
    assert sender_wallet.status_code == 200
    assert sender_wallet.json()["balance_tickets"] == 11


def test_wallet_transfer_insufficient_funds_and_rate_limit_429():
    client = TestClient(app)
    _, event_id, manager_token = _seed_manager_event()
    sender_id, sender_token = _guest(client, "sender2")
    receiver_id, _ = _guest(client, "receiver2")
    _topup(client, manager_token, event_id, sender_id, 40, "top-seed-2")

    low = client.post(
        "/wallet/transfers",
        json={"event_id": event_id, "to_user_id": receiver_id, "amount": 999, "reason_text": "stress"},
        headers={"Authorization": f"Bearer {sender_token}", "Idempotency-Key": "low-1"},
    )
    assert low.status_code == 400
    assert low.json()["detail"]["reason"] == "insufficient_balance"

    rate_limited = None
    for i in range(15):
        res = client.post(
            "/wallet/transfers",
            json={"event_id": event_id, "to_user_id": receiver_id, "amount": 1, "reason_text": "stress"},
            headers={"Authorization": f"Bearer {sender_token}", "Idempotency-Key": f"rl-{i}"},
        )
        if res.status_code == 429:
            rate_limited = res
            break
    assert rate_limited is not None


def test_privacy_endpoints_and_orders_live_masking():
    client = TestClient(app)
    bar_id, event_id, manager_token = _seed_manager_event()
    user_id, user_token = _guest(client, "Visible Name")

    get_privacy = client.get("/me/privacy", headers={"Authorization": f"Bearer {user_token}"})
    assert get_privacy.status_code == 200
    assert get_privacy.json()["visibility"] == "public"

    put_privacy = client.put(
        "/me/privacy",
        json={"visibility": "private", "show_identity_in_bar": True},
        headers={"Authorization": f"Bearer {user_token}", "Idempotency-Key": "privacy-1"},
    )
    assert put_privacy.status_code == 200
    assert put_privacy.json()["visibility"] == "private"

    s = get_session()
    try:
        s.add(BarPrivacySetting(bar_id=bar_id, staff_identity_consent_required=True))
        existing = s.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id == user_id).first()
        if existing:
            existing.visibility = "private"
            existing.show_identity_in_bar = True
            existing.show_identity_to_staff = True
            s.add(existing)
        else:
            s.add(AppUserPrivacySetting(user_id=user_id, visibility="private", show_identity_in_bar=True, show_identity_to_staff=True))
        s.add(
            Order(
                bar_id=bar_id,
                event_id=event_id,
                user_id=user_id,
                status="NEW",
                payment_status="PAID",
                total_cents=0,
                total_tickets=2,
                source="app",
                idempotency_key=secrets.token_hex(6),
            )
        )
        s.commit()

        audit = s.query(AuditLog).filter(AuditLog.action == "user.privacy.update", AuditLog.entity_id == user_id).first()
        assert audit is not None
    finally:
        s.close()

    live = client.get(
        f"/partner/portal/bar/events/{event_id}/orders/live",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert live.status_code == 200
    assert live.json()["items"]
    assert live.json()["items"][0]["customerLabel"].startswith("U***")
