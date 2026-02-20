from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _guest(name: str) -> str:
    return client.post('/auth/guest', json={'display_name': name}).json()['token']


def _create_event(token: str, *, visibility: str = 'PUBLIC') -> dict:
    res = client.post('/events', json={'name': 'PR51', 'starts_at': '2030-01-01T18:00:00Z', 'ends_at': '2030-01-01T23:00:00Z', 'visibility': visibility}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': f'create-{visibility}'})
    payload = res.json()
    client.post(f"/events/{payload['event_id']}/publish", headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': f"publish-{payload['event_id']}"})
    return payload


def test_codes_preview_has_open_url_and_deeplink_for_three_types():
    owner = _guest('owner')
    event = _create_event(owner)
    event_preview = client.get(f"/codes/preview?code={event['event_code']}")
    assert event_preview.status_code == 200
    assert event_preview.json()['openUrl'].startswith('http')
    assert event_preview.json()['deeplink'].startswith('tore://open')

    invite = client.post(f"/events/{event['event_id']}/staff_invite_code", json={'role': 'ENTRY'}, headers={'Authorization': f'Bearer {owner}', 'Idempotency-Key': 'staff-1'}).json()['code']
    staff_preview = client.get(f'/codes/preview?code={invite}')
    assert staff_preview.status_code == 200
    assert staff_preview.json()['kind'] == 'staff_invite'
    assert staff_preview.json()['deeplink'].startswith('tore://open')

    org = client.post('/orgas', json={'name': 'Org', 'visibility': 'PUBLIC'}, headers={'Authorization': f'Bearer {owner}', 'Idempotency-Key': 'orga-create'}).json()
    org_inv = client.post(f"/orgas/{org['orga']['id']}/invites", json={'inviteType': 'MEMBER'}, headers={'Authorization': f'Bearer {owner}', 'Idempotency-Key': 'orga-inv'}).json()['code']
    org_preview = client.get(f'/codes/preview?code={org_inv}')
    assert org_preview.status_code == 200
    assert org_preview.json()['kind'] == 'orga_invite'
    assert org_preview.json()['openUrl'].startswith('http')


def test_codes_consume_join_by_code_idempotent():
    owner = _guest('owner')
    user = _guest('joiner')
    event = _create_event(owner, visibility='PRIVATE')
    headers = {'Authorization': f'Bearer {user}', 'Idempotency-Key': 'consume-join-1'}
    first = client.post('/codes/consume', json={'code': event['event_code']}, headers=headers)
    second = client.post('/codes/consume', json={'code': event['event_code']}, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_codes_consume_staff_backup_one_time_then_stable():
    owner = _guest('owner')
    user = _guest('staffer')
    event = _create_event(owner)
    generated = client.post(
        f"/events/{event['event_id']}/staff_backup_codes/generate",
        json={'role': 'ENTRY', 'count': 1},
        headers={'Authorization': f'Bearer {owner}', 'Idempotency-Key': 'backup-gen-1'},
    )
    code = generated.json()['codes'][0]['code']
    first = client.post('/codes/consume', json={'code': f"{event['event_id']}:{code}"}, headers={'Authorization': f'Bearer {user}', 'Idempotency-Key': 'consume-backup-1'})
    second = client.post('/codes/consume', json={'code': f"{event['event_id']}:{code}"}, headers={'Authorization': f'Bearer {user}', 'Idempotency-Key': 'consume-backup-2'})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()['status'] in {'consumed', 'already-consumed'}
    assert second.json()['status'] in {'consumed', 'already-consumed'}


def test_codes_consume_orga_invite_already_member_stable_and_audit_suffix_only():
    owner = _guest('owner')
    user = _guest('member')
    org = client.post('/orgas', json={'name': 'Org2', 'visibility': 'PUBLIC'}, headers={'Authorization': f'Bearer {owner}', 'Idempotency-Key': 'orga-create-2'}).json()
    invite = client.post(f"/orgas/{org['orga']['id']}/invites", json={'inviteType': 'MEMBER'}, headers={'Authorization': f'Bearer {owner}', 'Idempotency-Key': 'orga-inv-2'}).json()['code']

    first = client.post('/codes/consume', json={'code': invite}, headers={'Authorization': f'Bearer {user}', 'Idempotency-Key': 'consume-orga-1'})
    second = client.post('/codes/consume', json={'code': invite}, headers={'Authorization': f'Bearer {user}', 'Idempotency-Key': 'consume-orga-2'})
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()['status'] in {'already-consumed', 'consumed'}

    with get_session() as session:
        logs = session.query(AuditLog).filter(AuditLog.action == 'code_consumed').all()
        assert logs
        payload = logs[-1].payload_json
        assert 'suffixHash' in payload
        assert payload.get('code') is None
