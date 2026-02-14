from fastapi.testclient import TestClient

from main import app


def test_p3_smoke_health_and_routes_exist():
    client = TestClient(app)
    assert client.get('/health').status_code == 200
    # unauthenticated protected endpoints
    assert client.post('/battles/create', json={}).status_code in {401, 403, 422}
    assert client.post('/drinks/checkin', json={'free_text_name': 'X'}).status_code == 401
