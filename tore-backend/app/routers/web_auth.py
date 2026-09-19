from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.legacy import monolith as legacy
from db import get_db, now_utc
from models import AppToken, RefreshToken


router = APIRouter(prefix="/auth/web", tags=["auth-web"])
REFRESH_COOKIE = "tore_web_refresh"


def _is_prod() -> bool:
    return legacy._resolved_env_name() == "PROD"


def _allowed_origins() -> set[str]:
    return {origin.rstrip("/") for origin in legacy._cors_origins()}


def _require_web_origin(request: Request) -> None:
    """Reject browser credential requests from origins outside TORÈ's explicit allowlist."""
    origin = (request.headers.get("origin") or "").strip().rstrip("/")
    fetch_site = (request.headers.get("sec-fetch-site") or "").strip().lower()
    allowed = _allowed_origins()

    if origin:
        if origin not in allowed:
            raise HTTPException(status_code=403, detail={"reason": "web_origin_forbidden"})
    elif _is_prod():
        # Browser credential endpoints are intentionally not a generic API surface.
        raise HTTPException(status_code=403, detail={"reason": "web_origin_required"})

    if fetch_site == "cross-site" and origin not in allowed:
        raise HTTPException(status_code=403, detail={"reason": "cross_site_forbidden"})


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        max_age=max(1, int(legacy.REFRESH_TOKEN_TTL_DAYS)) * 24 * 60 * 60,
        path="/auth/web",
        httponly=True,
        secure=_is_prod(),
        samesite="none" if _is_prod() else "lax",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path="/auth/web",
        httponly=True,
        secure=_is_prod(),
        samesite="none" if _is_prod() else "lax",
    )


def _web_payload(payload: dict[str, Any], response: Response) -> dict[str, Any]:
    data = dict(payload)
    refresh_token = str(data.pop("refresh_token", "") or "")
    data.pop("refreshToken", None)
    if not refresh_token:
        raise HTTPException(status_code=500, detail={"reason": "refresh_token_missing"})
    _set_refresh_cookie(response, refresh_token)
    return data


@router.post("/password/register")
def web_password_register(
    payload: legacy.PasswordRegisterIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _require_web_origin(request)
    return _web_payload(legacy.auth_password_register(payload, db), response)


@router.post("/password/login")
def web_password_login(
    payload: legacy.PasswordLoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _require_web_origin(request)
    return _web_payload(legacy.auth_password_login(payload, db), response)


@router.post("/email/verify_otp")
def web_email_verify_otp(
    payload: legacy.EmailOtpVerifyIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _require_web_origin(request)
    return _web_payload(legacy.auth_email_verify_otp(payload, request, db), response)


@router.post("/email/verify_link")
def web_email_verify_link(
    payload: legacy.MagicLinkVerifyIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _require_web_origin(request)
    return _web_payload(legacy.auth_email_verify_link(payload, request, db), response)


@router.post("/refresh")
def web_refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _require_web_origin(request)
    refresh_token = (request.cookies.get(REFRESH_COOKIE) or "").strip()
    if not refresh_token:
        raise HTTPException(status_code=401, detail={"reason": "missing_refresh_cookie"})
    return _web_payload(
        legacy.auth_refresh(legacy.RefreshIn(refreshToken=refresh_token), db),
        response,
    )


@router.post("/logout")
def web_logout(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_web_origin(request)
    now = now_utc()
    refresh_token = (request.cookies.get(REFRESH_COOKIE) or "").strip()
    if refresh_token:
        refresh = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token_hash == legacy._hash_token(refresh_token),
                RefreshToken.revoked_at.is_(None),
            )
            .first()
        )
        if refresh is not None:
            refresh.revoked_at = now
            db.add(refresh)

    if authorization and authorization.startswith("Bearer "):
        access_token = authorization.split(" ", 1)[1].strip()
        if access_token:
            access = (
                db.query(AppToken)
                .filter(
                    AppToken.token_hash == legacy._hash_token(access_token),
                    AppToken.revoked_at.is_(None),
                )
                .first()
            )
            if access is not None:
                access.revoked_at = now
                db.add(access)

    db.commit()
    _clear_refresh_cookie(response)
    return {"ok": True}
