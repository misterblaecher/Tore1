from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import Bar, Drink, Event, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager_event():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = datetime.utcnow().strftime('%H%M%S%f')[-8:]
        bar = Bar(name=f'Gate Bar {suffix}', city='Liege', partner_code=f'GT{suffix}')
        s.add(bar)
        s.flush()
        manager = PartnerUser(display_name='Manager', pin_hash='hash')
        s.add(manager)
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role='manager', display_name='Manager'))
        event = Event(
            bar_id=bar.id,
            name='Gate Event',
            starts_at=datetime.utcnow() - timedelta(hours=1),
            ends_at=datetime.utcnow() + timedelta(hours=5),
        )
        s.add(event)
        drink = Drink(name='IPA test', type='beer')
        s.add(drink)
        s.commit()
        token = _make_token(manager.id, bar.id, 'manager', 'Manager')
        return token, bar.id, event.id, drink.id
    finally:
        s.close()


def _set_state(client: TestClient, token: str, event_id: int, state: str):
    res = client.post(
        f'/partner/portal/event/{event_id}/state',
        json={'state': state, 'reason': f'test-{state.lower()}'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert res.status_code == 200


def test_event_state_pause_blocks_entry_wallet_checkin_and_wifi_public():
    manager_token, bar_id, event_id, drink_id = _seed_manager_event()
    client = TestClient(app)

    # Enable modules while live
    enable = client.post(
        f'/partner/portal/event/{event_id}/modules',
        json={'entry_enabled': True, 'checkins_enabled': True, 'wifi_enabled': True},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert enable.status_code == 200

    wifi = client.post(
        '/partner/portal/wifi/set',
        json={'bar_id': bar_id, 'event_id': event_id, 'ssid': 'TOR3', 'password': 'secret123', 'note': 'ops'},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert wifi.status_code == 200

    _set_state(client, manager_token, event_id, 'PAUSE')

    issue = client.post(
        '/entry/tokens/issue',
        json={'event_id': event_id, 'count': 1, 'expires_in_minutes': 30},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert issue.status_code == 423
    assert issue.json()['detail']['code'] == 'EVENT_PAUSED'

    guest = client.post('/auth/guest', json={'display_name': 'wallet-user'})
    user_id = guest.json()['user']['id']
    topup = client.post(
        '/partner/portal/wallet/admin/topup',
        json={'event_id': event_id, 'user_id': user_id, 'amount_tickets': 5, 'reason': 'test', 'idempotency_key': 'idem-1'},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert topup.status_code == 423
    assert topup.json()['detail']['code'] == 'EVENT_PAUSED'

    guest_token = guest.json()['token']
    checkin = client.post(
        '/drinks/checkin',
        json={'event_id': event_id, 'bar_id': bar_id, 'drink_id': drink_id, 'rating': 4},
        headers={'Authorization': f'Bearer {guest_token}'},
    )
    assert checkin.status_code == 423
    assert checkin.json()['detail']['code'] == 'EVENT_PAUSED'

    wifi_public = client.get(f'/public/wifi?bar_id={bar_id}&event_id={event_id}')
    assert wifi_public.status_code == 423
    assert wifi_public.json()['detail']['code'] == 'EVENT_PAUSED'


def test_menu_only_blocks_battles_writes():
    manager_token, bar_id, event_id, _ = _seed_manager_event()
    client = TestClient(app)

    enable = client.post(
        f'/partner/portal/event/{event_id}/modules',
        json={'battles_enabled': True, 'polymarket_enabled': True},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert enable.status_code == 200

    battle = client.post(
        '/battles/create',
        json={'event_id': event_id, 'bar_id': bar_id, 'mode': 'DUEL'},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert battle.status_code == 200
    battle_id = battle.json()['id']

    guest = client.post('/auth/guest', json={'display_name': 'battle-user'})
    user_token = guest.json()['token']

    _set_state(client, manager_token, event_id, 'MENU_ONLY')

    join = client.post(
        f'/battles/{battle_id}/join',
        json={'scan_id': 'join-1'},
        headers={'Authorization': f'Bearer {user_token}'},
    )
    assert join.status_code == 423
    assert join.json()['detail']['code'] == 'EVENT_MENU_ONLY'



def test_checkins_logs_pagination_is_stable_and_audit_written_for_wifi_set():
    manager_token, bar_id, event_id, drink_id = _seed_manager_event()
    client = TestClient(app)

    enable = client.post(
        f'/partner/portal/event/{event_id}/modules',
        json={'checkins_enabled': True, 'wifi_enabled': True, 'safety_enabled': True},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert enable.status_code == 200

    guest = client.post('/auth/guest', json={'display_name': 'pager-user'})
    guest_token = guest.json()['token']
    for i in range(3):
        row = client.post(
            '/drinks/checkin',
            json={'event_id': event_id, 'bar_id': bar_id, 'drink_id': drink_id, 'rating': 4, 'comment': f'c{i}'},
            headers={'Authorization': f'Bearer {guest_token}'},
        )
        assert row.status_code == 200

    page1 = client.get(
        f'/partner/portal/checkins/logs?event_id={event_id}&limit=2',
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert page1.status_code == 200
    data1 = page1.json()
    assert len(data1['items']) == 2
    assert data1['next_cursor']

    page2 = client.get(
        f'/partner/portal/checkins/logs?event_id={event_id}&limit=2&cursor={data1["next_cursor"]}',
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert page2.status_code == 200
    data2 = page2.json()
    assert len(data2['items']) >= 1

    ids = [x['id'] for x in data1['items']] + [x['id'] for x in data2['items']]
    assert ids == sorted(ids, reverse=True)

    wifi = client.post(
        '/partner/portal/wifi/set',
        json={'bar_id': bar_id, 'event_id': event_id, 'ssid': 'TOR3-2', 'password': 'secret123', 'note': 'ops'},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert wifi.status_code == 200

    audit = client.get(
        f'/partner/portal/audit/logs?event_id={event_id}&type=wifi.set&limit=5',
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert audit.status_code == 200
    assert len(audit.json()['items']) >= 1
