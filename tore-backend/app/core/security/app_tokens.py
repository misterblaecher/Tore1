from __future__ import annotations

import hashlib

from db import get_session
from models import AppToken


def decode_user_token(raw: str) -> str | None:
    """Resolve an app bearer token to its user id.

    App tokens are opaque values stored hashed in ``app_tokens``; they are not
    JWTs. This helper intentionally returns ``None`` for missing, invalid, or
    revoked tokens so optional-auth endpoints can stay anonymous instead of
    crashing.
    """
    token = (raw or "").strip().strip('"').strip("'").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        return None

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db = get_session()
    try:
        row = (
            db.query(AppToken)
            .filter(
                AppToken.token_hash == token_hash,
                AppToken.revoked_at.is_(None),
            )
            .first()
        )
        return str(row.user_id) if row is not None else None
    finally:
        db.close()
