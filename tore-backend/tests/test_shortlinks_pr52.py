from sqlalchemy import text
from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog
from app.services import rate_limit_service

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    rate_limit_service._store.clear()


def _guest(name: str) -> str:
    return client.post('/auth/guest', json={'display_name': name}).json()['token']


def _create_event(token: str) -> int:
    res = client.post('/events', json={'name': 'PR52', 'starts_at': '2030-01-01T18:00:00Z', 'ends_at': '2030-01-01T23:00:00Z', 'visibility': 'PUBLIC'}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'evt-create'})
    return res.json()['event_id']


def test_shortlinks_create_is_idempotent():
    token = _guest('owner')
    event_id = _create_event(token)
    headers = {'Authorization': f'Bearer {token}', 'Idempotency-Key': 'short-idem'}
    payload = {'kind': 'event_share', 'event_id': event_id}
    first = client.post('/shortlinks', json=payload, headers=headers)
    second = client.post('/shortlinks', json=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()



def test_shortlinks_create_returns_fallback_open_url():
    token = _guest('owner-fallback')
    event_id = _create_event(token)
    created = client.post('/shortlinks', json={'kind': 'event_share', 'event_id': event_id}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'short-fallback'})
    assert created.status_code == 200
    body = created.json()
    assert body['fallbackOpenUrl'] == body['openUrl']
    assert body['fallbackOpenUrl'].startswith('http')
    assert '/open?' in body['fallbackOpenUrl']

def test_shortlinks_redirect_302_to_open():
    token = _guest('owner')
    event_id = _create_event(token)
    created = client.post('/shortlinks', json={'kind': 'event_share', 'event_id': event_id}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'short-302'})
    slug = created.json()['slug']
    resolved = client.get(f'/s/{slug}', follow_redirects=False)
    assert resolved.status_code == 302
    location = resolved.headers.get('location') or ''
    assert '/open?type=event&id=' in location
    assert '/s/' not in location


def test_shortlinks_expired_404():
    token = _guest('owner')
    event_id = _create_event(token)
    created = client.post('/shortlinks', json={'kind': 'event_share', 'event_id': event_id, 'expiresInSeconds': 1}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'short-exp'})
    slug = created.json()['slug']
    with get_session() as db:
        row = db.execute(text("SELECT slug FROM short_links WHERE slug = :slug"), {'slug': slug}).fetchone()
        assert row is not None
        db.execute(text("UPDATE short_links SET expires_at = datetime('now', '-2 hours') WHERE slug = :slug"), {'slug': slug})
        db.commit()
    resolved = client.get(f'/s/{slug}', follow_redirects=False)
    assert resolved.status_code == 404


def test_shortlinks_no_secret_leak():
    token = _guest('owner')
    event_id = _create_event(token)
    raw_secret = 'ABCD1234'
    created = client.post('/shortlinks', json={'kind': 'open_url', 'open_type': 'staff_backup', 'open_id': event_id, 'open_code': raw_secret}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'short-safe'})
    text = created.text
    assert raw_secret not in text
    with get_session() as db:
      logs = db.query(AuditLog).filter(AuditLog.action == 'shortlink_created').all()
      assert logs
      payload = str(logs[-1].payload_json)
      assert raw_secret not in payload


def test_shortlinks_rate_limit():
    token = _guest('owner')
    event_id = _create_event(token)
    old = rate_limit_service._SCOPE_LIMITS.get('shortlinks_create_user')
    rate_limit_service._SCOPE_LIMITS['shortlinks_create_user'] = (2, 60)
    try:
      ok1 = client.post('/shortlinks', json={'kind': 'event_share', 'event_id': event_id}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'sl-1'})
      ok2 = client.post('/shortlinks', json={'kind': 'event_share', 'event_id': event_id}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'sl-2'})
      limited = client.post('/shortlinks', json={'kind': 'event_share', 'event_id': event_id}, headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'sl-3'})
      assert ok1.status_code == 200
      assert ok2.status_code == 200
      assert limited.status_code == 429
    finally:
      if old is None:
        rate_limit_service._SCOPE_LIMITS.pop('shortlinks_create_user', None)
      else:
        rate_limit_service._SCOPE_LIMITS['shortlinks_create_user'] = old
