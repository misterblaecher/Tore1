from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db import Base, engine, now_utc
from main import app
from models import AppUser, OrganizationMembership
from app.forum_models import StructureGovernance


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _raw_guest(name: str) -> tuple[str, str]:
    response = client.post('/auth/guest', json={'display_name': name})
    assert response.status_code == 200, response.text
    token = response.json()['token']
    me = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200, me.text
    return token, me.json()['id']


def _registered(name: str) -> tuple[str, str]:
    token, user_id = _raw_guest(name)
    with Session(engine) as db:
        user = db.get(AppUser, user_id)
        assert user is not None
        user.is_guest = False
        user.is_deleted = False
        user.deleted_at = None
        user.account_status = 'ACTIVE'
        db.commit()
    return token, user_id


def _h(token: str, idem: str | None = None) -> dict[str, str]:
    headers = {'Authorization': f'Bearer {token}'}
    if idem:
        headers['Idempotency-Key'] = idem
    return headers


def _create_structure(token: str, name: str) -> dict:
    response = client.post(
        '/forum/v2/structures',
        json={'name': name, 'org_type': 'COMMITTEE'},
        headers=_h(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _join_legacy(org_id: int, token: str, key: str) -> None:
    response = client.post(f'/orgas/{org_id}/join', headers=_h(token, key))
    assert response.status_code == 200, response.text


def test_raw_guest_cannot_create_structure_or_access_private_forum():
    guest, _ = _raw_guest('review-raw-guest')

    create = client.post(
        '/forum/v2/structures',
        json={'name': 'Forbidden Guest Structure', 'org_type': 'COMMITTEE'},
        headers=_h(guest),
    )
    private = client.get('/forum/v2/me/structures', headers=_h(guest))
    invitation = client.post(
        '/forum/v2/invitations/accept',
        json={'token': 'x' * 32},
        headers=_h(guest),
    )

    for response in (create, private, invitation):
        assert response.status_code == 401, response.text
        assert response.json()['detail']['reason'] == 'REGISTERED_FORUM_USER_REQUIRED'

    # The explicitly public read surface remains anonymous.
    assert client.get('/forum/v2/health').status_code == 200


def test_guest_cannot_submit_structure_claim():
    owner, _ = _registered('review-claim-owner')
    structure = _create_structure(owner, 'Review Claim Structure')
    guest, _ = _raw_guest('review-claim-guest')

    response = client.post(
        f"/forum/v2/public/structures/{structure['slug']}/claims",
        json={'reason': 'Guest claim must be refused'},
        headers=_h(guest),
    )
    assert response.status_code == 401, response.text
    assert response.json()['detail']['reason'] == 'REGISTERED_FORUM_USER_REQUIRED'


def test_deleted_user_cannot_access_private_forum():
    token, user_id = _registered('review-deleted-caller')
    with Session(engine) as db:
        user = db.get(AppUser, user_id)
        user.is_deleted = True
        user.deleted_at = now_utc()
        db.commit()

    response = client.get('/forum/v2/me/structures', headers=_h(token))
    assert response.status_code == 401, response.text
    assert response.json()['detail']['reason'] == 'REGISTERED_FORUM_USER_REQUIRED'


def test_owner_transfer_rejects_guest_and_deleted_targets():
    owner, owner_id = _registered('review-transfer-owner')
    structure = _create_structure(owner, 'Review Transfer Structure')
    org_id, slug = structure['id'], structure['slug']

    guest_token, guest_id = _raw_guest('review-transfer-guest')
    _join_legacy(org_id, guest_token, 'join-review-transfer-guest')
    guest_transfer = client.post(
        f'/forum/v2/structures/{slug}/ownership/transfer',
        json={'new_owner_user_id': guest_id},
        headers=_h(owner, 'review-transfer-guest'),
    )
    assert guest_transfer.status_code == 409, guest_transfer.text
    assert guest_transfer.json()['detail']['reason'] == 'NEW_OWNER_MUST_BE_REGISTERED_USER'

    deleted_token, deleted_id = _registered('review-transfer-deleted')
    _join_legacy(org_id, deleted_token, 'join-review-transfer-deleted')
    with Session(engine) as db:
        deleted = db.get(AppUser, deleted_id)
        deleted.is_deleted = True
        deleted.deleted_at = now_utc()
        db.commit()

    deleted_transfer = client.post(
        f'/forum/v2/structures/{slug}/ownership/transfer',
        json={'new_owner_user_id': deleted_id},
        headers=_h(owner, 'review-transfer-deleted'),
    )
    assert deleted_transfer.status_code == 409, deleted_transfer.text
    assert deleted_transfer.json()['detail']['reason'] == 'NEW_OWNER_MUST_BE_REGISTERED_USER'

    with Session(engine) as db:
        governance = db.get(StructureGovernance, org_id)
        assert governance.owner_user_id == owner_id
        assert db.query(OrganizationMembership).filter_by(
            organization_id=org_id,
            user_id=guest_id,
        ).one().status == 'ACTIVE'


def test_folklore_versions_require_manage_permission_even_with_direct_id():
    owner, _ = _registered('review-folklore-owner')
    member, _ = _registered('review-folklore-member')
    structure = _create_structure(owner, 'Review Folklore Structure')
    _join_legacy(structure['id'], member, 'join-review-folklore-member')

    page = client.post(
        f"/forum/v2/structures/{structure['slug']}/folklore",
        json={
            'title': 'Treasury folklore secret',
            'content': 'historical-secret-value',
            'category': 'archives',
            'visibility': 'TREASURY',
            'published': False,
        },
        headers=_h(owner),
    )
    assert page.status_code == 201, page.text

    direct = client.get(
        f"/forum/v2/structures/{structure['slug']}/folklore/{page.json()['id']}/versions",
        headers=_h(member),
    )
    assert direct.status_code == 403, direct.text
    assert 'historical-secret-value' not in direct.text

    owner_history = client.get(
        f"/forum/v2/structures/{structure['slug']}/folklore/{page.json()['id']}/versions",
        headers=_h(owner),
    )
    assert owner_history.status_code == 200, owner_history.text
    assert owner_history.json()['items'][0]['content'] == 'historical-secret-value'


def test_member_posts_list_hides_draft_and_future_scheduled():
    owner, _ = _registered('review-posts-owner')
    member, _ = _registered('review-posts-member')
    structure = _create_structure(owner, 'Review Posts Structure')
    slug = structure['slug']
    _join_legacy(structure['id'], member, 'join-review-posts-member')

    payloads = [
        {
            'title': 'Visible published',
            'body': 'published-body',
            'status': 'PUBLISHED',
            'visibility': 'MEMBERS',
        },
        {
            'title': 'Hidden draft',
            'body': 'draft-body',
            'status': 'DRAFT',
            'visibility': 'MEMBERS',
        },
        {
            'title': 'Hidden scheduled',
            'body': 'scheduled-body',
            'status': 'SCHEDULED',
            'visibility': 'MEMBERS',
            'publish_at': '2099-01-01T12:00:00Z',
        },
    ]
    created_ids = []
    for payload in payloads:
        response = client.post(
            f'/forum/v2/structures/{slug}/posts',
            json=payload,
            headers=_h(owner),
        )
        assert response.status_code == 201, response.text
        created_ids.append(response.json()['id'])

    member_posts = client.get(f'/forum/v2/structures/{slug}/posts', headers=_h(member))
    assert member_posts.status_code == 200, member_posts.text
    member_items = member_posts.json()['items']
    assert [item['title'] for item in member_items] == ['Visible published']
    assert {item['id'] for item in member_items} == {created_ids[0]}

    manager_posts = client.get(f'/forum/v2/structures/{slug}/posts', headers=_h(owner))
    assert manager_posts.status_code == 200, manager_posts.text
    assert {item['id'] for item in manager_posts.json()['items']} == set(created_ids)
