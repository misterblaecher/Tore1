from datetime import timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AuditLog, Bar, Event, EventJoin, EventRuntimeState


def _seed_event(*, charter_enabled: bool = False, state: str | None = None) -> tuple[int, str]:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        bar = Bar(name='Join Bar', city='Liege', partner_code=f'JOIN{now_utc().timestamp()}')
        s.add(bar)
        s.flush()
        event = Event(
            bar_id=bar.id,
            name='Join Event',
            starts_at=now_utc() - timedelta(hours=1),
            ends_at=now_utc() + timedelta(hours=2),
            event_code=f'J{secrets.token_hex(3).upper()}',
            charter_enabled=charter_enabled,
            charter_version='v1' if charter_enabled else None,
            charter_text='Respecte la charte de Liège.' if charter_enabled else None,
        )
        s.add(event)
        s.flush()
        if state is not None:
            s.add(EventRuntimeState(event_id=event.id, state=state))
        s.commit()
        return event.id, event.event_code or 'JOIN66'
    finally:
        s.close()


def _guest_token(client: TestClient, name: str = 'join-user') -> str:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    return res.json()['token']


def test_join_by_code_returns_event_payload():
    event_id, code = _seed_event()
    client = TestClient(app)
    token = _guest_token(client)

    res = client.post('/events/join_by_code', json={'code': code}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'join-by-code-1'})

    assert res.status_code == 200
    data = res.json()
    assert data['event']['id'] == event_id
    assert data['event']['event_code'] == code
    assert 'modulesOn' in data
    assert 'eventState' in data
    assert data['flags']['charterEnabled'] is False


def test_join_event_is_idempotent():
    event_id, _ = _seed_event()
    client = TestClient(app)
    token = _guest_token(client, 'join-idem')
    headers = {'Authorization': f'Bearer {token}', 'Idempotency-Key': 'join-idempotent'}

    first = client.post(f'/events/{event_id}/join', json={}, headers=headers)
    second = client.post(f'/events/{event_id}/join', json={}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200

    s = get_session()
    try:
        rows = s.query(EventJoin).filter(EventJoin.event_id == event_id).all()
        assert len(rows) == 1
    finally:
        s.close()


def test_charter_is_returned_when_enabled():
    event_id, _ = _seed_event(charter_enabled=True)
    client = TestClient(app)
    token = _guest_token(client, 'join-charter')

    res = client.get(f'/events/{event_id}/charter', headers={'Authorization': f'Bearer {token}'})

    assert res.status_code == 200
    data = res.json()
    assert data['enabled'] is True
    assert data['version'] == 'v1'
    assert 'Liège' in data['text']


def test_public_event_endpoint_requires_public_and_published():
    event_id, _ = _seed_event()
    client = TestClient(app)

    missing = client.get(f'/events/{event_id}/public')
    assert missing.status_code == 404

    s = get_session()
    try:
        event = s.get(Event, event_id)
        assert event is not None
        event.visibility = 'PUBLIC'
        event.publication_status = 'PUBLISHED'
        s.add(event)
        s.commit()
    finally:
        s.close()

    ok = client.get(f'/events/{event_id}/public')
    assert ok.status_code == 200


def test_public_event_endpoint_safe_payload_has_no_staff_qr_or_invites():
    event_id, _ = _seed_event()
    client = TestClient(app)

    s = get_session()
    try:
        event = s.get(Event, event_id)
        assert event is not None
        event.visibility = 'PUBLIC'
        event.publication_status = 'PUBLISHED'
        s.add(event)
        s.commit()
    finally:
        s.close()

    res = client.get(f'/events/{event_id}/public')
    assert res.status_code == 200
    payload = res.json()
    assert 'staff' not in payload
    assert 'qr' not in payload
    assert 'invites' not in payload
    assert payload['flags']['canJoin'] is True


def test_join_public_is_idempotent_has_audit_and_blocks_closed_or_frozen():
    event_id, _ = _seed_event()
    client = TestClient(app)
    token = _guest_token(client, 'join-public-idem')
    headers = {'Authorization': f'Bearer {token}', 'Idempotency-Key': 'join-public-idem'}

    s = get_session()
    try:
        event = s.get(Event, event_id)
        assert event is not None
        event.visibility = 'PUBLIC'
        event.publication_status = 'PUBLISHED'
        s.add(event)
        s.commit()
    finally:
        s.close()

    first = client.post(f'/events/{event_id}/join_public', json={}, headers=headers)
    second = client.post(f'/events/{event_id}/join_public', json={}, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200

    s = get_session()
    try:
        rows = s.query(EventJoin).filter(EventJoin.event_id == event_id).all()
        assert len(rows) == 1
        audit = s.query(AuditLog).filter(AuditLog.action == 'event.join', AuditLog.event_id == event_id).first()
        assert audit is not None
    finally:
        s.close()

    s = get_session()
    try:
        runtime = s.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).first()
        if runtime is None:
            runtime = EventRuntimeState(event_id=event_id, state='CLOSED')
        else:
            runtime.state = 'CLOSED'
        s.add(runtime)
        s.commit()
    finally:
        s.close()

    blocked = client.post(f'/events/{event_id}/join_public', json={}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'join-public-blocked'})
    assert blocked.status_code == 403
