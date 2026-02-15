from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import (
    AuditLog,
    Committee,
    CommitteeForumCategory,
    CommitteeMembership,
    CommitteeYear,
)


def _auth_guest(client: TestClient, name: str) -> tuple[str, str]:
    Base.metadata.create_all(engine)
    token = client.post('/auth/guest', json={'display_name': name}).json()['token']
    me = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'}).json()
    return token, me['id']


def _seed_committee(owner_user_id: str) -> tuple[int, int, int, int, str]:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(3)
        committee = Committee(name=f'Forum {suffix}', slug=f'forum-{suffix}', description_public='Forum test')
        s.add(committee)
        s.flush()
        year_active = CommitteeYear(committee_id=committee.id, year_label='2025-2026', is_active=True)
        year_old = CommitteeYear(committee_id=committee.id, year_label='2024-2025', is_active=False)
        s.add_all([year_active, year_old])
        s.flush()
        category = CommitteeForumCategory(
            committee_id=committee.id,
            year_id=year_active.id,
            name='Annonces',
            slug='annonces',
            order_index=0,
            is_archived=False,
        )
        old_category = CommitteeForumCategory(
            committee_id=committee.id,
            year_id=year_old.id,
            name='Old',
            slug='old',
            order_index=0,
            is_archived=False,
        )
        s.add_all([
            CommitteeMembership(committee_id=committee.id, user_id=owner_user_id, role='OWNER', is_active=True),
            category,
            old_category,
        ])
        s.commit()
        return committee.id, year_active.id, year_old.id, category.id, old_category.slug
    finally:
        s.close()


def test_member_can_list_categories_and_posts_and_create_post_idempotent():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'owner-forum-member')
    committee_id, year_id, _old_year_id, category_id, _ = _seed_committee(owner_id)

    member_token, member_id = _auth_guest(client, 'member-forum')
    s = get_session()
    try:
        s.add(CommitteeMembership(committee_id=committee_id, user_id=member_id, role='MEMBER', is_active=True))
        s.commit()
    finally:
        s.close()

    cats = client.get(
        f'/committees/{committee_id}/forum/categories?year_id={year_id}',
        headers={'Authorization': f'Bearer {member_token}'},
    )
    assert cats.status_code == 200
    assert cats.json()[0]['id'] == category_id

    headers = {'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'forum-post-idem-1'}
    p1 = client.post(
        f'/committees/{committee_id}/forum/posts',
        json={'yearId': year_id, 'categoryId': category_id, 'title': 'Salut', 'body': 'Premier post'},
        headers=headers,
    )
    p2 = client.post(
        f'/committees/{committee_id}/forum/posts',
        json={'yearId': year_id, 'categoryId': category_id, 'title': 'Salut', 'body': 'Premier post'},
        headers=headers,
    )
    assert p1.status_code == 200
    assert p2.status_code == 200
    assert p1.json()['id'] == p2.json()['id']

    listing = client.get(
        f'/committees/{committee_id}/forum/posts?year_id={year_id}&category_id={category_id}',
        headers={'Authorization': f'Bearer {member_token}'},
    )
    assert listing.status_code == 200
    assert listing.json()['items'][0]['title'] == 'Salut'


def test_rate_limit_create_post_three_per_minute():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'owner-rate')
    _ = owner_token
    committee_id, year_id, _old_year_id, category_id, _ = _seed_committee(owner_id)

    member_token, member_id = _auth_guest(client, 'member-rate')
    s = get_session()
    try:
        s.add(CommitteeMembership(committee_id=committee_id, user_id=member_id, role='MEMBER', is_active=True))
        s.commit()
    finally:
        s.close()

    for i in range(3):
        ok = client.post(
            f'/committees/{committee_id}/forum/posts',
            json={'yearId': year_id, 'categoryId': category_id, 'title': f'post {i}', 'body': 'x'},
            headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': f'forum-rate-{i}'},
        )
        assert ok.status_code == 200

    limited = client.post(
        f'/committees/{committee_id}/forum/posts',
        json={'yearId': year_id, 'categoryId': category_id, 'title': 'post 4', 'body': 'x'},
        headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'forum-rate-4'},
    )
    assert limited.status_code == 429


def test_mod_can_pin_lock_delete_member_cannot_and_audit_exists():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'owner-mod')
    committee_id, year_id, _old_year_id, category_id, _ = _seed_committee(owner_id)

    member_token, member_id = _auth_guest(client, 'member-no-mod')
    mod_token, mod_id = _auth_guest(client, 'mod-forum')
    s = get_session()
    try:
        s.add_all([
            CommitteeMembership(committee_id=committee_id, user_id=member_id, role='MEMBER', is_active=True),
            CommitteeMembership(committee_id=committee_id, user_id=mod_id, role='MOD', is_active=True),
        ])
        s.commit()
    finally:
        s.close()

    created = client.post(
        f'/committees/{committee_id}/forum/posts',
        json={'yearId': year_id, 'categoryId': category_id, 'title': 'to moderate', 'body': 'body'},
        headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'create-mod-1'},
    )
    assert created.status_code == 200
    post_id = created.json()['id']

    denied = client.post(
        f'/committees/{committee_id}/forum/posts/{post_id}/pin',
        json={'pinned': True, 'reason': 'xx'},
        headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'member-pin-1'},
    )
    assert denied.status_code == 403

    for action, payload in [
        ('pin', {'pinned': True, 'reason': 'important'}),
        ('lock', {'locked': True, 'reason': 'close'}),
        ('delete', {'reason': 'cleanup'}),
    ]:
        ok = client.post(
            f'/committees/{committee_id}/forum/posts/{post_id}/{action}',
            json=payload,
            headers={'Authorization': f'Bearer {mod_token}', 'Idempotency-Key': f'mod-{action}-1'},
        )
        assert ok.status_code == 200

    hidden = client.get(
        f'/committees/{committee_id}/forum/posts?year_id={year_id}&category_id={category_id}',
        headers={'Authorization': f'Bearer {member_token}'},
    )
    assert hidden.status_code == 200
    assert hidden.json()['items'] == []

    s = get_session()
    try:
        actions = {
            row.action
            for row in s.query(AuditLog)
            .filter(AuditLog.entity_id == str(post_id), AuditLog.action.like('committee.forum.post.%'))
            .all()
        }
        assert 'committee.forum.post.pin' in actions
        assert 'committee.forum.post.lock' in actions
        assert 'committee.forum.post.delete' in actions
    finally:
        s.close()


def test_year_scoping_and_category_admin_audit():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'owner-year')
    committee_id, year_id, old_year_id, category_id, _ = _seed_committee(owner_id)

    create_cat = client.post(
        f'/committees/{committee_id}/forum/categories',
        json={'yearId': year_id, 'name': 'Docs', 'orderIndex': 2},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'cat-create-1'},
    )
    assert create_cat.status_code == 200
    created_cat_id = create_cat.json()['id']

    update_cat = client.put(
        f'/committees/{committee_id}/forum/categories/{created_cat_id}',
        json={'name': 'Docs & PV', 'isArchived': True},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'cat-update-1'},
    )
    assert update_cat.status_code == 200
    assert update_cat.json()['isArchived'] is True

    wrong_year = client.post(
        f'/committees/{committee_id}/forum/posts',
        json={'yearId': old_year_id, 'categoryId': category_id, 'title': 'bad scope', 'body': 'x'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'wrong-year-1'},
    )
    assert wrong_year.status_code == 404

    s = get_session()
    try:
        audits = {
            row.action for row in s.query(AuditLog).filter(AuditLog.action.like('committee.forum.category.%')).all()
        }
        assert 'committee.forum.category.create' in audits
        assert 'committee.forum.category.update' in audits
    finally:
        s.close()
