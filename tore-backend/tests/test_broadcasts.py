from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AppUser, Bar, Event, EventStaff, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager_event(*, broadcast_on: bool = True):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = datetime.utcnow().strftime('%H%M%S%f')[-8:]
        bar = Bar(name=f'Broadcast Bar {suffix}', city='Liege', partner_code=f'BC{suffix}')
        s.add(bar)
        s.flush()
        manager = PartnerUser(display_name='Manager', pin_hash='hash')
        s.add(manager)
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role='manager', display_name='Manager'))
        event = Event(
            bar_id=bar.id,
            name='Broadcast Event',
            starts_at=datetime.utcnow() - timedelta(hours=1),
            ends_at=datetime.utcnow() + timedelta(hours=5),
            modules_on={'broadcast': broadcast_on},
        )
        s.add(event)
        s.commit()
        token = _make_token(manager.id, bar.id, 'manager', 'Manager')
        return token, event.id
    finally:
        s.close()


def test_create_broadcast_idempotent_and_fetchable():
    token, event_id = _seed_manager_event()
    client = TestClient(app)

    first = client.post(
        f'/partner/portal/orga/events/{event_id}/broadcast',
        json={'message': 'Test ORGA', 'level': 'warn'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'idem-broadcast-1'},
    )
    assert first.status_code == 200
    first_id = first.json()['id']

    second = client.post(
        f'/partner/portal/orga/events/{event_id}/broadcast',
        json={'message': 'Test ORGA', 'level': 'warn'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'idem-broadcast-1'},
    )
    assert second.status_code == 200
    assert second.json()['id'] == first_id

    listing = client.get(f'/events/{event_id}/broadcasts')
    assert listing.status_code == 200
    assert any(item['id'] == first_id for item in listing.json()['items'])


def test_broadcast_rate_limit_returns_429():
    token, event_id = _seed_manager_event()
    client = TestClient(app)

    for i in range(3):
        ok = client.post(
            f'/partner/portal/orga/events/{event_id}/broadcast',
            json={'message': f'Msg {i}', 'level': 'info'},
            headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': f'idem-{i}'},
        )
        if i == 0:
            assert ok.status_code == 200
        else:
            assert ok.status_code == 429
            assert ok.json()['detail']['reason'].startswith('broadcast_')


def test_module_off_returns_empty_feed():
    token, event_id = _seed_manager_event(broadcast_on=False)
    client = TestClient(app)

    create = client.post(
        f'/partner/portal/orga/events/{event_id}/broadcast',
        json={'message': 'nope', 'level': 'info'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'idem-off'},
    )
    assert create.status_code == 409
    assert create.json()['detail']['reason'] == 'module_off'

    listing = client.get(f'/events/{event_id}/broadcasts')
    assert listing.status_code == 200
    assert listing.json()['items'] == []


def test_mobile_broadcast_requires_event_capability_and_is_idempotent():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    guest = client.post('/auth/guest', json={'display_name': 'Mobile manager'})
    assert guest.status_code == 200
    token = guest.json()['token']
    user_id = guest.json()['user']['id']
    s = get_session()
    try:
        user = s.get(AppUser, user_id)
        user.is_guest = False
        bar = Bar(name='Mobile Broadcast Bar', city='Liege', partner_code=f'MB{user_id[-6:]}')
        s.add(bar)
        s.flush()
        s.add(PartnerUser(app_user_id=user_id, display_name='Mobile manager', pin_hash='hash'))
        event = Event(
            bar_id=bar.id, name='Mobile Broadcast Event',
            starts_at=datetime.utcnow() - timedelta(hours=1),
            ends_at=datetime.utcnow() + timedelta(hours=5),
            host_type='user', host_id=user_id, modules_on={'broadcast': True},
        )
        s.add(event)
        s.commit()
        event_id = event.id
    finally:
        s.close()

    headers = {'Authorization': f'Bearer {token}', 'Idempotency-Key': 'mobile-broadcast-1'}
    first = client.post(f'/ops/events/{event_id}/broadcast', json={'message': 'Ouverture', 'level': 'info'}, headers=headers)
    assert first.status_code == 200, first.text
    second = client.post(f'/ops/events/{event_id}/broadcast', json={'message': 'Ouverture', 'level': 'info'}, headers=headers)
    assert second.status_code == 200
    assert second.json()['id'] == first.json()['id']
