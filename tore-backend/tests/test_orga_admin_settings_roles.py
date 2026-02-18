from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog, OrganizationMembership


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _guest(name: str) -> tuple[str, str]:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    token = res.json()['token']
    me = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200
    return token, me.json()['id']


def _create_orga(owner_token: str) -> int:
    res = client.post('/orgas', json={'name': 'Club P10', 'city': 'Liege'}, headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'create-1'})
    assert res.status_code == 200
    return res.json()['orga']['id']


def _join_orga(token: str, org_id: int, key: str) -> None:
    res = client.post(f'/orgas/{org_id}/join', headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': key})
    assert res.status_code == 200


def test_owner_can_update_settings_idempotent():
    owner_token, _ = _guest('owner-settings')
    org_id = _create_orga(owner_token)
    headers = {'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'orga-update-1'}
    body = {'name': 'Club P10+', 'join_mode': 'REQUEST_TO_JOIN', 'visibility': 'PRIVATE', 'instagram': '@club'}

    first = client.put(f'/orgas/{org_id}', json=body, headers=headers)
    second = client.put(f'/orgas/{org_id}', json=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()['name'] == 'Club P10+'
    assert first.json()['join_mode'] == 'REQUEST_TO_JOIN'


def test_manager_can_update_settings():
    owner_token, _ = _guest('owner-manager-settings')
    manager_token, manager_id = _guest('manager-settings')
    org_id = _create_orga(owner_token)
    _join_orga(manager_token, org_id, 'join-manager-settings')
    promote = client.post(
        f'/orgas/{org_id}/memberships/{manager_id}/set_role',
        json={'role': 'MANAGER', 'reason': 'team'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'set-manager'},
    )
    assert promote.status_code == 200

    updated = client.put(
        f'/orgas/{org_id}',
        json={'city': 'Namur', 'join_mode': 'FOLLOW_ONLY'},
        headers={'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'manager-update-1'},
    )
    assert updated.status_code == 200
    assert updated.json()['city'] == 'Namur'
    assert updated.json()['join_mode'] == 'FOLLOW_ONLY'


def test_manager_cannot_set_owner():
    owner_token, _ = _guest('owner-role')
    manager_token, manager_id = _guest('manager-role')
    member_token, member_id = _guest('member-role')
    org_id = _create_orga(owner_token)

    _join_orga(manager_token, org_id, 'join-manager-role')
    _join_orga(member_token, org_id, 'join-member-role')

    _join_orga(manager_token, org_id, 'join-manager-remove')
    _join_orga(member_token, org_id, 'join-member-remove')

    assert client.post(
        f'/orgas/{org_id}/memberships/{manager_id}/set_role',
        json={'role': 'MANAGER', 'reason': 'ops'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'owner-set-manager'},
    ).status_code == 200

    denied = client.post(
        f'/orgas/{org_id}/memberships/{member_id}/set_role',
        json={'role': 'OWNER', 'reason': 'not allowed'},
        headers={'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'manager-owner-denied'},
    )
    assert denied.status_code == 403

    me = client.get(f'/orgas/{org_id}/memberships/me', headers={'Authorization': f'Bearer {member_token}'})
    assert me.status_code == 200


def test_cannot_remove_owner_and_remove_sets_left_with_audit_and_idempotency():
    owner_token, owner_id = _guest('owner-remove')
    manager_token, manager_id = _guest('manager-remove')
    member_token, member_id = _guest('member-remove')
    org_id = _create_orga(owner_token)
    _join_orga(manager_token, org_id, 'join-manager-remove')
    _join_orga(member_token, org_id, 'join-member-remove')

    assert client.post(
        f'/orgas/{org_id}/memberships/{manager_id}/set_role',
        json={'role': 'MANAGER', 'reason': 'ops'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'set-manager-remove'},
    ).status_code == 200

    denied = client.post(
        f'/orgas/{org_id}/memberships/{owner_id}/remove',
        json={'reason': 'cannot'},
        headers={'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'remove-owner-denied'},
    )
    assert denied.status_code == 400

    headers = {'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'remove-member-1'}
    first = client.post(f'/orgas/{org_id}/memberships/{member_id}/remove', json={'reason': 'cleanup'}, headers=headers)
    second = client.post(f'/orgas/{org_id}/memberships/{member_id}/remove', json={'reason': 'cleanup'}, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()['membership']['status'] == 'LEFT'

    with get_session() as s:
        membership = s.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org_id, OrganizationMembership.user_id == member_id).first()
        assert membership is not None
        assert membership.status == 'LEFT'
        assert s.query(AuditLog).filter(AuditLog.action == 'orga_member_removed').first() is not None
        assert s.query(AuditLog).filter(AuditLog.action == 'orga_member_role_changed').first() is not None
        assert s.query(AuditLog).filter(AuditLog.action == 'orga_updated').first() is None

    assert client.get(f'/orgas/{org_id}/memberships/me', headers={'Authorization': f'Bearer {member_token}'}).status_code == 200
