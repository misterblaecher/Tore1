from datetime import timedelta
import hashlib

from fastapi.testclient import TestClient

from db import get_session, now_utc
from main import ACCESS_TOKEN_TTL_MIN, app
from models import AppToken


WEB_HEADERS = {"Origin": "http://localhost:5173", "X-TORE-Web": "1"}


def _register(client: TestClient, prefix: str):
    email = f"{prefix}-{now_utc().timestamp()}@example.com"
    return client.post(
        "/auth/web/password/register",
        headers=WEB_HEADERS,
        json={"email": email, "password": "secret12", "first_name": "Web", "last_name": "User", "nickname": ""},
    )


def test_web_login_never_returns_refresh_token_and_sets_httponly_cookie():
    client = TestClient(app)
    registered = _register(client, "web")
    assert registered.status_code == 200, registered.text
    assert registered.json()["access_token"]
    assert "refresh_token" not in registered.json()
    cookie = registered.headers.get("set-cookie", "")
    assert "tore_web_refresh=" in cookie
    assert "HttpOnly" in cookie
    assert client.cookies.get("tore_web_refresh")


def test_web_refresh_rotates_cookie_and_logout_revokes_session():
    client = TestClient(app)
    registered = _register(client, "rotate")
    first_cookie = client.cookies.get("tore_web_refresh")
    access = registered.json()["access_token"]

    refreshed = client.post("/auth/web/refresh", headers=WEB_HEADERS)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["access_token"]
    assert "refresh_token" not in refreshed.json()
    assert client.cookies.get("tore_web_refresh") != first_cookie

    logged_out = client.post(
        "/auth/web/logout",
        headers={**WEB_HEADERS, "Authorization": f"Bearer {access}"},
    )
    assert logged_out.status_code == 204
    blocked = client.post("/auth/web/refresh", headers=WEB_HEADERS)
    assert blocked.status_code == 401


def test_web_refresh_requires_non_simple_web_header():
    client = TestClient(app)
    blocked = client.post("/auth/web/refresh", headers={"Origin": "http://localhost:5173"})
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["reason"] == "web_request_required"


def test_web_auth_rejects_unapproved_origin():
    client = TestClient(app)
    blocked = client.post(
        "/auth/web/password/login",
        headers={"Origin": "https://attacker.example", "X-TORE-Web": "1"},
        json={"email": "nobody@example.com", "password": "secret12"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["reason"] == "origin_forbidden"


def test_prod_refresh_cookie_is_secure_and_samesite_none(monkeypatch):
    monkeypatch.setenv("TORE_ENV", "PROD")
    monkeypatch.setenv("TORE_CORS_ORIGINS", "https://site.example.test")
    client = TestClient(app, base_url="https://api.example.test")
    email = f"secure-{now_utc().timestamp()}@example.com"
    response = client.post(
        "/auth/web/password/register",
        headers={"Origin": "https://site.example.test", "X-TORE-Web": "1"},
        json={"email": email, "password": "secret12", "first_name": "Secure", "last_name": "User", "nickname": ""},
    )
    assert response.status_code == 200, response.text
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=none" in cookie


def test_access_token_expires_server_side():
    client = TestClient(app)
    response = _register(client, "expiry")
    access = response.json()["access_token"]
    digest = hashlib.sha256(access.encode("utf-8")).hexdigest()
    with get_session() as db:
        row = db.query(AppToken).filter(AppToken.token_hash == digest).one()
        row.created_at = now_utc() - timedelta(minutes=ACCESS_TOKEN_TTL_MIN + 1)
        db.commit()

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 401
    assert me.json()["detail"]["reason"] == "access_token_expired"


def test_expired_access_token_is_rejected_by_shared_resolver():
    client = TestClient(app)
    response = _register(client, "shared-expiry")
    access = response.json()["access_token"]
    digest = hashlib.sha256(access.encode("utf-8")).hexdigest()
    with get_session() as db:
        row = db.query(AppToken).filter(AppToken.token_hash == digest).one()
        row.created_at = now_utc() - timedelta(minutes=ACCESS_TOKEN_TTL_MIN + 1)
        db.commit()

    from app.legacy.monolith import _resolve_app_user_from_token
    with get_session() as db:
        assert _resolve_app_user_from_token(access, db) is None
        row = db.query(AppToken).filter(AppToken.token_hash == digest).one()
        assert row.revoked_at is not None
