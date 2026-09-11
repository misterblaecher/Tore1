from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from models import AppUser
from app.legacy.monolith import (
    _extract_bearer_token,
    _resolve_app_user_from_token,
    get_db,
)


_PUBLIC_FORUM_GET_PREFIX = "/forum/v2/public/"
_PUBLIC_FORUM_GET_PATHS = {"/forum/v2/health"}


def _is_public_forum_read(request: Request) -> bool:
    """Return True only for explicitly public, read-only Forum v2 surfaces."""
    if request.method.upper() != "GET":
        return False
    path = request.url.path
    return path in _PUBLIC_FORUM_GET_PATHS or path.startswith(_PUBLIC_FORUM_GET_PREFIX)


def get_registered_forum_user(
    request: Request,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> Optional[AppUser]:
    """Enforce the Forum v2 trust boundary for every non-public request.

    Public Forum reads stay anonymous. Every other Forum v2 operation requires
    an existing TORÈ bearer token resolving to a registered, non-deleted user.
    In particular, guest sessions may not create or administer structures,
    accept Forum invitations, submit ownership claims, or access private Forum
    data.
    """
    if _is_public_forum_read(request):
        return None

    raw_token = _extract_bearer_token(authorization)
    user = _resolve_app_user_from_token(raw_token, db) if raw_token else None
    if (
        user is None
        or bool(user.is_guest)
        or bool(user.is_deleted)
        or user.deleted_at is not None
    ):
        raise HTTPException(
            status_code=401,
            detail={"reason": "REGISTERED_FORUM_USER_REQUIRED"},
        )
    return user
