import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import rate_limit_service


@pytest.fixture(autouse=True)
def _reset_rate_limit_service_state():
    old_max = rate_limit_service._RATE_LIMIT_MAX
    old_window = rate_limit_service._RATE_LIMIT_WINDOW_S
    try:
        yield
    finally:
        rate_limit_service._RATE_LIMIT_MAX = old_max
        rate_limit_service._RATE_LIMIT_WINDOW_S = old_window
        rate_limit_service._store.clear()
