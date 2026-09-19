from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.legacy import monolith
from db import get_db, now_utc
from models import AppToken, RefreshToken


router = APIRouter(prefix="/auth/web", tags=["auth-web"])
_REFRESH_COOKIE = "tore_web_refresh"
_WEB_HEADER = "X-TORE-Web"


def _require_web_request(request: Request) -> None:
    if request.headers.get(_WEB_HEADER) != "1":
        raise HTTPException(status_code=403, detail={"reason": "web_request_required"})
    origin = (request.headers.get("origin") or "").rstrip("/")
    if not origin:
        if monolith._resolved_env_name() == "PROD":
            raise HTTPException(status_code=403, detail={"reason": "origin_required"})
        return
    allowed = set(monolith._cors_origins())
    if origin not in allowed:
        raise HTTPException(status_code=403, detail={"reason": "origin_forbidden"})


def _cookie_options() -> dict[str, Any]:
    prod = monolith._resolved_env_name() == "PROD"
    return {
        "httponly": True,
        "secure": prod,
        "samesite": "none" if prod else "lax",
        "path": "/auth/web",
        "max_age": int(monolith.REFRESH_TOKEN_TTL_DAYS) * 86400,
    }


def _set_refresh_cookie(response: Response, raw_refresh: str) -> None:
    response.set_cookie(_REFRESH_COOKIE, raw_refresh, **_cookie_options())


def _clear_refresh_cookie(response: Response) -> None:
    options = _cookie_options()
    response.delete_cookie(
        _REFRESH_COOKIE,
        path=options["path"],
        secure=options["secure"],
        httponly=True,
        samesite=options["samesite"],
    )


def _sanitize_result(result: dict[str, Any], response: Response) -> dict[str, Any]:
    payload = dict(result)
    raw_refresh = str(payload.pop("refresh_token", "") or payload.pop("refreshToken", "") or "")
    if not raw_refresh:
        raise HTTPException(status_code=500, detail={"reason": "refresh_token_missing"})
    _set_refresh_cookie(response, raw_refresh)
    return payload


@router.post("/password/register")
def password_register(
    payload: monolith.PasswordRegisterIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _require_web_request(request)
    return _sanitize_result(monolith.auth_password_register(payload, db), response)


@router.post("/password/login")
def password_login(
    payload: monolith.PasswordLoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _require_web_request(request)
    return _sanitize_result(monolith.auth_password_login(payload, db), response)


@router.post("/email/verify_otp")
def email_verify_otp(
    payload: monolith.EmailOtpVerifyIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _require_web_request(request)
    return _sanitize_result(monolith.auth_email_verify_otp(payload, request, db), response)


@router.post("/email/verify_link")
def email_verify_link(
    payload: monolith.MagicLinkVerifyIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _require_web_request(request)
    return _sanitize_result(monolith.auth_email_verify_link(payload, request, db), response)


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    _require_web_request(request)
    raw_refresh = (request.cookies.get(_REFRESH_COOKIE) or "").strip()
    if not raw_refresh:
        raise HTTPException(status_code=401, detail={"reason": "refresh_cookie_missing"})
    result = monolith.auth_refresh(monolith.RefreshIn(refreshToken=raw_refresh), db)
    return _sanitize_result(result, response)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_web_request(request)
    now = now_utc()
    raw_refresh = (request.cookies.get(_REFRESH_COOKIE) or "").strip()
    if raw_refresh:
        refresh_row = db.query(RefreshToken).filter(
            RefreshToken.token_hash == monolith._hash_token(raw_refresh),
            RefreshToken.revoked_at.is_(None),
        ).first()
        if refresh_row:
            refresh_row.revoked_at = now
            db.add(refresh_row)

    if authorization and authorization.lower().startswith("bearer "):
        raw_access = authorization.split(" ", 1)[1].strip()
        access_row = db.query(AppToken).filter(
            AppToken.token_hash == monolith._hash_token(raw_access),
            AppToken.revoked_at.is_(None),
        ).first()
        if access_row:
            access_row.revoked_at = now
            db.add(access_row)

    db.commit()
    _clear_refresh_cookie(response)
    response.status_code = 204
    return response
