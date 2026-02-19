from __future__ import annotations

from datetime import datetime, timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import Organization, OrganizationMembership


def _seed_user(client: TestClient, name: str) -> tuple[str, str]:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    payload = res.json()
    return payload['user']['id'], payload['token']


def test_event_public_share_and_open_resolve_return_weburl_and_deeplink():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    user_id, token = _seed_user(client, f'open-event-{secrets.token_hex(2)}')

    start = datetime.utcnow().replace(microsecond=0)
    end = start + timedelta(hours=2)
    created = client.post(
        '/events',
        json={
            'name': 'Open Event',
            'startAt': start.isoformat() + 'Z',
            'endAt': end.isoformat() + 'Z',
            'host_type': 'user',
            'host_id': user_id,
            'visibility': 'PUBLIC',
        },
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': f'event-open-{secrets.token_hex(2)}'},
    )
    assert created.status_code == 200
    event_id = created.json()['event_id']

    share = client.get(f'/events/{event_id}/share')
    assert share.status_code == 200
    payload = share.json()
    assert payload['webUrl'].endswith(f'/open?type=event&id={event_id}')
    assert payload['deeplink'] == f'tore://open?type=event&id={event_id}'

    resolved = client.get(f'/open?type=event&id={event_id}')
    assert resolved.status_code == 200
    open_payload = resolved.json()
    assert open_payload['deeplink'] == payload['deeplink']
    assert open_payload['type'] == 'event'
    assert open_payload['target']['event_id'] == event_id
    assert 'event_code' not in open_payload
    assert 'token' not in str(open_payload).lower()


def test_orga_share_public_and_private_protection():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    owner_id, owner_token = _seed_user(client, f'open-orga-owner-{secrets.token_hex(2)}')
    outsider_id, outsider_token = _seed_user(client, f'open-orga-outsider-{secrets.token_hex(2)}')

    session = get_session()
    try:
        public_org = Organization(name='Open Public Orga', slug=f'open-public-{secrets.token_hex(3)}', visibility='PUBLIC', created_by_user_id=owner_id)
        private_org = Organization(name='Open Private Orga', slug=f'open-private-{secrets.token_hex(3)}', visibility='PRIVATE', created_by_user_id=owner_id)
        session.add(public_org)
        session.add(private_org)
        session.flush()
        session.add(OrganizationMembership(organization_id=public_org.id, user_id=owner_id, role='OWNER', created_by_user_id=owner_id))
        session.add(OrganizationMembership(organization_id=private_org.id, user_id=owner_id, role='OWNER', created_by_user_id=owner_id))
        session.commit()
        public_id = public_org.id
        private_id = private_org.id
    finally:
        session.close()

    public_share = client.get(f'/orgas/{public_id}/share')
    assert public_share.status_code == 200
    public_payload = public_share.json()
    assert public_payload['webUrl'].endswith(f'/open?type=orga&id={public_id}')
    assert public_payload['deeplink'] == f'tore://open?type=orga&id={public_id}'

    private_share_anon = client.get(f'/orgas/{private_id}/share')
    assert private_share_anon.status_code in {403, 404}

    private_share_outsider = client.get(f'/orgas/{private_id}/share', headers={'Authorization': f'Bearer {outsider_token}'})
    assert private_share_outsider.status_code in {403, 404}

    private_resolve = client.get(f'/open?type=orga&id={private_id}')
    assert private_resolve.status_code in {403, 404}

    private_resolve_owner = client.get(f'/open?type=orga&id={private_id}', headers={'Authorization': f'Bearer {owner_token}'})
    assert private_resolve_owner.status_code == 200


def test_join_code_preview_private_safe_and_public_open():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    user_id, token = _seed_user(client, f'open-join-{secrets.token_hex(2)}')

    start = datetime.utcnow().replace(microsecond=0)
    end = start + timedelta(hours=3)
    private_event = client.post(
        '/events',
        json={
            'name': 'Ultra Secret Event',
            'startAt': start.isoformat() + 'Z',
            'endAt': end.isoformat() + 'Z',
            'host_type': 'user',
            'host_id': user_id,
            'visibility': 'PRIVATE',
        },
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': f'event-private-{secrets.token_hex(2)}'},
    )
    assert private_event.status_code == 200

    private_code = private_event.json()['event_code']
    private_preview = client.get(f'/events/join_code/preview?code={private_code}')
    assert private_preview.status_code == 200
    private_payload = private_preview.json()
    assert private_payload['exists'] is True
    assert private_payload['requiresAuth'] is True
    assert private_payload['titleHint'] == 'Event privé TORÈ'
    assert private_payload.get('public') in (None, {})

    private_open = client.get(f'/open?type=join&code={private_code}')
    assert private_open.status_code == 200
    private_open_payload = private_open.json()
    assert private_open_payload['deeplink'] == f'tore://open?type=join&code={private_code}'
    assert private_open_payload['webFallback'].endswith(f'/open?type=join&code={private_code}')
    assert private_open_payload['title'] == 'Rejoindre un event privé'

    public_event = client.post(
        '/events',
        json={
            'name': 'Visible Event',
            'startAt': start.isoformat() + 'Z',
            'endAt': end.isoformat() + 'Z',
            'host_type': 'user',
            'host_id': user_id,
            'visibility': 'PUBLIC',
        },
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': f'event-public-{secrets.token_hex(2)}'},
    )
    assert public_event.status_code == 200
    public_id = public_event.json()['event_id']
    public_code = public_event.json()['event_code']

    published = client.post(f'/events/{public_id}/publish', headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': f'publish-{secrets.token_hex(2)}'})
    assert published.status_code == 200

    public_preview = client.get(f'/events/join_code/preview?code={public_code}')
    assert public_preview.status_code == 200
    public_payload = public_preview.json()
    assert public_payload['exists'] is True
    assert public_payload['requiresAuth'] is False
    assert public_payload['public']['id'] == public_id
