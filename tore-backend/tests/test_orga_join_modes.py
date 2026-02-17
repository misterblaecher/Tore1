from fastapi.testclient import TestClient

from db import Base, engine
from main import app

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _guest(name: str) -> tuple[str, str]:
    token = client.post('/auth/guest', json={'display_name': name}).json()['token']
    user_id = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'}).json()['id']
    return token, user_id


def _create_orga(owner_token: str, join_mode: str) -> int:
    res = client.post('/orgas', json={'name': f'Orga-{join_mode}', 'join_mode': join_mode}, headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': f'create-{join_mode}'})
    assert res.status_code == 200
    return res.json()['orga']['id']


def test_join_modes_map_to_membership_state():
    owner_token, _ = _guest('owner')
    user_token, _ = _guest('user')

    org_follow = _create_orga(owner_token, 'FOLLOW_ONLY')
    org_open = _create_orga(owner_token, 'OPEN_MEMBERSHIP')
    org_request = _create_orga(owner_token, 'REQUEST_TO_JOIN')

    follow = client.post(f'/orgas/{org_follow}/join', headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'join-follow'})
    assert follow.status_code == 200
    assert follow.json()['membership']['role'] == 'FOLLOWER'
    assert follow.json()['membership']['status'] == 'ACTIVE'

    opened = client.post(f'/orgas/{org_open}/join', headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'join-open'})
    assert opened.status_code == 200
    assert opened.json()['membership']['role'] == 'MEMBER'
    assert opened.json()['membership']['status'] == 'ACTIVE'

    requested = client.post(f'/orgas/{org_request}/join', headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'join-request'})
    assert requested.status_code == 200
    assert requested.json()['membership']['role'] == 'MEMBER'
    assert requested.json()['membership']['status'] == 'PENDING'


def test_approve_reject_and_role_guards():
    owner_token, _ = _guest('owner2')
    manager_token, manager_id = _guest('manager2')
    member_token, member_id = _guest('member2')

    org_id = _create_orga(owner_token, 'REQUEST_TO_JOIN')

    client.post(f'/orgas/{org_id}/members', json={'user_id': manager_id, 'role': 'MANAGER'}, headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'upsert-manager'})

    client.post(f'/orgas/{org_id}/join', headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'join-pending'})

    denied = client.post(f'/orgas/{org_id}/memberships/{member_id}/approve', json={}, headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'approve-denied'})
    assert denied.status_code == 403

    approved = client.post(f'/orgas/{org_id}/memberships/{member_id}/approve', json={}, headers={'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'approve-ok'})
    assert approved.status_code == 200
    assert approved.json()['membership']['status'] == 'ACTIVE'

    rejected = client.post(f'/orgas/{org_id}/memberships/{member_id}/reject', json={'reason': 'policy'}, headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'reject-ok'})
    assert rejected.status_code == 200
    assert rejected.json()['membership']['status'] == 'REJECTED'


def test_idempotency_join_and_approve_stable():
    owner_token, _ = _guest('owner3')
    member_token, member_id = _guest('member3')
    org_id = _create_orga(owner_token, 'REQUEST_TO_JOIN')

    first = client.post(f'/orgas/{org_id}/join', headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'idem-join'})
    second = client.post(f'/orgas/{org_id}/join', headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'idem-join'})
    assert first.status_code == 200
    assert first.json() == second.json()

    app1 = client.post(f'/orgas/{org_id}/memberships/{member_id}/approve', json={}, headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'idem-approve'})
    app2 = client.post(f'/orgas/{org_id}/memberships/{member_id}/approve', json={}, headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'idem-approve'})
    assert app1.status_code == 200
    assert app1.json() == app2.json()
