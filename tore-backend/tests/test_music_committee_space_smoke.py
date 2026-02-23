from datetime import timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Committee, CommitteeMembership, CommitteeYear, Event, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _guest(client: TestClient, name: str) -> tuple[str, str]:
    res = client.post('/auth/guest', json={'display_name': f'{name}-{secrets.token_hex(3)}'})
    assert res.status_code == 200
    payload = res.json()
    return payload['token'], payload['user']['id']


def _seed_event() -> tuple[int, str, str]:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f'Music Smoke {suffix}', city='Liège', partner_code=f'MSMK{suffix}')
        s.add(bar)
        s.flush()
        manager = PartnerUser(display_name='Manager', pin_hash='hash')
        s.add(manager)
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role='manager', display_name='Manager'))
        event = Event(
            bar_id=bar.id,
            name='Music Smoke Event',
            starts_at=now_utc() - timedelta(hours=1),
            ends_at=now_utc() + timedelta(hours=2),
            modules_on={'music_vote': True},
        )
        s.add(event)
        s.commit()
        return event.id, _make_token(manager.id, bar.id, 'manager', 'Manager'), manager.id
    finally:
        s.close()


def _seed_committee(owner_user_id: str) -> int:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(3)
        committee = Committee(name=f'Committee Smoke {suffix}', slug=f'c-smoke-{suffix}', description_public='committee smoke test')
        s.add(committee)
        s.flush()
        s.add(CommitteeYear(committee_id=committee.id, year_label='2026-2027', is_active=True))
        s.add(CommitteeMembership(committee_id=committee.id, user_id=owner_user_id, role='OWNER', is_active=True))
        s.commit()
        return committee.id
    finally:
        s.close()


def test_music_round_start_smoke_200_401_403():
    client = TestClient(app)
    event_id, manager_token, _ = _seed_event()
    guest_token, _ = _guest(client, 'music-user')

    ok = client.post(
        f'/events/{event_id}/music/admin/round/start',
        json={'durationSec': 60},
        headers={'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'smoke-music-1'},
    )
    assert ok.status_code == 200

    unauthorized = client.post(
        f'/events/{event_id}/music/admin/round/start',
        json={'durationSec': 60},
        headers={'Idempotency-Key': 'smoke-music-2'},
    )
    assert unauthorized.status_code == 403

    forbidden = client.post(
        f'/events/{event_id}/music/admin/round/start',
        json={'durationSec': 60},
        headers={'Authorization': f'Bearer {guest_token}', 'Idempotency-Key': 'smoke-music-3'},
    )
    assert forbidden.status_code == 403


def test_committee_feed_create_smoke_200_401_403():
    client = TestClient(app)
    owner_token, owner_user_id = _guest(client, 'committee-owner')
    member_token, member_user_id = _guest(client, 'committee-member')
    committee_id = _seed_committee(owner_user_id)

    s = get_session()
    try:
        s.add(CommitteeMembership(committee_id=committee_id, user_id=member_user_id, role='MEMBER', is_active=True))
        s.commit()
    finally:
        s.close()

    ok = client.post(
        f'/committees/{committee_id}/feed/posts',
        json={'title': 'Annonce', 'body': 'Bienvenue', 'pinned': False},
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    assert ok.status_code == 200

    unauthorized = client.post(
        f'/committees/{committee_id}/feed/posts',
        json={'title': 'Annonce', 'body': 'Bienvenue', 'pinned': False},
    )
    assert unauthorized.status_code == 401

    forbidden = client.post(
        f'/committees/{committee_id}/feed/posts',
        json={'title': 'Annonce', 'body': 'Bienvenue', 'pinned': False},
        headers={'Authorization': f'Bearer {member_token}'},
    )
    assert forbidden.status_code == 403
