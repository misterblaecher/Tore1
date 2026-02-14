from fastapi.testclient import TestClient

import secrets

from db import Base, engine, get_session
from main import app
from models import Bar, Event, EventModuleConfig, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager_with_event():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name='Snapshot Bar', city='Liege', partner_code=f'SNAP{suffix}')
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name='Mgr', pin_hash='hash')
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role='manager', display_name='Mgr'))
        event = Event(bar_id=bar.id, name='Event Snapshot')
        s.add(event)
        s.flush()
        s.add(EventModuleConfig(event_id=event.id, orders_enabled=True, entry_enabled=True, wifi_enabled=True, checkins_enabled=True, safety_enabled=True, hunt_enabled=True))
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
    manager_token, event_id = _seed_manager_with_event()
    client = TestClient(app)

    set_state = client.post(
        f'/partner/portal/event/{event_id}/state',
        json={'state': 'PAUSE', 'reason': 'pause ops'},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert set_state.status_code == 200
    assert set_state.json()['ok'] is True

    snap = client.get(
        f'/partner/portal/event/{event_id}/state-snapshot',
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert snap.status_code == 200
    data = snap.json()
    assert data['event_state'] in {'PAUSE', 'LIVE', 'SCHEDULED', 'CLOSED'}
    assert 'modules' in data
    assert 'orders_enabled' in data['modules']
    assert 'effective_state' in data['modules']['orders_enabled']


def test_qr_resolve_runtime_gate_respects_module_and_pause_state():
    manager_token, event_id = _seed_manager_with_event()
    client = TestClient(app)
    guest = client.post('/auth/guest', json={'display_name': 'qr-runtime'})
    token = guest.json()['token']

    s = get_session()
    try:
        cfg = s.query(EventModuleConfig).filter(EventModuleConfig.event_id == event_id).first()
        assert cfg is not None
        cfg.wifi_enabled = False
        s.add(cfg)
        s.commit()
    finally:
        s.close()

    wifi = client.post('/qr/resolve', json={'raw': f'tore://wifi?event_id={event_id}'}, headers={'Authorization': f'Bearer {token}'})
    assert wifi.status_code == 200
    assert wifi.json()['valid'] is False
    assert wifi.json()['reason'] == 'module_off'

    pause = client.post(
        f'/partner/portal/event/{event_id}/state',
        json={'state': 'PAUSE', 'reason': 'hold'},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert pause.status_code == 200

    entry = client.post('/qr/resolve', json={'raw': f'tore://entry?event_id={event_id}'}, headers={'Authorization': f'Bearer {token}'})
    assert entry.status_code == 200
    assert entry.json()['valid'] is False
    assert entry.json()['reason'] == 'event_paused'


def test_qr_resolve_contract_mvp_types():
    manager_token, event_id = _seed_manager_with_event()
    client = TestClient(app)
    guest = client.post('/auth/guest', json={'display_name': 'qr-mvp'})
    token = guest.json()['token']

    menu = client.post('/qr/resolve', json={'raw': f'tore://menu?event_id={event_id}'}, headers={'Authorization': f'Bearer {token}'})
    assert menu.status_code == 200
    assert menu.json()['type'] == 'menu'
    assert menu.json()['event_id'] == event_id

    join_event = client.post('/qr/resolve', json={'raw': f'tore://join_event?event_id={event_id}'}, headers={'Authorization': f'Bearer {token}'})
    assert join_event.status_code == 200
    assert join_event.json()['type'] == 'join_event'
    assert join_event.json()['valid'] is True

    entry_staff = client.post('/qr/resolve', json={'raw': f'tore://entry_staff?event_id={event_id}'}, headers={'Authorization': f'Bearer {token}'})
    assert entry_staff.status_code == 200
    assert entry_staff.json()['type'] == 'entry_staff'
    assert entry_staff.json()['reason'] == 'forbidden'

    bar_staff = client.post('/qr/resolve', json={'raw': f'tore://bar_staff?event_id={event_id}'}, headers={'Authorization': f'Bearer {token}'})
    assert bar_staff.status_code == 200
    assert bar_staff.json()['type'] == 'bar_staff'
    assert bar_staff.json()['reason'] == 'forbidden'

    unknown = client.post('/qr/resolve', json={'raw': 'tore://nope?event_id=1'}, headers={'Authorization': f'Bearer {token}'})
    assert unknown.status_code == 200
    assert unknown.json()['valid'] is False
    assert unknown.json()['type'] == 'unknown'
