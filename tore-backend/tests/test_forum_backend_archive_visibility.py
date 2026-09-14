from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db import Base, engine
from main import app
from models import AppUser


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _registered(name: str) -> tuple[str, str]:
    response = client.post('/auth/guest', json={'display_name': name})
    assert response.status_code == 200, response.text
    token = response.json()['token']
    me = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200, me.text
    user_id = me.json()['id']
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


def test_archived_event_is_removed_from_public_event_and_summary_surfaces():
    owner, _ = _registered('archive-public-owner')
    structure = client.post(
        '/forum/v2/structures',
        json={'name': 'Archive Public Structure', 'org_type': 'COMMITTEE'},
        headers=_h(owner),
    )
    assert structure.status_code == 201, structure.text
    slug = structure.json()['slug']

    published_page = client.patch(
        f'/forum/v2/structures/{slug}/public-page',
        json={'status': 'PUBLISHED'},
        headers=_h(owner),
    )
    assert published_page.status_code == 200, published_page.text

    event = client.post(
        f'/forum/v2/structures/{slug}/events',
        json={
            'name': 'Archive Me',
            'starts_at': '2034-01-01T18:00:00Z',
            'ends_at': '2034-01-01T22:00:00Z',
            'visibility': 'PUBLIC',
            'capacity': 100,
        },
        headers=_h(owner),
    )
    assert event.status_code == 201, event.text
    event_id = event.json()['id']

    states = [
        'PUBLISHED',
        'SYNCED_TO_APP',
        'LIVE',
        'CLOSED',
        'RECAP_DRAFT',
        'RECAP_PUBLISHED',
    ]
    for index, state in enumerate(states):
        transitioned = client.post(
            f'/forum/v2/structures/{slug}/events/{event_id}/transition',
            json={'target': state},
            headers=_h(owner, f'archive-sequence-{index}-{state}'),
        )
        assert transitioned.status_code == 200, transitioned.text

    public_before = client.get(f'/forum/v2/public/structures/{slug}/events')
    assert public_before.status_code == 200, public_before.text
    assert any(item['id'] == event_id for item in public_before.json()['items'])

    archived = client.post(
        f'/forum/v2/structures/{slug}/events/{event_id}/transition',
        json={'target': 'ARCHIVED'},
        headers=_h(owner, 'archive-sequence-final'),
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()['status'] == 'ARCHIVED'

    public_after = client.get(f'/forum/v2/public/structures/{slug}/events')
    assert public_after.status_code == 200, public_after.text
    assert all(item['id'] != event_id for item in public_after.json()['items'])

    summary_after = client.get(f'/forum/v2/public/events/{event_id}/summary')
    assert summary_after.status_code == 404
