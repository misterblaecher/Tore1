import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import Bar


def _signup_payload(suffix: str) -> dict:
    return {
        "bar_name": f"Signup Bar {suffix}",
        "city": "Test City",
        "manager_name": f"Manager {suffix}",
        "pin": "1234",
    }


def test_manager_signup_returns_partner_code():
    Base.metadata.create_all(engine)
    client = TestClient(app)

    suffix = secrets.token_hex(4)
    res = client.post("/partner/auth/manager/signup", json=_signup_payload(suffix))
    assert res.status_code == 200
    payload = res.json()
    assert payload["bar_id"]
    assert payload["token"]
    assert payload["role"] == "manager"
    assert payload["display_name"] == f"Manager {suffix}"

    s = get_session()
    try:
        bar = s.get(Bar, payload["bar_id"])
        assert bar is not None
        assert bar.partner_code
        assert bar.partner_code.startswith("BAR-")
    finally:
        s.close()


def test_partner_code_unique_for_signups():
    Base.metadata.create_all(engine)
    client = TestClient(app)

    suffix_a = secrets.token_hex(4)
    suffix_b = secrets.token_hex(4)

    res_a = client.post("/partner/auth/manager/signup", json=_signup_payload(suffix_a))
    res_b = client.post("/partner/auth/manager/signup", json=_signup_payload(suffix_b))

    assert res_a.status_code == 200
    assert res_b.status_code == 200

    s = get_session()
    try:
        bar_a = s.get(Bar, res_a.json()["bar_id"])
        bar_b = s.get(Bar, res_b.json()["bar_id"])
        assert bar_a.partner_code != bar_b.partner_code
    finally:
        s.close()