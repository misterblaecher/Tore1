"""P1 regression tests: bounded and atomic partner onboarding."""
import secrets

from fastapi.testclient import TestClient

import partner_auth
from app.services import rate_limit_service
from db import Base, engine, get_session
from main import app
from models import Bar, PartnerInvite, PartnerUser


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _payload(label):
    return {"bar_name": "Audit Bar " + label, "city": "Liège",
            "manager_name": "Manager " + label, "pin": "1234"}


def test_manager_signup_is_one_transaction(monkeypatch):
    client = TestClient(app)
    session = get_session()
    try:
        before = (session.query(Bar).count(), session.query(PartnerUser).count())
    finally:
        session.close()

    def break_membership(**_kwargs):
        raise RuntimeError("simulated internal membership failure")

    monkeypatch.setattr(partner_auth, "PartnerMembership", break_membership)
    response = client.post("/partner/auth/manager/signup", json=_payload(secrets.token_hex(4)))
    assert response.status_code == 500
    assert response.json()["detail"]["reason"] == "partner_signup_failed"
    assert "simulated" not in response.text

    session = get_session()
    try:
        assert (session.query(Bar).count(), session.query(PartnerUser).count()) == before
    finally:
        session.close()


def test_manager_signup_rate_limit():
    rate_limit_service._SCOPE_LIMITS["partner_manager_signup_ip"] = (1, 3600)
    client = TestClient(app)
    first = client.post("/partner/auth/manager/signup", json=_payload(secrets.token_hex(4)))
    second = client.post("/partner/auth/manager/signup", json=_payload(secrets.token_hex(4)))
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers.get("retry-after")


def test_staff_join_rolls_back_user_and_invite(monkeypatch):
    client = TestClient(app)
    signup = client.post("/partner/auth/manager/signup", json=_payload(secrets.token_hex(4)))
    assert signup.status_code == 200
    bar_id = signup.json()["bar_id"]
    db = get_session()
    try:
        db.add(PartnerInvite(bar_id=bar_id, code="AUDITCODE", role="bartender", max_uses=1, uses_count=0))
        db.commit()
        before_users = db.query(PartnerUser).count()
    finally:
        db.close()

    def break_membership(**_kwargs):
        raise RuntimeError("simulated membership failure")

    monkeypatch.setattr(partner_auth, "PartnerMembership", break_membership)
    response = client.post("/partner/auth/staff/join", json={
        "invite_code": "AUDITCODE", "display_name": "Staff Test", "pin": "1234",
    })
    assert response.status_code == 500
    assert response.json()["detail"]["reason"] == "staff_join_failed"
    db = get_session()
    try:
        assert db.query(PartnerUser).count() == before_users
        assert db.query(PartnerInvite).filter_by(code="AUDITCODE").one().uses_count == 0
    finally:
        db.close()


def test_staff_join_invite_code_rate_limit():
    client = TestClient(app)
    rate_limit_service._SCOPE_LIMITS["partner_staff_join_code"] = (1, 300)
    data = {"invite_code": "UNKNOWN1", "display_name": "Staff Test", "pin": "1234"}
    assert client.post("/partner/auth/staff/join", json=data).status_code == 400
    response = client.post("/partner/auth/staff/join", json=data)
    assert response.status_code == 429
