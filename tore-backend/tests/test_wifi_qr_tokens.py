from __future__ import annotations

from datetime import datetime, timedelta
import secrets

from fastapi.testclient import TestClient

from app.services.qr_signing_service import sign_payload
from db import Base, engine, get_session, now_utc
from main import app
from models import AuditLog, Bar, Event, EventModuleConfig, EventWifiSettings, EventWifiToken, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager_event(*, wifi_enabled: bool = True):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name='Wifi Bar', city='Liege', partner_code=f'WIF{suffix}')
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name='Manager Wifi', pin_hash='hash')
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role='manager', display_name='Manager Wifi'))
        event = Event(
            bar_id=bar.id,
            name='Wifi Event',
            starts_at=datetime.utcnow().replace(microsecond=0) - timedelta(hours=1),
            ends_at=datetime.utcnow().replace(microsecond=0) + timedelta(hours=4),
        )
        s.add(event)
        s.flush()
        s.add(EventModuleConfig(event_id=event.id, wifi_enabled=wifi_enabled, entry_enabled=True, orders_enabled=True))
        s.add(EventWifiSettings(event_id=event.id, enabled=wifi_enabled, ssid='TORE_WIFI', password='super-secret', instructions='ask orga if blocked'))
        s.commit()
        return _make_token(user.id, bar.id, 'manager', 'Manager Wifi'), event.id
    finally:
        s.close()


def _guest(client: TestClient) -> str:
    return client.post('/auth/guest', json={'display_name': f'wifi-{secrets.token_hex(2)}'}).json()['token']


def test_module_off_behavior_on_resolve_and_claim():
    manager_token, event_id = _seed_manager_event(wifi_enabled=False)
    client = TestClient(app)
    guest = _guest(client)

    create = client.post(
        f'/partner/portal/orga/events/{event_id}/wifi/tokens',
        json={'ttlSeconds': 1800},
        headers={'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'wifi-off-token'},
    )
    assert create.status_code == 404
    assert create.json()['detail']['reason'] == 'module_off'

    claim = client.get(f'/events/{event_id}/wifi/claim', params={'token': 'invalid-token'})
    assert claim.status_code == 404
    assert claim.json()['detail']['reason'] == 'module_off'

    raw = f'tore://qr?type=wifi_token&event_id={event_id}&token=abc&token_id=tok&issued_at=2026-01-01T00:00:00Z&expires_at=2030-01-01T00:00:00Z&nonce=n&sig=x'
    resolved = client.post('/qr/resolve', json={'raw': raw}, headers={'Authorization': f'Bearer {guest}'})
    assert resolved.status_code == 200
    assert resolved.json()['valid'] is False
    assert resolved.json()['reason'] == 'module_off'


def test_create_token_idempotent_claim_ok_expired_revoked_and_signed_enforced():
    manager_token, event_id = _seed_manager_event(wifi_enabled=True)
    client = TestClient(app)
    guest = _guest(client)

    headers = {'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'wifi-create-1'}
    first = client.post(f'/partner/portal/orga/events/{event_id}/wifi/tokens', json={'ttlSeconds': 600}, headers=headers)
    second = client.post(f'/partner/portal/orga/events/{event_id}/wifi/tokens', json={'ttlSeconds': 600}, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()['tokenId'] == second.json()['tokenId']

    token = first.json()['token']
    token_id = first.json()['tokenId']
    claim_ok = client.get(f'/events/{event_id}/wifi/claim', params={'token': token})
    assert claim_ok.status_code == 200
    assert claim_ok.json()['ssid'] == 'TORE_WIFI'
    assert claim_ok.json()['password'] == 'super-secret'

    issued_at = (now_utc() - timedelta(minutes=1)).replace(microsecond=0)
    issued_at_iso = issued_at.isoformat() + 'Z'
    expires_at = (now_utc() + timedelta(minutes=10)).replace(microsecond=0)
    expires_at_iso = expires_at.isoformat() + 'Z'
    nonce = 'wifi-nonce'
    sig = sign_payload('wifi_token', event_id, issued_at_iso, expires_at_iso, token_id, nonce)
    raw_signed = f'tore://qr?type=wifi_token&event_id={event_id}&token_id={token_id}&token={token}&issued_at={issued_at_iso}&expires_at={expires_at_iso}&nonce={nonce}&sig={sig}'

    ok_resolve = client.post('/qr/resolve', json={'raw': raw_signed}, headers={'Authorization': f'Bearer {guest}'})
    assert ok_resolve.status_code == 200
    assert ok_resolve.json()['valid'] is True

    invalid_sig = client.post('/qr/resolve', json={'raw': raw_signed.replace('sig=', 'sig=bad')}, headers={'Authorization': f'Bearer {guest}'})
    assert invalid_sig.status_code == 200
    assert invalid_sig.json()['valid'] is False
    assert invalid_sig.json()['reason'] == 'invalid'

    revoke = client.post(
        f'/partner/portal/orga/events/{event_id}/wifi/tokens/{token_id}/revoke',
        json={'reason': 'rotation'},
        headers={'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'wifi-revoke-1'},
    )
    assert revoke.status_code == 200

    revoked_claim = client.get(f'/events/{event_id}/wifi/claim', params={'token': token})
    assert revoked_claim.status_code == 403
    assert revoked_claim.json()['detail']['reason'] == 'revoked'

    s = get_session()
    try:
        # force an expired token then claim should fail as expired
        token_resp = client.post(
            f'/partner/portal/orga/events/{event_id}/wifi/tokens',
            json={'ttlSeconds': 300},
            headers={'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'wifi-create-2'},
        )
        tok2 = token_resp.json()['token']
        tok2id = token_resp.json()['tokenId']
        row = s.query(EventWifiToken).filter_by(token_id=tok2id).first()
        row.expires_at = now_utc() - timedelta(seconds=1)
        s.add(row)
        s.commit()
    finally:
        s.close()

    expired_claim = client.get(f'/events/{event_id}/wifi/claim', params={'token': tok2})
    assert expired_claim.status_code == 403
    assert expired_claim.json()['detail']['reason'] == 'expired'


def test_audit_logs_without_password_or_raw_token_leakage():
    manager_token, event_id = _seed_manager_event(wifi_enabled=True)
    client = TestClient(app)

    put = client.put(
        f'/partner/portal/orga/events/{event_id}/wifi',
        json={'enabled': True, 'ssid': 'MY_WIFI', 'password': 'VERY-SECRET', 'instructions': 'welcome'},
        headers={'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'wifi-put-1'},
    )
    assert put.status_code == 200

    created = client.post(
        f'/partner/portal/orga/events/{event_id}/wifi/tokens',
        json={'ttlSeconds': 1200},
        headers={'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'wifi-token-audit'},
    )
    assert created.status_code == 200

    raw_token = created.json()['token']

    s = get_session()
    try:
        audits = s.query(AuditLog).filter(AuditLog.event_id == event_id, AuditLog.action.like('orga.wifi.%')).all()
        assert audits
        audit_blob = ' '.join(str(item.payload_json or '') for item in audits)
        assert 'VERY-SECRET' not in audit_blob
        assert raw_token not in audit_blob
    finally:
        s.close()
