"""JWT helpers independent from the legacy runtime."""

from __future__ import annotations

from typing import Any, Optional

import jwt
from sqlalchemy.orm import Session

from app.core.settings import JWT_ALG, JWT_SECRET
from app.core.security.user_auth import (
    _extract_bearer_token,
    _hash_token,
    _resolve_app_user_from_token,
)
from models import PartnerMembership


def _resolve_partner_identity_from_token(raw: str, db: Session) -> Optional[dict[str, Any]]:
    try:
        payload = jwt.decode(raw, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None

    try:
        user_id = int(payload.get("sub"))
        bar_id = int(payload.get("bar_id"))
    except (TypeError, ValueError):
        return None

    membership = (
        db.query(PartnerMembership)
        .filter(
            PartnerMembership.user_id == user_id,
            PartnerMembership.bar_id == bar_id,
        )
        .first()
    )
    if membership is None:
        return None

    return {
        "user_id": user_id,
        "bar_id": bar_id,
        "role": membership.role,
        "display_name": membership.display_name,
    }


__all__ = [
    "_extract_bearer_token",
    "_hash_token",
    "_resolve_app_user_from_token",
    "_resolve_partner_identity_from_token",
]
