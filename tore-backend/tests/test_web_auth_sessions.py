from __future__ import annotations

from fastapi.testclient import TestClient

from db import Base, engine
from main import app


ALLOWED_ORIGIN = "http://localhost:8080"
WEB_HEADERS = {"Origin": ALLOWED_ORIGIN, "Sec-Fetch-Site": "same-site"}


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _register(client: TestClient, *, email: str = "web-session@example.com"):
    return client.post(
        "/auth/web/password/register",
        headers=WEB_HEADERS,
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "first_name": "Web",
            "last_name": "Session",
            "nickname": "web-session",
        },
    )


def test_web_login_keeps_refresh_token_out_of_json_and_in_httponly_cookie(monkeypatch):
    monkeypatch.setenv("ENV", "DEV")
    client = TestClient(app)

    response = _register(client)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["access_token"]
    assert "refresh_token" not in payload
    assert "refreshToken" not in payload

    cookie = response.headers["set-cookie"]
    assert "tore_web_refresh=" in cookie
    assert "HttpOnly" in cookie
    assert "Path=/auth/web" in cookie
    assert "SameSite=lax" in cookie


def test_web_refresh_rotates_cookie_and_logout_revokes_refresh_and_access(monkeypatch):
    monkeypatch.setenv("ENV", "DEV")
    client = TestClient(app)

    registered = _register(client, email="rotate-web@example.com")
    assert registered.status_code == 200, registered.text
    access = registered.json()["access_token"]
    first_refresh = client.cookies.get("tore_web_refresh")
    assert first_refresh

    refreshed = client.post("/auth/web/refresh", headers=WEB_HEADERS)
    assert refreshed.status_code == 200, refreshed.text
    second_access = refreshed.json()["access_token"]
    second_refresh = client.cookies.get("tore_web_refresh")
    assert second_refresh and second_refresh != first_refresh
    assert "refresh_token" not in refreshed.json()

    old_refresh = client.post("/auth/refresh", json={"refreshToken": first_refresh})
    assert old_refresh.status_code == 401

    logout = client.post(
        "/auth/web/logout",
        headers={**WEB_HEADERS, "Authorization": f"Bearer {second_access}"},
    )
    assert logout.status_code == 200
    assert logout.json() == {"ok": True}

    revoked_access = client.get("/auth/me", headers={"Authorization": f"Bearer {second_access}"})
    assert revoked_access.status_code == 401

    revoked_refresh = client.post("/auth/refresh", json={"refreshToken": second_refresh})
    assert revoked_refresh.status_code == 401

    # The earlier access token was not persisted by the browser and remains
    # independent from the currently revoked web session.
    assert access != second_access


def test_web_auth_rejects_untrusted_browser_origin(monkeypatch):
    monkeypatch.setenv("ENV", "DEV")
    client = TestClient(app)

    response = client.post(
        "/auth/web/password/login",
        headers={"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site"},
        json={"email": "nobody@example.com", "password": "password123"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "web_origin_forbidden"


def test_prod_cookie_is_secure_and_same_site_none(monkeypatch):
    monkeypatch.setenv("ENV", "PROD")
    monkeypatch.setenv("TORE_CORS_ORIGINS", "https://tore.example")
    client = TestClient(app, base_url="https://api.tore.example")

    response = client.post(
        "/auth/web/password/register",
        headers={"Origin": "https://tore.example", "Sec-Fetch-Site": "cross-site"},
        json={
            "email": "prod-web@example.com",
            "password": "correct-horse-battery-staple",
            "first_name": "Prod",
            "last_name": "Web",
            "nickname": "prod-web",
        },
    )
    assert response.status_code == 200, response.text
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=none" in cookie


def test_cors_credentials_are_limited_to_explicit_origin(monkeypatch):
    monkeypatch.setenv("ENV", "DEV")
    client = TestClient(app)

    allowed = client.options(
        "/auth/web/refresh",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert allowed.headers["access-control-allow-credentials"] == "true"

    denied = client.options(
        "/auth/web/refresh",
        headers={
            "Origin": "https://random-preview.onrender.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
