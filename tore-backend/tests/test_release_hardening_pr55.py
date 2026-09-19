import pytest
from fastapi.testclient import TestClient

from db import Base, engine
from main import app, _resolved_env_name, validate_env_or_warn

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_debug_health_ui_dev_returns_safe_payload(monkeypatch):
    monkeypatch.setenv('ENV', 'DEV')
    monkeypatch.setenv('TORE_QR_SIGNING_KEYS', 'dev_key_1234567890,dev_key_rotation_1234567890')
    response = client.get('/debug/health-ui')
    assert response.status_code == 200
    payload = response.json()
    assert payload['env'] == 'DEV'
    assert payload['serverTime']
    assert isinstance(payload['signingKeyIds'], list)
    assert 'modulesFlagsCount' in payload
    assert 'flagsEnabled' in payload
    assert payload['routesEnabled']['open'] is True
    assert payload['routesEnabled']['shortlinks'] is True
    assert payload['routesEnabled']['codes_preview'] is True
    assert payload['routesEnabled']['codes_consume'] is True


def test_debug_health_ui_prod_is_404(monkeypatch):
    monkeypatch.setenv('ENV', 'PROD')
    response = client.get('/debug/health-ui')
    assert response.status_code == 404


def test_validate_env_or_warn_fails_fast_in_prod(monkeypatch):
    monkeypatch.setenv('ENV', 'PROD')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('PUBLIC_URL', raising=False)
    monkeypatch.delenv('BASE_URL', raising=False)
    monkeypatch.delenv('TORE_QR_SIGNING_KEYS', raising=False)
    monkeypatch.delenv('CORS_ORIGINS', raising=False)
    monkeypatch.delenv('TORE_CORS_ORIGINS', raising=False)
    with pytest.raises(RuntimeError):
        validate_env_or_warn()


def test_app_env_prod_alias_enables_prod_hardening(monkeypatch):
    monkeypatch.delenv('TORE_ENV', raising=False)
    monkeypatch.delenv('ENV', raising=False)
    monkeypatch.setenv('APP_ENV', 'prod')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('PUBLIC_URL', raising=False)
    monkeypatch.delenv('BASE_URL', raising=False)
    monkeypatch.delenv('TORE_QR_SIGNING_KEYS', raising=False)
    monkeypatch.delenv('TORE_CORS_ORIGINS', raising=False)

    assert _resolved_env_name() == 'PROD'
    with pytest.raises(RuntimeError):
        validate_env_or_warn()
