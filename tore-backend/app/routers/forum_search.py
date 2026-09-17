"""Permission-first global Forum search.

Every query is scoped to the structure and every row is checked before its
title, snippet, id, or count can enter the response.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from models import AppUser, Event, OrganizationMembership, StructureDocument, StructureDiscussionChannel, StructureDiscussionPost, StructurePage
from app.legacy.monolith import get_current_user, get_db
from app.routers.forum import _can_view, _require_role, _structure_or_404
from app.services.forum_channel_acl_current import can_read

router = APIRouter(prefix="/forum", tags=["forum-search"])

@router.get("/structures/{slug}/search")
def global_search(slug: str, q: str = Query(min_length=2, max_length=120), limit: int = Query(default=8, ge=1, le=20), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    membership = _require_role(db, org.id, user, "MEMBER")
    needle = f"%{q.strip().lower()}%"
    results: list[dict] = []
    def add(kind, title, snippet, target, row_id):
        if len(results) < limit * 7:
            results.append({"category": kind, "id": row_id, "title": title, "snippet": (snippet or "")[:180], "target": target})
    channels = [c for c in db.query(StructureDiscussionChannel).filter_by(organization_id=org.id, is_archived=False).all() if _can_view(c.visibility, membership) and can_read(db, c, membership)]
    channel_ids = [c.id for c in channels]
    for c in db.query(StructureDiscussionChannel).filter(StructureDiscussionChannel.id.in_(channel_ids), or_(func.lower(StructureDiscussionChannel.name).like(needle), func.lower(StructureDiscussionChannel.slug).like(needle))).limit(limit).all(): add("channels", c.name, "Salon de discussion", f"/forum/structures/{slug}/discussions?channel={c.id}", c.id)
    for p in db.query(StructureDiscussionPost).filter(StructureDiscussionPost.organization_id == org.id, StructureDiscussionPost.channel_id.in_(channel_ids), StructureDiscussionPost.is_archived.is_(False), or_(func.lower(StructureDiscussionPost.title).like(needle), func.lower(StructureDiscussionPost.body).like(needle))).order_by(StructureDiscussionPost.created_at.desc()).limit(limit).all(): add("messages", p.title, p.body, f"/forum/structures/{slug}/discussions?post={p.id}", p.id)
    for d in db.query(StructureDocument).filter(StructureDocument.organization_id == org.id, StructureDocument.archived_at.is_(None), or_(func.lower(StructureDocument.title).like(needle), func.lower(func.coalesce(StructureDocument.description, "")).like(needle))).limit(limit).all():
        if _can_view(d.visibility, membership): add("documents", d.title, d.description, f"/forum/structures/{slug}/documents", d.id)
    for p in db.query(StructurePage).filter(StructurePage.organization_id == org.id, or_(func.lower(StructurePage.title).like(needle), func.lower(StructurePage.content).like(needle))).limit(limit).all():
        if p.published_at is not None and _can_view(p.visibility, membership): add("folklore", p.title, p.content, f"/forum/structures/{slug}/folklore#{p.slug}", p.id)
    for e in db.query(Event).filter(Event.host_type == "orga", Event.host_id == str(org.id), or_(func.lower(Event.name).like(needle), func.lower(func.coalesce(Event.public_description, "")).like(needle))).limit(limit).all():
        if (e.publication_status or "DRAFT").upper() == "PUBLISHED" and _can_view(e.visibility, membership): add("events", e.name, e.public_description, f"/forum/structures/{slug}/events/{e.id}", e.id)
    return {"query": q, "results": results, "categories": sorted({r["category"] for r in results})}
