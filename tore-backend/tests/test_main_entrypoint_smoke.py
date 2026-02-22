from fastapi.testclient import TestClient

from main import app


def test_openapi_available():
    client = TestClient(app)
    resp = client.get('/openapi.json')
    assert resp.status_code == 200


def test_partner_portal_bar_requires_auth():
    client = TestClient(app)
    resp = client.get('/partner/portal/bar')
    assert resp.status_code == 401
