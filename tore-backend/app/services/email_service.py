"""SMTP delivery boundary independent from the legacy runtime."""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Optional

from fastapi import HTTPException

from app.core.environment import _resolved_env_name, _strict_dev_env_enabled


def send_email(
    subject: str,
    body: str,
    to_email: str,
    reply_to: Optional[str] = None,
) -> None:
    host = (os.getenv("SMTP_HOST") or "").strip()
    if not host:
        if _resolved_env_name() == "PROD":
            raise HTTPException(status_code=503, detail={"code": "email_provider_missing"})
        logging.info("email.skip.no_smtp subject=%s to=%s", subject, to_email)
        return

    port = int((os.getenv("SMTP_PORT") or "587").strip())
    username = (os.getenv("SMTP_USERNAME") or "").strip()
    password = (os.getenv("SMTP_PASSWORD") or "").strip()
    sender = (os.getenv("SMTP_FROM") or "toreguindaille@gmail.com").strip()
    override_to = (os.getenv("MAIL_OVERRIDE_TO") or "").strip()
    target = override_to or to_email

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = target
    if reply_to and "@" in reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
    except Exception:
        logging.exception("email.send.failed subject=%s to=%s", subject, target)
        if _strict_dev_env_enabled():
            logging.info("email.send.dev_dry_run subject=%s to=%s", subject, to_email)
            return
        raise


# Temporary alias for callers/tests migrating from the historical name.
_send_email = send_email

__all__ = ["send_email", "_send_email"]
