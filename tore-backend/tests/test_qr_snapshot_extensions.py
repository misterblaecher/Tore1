from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import Bar, Event, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager_with_event():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        bar = Bar(name='Snapshot Bar', city='Liege', partner_code='SNAP001')
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name='Mgr', pin_hash='hash')
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role='manager', display_name='Mgr'))
        event = Event(bar_id=bar.id, name='Event Snapshot')
        s.add(event)
        s.commit()
        token = _make_token(user.id, bar.id, 'manager', 'Mgr')
        return token, event.id
    finally:
        s.close()


def test_qr_manual_code_and_extended_types():
    client = TestClient(app)
    guest = client.post('/auth/guest', json={'display_name': 'qr-ext'})
    token = guest.json()['token']

    manual = client.post('/qr/resolve', json={'raw': 'ABCD1234'}, headers={'Authorization': f'Bearer {token}'})
    assert manual.status_code == 200
    assert manual.json()['type'] == 'manual_code'
    assert manual.json()['reason'] == 'manual_required'

    hunt = client.post('/qr/resolve', json={'raw': 'tore://hunt?event_id=8'}, headers={'Authorization': f'Bearer {token}'})
    assert hunt.status_code == 200
    payload = hunt.json()
    assert payload['type'] == 'hunt'
    assert payload['event_id'] == 8


def test_event_state_snapshot_contract():
    token, event_id = _seed_manager_with_event()
    client = TestClient(app)

    set_state = client.post(
        f'/partner/portal/event/{event_id}/state',
        json={'state': 'PAUSE', 'reason': 'pause ops'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert set_state.status_code == 200
    assert set_state.json()['ok'] is True

    snap = client.get(
        f'/partner/portal/event/{event_id}/state-snapshot',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert snap.status_code == 200
    data = snap.json()
    assert data['event_state'] in {'PAUSE', 'LIVE', 'SCHEDULED', 'CLOSED'}
    assert 'modules' in data
    assert 'orders_enabled' in data['modules']
    assert 'effective_state' in data['modules']['orders_enabled']
