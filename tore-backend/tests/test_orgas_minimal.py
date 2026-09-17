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


def _publish(token: str, created, key: str) -> None:
    slug = created.json()['orga']['slug']
    response = client.post(
        f'/forum/structures/{slug}/publish',
        json={'reason': 'Publication explicite du test'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': key},
    )
    assert response.status_code == 200


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
    assert first.json()['orga']['visibility'] == 'PRIVATE'
    assert first.json()['orga']['lifecycle'] == 'SETUP'

    org_id = first.json()['orga']['id']
    with get_session() as s:
        rows = s.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org_id).all()
        assert len(rows) == 1
        assert rows[0].role == 'OWNER'


def test_explorer_filtering_basic():
    token = _guest('creator')
    alpha = client.post('/orgas', json={'name': 'Alpha Liège', 'city': 'Liège', 'org_type': 'Student'}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'orga-exp-1'})
    beta = client.post('/orgas', json={'name': 'Beta Namur', 'city': 'Namur', 'org_type': 'Association'}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'orga-exp-2'})
    _publish(token, alpha, 'orga-exp-publish-1')
    _publish(token, beta, 'orga-exp-publish-2')

    by_city = client.get('/orgas?city=liège')
    assert by_city.status_code == 200
    assert len(by_city.json()['items']) == 1

    by_query = client.get('/orgas?query=beta')
    assert by_query.status_code == 200
    assert len(by_query.json()['items']) == 1


def test_explorer_filters_private_ranking_and_sorting():
    token = _guest('explorer-owner')
    private_res = client.post('/orgas', json={'name': 'Private Club', 'city': 'Liege', 'org_type': 'asso', 'visibility': 'PRIVATE'}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'orga-private-1'})
    assert private_res.status_code == 200

    alpha = client.post('/orgas', json={'name': 'Comite Alpha', 'city': 'Liege', 'org_type': 'comite', 'instagram_handle': 'alphaoff', 'join_mode': 'FOLLOW_ONLY'}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'orga-public-a'})
    beta = client.post('/orgas', json={'name': 'Bar Beta', 'city': 'Bruxelles', 'org_type': 'bar', 'join_mode': 'OPEN_MEMBERSHIP'}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'orga-public-b'})
    gamma = client.post('/orgas', json={'name': 'Asso Gamma', 'city': 'Liege Centre', 'org_type': 'asso', 'join_mode': 'REQUEST_TO_JOIN'}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'orga-public-c'})
    assert alpha.status_code == beta.status_code == gamma.status_code == 200
    _publish(token, alpha, 'orga-public-a-publish')
    _publish(token, beta, 'orga-public-b-publish')
    _publish(token, gamma, 'orga-public-c-publish')

    alpha_id = alpha.json()['orga']['id']
    beta_id = beta.json()['orga']['id']

    follower = _guest('follower-one')
    client.post(f'/orgas/{alpha_id}/follow', headers={'Authorization': f'Bearer {follower}', 'Idempotency-Key': 'follow-1'})
    member = _guest('member-one')
    client.post(f'/orgas/{alpha_id}/join', headers={'Authorization': f'Bearer {member}', 'Idempotency-Key': 'join-1'})
    follower2 = _guest('follower-two')
    client.post(f'/orgas/{beta_id}/follow', headers={'Authorization': f'Bearer {follower2}', 'Idempotency-Key': 'follow-2'})

    by_q = client.get('/orgas?q=alphaoff')
    assert by_q.status_code == 200
    assert len(by_q.json()['items']) == 1
    assert by_q.json()['items'][0]['name'] == 'Comite Alpha'

    by_type = client.get('/orgas?type=bar')
    assert by_type.status_code == 200
    assert [item['name'] for item in by_type.json()['items']] == ['Bar Beta']

    by_city = client.get('/orgas?city=liege')
    assert by_city.status_code == 200
    names = [item['name'] for item in by_city.json()['items']]
    assert 'Comite Alpha' in names
    assert 'Asso Gamma' in names
    assert 'Private Club' not in names

    by_popular = client.get('/orgas?sort=popular&limit=2')
    assert by_popular.status_code == 200
    payload = by_popular.json()
    assert payload['items'][0]['name'] == 'Comite Alpha'
    assert payload['items'][0]['followersCount'] >= payload['items'][1]['followersCount']
    assert payload['nextCursor'] is not None

    next_page = client.get(f"/orgas?sort=popular&limit=2&cursor={payload['nextCursor']}")
    assert next_page.status_code == 200
    assert next_page.json()['items']

    recent = client.get('/orgas?sort=recent')
    assert recent.status_code == 200
    recent_items = recent.json()['items']
    recent_with_activity = [it for it in recent_items if it.get('lastActiveAt')]
    assert recent_with_activity
    parsed = [it['lastActiveAt'] for it in recent_with_activity]
    assert parsed == sorted(parsed, reverse=True)


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

    invite = client.post(f'/orgas/{org_id}/invites', json={'inviteType': 'MEMBER', 'expiresInHours': 24}, headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'orga-audit-invite-1'})
    code = invite.json()['code']
    join = client.post('/orgas/join_by_invite', json={'code': code}, headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'orga-audit-join-1'})
    assert join.status_code == 200

    with get_session() as s:
        create_log = s.query(AuditLog).filter(AuditLog.action == 'organization.create').first()
        join_log = s.query(AuditLog).filter(AuditLog.action == 'orga_join_by_invite').first()
        assert create_log is not None
        assert create_log.actor_user_id is not None
        assert create_log.idempotency_key == 'orga-audit-1'
        assert join_log is not None
        assert join_log.actor_user_id is not None
        assert join_log.idempotency_key == 'orga-audit-join-1'
