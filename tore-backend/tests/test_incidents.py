from __future__ import annotations

from datetime import datetime, timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import Bar, Event, EventModuleConfig, EventStaffAssignment, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager_event_and_staff():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name='Incidents Bar', city='Liege', partner_code=f'INC{suffix}')
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name='Manager', pin_hash='hash')
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role='manager', display_name='Manager'))
        event = Event(
            bar_id=bar.id,
            name='Incidents Event',
            starts_at=datetime.utcnow().replace(microsecond=0) - timedelta(hours=1),
            ends_at=datetime.utcnow().replace(microsecond=0) + timedelta(hours=4),
        )
        s.add(event)
        s.flush()
        s.add(EventModuleConfig(event_id=event.id, safety_enabled=True, entry_enabled=True))
        assignment = EventStaffAssignment(event_id=event.id, role='ENTRY', label='Gate A', created_by_user_id=user.id)
        s.add(assignment)
        s.commit()
        return _make_token(user.id, bar.id, 'manager', 'Manager'), event.id, assignment.id
    finally:
        s.close()


def _create_incident(client: TestClient, token: str, event_id: int, key: str = 'incident-key-1'):
    return client.post(
        f'/partner/portal/orga/events/{event_id}/incidents',
        json={'description': 'Test incident', 'severity': 'warn', 'location': 'Gate A'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': key},
    )


def test_create_incident_idempotent():
    token, event_id, _ = _seed_manager_event_and_staff()
    client = TestClient(app)

    first = _create_incident(client, token, event_id, 'idem-create-1')
    second = _create_incident(client, token, event_id, 'idem-create-1')

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()['incident']['id'] == second.json()['incident']['id']


def test_escalate_requires_reason():
    token, event_id, _ = _seed_manager_event_and_staff()
    client = TestClient(app)

    created = _create_incident(client, token, event_id, 'idem-create-2')
    incident_id = created.json()['incident']['id']

    missing_reason = client.post(
        f'/partner/portal/orga/incidents/{incident_id}/escalate',
        json={'severity': 'critical'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'idem-escalate-1'},
    )
    assert missing_reason.status_code == 422
    assert missing_reason.json()['detail']['reason'] == 'missing_reason'


def test_assign_logs_action():
    token, event_id, assignment_id = _seed_manager_event_and_staff()
    client = TestClient(app)

    created = _create_incident(client, token, event_id, 'idem-create-3')
    incident_id = created.json()['incident']['id']

    assigned = client.post(
        f'/partner/portal/orga/incidents/{incident_id}/assign',
        json={'assignmentId': assignment_id, 'reason': 'Dispatch'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'idem-assign-1'},
    )
    assert assigned.status_code == 200

    logs = client.get(
        f'/partner/portal/orga/incidents/{incident_id}/logs',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert logs.status_code == 200
    assert any(item['actionType'] == 'assigned' for item in logs.json()['items'])


def test_export_returns_incidents_and_logs():
    token, event_id, assignment_id = _seed_manager_event_and_staff()
    client = TestClient(app)

    created = _create_incident(client, token, event_id, 'idem-create-4')
    incident_id = created.json()['incident']['id']
    client.post(
        f'/partner/portal/orga/incidents/{incident_id}/assign',
        json={'assignmentId': assignment_id, 'reason': 'Dispatch'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'idem-assign-2'},
    )

    exported = client.get(
        f'/partner/portal/orga/events/{event_id}/incidents/export',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert exported.status_code == 200
    payload = exported.json()
    assert len(payload['incidents']) >= 1
    assert len(payload['logs']) >= 1
