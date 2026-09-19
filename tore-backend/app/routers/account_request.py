from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import timedelta
from typing import Iterator

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.services.rate_limit_service import standard_rate_limit_http_exception
from app.services.rate_limit_service import RateLimitExceeded, enforce_rate_limit
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from db import now_utc
from models import AccountRequest

router = APIRouter(tags=["public-account"])

ROLE_VALUES = {"student", "committee", "bar", "dj"}
_PHONE_CLEAN_RE = re.compile(r"[^0-9+]")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


from app.deps.db import get_db


class AccountRequestIn(BaseModel):
    name: str
    email: str
    phone: str
    is_whatsapp: bool = False
    role: str
    committee_name: str | None = None
    source: str | None = "tore_site"
    utm: dict | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Le nom doit contenir au moins 2 caractères")
        return cleaned

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ROLE_VALUES:
            raise ValueError("Rôle invalide")
        return normalized

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not _EMAIL_RE.match(cleaned):
            raise ValueError("Email invalide")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        stripped = value.strip()
        normalized = _PHONE_CLEAN_RE.sub("", stripped)
        if normalized.startswith("00"):
            normalized = "+" + normalized[2:]
        if not normalized.startswith("+"):
            normalized = "+" + normalized.lstrip("+")
        digits = normalized[1:]
        if not digits.isdigit() or len(digits) < 8 or len(digits) > 15:
            raise ValueError("Numéro de téléphone invalide")
        return normalized

    @field_validator("committee_name")
    @classmethod
    def normalize_committee_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class AccountRequestOut(BaseModel):
    ok: bool
    id: int
    message: str


class ContactIn(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    company: str | None = None
    role: str
    type: str
    city: str
    subject: str
    message: str

    @field_validator("email")
    @classmethod
    def validate_contact_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not _EMAIL_RE.match(cleaned):
            raise ValueError("Email invalide")
        return cleaned

    @field_validator("first_name", "last_name", "role", "type", "city", "subject", "message")
    @classmethod
    def validate_contact_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Champ requis")
        return cleaned

    @field_validator("message")
    @classmethod
    def validate_contact_message(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 10:
            raise ValueError("Message trop court")
        return cleaned[:8000]


class ContactOut(BaseModel):
    ok: bool
    message: str


class AccountRequestAdminRow(BaseModel):
    id: int
    created_at: str
    name: str
    email: str
    phone: str
    is_whatsapp: bool
    source: str | None
    status: str


class AccountRequestAdminListOut(BaseModel):
    items: list[AccountRequestAdminRow]
    next_cursor: int | None = None


class AccountRequestAdminPatchIn(BaseModel):
    status: str = "processed"

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"pending", "processed"}:
            raise ValueError("status invalide")
        return cleaned


def _require_admin_api_key(x_admin_api_key: str | None = Header(default=None, alias="X-Admin-Api-Key")) -> None:
    expected = (os.getenv("ADMIN_API_KEY") or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail={"reason": "admin_api_disabled", "message": "ADMIN_API_KEY non configurée"})
    if (x_admin_api_key or "").strip() != expected:
        raise HTTPException(status_code=401, detail={"reason": "invalid_admin_key", "message": "Clé admin invalide"})


@router.post("/public/account-request", response_model=AccountRequestOut)
def create_account_request(
    payload: AccountRequestIn,
    request: Request,
    db: Session = Depends(get_db),
):
    if payload.role == "committee" and not payload.committee_name:
        raise HTTPException(status_code=400, detail={"message": "Le nom du comité est requis pour ce rôle"})
    if payload.role != "committee":
        payload.committee_name = None

    window_minutes = int(os.getenv("ACCOUNT_RATE_LIMIT_WINDOW", os.getenv("RATE_LIMIT_WINDOW", "10")))
    max_attempts = int(os.getenv("ACCOUNT_RATE_LIMIT_MAX", os.getenv("RATE_LIMIT_MAX", "3")))
    email_cooldown_minutes = int(os.getenv("ACCOUNT_EMAIL_COOLDOWN_MIN", "2"))

    user_agent = (request.headers.get("user-agent") or "")[:500]
    forwarded_for = request.headers.get("x-forwarded-for") or ""
    raw_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else "")
    fingerprint = f"{raw_ip}|{user_agent}" if raw_ip or user_agent else "unknown"
    ip_hash = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    now = now_utc()
    window_start = now - timedelta(minutes=window_minutes)
    recent_attempts = (
        db.query(AccountRequest)
        .filter(AccountRequest.ip_hash == ip_hash, AccountRequest.user_agent == user_agent, AccountRequest.created_at >= window_start)
        .order_by(AccountRequest.created_at.asc())
        .all()
    )
    if len(recent_attempts) >= max_attempts:
        oldest = recent_attempts[0]
        retry_after_seconds = max(1, int((oldest.created_at + timedelta(minutes=window_minutes) - now).total_seconds()))
        raise standard_rate_limit_http_exception(scope="public_account_request", retry_after_seconds=retry_after_seconds)

    email_cutoff = now - timedelta(minutes=email_cooldown_minutes)
    duplicate = (
        db.query(AccountRequest)
        .filter(
            AccountRequest.email == payload.email,
            AccountRequest.phone == payload.phone,
            AccountRequest.created_at >= email_cutoff,
        )
        .first()
    )
    if duplicate:
        retry_after_seconds = max(1, int((duplicate.created_at + timedelta(minutes=email_cooldown_minutes) - now).total_seconds()))
        raise standard_rate_limit_http_exception(scope="public_account_request_email", retry_after_seconds=retry_after_seconds)

    row = AccountRequest(
        name=payload.name,
        email=str(payload.email),
        phone=payload.phone,
        is_whatsapp=payload.is_whatsapp,
        role=payload.role,
        committee_name=payload.committee_name,
        source=(payload.source or "tore_site")[:120],
        status="pending",
        ip_hash=ip_hash,
        user_agent=user_agent or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    notify_to = (os.getenv("CONTACT_TO_EMAIL") or os.getenv("SMTP_USERNAME") or "").strip()
    if notify_to:
        try:
            from app.legacy.monolith import _send_email

            _send_email(
                subject=f"Nouvelle demande d’accès TORÈ · {payload.role}",
                body=(
                    f"Nom : {payload.name}\nEmail : {payload.email}\nTéléphone : {payload.phone}\n"
                    f"Rôle : {payload.role}\nComité : {payload.committee_name or '-'}\n"
                    f"Source : {payload.source or 'tore_site'}\nDemande : {row.id}\n"
                ),
                to_email=notify_to,
                reply_to=payload.email,
            )
        except Exception:
            logging.exception("account_request.notify.failed request_id=%s", row.id)

    return AccountRequestOut(ok=True, id=row.id, message="Account request created")


@router.post("/public/contact", response_model=ContactOut)
def create_contact_message(payload: ContactIn, request: Request):
    actor_ip = request.client.host if request.client else "unknown"
    try:
        enforce_rate_limit("public_contact", actor_ip)
    except RateLimitExceeded as exc:
        raise standard_rate_limit_http_exception(scope=exc.scope, retry_after_seconds=exc.retry_after_seconds)

    notify_to = (os.getenv("CONTACT_TO_EMAIL") or os.getenv("SMTP_USERNAME") or "").strip()
    if not notify_to:
        raise HTTPException(status_code=503, detail={"reason": "email_provider_missing"})

    from app.legacy.monolith import _send_email

    _send_email(
        subject=f"Contact TORÈ · {payload.subject}",
        body=(
            f"Nom : {payload.first_name} {payload.last_name}\nEmail : {payload.email}\n"
            f"Téléphone : {payload.phone or '-'}\nEntreprise / structure : {payload.company or '-'}\n"
            f"Rôle : {payload.role}\nType : {payload.type}\nVille : {payload.city}\n"
            f"Sujet : {payload.subject}\n\n{payload.message}\n"
        ),
        to_email=notify_to,
        reply_to=payload.email,
    )
    return ContactOut(ok=True, message="Contact message sent")


@router.get("/admin/account-requests", response_model=AccountRequestAdminListOut, tags=["admin-account"])
def list_account_requests(
    status: str = "pending",
    limit: int = 50,
    cursor: int | None = None,
    _: None = Depends(_require_admin_api_key),
    db: Session = Depends(get_db),
):
    status_value = status.strip().lower()
    if status_value == "new":
        status_value = "pending"
    if status_value not in {"pending", "processed"}:
        raise HTTPException(status_code=400, detail={"reason": "invalid_status"})

    safe_limit = max(1, min(limit, 200))
    query = db.query(AccountRequest).filter(AccountRequest.status == status_value)
    if cursor is not None:
        query = query.filter(AccountRequest.id < cursor)
    rows = query.order_by(AccountRequest.id.desc()).limit(safe_limit + 1).all()

    has_more = len(rows) > safe_limit
    page = rows[:safe_limit]
    next_cursor = page[-1].id if has_more and page else None

    return AccountRequestAdminListOut(
        items=[
            AccountRequestAdminRow(
                id=row.id,
                created_at=row.created_at.isoformat(),
                name=row.name,
                email=row.email,
                phone=row.phone,
                is_whatsapp=bool(row.is_whatsapp),
                source=row.source,
                status="pending" if (row.status or "").lower() == "new" else row.status,
            )
            for row in page
        ],
        next_cursor=next_cursor,
    )


@router.patch("/admin/account-requests/{request_id}", response_model=AccountRequestAdminRow, tags=["admin-account"])
def patch_account_request(
    request_id: int,
    payload: AccountRequestAdminPatchIn,
    _: None = Depends(_require_admin_api_key),
    db: Session = Depends(get_db),
):
    row = db.get(AccountRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail={"reason": "not_found"})
    row.status = payload.status
    db.add(row)
    db.commit()
    db.refresh(row)
    return AccountRequestAdminRow(
        id=row.id,
        created_at=row.created_at.isoformat(),
        name=row.name,
        email=row.email,
        phone=row.phone,
        is_whatsapp=bool(row.is_whatsapp),
        source=row.source,
        status=row.status,
    )
