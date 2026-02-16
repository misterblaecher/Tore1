from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AuditLog, OrganizationInviteCode, OrganizationMembership


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _guest(name: str) -> str:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    return res.json()['token']


def test_create_orga_idempotent_and_owner_membership():
    token = _guest('orga-owner')
    headers = {'Authorization': f'Bearer {token}', 'Idempotency-Key': 'orga-create-1'}
    body = {'name': 'Tore Club', 'city': 'Liège', 'org_type': 'Student'}

    first = client.post('/orgas', json=body, headers=headers)
    second = client.post('/orgas', json=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()['role'] == 'OWNER'

    org_id = first.json()['orga']['id']
    with get_session() as s:
        rows = s.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org_id).all()
        assert len(rows) == 1
        assert rows[0].role == 'OWNER'


def test_explorer_filtering_basic():
    token = _guest('creator')
    client.post('/orgas', json={'name': 'Alpha Liège', 'city': 'Liège', 'org_type': 'Student'}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'orga-exp-1'})
    client.post('/orgas', json={'name': 'Beta Namur', 'city': 'Namur', 'org_type': 'Association'}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'orga-exp-2'})

    by_city = client.get('/orgas?city=liège')
    assert by_city.status_code == 200
    assert len(by_city.json()['items']) == 1

    by_query = client.get('/orgas?query=beta')
    assert by_query.status_code == 200
    assert len(by_query.json()['items']) == 1


def test_join_by_code_invalid_or_expired():
    owner_token = _guest('owner-1')
    member_token = _guest('member-1')
    created = client.post('/orgas', json={'name': 'Invite Club'}, headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'orga-join-1'})
    org_id = created.json()['orga']['id']

    invalid = client.post('/orgas/join_by_code', json={'code': 'NOPE1111'}, headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'orga-join-invalid'})
    assert invalid.status_code == 404

    with get_session() as s:
        row = OrganizationInviteCode(
            organization_id=org_id,
            code='EXPIRED1',
            role='MEMBER',
            max_uses=5,
            used_count=0,
            expires_at=now_utc() - timedelta(minutes=1),
            created_by_user_id='missing',
            created_at=now_utc(),
        )
        me = client.get('/auth/me', headers={'Authorization': f'Bearer {owner_token}'}).json()
        row.created_by_user_id = me['id']
        s.add(row)
        s.commit()

    expired = client.post('/orgas/join_by_code', json={'code': 'EXPIRED1'}, headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'orga-join-expired'})
    assert expired.status_code == 400


def test_permissions_invite_owner_manager_only():
    owner_token = _guest('owner-2')
    member_token = _guest('member-2')
    created = client.post('/orgas', json={'name': 'Perm Club'}, headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'orga-invite-1'})
    org_id = created.json()['orga']['id']

    owner_invite = client.get(f'/orgas/{org_id}/invite', headers={'Authorization': f'Bearer {owner_token}'})
    assert owner_invite.status_code == 200

    denied = client.get(f'/orgas/{org_id}/invite', headers={'Authorization': f'Bearer {member_token}'})
    assert denied.status_code == 403


def test_audit_log_presence_for_writes():
    owner_token = _guest('owner-audit')
    member_token = _guest('member-audit')

    created = client.post('/orgas', json={'name': 'Audit Club'}, headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'orga-audit-1'})
    org_id = created.json()['orga']['id']

    invite = client.get(f'/orgas/{org_id}/invite', headers={'Authorization': f'Bearer {owner_token}'})
    code = invite.json()['code']
    join = client.post('/orgas/join_by_code', json={'code': code}, headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'orga-audit-join-1'})
    assert join.status_code == 200

    with get_session() as s:
        create_log = s.query(AuditLog).filter(AuditLog.action == 'organization.create').first()
        join_log = s.query(AuditLog).filter(AuditLog.action == 'organization.join_by_code').first()
        assert create_log is not None
        assert create_log.actor_user_id is not None
        assert create_log.idempotency_key == 'orga-audit-1'
        assert join_log is not None
        assert join_log.actor_user_id is not None
        assert join_log.idempotency_key == 'orga-audit-join-1'
