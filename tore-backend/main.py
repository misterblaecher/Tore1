"""Minimal root entrypoint keeping legacy import compatibility."""

import sys

from app.main import create_app
from app.core.settings import EnvReport, _cors_origins, _env_bool, _resolved_env_name, _strict_dev_env_enabled, validate_env_or_warn
from app.core.errors import _http_exception_handler, _unhandled_exception_handler
from app.core.logging import _request_id_from_request
from app.core.startup import _startup, _startup_sanity_checks, ensure_seed, run_migrations_on_startup
from app.legacy import monolith as _monolith

_monolith.create_app = create_app
_monolith.app = create_app()

# Explicit compatibility re-exports requested by step plan.
_monolith.EnvReport = EnvReport
_monolith._env_bool = _env_bool
_monolith._strict_dev_env_enabled = _strict_dev_env_enabled
_monolith._resolved_env_name = _resolved_env_name
_monolith.validate_env_or_warn = validate_env_or_warn
_monolith._cors_origins = _cors_origins
_monolith._http_exception_handler = _http_exception_handler
_monolith._unhandled_exception_handler = _unhandled_exception_handler
_monolith._request_id_from_request = _request_id_from_request
_monolith._startup = _startup
_monolith._startup_sanity_checks = _startup_sanity_checks
_monolith.run_migrations_on_startup = run_migrations_on_startup
_monolith.ensure_seed = ensure_seed

sys.modules[__name__] = _monolith
