"""TORÈ backend ASGI entrypoint.

This is a normal Python module. Historical attribute imports are served through
an explicit legacy compatibility boundary; the module is no longer replaced in
sys.modules and no runtime monkey-patching is performed.
"""

from __future__ import annotations

from app.main import create_app
from app.core.environment import _env_bool, _resolved_env_name, _strict_dev_env_enabled
from app.core.errors import _http_exception_handler, _unhandled_exception_handler
from app.core.logging import _request_id_from_request
from app.core.settings import (
    ACCESS_TOKEN_TTL_MIN,
    EnvReport,
    _cors_origins,
    validate_env_or_warn,
)
from app.core.startup import (
    _startup,
    _startup_sanity_checks,
    ensure_seed,
    run_migrations_on_startup,
)
from app.core.security.app_tokens import decode_user_token
from app.legacy.runtime import legacy_export


app = create_app()


def __getattr__(name: str):
    """Keep historical imports working while the legacy route body is retired."""
    try:
        return legacy_export(name)
    except AttributeError as exc:
        raise AttributeError(f"module 'main' has no attribute {name!r}") from exc


__all__ = [
    "app",
    "create_app",
    "EnvReport",
    "_env_bool",
    "_strict_dev_env_enabled",
    "_resolved_env_name",
    "validate_env_or_warn",
    "_cors_origins",
    "_http_exception_handler",
    "_unhandled_exception_handler",
    "_request_id_from_request",
    "_startup",
    "_startup_sanity_checks",
    "run_migrations_on_startup",
    "ensure_seed",
    "decode_user_token",
    "ACCESS_TOKEN_TTL_MIN",
]
