from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, MenuCategory, MenuItem, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_partner():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        bar = Bar(name=f"Ticker Bar {now_utc().timestamp()}", city="Liege", partner_code=f"TK{int(now_utc().timestamp())}")
        s.add(bar)
        s.flush()
        event = Event(bar_id=bar.id, name="Ticker Event")
        s.add(event)
        s.flush()
        manager = PartnerUser(display_name="Mgr", pin_hash="hash")
        s.add(manager)
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role="manager", display_name="Mgr"))
        cat = MenuCategory(bar_id=bar.id, name="Biere", sort_order=1)
        s.add(cat)
        s.flush()
        item = MenuItem(bar_id=bar.id, category_id=cat.id, name="IPA", price_cents=500)
        s.add(item)
        s.commit()
        return bar.id, event.id, item.id, _make_token(manager.id, bar.id, "manager", "Mgr")
    finally:
        s.close()


def _guest(client: TestClient, name: str = "u") -> str:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    return res.json()['token']


def test_ticker_feed_pagination_and_order_status_and_module_toggle_and_stream_connectable():
    bar_id, event_id, item_id, manager_token = _seed_partner()
    client = TestClient(app)
    user_token = _guest(client, "alice")

    create = client.post('/orders', json={
        'bar_id': bar_id,
        'event_id': event_id,
        'items': [{'item_id': item_id, 'qty': 1}],
        'idempotency_key': 'ticker-order-1',
    }, headers={'Authorization': f'Bearer {user_token}'})
    assert create.status_code == 200
    order_id = create.json()['id']

    updated = client.patch(
        f'/orders/{order_id}/status',
        json={'status': 'accepted'},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert updated.status_code == 200

    modules = client.post(
        f'/partner/portal/event/{event_id}/modules',
        json={'checkins_enabled': True, 'wifi_enabled': True},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert modules.status_code == 200

    user_id = client.get('/auth/me', headers={'Authorization': f'Bearer {user_token}'}).json()['id']

    topup = client.post(
        '/partner/portal/wallet/topup',
        json={
            'event_id': event_id,
            'target_user_id': user_id,
            'amount_tickets': 3,
            'idempotency_key': 'ticker-topup-1',
        },
        headers={'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'ticker-topup-1'},
    )
    assert topup.status_code == 200


    feed = client.get(f'/events/{event_id}/ticker?limit=2', headers={'Authorization': f'Bearer {user_token}'})
    assert feed.status_code == 200
    data = feed.json()
    assert len(data['items']) == 2
    assert data['next_cursor'] is not None

    page2 = client.get(
        f"/events/{event_id}/ticker?limit=2&cursor={data['next_cursor']}",
        headers={'Authorization': f'Bearer {user_token}'},
    )
    assert page2.status_code == 200
    seen = {item['type'] for item in (data['items'] + page2.json()['items'])}
    assert 'order_status' in seen
    assert 'module_toggle' in seen

    with client.stream('GET', f'/events/{event_id}/ticker/stream?once=true', headers={'Authorization': f'Bearer {user_token}'}) as response:
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/event-stream')
