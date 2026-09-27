from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from app.legacy import monolith as legacy_monolith
from main import app
from models import Event, EventRuntimeState, EventStaff, Organization, OrganizationMembership


def _seed_user(client: TestClient, name: str) -> tuple[str, str]:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    payload = res.json()
    return payload['user']['id'], payload['token']


def test_me_events_includes_host_user_and_orga_manager_events():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    user_id, token = _seed_user(client, f'me-events-{secrets.token_hex(2)}')

    s = get_session()
    try:
        org = Organization(name='Club', slug=f'club-{secrets.token_hex(2)}', created_by_user_id=user_id)
        s.add(org)
        s.flush()
        s.add(OrganizationMembership(organization_id=org.id, user_id=user_id, role='MANAGER', status='ACTIVE', created_by_user_id=user_id))

        now = datetime.now(timezone.utc)
        user_event = Event(name='User Hosted', starts_at=now + timedelta(days=1), ends_at=now + timedelta(days=1, hours=2), host_type='user', host_id=user_id, visibility='PRIVATE', publication_status='DRAFT', modules_on={'entry': True})
        org_event = Event(name='Orga Hosted', starts_at=now + timedelta(days=2), ends_at=now + timedelta(days=2, hours=2), host_type='orga', host_id=str(org.id), visibility='PUBLIC', publication_status='PUBLISHED')
        s.add_all([user_event, org_event])
        s.flush()
        s.add(EventRuntimeState(event_id=user_event.id, state='LIVE', updated_at=now))
        s.add(EventRuntimeState(event_id=org_event.id, state='DEGRADED', updated_at=now))
        s.commit()
    finally:
        s.close()

    res = client.get('/me/events', headers={'Authorization': f'Bearer {token}'})
    assert res.status_code == 200
    payload = res.json()
    merged = [*payload['LIVE'], *payload['TODAY'], *payload['UPCOMING'], *payload['PAST']]
    names = {item['name'] for item in merged}
    assert 'User Hosted' in names
    assert 'Orga Hosted' in names
    by_name = {item['name']: item for item in merged}
    assert by_name['User Hosted']['roleForMe'] == 'OWNER'
    assert by_name['User Hosted']['canManage'] is True
    assert by_name['Orga Hosted']['roleForMe'] == 'MANAGER'
    assert by_name['Orga Hosted']['canManage'] is True


def test_orga_private_events_refuses_without_perms():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    owner_id, owner_token = _seed_user(client, f'owner-{secrets.token_hex(2)}')
    member_id, member_token = _seed_user(client, f'member-{secrets.token_hex(2)}')

    s = get_session()
    try:
        org = Organization(name='Private orga', slug=f'private-{secrets.token_hex(2)}', created_by_user_id=owner_id)
        s.add(org)
        s.flush()
        s.add(OrganizationMembership(organization_id=org.id, user_id=owner_id, role='OWNER', status='ACTIVE', created_by_user_id=owner_id))
        s.add(OrganizationMembership(organization_id=org.id, user_id=member_id, role='MEMBER', status='ACTIVE', created_by_user_id=owner_id))
        s.add(Event(name='Draft hidden', starts_at=datetime.now(timezone.utc), ends_at=datetime.now(timezone.utc) + timedelta(hours=2), host_type='orga', host_id=str(org.id), visibility='PRIVATE', publication_status='DRAFT'))
        s.commit()
        org_id = org.id
    finally:
        s.close()

    denied = client.get(f'/orgas/{org_id}/events/private', headers={'Authorization': f'Bearer {member_token}'})
    assert denied.status_code == 403

    allowed = client.get(f'/orgas/{org_id}/events/private', headers={'Authorization': f'Bearer {owner_token}'})
    assert allowed.status_code == 200
    merged = [*allowed.json()['LIVE'], *allowed.json()['TODAY'], *allowed.json()['UPCOMING'], *allowed.json()['PAST']]
    assert any(item['name'] == 'Draft hidden' for item in merged)


def test_bucketing_today_upcoming_live_timezone_and_staff_role(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    user_id, token = _seed_user(client, f'bucket-{secrets.token_hex(2)}')

    frozen = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(legacy_monolith, 'now_utc', lambda: frozen)

    s = get_session()
    try:
        live_event = Event(name='Live event', starts_at=frozen - timedelta(hours=1), ends_at=frozen + timedelta(hours=1), host_type='user', host_id='other-user', timezone='Europe/Brussels')
        today_event = Event(name='Today event', starts_at=datetime(2026, 1, 2, 18, 0, tzinfo=timezone.utc), ends_at=datetime(2026, 1, 2, 22, 0, tzinfo=timezone.utc), host_type='user', host_id=user_id, timezone='Europe/Brussels')
        upcoming_event = Event(name='Upcoming event', starts_at=datetime(2026, 1, 3, 8, 0, tzinfo=timezone.utc), ends_at=datetime(2026, 1, 3, 12, 0, tzinfo=timezone.utc), host_type='user', host_id=user_id, timezone='Europe/Brussels')
        s.add_all([live_event, today_event, upcoming_event])
        s.flush()
        s.add(EventStaff(event_id=live_event.id, user_id=user_id, role='entry', is_active=True, created_by_user_id=user_id))
        s.commit()
    finally:
        s.close()

    res = client.get('/me/events', headers={'Authorization': f'Bearer {token}'})
    assert res.status_code == 200
    payload = res.json()
    assert any(item['name'] == 'Live event' for item in payload['LIVE'])
    assert any(item['name'] == 'Today event' for item in payload['TODAY'])
    assert any(item['name'] == 'Upcoming event' for item in payload['UPCOMING'])

    live_item = next(item for item in payload['LIVE'] if item['name'] == 'Live event')
    assert live_item['roleForMe'] == 'STAFF'
    assert live_item['canManage'] is False


def test_orga_private_events_supports_cursor_pagination_and_fields():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    owner_id, owner_token = _seed_user(client, f'owner-page-{secrets.token_hex(2)}')

    s = get_session()
    try:
        org = Organization(name='Page orga', slug=f'page-{secrets.token_hex(2)}', created_by_user_id=owner_id)
        s.add(org)
        s.flush()
        s.add(OrganizationMembership(organization_id=org.id, user_id=owner_id, role='OWNER', status='ACTIVE', created_by_user_id=owner_id))
        now = datetime.now(timezone.utc)
        for i in range(3):
            event = Event(
                name=f'Page {i}',
                starts_at=now + timedelta(days=i + 1),
                ends_at=now + timedelta(days=i + 1, hours=2),
                host_type='orga',
                host_id=str(org.id),
                visibility='PRIVATE' if i == 0 else 'PUBLIC',
                publication_status='DRAFT' if i == 0 else 'PUBLISHED',
                modules_on={'entry': i % 2 == 0},
            )
            s.add(event)
            s.flush()
            s.add(EventRuntimeState(event_id=event.id, state='PAUSE' if i == 0 else 'LIVE', updated_at=now))
        s.commit()
        org_id = org.id
    finally:
        s.close()

    first = client.get(
        f'/orgas/{org_id}/events/private?limit=2',
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    assert first.status_code == 200
    payload = first.json()
    merged = [*payload['LIVE'], *payload['TODAY'], *payload['UPCOMING'], *payload['PAST']]
    assert len(merged) == 2
    assert payload['nextCursor'] is not None
    assert all('publicationStatus' in row for row in merged)
    assert all('visibility' in row for row in merged)
    assert all('modulesOn' in row for row in merged)
    assert all('host_type' in row for row in merged)
    assert all('host_id' in row for row in merged)
    assert all('eventState' in row for row in merged)
    assert all('event_code' not in row for row in merged)

    second = client.get(
        f"/orgas/{org_id}/events/private?limit=2&cursor={payload['nextCursor']}",
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    assert second.status_code == 200
    second_payload = second.json()
    second_merged = [*second_payload['LIVE'], *second_payload['TODAY'], *second_payload['UPCOMING'], *second_payload['PAST']]
    assert len(second_merged) == 1
    assert second_payload['nextCursor'] is None


def test_orga_public_events_contains_essential_fields_without_private_tokens():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    user_id, _ = _seed_user(client, f'public-fields-{secrets.token_hex(2)}')

    s = get_session()
    try:
        org = Organization(name='Public orga', slug=f'pub-{secrets.token_hex(2)}', created_by_user_id=user_id)
        s.add(org)
        s.flush()
        now = datetime.now(timezone.utc)
        event = Event(
            name='Public Listed',
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=3),
            host_type='orga',
            host_id=str(org.id),
            visibility='PUBLIC',
            publication_status='PUBLISHED',
            modules_on={'entry': True},
            event_code='SECRET-CODE',
        )
        s.add(event)
        s.flush()
        s.add(EventRuntimeState(event_id=event.id, state='LIVE', updated_at=now))
        s.commit()
        org_id = org.id
    finally:
        s.close()

    res = client.get(f'/orgas/{org_id}/events')
    assert res.status_code == 200
    items = res.json()['items']
    assert len(items) == 1
    row = items[0]
    assert row['publicationStatus'] == 'PUBLISHED'
    assert row['visibility'] == 'PUBLIC'
    assert row['eventState'] == 'LIVE'
    assert row['modulesOn']['entry'] is True
    assert row['host_type'] == 'orga'
    assert row['host_id'] == str(org_id)
    assert 'event_code' in row
