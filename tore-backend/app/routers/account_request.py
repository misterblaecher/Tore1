from __future__ import annotations

import hashlib
import os
import re
from datetime import timedelta
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from db import now_utc
from models import AccountRequest

router = APIRouter(tags=["public-account"])

ROLE_VALUES = {"student", "committee", "bar", "dj"}
_PHONE_CLEAN_RE = re.compile(r"[^0-9+]")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


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
    attempts = (
        db.query(AccountRequest)
        .filter(AccountRequest.ip_hash == ip_hash, AccountRequest.user_agent == user_agent, AccountRequest.created_at >= window_start)
        .count()
    )
    if attempts >= max_attempts:
        raise HTTPException(status_code=429, detail={"message": "Trop de requêtes, réessayez dans quelques minutes."})

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
        raise HTTPException(status_code=429, detail={"message": "Une demande récente existe déjà pour cet email."})

    row = AccountRequest(
        name=payload.name,
        email=str(payload.email),
        phone=payload.phone,
        is_whatsapp=payload.is_whatsapp,
        role=payload.role,
        committee_name=payload.committee_name,
        source=(payload.source or "tore_site")[:120],
        status="new",
        ip_hash=ip_hash,
        user_agent=user_agent or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return AccountRequestOut(ok=True, id=row.id, message="Account request created")
