from fastapi.testclient import TestClient

from db import Base, engine
from main import app


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _guest(name: str) -> tuple[str, str]:
    response = client.post("/auth/guest", json={"display_name": name})
    assert response.status_code == 200
    token = response.json()["token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    return token, me.json()["id"]


def _headers(token: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


def test_accounting_is_separate_and_treasury_protected():
    owner_token, _ = _guest("accounting-owner")
    member_token, _ = _guest("accounting-member")
    outsider_token, _ = _guest("accounting-outsider")
    created = client.post(
        "/orgas",
        json={"name": "Compta Forum", "org_type": "COMMITTEE"},
        headers=_headers(owner_token, "accounting-org"),
    )
    assert created.status_code == 200
    org_id = created.json()["orga"]["id"]
    slug = created.json()["orga"]["slug"]
    assert client.post(f"/orgas/{org_id}/join", headers=_headers(member_token, "accounting-join")).status_code == 200

    owner = client.get(f"/forum/structures/{slug}/accounting-summary", headers=_headers(owner_token))
    assert owner.status_code == 200
    assert owner.json()["privateByDefault"] is True
    assert owner.json()["history"] == []

    assert client.get(f"/forum/structures/{slug}/accounting-summary", headers=_headers(member_token)).status_code == 403
    assert client.get(f"/forum/structures/{slug}/accounting-summary", headers=_headers(outsider_token)).status_code == 403
