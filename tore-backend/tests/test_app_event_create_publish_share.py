from __future__ import annotations

from datetime import datetime, timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog, EventAppWriteIdempotency, Organization, OrganizationMembership


def _seed_user(client: TestClient, name: str) -> tuple[str, str]:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    payload = res.json()
    return payload['user']['id'], payload['token']


def test_create_event_host_user_ok_and_idempotent_and_audited():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    user_id, token = _seed_user(client, f'app-user-{secrets.token_hex(3)}')
    start = datetime.utcnow().replace(microsecond=0)
    end = start + timedelta(hours=3)
    body = {
        'name': 'In-app User Event',
        'startAt': start.isoformat() + 'Z',
        'endAt': end.isoformat() + 'Z',
        'host_type': 'user',
        'host_id': user_id,
        'visibility': 'PUBLIC',
        'modulesOn': {'entry': True, 'menu': True},
        'rulesFlags': {'charter_enabled': True},
    }
    headers = {'Authorization': f'Bearer {token}', 'Idempotency-Key': 'app-create-user-1'}
    first = client.post('/events', json=body, headers=headers)
    second = client.post('/events', json=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()['event_id'] == second.json()['event_id']
    assert first.json()['publicationStatus'] == 'DRAFT'
    assert first.json()['share']['deeplink'].startswith('tore://')

    s = get_session()
    try:
        idem = s.query(EventAppWriteIdempotency).filter(EventAppWriteIdempotency.actor_user_id == user_id, EventAppWriteIdempotency.action == 'event_create').first()
        assert idem is not None
        audit = s.query(AuditLog).filter(AuditLog.action == 'event.create', AuditLog.actor_user_id == user_id).first()
        assert audit is not None
        assert audit.idempotency_key == 'app-create-user-1'
    finally:
        s.close()


def test_create_event_host_orga_requires_owner_manager():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    owner_id, owner_token = _seed_user(client, f'owner-{secrets.token_hex(3)}')
    member_id, member_token = _seed_user(client, f'member-{secrets.token_hex(3)}')

    s = get_session()
    try:
        org = Organization(name='Orga App', slug=f'orga-app-{secrets.token_hex(3)}', created_by_user_id=owner_id)
        s.add(org)
        s.flush()
        s.add(OrganizationMembership(organization_id=org.id, user_id=owner_id, role='OWNER', created_by_user_id=owner_id))
        s.add(OrganizationMembership(organization_id=org.id, user_id=member_id, role='MEMBER', created_by_user_id=owner_id))
        s.commit()
        org_id = org.id
    finally:
        s.close()

    start = datetime.utcnow().replace(microsecond=0)
    end = start + timedelta(hours=2)
    body = {'name': 'Orga event', 'startAt': start.isoformat() + 'Z', 'endAt': end.isoformat() + 'Z', 'host_type': 'orga', 'host_id': str(org_id)}
    denied = client.post('/events', json=body, headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'app-create-orga-denied'})
    assert denied.status_code == 403

    allowed = client.post('/events', json=body, headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'app-create-orga-owner'})
    assert allowed.status_code == 200


def test_publish_requires_host_perms_and_idempotent_and_share_has_links():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    owner_id, owner_token = _seed_user(client, f'pub-owner-{secrets.token_hex(3)}')
    outsider_id, outsider_token = _seed_user(client, f'pub-outsider-{secrets.token_hex(3)}')

    start = datetime.utcnow().replace(microsecond=0)
    end = start + timedelta(hours=2)
    create = client.post(
        '/events',
        json={'name': 'Share Event', 'startAt': start.isoformat() + 'Z', 'endAt': end.isoformat() + 'Z', 'host_type': 'user', 'host_id': owner_id, 'visibility': 'PUBLIC'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'app-create-publish-1'},
    )
    assert create.status_code == 200
    event_id = create.json()['event_id']

    denied = client.post(f'/events/{event_id}/publish', headers={'Authorization': f'Bearer {outsider_token}', 'Idempotency-Key': 'pub-denied-1'})
    assert denied.status_code == 403

    first = client.post(f'/events/{event_id}/publish', headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'pub-ok-1'})
    second = client.post(f'/events/{event_id}/publish', headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'pub-ok-1'})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()['publicationStatus'] == 'PUBLISHED'
    assert second.json()['publicationStatus'] == 'PUBLISHED'

    share = client.get(f'/events/{event_id}/share')
    assert share.status_code == 200
    data = share.json()
    assert data['deeplink'].startswith('tore://')
    assert data['https_link'].startswith('http')

    s = get_session()
    try:
        audit = s.query(AuditLog).filter(AuditLog.action == 'event.publish', AuditLog.actor_user_id == owner_id).first()
        assert audit is not None
        assert audit.idempotency_key == 'pub-ok-1'
    finally:
        s.close()


def test_event_public_content_patch_is_authorized_and_exposed():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    owner_id, owner_token = _seed_user(client, f'content-owner-{secrets.token_hex(3)}')
    _, outsider_token = _seed_user(client, f'content-outsider-{secrets.token_hex(3)}')
    start = datetime.utcnow().replace(microsecond=0)
    created = client.post(
        '/events',
        json={
            'name': 'Public Content Event',
            'startAt': start.isoformat() + 'Z',
            'endAt': (start + timedelta(hours=3)).isoformat() + 'Z',
            'host_type': 'user',
            'host_id': owner_id,
            'visibility': 'PUBLIC',
        },
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'content-create-1'},
    )
    event_id = created.json()['event_id']

    denied = client.patch(
        f'/events/{event_id}/public-content',
        json={'short_description': 'interdit'},
        headers={'Authorization': f'Bearer {outsider_token}'},
    )
    assert denied.status_code == 403

    updated = client.patch(
        f'/events/{event_id}/public-content',
        json={
            'public_description': 'Le récit complet.',
            'short_description': 'Le résumé public.',
            'banner_url': 'https://cdn.tore.be/public-event.jpg',
            'capacity': 320,
            'access_type': 'OPEN',
            'entry_price_cents': 750,
            'currency': 'eur',
            'address': '4 rue TORÈ',
            'city': 'Liège',
            'lat': 50.64,
            'lng': 5.57,
        },
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    assert updated.status_code == 200
    assert updated.json()['pricing']['currency'] == 'EUR'
    assert updated.json()['capacity'] == 320

    invalid = client.patch(
        f'/events/{event_id}/public-content',
        json={'banner_url': 'file:///secret', 'capacity': 0, 'lat': 100},
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    assert invalid.status_code == 422
