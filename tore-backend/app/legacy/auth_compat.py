"""Explicit compatibility boundary for auth endpoints not yet split from legacy.

Modern code may depend on this narrow surface during the strangler migration,
but must not import app.legacy.monolith directly.
"""

from app.legacy.monolith import (
    EmailOtpVerifyIn,
    MagicLinkVerifyIn,
    PasswordLoginIn,
    PasswordRegisterIn,
    RefreshIn,
    auth_email_verify_link,
    auth_email_verify_otp,
    auth_password_login,
    auth_password_register,
    auth_refresh,
)

__all__ = [
    "EmailOtpVerifyIn",
    "MagicLinkVerifyIn",
    "PasswordLoginIn",
    "PasswordRegisterIn",
    "RefreshIn",
    "auth_email_verify_link",
    "auth_email_verify_otp",
    "auth_password_login",
    "auth_password_register",
    "auth_refresh",
]
