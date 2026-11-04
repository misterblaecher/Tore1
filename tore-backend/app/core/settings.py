"""Runtime settings and production hardening checks.

This module is intentionally independent from app.legacy.monolith so new code
can depend on configuration without importing the legacy runtime.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Optional

from app.core.environment import _env_bool, _resolved_env_name, _strict_dev_env_enabled


JWT_SECRET = os.getenv("TORE_JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
ACCESS_TOKEN_TTL_MIN = int(os.getenv("TORE_AUTH_ACCESS_TTL_MIN", "60"))
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("TORE_AUTH_REFRESH_TTL_DAYS", "30"))
MAGIC_LINK_TTL_MIN = int(os.getenv("TORE_AUTH_MAGIC_LINK_TTL_MIN", "10"))
MAGIC_LINK_RATE_SCOPE = "auth_email_request_link"
EMAIL_OTP_TTL_MIN = int(os.getenv("TORE_AUTH_EMAIL_OTP_TTL_MIN", "10"))
EMAIL_OTP_SCOPE_EMAIL = "auth_email_request_otp_email"
EMAIL_OTP_SCOPE_IP = "auth_email_request_otp_ip"
EMAIL_OTP_VERIFY_SCOPE = "auth_email_verify_otp"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
ENABLE_SMS_OTP = _env_bool("ENABLE_SMS_OTP", False)
ENABLE_WHATSAPP_OTP = _env_bool("ENABLE_WHATSAPP_OTP", False)
ORGA_CODE = (os.getenv("ORGA_CODE") or "").strip()
TEAM_CODE = (os.getenv("TEAM_CODE") or "").strip()
ADMIN_API_KEY = (os.getenv("ADMIN_API_KEY") or "").strip()


@dataclass
class EnvReport:
    env: str
    missing: list[str]
    warnings: list[str]


def _cors_origins() -> list[str]:
    raw = (os.getenv("TORE_CORS_ORIGINS") or "").strip()

    def _normalize(items: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in items:
            value = item.strip().rstrip("/")
            if not value or value == "*":
                continue
            if value not in seen:
                seen.add(value)
                normalized.append(value)
        return normalized

    if raw:
        return _normalize([value.strip() for value in raw.split(",") if value.strip()])

    # No development or hosting defaults in production.
    if _resolved_env_name() == "PROD":
        return []

    site_url = (os.getenv("TORE_SITE_URL") or os.getenv("PUBLIC_URL") or "").strip()
    defaults = [
        "https://tore-site.onrender.com",
        "https://tore.onrender.com",
        "https://tore1.onrender.com",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    if site_url:
        defaults.append(site_url)
    return _normalize(defaults)


def _validate_qr_signing_keys_format() -> tuple[bool, str]:
    ring = (os.getenv("TORE_QR_SIGNING_KEYS") or "").strip()
    if not ring:
        return True, "TORE_QR_SIGNING_KEYS not set (fallback secret strategy enabled)"

    values = [item.strip() for item in ring.split(",") if item.strip()]
    if not values:
        return False, "TORE_QR_SIGNING_KEYS is present but empty after parsing"

    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-:.")
    invalid: list[str] = []
    for idx, value in enumerate(values, start=1):
        if len(value) < 16:
            invalid.append(f"#{idx}:too_short")
            continue
        if any(ch not in allowed for ch in value):
            invalid.append(f"#{idx}:invalid_chars")
    if invalid:
        return False, f"invalid keys ({', '.join(invalid)})"
    return True, f"{len(values)} key(s)"


def validate_env_or_warn() -> EnvReport:
    env_name = _resolved_env_name()
    is_prod = env_name == "PROD"
    missing: list[str] = []
    warnings: list[str] = []

    if env_name not in {"DEV", "PROD", "TEST"}:
        warnings.append(f"ENV has unexpected value '{env_name}'")

    if is_prod:
        for key in ("TORE_JWT_SECRET", "ADMIN_API_KEY"):
            value = (os.getenv(key) or "").strip()
            if len(value) < 32 or value.lower().startswith(("dev-", "change-me", "replace-")):
                missing.append(f"{key} must be a unique secret of at least 32 characters")
        for key in ("TORE_EMAIL_OTP_DEV_MODE", "TORE_EMAIL_OTP_DRY_RUN", "ALLOW_DEV_OTP"):
            if _env_bool(key, False):
                missing.append(f"{key} must be disabled in PROD")
        if (os.getenv("MAIL_OVERRIDE_TO") or "").strip():
            missing.append("MAIL_OVERRIDE_TO must be unset in PROD")
        for key in ("SMTP_HOST", "SMTP_FROM"):
            if not (os.getenv(key) or "").strip():
                missing.append(key)

    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if not db_url:
        if is_prod:
            missing.append("DATABASE_URL")
        else:
            warnings.append("DATABASE_URL missing: sqlite dev fallback will be used")
    elif is_prod and db_url.lower().startswith("sqlite"):
        missing.append("DATABASE_URL must target Postgres in PROD")

    public_url = (os.getenv("PUBLIC_URL") or "").strip()
    base_url = (os.getenv("BASE_URL") or "").strip()
    if not (public_url or base_url):
        if is_prod:
            missing.append("PUBLIC_URL/BASE_URL")
        else:
            warnings.append("PUBLIC_URL/BASE_URL missing: using TORE_PUBLIC_APP_URL/default")

    qr_ring = (os.getenv("TORE_QR_SIGNING_KEYS") or "").strip()
    if not qr_ring:
        if is_prod:
            missing.append("TORE_QR_SIGNING_KEYS")
        else:
            warnings.append("TORE_QR_SIGNING_KEYS missing: fallback secret strategy in use")
    else:
        ok, msg = _validate_qr_signing_keys_format()
        if not ok:
            missing.append(f"TORE_QR_SIGNING_KEYS ({msg})")
        elif len([item for item in qr_ring.split(",") if item.strip()]) < 2:
            warnings.append("TORE_QR_SIGNING_KEYS rotation looks weak (<2 keys)")

    cors_raw = (os.getenv("TORE_CORS_ORIGINS") or "").strip()
    if is_prod:
        if not cors_raw:
            missing.append("TORE_CORS_ORIGINS")
        elif "*" in [origin.strip() for origin in cors_raw.split(",")]:
            missing.append("TORE_CORS_ORIGINS cannot be '*' in PROD")
    elif not cors_raw:
        warnings.append("TORE_CORS_ORIGINS missing: localhost defaults are enabled")

    google_enabled = _env_bool("TORE_AUTH_GOOGLE_ENABLED") or _env_bool("GOOGLE_AUTH_ENABLED")
    if google_enabled and not (os.getenv("GOOGLE_CLIENT_ID") or "").strip():
        missing.append("GOOGLE_CLIENT_ID")

    retention_raw = (os.getenv("RETENTION_DAYS") or os.getenv("TORE_PRIVACY_RETENTION_DAYS") or "").strip()
    if not retention_raw:
        warnings.append("RETENTION_DAYS/TORE_PRIVACY_RETENTION_DAYS missing: default retention=30")
    else:
        try:
            if int(retention_raw) < 1:
                missing.append("RETENTION_DAYS must be >= 1")
        except ValueError:
            missing.append("RETENTION_DAYS must be an integer")

    report = EnvReport(env=env_name, missing=missing, warnings=warnings)
    for warning in warnings:
        logging.warning("startup.env.warning=%s", warning)
    if is_prod and missing:
        raise RuntimeError(f"Critical environment configuration is missing: {', '.join(missing)}")
    if missing:
        for item in missing:
            logging.warning("startup.env.missing=%s", item)
    return report


def _debug_signing_key_ids() -> list[str]:
    ring = (os.getenv("TORE_QR_SIGNING_KEYS") or "").strip()
    if ring:
        values = [item.strip() for item in ring.split(",") if item.strip()]
    else:
        fallback = (os.getenv("TORE_QR_SIGNING_SECRET") or os.getenv("TORE_JWT_SECRET") or "").strip()
        values = [fallback] if fallback else []
    return [hashlib.sha256(value.encode("utf-8")).hexdigest()[:12] for value in values]


__all__ = [
    "EnvReport", "_env_bool", "_strict_dev_env_enabled", "_resolved_env_name",
    "validate_env_or_warn", "_cors_origins", "_validate_qr_signing_keys_format",
    "JWT_SECRET", "JWT_ALG", "ACCESS_TOKEN_TTL_MIN", "REFRESH_TOKEN_TTL_DAYS",
    "MAGIC_LINK_TTL_MIN", "MAGIC_LINK_RATE_SCOPE", "EMAIL_OTP_TTL_MIN",
    "EMAIL_OTP_SCOPE_EMAIL", "EMAIL_OTP_SCOPE_IP", "EMAIL_OTP_VERIFY_SCOPE",
    "GOOGLE_JWKS_URL", "GOOGLE_ISSUERS", "ENABLE_SMS_OTP",
    "ENABLE_WHATSAPP_OTP", "ORGA_CODE", "TEAM_CODE", "ADMIN_API_KEY",
]
