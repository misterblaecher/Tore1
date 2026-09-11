"""Forum / Structure API.

The existing Organization model is the first incremental Structure adapter.  This
router deliberately keeps the legacy organization and event APIs intact while
giving the web Forum one stable, structure-scoped contract.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from db import now_utc
from models import (
    AppUser,
    AuditLog,
    Entry,
    EntryScanLog,
    Event,
    EventCost,
    EventRuntimeState,
    Order,
    Organization,
    OrganizationMembership,
    OrganizationWriteIdempotency,
    StructureAlbum,
    StructureDiscussionCategory,
    StructureDiscussionChannel,
    StructureDiscussionPost,
    StructureDiscussionReaction,
    StructureDocument,
    StructureMedia,
    StructurePage,
)
from app.legacy.monolith import get_current_user, get_db
from app.services.audit_service import write_audit_log
from app.services.idempotency_service import ensure_idempotency_key


router = APIRouter(prefix="/forum", tags=["forum"])

STRUCTURE_TYPES = {"COMMITTEE", "CIRCLE", "ORDER", "BAR", "ASSOCIATION", "PARTNER", "OTHER"}
VISIBILITY_LEVELS = {"PUBLIC", "TORE_USERS", "STRUCTURE_MEMBERS", "STAFF", "OFFICE", "TREASURY", "ADMINS"}
ROLE_RANK = {
    "FOLLOWER": 0,
    "ANCIEN": 0,
    "MEMBER": 1,
    "STAFF": 2,
    "COMMUNICATION": 2,
    "ARCHIVIST": 2,
    "TREASURER": 3,
    "TRESORIER": 3,
    "SECRETARY": 3,
    "BUREAU": 4,
    "VICE_PRESIDENT": 4,
    "PRESIDENT": 4,
    "MANAGER": 4,
    "ADMIN": 5,
    "OWNER": 6,
}
DEFAULT_VISIBILITY = {
    "page": "PUBLIC",
    "description": "PUBLIC",
    "contact": "PUBLIC",
    "events": "PUBLIC",
    "members": "STRUCTURE_MEMBERS",
    "albums": "PUBLIC",
    "documents": "STRUCTURE_MEMBERS",
    "folklore": "PUBLIC",
    "stats": "ADMINS",
}


class MemberUpsertIn(BaseModel):
    user_id: str = Field(min_length=3, max_length=120)
    role: str = Field(default="MEMBER", min_length=2, max_length=32)
    status: str = Field(default="PENDING", pattern="^(ACTIVE|PENDING)$")
    mandate_label: Optional[str] = Field(default=None, max_length=120)
    visibility: str = Field(default="PRIVATE", pattern="^(PUBLIC|PRIVATE)$")
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class MemberPatchIn(BaseModel):
    role: Optional[str] = Field(default=None, min_length=2, max_length=32)
    status: Optional[str] = Field(default=None, pattern="^(ACTIVE|PENDING|REVOKED|LEFT)$")
    mandate_label: Optional[str] = Field(default=None, max_length=120)
    visibility: Optional[str] = Field(default=None, pattern="^(PUBLIC|PRIVATE)$")
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    reason: str = Field(default="Mise à jour depuis le Forum", min_length=2, max_length=280)


class DiscussionCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    body: str = Field(min_length=1, max_length=10000)
    channel_id: Optional[int] = None
    parent_id: Optional[int] = None
    document_ids: list[int] = Field(default_factory=list, max_length=8)


class ChannelCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    visibility: Literal["STRUCTURE_MEMBERS", "OFFICE", "TREASURY"] = "STRUCTURE_MEMBERS"


class DiscussionActionIn(BaseModel):
    pinned: Optional[bool] = None
    emoji: Optional[Literal["👍", "❤️", "✅"]] = None
    active: bool = True


class DocumentCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=5000)
    file_url: str = Field(min_length=8, max_length=1000)
    folder: Optional[str] = Field(default=None, max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=20)
    visibility: str = Field(default="STRUCTURE_MEMBERS", pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")
    event_id: Optional[int] = None


class AlbumCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=5000)
    cover_url: Optional[str] = Field(default=None, max_length=1000)
    visibility: str = Field(default="STRUCTURE_MEMBERS", pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")
    event_id: Optional[int] = None


class AlbumStatusIn(BaseModel):
    status: str = Field(pattern="^(DRAFT|PUBLISHED|ARCHIVED)$")
    reason: str = Field(default="Changement depuis le Forum", min_length=2, max_length=280)


class MediaCreateIn(BaseModel):
    media_url: str = Field(min_length=8, max_length=1000)
    media_type: str = Field(default="IMAGE", pattern="^(IMAGE|VIDEO|OTHER)$")
    caption: Optional[str] = Field(default=None, max_length=280)


class PageCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    slug: Optional[str] = Field(default=None, max_length=180)
    content: str = Field(default="", max_length=100000)
    visibility: str = Field(default="STRUCTURE_MEMBERS", pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")
    category: str = Field(default="OTHER", pattern="^(HISTORY|TRADITION|GLOSSARY|GUIDE|RULE|OTHER)$")
    published: bool = False


class PagePatchIn(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=180)
    content: Optional[str] = Field(default=None, max_length=100000)
    visibility: Optional[str] = Field(default=None, pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")
    category: Optional[str] = Field(default=None, pattern="^(HISTORY|TRADITION|GLOSSARY|GUIDE|RULE|OTHER)$")
    published: Optional[bool] = None


class VisibilityPatchIn(BaseModel):
    page: Optional[str] = Field(default=None, pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")
    description: Optional[str] = Field(default=None, pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")
    contact: Optional[str] = Field(default=None, pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")
    events: Optional[str] = Field(default=None, pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")
    members: Optional[str] = Field(default=None, pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")
    albums: Optional[str] = Field(default=None, pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")
    documents: Optional[str] = Field(default=None, pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")
    folklore: Optional[str] = Field(default=None, pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")
    stats: Optional[str] = Field(default=None, pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")
    confirm_public_finance: bool = False


class EventCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    starts_at: datetime
    ends_at: datetime
    venue: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=10000)
    visibility: str = Field(default="PRIVATE", pattern="^(PUBLIC|PRIVATE)$")
    publication_status: str = Field(default="DRAFT", pattern="^(DRAFT|PUBLISHED)$")
    entry_price_cents: int = Field(default=0, ge=0, le=100000)


class EventPatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=10000)
    venue: Optional[str] = Field(default=None, max_length=255)
    visibility: Optional[str] = Field(default=None, pattern="^(PUBLIC|PRIVATE)$")
    publication_status: Optional[str] = Field(default=None, pattern="^(DRAFT|PUBLISHED)$")


class PortalContentIn(BaseModel):
    about: str = Field(default="", max_length=10000)
    opening_hours: str = Field(default="", max_length=2000)
    services: list[str] = Field(default_factory=list, max_length=24)
    announcement: str = Field(default="", max_length=2000)
    hidden_blocks: list[Literal["about", "events", "services", "team", "gallery", "memory", "partners"]] = Field(default_factory=list, max_length=7)


class SettingsPatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=140)
    description: Optional[str] = Field(default=None, max_length=10000)
    city: Optional[str] = Field(default=None, max_length=120)
    org_type: Optional[str] = Field(default=None, max_length=64)
    website_url: Optional[str] = Field(default=None, max_length=512)
    instagram_handle: Optional[str] = Field(default=None, max_length=64)
    logo_url: Optional[str] = Field(default=None, max_length=512)
    banner_url: Optional[str] = Field(default=None, max_length=1000)
    primary_color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    address: Optional[str] = Field(default=None, max_length=255)
    contact_email: Optional[str] = Field(default=None, max_length=255)
    contact_phone: Optional[str] = Field(default=None, max_length=64)
    history: Optional[str] = Field(default=None, max_length=10000)
    sponsors: Optional[list[str]] = Field(default=None, max_length=30)
    portal: Optional[PortalContentIn] = None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:170] or "page"


def _visibility_settings(org: Organization) -> dict[str, str]:
    raw = org.visibility_settings_json if isinstance(org.visibility_settings_json, dict) else {}
    return {**DEFAULT_VISIBILITY, **{str(k): str(v).upper() for k, v in raw.items() if str(k) in DEFAULT_VISIBILITY}}


def _normalized_type(org: Organization) -> str:
    value = (org.org_type or "OTHER").strip().upper()
    aliases = {"COMITE": "COMMITTEE", "COMITÉ": "COMMITTEE", "CERCLE": "CIRCLE", "ORDRE": "ORDER", "BAR": "BAR"}
    return aliases.get(value, value if value in STRUCTURE_TYPES else "OTHER")


def _active_membership(db: Session, org_id: int, user_id: str) -> Optional[OrganizationMembership]:
    now = now_utc()
    return db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.status == "ACTIVE",
        OrganizationMembership.revoked_at.is_(None),
        or_(OrganizationMembership.starts_at.is_(None), OrganizationMembership.starts_at <= now),
        or_(OrganizationMembership.ends_at.is_(None), OrganizationMembership.ends_at > now),
    ).first()


def _require_role(db: Session, org_id: int, user: AppUser, minimum: str) -> OrganizationMembership:
    membership = _active_membership(db, org_id, user.id)
    if membership is None or ROLE_RANK.get((membership.role or "MEMBER").upper(), 0) < ROLE_RANK[minimum]:
        raise HTTPException(status_code=403, detail={"reason": "FORUM_PERMISSION_DENIED", "permission": minimum})
    return membership


def _can_view(level: str, membership: Optional[OrganizationMembership], *, is_user: bool = True) -> bool:
    normalized = (level or "STRUCTURE_MEMBERS").upper()
    if normalized == "PUBLIC":
        return True
    if not is_user or membership is None:
        return False
    role = (membership.role or "MEMBER").upper()
    rank = ROLE_RANK.get(role, 0)
    return {
        "TORE_USERS": True,
        "STRUCTURE_MEMBERS": rank >= ROLE_RANK["MEMBER"],
        "STAFF": rank >= ROLE_RANK["STAFF"],
        "OFFICE": rank >= ROLE_RANK["BUREAU"],
        "TREASURY": rank >= ROLE_RANK["TREASURER"],
        "ADMINS": rank >= ROLE_RANK["ADMIN"],
    }.get(normalized, False)


def _structure_or_404(db: Session, slug: str, *, public: bool = False) -> Organization:
    org = db.query(Organization).filter(func.lower(Organization.slug) == slug.strip().lower()).first()
    if org is None or (public and ((org.visibility or "PRIVATE").upper() != "PUBLIC" or _visibility_settings(org)["page"] != "PUBLIC")):
        raise HTTPException(status_code=404, detail="Structure not found")
    return org


def _event_payload(event: Event) -> dict[str, Any]:
    return {
        "id": event.id,
        "name": event.name,
        "startsAt": event.starts_at.isoformat() if event.starts_at else None,
        "endsAt": event.ends_at.isoformat() if event.ends_at else None,
        "venue": event.venue,
        "city": event.city,
        "description": event.public_description,
        "visibility": (event.visibility or "PRIVATE").upper(),
        "publicationStatus": (event.publication_status or "DRAFT").upper(),
        "entryPriceCents": event.entry_price_cents,
        "bannerUrl": event.banner_url,
    }


def _org_events(db: Session, org_id: int, *, public: bool = False) -> list[Event]:
    query = db.query(Event).filter(Event.host_type == "orga", Event.host_id == str(org_id))
    if public:
        query = query.filter(func.upper(Event.visibility) == "PUBLIC", func.upper(Event.publication_status) == "PUBLISHED")
    return query.order_by(Event.starts_at.asc(), Event.id.asc()).all()


def _structure_payload(org: Organization, *, include_private: bool = False) -> dict[str, Any]:
    content = org.public_content_json if isinstance(org.public_content_json, dict) else {}
    settings = _visibility_settings(org)
    description_visible = include_private or settings["description"] == "PUBLIC"
    contact_visible = include_private or settings["contact"] == "PUBLIC"
    payload = {
        "id": org.id,
        "slug": org.slug,
        "name": org.name,
        "type": _normalized_type(org),
        "description": org.description if description_visible else None,
        "city": org.city,
        "address": org.address if contact_visible else None,
        "websiteUrl": org.website_url if contact_visible else None,
        "instagramHandle": org.instagram_handle if contact_visible else None,
        "logoUrl": org.logo_url,
        "bannerUrl": org.banner_url,
        "primaryColor": org.primary_color,
        "secondaryColor": org.secondary_color,
        "socialLinks": org.social_links_json if contact_visible and isinstance(org.social_links_json, dict) else {},
        "visibility": (org.visibility or "PRIVATE").upper(),
    }
    portal = content.get("portal") if isinstance(content.get("portal"), dict) else {}
    payload["portal"] = {
        "about": portal.get("about", "") if description_visible else "",
        "services": portal.get("services", []) if description_visible else [],
        "announcement": portal.get("announcement", "") if description_visible else "",
        "opening_hours": portal.get("opening_hours", "") if contact_visible else "",
        "hidden_blocks": portal.get("hidden_blocks", []),
    }
    if include_private or settings["folklore"] == "PUBLIC":
        payload["history"] = content.get("history")
    if description_visible:
        payload["sponsors"] = content.get("sponsors", [])
    if contact_visible:
        payload["contactEmail"] = org.contact_email
        payload["contactPhone"] = org.contact_phone
    return payload


def _member_payload(db: Session, membership: OrganizationMembership, *, include_private: bool = False) -> dict[str, Any]:
    user = db.get(AppUser, membership.user_id)
    return {
        "id": membership.id,
        "userId": membership.user_id,
        "displayName": (user.display_name if user else None) or "Membre TORÈ",
        "avatarUrl": user.avatar_url if user else None,
        "role": (membership.role or "MEMBER").upper(),
        "status": (membership.status or "ACTIVE").upper(),
        "mandateLabel": membership.mandate_label,
        "startsAt": membership.starts_at.isoformat() if membership.starts_at else None,
        "endsAt": membership.ends_at.isoformat() if membership.ends_at else None,
        "joinedAt": membership.joined_at.isoformat() if membership.joined_at else None,
        "visibility": (membership.visibility or "PRIVATE").upper(),
        **({"email": user.email if user else None} if include_private else {}),
    }


def _write_idem(db: Session, user: AppUser, action: str, header: Optional[str]) -> tuple[str, Optional[dict[str, Any]]]:
    key = ensure_idempotency_key(header)
    row = db.query(OrganizationWriteIdempotency).filter(
        OrganizationWriteIdempotency.actor_user_id == user.id,
        OrganizationWriteIdempotency.action == action,
        OrganizationWriteIdempotency.idempotency_key == key,
    ).first()
    return key, row.response_json if row else None


def _save_idem(db: Session, user: AppUser, action: str, key: str, response: dict[str, Any]) -> None:
    db.add(OrganizationWriteIdempotency(actor_user_id=user.id, action=action, idempotency_key=key, response_json=response))


def _verify_event_scope(db: Session, org_id: int, event_id: Optional[int]) -> Optional[Event]:
    if event_id is None:
        return None
    event = db.get(Event, event_id)
    if event is None or event.host_type != "orga" or event.host_id != str(org_id):
        raise HTTPException(status_code=400, detail={"reason": "EVENT_OUTSIDE_STRUCTURE"})
    return event


def _base_public_page(db: Session, org: Organization) -> dict[str, Any]:
    settings = _visibility_settings(org)
    public_events = [] if settings["events"] != "PUBLIC" else [item for item in _org_events(db, org.id, public=True) if item.starts_at is None or item.starts_at >= now_utc()]
    members: list[dict[str, Any]] = []
    if settings["members"] == "PUBLIC":
        memberships = db.query(OrganizationMembership).filter(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.status == "ACTIVE",
            OrganizationMembership.revoked_at.is_(None),
            func.upper(OrganizationMembership.visibility) == "PUBLIC",
            or_(OrganizationMembership.starts_at.is_(None), OrganizationMembership.starts_at <= now_utc()),
            or_(OrganizationMembership.ends_at.is_(None), OrganizationMembership.ends_at > now_utc()),
        ).order_by(OrganizationMembership.joined_at.asc()).all()
        members = [_member_payload(db, item) for item in memberships]
    albums: list[dict[str, Any]] = []
    if settings["albums"] == "PUBLIC":
        album_rows = db.query(StructureAlbum).filter(
            StructureAlbum.organization_id == org.id,
            func.upper(StructureAlbum.status) == "PUBLISHED",
            func.upper(StructureAlbum.visibility) == "PUBLIC",
            StructureAlbum.archived_at.is_(None),
        ).order_by(StructureAlbum.created_at.desc()).all()
        albums = [_album_payload(db, item, include_media=True) for item in album_rows]
    pages: list[dict[str, Any]] = []
    if settings["folklore"] == "PUBLIC":
        page_rows = db.query(StructurePage).filter(
            StructurePage.organization_id == org.id,
            StructurePage.published_at.is_not(None),
            func.upper(StructurePage.visibility) == "PUBLIC",
        ).order_by(StructurePage.updated_at.desc()).all()
        pages = [_page_payload(item, include_content=True) for item in page_rows]
    member_count = db.scalar(select(func.count()).select_from(OrganizationMembership).where(
        OrganizationMembership.organization_id == org.id,
        OrganizationMembership.status == "ACTIVE",
        OrganizationMembership.revoked_at.is_(None),
    )) or 0
    public_stats = {"members": int(member_count), "publicEvents": len(public_events), "publicAlbums": len(albums)} if settings["stats"] == "PUBLIC" else None
    documents = []
    if settings["documents"] == "PUBLIC":
        documents = [_document_payload(row) for row in db.query(StructureDocument).filter(
            StructureDocument.organization_id == org.id,
            StructureDocument.archived_at.is_(None),
            func.upper(StructureDocument.visibility) == "PUBLIC",
        ).order_by(StructureDocument.created_at.desc()).limit(100).all()]
    return {
        "structure": _structure_payload(org),
        "visibility": settings,
        "events": [_event_payload(item) for item in public_events],
        "members": members,
        "albums": albums,
        "pages": pages,
        "documents": documents,
        "stats": public_stats,
    }


def _discussion_payload(db: Session, post: StructureDiscussionPost, membership=None) -> dict[str, Any]:
    author = db.get(AppUser, post.created_by_user_id)
    channel = db.get(StructureDiscussionChannel, post.channel_id)
    return {
        "id": post.id,
        "channelId": post.channel_id,
        "channelName": channel.name if channel else "Discussion",
        "title": post.title,
        "body": post.body,
        "parentId": post.parent_id,
        "authorAvatar": getattr(author, "avatar_url", None),
        "documents": [_document_payload(doc) for doc in db.query(StructureDocument).filter(StructureDocument.id.in_(post.document_ids or []), StructureDocument.organization_id == post.organization_id, StructureDocument.archived_at.is_(None)).all() if membership and _can_view(doc.visibility, membership)],
        "reactions": [{"emoji": emoji, "count": len(rows), "mine": bool(membership and any(r.user_id == membership.user_id for r in rows))} for emoji in ["👍", "❤️", "✅"] if (rows := db.query(StructureDiscussionReaction).filter_by(post_id=post.id, emoji=emoji).all())],
        "authorId": post.created_by_user_id,
        "authorName": author.display_name if author else "Membre TORÈ",
        "pinned": bool(post.is_pinned),
        "archived": bool(post.is_archived),
        "createdAt": post.created_at.isoformat() if post.created_at else None,
    }


def _visible_channel_ids(db, org_id, membership):
    return [c.id for c in db.query(StructureDiscussionChannel).filter_by(organization_id=org_id, is_archived=False).all() if _can_view(c.visibility, membership)]


def _accessible_post(db, org_id, post_id, membership):
    post = db.get(StructureDiscussionPost, post_id)
    if not post or post.organization_id != org_id or post.is_archived or post.channel_id not in _visible_channel_ids(db, org_id, membership):
        raise HTTPException(404, detail="Discussion inaccessible")
    return post


def _document_payload(row: StructureDocument) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "fileUrl": row.file_url,
        "folder": row.folder,
        "tags": row.tags_json if isinstance(row.tags_json, list) else [],
        "visibility": (row.visibility or "STRUCTURE_MEMBERS").upper(),
        "uploadedBy": row.uploaded_by_user_id,
        "eventId": row.event_id,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
        "archivedAt": row.archived_at.isoformat() if row.archived_at else None,
    }


def _album_payload(db: Session, row: StructureAlbum, *, include_media: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "coverUrl": row.cover_url,
        "visibility": (row.visibility or "STRUCTURE_MEMBERS").upper(),
        "status": (row.status or "DRAFT").upper(),
        "createdBy": row.created_by_user_id,
        "eventId": row.event_id,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }
    if include_media:
        payload["media"] = [
            {"id": media.id, "url": media.media_url, "type": media.media_type, "caption": media.caption, "sortOrder": media.sort_order}
            for media in db.query(StructureMedia).filter(StructureMedia.album_id == row.id).order_by(StructureMedia.sort_order.asc(), StructureMedia.id.asc()).all()
        ]
    return payload


def _page_payload(row: StructurePage, *, include_content: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": row.id,
        "title": row.title,
        "slug": row.slug,
        "visibility": (row.visibility or "STRUCTURE_MEMBERS").upper(),
        "category": (row.category or "OTHER").upper(),
        "version": row.version,
        "publishedAt": row.published_at.isoformat() if row.published_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }
    if include_content:
        payload["content"] = row.content
    return payload


def _latest_stats(db: Session, org_id: int, *, allow_finance: bool) -> dict[str, Any]:
    latest = db.query(Event).filter(Event.host_type == "orga", Event.host_id == str(org_id)).order_by(Event.ends_at.desc(), Event.id.desc()).first()
    if latest is None:
        return {"event": None, "canReadFinance": allow_finance, "entries": 0, "scans": 0, "revenueCents": None, "costsCents": None, "resultCents": None}
    entries = int(db.scalar(select(func.count()).select_from(Entry).where(Entry.event_id == latest.id, Entry.used.is_(True))) or 0)
    scans = int(db.scalar(select(func.count()).select_from(EntryScanLog).where(EntryScanLog.event_id == latest.id)) or 0)
    if not allow_finance:
        return {"event": _event_payload(latest), "canReadFinance": False, "entries": entries, "scans": scans, "revenueCents": None, "costsCents": None, "resultCents": None}
    revenue = int(db.scalar(select(func.coalesce(func.sum(Order.total_cents), 0)).where(Order.event_id == latest.id)) or 0)
    costs = int(db.scalar(select(func.coalesce(func.sum(EventCost.amount_cents), 0)).where(EventCost.event_id == latest.id)) or 0)
    return {"event": _event_payload(latest), "canReadFinance": True, "entries": entries, "scans": scans, "revenueCents": revenue, "costsCents": costs, "resultCents": revenue - costs}


@router.get("/me/structures")
def list_my_forum_structures(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Navigation metadata for the caller's currently accessible workspaces."""
    stamp = now_utc()
    rows = db.query(Organization, OrganizationMembership).join(
        OrganizationMembership, OrganizationMembership.organization_id == Organization.id,
    ).filter(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.status == "ACTIVE",
        OrganizationMembership.revoked_at.is_(None),
        or_(OrganizationMembership.starts_at.is_(None), OrganizationMembership.starts_at <= stamp),
        or_(OrganizationMembership.ends_at.is_(None), OrganizationMembership.ends_at > stamp),
    ).order_by(Organization.name.asc()).all()
    items = []
    for org, membership in rows:
        role = (membership.role or "MEMBER").upper()
        rank = ROLE_RANK.get(role, 0)
        if rank < ROLE_RANK["MEMBER"]:
            continue
        items.append({
            "id": org.id, "slug": org.slug, "name": org.name,
            "type": _normalized_type(org), "city": org.city, "logoUrl": org.logo_url,
            "role": role, "canManage": rank >= ROLE_RANK["MANAGER"],
            "canReadFinance": rank >= ROLE_RANK["TREASURER"],
        })
    return {"items": items}


@router.get("/structures")
def list_structures(
    q: Optional[str] = Query(default=None, max_length=120),
    type: Optional[str] = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
):
    query = db.query(Organization).filter(func.upper(Organization.visibility) == "PUBLIC")
    if q and q.strip():
        needle = f"%{q.strip().lower()}%"
        query = query.filter(or_(func.lower(Organization.name).like(needle), func.lower(func.coalesce(Organization.city, "")).like(needle)))
    if type and type.strip().upper() in STRUCTURE_TYPES:
        query = query.filter(func.upper(Organization.org_type) == type.strip().upper())
    rows = query.order_by(Organization.name.asc()).all()
    items = []
    for org in rows:
        members = int(db.scalar(select(func.count()).select_from(OrganizationMembership).where(OrganizationMembership.organization_id == org.id, OrganizationMembership.status == "ACTIVE", OrganizationMembership.revoked_at.is_(None))) or 0)
        items.append({**_structure_payload(org), "memberCount": members if _visibility_settings(org)["stats"] == "PUBLIC" else None})
    return {"items": items}


@router.get("/structures/{slug}")
def get_public_structure(slug: str, db: Session = Depends(get_db)):
    return _base_public_page(db, _structure_or_404(db, slug, public=True))


@router.get("/structures/{slug}/dashboard")
def get_structure_dashboard(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    membership = _require_role(db, org.id, user, "MEMBER")
    settings = _visibility_settings(org)
    recent_posts = db.query(StructureDiscussionPost).filter(StructureDiscussionPost.organization_id == org.id, StructureDiscussionPost.channel_id.in_(_visible_channel_ids(db, org.id, membership)), StructureDiscussionPost.parent_id.is_(None), StructureDiscussionPost.is_archived.is_(False)).order_by(StructureDiscussionPost.created_at.desc()).limit(5).all()
    recent_documents = db.query(StructureDocument).filter(StructureDocument.organization_id == org.id, StructureDocument.archived_at.is_(None)).order_by(StructureDocument.created_at.desc()).limit(5).all()
    active_members = int(db.scalar(select(func.count()).select_from(OrganizationMembership).where(OrganizationMembership.organization_id == org.id, OrganizationMembership.status == "ACTIVE", OrganizationMembership.revoked_at.is_(None))) or 0)
    allow_finance = ROLE_RANK.get((membership.role or "MEMBER").upper(), 0) >= ROLE_RANK["TREASURER"]
    return {
        "structure": _structure_payload(org, include_private=True),
        "membership": _member_payload(db, membership, include_private=True),
        "permissions": ["structure.read", "member.read", "discussion.read", "discussion.write", "event.read", "document.read", "album.read", "stats.read"] + (["accounting.read"] if allow_finance else []) + (["structure.edit", "member.manage", "event.create", "event.manage", "document.manage", "album.manage", "discussion.manage", "page.manage", "visibility.manage", "audit.read"] if ROLE_RANK.get((membership.role or "MEMBER").upper(), 0) >= ROLE_RANK["MANAGER"] else []),
        "stats": {"memberCount": active_members, "eventCount": len(_org_events(db, org.id)), "discussionCount": int(db.scalar(select(func.count()).select_from(StructureDiscussionPost).where(StructureDiscussionPost.organization_id == org.id, StructureDiscussionPost.is_archived.is_(False))) or 0), "documentCount": int(db.scalar(select(func.count()).select_from(StructureDocument).where(StructureDocument.organization_id == org.id, StructureDocument.archived_at.is_(None))) or 0), "albumCount": int(db.scalar(select(func.count()).select_from(StructureAlbum).where(StructureAlbum.organization_id == org.id, StructureAlbum.archived_at.is_(None))) or 0)},
        "upcomingEvents": [_event_payload(item) for item in _org_events(db, org.id) if item.starts_at and item.starts_at >= now_utc()][:5],
        "recentPosts": [_discussion_payload(db, item, membership) for item in recent_posts],
        "recentDocuments": [_document_payload(item) for item in recent_documents if _can_view(item.visibility, membership)],
        "latestEventStats": _latest_stats(db, org.id, allow_finance=allow_finance),
        "visibility": settings,
    }


@router.get("/structures/{slug}/members")
def list_structure_members(slug: str, include_archived: bool = False, search: Optional[str] = Query(default=None, max_length=120), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    membership = _require_role(db, org.id, user, "MEMBER")
    include_private = ROLE_RANK.get((membership.role or "MEMBER").upper(), 0) >= ROLE_RANK["MANAGER"]
    query = db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org.id)
    if not include_archived or not include_private:
        query = query.filter(OrganizationMembership.status == "ACTIVE", OrganizationMembership.revoked_at.is_(None))
    rows = query.order_by(OrganizationMembership.status.asc(), OrganizationMembership.joined_at.asc()).all()
    if search and search.strip():
        needle = search.strip().lower()
        matching_rows = []
        for row in rows:
            target = db.get(AppUser, row.user_id)
            display_name = (target.display_name if target and target.display_name else "").lower()
            if needle in (row.user_id or "").lower() or needle in display_name:
                matching_rows.append(row)
        rows = matching_rows
    return {"items": [_member_payload(db, item, include_private=include_private) for item in rows], "canManage": include_private}


@router.post("/structures/{slug}/members")
def upsert_structure_member(slug: str, payload: MemberUpsertIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    if payload.role.strip().upper() == "OWNER" and (actor.role or "").upper() != "OWNER":
        raise HTTPException(status_code=403, detail={"reason": "OWNER_ROLE_REQUIRES_OWNER"})
    member_action = f"forum_member_upsert:{org.id}"
    key, previous = _write_idem(db, user, member_action, idempotency_key)
    if previous is not None:
        return previous
    target = db.get(AppUser, payload.user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"reason": "USER_NOT_FOUND"})
    now = now_utc()
    row = db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org.id, OrganizationMembership.user_id == payload.user_id).first()
    if row is None:
        row = OrganizationMembership(organization_id=org.id, user_id=payload.user_id, created_by_user_id=user.id, created_at=now, joined_at=now)
        db.add(row)
    row.role = payload.role.strip().upper()
    row.status = payload.status
    row.mandate_label = payload.mandate_label
    row.visibility = payload.visibility
    row.starts_at = payload.starts_at or (now if payload.status == "ACTIVE" else None)
    row.ends_at = payload.ends_at
    row.revoked_at = None
    row.revoked_by_user_id = None
    row.validated_by_user_id = user.id if payload.status == "ACTIVE" else None
    row.validated_at = now if payload.status == "ACTIVE" else None
    row.validation_source = "FORUM_ADMIN"
    row.updated_at = now
    db.flush()
    response = _member_payload(db, row, include_private=True)
    _save_idem(db, user, member_action, key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.member.upsert", entity_type="organization_membership", entity_id=str(row.id), event_id=None, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "user_id": payload.user_id, "role": row.role, "status": row.status, "visibility": row.visibility})
    db.commit()
    return response


@router.patch("/structures/{slug}/members/{member_user_id}")
def patch_structure_member(slug: str, member_user_id: str, payload: MemberPatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    member_action = f"forum_member_patch:{org.id}"
    key, previous = _write_idem(db, user, member_action, idempotency_key)
    if previous is not None:
        return previous
    row = db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org.id, OrganizationMembership.user_id == member_user_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if (row.role or "").upper() == "OWNER" and (actor.role or "").upper() != "OWNER":
        raise HTTPException(status_code=403, detail={"reason": "OWNER_MEMBERSHIP_PROTECTED"})
    if (row.role or "").upper() == "OWNER" and payload.status in {"REVOKED", "LEFT"}:
        raise HTTPException(status_code=400, detail={"reason": "OWNER_MEMBERSHIP_PROTECTED"})
    if payload.role is not None and payload.role.strip().upper() == "OWNER" and (actor.role or "").upper() != "OWNER":
        raise HTTPException(status_code=403, detail={"reason": "OWNER_ROLE_REQUIRES_OWNER"})
    if payload.role is not None:
        row.role = payload.role.strip().upper()
    if payload.status is not None:
        row.status = payload.status
        if payload.status == "ACTIVE":
            row.revoked_at = None
            row.revoked_by_user_id = None
            row.validated_by_user_id = user.id
            row.validated_at = now_utc()
        elif payload.status in {"REVOKED", "LEFT"}:
            row.revoked_at = now_utc()
            row.revoked_by_user_id = user.id
            row.revoke_reason = payload.reason
    if payload.mandate_label is not None:
        row.mandate_label = payload.mandate_label
    if payload.visibility is not None:
        row.visibility = payload.visibility
    if payload.starts_at is not None:
        row.starts_at = payload.starts_at
    if payload.ends_at is not None:
        row.ends_at = payload.ends_at
    row.updated_at = now_utc()
    db.flush()
    response = _member_payload(db, row, include_private=True)
    _save_idem(db, user, member_action, key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.member.patch", entity_type="organization_membership", entity_id=str(row.id), event_id=None, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "user_id": member_user_id, "role": row.role, "status": row.status, "visibility": row.visibility, "reason": payload.reason})
    db.commit()
    return response


@router.delete("/structures/{slug}/members/{member_user_id}")
def revoke_structure_member(slug: str, member_user_id: str, reason: str = Query(default="Révocation depuis le Forum", min_length=2, max_length=280), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    member_action = f"forum_member_revoke:{org.id}"
    key, previous = _write_idem(db, user, member_action, idempotency_key)
    if previous is not None:
        return previous
    row = db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org.id, OrganizationMembership.user_id == member_user_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if (row.role or "").upper() == "OWNER":
        raise HTTPException(status_code=400, detail={"reason": "OWNER_MEMBERSHIP_PROTECTED"})
    row.status = "REVOKED"
    row.revoked_at = now_utc()
    row.revoked_by_user_id = user.id
    row.revoke_reason = reason
    row.updated_at = now_utc()
    response = {"ok": True, "memberUserId": member_user_id, "status": row.status}
    _save_idem(db, user, member_action, key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.member.revoke", entity_type="organization_membership", entity_id=str(row.id), event_id=None, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "user_id": member_user_id, "reason": reason})
    db.commit()
    return response


@router.get("/structures/{slug}/discussions")
def list_discussions(slug: str, search: Optional[str] = Query(default=None, max_length=120), channel_id: Optional[int] = None, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    membership = _require_role(db, org.id, user, "MEMBER")
    categories = db.query(StructureDiscussionCategory).filter(StructureDiscussionCategory.organization_id == org.id, StructureDiscussionCategory.is_archived.is_(False)).order_by(StructureDiscussionCategory.order_index.asc()).all()
    channels = db.query(StructureDiscussionChannel).filter(StructureDiscussionChannel.organization_id == org.id, StructureDiscussionChannel.is_archived.is_(False)).order_by(StructureDiscussionChannel.name.asc()).all()
    channels = [c for c in channels if _can_view(c.visibility, membership)]
    query = db.query(StructureDiscussionPost).filter(StructureDiscussionPost.organization_id == org.id, StructureDiscussionPost.channel_id.in_([c.id for c in channels]), StructureDiscussionPost.is_archived.is_(False))
    if channel_id is not None:
        query = query.filter(StructureDiscussionPost.channel_id == channel_id)
    if search and search.strip():
        needle = f"%{search.strip().lower()}%"
        query = query.filter(or_(func.lower(StructureDiscussionPost.title).like(needle), func.lower(StructureDiscussionPost.body).like(needle)))
    posts = query.order_by(StructureDiscussionPost.created_at.desc(), StructureDiscussionPost.id.desc()).limit(300).all()
    return {"categories": [{"id": c.id, "name": c.name, "slug": c.slug} for c in categories if any(ch.category_id == c.id for ch in channels)], "channels": [{"id": c.id, "categoryId": c.category_id, "name": c.name, "slug": c.slug, "visibility": c.visibility} for c in channels], "posts": [_discussion_payload(db, item, membership) for item in posts], "limited": len(posts) == 300}


@router.post("/structures/{slug}/channels")
def create_channel(slug: str, payload: ChannelCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    key, previous = _write_idem(db, user, f"forum_channel_create:{org.id}", idempotency_key)
    if previous is not None:
        return previous
    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(422, detail="Nom de salon trop court")
    channel_slug = re.sub(r"[^\w]+", "-", name.lower()).strip("-")
    if not channel_slug:
        raise HTTPException(422, detail="Nom de salon invalide")
    if db.query(StructureDiscussionChannel).filter_by(organization_id=org.id, slug=channel_slug).first():
        raise HTTPException(409, detail="Ce salon existe déjà")
    category = db.query(StructureDiscussionCategory).filter_by(organization_id=org.id, slug="interne").first()
    if not category:
        category = StructureDiscussionCategory(organization_id=org.id, name="Salons internes", slug="interne", order_index=1)
        db.add(category)
        db.flush()
    row = StructureDiscussionChannel(organization_id=org.id, category_id=category.id, name=name, slug=channel_slug, visibility=payload.visibility)
    db.add(row)
    db.flush()
    response = {"id": row.id, "name": row.name}
    _save_idem(db, user, f"forum_channel_create:{org.id}", key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.channel.create", entity_type="structure_discussion_channel", entity_id=str(row.id), event_id=None, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "visibility": row.visibility})
    db.commit()
    return response


@router.patch("/structures/{slug}/discussions/{post_id}")
def update_discussion(slug: str, post_id: int, payload: DiscussionActionIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MEMBER")
    row = _accessible_post(db, org.id, post_id, actor)
    key, previous = _write_idem(db, user, f"forum_discussion_action:{post_id}", idempotency_key)
    if previous is not None:
        return previous
    if payload.pinned is not None:
        _require_role(db, org.id, user, "MANAGER")
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


@router.post("/structures/{slug}/discussions")
def create_discussion(slug: str, payload: DiscussionCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MEMBER")
    key, previous = _write_idem(db, user, f"forum_discussion_create:{org.id}", idempotency_key)
    if previous is not None:
        return previous
    channel = db.get(StructureDiscussionChannel, payload.channel_id) if payload.channel_id else None
    if payload.channel_id is not None and (not channel or channel.is_archived or not _can_view(channel.visibility, actor)):
        raise HTTPException(404, detail="Salon inaccessible")
    if channel is not None and channel.organization_id != org.id:
        raise HTTPException(status_code=400, detail={"reason": "CHANNEL_OUTSIDE_STRUCTURE"})
    if channel is None:
        channel = db.query(StructureDiscussionChannel).filter_by(organization_id=org.id, slug="general", is_archived=False).first()
    if channel is None:
        category = db.query(StructureDiscussionCategory).filter(StructureDiscussionCategory.organization_id == org.id, StructureDiscussionCategory.slug == "general").first()
        if category is None:
            category = StructureDiscussionCategory(organization_id=org.id, name="Général", slug="general", order_index=0, created_at=now_utc())
            db.add(category)
            db.flush()
        channel = StructureDiscussionChannel(organization_id=org.id, category_id=category.id, name="Général", slug="general", visibility="STRUCTURE_MEMBERS", created_at=now_utc())
        db.add(channel)
        db.flush()
    if not _can_view(channel.visibility, actor):
        raise HTTPException(403, detail="Salon inaccessible")
    if not payload.body.strip() or len(payload.title.strip()) < 2:
        raise HTTPException(422, detail="Le titre et le message sont obligatoires")
    if payload.parent_id is not None:
        parent = _accessible_post(db, org.id, payload.parent_id, actor)
        if parent.channel_id != channel.id or parent.parent_id is not None:
            raise HTTPException(400, detail="Fil de réponse invalide")
    for doc_id in payload.document_ids:
        doc = db.get(StructureDocument, doc_id)
        if not doc or doc.organization_id != org.id or doc.archived_at or not _can_view(doc.visibility, actor):
            raise HTTPException(404, detail="Document inaccessible")
    row = StructureDiscussionPost(organization_id=org.id, channel_id=channel.id, parent_id=payload.parent_id, document_ids=list(set(payload.document_ids)), title=payload.title.strip(), body=payload.body.strip(), created_by_user_id=user.id, created_at=now_utc(), updated_at=now_utc())
    db.add(row)
    db.flush()
    response = _discussion_payload(db, row, actor)
    _save_idem(db, user, f"forum_discussion_create:{org.id}", key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.discussion.create", entity_type="structure_discussion_post", entity_id=str(row.id), event_id=None, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "channel_id": channel.id})
    db.commit()
    return response


@router.get("/structures/{slug}/events")
def list_structure_events(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    _require_role(db, org.id, user, "MEMBER")
    return {"items": [_event_payload(item) for item in _org_events(db, org.id)]}


@router.post("/structures/{slug}/events")
def create_structure_event(slug: str, payload: EventCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    key, previous = _write_idem(db, user, f"forum_event_create:{org.id}", idempotency_key)
    if previous is not None:
        return previous
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=400, detail={"reason": "INVALID_EVENT_DATES"})
    event = Event(host_type="orga", host_id=str(org.id), host_display_name=org.name, name=payload.name.strip(), starts_at=payload.starts_at.replace(tzinfo=None), ends_at=payload.ends_at.replace(tzinfo=None), venue=payload.venue, city=payload.city or org.city, public_description=payload.description, visibility=payload.visibility, publication_status=payload.publication_status, entry_price_cents=payload.entry_price_cents, created_by=f"app:{user.id}", last_state_updated_at=now_utc(), last_updated_at=now_utc())
    db.add(event)
    db.flush()
    db.add(EventRuntimeState(event_id=event.id, state="LIVE", updated_at=now_utc()))
    response = _event_payload(event)
    _save_idem(db, user, f"forum_event_create:{org.id}", key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.event.create", entity_type="event", entity_id=str(event.id), event_id=event.id, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "publication_status": event.publication_status})
    db.commit()
    return response


@router.patch("/structures/{slug}/events/{event_id}")
def patch_structure_event(slug: str, event_id: int, payload: EventPatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    key, previous = _write_idem(db, user, f"forum_event_patch:{event_id}", idempotency_key)
    if previous is not None:
        return previous
    event = _verify_event_scope(db, org.id, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if payload.name is not None:
        event.name = payload.name.strip()
    if payload.description is not None:
        event.public_description = payload.description
    if payload.venue is not None:
        event.venue = payload.venue
    if payload.visibility is not None:
        event.visibility = payload.visibility
    if payload.publication_status is not None:
        event.publication_status = payload.publication_status
    event.last_updated_at = now_utc()
    response = _event_payload(event)
    _save_idem(db, user, f"forum_event_patch:{event_id}", key, response)
    action = "forum.event.published" if payload.publication_status == "PUBLISHED" else "forum.event.patch"
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action=action, entity_type="event", entity_id=str(event.id), event_id=event.id, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "publication_status": event.publication_status, "visibility": event.visibility})
    db.commit()
    return response


@router.get("/structures/{slug}/documents")
def list_documents(slug: str, search: Optional[str] = Query(default=None, max_length=120), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    membership = _require_role(db, org.id, user, "MEMBER")
    query = db.query(StructureDocument).filter(StructureDocument.organization_id == org.id, StructureDocument.archived_at.is_(None))
    if search and search.strip():
        needle = f"%{search.strip().lower()}%"
        query = query.filter(or_(func.lower(StructureDocument.title).like(needle), func.lower(func.coalesce(StructureDocument.folder, "")).like(needle)))
    rows = query.order_by(StructureDocument.created_at.desc()).all()
    return {"items": [_document_payload(row) for row in rows if _can_view(row.visibility, membership)]}


@router.post("/structures/{slug}/documents")
def create_document(slug: str, payload: DocumentCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    event = _verify_event_scope(db, org.id, payload.event_id)
    key, previous = _write_idem(db, user, f"forum_document_create:{org.id}", idempotency_key)
    if previous is not None:
        return previous
    row = StructureDocument(organization_id=org.id, title=payload.title.strip(), description=payload.description, file_url=payload.file_url.strip(), folder=payload.folder, tags_json=[tag.strip() for tag in payload.tags if tag.strip()], visibility=payload.visibility, uploaded_by_user_id=user.id, event_id=event.id if event else None, created_at=now_utc(), updated_at=now_utc())
    db.add(row)
    db.flush()
    response = _document_payload(row)
    _save_idem(db, user, f"forum_document_create:{org.id}", key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.document.create", entity_type="structure_document", entity_id=str(row.id), event_id=row.event_id, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "visibility": row.visibility})
    db.commit()
    return response


@router.delete("/structures/{slug}/documents/{document_id}")
def archive_document(slug: str, document_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    key, previous = _write_idem(db, user, f"forum_document_archive:{document_id}", idempotency_key)
    if previous is not None:
        return previous
    row = db.get(StructureDocument, document_id)
    if row is None or row.organization_id != org.id:
        raise HTTPException(status_code=404, detail="Document not found")
    row.archived_at = now_utc()
    row.updated_at = now_utc()
    response = {"ok": True, "id": document_id, "archivedAt": row.archived_at.isoformat()}
    _save_idem(db, user, f"forum_document_archive:{document_id}", key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.document.archive", entity_type="structure_document", entity_id=str(document_id), event_id=row.event_id, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id})
    db.commit()
    return response


@router.get("/structures/{slug}/albums")
def list_albums(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    membership = _require_role(db, org.id, user, "MEMBER")
    rows = db.query(StructureAlbum).filter(StructureAlbum.organization_id == org.id, StructureAlbum.archived_at.is_(None)).order_by(StructureAlbum.created_at.desc()).all()
    return {"items": [_album_payload(db, row, include_media=True) for row in rows if _can_view(row.visibility, membership) and ((row.status or "DRAFT").upper() != "DRAFT" or row.created_by_user_id == user.id or ROLE_RANK.get((membership.role or "MEMBER").upper(), 0) >= ROLE_RANK["MANAGER"])]}


@router.post("/structures/{slug}/albums")
def create_album(slug: str, payload: AlbumCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    event = _verify_event_scope(db, org.id, payload.event_id)
    key, previous = _write_idem(db, user, f"forum_album_create:{org.id}", idempotency_key)
    if previous is not None:
        return previous
    row = StructureAlbum(organization_id=org.id, event_id=event.id if event else None, title=payload.title.strip(), description=payload.description, cover_url=payload.cover_url, visibility=payload.visibility, status="DRAFT", created_by_user_id=user.id, created_at=now_utc(), updated_at=now_utc())
    db.add(row)
    db.flush()
    response = _album_payload(db, row, include_media=True)
    _save_idem(db, user, f"forum_album_create:{org.id}", key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.album.create", entity_type="structure_album", entity_id=str(row.id), event_id=row.event_id, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "status": "DRAFT"})
    db.commit()
    return response


@router.post("/structures/{slug}/albums/{album_id}/media")
def add_album_media(slug: str, album_id: int, payload: MediaCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    key, previous = _write_idem(db, user, f"forum_album_media_create:{album_id}", idempotency_key)
    if previous is not None:
        return previous
    album = db.get(StructureAlbum, album_id)
    if album is None or album.organization_id != org.id:
        raise HTTPException(status_code=404, detail="Album not found")
    count = int(db.scalar(select(func.count()).select_from(StructureMedia).where(StructureMedia.album_id == album.id)) or 0)
    row = StructureMedia(album_id=album.id, media_url=payload.media_url.strip(), media_type=payload.media_type, caption=payload.caption, sort_order=count, created_at=now_utc())
    db.add(row)
    album.updated_at = now_utc()
    db.flush()
    response = {"id": row.id, "url": row.media_url, "type": row.media_type, "caption": row.caption, "sortOrder": row.sort_order}
    _save_idem(db, user, f"forum_album_media_create:{album_id}", key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.album.media.create", entity_type="structure_media", entity_id=str(row.id), event_id=album.event_id, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "album_id": album.id})
    db.commit()
    return response


@router.patch("/structures/{slug}/albums/{album_id}")
def update_album_status(slug: str, album_id: int, payload: AlbumStatusIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    key, previous = _write_idem(db, user, f"forum_album_status:{album_id}:{payload.status}", idempotency_key)
    if previous is not None:
        return previous
    album = db.get(StructureAlbum, album_id)
    if album is None or album.organization_id != org.id:
        raise HTTPException(status_code=404, detail="Album not found")
    album.status = payload.status
    album.archived_at = now_utc() if payload.status == "ARCHIVED" else None
    album.updated_at = now_utc()
    response = _album_payload(db, album, include_media=True)
    _save_idem(db, user, f"forum_album_status:{album_id}:{payload.status}", key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.album.status", entity_type="structure_album", entity_id=str(album.id), event_id=album.event_id, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "status": album.status, "reason": payload.reason})
    db.commit()
    return response


@router.get("/structures/{slug}/pages")
def list_pages(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    membership = _require_role(db, org.id, user, "MEMBER")
    rows = db.query(StructurePage).filter(StructurePage.organization_id == org.id).order_by(StructurePage.updated_at.desc()).all()
    return {"items": [_page_payload(row, include_content=True) for row in rows if _can_view(row.visibility, membership) and (row.published_at is not None or ROLE_RANK.get((membership.role or "MEMBER").upper(), 0) >= ROLE_RANK["MANAGER"])]}


@router.post("/structures/{slug}/pages")
def create_page(slug: str, payload: PageCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    key, previous = _write_idem(db, user, f"forum_page_create:{org.id}", idempotency_key)
    if previous is not None:
        return previous
    slug_value = _slugify(payload.slug or payload.title)
    if db.query(StructurePage).filter(StructurePage.organization_id == org.id, StructurePage.slug == slug_value).first() is not None:
        raise HTTPException(status_code=409, detail={"reason": "PAGE_SLUG_EXISTS"})
    now = now_utc()
    row = StructurePage(organization_id=org.id, title=payload.title.strip(), slug=slug_value, content=payload.content, visibility=payload.visibility, category=payload.category, created_by_user_id=user.id, updated_by_user_id=user.id, version=1, published_at=now if payload.published else None, created_at=now, updated_at=now)
    db.add(row)
    db.flush()
    response = _page_payload(row, include_content=True)
    _save_idem(db, user, f"forum_page_create:{org.id}", key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.page.create", entity_type="structure_page", entity_id=str(row.id), event_id=None, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "category": row.category})
    db.commit()
    return response


@router.patch("/structures/{slug}/pages/{page_id}")
def patch_page(slug: str, page_id: int, payload: PagePatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    key, previous = _write_idem(db, user, f"forum_page_patch:{page_id}", idempotency_key)
    if previous is not None:
        return previous
    row = db.get(StructurePage, page_id)
    if row is None or row.organization_id != org.id:
        raise HTTPException(status_code=404, detail="Page not found")
    if payload.title is not None:
        row.title = payload.title.strip()
    if payload.content is not None:
        row.content = payload.content
    if payload.visibility is not None:
        row.visibility = payload.visibility
    if payload.category is not None:
        row.category = payload.category
    if payload.published is not None:
        row.published_at = now_utc() if payload.published else None
    row.version += 1
    row.updated_by_user_id = user.id
    row.updated_at = now_utc()
    response = _page_payload(row, include_content=True)
    _save_idem(db, user, f"forum_page_patch:{page_id}", key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.page.patch", entity_type="structure_page", entity_id=str(row.id), event_id=None, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "version": row.version})
    db.commit()
    return response


@router.get("/structures/{slug}/visibility")
def get_visibility(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    membership = _require_role(db, org.id, user, "MEMBER")
    return {"settings": _visibility_settings(org), "structureVisibility": (org.visibility or "PRIVATE").upper(), "canManage": ROLE_RANK.get((membership.role or "MEMBER").upper(), 0) >= ROLE_RANK["MANAGER"], "preview": {"public": _base_public_page(db, org) if (org.visibility or "PRIVATE").upper() == "PUBLIC" else None, "member": {"name": org.name, "members": "visible selon rôle", "documents": "visible selon rôle", "stats": "privé"}}}


@router.patch("/structures/{slug}/visibility")
def patch_visibility(slug: str, payload: VisibilityPatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    key, previous = _write_idem(db, user, f"forum_visibility_patch:{org.id}", idempotency_key)
    if previous is not None:
        return previous
    if payload.stats == "PUBLIC" and not payload.confirm_public_finance:
        raise HTTPException(status_code=400, detail={"reason": "PUBLIC_FINANCE_CONFIRMATION_REQUIRED"})
    settings = _visibility_settings(org)
    for name, value in payload.model_dump(exclude_none=True, exclude={"confirm_public_finance"}).items():
        settings[name] = value
    org.visibility_settings_json = settings
    org.visibility = "PUBLIC" if settings["page"] == "PUBLIC" else "PRIVATE"
    response = {"settings": settings, "structureVisibility": org.visibility}
    _save_idem(db, user, f"forum_visibility_patch:{org.id}", key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.visibility.patch", entity_type="organization", entity_id=str(org.id), event_id=None, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "settings": settings})
    db.commit()
    return response


@router.get("/structures/{slug}/stats")
def get_stats(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    membership = _require_role(db, org.id, user, "MANAGER")
    return _latest_stats(db, org.id, allow_finance=ROLE_RANK.get((membership.role or "MEMBER").upper(), 0) >= ROLE_RANK["TREASURER"])


@router.get("/structures/{slug}/archives")
def get_archives(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    membership = _require_role(db, org.id, user, "MEMBER")
    return {
        "documents": [_document_payload(row) for row in db.query(StructureDocument).filter(StructureDocument.organization_id == org.id, StructureDocument.archived_at.is_not(None)).order_by(StructureDocument.archived_at.desc()).all()],
        "albums": [_album_payload(db, row, include_media=False) for row in db.query(StructureAlbum).filter(StructureAlbum.organization_id == org.id, StructureAlbum.status == "ARCHIVED").order_by(StructureAlbum.archived_at.desc()).all()],
        "discussions": [_discussion_payload(db, row, membership) for row in db.query(StructureDiscussionPost).filter(StructureDiscussionPost.organization_id == org.id, StructureDiscussionPost.channel_id.in_(_visible_channel_ids(db, org.id, membership)), StructureDiscussionPost.is_archived.is_(True)).order_by(StructureDiscussionPost.created_at.desc()).limit(100).all()],
        "pages": [_page_payload(row, include_content=True) for row in db.query(StructurePage).filter(StructurePage.organization_id == org.id, StructurePage.published_at.is_(None)).order_by(StructurePage.updated_at.desc()).all()],
    }


@router.get("/structures/{slug}/settings")
def get_settings(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    _require_role(db, org.id, user, "MANAGER")
    return _structure_payload(org, include_private=True)


@router.patch("/structures/{slug}/settings")
def patch_settings(slug: str, payload: SettingsPatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db), idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    org = _structure_or_404(db, slug)
    actor = _require_role(db, org.id, user, "MANAGER")
    key, previous = _write_idem(db, user, f"forum_settings_patch:{org.id}", idempotency_key)
    if previous is not None:
        return previous
    mapping = {"org_type": "org_type", "logo_url": "logo_url", "banner_url": "banner_url", "primary_color": "primary_color", "secondary_color": "secondary_color", "contact_email": "contact_email", "contact_phone": "contact_phone", "website_url": "website_url", "instagram_handle": "instagram_handle", "name": "name", "description": "description", "city": "city", "address": "address"}
    for key_name, value in payload.model_dump(exclude_none=True).items():
        if key_name in {"portal", "history", "sponsors"}:
            org.public_content_json = {**(org.public_content_json or {}), key_name: value}
        else:
            setattr(org, mapping[key_name], value.strip() if isinstance(value, str) else value)
    response = _structure_payload(org, include_private=True)
    _save_idem(db, user, f"forum_settings_patch:{org.id}", key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.settings.patch", entity_type="organization", entity_id=str(org.id), event_id=None, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "fields": list(payload.model_dump(exclude_none=True).keys())})
    db.commit()
    return response


@router.get("/structures/{slug}/audit")
def get_structure_audit(slug: str, limit: int = Query(default=100, ge=1, le=250), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    _require_role(db, org.id, user, "MANAGER")
    rows = db.query(AuditLog).order_by(AuditLog.ts.desc(), AuditLog.id.desc()).limit(1000).all()
    items = []
    for row in rows:
        payload = row.payload_json if isinstance(row.payload_json, dict) else {}
        if str(payload.get("structure_id") or payload.get("organization_id") or "") != str(org.id):
            continue
        actor = db.get(AppUser, row.actor_user_id) if row.actor_user_id else None
        items.append({"id": row.id, "userId": row.actor_user_id, "userName": actor.display_name if actor else None, "action": row.action, "resource": row.entity_type, "resourceId": row.entity_id, "date": row.ts.isoformat() if row.ts else None, "details": payload})
        if len(items) >= limit:
            break
    return {"items": items}
