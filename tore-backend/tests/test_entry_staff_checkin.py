from datetime import timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AppUser, Bar, Event, EventConfig, EventStaff


def _seed():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
      bar = Bar(name='Entry', city='Liege', partner_code=f'ENT-{secrets.token_hex(4)}')
      s.add(bar)
      s.flush()
      event = Event(bar_id=bar.id, name='Rush', starts_at=now_utc() - timedelta(hours=1), ends_at=now_utc() + timedelta(hours=5), event_state='LIVE')
      s.add(event)
      s.flush()
      s.add(EventConfig(event_id=event.id, entry_enabled=True))
      staff = AppUser(id=f'staff-{secrets.token_hex(4)}', display_name='Staff')
      s.add(staff)
      s.flush()
      s.add(EventStaff(event_id=event.id, user_id=staff.id, role='entry', is_active=True))
      s.commit()
      return event.id
    finally:
      s.close()


def _staff_token(client: TestClient) -> str:
    resp = client.post('/auth/guest', json={'display_name': 'entry-staff'})
    assert resp.status_code == 200
    return resp.json()['token'], resp.json()['user']['id']


def test_entry_checkin_accepts_and_increments_count():
    event_id = _seed()
    client = TestClient(app)
    token, user_id = _staff_token(client)
    s = get_session()
    try:
      s.add(EventStaff(event_id=event_id, user_id=user_id, role='entry', is_active=True))
      s.commit()
    finally:
      s.close()

    res = client.post(
        f'/events/{event_id}/entry/checkin',
        json={'ticket_qr_raw': 'QR-1', 'scanned_at': now_utc().isoformat(), 'device_id': 'dev-1'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'idem-1'},
    )
    assert res.status_code == 200
    assert res.json()['status'] == 'accepted'

    count = client.get(f'/events/{event_id}/entry/count', headers={'Authorization': f'Bearer {token}'})
    assert count.status_code == 200
    assert count.json()['entryCount'] == 1


def test_entry_checkin_is_idempotent_on_retry():
    event_id = _seed()
    client = TestClient(app)
    token, user_id = _staff_token(client)
    s = get_session()
    try:
      s.add(EventStaff(event_id=event_id, user_id=user_id, role='entry', is_active=True))
      s.commit()
    finally:
      s.close()

    payload = {'ticket_qr_raw': 'QR-2', 'scanned_at': now_utc().isoformat(), 'device_id': 'dev-2'}
    one = client.post(f'/events/{event_id}/entry/checkin', json=payload, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'idem-r'})
    two = client.post(f'/events/{event_id}/entry/checkin', json=payload, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'idem-r'})

    assert one.status_code == 200
    assert two.status_code == 200
    assert one.json()['entryCount'] == two.json()['entryCount'] == 1


def test_entry_checkin_already_checked_is_stable():
    event_id = _seed()
    client = TestClient(app)
    token, user_id = _staff_token(client)
    s = get_session()
    try:
      s.add(EventStaff(event_id=event_id, user_id=user_id, role='entry', is_active=True))
      s.commit()
    finally:
      s.close()

    first = client.post(
        f'/events/{event_id}/entry/checkin',
        json={'ticket_qr_raw': 'QR-3', 'scanned_at': now_utc().isoformat(), 'device_id': 'dev-3'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'idem-a'},
    )
    second = client.post(
        f'/events/{event_id}/entry/checkin',
        json={'ticket_qr_raw': 'QR-3', 'scanned_at': now_utc().isoformat(), 'device_id': 'dev-3'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'idem-b'},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()['status'] == 'already_checked'
    assert second.json()['entryCount'] == 1
