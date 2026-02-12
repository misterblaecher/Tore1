from datetime import timedelta

from fastapi.testclient import TestClient

import secrets

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, PartnerUser, PartnerMembership
from partner_auth import _make_token


def _seed_partner(role: str = "manager"):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Battle Bar {suffix}", city="Test", partner_code=f"BATTLE{suffix}")
        s.add(bar)
        s.flush()
        event = Event(
            bar_id=bar.id,
            name="Battle Event",
            starts_at=now_utc(),
            ends_at=now_utc() + timedelta(hours=4),
            entry_price_cents=0,
            ticket_mode=False,
        )
        s.add(event)
        s.flush()
        user = PartnerUser(display_name="Manager", pin_hash="hash")
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role=role, display_name="Manager"))
        s.commit()
        return bar.id, event.id, _make_token(user.id, bar.id, role, "Manager")
    finally:
        s.close()


def _guest_token(client: TestClient, name: str = "battle-user") -> str:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    return res.json()['token']


def test_partner_battles_create_list_and_guards():
    bar_id, event_id, manager_token = _seed_partner(role="manager")
    _, _, staff_token = _seed_partner(role="bartender")
    client = TestClient(app)

    unauthorized = client.post('/partner/portal/battles', json={'event_id': event_id, 'title': 'A'})
    assert unauthorized.status_code == 401

    forbidden = client.post(
        '/partner/portal/battles',
        json={'event_id': event_id, 'title': 'A'},
        headers={'Authorization': f'Bearer {staff_token}'},
    )
    assert forbidden.status_code == 403

    created = client.post(
        '/partner/portal/battles',
        json={
            'event_id': event_id,
            'title': 'Rouge vs Bleu',
            'mode': 'teams',
            'teams': [{'name': 'Rouge', 'color': '#f00'}, {'name': 'Bleu', 'color': '#00f'}],
        },
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload['bar_id'] == bar_id
    assert len(payload['teams']) == 2

    listed = client.get(
        f'/partner/portal/battles?event_id={event_id}',
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert listed.status_code == 200
    assert any(row['id'] == payload['id'] for row in listed.json())


def test_battle_join_unique_idempotent():
    _, event_id, manager_token = _seed_partner(role="manager")
    client = TestClient(app)
    created = client.post(
        '/partner/portal/battles',
        json={'event_id': event_id, 'title': 'Solo', 'mode': 'solo'},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    battle_id = created.json()['id']
    guest_token = _guest_token(client, 'joiner')

    first = client.post(
        f'/battles/{battle_id}/join',
        json={},
        headers={'Authorization': f'Bearer {guest_token}'},
    )
    assert first.status_code == 200
    assert first.json()['idempotent'] is False

    second = client.post(
        f'/battles/{battle_id}/join',
        json={},
        headers={'Authorization': f'Bearer {guest_token}'},
    )
    assert second.status_code == 200
    assert second.json()['idempotent'] is True


def test_battle_action_idempotent_and_stats():
    _, event_id, manager_token = _seed_partner(role="manager")
    client = TestClient(app)
    created = client.post(
        '/partner/portal/battles',
        json={
            'event_id': event_id,
            'title': 'Team battle',
            'mode': 'teams',
            'teams': [{'name': 'A'}, {'name': 'B'}],
        },
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    battle = created.json()
    battle_id = battle['id']
    team_id = battle['teams'][0]['id']

    first = client.post(
        f'/partner/portal/battles/{battle_id}/action',
        json={'team_id': team_id, 'kind': 'AFFOND', 'delta': 1, 'idempotency_key': 'dup-1'},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert first.status_code == 200
    assert first.json()['idempotent'] is False

    second = client.post(
        f'/partner/portal/battles/{battle_id}/action',
        json={'team_id': team_id, 'kind': 'AFFOND', 'delta': 1, 'idempotency_key': 'dup-1'},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert second.status_code == 200
    assert second.json()['idempotent'] is True

    stats = client.get(
        f'/partner/portal/battles/{battle_id}/stats',
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert stats.status_code == 200
    payload = stats.json()
    scores = {team['id']: team['score'] for team in payload['teams']}
    assert scores[team_id] == 1
    assert len(payload['recent_actions']) == 1

def test_qr_resolve_battle_route_front():
    _, event_id, manager_token = _seed_partner(role="manager")
    client = TestClient(app)
    created = client.post(
        '/partner/portal/battles',
        json={'event_id': event_id, 'title': 'QR battle', 'mode': 'solo'},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    battle_id = created.json()['id']
    user_token = _guest_token(client, 'qr-battle')
    res = client.post(
        '/qr/resolve',
        json={'raw': f'tore://battle?battle_id={battle_id}'},
        headers={'Authorization': f'Bearer {user_token}'},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload['valid'] is True
    assert payload['type'] == 'battle'
    assert payload['battle_id'] == battle_id
    assert payload['route_front'] == f'/battles/{battle_id}'
