from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog, Committee, CommitteeMembership, CommitteeYear


def _auth_guest(client: TestClient, name: str) -> tuple[str, str]:
    Base.metadata.create_all(engine)
    token = client.post('/auth/guest', json={'display_name': name}).json()['token']
    me = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'}).json()
    return token, me['id']


def _seed_committee(owner_user_id: str) -> tuple[int, int]:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(3)
        committee = Committee(name=f'OS {suffix}', slug=f'os-{suffix}', description_public='Committee OS')
        s.add(committee)
        s.flush()
        year = CommitteeYear(committee_id=committee.id, year_label='2025-2026', is_active=True)
        s.add(year)
        s.add(CommitteeMembership(committee_id=committee.id, user_id=owner_user_id, role='OWNER', is_active=True))
        s.commit()
        return committee.id, year.id
    finally:
        s.close()


def test_committee_space_feed_calendar_expenses_permissions_and_crud():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'owner-space')
    committee_id, _ = _seed_committee(owner_id)

    member_token, member_id = _auth_guest(client, 'member-space')
    s = get_session()
    try:
        s.add(CommitteeMembership(committee_id=committee_id, user_id=member_id, role='MEMBER', is_active=True))
        s.commit()
    finally:
        s.close()

    denied_post = client.post(
        f'/committees/{committee_id}/feed/posts',
        json={'title': 'x', 'body': 'x', 'pinned': False},
        headers={'Authorization': f'Bearer {member_token}'},
    )
    assert denied_post.status_code == 403

    created_post = client.post(
        f'/committees/{committee_id}/feed/posts',
        json={'title': 'Annonce', 'body': 'Bienvenue', 'pinned': True},
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    assert created_post.status_code == 200
    post_id = created_post.json()['id']

    list_posts = client.get(
        f'/committees/{committee_id}/feed/posts',
        headers={'Authorization': f'Bearer {member_token}'},
    )
    assert list_posts.status_code == 200
    assert list_posts.json()['items'][0]['id'] == post_id
    assert list_posts.json()['items'][0]['isPinned'] is True

    updated_post = client.put(
        f'/committees/{committee_id}/feed/posts/{post_id}',
        json={'title': 'Annonce MAJ', 'body': 'Bienvenue 2', 'pinned': False},
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    assert updated_post.status_code == 200
    assert updated_post.json()['title'] == 'Annonce MAJ'

    created_item = client.post(
        f'/committees/{committee_id}/calendar/items',
        json={'title': 'Réunion', 'date': '2026-03-10', 'location': 'Bureau', 'notes': 'Point budget'},
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    assert created_item.status_code == 200
    item_id = created_item.json()['id']

    month_items = client.get(
        f'/committees/{committee_id}/calendar/items?month=2026-03',
        headers={'Authorization': f'Bearer {member_token}'},
    )
    assert month_items.status_code == 200
    assert month_items.json()['items'][0]['id'] == item_id

    denied_expense = client.post(
        f'/committees/{committee_id}/expenses',
        json={'amountCents': 1200, 'label': 'Snacks', 'category': 'logistique', 'date': '2026-03-11'},
        headers={'Authorization': f'Bearer {member_token}'},
    )
    assert denied_expense.status_code == 403

    created_expense = client.post(
        f'/committees/{committee_id}/expenses',
        json={'amountCents': 1200, 'label': 'Snacks', 'category': 'logistique', 'date': '2026-03-11'},
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    assert created_expense.status_code == 200

    list_expenses = client.get(
        f'/committees/{committee_id}/expenses?month=2026-03',
        headers={'Authorization': f'Bearer {member_token}'},
    )
    assert list_expenses.status_code == 200
    assert list_expenses.json()['totalsByCategory']['logistique'] == 1200

    export_expenses = client.get(
        f'/committees/{committee_id}/expenses/export.json?month=2026-03',
        headers={'Authorization': f'Bearer {member_token}'},
    )
    assert export_expenses.status_code == 200
    assert export_expenses.json()['totalCents'] == 1200

    delete_post = client.delete(
        f'/committees/{committee_id}/feed/posts/{post_id}',
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    assert delete_post.status_code == 200

    s = get_session()
    try:
        actions = {
            row.action
            for row in s.query(AuditLog).filter(AuditLog.action.like('committee.space.%')).all()
        }
        assert 'committee.space.feed.create' in actions
        assert 'committee.space.calendar.create' in actions
        assert 'committee.space.expense.create' in actions
    finally:
        s.close()
