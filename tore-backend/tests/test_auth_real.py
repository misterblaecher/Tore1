from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text

from db import Base, engine, get_session, now_utc
from main import app, ensure_seed
import pytest
from models import AppUser, AuthOtpCode
from app.services import rate_limit_service



@pytest.fixture(autouse=True)
def _ensure_schema_ready():
    ensure_seed()
    yield


def test_google_auth_creates_user_and_returns_tokens(monkeypatch):
    client = TestClient(app)

    def fake_verify(_: str):
        return {"email": "google.user@example.com", "name": "Google User", "email_verified": True}

    monkeypatch.setattr("main._verify_google_id_token", fake_verify)
    res = client.post("/auth/google", json={"idToken": "fake-token"})
    assert res.status_code == 200
    data = res.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["user"]["email"] == "google.user@example.com"


def test_email_magic_link_request_verify_one_time_and_expiry(monkeypatch):
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setenv("TORE_DEV_EXPOSE_MAGIC_TOKEN", "1")
    client = TestClient(app)

    request_link = client.post("/auth/email/request_link", json={"email": "alice@example.com"})
    assert request_link.status_code == 200
    token = request_link.json().get("otp_debug") or request_link.json().get("code") or request_link.json().get("token")
    assert token

    verify_ok = client.post("/auth/email/verify_link", json={"email": "alice@example.com", "token": token})
    assert verify_ok.status_code == 200
    verify_data = verify_ok.json()
    assert verify_data["access_token"]
    assert verify_data["refresh_token"]

    reuse = client.post("/auth/email/verify_link", json={"email": "alice@example.com", "token": token})
    assert reuse.status_code == 400

    req2 = client.post("/auth/email/request_link", json={"email": "bob@example.com"})
    tok2 = req2.json().get("otp_debug") or req2.json().get("code") or req2.json()["token"]

    s = get_session()
    try:
        user = s.query(AppUser).filter(AppUser.email == "bob@example.com").first()
        if user is not None:
            s.delete(user)
            s.commit()
        link = s.query(AuthOtpCode).filter(AuthOtpCode.email == "bob@example.com").order_by(AuthOtpCode.id.desc()).first()
        assert link is not None
        link.expires_at = now_utc() - timedelta(minutes=1)
        s.add(link)
        s.commit()
    finally:
        s.close()

    expired = client.post("/auth/email/verify_link", json={"email": "bob@example.com", "token": tok2})
    assert expired.status_code == 400


def test_email_request_link_rate_limit(monkeypatch):
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setenv("TORE_DEV_EXPOSE_MAGIC_TOKEN", "1")
    rate_limit_service._SCOPE_LIMITS["auth_email_request_otp_email"] = (1, 60)

    client = TestClient(app)
    first = client.post("/auth/email/request_link", json={"email": "limit@example.com"})
    assert first.status_code == 200

    second = client.post("/auth/email/request_link", json={"email": "limit@example.com"})
    assert second.status_code == 429


def test_refresh_rotates_and_old_refresh_is_revoked(monkeypatch):
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setenv("TORE_DEV_EXPOSE_MAGIC_TOKEN", "1")
    client = TestClient(app)

    req = client.post("/auth/email/request_link", json={"email": "refresh@example.com"})
    verify = client.post(
        "/auth/email/verify_link",
        json={"email": "refresh@example.com", "token": req.json().get("otp_debug") or req.json().get("code") or req.json()["token"]},
    )
    assert verify.status_code == 200
    refresh_token = verify.json()["refresh_token"]

    refreshed = client.post("/auth/refresh", json={"refreshToken": refresh_token})
    assert refreshed.status_code == 200
    new_refresh = refreshed.json()["refresh_token"]
    assert new_refresh != refresh_token

    old_again = client.post("/auth/refresh", json={"refreshToken": refresh_token})
    assert old_again.status_code == 401


def test_magic_link_request_never_exposes_token_outside_dev(monkeypatch):
    monkeypatch.setenv("ENV", "PROD")
    monkeypatch.setenv("TORE_EMAIL_OTP_DEV_MODE", "0")
    monkeypatch.setenv("EMAIL_PROVIDER_API_KEY", "provider-key")
    client = TestClient(app)

    res = client.post("/auth/email/request_link", json={"email": "safe@example.com"})
    assert res.status_code == 200
    assert "token" not in res.json()
    assert "otp_debug" not in res.json()


def test_upgrade_guest_endpoint_acknowledges_device_id():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    guest = client.post("/auth/guest", json={"display_name": "Guest Upgrade"})
    assert guest.status_code == 200
    token = guest.json()["token"]

    up = client.post(
        "/auth/upgrade_guest",
        headers={"Authorization": f"Bearer {token}"},
        json={"guest_device_id": "11111111-1111-1111-1111-111111111111", "merge_policy": "keep"},
    )
    assert up.status_code == 200
    assert up.json()["ok"] is True




def test_auth_me_guest_returns_json_and_200():
    client = TestClient(app)
    guest = client.post("/auth/guest", json={"display_name": "Guest Me"})
    assert guest.status_code == 200
    token = guest.json()["token"]

    me = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200
    assert me.headers.get('content-type', '').startswith('application/json')
    body = me.json()
    assert body['id']
    assert 'account_mode' in body


def test_auth_me_fallbacks_when_role_upgrade_requests_table_missing():
    client = TestClient(app)
    guest = client.post('/auth/guest', json={'display_name': 'Guest Missing Table'})
    assert guest.status_code == 200
    token = guest.json()['token']

    s = get_session()
    try:
        s.execute(text('DROP TABLE IF EXISTS role_upgrade_requests'))
        s.commit()
    finally:
        s.close()

    me = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200
    assert me.headers.get('content-type', '').startswith('application/json')
    assert me.json()['role_request_pending'] is None


def test_internal_server_error_uses_json_handler(monkeypatch):
    client = TestClient(app, raise_server_exceptions=False)

    def explode(*_args, **_kwargs):
        raise RuntimeError('boom')

    monkeypatch.setattr('main._issue_auth_tokens', explode)

    res = client.post('/auth/guest', json={'display_name': 'Guest Error'})
    assert res.status_code == 500
    assert res.headers.get('content-type', '').startswith('application/json')
    payload = res.json()
    assert payload['detail'] == 'Internal Server Error'
    assert payload['code'] == 'internal_error'
    assert 'request_id' in payload

def test_refresh_rejects_deleted_user(monkeypatch):
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setenv("TORE_DEV_EXPOSE_MAGIC_TOKEN", "1")
    client = TestClient(app)

    email = f"deleted-{now_utc().timestamp()}@example.com"
    req = client.post("/auth/email/request_link", json={"email": email})
    verify = client.post(
        "/auth/email/verify_link",
        json={"email": email, "token": req.json().get("otp_debug") or req.json().get("code") or req.json()["token"]},
    )
    assert verify.status_code == 200
    refresh_token = verify.json()["refresh_token"]

    s = get_session()
    try:
        user = s.query(AppUser).filter(AppUser.email == email).first()
        assert user is not None
        user.is_deleted = True
        user.deleted_at = now_utc()
        s.add(user)
        s.commit()
    finally:
        s.close()

    blocked = client.post("/auth/refresh", json={"refreshToken": refresh_token})
    assert blocked.status_code == 403




def test_email_otp_and_welcome_only_on_first_account_creation(monkeypatch):
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setenv("TORE_DEV_EXPOSE_MAGIC_TOKEN", "1")
    rate_limit_service._SCOPE_LIMITS["auth_email_request_otp_email"] = (10, 60)
    sent = []

    def fake_send_email(subject: str, body: str, to_email: str):
        sent.append({"subject": subject, "to": to_email, "body": body})

    monkeypatch.setattr("main._send_email", fake_send_email)
    client = TestClient(app)

    email = f"otp-welcome-{now_utc().timestamp()}@example.com"
    req1 = client.post("/auth/email/request_otp", json={"email": email})
    assert req1.status_code == 200
    code1 = req1.json().get("otp_debug") or req1.json().get("code")
    assert code1 and len(code1) == 6

    verify1 = client.post("/auth/email/verify_otp", json={"email": email, "code": code1})
    assert verify1.status_code == 200
    assert verify1.json()["created"] is True

    req2 = client.post("/auth/email/request_otp", json={"email": email})
    assert req2.status_code == 200
    code2 = req2.json().get("otp_debug") or req2.json().get("code")
    verify2 = client.post("/auth/email/verify_otp", json={"email": email, "code": code2})
    assert verify2.status_code == 200
    assert verify2.json()["created"] is False

    welcome_count = len([m for m in sent if m["subject"] == "Bienvenue dans TORÈ 🐂"])
    assert welcome_count == 1


def test_verify_otp_counts_attempts_and_blocks_after_limit(monkeypatch):
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setenv("TORE_DEV_EXPOSE_MAGIC_TOKEN", "1")
    client = TestClient(app)

    req = client.post("/auth/email/request_otp", json={"email": "attempts@example.com"})
    assert req.status_code == 200

    for _ in range(5):
        bad = client.post("/auth/email/verify_otp", json={"email": "attempts@example.com", "code": "000000"})
        assert bad.status_code == 400

    blocked = client.post("/auth/email/verify_otp", json={"email": "attempts@example.com", "code": "111111"})
    assert blocked.status_code == 429


def test_email_request_otp_dev_dry_run_when_smtp_fails(monkeypatch):
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setenv("TORE_DEV_EXPOSE_MAGIC_TOKEN", "1")
    monkeypatch.setenv("SMTP_HOST", "smtp.invalid.local")

    def fake_smtp(*args, **kwargs):
        raise OSError("smtp down")

    monkeypatch.setattr("main.smtplib.SMTP", fake_smtp)

    client = TestClient(app)
    email = f"otp-dry-{now_utc().timestamp()}@example.com"
    res = client.post("/auth/email/request_otp", json={"email": email})

    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert len((res.json().get("otp_debug") or res.json().get("code") or "")) == 6


def test_email_request_otp_rate_limit_returns_retry_after_header(monkeypatch):
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setenv("TORE_DEV_EXPOSE_MAGIC_TOKEN", "1")
    rate_limit_service._SCOPE_LIMITS["auth_email_request_otp_email"] = (1, 60)
    rate_limit_service._SCOPE_LIMITS["auth_email_request_otp_ip"] = (100, 60)

    client = TestClient(app)
    email = f"otp-limit-{now_utc().timestamp()}@example.com"

    first = client.post("/auth/email/request_otp", json={"email": email})
    assert first.status_code == 200

    second = client.post("/auth/email/request_otp", json={"email": email})
    assert second.status_code == 429
    assert second.headers.get("Retry-After") is not None
    body = second.json().get("detail", {})
    assert body.get("detail") == "Too many requests"
    assert isinstance(body.get("retry_after_seconds"), int)
    assert body.get("retry_after_seconds") >= 1
    assert body.get("scope") == "auth_email_request_otp_email"


def test_email_request_otp_invalid_email_returns_400():
    client = TestClient(app)
    res = client.post("/auth/email/request_otp", json={"email": "not-an-email"})
    assert res.status_code == 400
    assert res.json()["detail"]["reason"] == "invalid_email"


def test_email_verify_otp_rejects_reuse(monkeypatch):
    monkeypatch.setenv("ENV", "DEV")
    monkeypatch.setenv("TORE_EMAIL_OTP_DEV_MODE", "1")
    client = TestClient(app)
    email = f"reuse-{now_utc().timestamp()}@example.com"

    req = client.post("/auth/email/request_otp", json={"email": email})
    code = req.json().get("otp_debug")
    assert code

    ok = client.post("/auth/email/verify_otp", json={"email": email, "code": code})
    assert ok.status_code == 200
    again = client.post("/auth/email/verify_otp", json={"email": email, "code": code})
    assert again.status_code == 400
    assert again.json()["detail"]["reason"] == "already_used"
