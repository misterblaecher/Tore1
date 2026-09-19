from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from db import engine
from app.models.rate_limit import RateLimitBucket
from app.services import rate_limit_service


@pytest.fixture(autouse=True)
def _clean_rate_limit_buckets():
    RateLimitBucket.__table__.create(bind=engine, checkfirst=True)
    with engine.begin() as connection:
        connection.execute(delete(RateLimitBucket.__table__))
    yield
    with engine.begin() as connection:
        connection.execute(delete(RateLimitBucket.__table__))


def test_database_store_is_shared_between_instances():
    first = rate_limit_service.DatabaseRateLimitStore(engine)
    second = rate_limit_service.DatabaseRateLimitStore(engine)
    key = rate_limit_service._distributed_key("shared", "user@example.com")

    assert first.consume(key, 2, 60, now_ms=1_000) is None
    assert second.consume(key, 2, 60, now_ms=1_000) is None
    assert first.consume(key, 2, 60, now_ms=1_000) == 60


def test_database_store_resets_after_window_expiry():
    store = rate_limit_service.DatabaseRateLimitStore(engine)
    key = rate_limit_service._distributed_key("ttl", "actor")

    assert store.consume(key, 1, 10, now_ms=1_000) is None
    assert store.consume(key, 1, 10, now_ms=2_000) == 9
    assert store.consume(key, 1, 10, now_ms=11_000) is None


def test_distributed_key_does_not_persist_raw_actor_data():
    key = rate_limit_service._distributed_key("auth_email_request_otp_email", "student@example.com")
    assert key.startswith("auth_email_request_otp_email:")
    assert "student@example.com" not in key


def test_prod_auto_selects_database(monkeypatch):
    monkeypatch.setenv("TORE_ENV", "PROD")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("TORE_RATE_LIMIT_BACKEND", raising=False)
    if engine.dialect.name != "postgresql":
        with pytest.raises(rate_limit_service.RateLimitBackendUnavailable):
            rate_limit_service._backend_name()
    else:
        assert rate_limit_service._backend_name() == "database"


def test_prod_refuses_memory_backend(monkeypatch):
    monkeypatch.setenv("TORE_ENV", "PROD")
    monkeypatch.setenv("TORE_RATE_LIMIT_BACKEND", "memory")

    with pytest.raises(rate_limit_service.RateLimitBackendUnavailable):
        rate_limit_service._backend_name()


def test_backend_failure_fails_closed_with_503(monkeypatch):
    monkeypatch.setenv("TORE_RATE_LIMIT_BACKEND", "database")
    monkeypatch.setenv("TORE_ENV", "DEV")

    def broken_consume(*_args, **_kwargs):
        raise SQLAlchemyError("store unavailable")

    monkeypatch.setattr(rate_limit_service._database_store, "consume", broken_consume)

    with pytest.raises(HTTPException) as exc_info:
        rate_limit_service.enforce_rate_limit("test", "actor")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "rate_limit_backend_unavailable"
    assert exc_info.value.headers["Retry-After"] == "5"


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="PostgreSQL atomicity integration")
def test_postgres_concurrent_requests_share_one_quota():
    stores = [
        rate_limit_service.DatabaseRateLimitStore(engine),
        rate_limit_service.DatabaseRateLimitStore(engine),
    ]
    key = rate_limit_service._distributed_key("concurrency", "same-actor")

    def consume(index: int):
        return stores[index % 2].consume(key, 5, 60, now_ms=5_000)

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(consume, range(20)))

    assert sum(result is None for result in results) == 5
    assert sum(result is not None for result in results) == 15


def test_partner_login_maps_identity_or_ip_limit_to_429(monkeypatch):
    calls = []

    def fake_enforce(scope: str, actor_key: str):
        calls.append((scope, actor_key))
        if scope == "partner_pin_login_ip":
            raise rate_limit_service.RateLimitExceeded(scope, 17)

    monkeypatch.setattr(rate_limit_service, "enforce_rate_limit", fake_enforce)

    from partner_auth import LoginIn, login

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/partner/auth/login",
            "headers": [],
            "client": ("203.0.113.10", 12345),
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        login(
            LoginIn(bar_id=42, display_name="Staff", pin="1234"),
            request,
            db=None,
        )

    assert [scope for scope, _ in calls] == ["partner_pin_login", "partner_pin_login_ip"]
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["scope"] == "partner_pin_login_ip"
    assert exc_info.value.headers["Retry-After"] == "17"
