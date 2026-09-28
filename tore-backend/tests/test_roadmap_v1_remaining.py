import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import (
    AppUser,
    Bar,
    Bet,
    Event,
    EventModuleConfig,
    PartnerMembership,
    PartnerUser,
    TicketBalance,
    Wallet,
)
from partner_auth import _make_token


def _seed_partner(role: str = "manager") -> tuple[int, str]:
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Bar {suffix}", city="City", partner_code=f"RM{suffix}")
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name="Partner", pin_hash="hash")
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role=role, display_name="Partner"))
        s.commit()
        return bar.id, _make_token(user.id, bar.id, role, "Partner")
    finally:
        s.close()


def _seed_event(bar_id: int) -> int:
    s = get_session()
    try:
        event = Event(
            bar_id=bar_id,
            name="Roadmap Event",
            starts_at=now_utc(),
            ends_at=now_utc() + timedelta(hours=4),
            entry_price_cents=0,
            ticket_mode=True,
        )
        s.add(event)
        s.commit()
        s.refresh(event)
        return event.id
    finally:
        s.close()


def _seed_user(user_id: str = "guest-v1") -> str:
    s = get_session()
    try:
        existing = s.get(AppUser, user_id)
        if not existing:
            s.add(AppUser(id=user_id, display_name="Guest"))
            s.commit()
        return user_id
    finally:
        s.close()


def _seed_event_bet(event_id: int, resolver_user_id: str) -> int:
    s = get_session()
    try:
        bet = Bet(
            scope="EVENT",
            event_id=event_id,
            question="Will queue be > 10?",
            kind="OBJECTIVE",
            status="RESOLVED_PENDING",
            deadline_at=now_utc() - timedelta(hours=1),
            resolver_user_id=resolver_user_id,
            rules_text="rule",
            dispute_window_minutes=60,
            created_by_user_id="creator",
            resolved_outcome="YES",
            resolved_at=now_utc(),
        )
        s.add(bet)
        s.commit()
        s.refresh(bet)
        return bet.id
    finally:
        s.close()


def test_entry_scan_guards_and_idempotency():
    Base.metadata.create_all(engine)
    bar_id, manager_token = _seed_partner("manager")
    _, bartender_token = _seed_partner("bartender")
    event_id = _seed_event(bar_id)
    client = TestClient(app)

    issued = client.post("/entry/tokens/issue", json={"event_id": event_id, "count": 1}, headers={"Authorization": f"Bearer {manager_token}"})
    assert issued.status_code == 200
    token = issued.json()["issued"][0]["token"]

    unauth = client.post("/entry/scan", json={"event_id": event_id, "token": token, "scan_id": "s10"})
    assert unauth.status_code == 401

    wrong_bar = client.post(
        "/entry/scan",
        json={"event_id": event_id, "token": token, "scan_id": "s10"},
        headers={"Authorization": f"Bearer {bartender_token}"},
    )
    assert wrong_bar.status_code == 403

    ok = client.post(
        "/entry/scan",
        json={"event_id": event_id, "token": token, "scan_id": "s20"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert ok.status_code == 200
    assert ok.json()["decision"] == "ACCEPT"

    dup = client.post(
        "/entry/scan",
        json={"event_id": event_id, "token": token, "scan_id": "s20"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert dup.status_code == 200
    assert dup.json()["idempotent"] is True
    assert dup.json()["log_id"] == ok.json()["log_id"]

    logs = client.get(f"/entry/logs?event_id={event_id}", headers={"Authorization": f"Bearer {manager_token}"})
    assert logs.status_code == 200
    assert len(logs.json()["items"]) >= 1


def test_event_module_toggles_defaults_and_guard():
    Base.metadata.create_all(engine)
    bar_id, manager_token = _seed_partner("manager")
    _, staff_token = _seed_partner("bartender")
    event_id = _seed_event(bar_id)
    client = TestClient(app)

    get_res = client.get(
        f"/partner/portal/event/{event_id}/modules",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["orders_enabled"] is False
    assert data["market_enabled"] is False

    forbidden = client.post(
        f"/partner/portal/event/{event_id}/modules",
        json={"orders_enabled": True},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert forbidden.status_code == 403

    update_res = client.post(
        f"/partner/portal/event/{event_id}/modules",
        json={"orders_enabled": True, "entry_enabled": True},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["orders_enabled"] is True
    assert update_res.json()["entry_enabled"] is True

    s = get_session()
    try:
        cfg = s.query(EventModuleConfig).filter(EventModuleConfig.event_id == event_id).first()
        assert cfg is not None
        assert cfg.orders_enabled is True
    finally:
        s.close()


def test_event_config_exposes_ticker_enabled_from_market_enabled():
    Base.metadata.create_all(engine)
    bar_id, _ = _seed_partner("manager")
    event_id = _seed_event(bar_id)
    client = TestClient(app)

    guest = client.post("/auth/guest", json={"display_name": "Ticker Config"})
    assert guest.status_code == 200
    token = guest.json()["token"]

    s = get_session()
    try:
        cfg = EventModuleConfig(event_id=event_id, market_enabled=True)
        s.add(cfg)
        s.commit()
    finally:
        s.close()

    enabled = client.get(
        f"/events/{event_id}/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["ticker_enabled"] is True

    s = get_session()
    try:
        cfg = s.query(EventModuleConfig).filter(
            EventModuleConfig.event_id == event_id
        ).first()
        assert cfg is not None
        cfg.market_enabled = False
        s.commit()
    finally:
        s.close()

    disabled = client.get(
        f"/events/{event_id}/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["ticker_enabled"] is False


def test_wallet_admin_topup_idempotent_and_balance_delta():
    Base.metadata.create_all(engine)
    bar_id, manager_token = _seed_partner("manager")
    event_id = _seed_event(bar_id)
    user_id = _seed_user(f"wallet-{secrets.token_hex(4)}")
    client = TestClient(app)

    first = client.post(
        "/partner/portal/wallet/admin/topup",
        json={
            "event_id": event_id,
            "user_id": user_id,
            "amount_tickets": 25,
            "reason": "manual correction",
            "idempotency_key": "wallet-topup-1",
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert first.status_code == 200
    assert first.json()["idempotent"] is False

    second = client.post(
        "/partner/portal/wallet/admin/topup",
        json={
            "event_id": event_id,
            "user_id": user_id,
            "amount_tickets": 25,
            "reason": "manual correction",
            "idempotency_key": "wallet-topup-1",
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert second.status_code == 200
    assert second.json()["idempotent"] is True

    s = get_session()
    try:
        wallet = s.get(Wallet, user_id)
        assert wallet is not None
        assert wallet.balance_tickets == 25
        tb = s.query(TicketBalance).filter(TicketBalance.event_id == event_id, TicketBalance.user_id == user_id).first()
        assert tb is not None
        assert tb.balance == 25
    finally:
        s.close()


def test_polymarket_event_listing_guard_and_finalize_disputed():
    Base.metadata.create_all(engine)
    bar_id, manager_token = _seed_partner("manager")
    _, other_token = _seed_partner("manager")
    event_id = _seed_event(bar_id)
    client = TestClient(app)
    guest = client.post("/auth/guest", json={"display_name": "Resolver"})
    assert guest.status_code == 200
    guest_token = guest.json()["token"]
    guest_user_id = guest.json()["user"]["id"]
    bet_id = _seed_event_bet(event_id, guest_user_id)

    list_ok = client.get(
        f"/partner/portal/polymarket/event/{event_id}",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert list_ok.status_code == 200
    bets = list_ok.json()["bets"]
    assert len(bets) >= 1
    assert bets[0]["status"] in {"RESOLVED_PENDING", "DISPUTED", "FINALIZED", "LIVE", "CANCELLED"}

    list_forbidden = client.get(
        f"/partner/portal/polymarket/event/{event_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert list_forbidden.status_code == 403

    dispute_guest = client.post("/auth/guest", json={"display_name": "Disputer"})
    assert dispute_guest.status_code == 200
    dispute_token = dispute_guest.json()["token"]

    dispute_res = client.post(
        f"/polymarket/bets/{bet_id}/dispute",
        json={"reason": "bad resolve"},
        headers={"Authorization": f"Bearer {dispute_token}"},
    )
    assert dispute_res.status_code == 200

    finalize_res = client.post(
        f"/polymarket/bets/{bet_id}/finalize",
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert finalize_res.status_code == 403
