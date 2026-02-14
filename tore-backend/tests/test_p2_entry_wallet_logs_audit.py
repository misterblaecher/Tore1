from sqlalchemy import text
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
        bar = Bar(name=f"P2 Bar {suffix}", city="City", partner_code=f"P2{suffix}")
        s.add(bar)
        s.flush()
        manager = PartnerUser(display_name="Manager", pin_hash="hash")
        s.add(manager)
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role="manager", display_name="Manager"))
        event = Event(bar_id=bar.id, name="P2 Event", starts_at=now_utc(), ends_at=now_utc() + timedelta(hours=2))
        s.add(event)
        s.commit()
        return bar.id, event.id, _make_token(manager.id, bar.id, "manager", "Manager"), manager.id
    finally:
        s.close()


def test_entry_token_lifecycle_idempotency_and_stats():
    _, event_id, manager_token, _ = _seed_manager_event()
    client = TestClient(app)

    issue = client.post(
        "/entry/tokens/issue",
        json={"event_id": event_id, "count": 2, "expires_in_minutes": 30},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert issue.status_code == 200
    tokens = issue.json()["issued"]
    t1 = tokens[0]["token"]
    t1_id = tokens[0]["token_id"]
    t2_id = tokens[1]["token_id"]

    first = client.post(
        "/entry/scan",
        json={"event_id": event_id, "token": t1, "scan_id": "scan-1"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert first.status_code == 200
    assert first.json()["decision"] == "ACCEPT"

    same_scan = client.post(
        "/entry/scan",
        json={"event_id": event_id, "token": t1, "scan_id": "scan-1"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert same_scan.status_code == 200
    assert same_scan.json()["idempotent"] is True
    assert same_scan.json()["log_id"] == first.json()["log_id"]

    second_scan = client.post(
        "/entry/scan",
        json={"event_id": event_id, "token": t1, "scan_id": "scan-2"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert second_scan.status_code == 200
    assert second_scan.json()["decision"] == "DENY"
    assert second_scan.json()["reason"] == "already_used"

    revoke = client.post(
        "/entry/tokens/revoke",
        json={"event_id": event_id, "token_ids": [t2_id]},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert revoke.status_code == 200
    assert revoke.json()["revoked_count"] == 1

    stats = client.get(f"/entry/tokens/stats?event_id={event_id}", headers={"Authorization": f"Bearer {manager_token}"})
    assert stats.status_code == 200
    assert stats.json()["counts"]["USED"] == 1
    assert stats.json()["counts"]["REVOKED"] == 1

    logs = client.get(f"/entry/logs?event_id={event_id}&search={t1_id}", headers={"Authorization": f"Bearer {manager_token}"})
    assert logs.status_code == 200
    assert len(logs.json()["items"]) >= 1

    s = get_session()
    try:
        actions = {r.action for r in s.query(AuditLog).filter(AuditLog.event_id == event_id).all()}
        assert "entry_token.issue" in actions
        assert "entry_token.revoke" in actions
        assert "entry_token.use" in actions
    finally:
        s.close()


def test_entry_token_expiry_and_sequential_concurrency_simulation():
    _, event_id, manager_token, _ = _seed_manager_event()
    client = TestClient(app)
    issue = client.post(
        "/entry/tokens/issue",
        json={"event_id": event_id, "count": 1, "expires_in_minutes": 1},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    token = issue.json()["issued"][0]["token"]

    s = get_session()
    try:
        s.execute(text("UPDATE entry_tokens SET expires_at = :ts"), {"ts": now_utc() - timedelta(minutes=2)})
        s.commit()
    finally:
        s.close()

    expired = client.post(
        "/entry/scan",
        json={"event_id": event_id, "token": token, "scan_id": "scan-exp"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert expired.status_code == 200
    assert expired.json()["reason"] == "expired"


def test_wallet_admin_logs_filters_and_cursor_and_audit_rows():
    _, event_id, manager_token, manager_id = _seed_manager_event()
    user_id = f"u-{secrets.token_hex(3)}"
    s = get_session()
    try:
        s.add(AppUser(id=user_id, display_name="User"))
        s.commit()
    finally:
        s.close()

    client = TestClient(app)
    for i in range(3):
        r = client.post(
            "/partner/portal/wallet/admin/topup",
            json={
                "event_id": event_id,
                "user_id": user_id,
                "amount_tickets": 10 + i,
                "reason": f"r{i}",
                "idempotency_key": f"key-{i}",
            },
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert r.status_code == 200

    p1 = client.get(
        f"/partner/portal/wallet/admin/logs?event_id={event_id}&limit=2",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert p1.status_code == 200
    assert len(p1.json()["items"]) == 2
    assert p1.json()["next_cursor"]

    p2 = client.get(
        f"/partner/portal/wallet/admin/logs?event_id={event_id}&limit=2&cursor={p1.json()['next_cursor']}",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert p2.status_code == 200
    ids = {row["id"] for row in p1.json()["items"]}
    ids2 = {row["id"] for row in p2.json()["items"]}
    assert ids.isdisjoint(ids2)

    filt = client.get(
        f"/partner/portal/wallet/admin/logs?event_id={event_id}&idempotency_key=key-1",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert filt.status_code == 200
    assert len(filt.json()["items"]) == 1

    mod = client.post(
        f"/partner/portal/event/{event_id}/modules",
        json={"entry_enabled": True},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert mod.status_code == 200

    s = get_session()
    try:
        rows = s.query(AuditLog).filter(AuditLog.actor_partner_id == manager_id, AuditLog.event_id == event_id).all()
        actions = {r.action for r in rows}
        assert "wallet_admin.topup" in actions
        assert "event_modules.update" in actions
    finally:
        s.close()
