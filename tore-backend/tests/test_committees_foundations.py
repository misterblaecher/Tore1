from __future__ import annotations

from datetime import timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import (
    AuditLog,
    Committee,
    CommitteeInviteCode,
    CommitteeMembership,
    CommitteeYear,
)


def _auth_guest(client: TestClient, name: str) -> tuple[str, str]:
    Base.metadata.create_all(engine)
    token = client.post('/auth/guest', json={'display_name': name}).json()['token']
    me = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'}).json()
    return token, me['id']


def _seed_committee(owner_user_id: str) -> tuple[int, str, str]:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(3)
        committee = Committee(name=f'GDL {suffix}', slug=f'gdl-{suffix}', description_public='Comité GDL')
        s.add(committee)
        s.flush()
        s.add(CommitteeYear(committee_id=committee.id, year_label='2025-2026', is_active=True))
        s.add(CommitteeMembership(committee_id=committee.id, user_id=owner_user_id, role='OWNER', is_active=True))
        s.add(
            CommitteeInviteCode(
                committee_id=committee.id,
                code=f'JOIN{suffix.upper()}',
                expires_at=now_utc() + timedelta(days=2),
                created_by=owner_user_id,
                uses_left=10,
            )
        )
        s.commit()
        return committee.id, committee.slug, f'JOIN{suffix.upper()}'
    finally:
        s.close()


def test_committees_list_get_and_years_ok():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'owner-list')
    committee_id, slug, join_code = _seed_committee(owner_id)

    listed = client.get('/committees')
    assert listed.status_code == 200
    assert any(item['id'] == committee_id for item in listed.json())

    got = client.get(f'/committees/{committee_id}')
    assert got.status_code == 200
    assert got.json()['slug'] == slug
    assert got.json()['activeYear'] == '2025-2026'

    years = client.get(f'/committees/{committee_id}/years')
    assert years.status_code == 200
    assert years.json()[0]['yearLabel'] == '2025-2026'

    me = client.get(f'/committees/{committee_id}/me', headers={'Authorization': f'Bearer {owner_token}'})
    assert me.status_code == 200
    assert me.json()['membership']['role'] == 'OWNER'


def test_join_by_code_is_idempotent_and_invalid_rejected():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'owner-join-seed')
    _ = owner_token
    committee_id, _slug, join_code = _seed_committee(owner_id)

    user_token, user_id = _auth_guest(client, 'join-member')
    headers = {'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'committee-join-1'}
    first = client.post(f'/committees/{committee_id}/join_by_code', json={'code': join_code}, headers=headers)
    second = client.post(f'/committees/{committee_id}/join_by_code', json={'code': join_code}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()['membership']['userId'] == user_id
    assert first.json() == second.json()

    invalid = client.post(
        f'/committees/{committee_id}/join_by_code',
        json={'code': 'WRONG'},
        headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'committee-join-2'},
    )
    assert invalid.status_code == 404
    assert invalid.json()['detail']['reason'] == 'invalid_code'


def test_admin_endpoints_require_permissions():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'owner-admin')
    committee_id, _, join_code = _seed_committee(owner_id)

    member_token, _member_id = _auth_guest(client, 'member-admin')
    join = client.post(
        f'/committees/{committee_id}/join_by_code',
        json={'code': join_code},
        headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'join-perm-1'},
    )
    assert join.status_code == 200

    denied_members = client.get(f'/committees/{committee_id}/members', headers={'Authorization': f'Bearer {member_token}'})
    assert denied_members.status_code == 403

    denied_code = client.post(
        f'/committees/{committee_id}/invite_codes',
        json={'usesLeft': 3},
        headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'invite-member-1'},
    )
    assert denied_code.status_code == 403

    allowed = client.get(f'/committees/{committee_id}/members', headers={'Authorization': f'Bearer {owner_token}'})
    assert allowed.status_code == 200


def test_role_change_is_audited():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'owner-audit')
    committee_id, _, join_code = _seed_committee(owner_id)

    user_token, user_id = _auth_guest(client, 'mod-target')
    joined = client.post(
        f'/committees/{committee_id}/join_by_code',
        json={'code': join_code},
        headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'join-audit-1'},
    )
    assert joined.status_code == 200

    role = client.post(
        f'/committees/{committee_id}/members/{user_id}/role',
        json={'role': 'MOD', 'reason': 'needs moderation'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'role-audit-1'},
    )
    assert role.status_code == 200

    s = get_session()
    try:
        audit = (
            s.query(AuditLog)
            .filter(AuditLog.action == 'committee.member.role_set', AuditLog.entity_id == f'{committee_id}:{user_id}')
            .first()
        )
        assert audit is not None
        assert audit.payload_json['role'] == 'MOD'
    finally:
        s.close()
