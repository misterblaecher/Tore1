from datetime import timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, EventModuleConfig, EventRuntimeState, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed(role: str = 'manager'):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        bar = Bar(name='Orga', city='Liege', partner_code=f'ORGA-{role}-{secrets.token_hex(4)}')
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name='Ops', pin_hash='hash')
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role=role, display_name='Ops'))
        event = Event(bar_id=bar.id, name='Soiree', starts_at=now_utc() - timedelta(hours=1), ends_at=now_utc() + timedelta(hours=3))
        s.add(event)
        s.flush()
        s.add(EventModuleConfig(event_id=event.id, entry_enabled=True, checkins_enabled=True, wifi_enabled=True, safety_enabled=True, orders_enabled=True))
        s.add(EventRuntimeState(event_id=event.id, state='LIVE'))
        s.commit()
        return event.id, _make_token(user.id, bar.id, role, 'Ops')
    finally:
        s.close()


def test_orga_active_event_allows_staff_readonly_context():
    event_id, token = _seed(role='bartender')
    client = TestClient(app)

    resp = client.get('/partner/portal/orga/events/active', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['event']['id'] == event_id
    assert data['event_state'] == 'LIVE'
    assert data['modulesOn']['entry_enabled'] is True


def test_runtime_state_change_requires_reason_and_supports_frozen():
    event_id, token = _seed(role='manager')
    client = TestClient(app)

    missing = client.post(f'/partner/portal/event/{event_id}/state', json={'state': 'FROZEN'}, headers={'Authorization': f'Bearer {token}'})
    assert missing.status_code == 400
    assert missing.json()['detail']['reason'] == 'reason_required'

    ok = client.post(
        f'/partner/portal/event/{event_id}/state',
        json={'state': 'FROZEN', 'reason': 'incident ops'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert ok.status_code == 200
    assert ok.json()['state'] == 'FROZEN'


def test_degraded_blocks_critical_entry_write():
    event_id, token = _seed(role='manager')
    client = TestClient(app)

    set_state = client.post(
        f'/partner/portal/event/{event_id}/state',
        json={'state': 'DEGRADED', 'reason': 'network unstable'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert set_state.status_code == 200

    denied = client.post(
        '/entry/scan',
        json={'event_id': event_id, 'token': 'abc', 'scan_id': 'scan-degraded-1'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert denied.status_code == 200
    assert denied.json()['reason'] == 'event_degraded_critical'
