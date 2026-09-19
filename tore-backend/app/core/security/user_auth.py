"""Application bearer-token authentication independent from the legacy runtime."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.settings import ACCESS_TOKEN_TTL_MIN
from app.deps.db import get_db
from db import now_utc
from models import AppToken, AppUser, UserSanction


security = HTTPBearer(auto_error=False)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    raw = authorization.strip().strip('"').strip("'").strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    raw = raw.strip().strip('"').strip("'").strip()
    return raw or None


def _active_sanction_for_user(db: Session, user_id: str) -> Optional[UserSanction]:
    now = now_utc()
    rows = (
        db.query(UserSanction)
        .filter(UserSanction.user_id == user_id, UserSanction.status == "ACTIVE")
        .order_by(UserSanction.created_at.desc())
        .all()
    )
    for row in rows:
        if row.starts_at and row.starts_at > now:
            continue
        if row.ends_at and row.ends_at <= now:
            row.status = "EXPIRED"
            db.add(row)
            continue
        return row
    return None


def _enforce_user_sanctions(db: Session, user: AppUser) -> None:
    if bool(getattr(user, "is_deleted", False)):
        raise HTTPException(status_code=403, detail={"reason": "ACCOUNT_DELETED"})
    status = (getattr(user, "account_status", None) or "ACTIVE").upper()
    if status not in {"ACTIVE", "LEGACY"}:
        raise HTTPException(
            status_code=403,
            detail={"reason": "ACCOUNT_INACTIVE", "status": status},
        )
    sanction = _active_sanction_for_user(db, user.id)
    if sanction and sanction.type in {"SUSPEND", "BAN"}:
        raise HTTPException(
            status_code=403,
            detail={
                "reason": "SANCTIONED",
                "type": sanction.type,
                "endsAt": sanction.ends_at.isoformat() if sanction.ends_at else None,
            },
        )


def _resolve_app_user_from_token(raw: str, db: Session) -> Optional[AppUser]:
    token_hash = _hash_token(raw)
    tok = (
        db.query(AppToken)
        .filter(AppToken.token_hash == token_hash, AppToken.revoked_at.is_(None))
        .first()
    )
    if not tok:
        return None

    user = db.get(AppUser, tok.user_id)
    if user is None:
        return None

    now = now_utc()
    if (
        not bool(getattr(user, "is_guest", False))
        and tok.created_at
        and tok.created_at <= now - timedelta(minutes=ACCESS_TOKEN_TTL_MIN)
    ):
        tok.revoked_at = now
        db.add(tok)
        db.commit()
        return None

    try:
        _enforce_user_sanctions(db, user)
    except HTTPException:
        return None
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> AppUser:
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing token")

    raw = _extract_bearer_token(credentials.credentials or "")
    if not raw:
        raise HTTPException(status_code=401, detail="Invalid token")

    token_hash = _hash_token(raw)
    tok = (
        db.query(AppToken)
        .filter(AppToken.token_hash == token_hash, AppToken.revoked_at.is_(None))
        .first()
    )
    if not tok:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.get(AppUser, tok.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    now = now_utc()
    if (
        not bool(getattr(user, "is_guest", False))
        and tok.created_at
        and tok.created_at <= now - timedelta(minutes=ACCESS_TOKEN_TTL_MIN)
    ):
        tok.revoked_at = now
        db.add(tok)
        db.commit()
        raise HTTPException(status_code=401, detail={"reason": "access_token_expired"})

    _enforce_user_sanctions(db, user)
    return user


__all__ = [
    "security",
    "_hash_token",
    "_extract_bearer_token",
    "_active_sanction_for_user",
    "_enforce_user_sanctions",
    "_resolve_app_user_from_token",
    "get_current_user",
]
