from __future__ import annotations

from datetime import datetime, timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog, Bar, Event, EventModuleConfig, EventQrToken, EventStaffAssignment
from models import PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager_with_event():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name='Staff Bar', city='Liege', partner_code=f'STF{suffix}')
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name='Manager', pin_hash='hash')
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role='manager', display_name='Manager'))
        event = Event(
            bar_id=bar.id,
            name='Staff Event',
            starts_at=datetime.utcnow().replace(microsecond=0) - timedelta(hours=1),
            ends_at=datetime.utcnow().replace(microsecond=0) + timedelta(hours=4),
        )
        s.add(event)
        s.flush()
        s.add(EventModuleConfig(event_id=event.id, entry_enabled=True, orders_enabled=True))
        s.commit()
        return _make_token(user.id, bar.id, 'manager', 'Manager'), event.id
    finally:
        s.close()


def test_create_staff_assignment_requires_idempotency():
    token, event_id = _seed_manager_with_event()
    client = TestClient(app)

    missing = client.post(
        f'/partner/portal/orga/events/{event_id}/staff',
        json={'role': 'ENTRY'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert missing.status_code == 400
    assert missing.json()['detail']['reason'] == 'missing_idempotency'

    headers = {'Authorization': f'Bearer {token}', 'Idempotency-Key': 'staff-idem-1'}
    first = client.post(
        f'/partner/portal/orga/events/{event_id}/staff',
        json={'role': 'ENTRY', 'label': 'Gate A'},
        headers=headers,
    )
    second = client.post(
        f'/partner/portal/orga/events/{event_id}/staff',
        json={'role': 'ENTRY', 'label': 'Gate A'},
        headers=headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()['assignment']['id'] == second.json()['assignment']['id']


def test_revoke_requires_reason_and_blocks_validation():
    token, event_id = _seed_manager_with_event()
    client = TestClient(app)
    guest = client.post('/auth/guest', json={'display_name': 'qr-staff'}).json()['token']

    created = client.post(
        f'/partner/portal/orga/events/{event_id}/staff',
        json={'role': 'ENTRY', 'label': 'Gate B'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'staff-idem-2'},
    )
    assert created.status_code == 200
    assignment_id = created.json()['assignment']['id']
    raw = created.json()['qr']['raw']

    missing_reason = client.post(
        f'/partner/portal/orga/staff/{assignment_id}/revoke',
        json={},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert missing_reason.status_code == 400

    revoked = client.post(
        f'/partner/portal/orga/staff/{assignment_id}/revoke',
        json={'reason': 'lost badge'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert revoked.status_code == 200

    resolved = client.post('/qr/resolve', json={'raw': raw}, headers={'Authorization': f'Bearer {guest}'})
    assert resolved.status_code == 200
    assert resolved.json()['valid'] is False
    assert resolved.json()['reason'] == 'revoked'


def test_staff_list_shows_status_and_resolve_revoked():
    token, event_id = _seed_manager_with_event()
    client = TestClient(app)
    guest = client.post('/auth/guest', json={'display_name': 'qr-list'}).json()['token']

    created = client.post(
        f'/partner/portal/orga/events/{event_id}/staff',
        json={'role': 'BAR', 'label': 'Bar 1'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'staff-idem-3'},
    )
    assert created.status_code == 200
    assignment_id = created.json()['assignment']['id']

    listed = client.get(
        f'/partner/portal/orga/events/{event_id}/staff',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert listed.status_code == 200
    first = listed.json()['items'][0]
    assert first['status'] == 'ACTIVE'
    assert first['role'] == 'BAR'

    revoke = client.post(
        f'/partner/portal/orga/staff/{assignment_id}/revoke',
        json={'reason': 'rotation complete'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert revoke.status_code == 200

    listed_after = client.get(
        f'/partner/portal/orga/events/{event_id}/staff',
        headers={'Authorization': f'Bearer {token}'},
    )
    revoked_item = next(item for item in listed_after.json()['items'] if item['id'] == assignment_id)
    assert revoked_item['status'] == 'REVOKED'

    resolved = client.post('/qr/resolve', json={'raw': created.json()['qr']['raw']}, headers={'Authorization': f'Bearer {guest}'})
    assert resolved.status_code == 200
    assert resolved.json()['reason'] == 'revoked'

    s = get_session()
    try:
        assignment = s.get(EventStaffAssignment, assignment_id)
        token_row = s.query(EventQrToken).filter(EventQrToken.assignment_id == assignment_id).first()
        assert assignment is not None and assignment.revoked_at is not None
        assert token_row is not None and token_row.revoked_at is not None
        audit = s.query(AuditLog).filter(AuditLog.action == 'orga.staff.revoke', AuditLog.entity_id == str(assignment_id)).first()
        assert audit is not None
    finally:
        s.close()
