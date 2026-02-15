import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, Order, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_partner(role: str = 'bartender'):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f'Bar {suffix}', city='Liege', partner_code=f'BAR{suffix}')
        s.add(bar)
        s.flush()

        user = PartnerUser(display_name='Bar Ops', pin_hash='hash')
        s.add(user)
        s.flush()

        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role=role, display_name='Bar Ops'))
        event = Event(bar_id=bar.id, name='Dashboard Event', event_state='PAUSE')
        s.add(event)
        s.commit()

        return bar.id, event.id, _make_token(user.id, bar.id, role, 'Bar Ops')
    finally:
        s.close()


def _seed_orders(event_id: int, bar_id: int):
    s = get_session()
    try:
        now = now_utc()
        rows = [
            Order(bar_id=bar_id, event_id=event_id, status='NEW', total_tickets=4, created_at=now - timedelta(minutes=20), updated_at=now - timedelta(minutes=20)),
            Order(bar_id=bar_id, event_id=event_id, status='NEW', total_tickets=2, created_at=now - timedelta(minutes=15), updated_at=now - timedelta(minutes=14)),
            Order(bar_id=bar_id, event_id=event_id, status='IN_PROGRESS', total_tickets=6, created_at=now - timedelta(minutes=10), updated_at=now - timedelta(minutes=7)),
            Order(bar_id=bar_id, event_id=event_id, status='READY', total_tickets=8, created_at=now - timedelta(minutes=9), updated_at=now - timedelta(minutes=5)),
            Order(bar_id=bar_id, event_id=event_id, status='CANCELLED', total_tickets=1, created_at=now - timedelta(minutes=8), updated_at=now - timedelta(minutes=7)),
        ]
        s.add_all(rows)
        s.commit()
    finally:
        s.close()


def test_dashboard_access_denied_without_bar_role():
    bar_id, event_id, _ = _seed_partner(role='bartender')

    s = get_session()
    try:
        outsider = PartnerUser(display_name='Outsider', pin_hash='hash')
        s.add(outsider)
        s.flush()
        s.add(PartnerMembership(user_id=outsider.id, bar_id=bar_id, role='entry', display_name='Outsider'))
        s.commit()
        token = _make_token(outsider.id, bar_id, 'entry', 'Outsider')
    finally:
        s.close()

    client = TestClient(app)
    res = client.get(f'/partner/portal/bar/events/{event_id}/dashboard', headers={'Authorization': f'Bearer {token}'})

    assert res.status_code == 403


def test_dashboard_kpis_are_computed_from_orders():
    bar_id, event_id, token = _seed_partner(role='bartender')
    _seed_orders(event_id, bar_id)
    client = TestClient(app)

    res = client.get(f'/partner/portal/bar/events/{event_id}/dashboard', headers={'Authorization': f'Bearer {token}'})

    assert res.status_code == 200
    payload = res.json()
    assert payload['event']['eventState'] == 'PAUSE'
    assert payload['ordersPending'] == 2
    assert payload['ordersPreparing'] == 1
    assert payload['ordersReady'] == 1
    assert payload['ordersTotalToday'] == 5
    assert payload['revenueTicketsToday'] == 21
    assert payload['avgPrepTime'] is not None


def test_dashboard_returns_empty_alerts_without_inventory_source():
    _, event_id, token = _seed_partner(role='manager')
    client = TestClient(app)

    res = client.get(f'/partner/portal/bar/events/{event_id}/dashboard', headers={'Authorization': f'Bearer {token}'})

    assert res.status_code == 200
    assert res.json()['inventoryAlerts'] == []
