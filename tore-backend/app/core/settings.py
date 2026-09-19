"""Environment/settings helpers used by app composition and legacy imports."""

import os

from app.legacy import monolith as _legacy_monolith
from app.legacy.monolith import (
    ACCESS_TOKEN_TTL_MIN,
    ADMIN_API_KEY,
    EMAIL_OTP_SCOPE_EMAIL,
    EMAIL_OTP_SCOPE_IP,
    EMAIL_OTP_TTL_MIN,
    EMAIL_OTP_VERIFY_SCOPE,
    ENABLE_SMS_OTP,
    ENABLE_WHATSAPP_OTP,
    EnvReport,
    GOOGLE_ISSUERS,
    GOOGLE_JWKS_URL,
    JWT_ALG,
    JWT_SECRET,
    MAGIC_LINK_RATE_SCOPE,
    MAGIC_LINK_TTL_MIN,
    ORGA_CODE,
    REFRESH_TOKEN_TTL_DAYS,
    TEAM_CODE,
    _cors_origins,
    _env_bool,
    validate_env_or_warn,
)


def _resolved_env_name() -> str:
    """Resolve the runtime profile from the canonical env and supported aliases."""
    raw = (
        os.getenv("TORE_ENV")
        or os.getenv("APP_ENV")
        or os.getenv("ENV")
        or "DEV"
    ).strip().upper()
    if raw in {"PRODUCTION", "PROD"}:
        return "PROD"
    if raw in {"DEVELOPMENT", "DEV", "TEST"}:
        return "DEV"
    return raw or "DEV"


def _strict_dev_env_enabled() -> bool:
    return _resolved_env_name() == "DEV"


# The legacy validation functions resolve these names dynamically in their
# module. Patch the compatibility module as soon as settings are imported so
# startup checks cannot silently treat APP_ENV=prod as development.
_legacy_monolith._resolved_env_name = _resolved_env_name
_legacy_monolith._strict_dev_env_enabled = _strict_dev_env_enabled

__all__ = [
    "EnvReport",
    "_env_bool",
    "_strict_dev_env_enabled",
    "_resolved_env_name",
    "validate_env_or_warn",
    "_cors_origins",
    "JWT_SECRET",
    "JWT_ALG",
    "ACCESS_TOKEN_TTL_MIN",
    "REFRESH_TOKEN_TTL_DAYS",
    "MAGIC_LINK_TTL_MIN",
    "MAGIC_LINK_RATE_SCOPE",
    "EMAIL_OTP_TTL_MIN",
    "EMAIL_OTP_SCOPE_EMAIL",
    "EMAIL_OTP_SCOPE_IP",
    "EMAIL_OTP_VERIFY_SCOPE",
    "GOOGLE_JWKS_URL",
    "GOOGLE_ISSUERS",
    "ENABLE_SMS_OTP",
    "ENABLE_WHATSAPP_OTP",
    "ORGA_CODE",
    "TEAM_CODE",
    "ADMIN_API_KEY",
]
