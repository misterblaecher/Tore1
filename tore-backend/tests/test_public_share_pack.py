from __future__ import annotations

from datetime import datetime, timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog


def _seed_user(client: TestClient, name: str) -> tuple[str, str]:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    payload = res.json()
    return payload['user']['id'], payload['token']


def _create_event(client: TestClient, owner_id: str, owner_token: str, *, visibility: str = 'PUBLIC') -> int:
    start = datetime.utcnow().replace(microsecond=0)
    end = start + timedelta(hours=4)
    created = client.post(
        '/events',
        json={
            'name': f'Public Share Event {secrets.token_hex(2)}',
            'startAt': start.isoformat() + 'Z',
            'endAt': end.isoformat() + 'Z',
            'host_type': 'user',
            'host_id': owner_id,
            'visibility': visibility,
        },
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': f'create-event-{secrets.token_hex(2)}'},
    )
    assert created.status_code == 200
    return int(created.json()['event_id'])


def _publish_event(client: TestClient, event_id: int, token: str) -> None:
    published = client.post(
        f'/events/{event_id}/publish',
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': f'publish-{secrets.token_hex(2)}'},
    )
    assert published.status_code == 200


def test_public_event_share_pack_returns_only_public_fields() -> None:
    Base.metadata.create_all(engine)
    client = TestClient(app)

    owner_id, owner_token = _seed_user(client, f'public-share-owner-{secrets.token_hex(2)}')
    event_id = _create_event(client, owner_id, owner_token, visibility='PUBLIC')
    _publish_event(client, event_id, owner_token)

    res = client.get(f'/share/event/{event_id}')
    assert res.status_code == 200
    payload = res.json()

    assert set(payload.keys()) == {'event', 'metadata', 'links', 'openUrl', 'printPackUrl'}
    assert set(payload['links'].keys()).issubset({'publicShare', 'joinPublic', 'open'})
    assert payload['event']['visibility'] == 'PUBLIC'
    assert payload['event']['publicationStatus'] == 'PUBLISHED'
    assert payload['openUrl'].endswith(f'/open?type=event&id={event_id}')
    assert payload['printPackUrl'].endswith(f'/share/event/{event_id}/print')



def test_private_event_public_share_pack_is_not_available() -> None:
    Base.metadata.create_all(engine)
    client = TestClient(app)

    owner_id, owner_token = _seed_user(client, f'private-share-owner-{secrets.token_hex(2)}')
    event_id = _create_event(client, owner_id, owner_token, visibility='PRIVATE')
    _publish_event(client, event_id, owner_token)

    res = client.get(f'/share/event/{event_id}')
    assert res.status_code == 404



def test_public_share_pack_has_no_secrets_and_audit_log() -> None:
    Base.metadata.create_all(engine)
    client = TestClient(app)

    owner_id, owner_token = _seed_user(client, f'public-share-owner-{secrets.token_hex(2)}')
    event_id = _create_event(client, owner_id, owner_token, visibility='PUBLIC')
    _publish_event(client, event_id, owner_token)

    res = client.get(f'/share/event/{event_id}')
    assert res.status_code == 200
    raw = res.text.lower()
    assert 'password' not in raw
    assert 'manage' not in raw
    assert 'staffinvites' not in raw

    session = get_session()
    try:
        logs = session.query(AuditLog).filter(
            AuditLog.event_id == event_id,
            AuditLog.action == 'event.public_share_pack.read',
        ).all()
        assert len(logs) >= 1
        assert any((log.payload_json or {}).get('scope') == 'public_share_pack' for log in logs)
    finally:
        session.close()
