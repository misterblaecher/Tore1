import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_DB_PATH = ROOT / "data" / "test_tore_pytest.db"
TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
for suffix in ("", "-journal", "-wal", "-shm"):
    path = Path(f"{TEST_DB_PATH}{suffix}")
    if path.exists():
        path.unlink()

import os

os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DB_PATH.as_posix()}")
# Existing prediction lifecycle tests exercise the explicitly enabled deployment.
# Production defaults remain OFF and are covered by test_release_security.py.
os.environ.setdefault("TORE_VALUE_PREDICTIONS_ENABLED", "1")

from sqlalchemy.orm import Session

from db import engine
from models import AppUser
from app.services import rate_limit_service


@pytest.fixture(autouse=True)
def _reset_rate_limit_service_state():
    old_max = rate_limit_service._RATE_LIMIT_MAX
    old_window = rate_limit_service._RATE_LIMIT_WINDOW_S
    old_scope_limits = dict(rate_limit_service._SCOPE_LIMITS)
    try:
        yield
    finally:
        rate_limit_service._RATE_LIMIT_MAX = old_max
        rate_limit_service._RATE_LIMIT_WINDOW_S = old_window
        rate_limit_service._SCOPE_LIMITS.clear()
        rate_limit_service._SCOPE_LIMITS.update(old_scope_limits)
        rate_limit_service._store.clear()


_FORUM_BACKEND_REGISTERED_COMPAT_MODULES = {
    "test_forum_backend_security",
    "test_forum_backend_final_hardening",
}


@pytest.fixture(autouse=True)
def _promote_legacy_forum_test_actors_to_registered(request):
    """Keep historical Forum test helpers while exercising registered actors.

    The two foundation suites predate the registered-only Forum boundary and
    named their actor factory ``_guest``. For those suites only, promote the
    freshly bootstrapped account immediately after ``/auth/guest`` so every
    owner/manager/member reaching a private ``/forum/v2`` route is a registered
    AppUser. Dedicated review-blocker tests intentionally do not use this shim
    and verify raw guest rejection directly.
    """
    module = getattr(request, "module", None)
    module_name = getattr(module, "__name__", "").rsplit(".", 1)[-1]
    if module_name not in _FORUM_BACKEND_REGISTERED_COMPAT_MODULES:
        yield
        return

    test_client = getattr(module, "client", None)
    if test_client is None:
        yield
        return

    original_post = test_client.post

    def registered_bootstrap_post(url, *args, **kwargs):
        response = original_post(url, *args, **kwargs)
        if str(url) == "/auth/guest" and response.status_code == 200:
            token = response.json()["token"]
            me = test_client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert me.status_code == 200, me.text
            with Session(engine) as db:
                user = db.get(AppUser, me.json()["id"])
                assert user is not None
                user.is_guest = False
                user.is_deleted = False
                user.deleted_at = None
                user.account_status = "ACTIVE"
                db.commit()
        return response

    test_client.post = registered_bootstrap_post
    try:
        yield
    finally:
        test_client.post = original_post
