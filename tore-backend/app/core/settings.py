"""Environment/settings helpers extracted from legacy main module."""

from main import (
    EnvReport,
    _cors_origins,
    _env_bool,
    _resolved_env_name,
    _strict_dev_env_enabled,
    validate_env_or_warn,
)

__all__ = [
    "EnvReport",
    "_env_bool",
    "_strict_dev_env_enabled",
    "_resolved_env_name",
    "validate_env_or_warn",
    "_cors_origins",
]
