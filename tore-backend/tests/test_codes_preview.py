from fastapi.testclient import TestClient

from db import Base, engine
from main import app

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _guest(name: str) -> str:
    return client.post('/auth/guest', json={'display_name': name}).json()['token']


def _create_event(token: str, *, visibility: str = 'PUBLIC', publish: bool = True) -> dict:
    res = client.post(
        '/events',
        json={
            'name': f'Ev-{visibility}',
            'starts_at': '2030-01-01T18:00:00Z',
            'ends_at': '2030-01-01T23:00:00Z',
            'visibility': visibility,
                    },
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': f'create-{visibility}'},
    )
    assert res.status_code == 200
    payload = res.json()
    if publish:
        published = client.post(f"/events/{payload['event_id']}/publish", headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': f"publish-{payload['event_id']}"})
        assert published.status_code == 200
    return payload


def test_codes_preview_join_public_and_private_safe_hints():
    owner = _guest('owner')
    pub = _create_event(owner, visibility='PUBLIC', publish=True)
    priv = _create_event(owner, visibility='PRIVATE', publish=True)

    pub_preview = client.get(f"/codes/preview?code={pub['event_code']}")
    assert pub_preview.status_code == 200
    assert pub_preview.json()['kind'] == 'join'
    assert pub_preview.json()['requiresAuth'] is False
    assert pub_preview.json()['status'] == 'ok'

    priv_preview = client.get(f"/codes/preview?code={priv['event_code']}")
    assert priv_preview.status_code == 200
    assert priv_preview.json()['requiresAuth'] is True
    assert priv_preview.json()['eventHint'] is None


def test_codes_preview_staff_invite_revoked_status():
    owner = _guest('owner-staff')
    event = _create_event(owner)
    event_id = event['event_id']

    created = client.post(
        f'/events/{event_id}/staff_invite_code',
        json={'role': 'ENTRY'},
        headers={'Authorization': f'Bearer {owner}', 'Idempotency-Key': 'staff-create'},
    )
    code = created.json()['code']

    revoked = client.post(
        f'/events/{event_id}/staff_invites/{code}/revoke',
        json={'reason': 'test'},
        headers={'Authorization': f'Bearer {owner}', 'Idempotency-Key': 'staff-revoke'},
    )
    assert revoked.status_code == 200

    preview = client.get(f'/codes/preview?code={code}')
    assert preview.status_code == 200
    assert preview.json()['kind'] == 'staff_invite'
    assert preview.json()['status'] == 'revoked'


def test_codes_preview_unknown_string_is_invalid_unknown():
    preview = client.get('/codes/preview?code=%40%40bad%0Acode###')
    assert preview.status_code == 200
    assert preview.json()['kind'] == 'unknown'
    assert preview.json()['status'] == 'invalid'


def test_codes_preview_private_join_no_title_leak_requires_auth():
    owner = _guest('owner-private')
    private_event = _create_event(owner, visibility='PRIVATE', publish=True)

    preview = client.get(f"/codes/preview?code= {private_event['event_code'][:3]}-{private_event['event_code'][3:]} ")
    assert preview.status_code == 200
    assert preview.json()['kind'] == 'join'
    assert preview.json()['requiresAuth'] is True
    assert preview.json()['eventHint'] is None
    assert preview.json()['titleHint'] == 'Event privé TORÈ'
