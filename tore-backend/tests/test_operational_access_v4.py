from __future__ import annotations

import json
import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import (
    AppUser,
    AuditLog,
    Bar,
    Event,
    EventAppWriteIdempotency,
    EventRuntimeState,
    EventStaff,
    EventStaffInviteCode,
    MenuCategory,
    MenuItem,
    Order,
    PartnerBarAccess,
    PartnerUser,
)


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _user(name: str) -> tuple[str, str]:
    response = client.post("/auth/guest", json={"display_name": name})
    assert response.status_code == 200
    token = response.json()["token"]
    user_id = response.json()["user"]["id"]
    with get_session() as db:
        user = db.get(AppUser, user_id)
        user.is_guest = False
        user.email = f"{user_id}@private.example"
        db.commit()
    return token, user_id


def _headers(token: str, idem: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if idem:
        headers["Idempotency-Key"] = idem
    return headers


def _event(*, host_id: str | None = None, bar_id: int | None = None, name: str = "Ops") -> int:
    with get_session() as db:
        event = Event(
            bar_id=bar_id,
            name=f"{name}-{secrets.token_hex(3)}",
            starts_at=now_utc() - timedelta(hours=1),
            ends_at=now_utc() + timedelta(hours=5),
            event_state="LIVE",
            host_type="user",
            host_id=host_id,
        )
        db.add(event)
        db.commit()
        return event.id


def _bar_access(user_id: str, *, role: str = "manager") -> tuple[int, int]:
    with get_session() as db:
        suffix = secrets.token_hex(3)
        bar = Bar(name=f"Bar {suffix}", city="Liège", partner_code=f"V4{suffix}")
        db.add(bar)
        db.flush()
        partner = PartnerUser(app_user_id=user_id, display_name="Bar user", pin_hash="hash", is_active=True)
        db.add(partner)
        db.flush()
        access = PartnerBarAccess(
            partner_user_id=partner.id,
            bar_id=bar.id,
            role=role,
            is_active=True,
            status="ACTIVE",
            starts_at=now_utc() - timedelta(minutes=1),
            expires_at=now_utc() + timedelta(hours=4),
        )
        db.add(access)
        db.commit()
        return bar.id, access.id


def _invite(owner_token: str, event_id: int, target_user_id: str, *, key: str = "invite-1") -> dict:
    response = client.post(
        f"/ops/events/{event_id}/staff-invitations",
        headers=_headers(owner_token, key),
        json={"target_user_id": target_user_id, "role": "ENTRY", "expires_in_hours": 12},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_user_mode_is_not_authorized_by_account_mode_or_forged_client_data():
    token, user_id = _user("Simple User")
    with get_session() as db:
        db.get(AppUser, user_id).account_mode = "organizer"
        db.commit()

    capabilities = client.get("/me/capabilities", headers=_headers(token))
    assert capabilities.status_code == 200
    assert capabilities.json()["capabilities"] == []
    assert capabilities.json()["operational_modes"] == {"organizer": False, "bar": False}

    event_id = _event(name="Forbidden")
    denied = client.get(
        f"/ops/events/{event_id}",
        headers={**_headers(token), "X-Tore-Capabilities": "event.manage_staff,event.manage_entry"},
    )
    assert denied.status_code == 403


def test_event_capability_active_then_expired_and_revoked_immediately():
    owner_token, owner_id = _user("Owner")
    staff_token, staff_id = _user("Entry")
    event_id = _event(host_id=owner_id)
    with get_session() as db:
        db.add(EventStaff(
            event_id=event_id,
            user_id=staff_id,
            role="entry",
            is_active=True,
            expires_at=now_utc() + timedelta(hours=2),
        ))
        db.commit()

    current = client.get("/me/capabilities", headers=_headers(staff_token)).json()
    assert current["operational_modes"]["organizer"] is True
    assert current["events"][0]["event_id"] == event_id
    assert "event.manage_entry" in current["events"][0]["actions"]

    revoked = client.post(
        f"/ops/events/{event_id}/staff/{staff_id}/revoke",
        headers=_headers(owner_token),
        json={"reason": "Shift completed"},
    )
    assert revoked.status_code == 200
    assert client.get(f"/ops/events/{event_id}", headers=_headers(staff_token)).status_code == 403

    with get_session() as db:
        row = db.query(EventStaff).filter(EventStaff.event_id == event_id, EventStaff.user_id == staff_id).one()
        row.is_active = True
        row.revoked_at = None
        row.expires_at = now_utc() - timedelta(seconds=1)
        db.commit()
    assert client.get(f"/ops/events/{event_id}", headers=_headers(staff_token)).status_code == 403


def test_secure_targeted_invitation_acceptance_idempotence_and_replay_protection():
    owner_token, owner_id = _user("Invite Owner")
    target_token, target_id = _user("Invite Target")
    wrong_token, _ = _user("Wrong Target")
    event_id = _event(host_id=owner_id)
    created = _invite(owner_token, event_id, target_id)
    raw_token = created["token"]
    assert raw_token and raw_token not in created["id"].__str__()

    with get_session() as db:
        stored = db.get(EventStaffInviteCode, created["id"])
        assert stored.token_hash and stored.token_hash != raw_token
        assert raw_token not in json.dumps(stored.__dict__, default=str)

    wrong = client.post(
        "/me/event-staff-invitations/accept",
        headers=_headers(wrong_token, "accept-wrong"),
        json={"token": raw_token},
    )
    assert wrong.status_code == 403

    first = client.post(
        "/me/event-staff-invitations/accept",
        headers=_headers(target_token, "accept-ok"),
        json={"token": raw_token},
    )
    retry = client.post(
        "/me/event-staff-invitations/accept",
        headers=_headers(target_token, "accept-ok"),
        json={"token": raw_token},
    )
    replay = client.post(
        "/me/event-staff-invitations/accept",
        headers=_headers(target_token, "accept-replay"),
        json={"token": raw_token},
    )
    assert first.status_code == retry.status_code == 200
    assert retry.json()["idempotent"] is True
    assert replay.status_code == 409
    assert client.get(f"/ops/events/{event_id}", headers=_headers(target_token)).status_code == 200


def test_invitation_expiry_revoke_and_audit_never_expose_token():
    owner_token, owner_id = _user("Audit Owner")
    target_token, target_id = _user("Audit Target")
    event_id = _event(host_id=owner_id)
    expired = _invite(owner_token, event_id, target_id, key="invite-expired")
    with get_session() as db:
        row = db.get(EventStaffInviteCode, expired["id"])
        row.expires_at = now_utc() - timedelta(seconds=1)
        db.commit()
    rejected = client.post(
        "/me/event-staff-invitations/accept",
        headers=_headers(target_token, "expired-accept"),
        json={"token": expired["token"]},
    )
    assert rejected.status_code == 409

    pending = _invite(owner_token, event_id, target_id, key="invite-revoke")
    revoked = client.post(
        f"/ops/events/{event_id}/staff-invitations/{pending['id']}/revoke",
        headers=_headers(owner_token),
        json={"reason": "Planning changed"},
    )
    assert revoked.status_code == 200
    old_token = client.post(
        "/me/event-staff-invitations/accept",
        headers=_headers(target_token, "revoked-accept"),
        json={"token": pending["token"]},
    )
    assert old_token.status_code == 409

    audit = client.get(f"/ops/events/{event_id}/audit", headers=_headers(owner_token))
    assert audit.status_code == 200
    serialized = json.dumps(audit.json())
    assert expired["token"] not in serialized
    assert pending["token"] not in serialized
    with get_session() as db:
        assert all("token" not in json.dumps(row.payload_json or {}) for row in db.query(AuditLog).all())


def test_event_a_capability_never_opens_event_b_or_its_entry_endpoint():
    _, owner_id = _user("Other Host")
    staff_token, staff_id = _user("Scoped Entry")
    event_a = _event(host_id=owner_id, name="A")
    event_b = _event(host_id=owner_id, name="B")
    with get_session() as db:
        db.add(EventStaff(event_id=event_a, user_id=staff_id, role="entry", is_active=True))
        db.commit()

    assert client.get(f"/ops/events/{event_a}", headers=_headers(staff_token)).status_code == 200
    assert client.get(f"/ops/events/{event_b}", headers=_headers(staff_token)).status_code == 403
    cross_scan = client.post(
        f"/events/{event_b}/entry/checkin",
        headers=_headers(staff_token, "cross-event-scan"),
        json={"ticket_qr_raw": "TICKET-B", "scanned_at": now_utc().isoformat(), "device_id": "gate-a"},
    )
    assert cross_scan.status_code == 403


def test_bar_capability_is_scoped_and_revocation_is_immediate():
    token, user_id = _user("Bar Operator")
    bar_a, access_id = _bar_access(user_id)
    with get_session() as db:
        suffix = secrets.token_hex(3)
        bar_b = Bar(name="Bar B", city="Namur", partner_code=f"B{suffix}")
        db.add(bar_b)
        db.commit()
        bar_b_id = bar_b.id

    capabilities = client.get("/me/capabilities", headers=_headers(token)).json()
    assert capabilities["operational_modes"]["bar"] is True
    assert [item["bar_id"] for item in capabilities["bars"]] == [bar_a]
    assert client.get(f"/ops/bars/{bar_a}", headers=_headers(token)).status_code == 200
    assert client.get(f"/ops/bars/{bar_b_id}", headers=_headers(token)).status_code == 403

    with get_session() as db:
        access = db.get(PartnerBarAccess, access_id)
        access.status = "REVOKED"
        access.revoked_at = now_utc()
        access.is_active = False
        db.commit()
    assert client.get(f"/ops/bars/{bar_a}", headers=_headers(token)).status_code == 403


def test_bar_menu_availability_is_scoped_idempotent_and_price_is_read_only():
    manager_token, manager_id = _user("Menu Manager")
    staff_token, staff_id = _user("Menu Staff")
    bar_id, _ = _bar_access(manager_id)
    _bar_access(staff_id, role="bartender")
    with get_session() as db:
        category = MenuCategory(bar_id=bar_id, name="Drinks")
        db.add(category)
        db.flush()
        item = MenuItem(bar_id=bar_id, category_id=category.id, name="Cola", price_cents=350)
        db.add(item)
        db.commit()
        item_id = item.id

    url = f"/ops/bars/{bar_id}/menu/items/{item_id}/availability"
    listed = client.get(f"/ops/bars/{bar_id}/menu", headers=_headers(manager_token))
    assert listed.status_code == 200
    assert listed.json()["items"][0]["price_cents"] == 350
    assert client.get(f"/ops/bars/{bar_id}/menu", headers=_headers(staff_token)).status_code == 403
    assert client.put(url, headers=_headers(manager_token), json={
        "available": False, "stock_status": "OUT", "expected_version": 1,
    }).status_code == 400
    payload = {"available": False, "stock_status": "OUT", "expected_version": 1}
    first = client.put(url, headers=_headers(manager_token, "menu-out"), json=payload)
    replay = client.put(url, headers=_headers(manager_token, "menu-out"), json=payload)
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert first.json()["item"]["version"] == 2
    assert client.put(url, headers=_headers(manager_token, "menu-stale"), json=payload).status_code == 409
    assert client.put(url, headers=_headers(manager_token, "menu-price"), json={
        **payload, "price_cents": 1,
    }).status_code == 422
    with get_session() as db:
        saved = db.get(MenuItem, item_id)
        assert saved.price_cents == 350
        assert saved.is_available is False


def test_bar_order_scope_valid_transitions_invalid_transition_and_idempotence():
    token, user_id = _user("Order Operator")
    bar_a, _ = _bar_access(user_id)
    with get_session() as db:
        suffix = secrets.token_hex(3)
        bar_b = Bar(name="Other Bar", city="Mons", partner_code=f"O{suffix}")
        db.add(bar_b)
        db.flush()
        event_a = Event(bar_id=bar_a, name="Order Event A", event_state="LIVE", ends_at=now_utc() + timedelta(hours=3))
        event_b = Event(bar_id=bar_b.id, name="Order Event B", event_state="LIVE", ends_at=now_utc() + timedelta(hours=3))
        db.add_all([event_a, event_b])
        db.flush()
        own = Order(bar_id=bar_a, event_id=event_a.id, status="NEW", total_tickets=2)
        other = Order(bar_id=bar_b.id, event_id=event_b.id, status="NEW", total_tickets=3)
        db.add_all([own, other])
        db.commit()
        own_id, other_id = own.id, other.id

    listed = client.get(f"/ops/bars/{bar_a}/orders", headers=_headers(token))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [own_id]
    cross = client.post(
        f"/ops/bars/{bar_a}/orders/{other_id}/transition",
        headers=_headers(token, "cross-order"),
        json={"action": "accept"},
    )
    assert cross.status_code == 403

    first = client.post(
        f"/ops/bars/{bar_a}/orders/{own_id}/transition",
        headers=_headers(token, "accept-own"),
        json={"action": "accept"},
    )
    retry = client.post(
        f"/ops/bars/{bar_a}/orders/{own_id}/transition",
        headers=_headers(token, "accept-own"),
        json={"action": "accept"},
    )
    invalid = client.post(
        f"/ops/bars/{bar_a}/orders/{own_id}/transition",
        headers=_headers(token, "complete-too-soon"),
        json={"action": "complete"},
    )
    assert first.status_code == retry.status_code == 200
    assert first.json()["status"] == "accepted"
    assert retry.json()["idempotent"] is True
    assert invalid.status_code == 409



def test_event_manage_state_capability_is_limited_to_admin_and_manager():
    host_token, host_id = _user("Runtime Host")
    manager_token, manager_id = _user("Runtime Manager")
    admin_token, admin_id = _user("Runtime Admin")
    entry_token, entry_id = _user("Runtime Entry")
    event_id = _event(host_id=host_id, name="Runtime capability")
    with get_session() as db:
        db.add_all([
            EventStaff(event_id=event_id, user_id=manager_id, role="manager", is_active=True),
            EventStaff(event_id=event_id, user_id=admin_id, role="admin", is_active=True),
            EventStaff(event_id=event_id, user_id=entry_id, role="entry", is_active=True),
        ])
        db.commit()

    host_actions = client.get("/me/capabilities", headers=_headers(host_token)).json()["events"][0]["actions"]
    manager_actions = client.get("/me/capabilities", headers=_headers(manager_token)).json()["events"][0]["actions"]
    admin_actions = client.get("/me/capabilities", headers=_headers(admin_token)).json()["events"][0]["actions"]
    entry_actions = client.get("/me/capabilities", headers=_headers(entry_token)).json()["events"][0]["actions"]

    assert "event.manage_state" in host_actions
    assert "event.manage_state" in manager_actions
    assert "event.manage_state" in admin_actions
    assert "event.manage_state" not in entry_actions


def test_event_runtime_state_requires_capability_reason_and_idempotency():
    _, owner_id = _user("Runtime Owner")
    manager_token, manager_id = _user("Runtime Manager")
    entry_token, entry_id = _user("Runtime Entry")
    event_id = _event(host_id=owner_id, name="Runtime command")
    with get_session() as db:
        db.add_all([
            EventStaff(event_id=event_id, user_id=manager_id, role="manager", is_active=True),
            EventStaff(event_id=event_id, user_id=entry_id, role="entry", is_active=True),
        ])
        db.commit()

    denied = client.post(
        f"/ops/events/{event_id}/state",
        headers=_headers(entry_token, "runtime-entry"),
        json={"state": "PAUSE", "reason": "Pause demandée"},
    )
    assert denied.status_code == 403

    missing_key = client.post(
        f"/ops/events/{event_id}/state",
        headers=_headers(manager_token),
        json={"state": "PAUSE", "reason": "Pause demandée"},
    )
    assert missing_key.status_code == 400
    assert missing_key.json()["detail"]["reason"] == "IDEMPOTENCY_REQUIRED"

    missing_reason = client.post(
        f"/ops/events/{event_id}/state",
        headers=_headers(manager_token, "runtime-no-reason"),
        json={"state": "PAUSE"},
    )
    assert missing_reason.status_code == 400
    assert missing_reason.json()["detail"]["reason"] == "reason_required"


def test_event_runtime_state_replay_audit_and_hub_use_server_runtime_state():
    token, user_id = _user("Runtime Manager")
    event_id = _event(host_id=user_id, name="Runtime replay")
    headers = _headers(token, "runtime-pause-1")
    payload = {"state": "PAUSE", "reason": "Incident temporaire"}

    first = client.post(f"/ops/events/{event_id}/state", headers=headers, json=payload)
    replay = client.post(f"/ops/events/{event_id}/state", headers=headers, json=payload)

    assert first.status_code == replay.status_code == 200
    assert first.json()["state"] == "PAUSE"
    assert first.json()["reason"] == "Incident temporaire"
    assert first.json()["idempotent"] is False
    assert replay.json()["state"] == "PAUSE"
    assert replay.json()["idempotent"] is True

    hub = client.get(f"/ops/events/{event_id}", headers=_headers(token))
    assert hub.status_code == 200
    assert hub.json()["event"]["state"] == "PAUSE"
    assert hub.json()["event"]["runtime_reason"] == "Incident temporaire"

    with get_session() as db:
        runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).one()
        assert runtime.state == "PAUSE"
        assert runtime.reason == "Incident temporaire"
        assert db.query(EventAppWriteIdempotency).filter(
            EventAppWriteIdempotency.actor_user_id == user_id,
            EventAppWriteIdempotency.action == f"event_state:{event_id}",
            EventAppWriteIdempotency.idempotency_key == "runtime-pause-1",
        ).count() == 1
        audits = db.query(AuditLog).filter(
            AuditLog.event_id == event_id,
            AuditLog.action == "event_state.update",
        ).all()
        assert len(audits) == 1
        assert audits[0].payload_json["before"] == {"state": "LIVE", "reason": None}
        assert audits[0].payload_json["after"] == {
            "state": "PAUSE",
            "reason": "Incident temporaire",
        }


def test_event_runtime_state_cross_event_scope_is_forbidden():
    _, owner_id = _user("Runtime Scope Owner")
    manager_token, manager_id = _user("Runtime Scoped Manager")
    event_a = _event(host_id=owner_id, name="Runtime A")
    event_b = _event(host_id=owner_id, name="Runtime B")
    with get_session() as db:
        db.add(EventStaff(
            event_id=event_a,
            user_id=manager_id,
            role="manager",
            is_active=True,
        ))
        db.commit()

    own = client.post(
        f"/ops/events/{event_a}/state",
        headers=_headers(manager_token, "runtime-a"),
        json={"state": "DEGRADED", "reason": "Réseau instable"},
    )
    cross = client.post(
        f"/ops/events/{event_b}/state",
        headers=_headers(manager_token, "runtime-b"),
        json={"state": "PAUSE", "reason": "Tentative hors scope"},
    )

    assert own.status_code == 200
    assert cross.status_code == 403
    with get_session() as db:
        assert db.query(EventRuntimeState).filter(
            EventRuntimeState.event_id == event_b
        ).count() == 0
