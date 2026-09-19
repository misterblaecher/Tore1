"""Organization compatibility helpers extracted from the legacy runtime."""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from db import now_utc
from models import (
    Organization,
    OrganizationMembership,
    OrganizationWriteIdempotency,
)


ORGA_ROLE_RANK = {
    "FOLLOWER": 0,
    "ALUMNI": 1,
    "MEMBER": 1,
    "STAFF": 2,
    "TRESORIER": 3,
    "BUREAU": 3,
    "PRESIDENT": 4,
    "MANAGER": 4,
    "OWNER": 5,
}


def membership_for(
    db: Session,
    *,
    org_id: int,
    user_id: str,
) -> Optional[OrganizationMembership]:
    now = now_utc()
    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == "ACTIVE",
            OrganizationMembership.revoked_at.is_(None),
            or_(
                OrganizationMembership.starts_at.is_(None),
                OrganizationMembership.starts_at <= now,
            ),
            or_(
                OrganizationMembership.ends_at.is_(None),
                OrganizationMembership.ends_at > now,
            ),
        )
        .first()
    )


def require_membership_role(
    db: Session,
    *,
    org_id: int,
    user_id: str,
    min_role: str,
) -> OrganizationMembership:
    membership = membership_for(db, org_id=org_id, user_id=user_id)
    if not membership:
        raise HTTPException(403, "Forbidden")
    if ORGA_ROLE_RANK.get(membership.role, -1) < ORGA_ROLE_RANK.get(min_role, 999):
        raise HTTPException(403, "Forbidden")
    return membership


def organization_write_idempotency(
    db: Session,
    *,
    actor_user_id: str,
    action: str,
    idempotency_key: str,
) -> Optional[OrganizationWriteIdempotency]:
    return (
        db.query(OrganizationWriteIdempotency)
        .filter(
            OrganizationWriteIdempotency.actor_user_id == actor_user_id,
            OrganizationWriteIdempotency.action == action,
            OrganizationWriteIdempotency.idempotency_key == idempotency_key,
        )
        .first()
    )


def slugify_organization_name(db: Session, base_name: str) -> str:
    cleaned = "".join(
        ch.lower() if ch.isalnum() else "-"
        for ch in base_name
    ).strip("-")
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    root = cleaned[:120] or f"orga-{secrets.token_hex(2)}"
    slug = root
    idx = 1
    while db.scalar(select(Organization.id).where(Organization.slug == slug)) is not None:
        idx += 1
        slug = f"{root}-{idx}"
    return slug


# Stable migration aliases for the historical names.
_membership_for = membership_for
_require_membership_role = require_membership_role
_orga_write_idem = organization_write_idempotency
_slugify_orga_name = slugify_organization_name

__all__ = [
    "ORGA_ROLE_RANK",
    "membership_for",
    "require_membership_role",
    "organization_write_idempotency",
    "slugify_organization_name",
    "_membership_for",
    "_require_membership_role",
    "_orga_write_idem",
    "_slugify_orga_name",
]
