from __future__ import annotations

import hashlib
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import now_utc
from models import PartnerMembership, PartnerTokenRevocation


ALLOWED_ROLES_ORDER = {"bartender": 1, "manager": 2}


def ensure_partner_role(identity: dict, allowed_roles: Iterable[str]) -> None:
    role = str(identity.get("role") or "")
    if role not in set(allowed_roles):
        raise HTTPException(status_code=403, detail={"reason": "forbidden", "message": "Forbidden"})


def revoke_partner_token(db: Session, *, token: str, actor_partner_id: int) -> None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = db.query(PartnerTokenRevocation).filter(PartnerTokenRevocation.token_hash == token_hash).first()
    if row:
        return
    db.add(
        PartnerTokenRevocation(
            token_hash=token_hash,
            revoked_at=now_utc(),
            revoked_by_partner_id=actor_partner_id,
        )
    )


def ensure_partner_token_not_revoked(db: Session, *, token: Optional[str]) -> None:
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = db.query(PartnerTokenRevocation).filter(PartnerTokenRevocation.token_hash == token_hash).first()
    if row:
        raise HTTPException(status_code=403, detail={"reason": "revoked", "message": "Token revoked"})


def ensure_partner_membership_active(db: Session, *, user_id: int, bar_id: int) -> PartnerMembership:
    membership = (
        db.query(PartnerMembership)
        .filter(PartnerMembership.user_id == user_id, PartnerMembership.bar_id == bar_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=401, detail={"reason": "forbidden", "message": "Membership not found"})
    return membership
