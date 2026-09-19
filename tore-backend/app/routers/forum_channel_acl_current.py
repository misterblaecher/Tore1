from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from db import now_utc
from models import AppUser, OrganizationMembership, StructureDiscussionCategory, StructureDiscussionChannel, StructureDiscussionPost, StructureDiscussionReaction, StructureDocument
from app.forum_acl_models import StructureChannelAcl, StructureChannelAclGrant
from app.legacy.monolith import get_current_user
from app.deps.db import get_db
from app.models.structure_rbac import StructureRole
from app.routers.forum import DiscussionActionIn, DiscussionCreateIn, _can_view, _discussion_payload, _document_payload, _save_idem, _structure_or_404, _write_idem
from app.services.audit_service import write_audit_log
from app.services.forum_channel_acl_current import can_read, explicit_enabled
from app.services.structure_rbac import STRUCTURE_CAPABILITIES, capabilities_for_user, require_capability

router = APIRouter(prefix="/forum", tags=["forum-channel-acl"])


class AclUpdateIn(BaseModel):
    enabled: bool = True
    role_ids: list[int] = Field(default_factory=list, max_length=100)
    capabilities: list[str] = Field(default_factory=list, max_length=100)
    member_user_ids: list[str] = Field(default_factory=list, max_length=100)


def _ctx(db: Session, org_id: int, user: AppUser):
    return capabilities_for_user(db, org_id, user.id)


def _channel(db: Session, org_id: int, channel_id: int):
    row = db.get(StructureDiscussionChannel, channel_id)
    if not row or row.organization_id != org_id:
        raise HTTPException(404, detail="Channel not found")
    return row


def _post(db: Session, org_id: int, post_id: int, membership: OrganizationMembership):
    row = db.get(StructureDiscussionPost, post_id)
    if not row or row.organization_id != org_id or row.is_archived:
        raise HTTPException(404, detail="Discussion inaccessible")
    channel = _channel(db, org_id, row.channel_id)
    if not can_read(db, channel, membership):
        raise HTTPException(404, detail="Discussion inaccessible")
    return row


def _state(db: Session, org_id: int, channel: StructureDiscussionChannel, options: bool = False):
    acl = db.get(StructureChannelAcl, channel.id)
    grants = db.query(StructureChannelAclGrant).filter_by(organization_id=org_id, channel_id=channel.id).all()
    out = {
        "channelId": channel.id,
        "enabled": bool(acl and acl.enabled),
        "legacyVisibility": channel.visibility,
        "roleIds": [int(g.subject_key) for g in grants if g.subject_type == "ROLE" and g.subject_key.isdigit()],
        "capabilities": [g.subject_key for g in grants if g.subject_type == "CAPABILITY"],
        "memberUserIds": [g.subject_key for g in grants if g.subject_type == "MEMBER"],
    }
    if options:
        roles = db.query(StructureRole).filter(or_(StructureRole.organization_id == org_id, StructureRole.organization_id.is_(None))).order_by(StructureRole.name).all()
        members = db.query(OrganizationMembership).filter_by(organization_id=org_id, status="ACTIVE").all()
        names = []
        for member in members:
            target = db.get(AppUser, member.user_id)
            names.append({"userId": member.user_id, "displayName": target.display_name if target and target.display_name else member.user_id})
        out["options"] = {
            "roles": [{"id": role.id, "name": role.name} for role in roles],
            "capabilities": list(STRUCTURE_CAPABILITIES),
            "members": names,
        }
    return out


@router.get("/structures/{slug}/channel-acl-options")
def acl_options(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    require_capability(db, org.id, user, "channel.manage")
    rows = db.query(StructureDiscussionChannel).filter_by(organization_id=org.id, is_archived=False).order_by(StructureDiscussionChannel.name).all()
    return {"items": [{"id": row.id, "name": row.name, "visibility": row.visibility, "aclExplicit": explicit_enabled(db, row.id)} for row in rows]}


@router.get("/structures/{slug}/channels/{channel_id}/acl")
def get_acl(slug: str, channel_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    require_capability(db, org.id, user, "channel.manage")
    return _state(db, org.id, _channel(db, org.id, channel_id), True)


@router.put("/structures/{slug}/channels/{channel_id}/acl")
def put_acl(slug: str, channel_id: int, payload: AclUpdateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    actor = require_capability(db, org.id, user, "channel.manage")
    channel = _channel(db, org.id, channel_id)
    before = _state(db, org.id, channel)
    unknown = set(payload.capabilities) - set(STRUCTURE_CAPABILITIES)
    if unknown:
        raise HTTPException(422, detail={"reason": "UNKNOWN_CAPABILITY", "capabilities": sorted(unknown)})
    valid_roles = {role.id for role in db.query(StructureRole).filter(StructureRole.id.in_(payload.role_ids or [-1])).all() if role.organization_id is None or role.organization_id == org.id}
    if valid_roles != set(payload.role_ids):
        raise HTTPException(422, detail={"reason": "ROLE_OUTSIDE_STRUCTURE"})
    valid_members = {row[0] for row in db.query(OrganizationMembership.user_id).filter(OrganizationMembership.organization_id == org.id, OrganizationMembership.user_id.in_(payload.member_user_ids or ["__none__"])).all()}
    if valid_members != set(payload.member_user_ids):
        raise HTTPException(422, detail={"reason": "MEMBER_OUTSIDE_STRUCTURE"})
    acl = db.get(StructureChannelAcl, channel.id)
    if not acl:
        acl = StructureChannelAcl(channel_id=channel.id, organization_id=org.id, created_at=now_utc(), updated_at=now_utc())
        db.add(acl)
    acl.enabled = payload.enabled
    acl.updated_by_user_id = user.id
    acl.updated_at = now_utc()
    db.query(StructureChannelAclGrant).filter_by(organization_id=org.id, channel_id=channel.id).delete(synchronize_session=False)
    for role_id in payload.role_ids:
        db.add(StructureChannelAclGrant(organization_id=org.id, channel_id=channel.id, subject_type="ROLE", subject_key=str(role_id), created_by_user_id=user.id, created_at=now_utc()))
    for capability in payload.capabilities:
        db.add(StructureChannelAclGrant(organization_id=org.id, channel_id=channel.id, subject_type="CAPABILITY", subject_key=capability, created_by_user_id=user.id, created_at=now_utc()))
    for user_id in payload.member_user_ids:
        db.add(StructureChannelAclGrant(organization_id=org.id, channel_id=channel.id, subject_type="MEMBER", subject_key=user_id, created_by_user_id=user.id, created_at=now_utc()))
    db.flush()
    after = _state(db, org.id, channel)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.channel.acl.replace", entity_type="structure_discussion_channel", entity_id=str(channel.id), event_id=None, committee_id=None, bar_id=None, payload={"structure_id": org.id, "before": before, "after": after})
    db.commit()
    return _state(db, org.id, channel, True)


@router.get("/structures/{slug}/discussions")
def list_discussions(slug: str, search: Optional[str] = Query(default=None, max_length=120), channel_id: Optional[int] = None, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    membership, _caps = _ctx(db, org.id, user)
    categories = db.query(StructureDiscussionCategory).filter_by(organization_id=org.id, is_archived=False).order_by(StructureDiscussionCategory.order_index).all()
    channels = [row for row in db.query(StructureDiscussionChannel).filter_by(organization_id=org.id, is_archived=False).order_by(StructureDiscussionChannel.name).all() if can_read(db, row, membership)]
    channel_ids = [row.id for row in channels]
    query = db.query(StructureDiscussionPost).filter(StructureDiscussionPost.organization_id == org.id, StructureDiscussionPost.channel_id.in_(channel_ids or [-1]), StructureDiscussionPost.is_archived.is_(False))
    if channel_id is not None:
        if channel_id not in channel_ids:
            raise HTTPException(404, detail="Salon inaccessible")
        query = query.filter(StructureDiscussionPost.channel_id == channel_id)
    if search and search.strip():
        needle = f"%{search.strip().lower()}%"
        query = query.filter(or_(func.lower(StructureDiscussionPost.title).like(needle), func.lower(StructureDiscussionPost.body).like(needle)))
    posts = query.order_by(StructureDiscussionPost.created_at.desc(), StructureDiscussionPost.id.desc()).limit(300).all()
    return {
        "categories": [{"id": row.id, "name": row.name, "slug": row.slug} for row in categories if any(channel.category_id == row.id for channel in channels)],
        "channels": [{"id": row.id, "categoryId": row.category_id, "name": row.name, "slug": row.slug, "visibility": row.visibility, "aclExplicit": explicit_enabled(db, row.id)} for row in channels],
        "posts": [_discussion_payload(db, post, membership) for post in posts],
        "limited": len(posts) == 300,
    }


@router.post("/structures/{slug}/discussions")
def create_discussion(slug: str, payload: DiscussionCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = require_capability(db, org.id, user, "discussion.write")
    key, previous = _write_idem(db, user, f"forum_discussion_create:{org.id}", idempotency_key)
    if previous is not None:
        return previous

    channel = db.get(StructureDiscussionChannel, payload.channel_id) if payload.channel_id else db.query(StructureDiscussionChannel).filter_by(organization_id=org.id, slug="general", is_archived=False).first()
    if payload.channel_id is None and channel is None:
        category = db.query(StructureDiscussionCategory).filter_by(organization_id=org.id, slug="general").first()
        if category is None:
            category = StructureDiscussionCategory(organization_id=org.id, name="Général", slug="general", order_index=0, created_at=now_utc())
            db.add(category)
            db.flush()
        channel = StructureDiscussionChannel(organization_id=org.id, category_id=category.id, name="Général", slug="general", visibility="STRUCTURE_MEMBERS", created_at=now_utc())
        db.add(channel)
        db.flush()

    if not channel or channel.organization_id != org.id or channel.is_archived or not can_read(db, channel, actor):
        raise HTTPException(404, detail="Salon inaccessible")
    if not payload.body.strip() or len(payload.title.strip()) < 2:
        raise HTTPException(422, detail="Le titre et le message sont obligatoires")
    if payload.parent_id is not None:
        parent = _post(db, org.id, payload.parent_id, actor)
        if parent.channel_id != channel.id or parent.parent_id is not None:
            raise HTTPException(400, detail="Fil de réponse invalide")
    for doc_id in payload.document_ids:
        document = db.get(StructureDocument, doc_id)
        if not document or document.organization_id != org.id or document.archived_at or not _can_view(document.visibility, actor):
            raise HTTPException(404, detail="Document inaccessible")
    row = StructureDiscussionPost(organization_id=org.id, channel_id=channel.id, parent_id=payload.parent_id, document_ids=list(set(payload.document_ids)), title=payload.title.strip(), body=payload.body.strip(), created_by_user_id=user.id, created_at=now_utc(), updated_at=now_utc())
    db.add(row)
    db.flush()
    response = _discussion_payload(db, row, actor)
    _save_idem(db, user, f"forum_discussion_create:{org.id}", key, response)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="forum.discussion.create",
        entity_type="structure_discussion_post",
        entity_id=str(row.id),
        event_id=None,
        committee_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={"structure_id": org.id, "channel_id": channel.id},
    )
    db.commit()
    return response


@router.patch("/structures/{slug}/discussions/{post_id}")
def update_discussion(slug: str, post_id: int, payload: DiscussionActionIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = require_capability(db, org.id, user, "discussion.write")
    row = _post(db, org.id, post_id, actor)
    key, previous = _write_idem(db, user, f"forum_discussion_action:{post_id}", idempotency_key)
    if previous is not None:
        return previous
    if payload.pinned is not None:
        require_capability(db, org.id, user, "discussion.manage")
        if row.parent_id is not None:
            raise HTTPException(400, detail="Seules les discussions peuvent être épinglées")
        row.is_pinned = payload.pinned
    if payload.emoji:
        reaction = db.query(StructureDiscussionReaction).filter_by(post_id=row.id, user_id=user.id, emoji=payload.emoji).first()
        if payload.active and not reaction:
            db.add(StructureDiscussionReaction(post_id=row.id, user_id=user.id, emoji=payload.emoji))
        elif not payload.active and reaction:
            db.delete(reaction)
    db.flush()
    response = _discussion_payload(db, row, actor)
    _save_idem(db, user, f"forum_discussion_action:{post_id}", key, response)
    db.commit()
    return response


@router.get("/structures/{slug}/documents")
def list_documents_acl(slug: str, search: Optional[str] = Query(default=None, max_length=120), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    membership = require_capability(db, org.id, user, "document.read")
    query = db.query(StructureDocument).filter(StructureDocument.organization_id == org.id, StructureDocument.archived_at.is_(None))
    if search and search.strip():
        needle = f"%{search.strip().lower()}%"
        query = query.filter(or_(func.lower(StructureDocument.title).like(needle), func.lower(func.coalesce(StructureDocument.folder, "")).like(needle)))
    denied_channels = {channel.id for channel in db.query(StructureDiscussionChannel).filter_by(organization_id=org.id).all() if not can_read(db, channel, membership)}
    denied_posts = db.query(StructureDiscussionPost).filter(StructureDiscussionPost.organization_id == org.id, StructureDiscussionPost.channel_id.in_(denied_channels or [-1])).all()
    denied_docs = {doc_id for post in denied_posts for doc_id in (post.document_ids or [])}
    accessible_posts = db.query(StructureDiscussionPost).filter(StructureDiscussionPost.organization_id == org.id, ~StructureDiscussionPost.channel_id.in_(denied_channels or [-1])).all()
    accessible_docs = {doc_id for post in accessible_posts for doc_id in (post.document_ids or [])}
    return {"items": [_document_payload(document) for document in query.order_by(StructureDocument.created_at.desc()).all() if _can_view(document.visibility, membership) and (document.id not in denied_docs or document.id in accessible_docs)]}
