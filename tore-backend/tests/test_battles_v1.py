from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AppToken, AppUser, AppUserPrivacySetting, AuditLog, Bar, Event, EventBattleRound, EventModuleConfig, EventRuntimeState, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_partner(*, module_on: bool = True, runtime: str = "LIVE") -> tuple[str, int]:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Battle Bar {suffix}", city="Liege", partner_code=f"B{suffix}")
        s.add(bar)
        s.flush()
        partner = PartnerUser(display_name="Orga", pin_hash="hash")
        s.add(partner)
        s.flush()
        s.add(PartnerMembership(user_id=partner.id, bar_id=bar.id, role="manager", display_name="Orga"))
        event = Event(bar_id=bar.id, name="Battle Event", starts_at=now_utc() - timedelta(hours=1), ends_at=now_utc() + timedelta(hours=2))
        s.add(event)
        s.flush()
        s.add(EventModuleConfig(event_id=event.id, battles_enabled=module_on, orders_enabled=True, hunt_enabled=True, entry_enabled=True, checkins_enabled=True, wifi_enabled=True, safety_enabled=True, polymarket_enabled=False, market_enabled=False))
        if runtime != "LIVE":
            s.add(EventRuntimeState(event_id=event.id, state=runtime, reason="test"))
        token = _make_token(partner.id, bar.id, "manager", "Orga")
        s.commit()
        return token, event.id
    finally:
        s.close()


def _seed_user(name: str, visibility: str | None = None) -> tuple[str, str]:
    s = get_session()
    try:
        uid = f"u-{secrets.token_hex(4)}"
        raw = f"tok-{secrets.token_hex(10)}"
        s.add(AppUser(id=uid, display_name=name))
        s.add(AppToken(user_id=uid, token_hash=hashlib.sha256(raw.encode()).hexdigest()))
        if visibility:
            s.add(AppUserPrivacySetting(user_id=uid, visibility=visibility, show_identity_to_staff=False, show_identity_in_bar=False))
        s.commit()
        return uid, raw
    finally:
        s.close()


def test_module_off_strict_404():
    manager_token, event_id = _seed_partner(module_on=False)
    _, app_token = _seed_user("Ana")
    client = TestClient(app)

    state = client.get(f"/events/{event_id}/battles/state", headers={"Authorization": f"Bearer {app_token}"})
    assert state.status_code == 404
    assert state.json()["detail"]["reason"] == "MODULE_OFF"

    start = client.post(
        f"/partner/portal/orga/events/{event_id}/battles/rounds/start",
        json={"title": "duel", "kind": "DUEL", "durationSeconds": 90, "optionALabel": "A", "optionBLabel": "B"},
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "off-start"},
    )
    assert start.status_code == 404
    assert start.json()["detail"]["reason"] == "MODULE_OFF"


def test_start_round_idempotent_and_key_required():
    manager_token, event_id = _seed_partner(module_on=True)
    client = TestClient(app)

    miss = client.post(
        f"/partner/portal/orga/events/{event_id}/battles/rounds/start",
        json={"title": "duel", "kind": "DUEL", "durationSeconds": 120, "optionALabel": "A", "optionBLabel": "B"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert miss.status_code == 400
    assert miss.json()["detail"]["reason"] == "IDEMPOTENCY_REQUIRED"

    first = client.post(
        f"/partner/portal/orga/events/{event_id}/battles/rounds/start",
        json={"title": "duel", "kind": "DUEL", "durationSeconds": 120, "optionALabel": "A", "optionBLabel": "B"},
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "same-start"},
    )
    second = client.post(
        f"/partner/portal/orga/events/{event_id}/battles/rounds/start",
        json={"title": "duel", "kind": "DUEL", "durationSeconds": 120, "optionALabel": "A", "optionBLabel": "B"},
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "same-start"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["roundId"] == second.json()["roundId"]


def test_vote_open_only_and_before_expiry():
    manager_token, event_id = _seed_partner(module_on=True)
    _, token = _seed_user("Voter")
    client = TestClient(app)

    started = client.post(
        f"/partner/portal/orga/events/{event_id}/battles/rounds/start",
        json={"title": "quick", "kind": "DUEL", "durationSeconds": 60, "optionALabel": "A", "optionBLabel": "B"},
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "start-vote"},
    ).json()
    round_id = started["roundId"]

    ok = client.post(
        f"/events/{event_id}/battles/vote",
        json={"roundId": round_id, "choice": "A"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "vote-open"},
    )
    assert ok.status_code == 200

    lock = client.post(
        f"/partner/portal/orga/events/{event_id}/battles/rounds/lock",
        json={"roundId": round_id},
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "lock-vote"},
    )
    assert lock.status_code == 200

    blocked = client.post(
        f"/events/{event_id}/battles/vote",
        json={"roundId": round_id, "choice": "A"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "vote-closed"},
    )
    assert blocked.status_code == 409


def test_lock_computes_winner_and_updates_scores_and_audit():
    manager_token, event_id = _seed_partner(module_on=True)
    _, token_a = _seed_user("A")
    _, token_b = _seed_user("B")
    client = TestClient(app)

    started = client.post(
        f"/partner/portal/orga/events/{event_id}/battles/rounds/start",
        json={"title": "duel", "kind": "DUEL", "durationSeconds": 180, "optionALabel": "Rouge", "optionBLabel": "Bleu"},
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "start-lock"},
    ).json()
    rid = started["roundId"]

    client.post(f"/events/{event_id}/battles/vote", json={"roundId": rid, "choice": "A"}, headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "va"})
    client.post(f"/events/{event_id}/battles/vote", json={"roundId": rid, "choice": "B"}, headers={"Authorization": f"Bearer {token_b}", "Idempotency-Key": "vb"})
    client.post(f"/events/{event_id}/battles/vote", json={"roundId": rid, "choice": "A"}, headers={"Authorization": f"Bearer {token_b}", "Idempotency-Key": "vb2"})

    lock = client.post(
        f"/partner/portal/orga/events/{event_id}/battles/rounds/lock",
        json={"roundId": rid},
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "lock-1"},
    )
    assert lock.status_code == 200
    assert lock.json()["winner"] == "A"

    lb = client.get(f"/events/{event_id}/battles/leaderboard", headers={"Authorization": f"Bearer {token_a}"})
    assert lb.status_code == 200
    assert lb.json()["top3"][0]["score"] >= 4

    s = get_session()
    try:
        audit_actions = [r.action for r in s.query(AuditLog).filter(AuditLog.event_id == event_id).all()]
        assert "orga.battles.round.lock" in audit_actions
        assert "battle.vote" in audit_actions
    finally:
        s.close()


def test_leaderboard_masks_private_but_me_visible():
    manager_token, event_id = _seed_partner(module_on=True)
    private_uid, private_token = _seed_user("Priv", visibility="private")
    _, public_token = _seed_user("Pub")
    client = TestClient(app)

    rid = client.post(
        f"/partner/portal/orga/events/{event_id}/battles/rounds/start",
        json={"title": "part", "kind": "PARTICIPATION", "durationSeconds": 120},
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "start-p"},
    ).json()["roundId"]
    client.post(f"/events/{event_id}/battles/vote", json={"roundId": rid, "choice": "PARTICIPATE"}, headers={"Authorization": f"Bearer {private_token}", "Idempotency-Key": "p1"})
    client.post(f"/events/{event_id}/battles/vote", json={"roundId": rid, "choice": "PARTICIPATE"}, headers={"Authorization": f"Bearer {public_token}", "Idempotency-Key": "p2"})
    client.post(f"/partner/portal/orga/events/{event_id}/battles/rounds/lock", json={"roundId": rid}, headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "lock-p"})

    other_view = client.get(f"/events/{event_id}/battles/leaderboard", headers={"Authorization": f"Bearer {public_token}"}).json()
    p_row = next(r for r in other_view["list"] if r["userId"] == private_uid)
    assert p_row["name"].startswith("Anonymous-")

    me_view = client.get(f"/events/{event_id}/battles/leaderboard", headers={"Authorization": f"Bearer {private_token}"}).json()
    me_row = next(r for r in me_view["list"] if r["userId"] == private_uid)
    assert me_row["name"] == "Priv"


def test_runtime_blocked_write_behavior():
    manager_token, event_id = _seed_partner(module_on=True, runtime="PAUSE")
    _, token = _seed_user("Pause")
    client = TestClient(app)

    start = client.post(
        f"/partner/portal/orga/events/{event_id}/battles/rounds/start",
        json={"title": "x", "kind": "PARTICIPATION", "durationSeconds": 120},
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "pause-start"},
    )
    assert start.status_code == 423

    # read remains available
    state = client.get(f"/events/{event_id}/battles/state", headers={"Authorization": f"Bearer {token}"})
    assert state.status_code in {200, 404}


def test_idempotency_required_on_all_write_endpoints():
    manager_token, event_id = _seed_partner(module_on=True)
    _, token = _seed_user("Idem")
    client = TestClient(app)
    rid = client.post(
        f"/partner/portal/orga/events/{event_id}/battles/rounds/start",
        json={"title": "x", "kind": "PARTICIPATION", "durationSeconds": 120},
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "seed"},
    ).json()["roundId"]

    for path, body, hdr in [
        (f"/events/{event_id}/battles/vote", {"roundId": rid, "choice": "PARTICIPATE"}, {"Authorization": f"Bearer {token}"}),
        (f"/partner/portal/orga/events/{event_id}/battles/rounds/lock", {"roundId": rid}, {"Authorization": f"Bearer {manager_token}"}),
        (f"/partner/portal/orga/events/{event_id}/battles/rounds/force_winner", {"roundId": rid, "winner": "NONE", "reason": "manual"}, {"Authorization": f"Bearer {manager_token}"}),
        (f"/partner/portal/orga/events/{event_id}/battles/clear", {"reason": "reset"}, {"Authorization": f"Bearer {manager_token}"}),
    ]:
        res = client.post(path, json=body, headers=hdr)
        assert res.status_code == 400
        assert res.json()["detail"]["reason"] == "IDEMPOTENCY_REQUIRED"
