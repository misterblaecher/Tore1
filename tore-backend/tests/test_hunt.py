from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AppToken, AppUser, Bar, Event, PartnerMembership, PartnerUser, WalletTx
from partner_auth import _make_token


def _seed_partner(role: str = "manager") -> tuple[int, str, int]:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Hunt Bar {suffix}", city="Liege", partner_code=f"HUNT{suffix}")
        s.add(bar)
        s.flush()

        user = PartnerUser(display_name="Partner", pin_hash="hash")
        s.add(user)
        s.flush()

        membership = PartnerMembership(
            user_id=user.id,
            bar_id=bar.id,
            role=role,
            display_name="Partner",
        )
        s.add(membership)

        event = Event(
            bar_id=bar.id,
            name="Hunt Event",
            starts_at=now_utc(),
            ends_at=now_utc() + timedelta(hours=4),
        )
        s.add(event)
        s.commit()
        s.refresh(event)
        token = _make_token(user.id, bar.id, role, "Partner")
        return bar.id, token, event.id
    finally:
        s.close()


def _seed_app_user() -> tuple[str, str]:
    s = get_session()
    try:
        user_id = f"u-{secrets.token_hex(6)}"
        raw_token = f"tok-{secrets.token_hex(12)}"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        user = AppUser(id=user_id, display_name="Hunter")
        token = AppToken(user_id=user_id, token_hash=token_hash)
        s.add_all([user, token])
        s.commit()
        return user_id, raw_token
    finally:
        s.close()


def _create_hunt(client: TestClient, manager_token: str, event_id: int, reward_tickets: int = 0) -> int:
    res = client.post(
        "/partner/portal/hunt",
        json={"event_id": event_id, "name": "Campus Hunt", "reward_tickets": reward_tickets},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert res.status_code == 200
    return res.json()["id"]


def test_hunt_manager_crud_and_bar_guard():
    bar_id, manager_token, event_id = _seed_partner(role="manager")
    _, other_manager_token, _ = _seed_partner(role="manager")
    client = TestClient(app)

    hunt_id = _create_hunt(client, manager_token, event_id)

    create_point = client.post(
        f"/partner/portal/hunt/{hunt_id}/points",
        json={"name": "Entrance", "hint": "Near the door", "sort_order": 1},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert create_point.status_code == 200
    point_id = create_point.json()["id"]

    list_points = client.get(
        f"/partner/portal/hunt/{hunt_id}/points",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert list_points.status_code == 200
    assert list_points.json()[0]["qr_payload"].startswith(f"tore://hunt?event_id={event_id}&code=HP-")

    forbidden = client.patch(
        f"/partner/portal/hunt/{hunt_id}",
        json={"name": "Nope"},
        headers={"Authorization": f"Bearer {other_manager_token}"},
    )
    assert forbidden.status_code == 403

    patch_point = client.patch(
        f"/partner/portal/hunt/points/{point_id}",
        json={"name": "Desk"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert patch_point.status_code == 200
    assert patch_point.json()["name"] == "Desk"

    delete_point = client.delete(
        f"/partner/portal/hunt/points/{point_id}",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert delete_point.status_code == 200
    assert delete_point.json()["ok"] is True
    assert bar_id > 0


def test_hunt_scan_idempotent_and_reward_once():
    _, manager_token, event_id = _seed_partner(role="manager")
    user_id, app_token = _seed_app_user()
    client = TestClient(app)

    hunt_id = _create_hunt(client, manager_token, event_id, reward_tickets=20)

    p1 = client.post(
        f"/partner/portal/hunt/{hunt_id}/points",
        json={"name": "A", "hint": "H1", "sort_order": 1},
        headers={"Authorization": f"Bearer {manager_token}"},
    ).json()
    p2 = client.post(
        f"/partner/portal/hunt/{hunt_id}/points",
        json={"name": "B", "hint": "H2", "sort_order": 2},
        headers={"Authorization": f"Bearer {manager_token}"},
    ).json()

    first_scan = client.post(
        "/hunt/scan",
        json={"event_id": event_id, "code": p1["secret_code"]},
        headers={"Authorization": f"Bearer {app_token}"},
    )
    assert first_scan.status_code == 200
    assert first_scan.json()["already_scanned"] is False

    replay_scan = client.post(
        "/hunt/scan",
        json={"event_id": event_id, "code": p1["secret_code"]},
        headers={"Authorization": f"Bearer {app_token}"},
    )
    assert replay_scan.status_code == 200
    assert replay_scan.json()["already_scanned"] is True
    assert replay_scan.json()["point_id"] == first_scan.json()["point_id"]

    complete_scan = client.post(
        "/hunt/scan",
        json={"event_id": event_id, "code": p2["secret_code"]},
        headers={"Authorization": f"Bearer {app_token}"},
    )
    assert complete_scan.status_code == 200
    assert complete_scan.json()["completed"] is True
    assert complete_scan.json()["reward_granted"] is True

    res_me = client.get(
        f"/hunt/me/event/{event_id}",
        headers={"Authorization": f"Bearer {app_token}"},
    )
    assert res_me.status_code == 200
    assert res_me.json()["completed"] is True

    res_second_completion = client.post(
        "/hunt/scan",
        json={"event_id": event_id, "code": p2["secret_code"]},
        headers={"Authorization": f"Bearer {app_token}"},
    )
    assert res_second_completion.status_code == 200

    s = get_session()
    try:
        txs = (
            s.query(WalletTx)
            .filter(
                WalletTx.user_id == user_id,
                WalletTx.kind == "HUNT_REWARD",
                WalletTx.ref_id == str(hunt_id),
            )
            .all()
        )
        assert len(txs) == 1
        assert txs[0].amount_tickets == 20
    finally:
        s.close()
