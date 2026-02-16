from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog, OrganizationMembership

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _guest(name: str) -> str:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    return res.json()['token']


def _create_orga(owner_token: str) -> int:
    res = client.post('/orgas', json={'name': 'Community X'}, headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'orga-create-v2'})
    assert res.status_code == 200
    return res.json()['orga']['id']


def test_membership_role_enforcement_and_posts_permissions():
    owner = _guest('owner')
    member = _guest('member')
    outsider = _guest('outsider')
    org_id = _create_orga(owner)

    upsert = client.post(f'/orgas/{org_id}/members', json={'user_id': client.get('/auth/me', headers={'Authorization': f'Bearer {member}'}).json()['id'], 'role': 'MEMBER'}, headers={'Authorization': f'Bearer {owner}', 'Idempotency-Key': 'm-upsert-1'})
    assert upsert.status_code == 200

    denied = client.get(f'/orgas/{org_id}/members', headers={'Authorization': f'Bearer {member}'})
    assert denied.status_code == 403

    post_denied = client.post(f'/orgas/{org_id}/posts', json={'text': 'hello'}, headers={'Authorization': f'Bearer {outsider}', 'Idempotency-Key': 'p-denied'})
    assert post_denied.status_code == 403

    post_ok = client.post(f'/orgas/{org_id}/posts', json={'text': 'hello members'}, headers={'Authorization': f'Bearer {member}', 'Idempotency-Key': 'p-ok'})
    assert post_ok.status_code == 200
    post_id = post_ok.json()['id']

    pin_denied = client.post(f'/orgas/{org_id}/posts/{post_id}/pin', headers={'Authorization': f'Bearer {member}', 'Idempotency-Key': 'pin-denied'})
    assert pin_denied.status_code == 403

    pin_ok = client.post(f'/orgas/{org_id}/posts/{post_id}/pin', headers={'Authorization': f'Bearer {owner}', 'Idempotency-Key': 'pin-ok'})
    assert pin_ok.status_code == 200


def test_follow_unfollow_and_profile_idempotency_with_audit():
    user_token = _guest('profile-user')
    owner = _guest('org-owner')
    org_id = _create_orga(owner)

    follow1 = client.post(f'/orgas/{org_id}/follow', headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'follow-1'})
    follow2 = client.post(f'/orgas/{org_id}/follow', headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'follow-1'})
    assert follow1.status_code == 200
    assert follow2.status_code == 200
    assert follow1.json() == follow2.json()

    unf1 = client.post(f'/orgas/{org_id}/unfollow', headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'unfollow-1'})
    unf2 = client.post(f'/orgas/{org_id}/unfollow', headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'unfollow-1'})
    assert unf1.status_code == 200
    assert unf2.status_code == 200

    bad = client.put('/me/profile', json={'display_name': '', 'visibility': 'PUBLIC'}, headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'profile-bad'})
    assert bad.status_code == 422

    good1 = client.put('/me/profile', json={'display_name': 'PseudoV2', 'bio': 'bio', 'instagram_handle': 'insta', 'visibility': 'PUBLIC'}, headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'profile-1'})
    good2 = client.put('/me/profile', json={'display_name': 'PseudoV2', 'bio': 'bio', 'instagram_handle': 'insta', 'visibility': 'PUBLIC'}, headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'profile-1'})
    assert good1.status_code == 200
    assert good2.status_code == 200
    assert good1.json() == good2.json()

    with get_session() as s:
        audits = s.query(AuditLog).filter(AuditLog.actor_user_id.is_not(None)).all()
        actions = {a.action for a in audits}
        assert 'organization.follow' in actions
        assert 'organization.unfollow' in actions
        assert 'user.profile.update' in actions
        for row in audits:
            if row.action in {'organization.follow', 'organization.unfollow', 'user.profile.update'}:
                assert row.idempotency_key is not None
                assert isinstance(row.payload_json, dict)


def test_invite_payload_contains_qr_link_and_code():
    owner = _guest('owner-invite')
    org_id = _create_orga(owner)
    res = client.get(f'/orgas/{org_id}/invite', headers={'Authorization': f'Bearer {owner}'})
    assert res.status_code == 200
    payload = res.json()
    assert payload['invite_code']
    assert payload['https_link'].startswith('https://')
    assert payload['deeplink'].startswith('tore://')
    assert payload['qr_payload'] == payload['deeplink']
