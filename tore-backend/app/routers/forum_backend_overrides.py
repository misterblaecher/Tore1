"""Typed Forum v2 endpoints that replace legacy-compatible route definitions.

These routes are composed in ``app.main`` after the original Forum router has
had the replaced route objects removed.  Keeping the replacement isolated lets
us harden the public contract without duplicating domain logic.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import now_utc
from models import AppUser, StructureDiscussionPost
from app.forum_models import StructureGovernance, StructurePublicPage
from app.legacy.monolith import get_current_user, get_db
from app.schemas.forum_backend import MessageCreateIn, PublicPagePatchIn
from app.routers.forum_backend import (
    _channel_scoped,
    _ctx,
    _document_scoped,
    _limit,
    _organization,
)
from app.services.forum_authorization import AuthorizationService
from app.services.forum_audit import write_structure_audit


router = APIRouter(prefix="/forum/v2", tags=["forum-v2"])


@router.patch("/structures/{slug}/public-page")
def patch_public_page(
    slug: str,
    payload: PublicPagePatchIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "visibility.manage")
    page = db.get(StructurePublicPage, org.id)
    governance = db.get(StructureGovernance, org.id)
    if page is None or governance is None:
        raise HTTPException(status_code=409, detail={"reason": "FORUM_FOUNDATION_MISSING"})

    before = {
        "status": page.status,
        "seoEnabled": page.seo_enabled,
        "indexable": page.indexable,
        "structureStatus": governance.status,
    }
    page.status = payload.status
    if payload.seo_enabled is not None:
        page.seo_enabled = payload.seo_enabled
    if payload.indexable is not None:
        page.indexable = payload.indexable
    if payload.status == "PUBLISHED":
        if page.published_at is None:
            page.published_at = now_utc()
        # Publishing completes initial setup, but must never reactivate a
        # LOCKED/ARCHIVED structure implicitly.
        if governance.status == "SETUP":
            governance.status = "ACTIVE"
            governance.updated_at = now_utc()
    page.updated_at = now_utc()

    # Keep the existing TORÈ mobile/public contract coherent during migration.
    org.visibility = "PUBLIC" if payload.status == "PUBLISHED" else "PRIVATE"
    after = {
        "status": page.status,
        "seoEnabled": page.seo_enabled,
        "indexable": page.indexable,
        "structureStatus": governance.status,
    }
    write_structure_audit(
        db,
        organization_id=org.id,
        actor_user_id=user.id,
        actor_role=ctx.role.name,
        action="forum.public_page.update",
        resource_type="structure_public_page",
        resource_id=str(org.id),
        before=before,
        after=after,
    )
    db.commit()
    return after


@router.post("/structures/{slug}/channels/{channel_id}/messages", status_code=201)
def post_message(
    slug: str,
    channel_id: int,
    payload: MessageCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a channel message from an explicit Pydantic request body."""
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.post")
    _limit("forum_message_post", f"{user.id}:{org.id}")
    channel = _channel_scoped(db, org.id, channel_id)
    if not AuthorizationService.can_post_channel(ctx, channel):
        raise HTTPException(status_code=404, detail="Channel not found")

    if payload.parent_message_id is not None:
        parent = db.get(StructureDiscussionPost, payload.parent_message_id)
        if (
            parent is None
            or parent.organization_id != org.id
            or parent.channel_id != channel.id
            or parent.is_archived
        ):
            raise HTTPException(status_code=404, detail="Parent message not found")

    for document_id in payload.document_ids:
        doc = _document_scoped(db, org.id, document_id)
        if not AuthorizationService.can_read_document(ctx, doc):
            raise HTTPException(status_code=404, detail="Document not found")

    row = StructureDiscussionPost(
        organization_id=org.id,
        channel_id=channel.id,
        parent_id=payload.parent_message_id,
        document_ids=list(set(payload.document_ids)),
        title=(payload.title or payload.body[:80] or "Message").strip(),
        body=payload.body.strip(),
        created_by_user_id=user.id,
        is_pinned=False,
        is_archived=False,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(row)
    db.flush()
    db.commit()
    return {
        "id": row.id,
        "body": row.body,
        "parentMessageId": row.parent_id,
        "createdAt": row.created_at.isoformat(),
    }
