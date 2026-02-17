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


def _create_orga(owner_token: str, visibility: str = 'PUBLIC') -> int:
    res = client.post(
        '/orgas',
        json={'name': f'Orga-{visibility}', 'visibility': visibility},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': f'create-{visibility}'},
    )
    assert res.status_code == 200
    return res.json()['orga']['id']


def test_create_invite_idempotent_and_list_does_not_leak_raw_code():
    owner_token, _ = _guest('owner-invite')
    org_id = _create_orga(owner_token)
    headers = {'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'create-member-invite'}
    first = client.post(f'/orgas/{org_id}/invites', json={'inviteType': 'MEMBER', 'expiresInHours': 24}, headers=headers)
    second = client.post(f'/orgas/{org_id}/invites', json={'inviteType': 'MEMBER', 'expiresInHours': 24}, headers=headers)

    assert first.status_code == 200
    assert first.json() == second.json()
    assert len(first.json()['code']) >= 8

    listed = client.get(f'/orgas/{org_id}/invites', headers={'Authorization': f'Bearer {owner_token}'})
    assert listed.status_code == 200
    payload = listed.json()['items'][0]
    assert payload['suffix'] == first.json()['suffix']
    assert 'code' not in payload


def test_join_by_invite_applies_role_and_idempotent_when_already_higher_role():
    owner_token, _ = _guest('owner-join')
    user_token, user_id = _guest('staff-user')
    org_id = _create_orga(owner_token)

    create = client.post(
        f'/orgas/{org_id}/invites',
        json={'inviteType': 'STAFF', 'expiresInHours': 24},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'create-staff'},
    )
    code = create.json()['code']

    join_headers = {'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'join-staff'}
    joined = client.post('/orgas/join_by_invite', json={'code': code}, headers=join_headers)
    assert joined.status_code == 200
    assert joined.json()['role'] == 'STAFF'

    manager_invite = client.post(
        f'/orgas/{org_id}/invites',
        json={'inviteType': 'MANAGER'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'create-manager'},
    ).json()['code']
    upgraded = client.post('/orgas/join_by_invite', json={'code': manager_invite}, headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'join-manager'})
    assert upgraded.status_code == 200
    assert upgraded.json()['role'] == 'MANAGER'

    no_op = client.post('/orgas/join_by_invite', json={'code': code}, headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'join-staff-again'})
    assert no_op.status_code == 200
    assert no_op.json()['role'] == 'MANAGER'
    assert no_op.json()['idempotent'] is True

    members = client.get(f'/orgas/{org_id}/members', headers={'Authorization': f'Bearer {owner_token}'}).json()['items']
    row = [m for m in members if m['user_id'] == user_id][0]
    assert row['role'] == 'MANAGER'


def test_revoke_prevents_join_and_open_and_preview_visibility_rules():
    owner_token, _ = _guest('owner-revoke')
    user_token, _ = _guest('joiner-revoke')
    org_id = _create_orga(owner_token)

    created = client.post(
        f'/orgas/{org_id}/invites',
        json={'inviteType': 'FOLLOWER'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'create-revokable'},
    ).json()

    open_res = client.get(f"/open?type=orga_invite&code={created['code']}")
    assert open_res.status_code == 200
    assert open_res.json()['type'] == 'orga_invite'

    revoked = client.post(
        f"/orgas/{org_id}/invites/{created['id']}/revoke",
        json={'reason': 'rotation'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'revoke-1'},
    )
    assert revoked.status_code == 200

    denied = client.post('/orgas/join_by_invite', json={'code': created['code']}, headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'join-revoked'})
    assert denied.status_code == 400

    preview_public = client.get(f"/orgas/invites/{created['code']}/preview")
    assert preview_public.status_code == 200

    private_org = _create_orga(owner_token, visibility='PRIVATE')
    private_invite = client.post(
        f'/orgas/{private_org}/invites',
        json={'inviteType': 'MEMBER'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'private-create'},
    ).json()['code']
    preview_private = client.get(f'/orgas/invites/{private_invite}/preview')
    assert preview_private.status_code == 404
