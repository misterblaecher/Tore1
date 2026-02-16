from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AuditLog, AppToken, AppUser, Bar, Event, EventModuleConfig, EventRuntimeState, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_base(*, module_on: bool = True, runtime: str = "LIVE"):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Safety {suffix}", city="Liege", partner_code=f"SF{suffix}")
        s.add(bar)
        s.flush()
        manager = PartnerUser(display_name="Manager", pin_hash="hash")
        s.add(manager)
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role="manager", display_name="Manager"))
        event = Event(bar_id=bar.id, name="Safe Event", starts_at=now_utc() - timedelta(hours=1), ends_at=now_utc() + timedelta(hours=4))
        s.add(event)
        s.flush()
        s.add(EventModuleConfig(event_id=event.id, safety_enabled=module_on, checkins_enabled=True, wifi_enabled=True, entry_enabled=True))
        if runtime != "LIVE":
            s.add(EventRuntimeState(event_id=event.id, state=runtime, reason="test"))

        u1 = AppUser(id=f"u-{suffix}", display_name="U1")
        u2 = AppUser(id=f"b-{suffix}", display_name="Buddy")
        s.add_all([u1, u2])
        t1 = f"tok-{secrets.token_hex(8)}"
        t2 = f"tok-{secrets.token_hex(8)}"
        s.add_all([
            AppToken(user_id=u1.id, token_hash=hashlib.sha256(t1.encode()).hexdigest()),
            AppToken(user_id=u2.id, token_hash=hashlib.sha256(t2.encode()).hexdigest()),
        ])
        s.commit()
        return {
            "event_id": event.id,
            "manager_token": _make_token(manager.id, bar.id, "manager", "Manager"),
            "user_id": u1.id,
            "buddy_id": u2.id,
            "user_token": t1,
            "buddy_token": t2,
        }
    finally:
        s.close()


def test_module_off_strict_and_idempotency_required():
    ctx = _seed_base(module_on=False)
    client = TestClient(app)

    st = client.get(f"/events/{ctx['event_id']}/safety/state", headers={"Authorization": f"Bearer {ctx['user_token']}"})
    assert st.status_code == 404
    assert st.json()["detail"]["code"] == "MODULE_OFF"

    off_write = client.post(
        f"/events/{ctx['event_id']}/safety/checkin",
        json={"type": "OK"},
        headers={"Authorization": f"Bearer {ctx['user_token']}", "Idempotency-Key": "k1"},
    )
    assert off_write.status_code == 404

    ctx_on = _seed_base(module_on=True)
    missing = client.post(
        f"/events/{ctx_on['event_id']}/safety/checkin",
        json={"type": "OK"},
        headers={"Authorization": f"Bearer {ctx_on['user_token']}"},
    )
    assert missing.status_code == 400
    assert missing.json()["detail"]["reason"] == "IDEMPOTENCY_REQUIRED"


def test_checkin_ok_panic_and_runtime_block_and_buddy_idempotent():
    ctx = _seed_base(module_on=True)
    client = TestClient(app)

    buddy_set = client.post(
        f"/events/{ctx['event_id']}/safety/buddy",
        json={"buddyUserId": ctx["buddy_id"]},
        headers={"Authorization": f"Bearer {ctx['user_token']}", "Idempotency-Key": "buddy-1"},
    )
    buddy_set2 = client.post(
        f"/events/{ctx['event_id']}/safety/buddy",
        json={"buddyUserId": ctx["buddy_id"]},
        headers={"Authorization": f"Bearer {ctx['user_token']}", "Idempotency-Key": "buddy-1"},
    )
    assert buddy_set.status_code == 200
    assert buddy_set.json() == buddy_set2.json()

    ok = client.post(
        f"/events/{ctx['event_id']}/safety/checkin",
        json={"type": "OK"},
        headers={"Authorization": f"Bearer {ctx['user_token']}", "Idempotency-Key": "ok-1"},
    )
    panic = client.post(
        f"/events/{ctx['event_id']}/safety/checkin",
        json={"type": "PANIC"},
        headers={"Authorization": f"Bearer {ctx['user_token']}", "Idempotency-Key": "panic-1"},
    )
    assert ok.status_code == 200 and panic.status_code == 200

    state = client.get(f"/events/{ctx['event_id']}/safety/state", headers={"Authorization": f"Bearer {ctx['user_token']}"})
    assert state.status_code == 200
    assert state.json()["myBuddy"]["userId"] == ctx["buddy_id"]

    blocked = _seed_base(module_on=True, runtime="DEGRADED")
    blocked_write = client.post(
        f"/events/{blocked['event_id']}/safety/checkin",
        json={"type": "OK"},
        headers={"Authorization": f"Bearer {blocked['user_token']}", "Idempotency-Key": "blocked-1"},
    )
    assert blocked_write.status_code == 423


def test_orga_alerts_assign_resolve_audit_and_exports():
    ctx = _seed_base(module_on=True)
    client = TestClient(app)

    panic = client.post(
        f"/events/{ctx['event_id']}/safety/checkin",
        json={"type": "PANIC"},
        headers={"Authorization": f"Bearer {ctx['user_token']}", "Idempotency-Key": "panic-alert"},
    )
    alert_id = panic.json()["id"]

    open_alerts = client.get(
        f"/partner/portal/orga/events/{ctx['event_id']}/safety/alerts?status=open",
        headers={"Authorization": f"Bearer {ctx['manager_token']}"},
    )
    assert open_alerts.status_code == 200
    assert any(a["id"] == alert_id for a in open_alerts.json()["alerts"])

    assign = client.post(
        f"/partner/portal/orga/events/{ctx['event_id']}/safety/alerts/{alert_id}/assign",
        json={},
        headers={"Authorization": f"Bearer {ctx['manager_token']}", "Idempotency-Key": "assign-1"},
    )
    resolve = client.post(
        f"/partner/portal/orga/events/{ctx['event_id']}/safety/alerts/{alert_id}/resolve",
        json={"reason": "handled"},
        headers={"Authorization": f"Bearer {ctx['manager_token']}", "Idempotency-Key": "resolve-1"},
    )
    assert assign.status_code == 200
    assert resolve.status_code == 200

    csv_exp = client.get(
        f"/partner/portal/orga/events/{ctx['event_id']}/safety/export.csv",
        headers={"Authorization": f"Bearer {ctx['manager_token']}"},
    )
    js_exp = client.get(
        f"/partner/portal/orga/events/{ctx['event_id']}/safety/export.json",
        headers={"Authorization": f"Bearer {ctx['manager_token']}"},
    )
    assert csv_exp.status_code == 200
    assert "id,user_id,type,created_at,resolved_at,assigned_to_user_id" in csv_exp.text
    assert js_exp.status_code == 200
    assert {"id", "userId", "type", "createdAt"}.issubset(js_exp.json()["items"][0].keys())

    s = get_session()
    try:
        actions = {row.action for row in s.query(AuditLog).filter(AuditLog.event_id == ctx["event_id"]).all()}
        assert "safety.alert.assign" in actions
        assert "safety.alert.resolve" in actions
    finally:
        s.close()
