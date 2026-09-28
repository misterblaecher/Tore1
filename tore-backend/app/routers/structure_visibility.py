from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import AppUser, Organization, OrganizationWriteIdempotency
from app.legacy.monolith import _orga_write_idem, get_current_user
from app.deps.db import get_db
from app.routers.forum import _visibility_settings
from app.services.audit_service import write_audit_log
from app.services.idempotency_service import ensure_idempotency_key
from app.services.structure_lifecycle import lifecycle_status
from app.services.structure_rbac import require_capability


router = APIRouter(prefix="/forum", tags=["forum"])

VisibilityLevel = Literal[
    "PUBLIC",
    "PRIVATE",
    "TORE_USERS",
    "STRUCTURE_MEMBERS",
    "STAFF",
    "OFFICE",
    "TREASURY",
    "ADMINS",
]


class VisibilityPatchPrivateIn(BaseModel):
    page: Optional[VisibilityLevel] = None
    description: Optional[VisibilityLevel] = None
    contact: Optional[VisibilityLevel] = None
    events: Optional[VisibilityLevel] = None
    members: Optional[VisibilityLevel] = None
    albums: Optional[VisibilityLevel] = None
    documents: Optional[VisibilityLevel] = None
    folklore: Optional[VisibilityLevel] = None
    stats: Optional[VisibilityLevel] = None
    confirm_public_finance: bool = False


def _org_by_slug(db: Session, slug: str) -> Organization:
    org = db.query(Organization).filter(Organization.slug == slug.strip()).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Structure not found")
    return org


@router.patch("/structures/{slug}/visibility")
def patch_visibility_private_safe(
    slug: str,
    payload: VisibilityPatchPrivateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Change block visibility without ever publishing the Structure implicitly.

    `page=PUBLIC` only prepares the page block. The organization-level PUBLIC bit is
    controlled exclusively by the explicit publish lifecycle action.
    """
    org = _org_by_slug(db, slug)
    actor = require_capability(db, org.id, user, "visibility.manage")
    key = ensure_idempotency_key(idempotency_key)
    action = f"forum_visibility_patch:{org.id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem is not None:
        return idem.response_json

    if payload.stats == "PUBLIC":
        # Publishing potentially sensitive statistics requires both visibility control
        # and finance access. A communication-only role must never expose finance.
        require_capability(db, org.id, user, "finance.read")
        if not payload.confirm_public_finance:
            raise HTTPException(
                status_code=400,
                detail={"reason": "PUBLIC_FINANCE_CONFIRMATION_REQUIRED"},
            )

    settings = _visibility_settings(org)
    changes = payload.model_dump(exclude_none=True, exclude={"confirm_public_finance"})
    for name, value in changes.items():
        settings[name] = value
    org.visibility_settings_json = settings

    status = lifecycle_status(db, org.id)
    if status != "ACTIVE" or settings["page"] != "PUBLIC":
        org.visibility = "PRIVATE"
    # Intentionally never flip PRIVATE -> PUBLIC here. That requires /publish.

    response = {
        "settings": settings,
        "structureVisibility": (org.visibility or "PRIVATE").upper(),
        "lifecycle": status,
        "published": status == "ACTIVE" and (org.visibility or "PRIVATE").upper() == "PUBLIC" and settings["page"] == "PUBLIC",
    }
    db.add(
        OrganizationWriteIdempotency(
            actor_user_id=user.id,
            action=action,
            idempotency_key=key,
            response_json=response,
        )
    )
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="forum.visibility.patch",
        entity_type="organization",
        entity_id=str(org.id),
        event_id=None,
        committee_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={
            "structure_id": org.id,
            "settings": settings,
            "changes": changes,
            "lifecycle": status,
            "published": response["published"],
        },
    )
    db.commit()
    return response
