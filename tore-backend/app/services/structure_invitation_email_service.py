from __future__ import annotations

import html
import logging
import os
import smtplib
from email.message import EmailMessage


logger = logging.getLogger(__name__)


def send_structure_invitation_email(
    *,
    recipient_email: str,
    structure_name: str,
    invited_role: str,
    invite_url: str,
    expires_label: str,
) -> str:
    """Deliver a structure invitation through the existing SMTP configuration.

    The function intentionally never logs the invite URL/token. Returning a
    delivery state lets the manager know about mail infrastructure failures
    without exposing whether the recipient already owns a TORÈ account.
    """

    host = (os.getenv("SMTP_HOST") or "").strip()
    if not host:
        logger.info("Structure invitation email skipped because SMTP_HOST is not configured")
        return "SKIPPED"

    port = int(os.getenv("SMTP_PORT", "587"))
    username = (os.getenv("SMTP_USERNAME") or "").strip()
    password = os.getenv("SMTP_PASSWORD") or ""
    sender = (os.getenv("SMTP_FROM") or username or "TORÈ <no-reply@tore.local>").strip()
    override_to = (os.getenv("MAIL_OVERRIDE_TO") or "").strip()
    destination = override_to or recipient_email

    message = EmailMessage()
    message["Subject"] = f"Invitation à rejoindre {structure_name} sur TORÈ"
    message["From"] = sender
    message["To"] = destination
    message.set_content(
        "\n".join(
            [
                f"Vous êtes invité·e à rejoindre {structure_name} sur TORÈ avec le rôle {invited_role}.",
                "",
                f"Ouvrir l'invitation : {invite_url}",
                f"Ce lien expire {expires_label} et ne peut être utilisé qu'une seule fois.",
                "",
                "Si vous n'attendiez pas cette invitation, vous pouvez l'ignorer ou la refuser depuis le lien.",
            ]
        )
    )
    safe_structure = html.escape(structure_name)
    safe_role = html.escape(invited_role)
    safe_url = html.escape(invite_url, quote=True)
    safe_expiry = html.escape(expires_label)
    message.add_alternative(
        f"""
        <html><body style="font-family:Arial,sans-serif;color:#18181b">
          <h2>Invitation TORÈ</h2>
          <p>Vous êtes invité·e à rejoindre <strong>{safe_structure}</strong> avec le rôle <strong>{safe_role}</strong>.</p>
          <p><a href="{safe_url}" style="display:inline-block;padding:12px 18px;background:#18181b;color:#fff;text-decoration:none;border-radius:8px">Voir l'invitation</a></p>
          <p>Ce lien expire {safe_expiry} et ne peut être utilisé qu'une seule fois.</p>
          <p style="color:#71717a;font-size:13px">Si vous n'attendiez pas cette invitation, ignorez ce message ou refusez l'invitation depuis le lien.</p>
        </body></html>
        """,
        subtype="html",
    )

    try:
        timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))
        use_ssl = (os.getenv("SMTP_USE_SSL") or "").strip().lower() in {"1", "true", "yes", "on"}
        starttls = (os.getenv("SMTP_STARTTLS", "1") or "1").strip().lower() in {"1", "true", "yes", "on"}
        client_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        with client_cls(host, port, timeout=timeout) as smtp:
            if not use_ssl and starttls:
                smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
        return "SENT"
    except Exception:
        logger.exception("Structure invitation email delivery failed")
        return "FAILED"
