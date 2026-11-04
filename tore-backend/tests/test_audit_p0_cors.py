"""P0 regression tests: explicit production CORS and runtime profile."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import _cors_origins as core_cors_origins
from app.legacy.monolith import _cors_origins as legacy_cors_origins
from main import app


def test_prod_has_no_implicit_cors_allowlist(monkeypatch):
    monkeypatch.setenv("TORE_ENV", "PROD")
    monkeypatch.delenv("TORE_CORS_ORIGINS", raising=False)
    assert core_cors_origins() == []
    assert legacy_cors_origins() == []


def test_explicit_production_cors_allowlist(monkeypatch):
    monkeypatch.setenv("TORE_ENV", "PROD")
    monkeypatch.setenv("TORE_CORS_ORIGINS", "https://portal.tore.be,https://tore.be")
    assert core_cors_origins() == ["https://portal.tore.be", "https://tore.be"]
    assert legacy_cors_origins() == ["https://portal.tore.be", "https://tore.be"]


def test_untrusted_render_domain_not_implicitly_allowed():
    response = TestClient(app).options("/healthz", headers={
        "Origin": "https://untrusted-project.onrender.com",
        "Access-Control-Request-Method": "GET",
    })
    assert response.headers.get("access-control-allow-origin") is None


def test_prodlike_compose_forces_prod():
    compose = (Path(__file__).resolve().parents[2] / "docker-compose.yml").read_text()
    prod = compose.split("  backend-prodlike:", 1)[1].split("\nvolumes:", 1)[0]
    assert 'TORE_ENV: "PROD"' in prod
    assert 'TORE_RATE_LIMIT_BACKEND: "database"' in prod
    assert "https://portal.example" not in prod
