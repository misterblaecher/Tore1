import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AppToken, AppUser, Bar, Event, UserPrivacyDeleteRequest
from partner_auth import _make_token
from models import PartnerMembership, PartnerUser


def _seed_admin_global() -> tuple[str, int]:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Capstone Bar {suffix}", city="Liège", partner_code=f"CAP{suffix}")
        s.add(bar)
        s.flush()
        admin = PartnerUser(display_name="Global Admin", pin_hash="hash")
        s.add(admin)
        s.flush()
        s.add(PartnerMembership(user_id=admin.id, bar_id=bar.id, role="manager", display_name="Global Admin"))
        event = Event(bar_id=bar.id, name="Capstone Event", starts_at=now_utc(), ends_at=now_utc() + timedelta(hours=5))
        s.add(event)
        s.commit()
        return _make_token(admin.id, bar.id, "ADMIN_GLOBAL", "Global Admin"), event.id
    finally:
        s.close()


def _guest(client: TestClient, name: str) -> tuple[str, str]:
    Base.metadata.create_all(engine)
    res = client.post("/auth/guest", json={"display_name": name})
    assert res.status_code == 200
    payload = res.json()
    return payload["user"]["id"], payload["token"]


def test_export_endpoints_return_json_and_csv():
    client = TestClient(app)
    _, token = _guest(client, "RGPD User")

    export_json = client.get("/me/export.json", headers={"Authorization": f"Bearer {token}"})
    assert export_json.status_code == 200
    assert "profile" in export_json.json()

    export_csv = client.get("/me/export.csv", headers={"Authorization": f"Bearer {token}"})
    assert export_csv.status_code == 200
    assert "section,field,value" in export_csv.text


def test_delete_is_idempotent_and_status_changes_after_purge():
    client = TestClient(app)
    admin_token, _ = _seed_admin_global()
    user_id, token = _guest(client, "Delete Me")

    delete_first = client.post("/me/delete", headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "del-1"})
    assert delete_first.status_code == 200
    assert delete_first.json()["status"] == "PENDING"

    delete_replay = client.post("/me/delete", headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "del-1"})
    assert delete_replay.status_code == 401

    s = get_session()
    try:
        row = s.query(UserPrivacyDeleteRequest).filter(UserPrivacyDeleteRequest.user_id == user_id).first()
        assert row is not None
        row.effective_at = now_utc() - timedelta(days=1)
        s.add(row)
        s.commit()
    finally:
        s.close()

    purge = client.post("/admin/purge/run", headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "purge-1"})
    assert purge.status_code == 200
    assert purge.json()["purgedCount"] >= 1

    blocked = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert blocked.status_code in {401, 403}


def test_sanctions_block_access_and_revoke_unblocks_and_audit_query_has_idempotency():
    client = TestClient(app)
    admin_token, _ = _seed_admin_global()
    user_id, token = _guest(client, "Sanction Target")

    sanction = client.post(
        f"/admin/users/{user_id}/sanctions",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "sanction-1"},
        json={"type": "SUSPEND", "durationHours": 2, "reason": "abuse"},
    )
    assert sanction.status_code == 200
    sanction_id = sanction.json()["id"]

    blocked = client.get("/wallet/me", headers={"Authorization": f"Bearer {token}"})
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["reason"] == "SANCTIONED"

    revoke = client.post(
        f"/admin/users/{user_id}/sanctions/{sanction_id}/revoke",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "sanction-revoke-1"},
        json={"reason": "appeal accepted"},
    )
    assert revoke.status_code == 200

    unblocked = client.get("/wallet/me", headers={"Authorization": f"Bearer {token}"})
    assert unblocked.status_code == 200

    audit = client.get("/admin/audit", params={"user": user_id}, headers={"Authorization": f"Bearer {admin_token}"})
    assert audit.status_code == 200
    items = audit.json()["items"]
    assert any(item.get("actorUserId") == user_id for item in items)
    assert any(item.get("idempotencyKey") for item in items)


def test_admin_flags_override_modules_response():
    client = TestClient(app)
    admin_token, _ = _seed_admin_global()

    update = client.put(
        "/admin/flags",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "flag-1"},
        json={"key": "committee_os", "enabled": False, "reason": "maintenance"},
    )
    assert update.status_code == 200

    modules = client.get("/modules")
    assert modules.status_code == 200
    assert modules.json()["committee_os"] is False

    flags = client.get("/admin/flags", headers={"Authorization": f"Bearer {admin_token}"})
    assert flags.status_code == 200
    assert any(row["key"] == "committee_os" for row in flags.json()["items"])
