from fastapi.testclient import TestClient

import secrets

from db import Base, engine, get_session
from main import app
from models import (
    Bar,
    Bet,
    BetPosition,
    Event,
    MenuCategory,
    MenuItem,
    MenuTrackEvent,
    Order,
    PartnerMembership,
    PartnerUser,
)
from partner_auth import _make_token


def _seed_manager(name: str = "Manager") -> tuple[int, str]:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Analytics Bar {suffix}", city="Test", partner_code=f"ANA{suffix}")
        s.add(bar)
        s.flush()

        user = PartnerUser(display_name=name, pin_hash="hash")
        s.add(user)
        s.flush()

        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role="manager", display_name=name))
        s.commit()
        return bar.id, _make_token(user.id, bar.id, "manager", name)
    finally:
        s.close()


def _seed_analytics_data(bar_id: int) -> int:
    s = get_session()
    try:
        event = Event(bar_id=bar_id, name="Ops Event", ticket_value_cents=100)
        s.add(event)
        s.flush()

        cat = MenuCategory(bar_id=bar_id, name="Shots", sort_order=1)
        s.add(cat)
        s.flush()

        item = MenuItem(bar_id=bar_id, category_id=cat.id, name="Tequila", price_cents=400)
        s.add(item)
        s.flush()

        s.add_all(
            [
                MenuTrackEvent(bar_id=bar_id, event_id=event.id, item_id=item.id, action="view"),
                MenuTrackEvent(bar_id=bar_id, event_id=event.id, item_id=item.id, action="add"),
            ]
        )

        s.add_all(
            [
                Order(bar_id=bar_id, event_id=event.id, total_cents=800, payment_status="PAID", total_tickets=8),
                Order(bar_id=bar_id, event_id=event.id, total_cents=400, payment_status="UNPAID", total_tickets=0),
            ]
        )

        bet = Bet(
            scope="EVENT",
            event_id=event.id,
            question="Will it rain?",
            kind="OBJECTIVE",
            status="LIVE",
            deadline_at=event.ends_at,
            created_by_user_id="user-x",
        )
        s.add(bet)
        s.flush()

        s.add(BetPosition(bet_id=bet.id, user_id="user-x", side="YES", stake_tickets=12, idempotency_key=f"k-{secrets.token_hex(4)}"))

        s.commit()
        return event.id
    finally:
        s.close()


def test_partner_portal_analytics_requires_token():
    client = TestClient(app)
    res = client.get('/partner/portal/analytics/summary')
    assert res.status_code == 401


def test_partner_portal_analytics_forbidden_on_event_bar_mismatch():
    bar_id, token = _seed_manager()
    _seed_analytics_data(bar_id)

    other_event_id = _seed_analytics_data(_seed_manager(name="Other")[0])

    client = TestClient(app)
    res = client.get(
        f'/partner/portal/analytics/summary?event_id={other_event_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert res.status_code == 403


def test_partner_portal_analytics_summary_shape_for_manager():
    bar_id, token = _seed_manager()
    event_id = _seed_analytics_data(bar_id)

    client = TestClient(app)
    res = client.get(
        f'/partner/portal/analytics/summary?event_id={event_id}&days=7',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert res.status_code == 200
    payload = res.json()

    assert 'orders' in payload
    assert 'menu' in payload
    assert 'polymarket' in payload
    assert {'count', 'total_cents', 'paid_count', 'unpaid_count', 'paid_tickets_total'} <= set(payload['orders'].keys())
    assert {'top_items', 'totals'} <= set(payload['menu'].keys())
    assert {
        'bets_live',
        'bets_pending',
        'bets_finalized',
        'total_staked_tickets',
        'total_payout_tickets',
    } <= set(payload['polymarket'].keys())
