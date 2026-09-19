from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import now_utc
from models import AppUser, Organization, OrganizationMembership, OrganizationWriteIdempotency
from app.legacy.monolith import (
    _extract_bearer_token,
    _membership_for,
    _orga_write_idem,
    _require_membership_role,
    _resolve_app_user_from_token,
    _slugify_orga_name,
    get_current_user,
    get_db,
)
from app.services.audit_service import write_audit_log
from app.services.idempotency_service import ensure_idempotency_key
from app.services.structure_lifecycle import (
    PRIVATE_STRUCTURE_VISIBILITY,
    STRUCTURE_LIFECYCLE_STATES,
    ensure_lifecycle,
    hide_structure_events,
    lifecycle_status,
    private_visibility_settings,
    set_page_published,
    structure_is_published,
    transition_lifecycle,
)
from app.services.structure_rbac import require_capability


router = APIRouter(tags=["structure-lifecycle"])


class OrgaCreateCompatIn(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    description: Optional[str] = Field(default=None, max_length=2000)
    city: Optional[str] = Field(default=None, max_length=120)
    org_type: Optional[str] = Field(default=None, max_length=64)
    website_url: Optional[str] = Field(default=None, max_length=255)
    instagram_handle: Optional[str] = Field(default=None, max_length=64)
    # Kept only for wire compatibility. Creation is always PRIVATE/SETUP.
    visibility: Literal["PUBLIC", "PRIVATE"] = "PRIVATE"
    join_mode: Literal["FOLLOW_ONLY", "OPEN_MEMBERSHIP", "REQUEST_TO_JOIN"] = "OPEN_MEMBERSHIP"


class OrgaUpdateCompatIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=140)
    city: Optional[str] = Field(default=None, max_length=120)
    type: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = Field(default=None, max_length=4000)
    instagram: Optional[str] = Field(default=None, max_length=64)
    logoUrl: Optional[str] = Field(default=None, max_length=512)
    visibility: Optional[Literal["PUBLIC", "PRIVATE"]] = None
    join_mode: Optional[Literal["FOLLOW_ONLY", "OPEN_MEMBERSHIP", "REQUEST_TO_JOIN"]] = None


class LifecycleTransitionIn(BaseModel):
    target: Literal["REQUESTED", "SETUP", "ACTIVE", "SUSPENDED", "ARCHIVED"]
    reason: str = Field(default="Transition lifecycle structure", min_length=2, max_length=280)


class LifecycleReasonIn(BaseModel):
    reason: str = Field(default="Action explicite depuis le Forum", min_length=2, max_length=280)


def _orga_payload(db: Session, row: Organization) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "slug": row.slug,
        "description": row.description,
        "city": row.city,
        "org_type": row.org_type,
        "website_url": row.website_url,
        "instagram_handle": row.instagram_handle,
        "visibility": (row.visibility or "PRIVATE").upper(),
        "join_mode": (row.join_mode or "OPEN_MEMBERSHIP").upper(),
        "lifecycle": lifecycle_status(db, row.id),
    }


def _org_by_slug(db: Session, slug: str) -> Organization:
    row = db.query(Organization).filter(Organization.slug == slug.strip()).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Structure not found")
    return row


def _org_by_id(db: Session, org_id: int) -> Organization:
    row = db.get(Organization, org_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return row


def _save_idem(db: Session, user_id: str, action: str, key: str, response: dict) -> None:
    db.add(
        OrganizationWriteIdempotency(
            actor_user_id=user_id,
            action=action,
            idempotency_key=key,
            response_json=response,
        )
    )


def _audit(
    db: Session,
    *,
    user: AppUser,
    role: str,
    action: str,
    org: Organization,
    key: str,
    payload: dict,
) -> None:
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=role,
        action=action,
        entity_type="organization",
        entity_id=str(org.id),
        event_id=None,
        committee_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={"structure_id": org.id, **payload},
    )


@router.post("/orgas")
def create_organization_private_by_default(
    payload: OrgaCreateCompatIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Backward-compatible /orgas creation with the new privacy invariant."""
    key = ensure_idempotency_key(idempotency_key)
    action = "orga_create"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem is not None:
        return idem.response_json

    org = Organization(
        name=payload.name.strip(),
        slug=_slugify_orga_name(db, payload.name.strip()),
        description=(payload.description or "").strip() or None,
        city=(payload.city or "").strip() or None,
        org_type=(payload.org_type or "").strip() or None,
        website_url=(payload.website_url or "").strip() or None,
        instagram_handle=(payload.instagram_handle or "").strip() or None,
        visibility="PRIVATE",
        visibility_settings_json=private_visibility_settings(),
        join_mode=(payload.join_mode or "OPEN_MEMBERSHIP").upper(),
        created_by_user_id=user.id,
        created_at=now_utc(),
    )
    db.add(org)
    db.flush()
    ensure_lifecycle(db, org.id, initial_status="SETUP")

    stamp = now_utc()
    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role="OWNER",
        status="ACTIVE",
        joined_at=stamp,
        starts_at=stamp,
        validation_source="OWNER_CREATION",
        validated_by_user_id=user.id,
        validated_at=stamp,
        updated_at=stamp,
        created_by_user_id=user.id,
        created_at=stamp,
    )
    db.add(membership)

    response = {"orga": _orga_payload(db, org), "role": "OWNER", "status": "ACTIVE"}
    _save_idem(db, user.id, action, key, response)
    _audit(
        db,
        user=user,
        role="OWNER",
        action="organization.create",
        org=org,
        key=key,
        payload={
            "name": org.name,
            "org_type": org.org_type,
            "city": org.city,
            "lifecycle": "SETUP",
            "visibility": "PRIVATE",
            "visibility_defaults": PRIVATE_STRUCTURE_VISIBILITY,
            "requested_visibility": payload.visibility,
        },
    )
    db.commit()
    return response


@router.get("/orgas/{org_id}")
def get_organization_compat(
    org_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    org = _org_by_id(db, org_id)
    if structure_is_published(db, org):
        return _orga_payload(db, org)

    user = None
    token = _extract_bearer_token(authorization)
    if token:
        user = _resolve_app_user_from_token(token, db)
    if user is None or _membership_for(db, org_id=org.id, user_id=user.id) is None:
        # Non-public structures are deliberately indistinguishable from absent structures.
        raise HTTPException(status_code=404, detail="Organization not found")
    return _orga_payload(db, org)


@router.put("/orgas/{org_id}")
def update_organization_compat(
    org_id: int,
    payload: OrgaUpdateCompatIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    actor = _require_membership_role(db, org_id=org_id, user_id=user.id, min_role="MANAGER")
    key = ensure_idempotency_key(idempotency_key)
    action = f"orga_update:{org_id}"
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem is not None:
        return idem.response_json

    org = _org_by_id(db, org_id)
    if lifecycle_status(db, org.id) == "ARCHIVED":
        raise HTTPException(status_code=409, detail={"reason": "STRUCTURE_ARCHIVED"})

    if payload.name is not None:
        cleaned_name = payload.name.strip()
        if not cleaned_name:
            raise HTTPException(status_code=400, detail={"reason": "invalid_name"})
        org.name = cleaned_name
    if payload.city is not None:
        org.city = payload.city.strip() or None
    if payload.type is not None:
        org.org_type = payload.type.strip() or None
    if payload.description is not None:
        org.description = payload.description.strip() or None
    if payload.instagram is not None:
        org.instagram_handle = payload.instagram.strip() or None
    if payload.logoUrl is not None:
        # Keep the historical /orgas wire behavior untouched.
        org.website_url = payload.logoUrl.strip() or None
    if payload.join_mode is not None:
        org.join_mode = payload.join_mode.upper()
    if payload.visibility == "PUBLIC" and not structure_is_published(db, org):
        raise HTTPException(
            status_code=409,
            detail={"reason": "EXPLICIT_STRUCTURE_PUBLICATION_REQUIRED"},
        )
    if payload.visibility == "PRIVATE":
        set_page_published(org, False)

    response = _orga_payload(db, org)
    _save_idem(db, user.id, action, key, response)
    _audit(
        db,
        user=user,
        role=actor.role,
        action="orga_updated",
        org=org,
        key=key,
        payload={"scope": f"orga:{org_id}", "lifecycle": lifecycle_status(db, org.id)},
    )
    db.commit()
    return response


def _lifecycle_response(db: Session, org: Organization) -> dict:
    return {
        "organizationId": org.id,
        "slug": org.slug,
        "lifecycle": lifecycle_status(db, org.id),
        "visibility": (org.visibility or "PRIVATE").upper(),
        "published": structure_is_published(db, org),
        "visibilitySettings": org.visibility_settings_json if isinstance(org.visibility_settings_json, dict) else {},
    }


def _run_lifecycle_mutation(
    *,
    db: Session,
    org: Organization,
    user: AppUser,
    actor_role: str,
    action: str,
    key: str,
    reason: str,
    target: Optional[str] = None,
    publish: Optional[bool] = None,
) -> dict:
    idem = _orga_write_idem(db, actor_user_id=user.id, action=action, idempotency_key=key)
    if idem is not None:
        return idem.response_json

    ensure_lifecycle(db, org.id, initial_status="ACTIVE")
    before = lifecycle_status(db, org.id)
    hidden_events = 0

    if target is not None:
        try:
            source, destination = transition_lifecycle(db, org.id, target)
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "reason": str(exc),
                    "current": before,
                    "target": target.upper(),
                },
            ) from exc
        if destination in {"SUSPENDED", "ARCHIVED"}:
            set_page_published(org, False)
            hidden_events = hide_structure_events(db, org.id)
    else:
        source = before
        destination = before

    if publish is True:
        current = lifecycle_status(db, org.id)
        if current == "SETUP":
            try:
                source, destination = transition_lifecycle(db, org.id, "ACTIVE")
            except ValueError as exc:
                raise HTTPException(status_code=409, detail={"reason": str(exc), "current": current, "target": "ACTIVE"}) from exc
        elif current != "ACTIVE":
            raise HTTPException(
                status_code=409,
                detail={"reason": "INVALID_LIFECYCLE_TRANSITION", "current": current, "target": "ACTIVE"},
            )
        set_page_published(org, True)
    elif publish is False:
        current = lifecycle_status(db, org.id)
        if current != "ACTIVE":
            raise HTTPException(
                status_code=409,
                detail={"reason": "INVALID_LIFECYCLE_TRANSITION", "current": current, "target": current},
            )
        set_page_published(org, False)

    db.flush()
    response = _lifecycle_response(db, org)
    _save_idem(db, user.id, action, key, response)
    _audit(
        db,
        user=user,
        role=actor_role,
        action=action,
        org=org,
        key=key,
        payload={
            "from": source,
            "to": lifecycle_status(db, org.id),
            "published": response["published"],
            "hidden_events": hidden_events,
            "reason": reason,
        },
    )
    db.commit()
    return response


@router.get("/forum/structures/{slug}/lifecycle")
def get_structure_lifecycle(
    slug: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _org_by_slug(db, slug)
    require_capability(db, org.id, user, "structure.read")
    return _lifecycle_response(db, org)


@router.post("/forum/structures/{slug}/publish")
def publish_structure(
    slug: str,
    payload: LifecycleReasonIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    org = _org_by_slug(db, slug)
    actor = require_capability(db, org.id, user, "structure.publish")
    return _run_lifecycle_mutation(
        db=db,
        org=org,
        user=user,
        actor_role=actor.role,
        action=f"forum.structure.publish:{org.id}",
        key=ensure_idempotency_key(idempotency_key),
        reason=payload.reason,
        publish=True,
    )


@router.post("/forum/structures/{slug}/unpublish")
def unpublish_structure(
    slug: str,
    payload: LifecycleReasonIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    org = _org_by_slug(db, slug)
    actor = require_capability(db, org.id, user, "structure.publish")
    return _run_lifecycle_mutation(
        db=db,
        org=org,
        user=user,
        actor_role=actor.role,
        action=f"forum.structure.unpublish:{org.id}",
        key=ensure_idempotency_key(idempotency_key),
        reason=payload.reason,
        publish=False,
    )


@router.post("/forum/structures/{slug}/suspend")
def suspend_structure(
    slug: str,
    payload: LifecycleReasonIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    org = _org_by_slug(db, slug)
    actor = require_capability(db, org.id, user, "structure.publish")
    return _run_lifecycle_mutation(
        db=db,
        org=org,
        user=user,
        actor_role=actor.role,
        action=f"forum.structure.suspend:{org.id}",
        key=ensure_idempotency_key(idempotency_key),
        reason=payload.reason,
        target="SUSPENDED",
    )


@router.post("/forum/structures/{slug}/archive")
def archive_structure(
    slug: str,
    payload: LifecycleReasonIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    org = _org_by_slug(db, slug)
    actor = require_capability(db, org.id, user, "structure.publish")
    return _run_lifecycle_mutation(
        db=db,
        org=org,
        user=user,
        actor_role=actor.role,
        action=f"forum.structure.archive:{org.id}",
        key=ensure_idempotency_key(idempotency_key),
        reason=payload.reason,
        target="ARCHIVED",
    )


@router.post("/forum/structures/{slug}/lifecycle")
def transition_structure_lifecycle(
    slug: str,
    payload: LifecycleTransitionIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    org = _org_by_slug(db, slug)
    actor = require_capability(db, org.id, user, "structure.publish")
    target = payload.target.upper()
    if target not in STRUCTURE_LIFECYCLE_STATES:
        raise HTTPException(status_code=422, detail={"reason": "UNKNOWN_LIFECYCLE_STATE"})
    return _run_lifecycle_mutation(
        db=db,
        org=org,
        user=user,
        actor_role=actor.role,
        action=f"forum.structure.lifecycle:{org.id}:{target}",
        key=ensure_idempotency_key(idempotency_key),
        reason=payload.reason,
        target=target,
    )
