from __future__ import annotations

"""ACL-aware Forum v2 discussion endpoints.

These handlers replace the compatibility channel/message/document-search reads in
``app.main``.  Every descendant resource is authorized through its parent
channel before serialization so direct ids are not an ACL bypass.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from db import now_utc
from models import (
    AppUser,
    Event,
    StructureDiscussionChannel,
    StructureDiscussionPost,
    StructureDiscussionReaction,
    StructureDocument,
    StructurePage,
)
from app.forum_models import EventStructure, StructureDocumentVersion
from app.legacy.monolith import get_current_user, get_db
from app.routers.forum_backend import (
    _channel_scoped,
    _ctx,
    _document_scoped,
    _limit,
    _organization,
)
from app.schemas.forum_backend import MessageCreateIn
from app.services.forum_audit import write_structure_audit
from app.services.forum_authorization import AuthorizationService, normalize_visibility
from app.services.forum_channel_acl import ChannelAclService
from app.services.forum_storage import get_forum_storage


router = APIRouter(prefix="/forum/v2", tags=["forum-v2-channel-acl"])


class ChannelAclUpdateIn(BaseModel):
    enabled: bool = True
    role_ids: list[int] = Field(default_factory=list, max_length=100)
    capabilities: list[str] = Field(default_factory=list, max_length=100)
    member_user_ids: list[str] = Field(default_factory=list, max_length=100)


class ReactionUpdateIn(BaseModel):
    emoji: str = Field(min_length=1, max_length=16)
    active: bool = True


def _message_out(message: StructureDiscussionPost) -> dict:
    return {
        "id": message.id,
        "channelId": message.channel_id,
        "title": message.title,
        "body": message.body,
        "parentMessageId": message.parent_id,
        "documentIds": list(message.document_ids or []),
        "authorUserId": message.created_by_user_id,
        "pinned": bool(message.is_pinned),
        "createdAt": message.created_at.isoformat() if message.created_at else None,
        "updatedAt": message.updated_at.isoformat() if message.updated_at else None,
    }


def _document_out(db: Session, organization_id: int, doc: StructureDocument) -> dict:
    versions = db.query(StructureDocumentVersion).filter_by(
        organization_id=organization_id,
        document_id=doc.id,
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


@router.get("/structures/{slug}/channels")
def list_channels(
    slug: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.read")
    rows = db.query(StructureDiscussionChannel).filter_by(
        organization_id=org.id,
        is_archived=False,
    ).order_by(StructureDiscussionChannel.id).all()
    return {
        "items": [
            {
                "id": channel.id,
                "categoryId": channel.category_id,
                "name": channel.name,
                "visibility": normalize_visibility(channel.visibility),
                "aclExplicit": ChannelAclService.explicit_enabled(db, channel),
            }
            for channel in rows
            if ChannelAclService.can_read(db, ctx, channel)
        ]
    }


@router.get("/structures/{slug}/channels/{channel_id}")
def get_channel(
    slug: str,
    channel_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.read")
    channel = _channel_scoped(db, org.id, channel_id)
    ChannelAclService.require_read(db, ctx, channel)
    return {
        "id": channel.id,
        "categoryId": channel.category_id,
        "name": channel.name,
        "visibility": normalize_visibility(channel.visibility),
        "aclExplicit": ChannelAclService.explicit_enabled(db, channel),
    }


@router.get("/structures/{slug}/channels/{channel_id}/acl")
def get_channel_acl(
    slug: str,
    channel_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.manage")
    channel = _channel_scoped(db, org.id, channel_id)
    return ChannelAclService.state(db, ctx, channel, options=True)


@router.put("/structures/{slug}/channels/{channel_id}/acl")
def replace_channel_acl(
    slug: str,
    channel_id: int,
    payload: ChannelAclUpdateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.manage")
    channel = _channel_scoped(db, org.id, channel_id)
    before = ChannelAclService.state(db, ctx, channel)
    after = ChannelAclService.replace(
        db,
        ctx,
        channel,
        enabled=payload.enabled,
        role_ids=payload.role_ids,
        capabilities=payload.capabilities,
        member_user_ids=payload.member_user_ids,
    )
    write_structure_audit(
        db,
        organization_id=org.id,
        actor_user_id=user.id,
        actor_role=ctx.role.name,
        action="forum.channel.acl.update",
        resource_type="forum_channel_acl",
        resource_id=str(channel.id),
        before=before,
        after=after,
        context={"channelName": channel.name},
    )
    db.commit()
    return ChannelAclService.state(db, ctx, channel, options=True)


@router.get("/structures/{slug}/channels/{channel_id}/messages")
def list_messages(
    slug: str,
    channel_id: int,
    limit: int = Query(default=100, ge=1, le=300),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.read")
    channel = _channel_scoped(db, org.id, channel_id)
    ChannelAclService.require_read(db, ctx, channel)
    rows = db.query(StructureDiscussionPost).filter_by(
        organization_id=org.id,
        channel_id=channel.id,
        is_archived=False,
    ).order_by(StructureDiscussionPost.created_at.asc(), StructureDiscussionPost.id.asc()).limit(limit).all()
    return {"items": [_message_out(message) for message in rows]}


@router.post("/structures/{slug}/channels/{channel_id}/messages", status_code=201)
def post_message(
    slug: str,
    channel_id: int,
    payload: MessageCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.post")
    _limit("forum_message_post", f"{user.id}:{org.id}")
    channel = _channel_scoped(db, org.id, channel_id)
    ChannelAclService.require_post(db, ctx, channel)

    if payload.parent_message_id is not None:
        parent = ChannelAclService.message_for_user(
            db, ctx, payload.parent_message_id, channel_id=channel.id
        )
        if parent.is_archived:
            raise HTTPException(status_code=404, detail="Parent message not found")

    for document_id in payload.document_ids:
        document = _document_scoped(db, org.id, document_id)
        if not ChannelAclService.can_read_document(db, ctx, document):
            raise HTTPException(status_code=404, detail="Document not found")

    row = StructureDiscussionPost(
        organization_id=org.id,
        channel_id=channel.id,
        parent_id=payload.parent_message_id,
        document_ids=sorted(set(payload.document_ids)),
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
    response = _message_out(row)
    db.commit()
    return response


@router.get("/structures/{slug}/messages/{message_id}")
def get_message(
    slug: str,
    message_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.read")
    message = ChannelAclService.message_for_user(db, ctx, message_id)
    return _message_out(message)


@router.get("/structures/{slug}/messages/{message_id}/thread")
def get_thread(
    slug: str,
    message_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.read")
    root = ChannelAclService.message_for_user(db, ctx, message_id)
    if root.parent_id is not None:
        root = ChannelAclService.message_for_user(db, ctx, root.parent_id, channel_id=root.channel_id)
    replies = db.query(StructureDiscussionPost).filter_by(
        organization_id=org.id,
        channel_id=root.channel_id,
        parent_id=root.id,
        is_archived=False,
    ).order_by(StructureDiscussionPost.created_at.asc(), StructureDiscussionPost.id.asc()).all()
    return {"root": _message_out(root), "replies": [_message_out(reply) for reply in replies]}


@router.post("/structures/{slug}/messages/{message_id}/reactions")
def update_reaction(
    slug: str,
    message_id: int,
    payload: ReactionUpdateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.post")
    message = ChannelAclService.message_for_user(db, ctx, message_id)
    channel = _channel_scoped(db, org.id, message.channel_id)
    ChannelAclService.require_post(db, ctx, channel)

    row = db.query(StructureDiscussionReaction).filter_by(
        post_id=message.id,
        user_id=user.id,
        emoji=payload.emoji,
    ).first()
    if payload.active and row is None:
        db.add(StructureDiscussionReaction(post_id=message.id, user_id=user.id, emoji=payload.emoji))
    elif not payload.active and row is not None:
        db.delete(row)
    db.commit()
    count = db.query(StructureDiscussionReaction).filter_by(
        post_id=message.id,
        emoji=payload.emoji,
    ).count()
    return {"emoji": payload.emoji, "count": count, "mine": payload.active}


@router.get("/structures/{slug}/messages/{message_id}/attachments/{document_id}")
def get_message_attachment(
    slug: str,
    message_id: int,
    document_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.read")
    _, document = ChannelAclService.attachment_for_user(db, ctx, message_id, document_id)
    if "documents.view" not in ctx.permissions:
        raise HTTPException(status_code=403, detail={"reason": "FORUM_PERMISSION_DENIED", "permission": "documents.view"})
    return _document_out(db, org.id, document)


@router.get("/structures/{slug}/messages/{message_id}/attachments/{document_id}/download")
def download_message_attachment(
    slug: str,
    message_id: int,
    document_id: int,
    version: Optional[int] = Query(default=None, ge=1),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "channels.read")
    _, document = ChannelAclService.attachment_for_user(db, ctx, message_id, document_id)
    if "documents.download" not in ctx.permissions:
        raise HTTPException(status_code=403, detail={"reason": "FORUM_PERMISSION_DENIED", "permission": "documents.download"})
    query = db.query(StructureDocumentVersion).filter_by(
        organization_id=org.id,
        document_id=document.id,
    )
    if version is not None:
        query = query.filter_by(version_number=version)
    file_version = query.order_by(StructureDocumentVersion.version_number.desc()).first()
    if file_version is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = get_forum_storage().local_path(file_version.storage_key)
    return FileResponse(path, media_type=file_version.mime_type, filename=file_version.original_name)


@router.get("/structures/{slug}/documents")
def list_documents(
    slug: str,
    q: Optional[str] = Query(default=None, max_length=120),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "documents.view")
    query = db.query(StructureDocument).filter(
        StructureDocument.organization_id == org.id,
        StructureDocument.archived_at.is_(None),
    )
    if q:
        needle = f"%{q.strip()}%"
        query = query.filter(or_(StructureDocument.title.ilike(needle), StructureDocument.description.ilike(needle)))
    rows = query.order_by(StructureDocument.updated_at.desc(), StructureDocument.id.desc()).limit(300).all()
    return {"items": [_document_out(db, org.id, doc) for doc in rows if ChannelAclService.can_read_document(db, ctx, doc)]}


@router.get("/structures/{slug}/documents/{document_id}")
def get_document_metadata(
    slug: str,
    document_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "documents.view")
    document = _document_scoped(db, org.id, document_id)
    if not ChannelAclService.can_read_document(db, ctx, document):
        raise HTTPException(status_code=404, detail="Document not found")
    return _document_out(db, org.id, document)


@router.get("/structures/{slug}/documents/{document_id}/download")
def download_document(
    slug: str,
    document_id: int,
    version: Optional[int] = Query(default=None, ge=1),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "documents.download")
    document = _document_scoped(db, org.id, document_id)
    if not ChannelAclService.can_read_document(db, ctx, document):
        raise HTTPException(status_code=404, detail="Document not found")
    query = db.query(StructureDocumentVersion).filter_by(
        organization_id=org.id,
        document_id=document.id,
    )
    if version is not None:
        query = query.filter_by(version_number=version)
    file_version = query.order_by(StructureDocumentVersion.version_number.desc()).first()
    if file_version is None:
        raise HTTPException(status_code=404, detail="Document not found")
    path = get_forum_storage().local_path(file_version.storage_key)
    return FileResponse(path, media_type=file_version.mime_type, filename=file_version.original_name)


@router.get("/structures/{slug}/search")
def search_structure(
    slug: str,
    q: str = Query(min_length=2, max_length=120),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    ctx = _ctx(db, org, user, "search.view")
    _limit("forum_search", f"{user.id}:{org.id}")
    needle = f"%{q.strip()}%"
    results: list[dict] = []

    relation_ids = [row.event_id for row in db.query(EventStructure).filter_by(organization_id=org.id).all()]
    for event in db.query(Event).filter(
        or_(
            and_(Event.host_type == "orga", Event.host_id == str(org.id)),
            Event.id.in_(relation_ids or [-1]),
        ),
        Event.name.ilike(needle),
    ).limit(30).all():
        results.append({"type": "event", "id": event.id, "title": event.name})

    for document in db.query(StructureDocument).filter(
        StructureDocument.organization_id == org.id,
        StructureDocument.archived_at.is_(None),
        or_(StructureDocument.title.ilike(needle), StructureDocument.description.ilike(needle)),
    ).limit(30).all():
        if ChannelAclService.can_read_document(db, ctx, document):
            results.append({"type": "document", "id": document.id, "title": document.title})

    for page in db.query(StructurePage).filter(
        StructurePage.organization_id == org.id,
        or_(StructurePage.title.ilike(needle), StructurePage.content.ilike(needle)),
    ).limit(30).all():
        if AuthorizationService.can_view_level(page.visibility, user, ctx):
            results.append({"type": "folklore", "id": page.id, "title": page.title})

    channels = [
        channel
        for channel in db.query(StructureDiscussionChannel).filter_by(
            organization_id=org.id, is_archived=False
        ).all()
        if ChannelAclService.can_read(db, ctx, channel)
    ]
    channel_ids = [channel.id for channel in channels]
    if channel_ids:
        for message in db.query(StructureDiscussionPost).filter(
            StructureDiscussionPost.organization_id == org.id,
            StructureDiscussionPost.channel_id.in_(channel_ids),
            StructureDiscussionPost.is_archived.is_(False),
            or_(StructureDiscussionPost.title.ilike(needle), StructureDiscussionPost.body.ilike(needle)),
        ).limit(30).all():
            results.append({
                "type": "message",
                "id": message.id,
                "title": message.title,
                "channelId": message.channel_id,
            })
    return {"items": results[:100]}
