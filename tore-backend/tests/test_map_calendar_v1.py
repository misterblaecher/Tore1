from __future__ import annotations

from datetime import datetime, timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog, Bar, Event, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_event(*, map_on: bool):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name='Map Bar', city='Liege', partner_code=f'MAP{suffix}')
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name='Manager Map', pin_hash='hash')
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role='manager', display_name='Manager Map'))
        event = Event(
            bar_id=bar.id,
            name='Guindaille publique',
            venue='Place du Marché, Liège',
            starts_at=datetime.utcnow().replace(microsecond=0) - timedelta(hours=2),
            ends_at=datetime.utcnow().replace(microsecond=0) + timedelta(hours=4),
            modules_on={'map': map_on},
        )
        s.add(event)
        s.commit()
        return _make_token(user.id, bar.id, 'manager', 'Manager Map'), event.id
    finally:
        s.close()


def test_event_map_module_off_strict_404():
    _, event_id = _seed_event(map_on=False)
    client = TestClient(app)

    res = client.get(f'/events/{event_id}/map')
    assert res.status_code == 404
    assert res.json()['detail']['reason'] == 'MODULE_OFF'


def test_calendar_events_shape_and_status():
    _, event_id = _seed_event(map_on=True)
    client = TestClient(app)

    now = datetime.utcnow().replace(microsecond=0)
    res = client.get('/calendar/events', params={'from': (now - timedelta(days=1)).isoformat(), 'to': (now + timedelta(days=7)).isoformat(), 'scope': 'public'})
    assert res.status_code == 200
    payload = res.json()
    assert isinstance(payload.get('items'), list)
    item = next((x for x in payload['items'] if x['id'] == event_id), None)
    assert item is not None
    assert {'id', 'name', 'startAt', 'endAt', 'venue', 'address', 'barId', 'barName', 'status'}.issubset(item.keys())


def test_ics_endpoint_contains_vevent_fields():
    _, event_id = _seed_event(map_on=True)
    client = TestClient(app)

    res = client.get(f'/calendar/events/{event_id}.ics')
    assert res.status_code == 200
    body = res.text
    assert 'BEGIN:VEVENT' in body
    assert 'DTSTART:' in body
    assert 'DTEND:' in body
    assert 'LOCATION:' in body
    assert 'SUMMARY:' in body


def test_map_settings_put_requires_idempotency_and_writes_audit_log():
    manager_token, event_id = _seed_event(map_on=True)
    client = TestClient(app)

    missing = client.put(
        f'/partner/portal/orga/events/{event_id}/map/settings',
        json={'enabled': True, 'address': 'Rue Cathédrale, Liège'},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert missing.status_code == 400
    assert missing.json()['detail']['reason'] == 'missing_idempotency'

    ok = client.put(
        f'/partner/portal/orga/events/{event_id}/map/settings',
        json={
            'enabled': True,
            'venueName': 'Carré',
            'address': 'Rue Pont d\'Avroy, Liège',
            'lat': 50.637,
            'lng': 5.571,
            'tecLink': 'https://www.letec.be/',
            'wazeLink': 'https://waze.com/ul?ll=50.637,5.571&navigate=yes',
            'navettes': {'enabled': True, 'address': 'Guillemins', 'lastReturnTime': '04:30', 'notes': 'Dernier départ 4h30'},
        },
        headers={'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'map-settings-1'},
    )
    assert ok.status_code == 200
    assert ok.json()['enabled'] is True
    assert ok.json()['navettes']['enabled'] is True

    s = get_session()
    try:
        audit = s.query(AuditLog).filter(AuditLog.event_id == event_id, AuditLog.action == 'orga.map.settings.update').first()
        assert audit is not None
    finally:
        s.close()
