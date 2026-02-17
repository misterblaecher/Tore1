from __future__ import annotations

from datetime import datetime, timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog, EventStaff


def _seed_user(client: TestClient, name: str) -> tuple[str, str]:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    payload = res.json()
    return payload['user']['id'], payload['token']


def _create_event(client: TestClient, owner_id: str, owner_token: str, *, visibility: str = 'PRIVATE') -> int:
    start = datetime.utcnow().replace(microsecond=0)
    end = start + timedelta(hours=4)
    created = client.post(
        '/events',
        json={
            'name': f'Staff Invite Event {secrets.token_hex(2)}',
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


def test_create_staff_invite_is_idempotent_for_same_key() -> None:
    Base.metadata.create_all(engine)
    client = TestClient(app)
    owner_id, owner_token = _seed_user(client, f'staff-owner-{secrets.token_hex(2)}')
    event_id = _create_event(client, owner_id, owner_token)

    headers = {'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'staff-idem-create-1'}
    first = client.post(f'/events/{event_id}/staff_invite_code', json={'role': 'ENTRY'}, headers=headers)
    assert first.status_code == 200

    second = client.post(f'/events/{event_id}/staff_invite_code', json={'role': 'ENTRY'}, headers=headers)
    assert second.status_code == 200

    assert second.json()['code'] == first.json()['code']
    assert second.json()['webUrl'] == first.json()['webUrl']


def test_join_by_invite_creates_staff_membership_and_audit() -> None:
    Base.metadata.create_all(engine)
    client = TestClient(app)
    owner_id, owner_token = _seed_user(client, f'staff-owner-{secrets.token_hex(2)}')
    staff_id, staff_token = _seed_user(client, f'staff-user-{secrets.token_hex(2)}')
    event_id = _create_event(client, owner_id, owner_token)

    invite = client.post(
        f'/events/{event_id}/staff_invite_code',
        json={'role': 'BAR', 'expiresInHours': 24},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': f'invite-{secrets.token_hex(2)}'},
    )
    assert invite.status_code == 200
    code = invite.json()['code']

    join_headers = {'Authorization': f'Bearer {staff_token}', 'Idempotency-Key': 'staff-join-idem-1'}
    join_a = client.post(f'/events/{event_id}/staff/join_by_invite', json={'code': code}, headers=join_headers)
    assert join_a.status_code == 200
    join_b = client.post(f'/events/{event_id}/staff/join_by_invite', json={'code': code}, headers=join_headers)
    assert join_b.status_code == 200
    assert join_a.json() == join_b.json()

    session = get_session()
    try:
        membership = session.query(EventStaff).filter(EventStaff.event_id == event_id, EventStaff.user_id == staff_id).all()
        assert len(membership) == 1
        assert (membership[0].role or '').lower() == 'bar'

        audit = session.query(AuditLog).filter(AuditLog.event_id == event_id, AuditLog.action == 'event.staff_invite.join').all()
        assert len(audit) >= 1
    finally:
        session.close()


def test_revoke_requires_reason_and_blocks_join() -> None:
    Base.metadata.create_all(engine)
    client = TestClient(app)
    owner_id, owner_token = _seed_user(client, f'staff-owner-{secrets.token_hex(2)}')
    staff_id, staff_token = _seed_user(client, f'staff-user-{secrets.token_hex(2)}')
    event_id = _create_event(client, owner_id, owner_token)

    invite = client.post(
        f'/events/{event_id}/staff_invite_code',
        json={'role': 'HELPER'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': f'invite-{secrets.token_hex(2)}'},
    )
    assert invite.status_code == 200
    code = invite.json()['code']

    missing_reason = client.post(
        f'/events/{event_id}/staff_invites/{code}/revoke',
        json={},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': f'revoke-missing-{secrets.token_hex(2)}'},
    )
    assert missing_reason.status_code == 422

    revoked = client.post(
        f'/events/{event_id}/staff_invites/{code}/revoke',
        json={'reason': 'Rotation complete'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': f'revoke-{secrets.token_hex(2)}'},
    )
    assert revoked.status_code == 200

    join = client.post(
        f'/events/{event_id}/staff/join_by_invite',
        json={'code': code},
        headers={'Authorization': f'Bearer {staff_token}', 'Idempotency-Key': f'join-after-revoke-{secrets.token_hex(2)}'},
    )
    assert join.status_code == 409


def test_open_resolves_staff_invite_and_private_share_pack_requires_auth() -> None:
    Base.metadata.create_all(engine)
    client = TestClient(app)
    owner_id, owner_token = _seed_user(client, f'staff-owner-{secrets.token_hex(2)}')
    event_id = _create_event(client, owner_id, owner_token, visibility='PRIVATE')

    invite = client.post(
        f'/events/{event_id}/staff_invite_code',
        json={'role': 'ENTRY'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': f'invite-{secrets.token_hex(2)}'},
    )
    assert invite.status_code == 200
    code = invite.json()['code']

    resolved = client.get(f'/open?type=staff_invite&code={code}')
    assert resolved.status_code == 200
    payload = resolved.json()
    assert payload['target']['event_id'] == event_id
    assert payload['target']['role'] == 'ENTRY'

    no_auth_pack = client.get(f'/events/{event_id}/share_pack')
    assert no_auth_pack.status_code == 401


def test_rotate_staff_invite_is_idempotent_and_revokes_previous() -> None:
    Base.metadata.create_all(engine)
    client = TestClient(app)
    owner_id, owner_token = _seed_user(client, f'staff-owner-{secrets.token_hex(2)}')
    event_id = _create_event(client, owner_id, owner_token)

    created = client.post(
        f'/events/{event_id}/staff_invite_code',
        json={'role': 'ENTRY'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': f'invite-{secrets.token_hex(2)}'},
    )
    assert created.status_code == 200
    old_code = created.json()['code']

    headers = {'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'rotate-entry-idem-1'}
    first = client.post(
        f'/events/{event_id}/staff_invites/rotate',
        json={'role': 'ENTRY', 'expiresInMinutes': 90},
        headers=headers,
    )
    assert first.status_code == 200

    second = client.post(
        f'/events/{event_id}/staff_invites/rotate',
        json={'role': 'ENTRY', 'expiresInMinutes': 90},
        headers=headers,
    )
    assert second.status_code == 200
    assert first.json()['code'] == second.json()['code']

    current = client.get(f'/events/{event_id}/staff_invites/current', headers={'Authorization': f'Bearer {owner_token}'})
    assert current.status_code == 200
    roles = current.json()['roles']
    assert roles['ENTRY']['code'] == first.json()['code']
    assert roles['ENTRY']['status'] == 'ACTIVE'

    session = get_session()
    try:
        old = session.query(AuditLog).filter(AuditLog.event_id == event_id, AuditLog.action == 'staff_invite_rotated').all()
        assert len(old) >= 1
    finally:
        session.close()

    join_old = client.post(
        f'/events/{event_id}/staff/join_by_invite',
        json={'code': old_code},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': f'join-rot-old-{secrets.token_hex(2)}'},
    )
    assert join_old.status_code == 409


def test_current_staff_invites_returns_one_active_per_role_and_audit() -> None:
    Base.metadata.create_all(engine)
    client = TestClient(app)
    owner_id, owner_token = _seed_user(client, f'staff-owner-{secrets.token_hex(2)}')
    event_id = _create_event(client, owner_id, owner_token)

    for role in ('ENTRY', 'BAR'):
        res = client.post(
            f'/events/{event_id}/staff_invites/rotate',
            json={'role': role},
            headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': f'rot-{role}-{secrets.token_hex(2)}'},
        )
        assert res.status_code == 200

    current = client.get(f'/events/{event_id}/staff_invites/current', headers={'Authorization': f'Bearer {owner_token}'})
    assert current.status_code == 200
    payload = current.json()
    assert set(payload['roles'].keys()) == {'ENTRY', 'BAR', 'MANAGER', 'HELPER'}
    assert payload['roles']['ENTRY']['status'] == 'ACTIVE'
    assert payload['roles']['BAR']['status'] == 'ACTIVE'
    assert payload['roles']['MANAGER'] is None

    session = get_session()
    try:
        audits = session.query(AuditLog).filter(AuditLog.event_id == event_id, AuditLog.action == 'event.staff_invites.current.read').all()
        assert len(audits) >= 1
    finally:
        session.close()
