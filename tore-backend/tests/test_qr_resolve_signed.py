from __future__ import annotations

from datetime import datetime, timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, EventQrToken
from app.services.qr_signing_service import sign_payload


def _seed_event_and_guest():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    token = client.post('/auth/guest', json={'display_name': f'qr-{secrets.token_hex(2)}'}).json()['token']
    s = get_session()
    try:
        bar = Bar(name='QR Bar', city='Liege', partner_code=f'QR{secrets.token_hex(3)}')
        s.add(bar)
        s.flush()
        event = Event(
            bar_id=bar.id,
            name='QR Event',
            starts_at=datetime.utcnow().replace(microsecond=0) - timedelta(hours=1),
            ends_at=datetime.utcnow().replace(microsecond=0) + timedelta(hours=3),
        )
        s.add(event)
        s.commit()
        return client, token, event.id
    finally:
        s.close()


def _build_signed_qr(event_id: int, qr_type: str, *, token_id: str, expires_at: datetime, nonce: str = 'nonce-1', signature: str | None = None) -> tuple[str, str]:
    issued_at = (now_utc() - timedelta(minutes=1)).replace(microsecond=0)
    issued_at_iso = issued_at.isoformat() + 'Z'
    expires_at_iso = expires_at.replace(microsecond=0).isoformat() + 'Z'
    sig = signature or sign_payload(qr_type, event_id, issued_at_iso, expires_at_iso, token_id, nonce)
    raw = f'tore://{qr_type}?event_id={event_id}&issued_at={issued_at_iso}&expires_at={expires_at_iso}&token_id={token_id}&nonce={nonce}&sig={sig}'
    return raw, sig


def test_qr_resolve_signed_statuses_ok_expired_invalid_revoked():
    client, token, event_id = _seed_event_and_guest()

    s = get_session()
    try:
        token_ok = f'tok-ok-{secrets.token_hex(4)}'
        raw_ok, sig_ok = _build_signed_qr(event_id, 'join_event', token_id=token_ok, expires_at=now_utc() + timedelta(minutes=30))
        s.add(EventQrToken(event_id=event_id, qr_type='JOIN_EVENT', token_id=token_ok, nonce='nonce-1', payload=raw_ok, signature=sig_ok, issued_at=now_utc(), expires_at=now_utc() + timedelta(minutes=30)))

        token_expired = f'tok-expired-{secrets.token_hex(4)}'
        raw_expired, sig_expired = _build_signed_qr(event_id, 'entry_staff', token_id=token_expired, expires_at=now_utc() - timedelta(minutes=5), nonce='nonce-2')
        s.add(EventQrToken(event_id=event_id, qr_type='ENTRY_STAFF', token_id=token_expired, nonce='nonce-2', payload=raw_expired, signature=sig_expired, issued_at=now_utc() - timedelta(hours=1), expires_at=now_utc() - timedelta(minutes=5)))

        token_revoked = f'tok-revoked-{secrets.token_hex(4)}'
        raw_revoked, sig_revoked = _build_signed_qr(event_id, 'bar_staff', token_id=token_revoked, expires_at=now_utc() + timedelta(minutes=30), nonce='nonce-3')
        s.add(EventQrToken(event_id=event_id, qr_type='BAR_STAFF', token_id=token_revoked, nonce='nonce-3', payload=raw_revoked, signature=sig_revoked, issued_at=now_utc(), expires_at=now_utc() + timedelta(minutes=30), revoked_at=now_utc()))
        s.commit()
    finally:
        s.close()

    ok = client.post('/qr/resolve', json={'raw': raw_ok}, headers={'Authorization': f'Bearer {token}'})
    assert ok.status_code == 200
    assert ok.json()['valid'] is True

    expired = client.post('/qr/resolve', json={'raw': raw_expired}, headers={'Authorization': f'Bearer {token}'})
    assert expired.status_code == 200
    assert expired.json()['valid'] is False
    assert expired.json()['reason'] == 'expired'

    invalid_raw = raw_ok.replace('sig=', 'sig=broken')
    invalid = client.post('/qr/resolve', json={'raw': invalid_raw}, headers={'Authorization': f'Bearer {token}'})
    assert invalid.status_code == 200
    assert invalid.json()['valid'] is False
    assert invalid.json()['reason'] == 'invalid'

    revoked = client.post('/qr/resolve', json={'raw': raw_revoked}, headers={'Authorization': f'Bearer {token}'})
    assert revoked.status_code == 200
    assert revoked.json()['valid'] is False
    assert revoked.json()['reason'] == 'revoked'
