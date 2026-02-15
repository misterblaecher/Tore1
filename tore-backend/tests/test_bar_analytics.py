import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, Order, OrderItem, PartnerMembership, PartnerUser
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
        event = Event(bar_id=bar.id, name='Analytics Event', event_state='LIVE')
        s.add(event)
        s.commit()

        return bar.id, event.id, _make_token(user.id, bar.id, role, 'Bar Ops')
    finally:
        s.close()


def _seed_orders(event_id: int, bar_id: int):
    s = get_session()
    try:
        now = now_utc().replace(second=0, microsecond=0)
        orders = [
            Order(bar_id=bar_id, event_id=event_id, status='NEW', total_tickets=4, created_at=now - timedelta(minutes=44), updated_at=now - timedelta(minutes=44)),
            Order(bar_id=bar_id, event_id=event_id, status='IN_PROGRESS', total_tickets=2, created_at=now - timedelta(minutes=35), updated_at=now - timedelta(minutes=33)),
            Order(bar_id=bar_id, event_id=event_id, status='READY', total_tickets=6, created_at=now - timedelta(minutes=18), updated_at=now - timedelta(minutes=15)),
            Order(bar_id=bar_id, event_id=event_id, status='SERVED', total_tickets=8, created_at=now - timedelta(minutes=16), updated_at=now - timedelta(minutes=12)),
            Order(bar_id=bar_id, event_id=event_id, status='CANCELLED', total_tickets=1, created_at=now - timedelta(minutes=2), updated_at=now - timedelta(minutes=1)),
        ]
        s.add_all(orders)
        s.flush()

        items = [
            OrderItem(order_id=orders[0].id, drink_id=101, name_snapshot='Mojito', qty=2, line_total_cents=1000),
            OrderItem(order_id=orders[1].id, drink_id=101, name_snapshot='Mojito', qty=1, line_total_cents=500),
            OrderItem(order_id=orders[2].id, drink_id=102, name_snapshot='Negroni', qty=3, line_total_cents=1800),
            OrderItem(order_id=orders[3].id, drink_id=101, name_snapshot='Mojito', qty=2, line_total_cents=1000),
        ]
        s.add_all(items)
        s.commit()
    finally:
        s.close()


def test_bar_analytics_totals_and_timeline_are_correct():
    bar_id, event_id, token = _seed_partner(role='manager')
    _seed_orders(event_id, bar_id)
    client = TestClient(app)

    res = client.get(f'/partner/portal/bar/events/{event_id}/analytics', headers={'Authorization': f'Bearer {token}'})

    assert res.status_code == 200
    payload = res.json()
    assert payload['orders']['total'] == 5
    assert payload['orders']['byStatus'] == {
        'pending': 1,
        'preparing': 1,
        'ready': 1,
        'claimed': 1,
        'canceled': 1,
    }
    assert len(payload['orders']['timelineBuckets']) >= 3
    assert sum(bucket['ordersCount'] for bucket in payload['orders']['timelineBuckets']) == 5
    assert payload['peak']['ordersCount'] >= 1


def test_bar_analytics_items_top_are_aggregated():
    bar_id, event_id, token = _seed_partner(role='bartender')
    _seed_orders(event_id, bar_id)
    client = TestClient(app)

    res = client.get(f'/partner/portal/bar/events/{event_id}/analytics', headers={'Authorization': f'Bearer {token}'})

    assert res.status_code == 200
    items = res.json()['itemsTop']
    assert items[0]['drinkId'] == 101
    assert items[0]['qty'] == 5
    assert items[0]['revenueTickets'] == 25


def test_bar_analytics_exports_have_expected_headers():
    bar_id, event_id, token = _seed_partner(role='manager')
    _seed_orders(event_id, bar_id)
    client = TestClient(app)
    headers = {'Authorization': f'Bearer {token}'}

    orders_csv = client.get(f'/partner/portal/bar/events/{event_id}/analytics/export/orders.csv', headers=headers)
    items_csv = client.get(f'/partner/portal/bar/events/{event_id}/analytics/export/items.csv', headers=headers)
    snapshot = client.get(f'/partner/portal/bar/events/{event_id}/analytics/export/snapshot.json', headers=headers)

    assert orders_csv.status_code == 200
    assert 'text/csv' in orders_csv.headers.get('content-type', '')
    assert 'order_id,created_at,status,total_tickets' in orders_csv.text.splitlines()[0]

    assert items_csv.status_code == 200
    assert 'text/csv' in items_csv.headers.get('content-type', '')
    assert 'drink_id,name,qty,revenue_tickets' in items_csv.text.splitlines()[0]

    assert snapshot.status_code == 200
    assert 'application/json' in snapshot.headers.get('content-type', '')
    assert snapshot.json()['orders']['total'] == 5
