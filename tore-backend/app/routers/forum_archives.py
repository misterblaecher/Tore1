"""Structured heritage archives for the Structure Portal.

This module intentionally projects archived/finished domain objects into one
read model. It does not persist archive copies: documents, albums, pages,
events and memberships remain the source of truth.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from db import now_utc
from models import (
    AppUser,
    Event,
    OrganizationMembership,
    StructureAlbum,
    StructureDiscussionPost,
    StructureDocument,
    StructurePage,
)
from app.legacy.monolith import get_current_user, get_db
from app.routers.forum import (
    _album_payload,
    _can_view,
    _discussion_payload,
    _document_payload,
    _event_payload,
    _page_payload,
    _require_role,
    _save_idem,
    _structure_or_404,
    _visible_channel_ids,
    _write_idem,
)
from app.services.audit_service import write_audit_log
from app.services.structure_rbac import capabilities_for_user, require_capability

router = APIRouter(prefix="/forum", tags=["forum-archives"])

OFFICE_ROLES = {
    "OWNER",
    "PRESIDENT",
    "VICE_PRESIDENT",
    "ADMIN",
    "MANAGER",
    "BUREAU",
    "TREASURER",
    "TRESORIER",
    "SECRETARY",
}
ARCHIVE_CATEGORIES = {"DOCUMENT", "ALBUM", "PAGE", "DISCUSSION", "EVENT"}


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _year(value: Optional[datetime]) -> Optional[int]:
    return value.year if value else None


def _event_for_id(events: dict[int, Event], event_id: Optional[int]) -> Optional[Event]:
    return events.get(event_id) if event_id is not None else None


def _mandate_payload(db: Session, row: OrganizationMembership) -> dict[str, Any]:
    member = None
    try:
        from app.routers.forum import _member_payload
        member = _member_payload(db, row, include_private=False)
    except Exception:
        member = None
    label = row.mandate_label or (row.role or "MEMBER").replace("_", " ").title()
    return {
        "id": row.id,
        "label": label,
        "role": (row.role or "MEMBER").upper(),
        "status": (row.status or "ACTIVE").upper(),
        "member": member,
        "startsAt": _iso(row.starts_at or row.joined_at),
        "endsAt": _iso(row.ends_at or row.revoked_at),
        "isAlumni": (row.status or "ACTIVE").upper() in {"REVOKED", "LEFT"} or row.ends_at is not None,
    }


def _mandate_for_date(mandates: list[dict[str, Any]], at: Optional[datetime]) -> Optional[dict[str, Any]]:
    if at is None:
        return None
    for mandate in mandates:
        start = datetime.fromisoformat(mandate["startsAt"]) if mandate.get("startsAt") else None
        end = datetime.fromisoformat(mandate["endsAt"]) if mandate.get("endsAt") else None
        if (start is None or start <= at) and (end is None or at <= end):
            return mandate
    return None


def _entry(
    *,
    category: str,
    object_id: int,
    title: str,
    archived_at: Optional[datetime],
    event: Optional[Event],
    mandate: Optional[dict[str, Any]],
    target: str,
    subtitle: Optional[str] = None,
    restore_path: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "key": f"{category.lower()}:{object_id}",
        "category": category,
        "objectId": object_id,
        "title": title,
        "subtitle": subtitle,
        "archivedAt": _iso(archived_at),
        "year": _year(archived_at),
        "event": _event_payload(event) if event else None,
        "mandate": mandate,
        "target": target,
        "restorePath": restore_path,
    }


def _matches(entry: dict[str, Any], *, search: str, year: Optional[int], mandate: Optional[str], event_id: Optional[int], category: Optional[str]) -> bool:
    if year is not None and entry.get("year") != year:
        return False
    if category and entry.get("category") != category:
        return False
    if event_id is not None and (entry.get("event") or {}).get("id") != event_id:
        return False
    if mandate and mandate.lower() not in ((entry.get("mandate") or {}).get("label") or "").lower():
        return False
    if search:
        haystack = " ".join(
            str(value or "")
            for value in (
                entry.get("title"),
                entry.get("subtitle"),
                (entry.get("event") or {}).get("name"),
                (entry.get("mandate") or {}).get("label"),
                entry.get("category"),
            )
        ).lower()
        if search.lower() not in haystack:
            return False
    return True


@router.get("/structures/{slug}/archives/structured")
def get_structured_archives(
    slug: str,
    search: str = Query(default="", max_length=120),
    year: Optional[int] = Query(default=None, ge=1900, le=2200),
    mandate: Optional[str] = Query(default=None, max_length=120),
    event_id: Optional[int] = Query(default=None, ge=1),
    category: Optional[str] = Query(default=None),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    membership = _require_role(db, org.id, user, "MEMBER")
    _, capabilities = capabilities_for_user(db, org.id, user.id)
    normalized_category = category.upper() if category else None
    if normalized_category and normalized_category not in ARCHIVE_CATEGORIES:
        raise HTTPException(status_code=400, detail={"reason": "INVALID_ARCHIVE_CATEGORY"})

    membership_rows = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org.id
    ).order_by(OrganizationMembership.starts_at.desc(), OrganizationMembership.joined_at.desc()).all()
    office_history = [_mandate_payload(db, row) for row in membership_rows if (row.role or "MEMBER").upper() in OFFICE_ROLES]

    events = db.query(Event).filter(Event.host_type == "orga", Event.host_id == str(org.id)).all()
    event_map = {row.id: row for row in events}
    now = now_utc()
    past_events = [row for row in events if row.starts_at and row.starts_at < now]
    past_events.sort(key=lambda row: row.starts_at or datetime.min, reverse=True)

    entries: list[dict[str, Any]] = []

    for row in db.query(StructureDocument).filter(
        StructureDocument.organization_id == org.id,
        StructureDocument.archived_at.is_not(None),
    ).order_by(StructureDocument.archived_at.desc()).all():
        if not _can_view(row.visibility, membership):
            continue
        event = _event_for_id(event_map, row.event_id)
        at = row.archived_at or row.updated_at or row.created_at
        entries.append(_entry(
            category="DOCUMENT",
            object_id=row.id,
            title=row.title,
            subtitle=row.folder or "Document archivé",
            archived_at=at,
            event=event,
            mandate=_mandate_for_date(office_history, at),
            target=f"/forum/structures/{slug}/documents",
            restore_path=f"/forum/structures/{slug}/archives/documents/{row.id}/restore" if "document.manage" in capabilities else None,
        ))

    for row in db.query(StructureAlbum).filter(
        StructureAlbum.organization_id == org.id,
        or_(StructureAlbum.archived_at.is_not(None), StructureAlbum.status == "ARCHIVED"),
    ).order_by(StructureAlbum.archived_at.desc()).all():
        if not _can_view(row.visibility, membership):
            continue
        event = _event_for_id(event_map, row.event_id)
        at = row.archived_at or row.updated_at or row.created_at
        entries.append(_entry(
            category="ALBUM",
            object_id=row.id,
            title=row.title,
            subtitle="Album archivé",
            archived_at=at,
            event=event,
            mandate=_mandate_for_date(office_history, at),
            target=f"/forum/structures/{slug}/albums",
            restore_path=f"/forum/structures/{slug}/archives/albums/{row.id}/restore" if "album.manage" in capabilities else None,
        ))

    for row in db.query(StructurePage).filter(
        StructurePage.organization_id == org.id,
        StructurePage.published_at.is_(None),
    ).order_by(StructurePage.updated_at.desc()).all():
        if not _can_view(row.visibility, membership):
            continue
        at = row.updated_at or row.created_at
        entries.append(_entry(
            category="PAGE",
            object_id=row.id,
            title=row.title,
            subtitle=f"{row.category} · v{row.version}",
            archived_at=at,
            event=None,
            mandate=_mandate_for_date(office_history, at),
            target=f"/forum/structures/{slug}/folklore",
        ))

    visible_channel_ids = _visible_channel_ids(db, org.id, membership)
    if visible_channel_ids:
        for row in db.query(StructureDiscussionPost).filter(
            StructureDiscussionPost.organization_id == org.id,
            StructureDiscussionPost.channel_id.in_(visible_channel_ids),
            StructureDiscussionPost.is_archived.is_(True),
        ).order_by(StructureDiscussionPost.created_at.desc()).limit(200).all():
            payload = _discussion_payload(db, row, membership)
            at = row.updated_at or row.created_at
            entries.append(_entry(
                category="DISCUSSION",
                object_id=row.id,
                title=payload.get("title") or "Discussion archivée",
                subtitle=payload.get("channelName") or "Discussion interne",
                archived_at=at,
                event=None,
                mandate=_mandate_for_date(office_history, at),
                target=f"/forum/structures/{slug}/discussions",
            ))

    for event in past_events:
        at = event.ends_at or event.starts_at
        entries.append(_entry(
            category="EVENT",
            object_id=event.id,
            title=event.name,
            subtitle=event.venue or event.city or "Événement passé",
            archived_at=at,
            event=event,
            mandate=_mandate_for_date(office_history, at),
            target=f"/forum/structures/{slug}/events/{event.id}",
        ))

    filtered = [item for item in entries if _matches(
        item,
        search=search.strip(),
        year=year,
        mandate=(mandate or "").strip() or None,
        event_id=event_id,
        category=normalized_category,
    )]
    filtered.sort(key=lambda item: item.get("archivedAt") or "", reverse=True)

    years = sorted({item["year"] for item in entries if item.get("year") is not None}, reverse=True)
    event_options = [{"id": row.id, "name": row.name, "startsAt": _iso(row.starts_at)} for row in past_events]
    mandate_options = []
    seen_mandates: set[str] = set()
    for item in office_history:
        label = item["label"]
        if label not in seen_mandates:
            seen_mandates.add(label)
            mandate_options.append(item)

    return {
        "structure": {"id": org.id, "slug": org.slug, "name": org.name},
        "filters": {
            "years": years,
            "mandates": mandate_options,
            "events": event_options,
            "categories": sorted(ARCHIVE_CATEGORIES),
        },
        "summary": {
            "total": len(entries),
            "filtered": len(filtered),
            "pastEvents": len(past_events),
            "officeTerms": len(office_history),
        },
        "items": filtered,
        "officeHistory": office_history,
        "pastEvents": [_event_payload(row) for row in past_events[:100]],
        "links": {
            "members": f"/forum/structures/{slug}/members",
            "alumni": f"/forum/structures/{slug}/members?include_archived=true",
        },
    }


@router.post("/structures/{slug}/archives/documents/{document_id}/restore")
def restore_archived_document(
    slug: str,
    document_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    org = _structure_or_404(db, slug)
    actor = require_capability(db, org.id, user, "document.manage")
    key, previous = _write_idem(db, user, f"forum_document_restore:{document_id}", idempotency_key)
    if previous is not None:
        return previous
    row = db.get(StructureDocument, document_id)
    if row is None or row.organization_id != org.id:
        raise HTTPException(status_code=404, detail="Document not found")
    row.archived_at = None
    row.updated_at = now_utc()
    response = {"ok": True, "id": row.id, "restored": True}
    _save_idem(db, user, f"forum_document_restore:{document_id}", key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.document.restore", entity_type="structure_document", entity_id=str(row.id), event_id=row.event_id, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id})
    db.commit()
    return response


@router.post("/structures/{slug}/archives/albums/{album_id}/restore")
def restore_archived_album(
    slug: str,
    album_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    org = _structure_or_404(db, slug)
    actor = require_capability(db, org.id, user, "album.manage")
    key, previous = _write_idem(db, user, f"forum_album_restore:{album_id}", idempotency_key)
    if previous is not None:
        return previous
    row = db.get(StructureAlbum, album_id)
    if row is None or row.organization_id != org.id:
        raise HTTPException(status_code=404, detail="Album not found")
    row.archived_at = None
    row.status = "DRAFT"
    row.updated_at = now_utc()
    response = {"ok": True, "id": row.id, "restored": True, "status": row.status}
    _save_idem(db, user, f"forum_album_restore:{album_id}", key, response)
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=actor.role, action="forum.album.restore", entity_type="structure_album", entity_id=str(row.id), event_id=row.event_id, committee_id=None, bar_id=None, idempotency_key=key, payload={"structure_id": org.id, "status": row.status})
    db.commit()
    return response
