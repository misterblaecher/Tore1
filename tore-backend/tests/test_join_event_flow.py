from datetime import timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, EventJoin


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
