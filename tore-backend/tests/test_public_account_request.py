import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AccountRequest


def test_public_account_request_creates_row():
    Base.metadata.create_all(engine)
    client = TestClient(app)

    payload = {
        "name": "Alice Martin",
        "email": f"alice-{secrets.token_hex(4)}@example.com",
        "phone": "+32 495 12 34 56",
        "is_whatsapp": True,
        "role": "student",
        "committee_name": None,
        "source": "tore_site",
    }

    response = client.post("/public/account-request", json=payload, headers={"user-agent": "pytest"})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["message"] == "Account request created"

    s = get_session()
    try:
        row = s.get(AccountRequest, body["id"])
        assert row is not None
        assert row.email == payload["email"]
        assert row.role == "student"
    finally:
        s.close()


def test_public_account_request_rate_limit_shape(monkeypatch):
    Base.metadata.create_all(engine)
    monkeypatch.setenv("ACCOUNT_RATE_LIMIT_MAX", "1")
    monkeypatch.setenv("ACCOUNT_RATE_LIMIT_WINDOW", "10")
    client = TestClient(app)

    payload = {
        "name": "Alice Martin",
        "email": f"alice-limit-{secrets.token_hex(4)}@example.com",
        "phone": "+32495123456",
        "is_whatsapp": False,
        "role": "student",
        "source": "tore_site",
    }

    first = client.post("/public/account-request", json=payload, headers={"user-agent": "pytest-limit"})
    assert first.status_code == 200

    second = client.post("/public/account-request", json=payload, headers={"user-agent": "pytest-limit"})
    assert second.status_code == 429
    assert second.headers.get("Retry-After") is not None
    body = second.json().get("detail", {})
    assert body.get("detail") == "Too many requests"
    assert isinstance(body.get("retry_after_seconds"), int)
    assert body.get("retry_after_seconds") >= 1
    assert body.get("scope") in {"public_account_request", "public_account_request_email"}
