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
