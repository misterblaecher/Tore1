"""Typed Forum v2 endpoints that replace or extend compatibility route definitions.

These routes are composed in ``app.main`` after the original Forum router has
had the replaced route objects removed. Keeping the replacement isolated lets
us harden the public contract without duplicating the broader router.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import now_utc
from models import AppUser, OrgaPost, StructureDiscussionPost
from app.forum_models import (
    OrgaPostPublication,
    StructureDocumentVersion,
    StructureGovernance,
    StructurePageVersion,
    StructurePublicPage,
)
from app.legacy.monolith import get_current_user, get_db
from app.schemas.forum_backend import DocumentOut, DocumentPatchIn, MessageCreateIn, PublicPagePatchIn
from app.routers.forum_backend import (
    _channel_scoped,
    _ctx,
    _document_scoped,
    _event_scoped,
    _limit,
    _organization,
    _page_scoped,
)
from app.services.forum_authorization import AuthorizationService, normalize_visibility
from app.services.forum_audit import write_structure_audit


router = APIRouter(prefix="/forum/v2", tags=["forum-v2"])


def _document_out(db: Session, organization_id: int, doc) -> dict:
    versions = db.query(StructureDocumentVersion).filter_by(
        document_id=doc.id,
        organization_id=organization_id,
    ).order_by(StructureDocumentVersion.version_number.desc()).all()
    return {
        "id": doc.id,
        "title": doc.title,
        "description": doc.description,
        "folder": doc.folder,
        "tags": list(doc.tags_json or []),
        "visibility": normalize_visibility(doc.visibility),
        "eventId": doc.event_id,
        "currentVersion": versions[0].version_number if versions else 0,
        "versions": [
            {
                "version": version.version_number,
                "name": version.original_name,
                "mimeType": version.mime_type,
                "size": version.size_bytes,
                "checksum": version.checksum_sha256,
                "createdAt": version.created_at.isoformat(),
            }
            for version in versions
        ],
    }


def _post_out(post: OrgaPost, publication: OrgaPostPublication) -> dict:
    return {
        "id": post.id,
        "title": publication.title,
        "body": post.text,
        "eventId": publication.event_id,
        "mediaId": publication.media_id,
        "status": publication.status,
        "visibility": publication.visibility,
        "publishAt": publication.publish_at.isoformat() if publication.publish_at else None,
        "publishedAt": publication.published_at.isoformat() if publication.published_at else None,
        "createdAt": post.created_at.isoformat() if post.created_at else None,
    }


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


@router.get("/structures/{slug}/documents/{document_id}", response_model=DocumentOut)
def get_document_metadata(
    slug: str,
    document_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "documents.view")
    doc = _document_scoped(db, org.id, document_id)
    if not AuthorizationService.can_read_document(ctx, doc):
        raise HTTPException(status_code=404, detail="Document not found")
    return _document_out(db, org.id, doc)


@router.patch("/structures/{slug}/documents/{document_id}", response_model=DocumentOut)
def patch_document_metadata(
    slug: str,
    document_id: int,
    payload: DocumentPatchIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "documents.manage")
    doc = _document_scoped(db, org.id, document_id)
    before = _document_out(db, org.id, doc)
    values = payload.model_dump(exclude_unset=True)
    if values.get("event_id") is not None:
        _event_scoped(db, org.id, values["event_id"])
    if "title" in values and values["title"] is not None:
        doc.title = values["title"].strip()
    if "description" in values:
        doc.description = values["description"]
    if "folder" in values:
        doc.folder = values["folder"]
    if "tags" in values and values["tags"] is not None:
        doc.tags_json = [tag.strip() for tag in values["tags"] if tag.strip()]
    if "visibility" in values and values["visibility"] is not None:
        doc.visibility = values["visibility"]
    if "event_id" in values:
        doc.event_id = values["event_id"]
    doc.updated_at = now_utc()
    after = _document_out(db, org.id, doc)
    write_structure_audit(
        db,
        organization_id=org.id,
        actor_user_id=user.id,
        actor_role=ctx.role.name,
        action="forum.document.update",
        resource_type="document",
        resource_id=str(doc.id),
        before=before,
        after=after,
        event_id=doc.event_id,
    )
    db.commit()
    return after


@router.get("/structures/{slug}/folklore/{page_id}/versions")
def folklore_versions(
    slug: str,
    page_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full folklore history is an editor/admin surface, never a read bypass."""
    org = _organization(db, slug)
    _ctx(db, org, user, "folklore.manage")
    _page_scoped(db, org.id, page_id)
    rows = db.query(StructurePageVersion).filter_by(
        organization_id=org.id,
        page_id=page_id,
    ).order_by(StructurePageVersion.version_number.desc()).all()
    return {
        "items": [
            {
                "version": row.version_number,
                "title": row.title,
                "content": row.content,
                "category": row.category,
                "visibility": normalize_visibility(row.visibility),
                "createdAt": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


@router.get("/structures/{slug}/posts")
def list_posts(
    slug: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Managers see editorial state; members see only already-public content."""
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "structure.read")
    rows = db.query(OrgaPost, OrgaPostPublication).join(
        OrgaPostPublication,
        OrgaPostPublication.post_id == OrgaPost.id,
    ).filter(
        OrgaPost.organization_id == org.id,
        OrgaPost.deleted_at.is_(None),
    ).order_by(OrgaPost.created_at.desc()).all()

    can_manage_publications = "publications.manage" in ctx.permissions
    stamp = now_utc()
    items = []
    for post, publication in rows:
        if not AuthorizationService.can_view_level(publication.visibility, user, ctx):
            continue
        if not can_manage_publications:
            status = (publication.status or "DRAFT").upper()
            visible_now = status == "PUBLISHED" or (
                status == "SCHEDULED"
                and publication.publish_at is not None
                and publication.publish_at <= stamp
            )
            if not visible_now:
                continue
        items.append(_post_out(post, publication))
    return {"items": items}
