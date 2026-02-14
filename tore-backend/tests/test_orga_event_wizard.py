from __future__ import annotations

from datetime import datetime, timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog, Bar, EventCreateIdempotency, EventQrPackIdempotency, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name='Wizard Bar', city='Liege', partner_code=f'WIZ{suffix}')
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name='Orga', pin_hash='hash')
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role='manager', display_name='Orga'))
        s.commit()
        return bar.id, _make_token(user.id, bar.id, 'manager', 'Orga')
    finally:
        s.close()


def test_create_event_is_idempotent_and_audited():
    _, token = _seed_manager()
    client = TestClient(app)

    start = datetime.utcnow().replace(microsecond=0)
    end = start + timedelta(hours=4)
    body = {
        'name': 'PR9 Event',
        'venue': 'Main Hall',
        'startAt': start.isoformat() + 'Z',
        'endAt': end.isoformat() + 'Z',
        'timezone': 'Europe/Brussels',
        'templateId': 'chapi',
        'modulesOn': {'menu': True, 'entry': True, 'wallet': True, 'wifi': False},
        'rulesFlags': {'charter_enabled': True, 'require_charter_accept': True},
    }
    headers = {'Authorization': f'Bearer {token}', 'Idempotency-Key': 'create-pr9-1'}
    first = client.post('/partner/portal/orga/events', json=body, headers=headers)
    second = client.post('/partner/portal/orga/events', json=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    payload = first.json()
    assert payload['id'] == second.json()['id']
    assert payload['eventState'] == 'LIVE'
    assert payload['modulesOn']['menu'] is True
    assert payload['rulesFlags']['charter_enabled'] is True
    assert payload['lastStateUpdatedAt']
    assert payload['lastUpdatedAt']

    s = get_session()
    try:
        idem = s.query(EventCreateIdempotency).filter(EventCreateIdempotency.idempotency_key == 'create-pr9-1').first()
        assert idem is not None
        audit = s.query(AuditLog).filter(AuditLog.action == 'orga.event.create', AuditLog.entity_id == str(payload['id'])).first()
        assert audit is not None
    finally:
        s.close()


def test_qr_pack_has_required_types_signature_and_expiry():
    _, token = _seed_manager()
    client = TestClient(app)

    start = datetime.utcnow().replace(microsecond=0)
    end = start + timedelta(hours=2)
    create = client.post(
        '/partner/portal/orga/events',
        json={
            'name': 'QR Pack Event',
            'venue': 'Warehouse',
            'startAt': start.isoformat() + 'Z',
            'endAt': end.isoformat() + 'Z',
            'modulesOn': {'menu': True, 'entry': True, 'wallet': True},
            'rulesFlags': {'charter_enabled': False},
        },
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'create-pr9-2'},
    )
    assert create.status_code == 200
    event_id = create.json()['id']

    headers = {'Authorization': f'Bearer {token}', 'Idempotency-Key': 'qr-pack-1'}
    first = client.post(f'/partner/portal/orga/events/{event_id}/qr_pack', headers=headers)
    second = client.post(f'/partner/portal/orga/events/{event_id}/qr_pack', headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    items = first.json()['items']
    assert len(items) == 4
    assert {item['type'] for item in items} == {'JOIN_EVENT', 'ENTRY_STAFF', 'BAR_STAFF', 'MENU'}
    for item in items:
        assert item['expiresAt']
        assert item['signature']
        assert item['payload'].startswith('tore://')
        assert 'sig=' in item['payload']
        assert item['tokenId']

    assert first.json()['items'] == second.json()['items']

    s = get_session()
    try:
        idem = s.query(EventQrPackIdempotency).filter(EventQrPackIdempotency.event_id == event_id, EventQrPackIdempotency.idempotency_key == 'qr-pack-1').first()
        assert idem is not None
        audit = s.query(AuditLog).filter(AuditLog.action == 'orga.qr_pack.generate', AuditLog.event_id == event_id).first()
        assert audit is not None
    finally:
        s.close()
