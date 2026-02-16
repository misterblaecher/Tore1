from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import (
    AppToken,
    AppUser,
    AppUserPrivacySetting,
    AuditLog,
    Bar,
    Event,
    EventHuntSteal,
    EventModuleConfig,
    EventQrToken,
    PartnerMembership,
    PartnerUser,
)
from partner_auth import _make_token


def _seed_partner(role: str = "manager", module_on: bool = True) -> tuple[str, int, str, int]:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Hunt V1 {suffix}", city="Liege", partner_code=f"HV1{suffix}")
        s.add(bar)
        s.flush()

        partner = PartnerUser(display_name="Orga", pin_hash="hash")
        s.add(partner)
        s.flush()
        s.add(PartnerMembership(user_id=partner.id, bar_id=bar.id, role=role, display_name="Orga"))

        event = Event(bar_id=bar.id, name="Hunt Event", starts_at=now_utc() - timedelta(hours=1), ends_at=now_utc() + timedelta(hours=3))
        s.add(event)
        s.flush()
        s.add(EventModuleConfig(event_id=event.id, hunt_enabled=module_on, orders_enabled=True, market_enabled=False, battles_enabled=False, polymarket_enabled=False, entry_enabled=True, checkins_enabled=True, wifi_enabled=True, safety_enabled=True))

        token = _make_token(partner.id, bar.id, role, "Orga")
        s.commit()
        return token, bar.id, str(partner.id), event.id
    finally:
        s.close()


def _seed_user(display_name: str = "Hunter", visibility: str | None = None) -> tuple[str, str]:
    s = get_session()
    try:
        user_id = f"u-{secrets.token_hex(5)}"
        raw_token = f"tok-{secrets.token_hex(12)}"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        s.add(AppUser(id=user_id, display_name=display_name))
        s.add(AppToken(user_id=user_id, token_hash=token_hash))
        if visibility:
            s.add(AppUserPrivacySetting(user_id=user_id, visibility=visibility, show_identity_to_staff=False, show_identity_in_bar=False))
        s.commit()
        return user_id, raw_token
    finally:
        s.close()


def _create_hunt(client: TestClient, manager_token: str, event_id: int, idem: str = "hunt-create-1") -> dict:
    res = client.post(
        f"/partner/portal/orga/events/{event_id}/hunts",
        json={
            "title": "Campus Hunt",
            "description": "Find all QR",
            "startsAt": (now_utc() - timedelta(minutes=5)).isoformat(),
            "endsAt": (now_utc() + timedelta(hours=2)).isoformat(),
            "rulesText": "No cheating",
            "checkpoints": [
                {"label": "A", "points": 10, "orderIndex": 1},
                {"label": "B", "points": 20, "orderIndex": 2},
            ],
        },
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": idem},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _claim_from_deeplink(client: TestClient, app_token: str, event_id: int, hunt_id: int, deeplink: str, idem: str) -> dict:
    params = parse_qs(urlparse(deeplink).query)
    checkpoint_id = int(params["checkpoint_id"][0])
    token = params["token"][0]
    res = client.post(
        f"/events/{event_id}/hunts/{hunt_id}/claim",
        json={"checkpointId": checkpoint_id, "token": token},
        headers={"Authorization": f"Bearer {app_token}", "Idempotency-Key": idem},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_hunt_v1_module_off_strict():
    manager_token, _, _, event_id = _seed_partner(module_on=False)
    _, app_token = _seed_user()
    client = TestClient(app)

    create = client.post(
        f"/partner/portal/orga/events/{event_id}/hunts",
        json={"title": "X", "startsAt": now_utc().isoformat(), "endsAt": (now_utc() + timedelta(hours=1)).isoformat(), "checkpoints": []},
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "off-create"},
    )
    assert create.status_code == 404
    assert create.json()["detail"]["reason"] == "MODULE_OFF"

    active = client.get(f"/events/{event_id}/hunts/active", headers={"Authorization": f"Bearer {app_token}"})
    assert active.status_code == 404
    assert active.json()["detail"]["reason"] == "MODULE_OFF"


def test_hunt_v1_create_idempotent_and_claim_replay():
    manager_token, _, _, event_id = _seed_partner(module_on=True)
    _, app_token = _seed_user()
    client = TestClient(app)

    first = _create_hunt(client, manager_token, event_id, idem="hunt-create-idem")
    second = _create_hunt(client, manager_token, event_id, idem="hunt-create-idem")
    assert second["id"] == first["id"]

    hunt_id = first["id"]
    qr_pack = client.get(f"/partner/portal/orga/hunts/{hunt_id}/qr_pack", headers={"Authorization": f"Bearer {manager_token}"})
    assert qr_pack.status_code == 200
    first_qr = qr_pack.json()["items"][0]["deeplink"]

    claim_1 = _claim_from_deeplink(client, app_token, event_id, hunt_id, first_qr, idem="claim-1")
    assert claim_1["ok"] is True
    assert claim_1["alreadyClaimed"] is False
    assert claim_1["pointsAwarded"] == 10

    claim_2 = _claim_from_deeplink(client, app_token, event_id, hunt_id, first_qr, idem="claim-2")
    assert claim_2["alreadyClaimed"] is True
    assert claim_2["pointsAwarded"] == 0


def test_hunt_v1_claim_invalid_or_expired_token():
    manager_token, _, _, event_id = _seed_partner(module_on=True)
    _, app_token = _seed_user()
    client = TestClient(app)

    hunt = _create_hunt(client, manager_token, event_id, idem="hunt-create-exp")
    hunt_id = hunt["id"]
    qr_pack = client.get(f"/partner/portal/orga/hunts/{hunt_id}/qr_pack", headers={"Authorization": f"Bearer {manager_token}"}).json()
    deeplink = qr_pack["items"][0]["deeplink"]
    params = parse_qs(urlparse(deeplink).query)

    invalid = client.post(
        f"/events/{event_id}/hunts/{hunt_id}/claim",
        json={"checkpointId": int(params["checkpoint_id"][0]), "token": "bad"},
        headers={"Authorization": f"Bearer {app_token}", "Idempotency-Key": "claim-invalid"},
    )
    assert invalid.status_code == 400

    s = get_session()
    try:
        token_id = params["token_id"][0]
        row = s.query(EventQrToken).filter_by(token_id=token_id).first()
        row.expires_at = now_utc() - timedelta(minutes=1)
        s.add(row)
        s.commit()
    finally:
        s.close()

    expired = client.post(
        f"/events/{event_id}/hunts/{hunt_id}/claim",
        json={"checkpointId": int(params["checkpoint_id"][0]), "token": params["token"][0]},
        headers={"Authorization": f"Bearer {app_token}", "Idempotency-Key": "claim-expired"},
    )
    assert expired.status_code == 400
    assert expired.json()["detail"]["reason"] == "expired_token"


def test_hunt_v1_leaderboard_masking_and_steal_guards_and_audit():
    manager_token, _, _, event_id = _seed_partner(module_on=True)
    user_a, token_a = _seed_user("Alice")
    user_b, token_b = _seed_user("Bob", visibility="private")
    client = TestClient(app)

    hunt = _create_hunt(client, manager_token, event_id, idem="hunt-create-lb")
    hunt_id = hunt["id"]
    qr_pack = client.get(f"/partner/portal/orga/hunts/{hunt_id}/qr_pack", headers={"Authorization": f"Bearer {manager_token}"}).json()

    _claim_from_deeplink(client, token_a, event_id, hunt_id, qr_pack["items"][0]["deeplink"], idem="a-c1")
    _claim_from_deeplink(client, token_a, event_id, hunt_id, qr_pack["items"][1]["deeplink"], idem="a-c2")
    _claim_from_deeplink(client, token_b, event_id, hunt_id, qr_pack["items"][1]["deeplink"], idem="b-c1")

    lb = client.get(f"/events/{event_id}/hunts/{hunt_id}/leaderboard", headers={"Authorization": f"Bearer {token_a}"})
    assert lb.status_code == 200
    rows = lb.json()["list"]
    row_b = next(r for r in rows if r["userId"] == user_b)
    assert row_b["name"].startswith("Anonymous-")

    steal_private = client.post(
        f"/events/{event_id}/hunts/{hunt_id}/steal",
        json={"victimUserId": user_b},
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "steal-private"},
    )
    assert steal_private.status_code == 200
    assert steal_private.json()["result"] == "VICTIM_PRIVATE"

    steal_ok = client.post(
        f"/events/{event_id}/hunts/{hunt_id}/steal",
        json={"victimUserId": user_a},
        headers={"Authorization": f"Bearer {token_b}", "Idempotency-Key": "steal-ok"},
    )
    assert steal_ok.status_code == 200
    assert steal_ok.json()["ok"] is True

    steal_cd = client.post(
        f"/events/{event_id}/hunts/{hunt_id}/steal",
        json={"victimUserId": user_a},
        headers={"Authorization": f"Bearer {token_b}", "Idempotency-Key": "steal-cd"},
    )
    assert steal_cd.status_code == 200
    assert steal_cd.json()["result"] == "COOLDOWN"

    s = get_session()
    try:
        audit_actions = [r.action for r in s.query(AuditLog).filter(AuditLog.event_id == event_id).all()]
        assert "orga.hunt.create" in audit_actions
        assert "hunt.claim" in audit_actions
        assert "hunt.steal" in audit_actions
        steal_rows = s.query(EventHuntSteal).filter(EventHuntSteal.hunt_id == hunt_id).all()
        assert len(steal_rows) >= 2
    finally:
        s.close()
