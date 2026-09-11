from __future__ import annotations

"""Production-authority Forum API.

This router is additive while the frontend migration is in progress.  It reuses
TORÈ AppUser, Organization, OrganizationMembership and Event.  Every private
query is scoped by the resolved Organization and re-authorized server-side.
"""

import hashlib
import re
import secrets
from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from db import now_utc
from models import (
    AppUser,
    AuditLog,
    Entry,
    EntryScanLog,
    Event,
    EventRuntimeState,
    Organization,
    OrganizationMembership,
    OrganizationWriteIdempotency,
    OrgaPost,
    StructureAlbum,
    StructureDiscussionCategory,
    StructureDiscussionChannel,
    StructureDiscussionPost,
    StructureDocument,
    StructurePage,
)
from app.forum_models import (
    AccountingEntry,
    EventPublicSummary,
    EventStructure,
    ForumEventLifecycle,
    OrgaPostPublication,
    StructureAlbumMedia,
    StructureAuditContext,
    StructureClaim,
    StructureDocumentVersion,
    StructureGovernance,
    StructureInvitation,
    StructureMediaAsset,
    StructurePublicPage,
    StructureRole,
    StructureRoleAssignment,
    StructurePageVersion,
    VisibilityPolicy,
)
from app.legacy.monolith import get_current_user, get_db
from app.schemas.forum_backend import (
    AccountingEntryCreateIn,
    AccountingEntryPatchIn,
    AlbumCreateIn,
    AlbumPatchIn,
    ChannelCreateIn,
    ChannelPatchIn,
    ClaimCreateIn,
    ClaimReviewIn,
    DocumentCreateIn,
    EventCreateIn,
    EventPatchIn,
    EventTransitionIn,
    FolklorePageCreateIn,
    FolklorePagePatchIn,
    FolkloreRestoreIn,
    InvitationAcceptIn,
    InvitationCreateIn,
    MediaOrderIn,
    MemberPatchIn,
    OwnershipTransferIn,
    PublicPagePatchIn,
    PublicPostCreateIn,
    PublicPostPatchIn,
    RoleCreateIn,
    RoleOut,
    RolePatchIn,
    StructureCreateIn,
    StructureOut,
    StructurePatchIn,
    VisibilityPolicyIn,
)
from app.services.forum_authorization import (
    ALL_PERMISSIONS,
    AuthorizationContext,
    AuthorizationService,
    VisibilityService,
    normalize_visibility,
)
from app.services.forum_audit import write_structure_audit
from app.services.forum_domain import AccountingService, EventLifecycleService, RoleService, StructureService
from app.services.forum_storage import get_forum_storage
from app.services.idempotency_service import ensure_idempotency_key
from app.services.rate_limit_service import RateLimitExceeded, enforce_rate_limit, standard_rate_limit_http_exception


router = APIRouter(prefix="/forum/v2", tags=["forum-v2"])


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:150] or "structure"


def _organization(db: Session, slug: str, *, bootstrap: bool = True) -> Organization:
    org = db.query(Organization).filter(func.lower(Organization.slug) == slug.strip().lower()).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Structure not found")
    if bootstrap and AuthorizationService.ensure_foundation(db, org):
        # Commit only the compatibility bootstrap before the caller starts its
        # business transaction.  Normal authorization never trusts client scope.
        db.commit()
        db.refresh(org)
    return org


def _public_org(db: Session, slug: str) -> tuple[Organization, StructureGovernance, StructurePublicPage]:
    org = _organization(db, slug)
    governance = db.get(StructureGovernance, org.id)
    page = db.get(StructurePublicPage, org.id)
    if governance is None or governance.status != "ACTIVE" or page is None or page.status != "PUBLISHED":
        raise HTTPException(status_code=404, detail="Structure not found")
    return org, governance, page


def _ctx(db: Session, org: Organization, user: AppUser, permission: Optional[str] = None) -> AuthorizationContext:
    return AuthorizationService.require_permission(db, org, user, permission) if permission else AuthorizationService.context(db, org, user)


def _idem(db: Session, user: AppUser, action: str, raw_key: Optional[str]) -> tuple[str, Optional[dict[str, Any]]]:
    key = ensure_idempotency_key(raw_key)
    row = db.query(OrganizationWriteIdempotency).filter(
        OrganizationWriteIdempotency.actor_user_id == user.id,
        OrganizationWriteIdempotency.action == action,
        OrganizationWriteIdempotency.idempotency_key == key,
    ).first()
    return key, row.response_json if row else None


def _save_idem(db: Session, user: AppUser, action: str, key: str, response: dict[str, Any]) -> None:
    db.add(OrganizationWriteIdempotency(
        actor_user_id=user.id,
        action=action,
        idempotency_key=key,
        response_json=response,
    ))


def _limit(scope: str, actor: str) -> None:
    try:
        enforce_rate_limit(scope, actor)
    except RateLimitExceeded as exc:
        raise standard_rate_limit_http_exception(exc.scope, exc.retry_after_seconds) from exc


def _role_out(role: StructureRole) -> dict[str, Any]:
    return {
        "id": role.id,
        "name": role.name,
        "system_role": bool(role.system_role),
        "audience_level": role.audience_level,
        "permissions": list(role.permissions_json or []),
    }


def _member_out(db: Session, membership: OrganizationMembership) -> dict[str, Any]:
    user = db.get(AppUser, membership.user_id)
    assignment = db.query(StructureRoleAssignment).filter_by(membership_id=membership.id).first()
    role = db.get(StructureRole, assignment.role_id) if assignment else None
    meta = membership.metadata_json if isinstance(membership.metadata_json, dict) else {}
    return {
        "id": membership.id,
        "userId": membership.user_id,
        "displayName": user.display_name if user else "Membre TORÈ",
        "avatarUrl": user.avatar_url if user else None,
        "role": _role_out(role) if role else None,
        "status": membership.status,
        "title": meta.get("forum_title"),
        "team": meta.get("forum_team"),
        "mandateStart": membership.starts_at.isoformat() if membership.starts_at else None,
        "mandateEnd": membership.ends_at.isoformat() if membership.ends_at else None,
        "publicProfile": (membership.visibility or "PRIVATE").upper() == "PUBLIC",
    }


def _event_scoped(db: Session, org_id: int, event_id: int) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, detail="Event not found")
    relation = db.query(EventStructure).filter_by(event_id=event_id, organization_id=org_id).first()
    legacy = event.host_type == "orga" and event.host_id == str(org_id)
    if relation is None and not legacy:
        # 404 deliberately hides cross-tenant existence.
        raise HTTPException(404, detail="Event not found")
    if relation is None and legacy:
        db.add(EventStructure(event_id=event.id, organization_id=org_id, role="HOST", created_at=now_utc()))
        db.flush()
    return event


def _event_out(db: Session, org_id: int, event: Event) -> dict[str, Any]:
    lifecycle = EventLifecycleService.ensure(db, organization_id=org_id, event=event)
    return {
        "id": event.id,
        "name": event.name,
        "startsAt": event.starts_at.isoformat() if event.starts_at else None,
        "endsAt": event.ends_at.isoformat() if event.ends_at else None,
        "venue": event.venue,
        "city": event.city,
        "description": event.public_description,
        "visibility": event.visibility,
        "publicationStatus": event.publication_status,
        "capacity": event.capacity,
        "entryPriceCents": event.entry_price_cents,
        "lifecycle": lifecycle.status,
    }


def _document_scoped(db: Session, org_id: int, document_id: int, *, include_archived: bool = False) -> StructureDocument:
    doc = db.get(StructureDocument, document_id)
    if doc is None or doc.organization_id != org_id or (doc.archived_at is not None and not include_archived):
        raise HTTPException(404, detail="Document not found")
    return doc


def _channel_scoped(db: Session, org_id: int, channel_id: int) -> StructureDiscussionChannel:
    channel = db.get(StructureDiscussionChannel, channel_id)
    if channel is None or channel.organization_id != org_id:
        raise HTTPException(404, detail="Channel not found")
    return channel


def _album_scoped(db: Session, org_id: int, album_id: int) -> StructureAlbum:
    album = db.get(StructureAlbum, album_id)
    if album is None or album.organization_id != org_id or album.archived_at is not None:
        raise HTTPException(404, detail="Album not found")
    return album


def _page_scoped(db: Session, org_id: int, page_id: int) -> StructurePage:
    page = db.get(StructurePage, page_id)
    if page is None or page.organization_id != org_id:
        raise HTTPException(404, detail="Page not found")
    return page


def _structure_out(db: Session, org: Organization, *, expose_owner: bool) -> dict[str, Any]:
    governance = db.get(StructureGovernance, org.id)
    public_page = db.get(StructurePublicPage, org.id)
    return {
        "id": org.id,
        "slug": org.slug,
        "name": org.name,
        "type": org.org_type,
        "description": org.description,
        "city": org.city,
        "status": governance.status if governance else "SETUP",
        "public_page_status": public_page.status if public_page else "DRAFT",
        "owner_user_id": governance.owner_user_id if (governance and expose_owner) else None,
        "primary_color": org.primary_color,
    }


@router.get("/health")
def forum_backend_health():
    return {"ok": True, "authority": "server", "version": "foundation-1"}


# ---------------------------------------------------------------------------
# Structures / public lifecycle / members / roles
# ---------------------------------------------------------------------------

@router.post("/structures", response_model=StructureOut, status_code=201)
def create_structure(payload: StructureCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _limit("forum_structure_create", user.id)
    base_slug = _slugify(payload.slug or payload.name)
    slug = base_slug
    suffix = 2
    while db.query(Organization).filter(func.lower(Organization.slug) == slug.lower()).first():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    now = now_utc()
    org = Organization(
        name=payload.name.strip(), slug=slug, description=payload.description, city=payload.city,
        org_type=payload.org_type.strip().upper(), visibility="PRIVATE", join_mode="INVITE_ONLY",
        created_by_user_id=user.id, created_at=now,
    )
    db.add(org)
    db.flush()
    membership = OrganizationMembership(
        organization_id=org.id, user_id=user.id, role="OWNER", status="ACTIVE",
        joined_at=now, starts_at=now, visibility="PRIVATE", created_at=now,
        created_by_user_id=user.id, validated_by_user_id=user.id, validated_at=now,
    )
    db.add(membership)
    db.flush()
    AuthorizationService.ensure_foundation(db, org)
    governance = db.get(StructureGovernance, org.id)
    if governance:
        governance.owner_user_id = user.id
        governance.status = "SETUP"
        governance.updated_at = now
    write_structure_audit(
        db, organization_id=org.id, actor_user_id=user.id, actor_role="Owner",
        action="forum.structure.create", resource_type="organization", resource_id=str(org.id),
        before=None, after={"name": org.name, "slug": org.slug, "status": "SETUP"},
    )
    db.commit()
    return _structure_out(db, org, expose_owner=True)


@router.get("/me/structures")
def my_structures(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    stamp = now_utc()
    rows = db.query(Organization).join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id).filter(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.status == "ACTIVE",
        OrganizationMembership.revoked_at.is_(None),
        or_(OrganizationMembership.starts_at.is_(None), OrganizationMembership.starts_at <= stamp),
        or_(OrganizationMembership.ends_at.is_(None), OrganizationMembership.ends_at > stamp),
    ).order_by(Organization.name).all()
    items = []
    for org in rows:
        if AuthorizationService.ensure_foundation(db, org):
            db.flush()
        ctx = AuthorizationService.context(db, org, user)
        items.append({
            **_structure_out(db, org, expose_owner=ctx.is_owner),
            "role": _role_out(ctx.role),
            "permissions": sorted(ctx.permissions),
        })
    db.commit()
    return {"items": items}


@router.get("/structures/{slug}/context")
def structure_context(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "structure.read")
    return {"structure": _structure_out(db, org, expose_owner=ctx.is_owner), "membership": _member_out(db, ctx.membership), "role": _role_out(ctx.role), "permissions": sorted(ctx.permissions)}


@router.patch("/structures/{slug}", response_model=StructureOut)
def patch_structure(slug: str, payload: StructurePatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "structure.manage")
    governance = db.get(StructureGovernance, org.id)
    before = _structure_out(db, org, expose_owner=True)
    values = payload.model_dump(exclude_none=True)
    for field in ("name", "description", "org_type", "city", "primary_color", "contact_email", "contact_phone"):
        if field in values:
            setattr(org, field, values[field].strip() if isinstance(values[field], str) else values[field])
    if governance:
        if "seo_title" in values:
            governance.seo_title = values["seo_title"]
        if "seo_description" in values:
            governance.seo_description = values["seo_description"]
        governance.updated_at = now_utc()
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.structure.update", resource_type="organization", resource_id=str(org.id), before=before, after=_structure_out(db, org, expose_owner=True))
    db.commit()
    return _structure_out(db, org, expose_owner=True)


@router.patch("/structures/{slug}/public-page")
def patch_public_page(slug: str, payload: PublicPagePatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "visibility.manage")
    page = db.get(StructurePublicPage, org.id)
    before = {"status": page.status, "seoEnabled": page.seo_enabled, "indexable": page.indexable}
    page.status = payload.status
    if payload.seo_enabled is not None:
        page.seo_enabled = payload.seo_enabled
    if payload.indexable is not None:
        page.indexable = payload.indexable
    if payload.status == "PUBLISHED" and page.published_at is None:
        page.published_at = now_utc()
    page.updated_at = now_utc()
    # Keep the legacy mobile/public API coherent during migration.
    org.visibility = "PUBLIC" if payload.status == "PUBLISHED" else "PRIVATE"
    after = {"status": page.status, "seoEnabled": page.seo_enabled, "indexable": page.indexable}
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.public_page.update", resource_type="structure_public_page", resource_id=str(org.id), before=before, after=after)
    db.commit()
    return after


@router.get("/structures/{slug}/roles", response_model=list[RoleOut])
def list_roles(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    _ctx(db, org, user, "members.view")
    return [_role_out(role) for role in db.query(StructureRole).filter_by(organization_id=org.id).order_by(StructureRole.system_role.desc(), StructureRole.name).all()]


@router.post("/structures/{slug}/roles", response_model=RoleOut, status_code=201)
def create_role(slug: str, payload: RoleCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "roles.manage")
    role = RoleService.create(db, ctx=ctx, name=payload.name, audience_level=payload.audience_level, permissions=payload.permissions)
    db.commit()
    return _role_out(role)


@router.patch("/structures/{slug}/roles/{role_id}", response_model=RoleOut)
def patch_role(slug: str, role_id: int, payload: RolePatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "roles.manage")
    role = db.get(StructureRole, role_id)
    if role is None:
        raise HTTPException(404, detail="Role not found")
    RoleService.update(db, ctx=ctx, role=role, name=payload.name, audience_level=payload.audience_level, permissions=payload.permissions)
    db.commit()
    return _role_out(role)


@router.delete("/structures/{slug}/roles/{role_id}", status_code=204)
def delete_role(slug: str, role_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "roles.manage")
    role = db.get(StructureRole, role_id)
    if role is None:
        raise HTTPException(404, detail="Role not found")
    RoleService.delete(db, ctx=ctx, role=role)
    db.commit()


@router.get("/structures/{slug}/members")
def list_members(slug: str, include_former: bool = False, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    _ctx(db, org, user, "members.view")
    query = db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org.id)
    if not include_former:
        query = query.filter(OrganizationMembership.status == "ACTIVE", OrganizationMembership.revoked_at.is_(None))
    return {"items": [_member_out(db, row) for row in query.order_by(OrganizationMembership.id).all()]}


@router.patch("/structures/{slug}/members/{member_id}")
def patch_member(slug: str, member_id: int, payload: MemberPatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "members.manage")
    membership = db.get(OrganizationMembership, member_id)
    if membership is None or membership.organization_id != org.id:
        raise HTTPException(404, detail="Member not found")
    governance = db.get(StructureGovernance, org.id)
    if governance and membership.user_id == governance.owner_user_id and payload.status in {"FORMER", "REVOKED"}:
        raise HTTPException(409, detail={"reason": "OWNER_MEMBERSHIP_PROTECTED"})
    if payload.role_id is not None:
        assignment = db.query(StructureRoleAssignment).filter_by(membership_id=membership.id).first()
        if assignment is None or assignment.role_id != payload.role_id:
            role = db.get(StructureRole, payload.role_id)
            if role is None:
                raise HTTPException(404, detail="Role not found")
            RoleService.assign(db, ctx=ctx, membership=membership, role=role)
    if payload.status is not None:
        mapping = {"INVITED":"PENDING", "ACTIVE":"ACTIVE", "FORMER":"LEFT", "REVOKED":"REVOKED"}
        membership.status = mapping[payload.status]
        if payload.status in {"FORMER", "REVOKED"}:
            membership.revoked_at = now_utc() if payload.status == "REVOKED" else None
            membership.ends_at = membership.ends_at or now_utc()
        elif payload.status == "ACTIVE":
            membership.revoked_at = None
            membership.ends_at = payload.mandate_end
    meta = dict(membership.metadata_json or {})
    if payload.title is not None:
        meta["forum_title"] = payload.title
    if payload.team is not None:
        meta["forum_team"] = payload.team
    membership.metadata_json = meta
    if payload.public_profile is not None:
        membership.visibility = "PUBLIC" if payload.public_profile else "PRIVATE"
    if payload.mandate_start is not None:
        membership.starts_at = payload.mandate_start.replace(tzinfo=None)
    if payload.mandate_end is not None:
        membership.ends_at = payload.mandate_end.replace(tzinfo=None)
    membership.updated_at = now_utc()
    db.commit()
    return _member_out(db, membership)


@router.post("/structures/{slug}/ownership/transfer")
def transfer_ownership(slug: str, payload: OwnershipTransferIn, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "ownership.transfer")
    action = f"forum_v2_ownership_transfer:{org.id}:{payload.new_owner_user_id}"
    key, previous = _idem(db, user, action, idempotency_key)
    if previous:
        return previous
    governance = StructureService.transfer_ownership(db, ctx=ctx, new_owner_user_id=payload.new_owner_user_id)
    response = {"ok": True, "ownerUserId": governance.owner_user_id}
    _save_idem(db, user, action, key, response)
    db.commit()
    return response


# ---------------------------------------------------------------------------
# Invitations / claims / visibility
# ---------------------------------------------------------------------------

@router.post("/structures/{slug}/invitations", status_code=201)
def create_invitation(slug: str, payload: InvitationCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "members.manage")
    _limit("forum_invitation_create", f"{user.id}:{org.id}")
    role = db.get(StructureRole, payload.role_id)
    if role is None or role.organization_id != org.id:
        raise HTTPException(404, detail="Role not found")
    if role.system_role:
        raise HTTPException(403, detail={"reason": "SYSTEM_ROLE_INVITATION_FORBIDDEN"})
    AuthorizationService.assert_grantable(ctx, role.permissions_json or [])
    if db.query(StructureInvitation).filter_by(organization_id=org.id, email=payload.email, status="PENDING").first():
        raise HTTPException(409, detail={"reason": "INVITATION_ALREADY_PENDING"})
    raw_token = secrets.token_urlsafe(36)
    row = StructureInvitation(
        organization_id=org.id, email=payload.email, role_id=role.id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=now_utc() + timedelta(hours=payload.expires_in_hours), status="PENDING",
        invited_by_user_id=user.id, created_at=now_utc(),
    )
    db.add(row)
    db.flush()
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.invitation.create", resource_type="structure_invitation", resource_id=str(row.id), after={"email": payload.email, "roleId": role.id, "expiresAt": row.expires_at.isoformat()})
    db.commit()
    # Raw token is intentionally returned once and never stored in plaintext.
    return {"id": row.id, "email": row.email, "status": row.status, "expiresAt": row.expires_at.isoformat(), "token": raw_token}


@router.post("/invitations/accept")
def accept_invitation(payload: InvitationAcceptIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _limit("forum_invitation_accept", user.id)
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    invitation = db.query(StructureInvitation).filter_by(token_hash=token_hash).first()
    if invitation is None or invitation.status != "PENDING" or invitation.expires_at <= now_utc():
        raise HTTPException(404, detail={"reason": "INVITATION_NOT_AVAILABLE"})
    if not user.email or user.email.strip().lower() != invitation.email.strip().lower():
        raise HTTPException(403, detail={"reason": "VERIFIED_EMAIL_REQUIRED"})
    org = db.get(Organization, invitation.organization_id)
    if org is None:
        raise HTTPException(404, detail="Structure not found")
    AuthorizationService.ensure_foundation(db, org)
    membership = db.query(OrganizationMembership).filter_by(organization_id=org.id, user_id=user.id).first()
    now = now_utc()
    if membership is None:
        membership = OrganizationMembership(organization_id=org.id, user_id=user.id, role="MEMBER", status="ACTIVE", joined_at=now, starts_at=now, visibility="PRIVATE", created_at=now, created_by_user_id=invitation.invited_by_user_id, validated_by_user_id=invitation.invited_by_user_id, validated_at=now)
        db.add(membership)
        db.flush()
    else:
        membership.status = "ACTIVE"
        membership.revoked_at = None
        membership.ends_at = None
        membership.updated_at = now
    role = db.get(StructureRole, invitation.role_id)
    if role is None or role.organization_id != org.id or role.system_role:
        raise HTTPException(409, detail={"reason": "INVITATION_ROLE_INVALID"})
    assignment = db.query(StructureRoleAssignment).filter_by(membership_id=membership.id).first()
    if assignment is None:
        assignment = StructureRoleAssignment(organization_id=org.id, membership_id=membership.id, role_id=role.id, assigned_by_user_id=invitation.invited_by_user_id, created_at=now, updated_at=now)
        db.add(assignment)
    else:
        assignment.role_id = role.id
        assignment.updated_at = now
    membership.role = role.name.upper()[:32]
    invitation.status = "ACCEPTED"
    invitation.accepted_at = now
    invitation.accepted_by_user_id = user.id
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=role.name, action="forum.invitation.accept", resource_type="structure_invitation", resource_id=str(invitation.id), after={"memberUserId": user.id, "roleId": role.id})
    db.commit()
    return {"ok": True, "structure": org.slug, "membershipId": membership.id}


@router.post("/public/structures/{slug}/claims", status_code=201)
def create_claim(slug: str, payload: ClaimCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    _limit("forum_claim_create", user.id)
    existing = db.query(StructureClaim).filter_by(organization_id=org.id, requested_by_user_id=user.id, status="PENDING").first()
    if existing:
        raise HTTPException(409, detail={"reason": "CLAIM_ALREADY_PENDING"})
    claim = StructureClaim(organization_id=org.id, requested_by_user_id=user.id, status="PENDING", reason=payload.reason, created_at=now_utc())
    db.add(claim)
    db.flush()
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role="CLAIMANT", action="forum.claim.create", resource_type="structure_claim", resource_id=str(claim.id), after={"status": "PENDING"})
    db.commit()
    return {"id": claim.id, "status": claim.status}


@router.post("/structures/{slug}/claims/{claim_id}/review")
def review_claim(slug: str, claim_id: int, payload: ClaimReviewIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "structure.admin")
    claim = db.get(StructureClaim, claim_id)
    if claim is None or claim.organization_id != org.id or claim.status != "PENDING":
        raise HTTPException(404, detail="Claim not found")
    requester = db.get(AppUser, claim.requested_by_user_id)
    if requester is None:
        raise HTTPException(409, detail={"reason": "CLAIM_REQUESTER_MISSING"})
    now = now_utc()
    if payload.decision == "APPROVED":
        membership = db.query(OrganizationMembership).filter_by(organization_id=org.id, user_id=requester.id).first()
        if membership is None:
            membership = OrganizationMembership(organization_id=org.id, user_id=requester.id, role="MEMBER", status="ACTIVE", joined_at=now, starts_at=now, visibility="PRIVATE", created_at=now, created_by_user_id=user.id, validated_by_user_id=user.id, validated_at=now)
            db.add(membership)
            db.flush()
        else:
            membership.status = "ACTIVE"
            membership.revoked_at = None
            membership.ends_at = None
        AuthorizationService.ensure_foundation(db, org)
        assignment = db.query(StructureRoleAssignment).filter_by(membership_id=membership.id).first()
        if assignment is None:
            member_role = db.query(StructureRole).filter_by(organization_id=org.id, name="Membre", system_role=True).one()
            db.add(StructureRoleAssignment(organization_id=org.id, membership_id=membership.id, role_id=member_role.id, assigned_by_user_id=user.id, created_at=now, updated_at=now))
        if payload.transfer_ownership:
            StructureService.transfer_ownership(db, ctx=ctx, new_owner_user_id=requester.id)
    claim.status = payload.decision
    claim.reviewed_at = now
    claim.reviewed_by_user_id = user.id
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.claim.review", resource_type="structure_claim", resource_id=str(claim.id), before={"status": "PENDING"}, after={"status": claim.status, "transferOwnership": payload.transfer_ownership})
    db.commit()
    return {"id": claim.id, "status": claim.status}


@router.get("/structures/{slug}/visibility")
def list_visibility(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    _ctx(db, org, user, "structure.read")
    rows = db.query(VisibilityPolicy).filter_by(organization_id=org.id).order_by(VisibilityPolicy.resource_type, VisibilityPolicy.resource_id).all()
    return {"items": [{"resourceType": r.resource_type, "resourceId": r.resource_id, "level": r.level} for r in rows]}


@router.put("/structures/{slug}/visibility")
def put_visibility(slug: str, payload: VisibilityPolicyIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "visibility.manage")
    row = db.query(VisibilityPolicy).filter_by(organization_id=org.id, resource_type=payload.resource_type, resource_id=payload.resource_id).first()
    before = {"level": row.level} if row else None
    if row is None:
        row = VisibilityPolicy(organization_id=org.id, resource_type=payload.resource_type, resource_id=payload.resource_id, level=payload.level, updated_by_user_id=user.id, created_at=now_utc(), updated_at=now_utc())
        db.add(row)
    else:
        row.level = payload.level
        row.updated_by_user_id = user.id
        row.updated_at = now_utc()
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.visibility.update", resource_type="visibility_policy", resource_id=f"{payload.resource_type}:{payload.resource_id}", before=before, after={"level": payload.level})
    db.commit()
    return {"resourceType": row.resource_type, "resourceId": row.resource_id, "level": row.level}


# ---------------------------------------------------------------------------
# Events / operational stats / accounting
# ---------------------------------------------------------------------------

@router.get("/structures/{slug}/events")
def list_events(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    _ctx(db, org, user, "events.view")
    rel_ids = [r.event_id for r in db.query(EventStructure).filter_by(organization_id=org.id).all()]
    query = db.query(Event).filter(or_(Event.id.in_(rel_ids or [-1]), and_(Event.host_type == "orga", Event.host_id == str(org.id))))
    rows = query.order_by(Event.starts_at.desc(), Event.id.desc()).all()
    return {"items": [_event_out(db, org.id, event) for event in rows]}


@router.post("/structures/{slug}/events", status_code=201)
def create_event(slug: str, payload: EventCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "events.manage")
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(422, detail={"reason": "INVALID_EVENT_DATES"})
    cohosts = []
    for other_id in set(payload.co_host_structure_ids):
        if other_id == org.id:
            continue
        other = db.get(Organization, other_id)
        if other is None:
            raise HTTPException(404, detail="Co-host structure not found")
        AuthorizationService.ensure_foundation(db, other)
        AuthorizationService.require_permission(db, other, user, "events.manage")
        cohosts.append(other)
    event = Event(
        host_type="orga", host_id=str(org.id), host_display_name=org.name, name=payload.name.strip(),
        starts_at=payload.starts_at.replace(tzinfo=None), ends_at=payload.ends_at.replace(tzinfo=None),
        venue=payload.venue, city=payload.city or org.city, public_description=payload.description,
        visibility=payload.visibility, publication_status="DRAFT", capacity=payload.capacity,
        entry_price_cents=payload.entry_price_cents, event_state="DRAFT", created_by=f"app:{user.id}",
        last_state_updated_at=now_utc(), last_updated_at=now_utc(),
    )
    db.add(event)
    db.flush()
    db.add(EventStructure(event_id=event.id, organization_id=org.id, role="HOST", created_at=now_utc()))
    for other in cohosts:
        db.add(EventStructure(event_id=event.id, organization_id=other.id, role="CO_HOST", created_at=now_utc()))
    db.add(ForumEventLifecycle(event_id=event.id, organization_id=org.id, status="DRAFT", updated_by_user_id=user.id, created_at=now_utc(), updated_at=now_utc()))
    db.add(EventRuntimeState(event_id=event.id, state="DRAFT", updated_at=now_utc()))
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.event.create", resource_type="event", resource_id=str(event.id), after={"name": event.name, "lifecycle": "DRAFT"}, event_id=event.id)
    db.commit()
    return _event_out(db, org.id, event)


@router.patch("/structures/{slug}/events/{event_id}")
def patch_event(slug: str, event_id: int, payload: EventPatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "events.manage")
    event = _event_scoped(db, org.id, event_id)
    before = _event_out(db, org.id, event)
    values = payload.model_dump(exclude_none=True)
    starts_at = values.get("starts_at", event.starts_at)
    ends_at = values.get("ends_at", event.ends_at)
    if ends_at <= starts_at:
        raise HTTPException(422, detail={"reason": "INVALID_EVENT_DATES"})
    mapping = {"description": "public_description"}
    for key, value in values.items():
        field = mapping.get(key, key)
        if key in {"starts_at", "ends_at"}:
            value = value.replace(tzinfo=None)
        setattr(event, field, value.strip() if isinstance(value, str) else value)
    event.last_updated_at = now_utc()
    after = _event_out(db, org.id, event)
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.event.update", resource_type="event", resource_id=str(event.id), before=before, after=after, event_id=event.id)
    db.commit()
    return after


@router.post("/structures/{slug}/events/{event_id}/transition")
def transition_event(slug: str, event_id: int, payload: EventTransitionIn, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "events.publish")
    event = _event_scoped(db, org.id, event_id)
    action = f"forum_v2_event_transition:{org.id}:{event.id}:{payload.target}"
    key, previous = _idem(db, user, action, idempotency_key)
    if previous:
        return previous
    lifecycle = EventLifecycleService.transition(db, ctx=ctx, event=event, target=payload.target)
    response = {"eventId": event.id, "status": lifecycle.status}
    _save_idem(db, user, action, key, response)
    db.commit()
    return response


@router.get("/structures/{slug}/stats")
def operational_stats(slug: str, event_id: Optional[int] = None, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    _ctx(db, org, user, "stats.view")
    event = _event_scoped(db, org.id, event_id) if event_id else None
    if event is None:
        rel_ids = [r.event_id for r in db.query(EventStructure).filter_by(organization_id=org.id).all()]
        event = db.query(Event).filter(or_(Event.id.in_(rel_ids or [-1]), and_(Event.host_type == "orga", Event.host_id == str(org.id)))).order_by(Event.ends_at.desc(), Event.id.desc()).first()
    if event is None:
        return {"eventId": None, "entries": 0, "scans": 0, "capacity": None, "occupancyPercent": None}
    entries = int(db.scalar(select(func.count()).select_from(Entry).where(Entry.event_id == event.id, Entry.used.is_(True))) or 0)
    scans = int(db.scalar(select(func.count()).select_from(EntryScanLog).where(EntryScanLog.event_id == event.id)) or 0)
    occupancy = round(entries * 100 / event.capacity) if event.capacity and event.capacity > 0 else None
    # Deliberately no revenue/cost/profit keys here.
    return {"eventId": event.id, "entries": entries, "scans": scans, "capacity": event.capacity, "occupancyPercent": occupancy}


@router.get("/structures/{slug}/accounting")
def list_accounting(slug: str, event_id: Optional[int] = None, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    _ctx(db, org, user, "accounting.view")
    query = db.query(AccountingEntry).filter(AccountingEntry.organization_id == org.id)
    if event_id is not None:
        _event_scoped(db, org.id, event_id)
        query = query.filter(AccountingEntry.event_id == event_id)
    rows = query.order_by(AccountingEntry.created_at.desc()).all()
    income = sum(row.amount_cents for row in rows if row.entry_type == "INCOME")
    expenses = sum(row.amount_cents for row in rows if row.entry_type == "EXPENSE")
    return {"items": [_accounting_out(row) for row in rows], "totals": {"incomeCents": income, "expenseCents": expenses, "resultCents": income - expenses}}


def _accounting_out(row: AccountingEntry) -> dict[str, Any]:
    return {"id": row.id, "eventId": row.event_id, "type": row.entry_type, "category": row.category, "label": row.label, "amountCents": row.amount_cents, "status": row.status, "supplier": row.supplier, "paid": row.paid, "notes": row.notes, "lockedAt": row.locked_at.isoformat() if row.locked_at else None}


@router.post("/structures/{slug}/accounting", status_code=201)
def create_accounting(slug: str, payload: AccountingEntryCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "accounting.manage")
    if payload.event_id is not None:
        _event_scoped(db, org.id, payload.event_id)
    row = AccountingEntry(organization_id=org.id, event_id=payload.event_id, entry_type=payload.entry_type, category=payload.category, label=payload.label, amount_cents=payload.amount_cents, status="DRAFT", supplier=payload.supplier, paid=payload.paid, notes=payload.notes, created_by_user_id=user.id, created_at=now_utc(), updated_at=now_utc())
    db.add(row)
    db.flush()
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.accounting.create", resource_type="accounting_entry", resource_id=str(row.id), after=_accounting_out(row), event_id=row.event_id)
    db.commit()
    return _accounting_out(row)


@router.patch("/structures/{slug}/accounting/{entry_id}")
def patch_accounting(slug: str, entry_id: int, payload: AccountingEntryPatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "accounting.manage")
    row = db.get(AccountingEntry, entry_id)
    if row is None or row.organization_id != org.id:
        raise HTTPException(404, detail="Accounting entry not found")
    AccountingService.assert_mutable(row)
    before = _accounting_out(row)
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(row, key if key != "status" else "status", value)
    row.updated_at = now_utc()
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.accounting.update", resource_type="accounting_entry", resource_id=str(row.id), before=before, after=_accounting_out(row), event_id=row.event_id)
    db.commit()
    return _accounting_out(row)


@router.delete("/structures/{slug}/accounting/{entry_id}", status_code=204)
def delete_accounting(slug: str, entry_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "accounting.manage")
    row = db.get(AccountingEntry, entry_id)
    if row is None or row.organization_id != org.id:
        raise HTTPException(404, detail="Accounting entry not found")
    AccountingService.assert_mutable(row)
    before = _accounting_out(row)
    db.delete(row)
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.accounting.delete", resource_type="accounting_entry", resource_id=str(entry_id), before=before, after=None, event_id=row.event_id)
    db.commit()


@router.post("/structures/{slug}/accounting/{entry_id}/lock")
def lock_accounting(slug: str, entry_id: int, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "accounting.manage")
    row = db.get(AccountingEntry, entry_id)
    if row is None or row.organization_id != org.id:
        raise HTTPException(404, detail="Accounting entry not found")
    action = f"forum_v2_accounting_lock:{entry_id}"
    key, previous = _idem(db, user, action, idempotency_key)
    if previous:
        return previous
    AccountingService.lock(db, ctx=ctx, entry=row)
    response = _accounting_out(row)
    _save_idem(db, user, action, key, response)
    db.commit()
    return response


@router.post("/structures/{slug}/accounting/{entry_id}/unlock")
def unlock_accounting(slug: str, entry_id: int, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "accounting.unlock")
    row = db.get(AccountingEntry, entry_id)
    if row is None or row.organization_id != org.id:
        raise HTTPException(404, detail="Accounting entry not found")
    action = f"forum_v2_accounting_unlock:{entry_id}"
    key, previous = _idem(db, user, action, idempotency_key)
    if previous:
        return previous
    AccountingService.unlock(db, ctx=ctx, entry=row)
    response = _accounting_out(row)
    _save_idem(db, user, action, key, response)
    db.commit()
    return response


@router.post("/structures/{slug}/events/{event_id}/public-summary")
def publish_public_summary(slug: str, event_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "events.publish")
    if "stats.view" not in ctx.permissions:
        raise HTTPException(403, detail={"reason": "FORUM_PERMISSION_DENIED", "permission": "stats.view"})
    event = _event_scoped(db, org.id, event_id)
    entries = int(db.scalar(select(func.count()).select_from(Entry).where(Entry.event_id == event.id, Entry.used.is_(True))) or 0)
    scans = int(db.scalar(select(func.count()).select_from(EntryScanLog).where(EntryScanLog.event_id == event.id)) or 0)
    occupancy = round(entries * 100 / event.capacity) if event.capacity and event.capacity > 0 else None
    row = db.query(EventPublicSummary).filter_by(event_id=event.id).first()
    before = None if row is None else {"entries": row.entries, "scans": row.scans, "capacity": row.capacity, "occupancyPercent": row.occupancy_percent}
    if row is None:
        row = EventPublicSummary(event_id=event.id, organization_id=org.id, published_by_user_id=user.id)
        db.add(row)
    row.entries, row.scans, row.capacity, row.occupancy_percent = entries, scans, event.capacity, occupancy
    row.published_at = now_utc()
    row.published_by_user_id = user.id
    after = {"entries": entries, "scans": scans, "capacity": event.capacity, "occupancyPercent": occupancy}
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.stats.public_summary.publish", resource_type="event_public_summary", resource_id=str(event.id), before=before, after=after, event_id=event.id)
    db.commit()
    return {"eventId": event.id, **after, "publishedAt": row.published_at.isoformat()}


# ---------------------------------------------------------------------------
# Discussions
# ---------------------------------------------------------------------------

@router.get("/structures/{slug}/channels")
def list_channels(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.read")
    rows = db.query(StructureDiscussionChannel).filter_by(organization_id=org.id, is_archived=False).order_by(StructureDiscussionChannel.id).all()
    return {"items": [{"id": c.id, "name": c.name, "visibility": normalize_visibility(c.visibility)} for c in rows if AuthorizationService.can_read_channel(ctx, c)]}


@router.post("/structures/{slug}/channels", status_code=201)
def create_channel(slug: str, payload: ChannelCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.manage")
    category = db.query(StructureDiscussionCategory).filter_by(organization_id=org.id, slug="forum").first()
    if category is None:
        category = StructureDiscussionCategory(organization_id=org.id, name="Forum", slug="forum", order_index=0, is_archived=False, created_at=now_utc())
        db.add(category)
        db.flush()
    slug_value = _slugify(payload.name)[:120]
    if db.query(StructureDiscussionChannel).filter_by(organization_id=org.id, slug=slug_value).first():
        raise HTTPException(409, detail={"reason": "CHANNEL_EXISTS"})
    row = StructureDiscussionChannel(organization_id=org.id, category_id=category.id, name=payload.name.strip(), slug=slug_value, visibility=payload.visibility, is_archived=False, created_at=now_utc())
    db.add(row)
    db.flush()
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.channel.create", resource_type="forum_channel", resource_id=str(row.id), after={"name": row.name, "visibility": row.visibility})
    db.commit()
    return {"id": row.id, "name": row.name, "visibility": normalize_visibility(row.visibility)}


@router.patch("/structures/{slug}/channels/{channel_id}")
def patch_channel(slug: str, channel_id: int, payload: ChannelPatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.manage")
    channel = _channel_scoped(db, org.id, channel_id)
    before = {"name": channel.name, "visibility": channel.visibility, "archived": channel.is_archived}
    if payload.name is not None:
        channel.name = payload.name.strip()
    if payload.visibility is not None:
        channel.visibility = payload.visibility
    if payload.archived is not None:
        channel.is_archived = payload.archived
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.channel.update", resource_type="forum_channel", resource_id=str(channel.id), before=before, after={"name": channel.name, "visibility": channel.visibility, "archived": channel.is_archived})
    db.commit()
    return {"id": channel.id, "name": channel.name, "visibility": normalize_visibility(channel.visibility), "archived": channel.is_archived}


@router.get("/structures/{slug}/channels/{channel_id}/messages")
def list_messages(slug: str, channel_id: int, limit: int = Query(default=100, ge=1, le=300), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.read")
    channel = _channel_scoped(db, org.id, channel_id)
    if not AuthorizationService.can_read_channel(ctx, channel):
        raise HTTPException(404, detail="Channel not found")
    rows = db.query(StructureDiscussionPost).filter_by(organization_id=org.id, channel_id=channel.id, is_archived=False).order_by(StructureDiscussionPost.created_at.asc(), StructureDiscussionPost.id.asc()).limit(limit).all()
    return {"items": [{"id": m.id, "title": m.title, "body": m.body, "parentMessageId": m.parent_id, "authorUserId": m.created_by_user_id, "createdAt": m.created_at.isoformat() if m.created_at else None} for m in rows]}


@router.post("/structures/{slug}/channels/{channel_id}/messages", status_code=201)
def post_message(slug: str, channel_id: int, payload: Any = None, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    # Payload is validated explicitly to keep the body schema in OpenAPI even
    # though FastAPI cannot infer it after older clients sent arbitrary JSON.
    from app.schemas.forum_backend import MessageCreateIn
    message = payload if isinstance(payload, MessageCreateIn) else MessageCreateIn.model_validate(payload or {})
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.post")
    _limit("forum_message_post", f"{user.id}:{org.id}")
    channel = _channel_scoped(db, org.id, channel_id)
    if not AuthorizationService.can_post_channel(ctx, channel):
        raise HTTPException(404, detail="Channel not found")
    if message.parent_message_id is not None:
        parent = db.get(StructureDiscussionPost, message.parent_message_id)
        if parent is None or parent.organization_id != org.id or parent.channel_id != channel.id or parent.is_archived:
            raise HTTPException(404, detail="Parent message not found")
    for document_id in message.document_ids:
        doc = _document_scoped(db, org.id, document_id)
        if not AuthorizationService.can_read_document(ctx, doc):
            raise HTTPException(404, detail="Document not found")
    row = StructureDiscussionPost(organization_id=org.id, channel_id=channel.id, parent_id=message.parent_message_id, document_ids=list(set(message.document_ids)), title=(message.title or message.body[:80] or "Message").strip(), body=message.body.strip(), created_by_user_id=user.id, is_pinned=False, is_archived=False, created_at=now_utc(), updated_at=now_utc())
    db.add(row)
    db.flush()
    db.commit()
    return {"id": row.id, "body": row.body, "parentMessageId": row.parent_id, "createdAt": row.created_at.isoformat()}


# ---------------------------------------------------------------------------
# Documents / storage
# ---------------------------------------------------------------------------

@router.get("/structures/{slug}/documents")
def list_documents(slug: str, q: Optional[str] = Query(default=None, max_length=120), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "documents.view")
    query = db.query(StructureDocument).filter(StructureDocument.organization_id == org.id, StructureDocument.archived_at.is_(None))
    if q:
        needle = f"%{q.strip()}%"
        query = query.filter(or_(StructureDocument.title.ilike(needle), StructureDocument.description.ilike(needle), StructureDocument.folder.ilike(needle)))
    rows = [row for row in query.order_by(StructureDocument.updated_at.desc()).all() if AuthorizationService.can_read_document(ctx, row)]
    items = []
    for row in rows:
        versions = db.query(StructureDocumentVersion).filter_by(document_id=row.id, organization_id=org.id).order_by(StructureDocumentVersion.version_number.desc()).all()
        items.append({"id": row.id, "title": row.title, "description": row.description, "folder": row.folder, "tags": row.tags_json or [], "visibility": normalize_visibility(row.visibility), "eventId": row.event_id, "currentVersion": versions[0].version_number if versions else 0, "versions": [{"version": v.version_number, "name": v.original_name, "mimeType": v.mime_type, "size": v.size_bytes, "checksum": v.checksum_sha256, "createdAt": v.created_at.isoformat()} for v in versions]})
    return {"items": items}


@router.post("/structures/{slug}/documents", status_code=201)
def create_document(slug: str, payload: DocumentCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "documents.manage")
    if payload.event_id is not None:
        _event_scoped(db, org.id, payload.event_id)
    row = StructureDocument(organization_id=org.id, title=payload.title.strip(), description=payload.description, file_url="storage://pending", folder=payload.folder, tags_json=[tag.strip() for tag in payload.tags if tag.strip()], visibility=payload.visibility, uploaded_by_user_id=user.id, event_id=payload.event_id, created_at=now_utc(), updated_at=now_utc())
    db.add(row)
    db.flush()
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.document.create", resource_type="document", resource_id=str(row.id), after={"title": row.title, "visibility": row.visibility}, event_id=row.event_id)
    db.commit()
    return {"id": row.id, "title": row.title, "currentVersion": 0}


@router.post("/structures/{slug}/documents/{document_id}/versions", status_code=201)
async def upload_document_version(slug: str, document_id: int, file: UploadFile = File(...), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "documents.manage")
    _limit("forum_upload", f"{user.id}:{org.id}")
    doc = _document_scoped(db, org.id, document_id)
    latest = db.scalar(select(func.max(StructureDocumentVersion.version_number)).where(StructureDocumentVersion.document_id == doc.id)) or 0
    stored = await get_forum_storage().save_upload(organization_id=org.id, namespace=f"documents/{doc.id}", upload=file)
    version = StructureDocumentVersion(organization_id=org.id, document_id=doc.id, version_number=int(latest) + 1, storage_key=stored.storage_key, original_name=stored.original_name, mime_type=stored.mime_type, size_bytes=stored.size_bytes, checksum_sha256=stored.checksum_sha256, uploaded_by_user_id=user.id, created_at=now_utc())
    db.add(version)
    doc.file_url = f"storage://{stored.storage_key}"
    doc.updated_at = now_utc()
    db.flush()
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.document.version.create", resource_type="document", resource_id=str(doc.id), after={"version": version.version_number, "mimeType": version.mime_type, "size": version.size_bytes, "checksum": version.checksum_sha256}, event_id=doc.event_id)
    db.commit()
    return {"documentId": doc.id, "version": version.version_number, "name": version.original_name, "mimeType": version.mime_type, "size": version.size_bytes, "checksum": version.checksum_sha256}


@router.get("/structures/{slug}/documents/{document_id}/download")
def download_document(slug: str, document_id: int, version: Optional[int] = Query(default=None, ge=1), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "documents.download")
    doc = _document_scoped(db, org.id, document_id)
    if not AuthorizationService.can_read_document(ctx, doc):
        raise HTTPException(404, detail="Document not found")
    query = db.query(StructureDocumentVersion).filter_by(organization_id=org.id, document_id=doc.id)
    if version is not None:
        row = query.filter_by(version_number=version).first()
    else:
        row = query.order_by(StructureDocumentVersion.version_number.desc()).first()
    if row is None:
        raise HTTPException(404, detail="Document version not found")
    path = get_forum_storage().local_path(row.storage_key)
    return FileResponse(path, media_type=row.mime_type, filename=row.original_name)


@router.delete("/structures/{slug}/documents/{document_id}", status_code=204)
def archive_document(slug: str, document_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "documents.manage")
    doc = _document_scoped(db, org.id, document_id)
    doc.archived_at = now_utc()
    doc.updated_at = now_utc()
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.document.archive", resource_type="document", resource_id=str(doc.id), before={"archived": False}, after={"archived": True}, event_id=doc.event_id)
    db.commit()


# ---------------------------------------------------------------------------
# Albums / media
# ---------------------------------------------------------------------------

@router.get("/structures/{slug}/albums")
def list_albums(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "albums.view")
    rows = db.query(StructureAlbum).filter(StructureAlbum.organization_id == org.id, StructureAlbum.archived_at.is_(None)).order_by(StructureAlbum.updated_at.desc()).all()
    return {"items": [_album_out(db, row) for row in rows if AuthorizationService.can_view_level(row.visibility, user, ctx)]}


def _album_out(db: Session, album: StructureAlbum) -> dict[str, Any]:
    links = db.query(StructureAlbumMedia).filter_by(organization_id=album.organization_id, album_id=album.id).order_by(StructureAlbumMedia.position, StructureAlbumMedia.id).all()
    return {"id": album.id, "title": album.title, "description": album.description, "visibility": normalize_visibility(album.visibility), "status": album.status, "eventId": album.event_id, "media": [{"id": link.media_id, "position": link.position, "cover": link.is_cover} for link in links], "mediaCount": len(links), "coverMediaId": next((link.media_id for link in links if link.is_cover), None)}


@router.post("/structures/{slug}/albums", status_code=201)
def create_album(slug: str, payload: AlbumCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "albums.manage")
    if payload.event_id is not None:
        _event_scoped(db, org.id, payload.event_id)
    row = StructureAlbum(organization_id=org.id, event_id=payload.event_id, title=payload.title.strip(), description=payload.description, cover_url=None, visibility=payload.visibility, status="DRAFT", created_by_user_id=user.id, created_at=now_utc(), updated_at=now_utc())
    db.add(row)
    db.flush()
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.album.create", resource_type="album", resource_id=str(row.id), after={"title": row.title, "visibility": row.visibility})
    db.commit()
    return _album_out(db, row)


@router.post("/structures/{slug}/albums/{album_id}/media", status_code=201)
async def upload_album_media(slug: str, album_id: int, file: UploadFile = File(...), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "albums.manage")
    _limit("forum_upload", f"{user.id}:{org.id}")
    album = _album_scoped(db, org.id, album_id)
    if not (file.content_type or "").lower().startswith("image/"):
        raise HTTPException(422, detail={"reason": "ALBUM_MEDIA_MUST_BE_IMAGE"})
    stored = await get_forum_storage().save_upload(organization_id=org.id, namespace=f"albums/{album.id}", upload=file)
    asset = StructureMediaAsset(organization_id=org.id, storage_key=stored.storage_key, mime_type=stored.mime_type, size_bytes=stored.size_bytes, checksum_sha256=stored.checksum_sha256, uploaded_by_user_id=user.id, created_at=now_utc())
    db.add(asset)
    db.flush()
    position = int(db.scalar(select(func.count()).select_from(StructureAlbumMedia).where(StructureAlbumMedia.album_id == album.id)) or 0)
    link = StructureAlbumMedia(organization_id=org.id, album_id=album.id, media_id=asset.id, position=position, is_cover=position == 0, created_at=now_utc())
    db.add(link)
    album.updated_at = now_utc()
    if position == 0:
        album.cover_url = f"media://{asset.id}"
    db.flush()
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.album.media.upload", resource_type="media", resource_id=str(asset.id), after={"albumId": album.id, "mimeType": asset.mime_type, "size": asset.size_bytes})
    db.commit()
    return {"id": asset.id, "albumId": album.id, "position": link.position, "cover": link.is_cover}


@router.patch("/structures/{slug}/albums/{album_id}")
def patch_album(slug: str, album_id: int, payload: AlbumPatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "albums.manage")
    album = _album_scoped(db, org.id, album_id)
    before = _album_out(db, album)
    if payload.title is not None: album.title = payload.title.strip()
    if payload.description is not None: album.description = payload.description
    if payload.visibility is not None: album.visibility = payload.visibility
    if payload.status is not None:
        album.status = payload.status
        album.archived_at = now_utc() if payload.status == "ARCHIVED" else None
    if payload.cover_media_id is not None:
        links = db.query(StructureAlbumMedia).filter_by(organization_id=org.id, album_id=album.id).all()
        if payload.cover_media_id not in {link.media_id for link in links}:
            raise HTTPException(404, detail="Media not found in album")
        for link in links:
            link.is_cover = link.media_id == payload.cover_media_id
        album.cover_url = f"media://{payload.cover_media_id}"
    album.updated_at = now_utc()
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.album.update", resource_type="album", resource_id=str(album.id), before=before, after=_album_out(db, album))
    db.commit()
    return _album_out(db, album)


@router.put("/structures/{slug}/albums/{album_id}/media-order")
def reorder_album_media(slug: str, album_id: int, payload: MediaOrderIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    _ctx(db, org, user, "albums.manage")
    album = _album_scoped(db, org.id, album_id)
    links = db.query(StructureAlbumMedia).filter_by(organization_id=org.id, album_id=album.id).all()
    by_id = {link.media_id: link for link in links}
    if set(payload.media_ids) != set(by_id):
        raise HTTPException(422, detail={"reason": "MEDIA_ORDER_MUST_CONTAIN_ALL_ALBUM_MEDIA"})
    for position, media_id in enumerate(payload.media_ids):
        by_id[media_id].position = position
    album.updated_at = now_utc()
    db.commit()
    return _album_out(db, album)


@router.get("/structures/{slug}/media/{media_id}")
def download_private_media(slug: str, media_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "albums.view")
    asset = db.get(StructureMediaAsset, media_id)
    if asset is None or asset.organization_id != org.id:
        raise HTTPException(404, detail="Media not found")
    links = db.query(StructureAlbumMedia).filter_by(organization_id=org.id, media_id=media_id).all()
    allowed = any(AuthorizationService.can_view_level(_album_scoped(db, org.id, link.album_id).visibility, user, ctx) for link in links)
    if not allowed:
        raise HTTPException(404, detail="Media not found")
    return FileResponse(get_forum_storage().local_path(asset.storage_key), media_type=asset.mime_type)


# ---------------------------------------------------------------------------
# Folklore / posts / audit / search
# ---------------------------------------------------------------------------

@router.get("/structures/{slug}/folklore")
def list_folklore(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "folklore.view")
    rows = db.query(StructurePage).filter_by(organization_id=org.id).order_by(StructurePage.updated_at.desc()).all()
    return {"items": [_page_out(row) for row in rows if AuthorizationService.can_view_level(row.visibility, user, ctx)]}


def _page_out(row: StructurePage) -> dict[str, Any]:
    return {"id": row.id, "slug": row.slug, "title": row.title, "content": row.content, "category": row.category, "visibility": normalize_visibility(row.visibility), "version": row.version, "published": row.published_at is not None, "publishedAt": row.published_at.isoformat() if row.published_at else None}


def _slug_for_page(value: str) -> str:
    return _slugify(value)[:180]


@router.post("/structures/{slug}/folklore", status_code=201)
def create_folklore(slug: str, payload: FolklorePageCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "folklore.manage")
    page_slug = _slug_for_page(payload.slug or payload.title)
    if db.query(StructurePage).filter_by(organization_id=org.id, slug=page_slug).first():
        raise HTTPException(409, detail={"reason": "PAGE_SLUG_EXISTS"})
    now = now_utc()
    row = StructurePage(organization_id=org.id, title=payload.title.strip(), slug=page_slug, content=payload.content, visibility=payload.visibility, category=payload.category, created_by_user_id=user.id, updated_by_user_id=user.id, version=1, published_at=now if payload.published else None, created_at=now, updated_at=now)
    db.add(row)
    db.flush()
    db.add(StructurePageVersion(organization_id=org.id, page_id=row.id, version_number=1, title=row.title, content=row.content, category=row.category, visibility=row.visibility, created_by_user_id=user.id, created_at=now))
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.folklore.create", resource_type="folklore_page", resource_id=str(row.id), after={"version": 1, "visibility": row.visibility})
    db.commit()
    return _page_out(row)


@router.patch("/structures/{slug}/folklore/{page_id}")
def patch_folklore(slug: str, page_id: int, payload: FolklorePagePatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "folklore.manage")
    row = _page_scoped(db, org.id, page_id)
    before = _page_out(row)
    values = payload.model_dump(exclude_none=True)
    if "title" in values: row.title = values["title"].strip()
    if "content" in values: row.content = values["content"]
    if "category" in values: row.category = values["category"]
    if "visibility" in values: row.visibility = values["visibility"]
    if "published" in values: row.published_at = now_utc() if values["published"] else None
    row.version = (row.version or 1) + 1
    row.updated_by_user_id = user.id
    row.updated_at = now_utc()
    db.add(StructurePageVersion(organization_id=org.id, page_id=row.id, version_number=row.version, title=row.title, content=row.content, category=row.category, visibility=row.visibility, created_by_user_id=user.id, created_at=now_utc()))
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.folklore.update", resource_type="folklore_page", resource_id=str(row.id), before=before, after=_page_out(row))
    db.commit()
    return _page_out(row)


@router.get("/structures/{slug}/folklore/{page_id}/versions")
def folklore_versions(slug: str, page_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    _ctx(db, org, user, "folklore.view")
    _page_scoped(db, org.id, page_id)
    rows = db.query(StructurePageVersion).filter_by(organization_id=org.id, page_id=page_id).order_by(StructurePageVersion.version_number.desc()).all()
    return {"items": [{"version": r.version_number, "title": r.title, "content": r.content, "category": r.category, "visibility": normalize_visibility(r.visibility), "createdAt": r.created_at.isoformat()} for r in rows]}


@router.post("/structures/{slug}/folklore/{page_id}/restore")
def restore_folklore(slug: str, page_id: int, payload: FolkloreRestoreIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "folklore.manage")
    page = _page_scoped(db, org.id, page_id)
    source = db.query(StructurePageVersion).filter_by(organization_id=org.id, page_id=page.id, version_number=payload.version_number).first()
    if source is None:
        raise HTTPException(404, detail="Version not found")
    before = _page_out(page)
    page.title, page.content, page.category, page.visibility = source.title, source.content, source.category, source.visibility
    page.version = (page.version or 1) + 1
    page.updated_by_user_id = user.id
    page.updated_at = now_utc()
    db.add(StructurePageVersion(organization_id=org.id, page_id=page.id, version_number=page.version, title=page.title, content=page.content, category=page.category, visibility=page.visibility, created_by_user_id=user.id, created_at=now_utc()))
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.folklore.restore", resource_type="folklore_page", resource_id=str(page.id), before=before, after={**_page_out(page), "restoredFrom": payload.version_number})
    db.commit()
    return _page_out(page)


@router.get("/structures/{slug}/posts")
def list_posts(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "structure.read")
    rows = db.query(OrgaPost, OrgaPostPublication).join(OrgaPostPublication, OrgaPostPublication.post_id == OrgaPost.id).filter(OrgaPost.organization_id == org.id, OrgaPost.deleted_at.is_(None)).order_by(OrgaPost.created_at.desc()).all()
    return {"items": [_post_out(post, publication) for post, publication in rows if AuthorizationService.can_view_level(publication.visibility, user, ctx)]}


def _post_out(post: OrgaPost, publication: OrgaPostPublication) -> dict[str, Any]:
    return {"id": post.id, "title": publication.title, "body": post.text, "eventId": publication.event_id, "mediaId": publication.media_id, "status": publication.status, "visibility": publication.visibility, "publishAt": publication.publish_at.isoformat() if publication.publish_at else None, "publishedAt": publication.published_at.isoformat() if publication.published_at else None, "createdAt": post.created_at.isoformat() if post.created_at else None}


def _validate_post_schedule(status: str, publish_at) -> None:
    if status == "SCHEDULED":
        if publish_at is None or publish_at.replace(tzinfo=None) <= now_utc():
            raise HTTPException(422, detail={"reason": "SCHEDULED_PUBLICATION_MUST_BE_FUTURE"})


@router.post("/structures/{slug}/posts", status_code=201)
def create_post(slug: str, payload: PublicPostCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "publications.manage")
    _validate_post_schedule(payload.status, payload.publish_at)
    if payload.event_id is not None: _event_scoped(db, org.id, payload.event_id)
    if payload.media_id is not None:
        media = db.get(StructureMediaAsset, payload.media_id)
        if media is None or media.organization_id != org.id: raise HTTPException(404, detail="Media not found")
    now = now_utc()
    post = OrgaPost(organization_id=org.id, author_user_id=user.id, text=payload.body, image_url=None, pinned=False, created_at=now)
    db.add(post)
    db.flush()
    publication = OrgaPostPublication(organization_id=org.id, post_id=post.id, event_id=payload.event_id, media_id=payload.media_id, title=payload.title, status=payload.status, visibility=payload.visibility, publish_at=payload.publish_at.replace(tzinfo=None) if payload.publish_at else None, published_at=now if payload.status == "PUBLISHED" else None, updated_at=now)
    db.add(publication)
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.post.create", resource_type="public_post", resource_id=str(post.id), after={"status": publication.status, "visibility": publication.visibility})
    db.commit()
    return _post_out(post, publication)


@router.patch("/structures/{slug}/posts/{post_id}")
def patch_post(slug: str, post_id: int, payload: PublicPostPatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "publications.manage")
    post = db.get(OrgaPost, post_id)
    publication = db.query(OrgaPostPublication).filter_by(post_id=post_id, organization_id=org.id).first()
    if post is None or post.organization_id != org.id or publication is None or post.deleted_at is not None:
        raise HTTPException(404, detail="Post not found")
    before = _post_out(post, publication)
    values = payload.model_dump(exclude_none=True)
    next_status = values.get("status", publication.status)
    next_publish_at = values.get("publish_at", publication.publish_at)
    _validate_post_schedule(next_status, next_publish_at)
    if "title" in values: publication.title = values["title"]
    if "body" in values: post.text = values["body"]
    if "event_id" in values:
        if values["event_id"] is not None: _event_scoped(db, org.id, values["event_id"])
        publication.event_id = values["event_id"]
    if "media_id" in values:
        if values["media_id"] is not None:
            media = db.get(StructureMediaAsset, values["media_id"])
            if media is None or media.organization_id != org.id: raise HTTPException(404, detail="Media not found")
        publication.media_id = values["media_id"]
    if "visibility" in values: publication.visibility = values["visibility"]
    if "publish_at" in values: publication.publish_at = values["publish_at"].replace(tzinfo=None) if values["publish_at"] else None
    if "status" in values:
        publication.status = values["status"]
        if publication.status == "PUBLISHED" and publication.published_at is None: publication.published_at = now_utc()
    publication.updated_at = now_utc()
    write_structure_audit(db, organization_id=org.id, actor_user_id=user.id, actor_role=ctx.role.name, action="forum.post.update", resource_type="public_post", resource_id=str(post.id), before=before, after=_post_out(post, publication))
    db.commit()
    return _post_out(post, publication)


@router.get("/structures/{slug}/audit")
def structure_audit(slug: str, limit: int = Query(default=100, ge=1, le=250), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    _ctx(db, org, user, "audit.view")
    rows = db.query(AuditLog, StructureAuditContext).join(StructureAuditContext, StructureAuditContext.audit_log_id == AuditLog.id).filter(StructureAuditContext.organization_id == org.id).order_by(AuditLog.ts.desc(), AuditLog.id.desc()).limit(limit).all()
    return {"items": [{"id": log.id, "actorUserId": log.actor_user_id, "action": log.action, "resourceType": log.entity_type, "resourceId": log.entity_id, "before": context.before_json, "after": context.after_json, "context": context.context_json, "createdAt": log.ts.isoformat() if log.ts else None} for log, context in rows]}


@router.get("/structures/{slug}/search")
def search_structure(slug: str, q: str = Query(min_length=2, max_length=120), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "search.view")
    _limit("forum_search", f"{user.id}:{org.id}")
    needle = f"%{q.strip()}%"
    results: list[dict[str, Any]] = []
    for event in db.query(Event).filter(or_(and_(Event.host_type == "orga", Event.host_id == str(org.id)), Event.id.in_([r.event_id for r in db.query(EventStructure).filter_by(organization_id=org.id).all()] or [-1])), Event.name.ilike(needle)).limit(30).all():
        results.append({"type": "event", "id": event.id, "title": event.name})
    for doc in db.query(StructureDocument).filter(StructureDocument.organization_id == org.id, StructureDocument.archived_at.is_(None), or_(StructureDocument.title.ilike(needle), StructureDocument.description.ilike(needle))).limit(30).all():
        if AuthorizationService.can_read_document(ctx, doc): results.append({"type": "document", "id": doc.id, "title": doc.title})
    for page in db.query(StructurePage).filter(StructurePage.organization_id == org.id, or_(StructurePage.title.ilike(needle), StructurePage.content.ilike(needle))).limit(30).all():
        if AuthorizationService.can_view_level(page.visibility, user, ctx): results.append({"type": "folklore", "id": page.id, "title": page.title})
    channels = [channel for channel in db.query(StructureDiscussionChannel).filter_by(organization_id=org.id, is_archived=False).all() if AuthorizationService.can_read_channel(ctx, channel)]
    channel_ids = [channel.id for channel in channels]
    if channel_ids:
        for message in db.query(StructureDiscussionPost).filter(StructureDiscussionPost.organization_id == org.id, StructureDiscussionPost.channel_id.in_(channel_ids), StructureDiscussionPost.is_archived.is_(False), or_(StructureDiscussionPost.title.ilike(needle), StructureDiscussionPost.body.ilike(needle))).limit(30).all():
            results.append({"type": "message", "id": message.id, "title": message.title, "channelId": message.channel_id})
    return {"items": results[:100]}


# ---------------------------------------------------------------------------
# Explicit public DTO endpoints.  These never serialize private ORM models.
# ---------------------------------------------------------------------------

@router.get("/public/structures/{slug}")
def public_structure(slug: str, db: Session = Depends(get_db)):
    org, governance, page = _public_org(db, slug)
    result = _structure_out(db, org, expose_owner=False)
    result.pop("owner_user_id", None)
    if not VisibilityService.can_view(db, org.id, "presentation", user=None, ctx=None, fallback_level="PRIVATE"):
        result["description"] = None
    if VisibilityService.can_view(db, org.id, "contact", user=None, ctx=None, fallback_level="PRIVATE"):
        result["contact"] = {"email": org.contact_email, "phone": org.contact_phone, "website": org.website_url, "instagram": org.instagram_handle}
    else:
        result["contact"] = None
    public_members = []
    if VisibilityService.can_view(db, org.id, "members", user=None, ctx=None, fallback_level="PRIVATE"):
        rows = db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org.id, OrganizationMembership.status == "ACTIVE", OrganizationMembership.revoked_at.is_(None), func.upper(OrganizationMembership.visibility) == "PUBLIC").all()
        for membership in rows:
            account = db.get(AppUser, membership.user_id)
            public_members.append({"displayName": account.display_name if account else "Membre TORÈ", "avatarUrl": account.avatar_url if account else None, "title": (membership.metadata_json or {}).get("forum_title") if isinstance(membership.metadata_json, dict) else None})
    result["members"] = public_members
    return result


@router.get("/public/structures/{slug}/events")
def public_events(slug: str, db: Session = Depends(get_db)):
    org, _, _ = _public_org(db, slug)
    if not VisibilityService.can_view(db, org.id, "events", user=None, ctx=None, fallback_level="PRIVATE"):
        return {"items": []}
    rel_ids = [r.event_id for r in db.query(EventStructure).filter_by(organization_id=org.id).all()]
    rows = db.query(Event).filter(or_(Event.id.in_(rel_ids or [-1]), and_(Event.host_type == "orga", Event.host_id == str(org.id))), func.upper(Event.visibility) == "PUBLIC", func.upper(Event.publication_status) == "PUBLISHED").order_by(Event.starts_at.desc()).all()
    return {"items": [{"id": e.id, "name": e.name, "startsAt": e.starts_at.isoformat(), "endsAt": e.ends_at.isoformat(), "venue": e.venue, "city": e.city, "description": e.public_description, "capacity": e.capacity} for e in rows]}


@router.get("/public/events/{event_id}/summary")
def public_event_summary(event_id: int, db: Session = Depends(get_db)):
    relation = db.query(EventStructure).filter_by(event_id=event_id, role="HOST").first()
    event = db.get(Event, event_id)
    if event is None or relation is None:
        raise HTTPException(404, detail="Event not found")
    org = db.get(Organization, relation.organization_id)
    if org is None:
        raise HTTPException(404, detail="Event not found")
    _public_org(db, org.slug)
    if not VisibilityService.can_view(db, org.id, "stats", user=None, ctx=None, fallback_level="PRIVATE") or (event.visibility or "PRIVATE").upper() != "PUBLIC" or (event.publication_status or "DRAFT").upper() != "PUBLISHED":
        raise HTTPException(404, detail="Summary not found")
    row = db.query(EventPublicSummary).filter_by(event_id=event.id, organization_id=org.id).first()
    if row is None:
        raise HTTPException(404, detail="Summary not found")
    return {"eventId": event.id, "entries": row.entries, "scans": row.scans, "capacity": row.capacity, "occupancyPercent": row.occupancy_percent, "publishedAt": row.published_at.isoformat()}


@router.get("/public/structures/{slug}/albums")
def public_albums(slug: str, db: Session = Depends(get_db)):
    org, _, _ = _public_org(db, slug)
    if not VisibilityService.can_view(db, org.id, "albums", user=None, ctx=None, fallback_level="PRIVATE"):
        return {"items": []}
    rows = db.query(StructureAlbum).filter(StructureAlbum.organization_id == org.id, StructureAlbum.archived_at.is_(None), func.upper(StructureAlbum.status) == "PUBLISHED", func.upper(StructureAlbum.visibility).in_(["PUBLIC"])).order_by(StructureAlbum.created_at.desc()).all()
    return {"items": [_album_out(db, row) for row in rows]}


@router.get("/public/media/{media_id}")
def public_media(media_id: int, db: Session = Depends(get_db)):
    asset = db.get(StructureMediaAsset, media_id)
    if asset is None:
        raise HTTPException(404, detail="Media not found")
    org = db.get(Organization, asset.organization_id)
    if org is None:
        raise HTTPException(404, detail="Media not found")
    _public_org(db, org.slug)
    if not VisibilityService.can_view(db, org.id, "albums", user=None, ctx=None, fallback_level="PRIVATE"):
        raise HTTPException(404, detail="Media not found")
    links = db.query(StructureAlbumMedia).filter_by(organization_id=org.id, media_id=media_id).all()
    allowed = False
    for link in links:
        album = db.get(StructureAlbum, link.album_id)
        if album and album.archived_at is None and album.status == "PUBLISHED" and normalize_visibility(album.visibility) == "PUBLIC":
            allowed = True
            break
    if not allowed:
        raise HTTPException(404, detail="Media not found")
    return FileResponse(get_forum_storage().local_path(asset.storage_key), media_type=asset.mime_type)


@router.get("/public/structures/{slug}/folklore")
def public_folklore(slug: str, db: Session = Depends(get_db)):
    org, _, _ = _public_org(db, slug)
    if not VisibilityService.can_view(db, org.id, "folklore", user=None, ctx=None, fallback_level="PRIVATE"):
        return {"items": []}
    rows = db.query(StructurePage).filter(StructurePage.organization_id == org.id, StructurePage.published_at.is_not(None), func.upper(StructurePage.visibility) == "PUBLIC").order_by(StructurePage.updated_at.desc()).all()
    return {"items": [_page_out(row) for row in rows]}


@router.get("/public/structures/{slug}/posts")
def public_posts(slug: str, db: Session = Depends(get_db)):
    org, _, _ = _public_org(db, slug)
    if not VisibilityService.can_view(db, org.id, "publications", user=None, ctx=None, fallback_level="PRIVATE"):
        return {"items": []}
    now = now_utc()
    rows = db.query(OrgaPost, OrgaPostPublication).join(OrgaPostPublication, OrgaPostPublication.post_id == OrgaPost.id).filter(OrgaPost.organization_id == org.id, OrgaPost.deleted_at.is_(None), OrgaPostPublication.visibility == "PUBLIC", or_(OrgaPostPublication.status == "PUBLISHED", and_(OrgaPostPublication.status == "SCHEDULED", OrgaPostPublication.publish_at.is_not(None), OrgaPostPublication.publish_at <= now))).order_by(OrgaPost.created_at.desc()).all()
    return {"items": [_post_out(post, publication) for post, publication in rows]}
