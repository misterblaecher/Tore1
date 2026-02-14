from fastapi.testclient import TestClient

import secrets

from db import Base, engine, get_session
from main import app
from models import Bar, Event, EventModuleConfig, MenuCategory, MenuItem, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed(role: str = 'manager'):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f'Ops {suffix}', city='Paris', partner_code=f'OPS{suffix}')
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name='Staff', pin_hash='hash')
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role=role, display_name='Staff'))
        event = Event(bar_id=bar.id, name='Ops Event')
        s.add(event)
        s.flush()
        s.add(EventModuleConfig(event_id=event.id, orders_enabled=True, entry_enabled=True))
        cat = MenuCategory(bar_id=bar.id, name='Drinks', sort_order=1)
        s.add(cat)
        s.flush()
        item = MenuItem(bar_id=bar.id, category_id=cat.id, name='Beer', price_cents=500)
        s.add(item)
        s.commit()
        return bar.id, event.id, item.id, user.id, _make_token(user.id, bar.id, role, 'Staff')
    finally:
        s.close()


def test_staff_revoke_blocks_entry_and_order_status():
    bar_id, event_id, item_id, _, token = _seed('bartender')

    client = TestClient(app)
    # use bartender token create order
    created = client.post('/orders', json={
        'bar_id': bar_id,
        'event_id': event_id,
        'items': [{'item_id': item_id, 'qty': 1}],
        'device_id': 'dev-a',
        'idempotency_key': 'idem-revoke',
    }, headers={'Authorization': f'Bearer {token}'})
    assert created.status_code == 200

    # self-revoke token
    revoke = client.post('/partner/auth/revoke-token', headers={'Authorization': f'Bearer {token}'})
    assert revoke.status_code == 200

    blocked_order = client.patch(f"/orders/{created.json()['id']}/status", json={'status': 'accepted'}, headers={'Authorization': f'Bearer {token}'})
    assert blocked_order.status_code == 403
    assert blocked_order.json()['detail']['reason'] == 'revoked'

    blocked_scan = client.post('/entry/scan', json={'event_id': event_id, 'token': 'x', 'scan_id': 'scan-rv-1'}, headers={'Authorization': f'Bearer {token}'})
    assert blocked_scan.status_code == 403
    assert blocked_scan.json()['detail']['reason'] == 'revoked'


def test_rate_limit_and_ops_snapshot_and_spam_idempotence():
    bar_id, event_id, item_id, _, token = _seed('manager')
    client = TestClient(app)

    # orders create rate limit
    last = None
    for i in range(30):
        last = client.post('/orders', json={
            'bar_id': bar_id,
            'event_id': event_id,
            'items': [{'item_id': item_id, 'qty': 1}],
            'device_id': 'dev-rate',
            'idempotency_key': f'idem-rate-{i}',
        })
    assert last is not None
    assert last.status_code == 429
    assert last.json()['detail']['reason'] == 'rate_limited'

    # idempotence under spam-like rapid calls
    ids = set()
    for _ in range(12):
        res = client.post('/orders', json={
            'bar_id': bar_id,
            'event_id': event_id,
            'items': [{'item_id': item_id, 'qty': 1}],
            'device_id': 'dev-spam',
            'idempotency_key': 'idem-spam-1',
        }, headers={'Idempotency-Key': 'idem-spam-1'})
        assert res.status_code == 200
        ids.add(res.json()['id'])
    assert len(ids) == 1

    snap = client.get(f'/events/{event_id}/ops/snapshot', headers={'Authorization': f'Bearer {token}'})
    assert snap.status_code == 200
    data = snap.json()
    assert 'runtime_state' in data
    assert 'modules' in data
    assert 'counts' in data
    assert 'orders_pending' in data['counts']

    metrics = client.get('/ops/metrics-lite', headers={'Authorization': f'Bearer {token}'})
    assert metrics.status_code == 200
    assert 'requests_total' in metrics.json()
