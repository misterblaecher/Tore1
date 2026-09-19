from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security.user_auth import (
    _extract_bearer_token,
    _hash_token,
    _resolve_app_user_from_token,
    get_current_user,
)
from app.services.event_role_service import _role_rank
from db import Base, engine, now_utc
from models import AppToken, AppUser
from fastapi.security import HTTPAuthorizationCredentials


@pytest.fixture(autouse=True)
def _db_schema():
    Base.metadata.create_all(engine)
    yield


def test_extract_bearer_token_preserves_legacy_normalization():
    assert _extract_bearer_token(' Bearer "abc" ') == "abc"
    assert _extract_bearer_token("'abc'") == "abc"
    assert _extract_bearer_token(None) is None


def test_hash_token_is_sha256_hex():
    assert _hash_token("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_resolver_and_dependency_share_same_token_contract():
    with Session(engine) as db:
        user = AppUser(id="auth-boundary-user", display_name="Auth Boundary")
        db.add(user)
        db.flush()
        raw = "auth-boundary-token"
        db.add(AppToken(user_id=user.id, token_hash=_hash_token(raw), created_at=now_utc()))
        db.commit()

        resolved = _resolve_app_user_from_token(raw, db)
        assert resolved is not None
        assert resolved.id == user.id

        current = get_current_user(
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw),
            db=db,
        )
        assert current.id == user.id


def test_expired_registered_token_is_revoked():
    from app.core.settings import ACCESS_TOKEN_TTL_MIN

    with Session(engine) as db:
        user = AppUser(id="auth-boundary-expired", display_name="Expired")
        db.add(user)
        db.flush()
        raw = "auth-boundary-expired-token"
        row = AppToken(
            user_id=user.id,
            token_hash=_hash_token(raw),
            created_at=now_utc() - timedelta(minutes=ACCESS_TOKEN_TTL_MIN + 1),
        )
        db.add(row)
        db.commit()

        assert _resolve_app_user_from_token(raw, db) is None
        db.refresh(row)
        assert row.revoked_at is not None


def test_invalid_token_keeps_401_contract():
    with Session(engine) as db:
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="missing"),
                db=db,
            )
    assert exc_info.value.status_code == 401


def test_event_role_rank_contract_is_stable():
    assert _role_rank("guest") < _role_rank("entry") < _role_rank("admin")
