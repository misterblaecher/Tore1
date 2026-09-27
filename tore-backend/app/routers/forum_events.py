from __future__ import annotations

import re
import unicodedata
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security.user_auth import get_current_user
from app.deps.db import get_db
from app.models.forum_events import ForumEventPage
from app.routers.forum import (
    _album_payload,
    _save_idem,
    _structure_or_404,
    _visibility_settings,
    _write_idem,
)
from app.services.audit_service import write_audit_log
from app.services.structure_rbac import require_capability
from app.services.p3_common import get_event_runtime_state
from db import now_utc
from models import AppUser, Event, Organization, StructureAlbum


router = APIRouter(prefix="/forum", tags=["forum-events"])

RECAP_NONE = "NONE"
RECAP_DRAFT = "RECAP_DRAFT"
RECAP_PUBLISHED = "RECAP_PUBLISHED"
CLOSED_STATES = {"CLOSED", "ENDED"}


class EventPageSettingsIn(BaseModel):
    capacity_public: bool = False
    cohost_structure_ids: list[int] = Field(default_factory=list, max_length=12)
    previous_event_id: Optional[int] = None
    next_event_id: Optional[int] = None


class RecapStatIn(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=120)


class RecapDraftIn(BaseModel):
    summary: Optional[str] = Field(default=None, max_length=10000)
    album_id: Optional[int] = None
    stats: list[RecapStatIn] = Field(default_factory=list, max_length=12)


class RecapPublishIn(BaseModel):
    confirm_publish: bool = False


def _event_slug(event: Event) -> str:
    normalized_name = "".join(
        character
        for character in unicodedata.normalize("NFD", event.name or "event")
        if unicodedata.category(character) != "Mn"
    )
    base = re.sub(r"[^a-z0-9]+", "-", normalized_name.lower()).strip("-")[:180] or "event"
    return f"{base}-{event.id}"


def _legacy_event_slug(event: Event) -> str:
    """Slug emitted before accent normalization; kept only as a read alias."""
    base = re.sub(r"[^a-z0-9]+", "-", (event.name or "event").lower()).strip("-")[:180] or "event"
    return f"{base}-{event.id}"


def _event_for_org(db: Session, org_id: int, event_id: int) -> Event:
    event = db.get(Event, event_id)
    if event is None or (event.host_type or "").lower() != "orga" or str(event.host_id or "") != str(org_id):
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def _page_for_event(db: Session, event: Event, *, create: bool) -> Optional[ForumEventPage]:
    row = db.query(ForumEventPage).filter(ForumEventPage.event_id == event.id).first()
    if row is None and create:
        row = ForumEventPage(event_id=event.id, slug=_event_slug(event))
        db.add(row)
        db.flush()
    elif row is not None:
        canonical = _event_slug(event)
        if row.slug != canonical:
            row.slug = canonical
            row.updated_at = now_utc()
    return row


def _sync_recap_draft(db: Session, event: Event, row: ForumEventPage) -> bool:
    runtime_state = (get_event_runtime_state(db, event.id) or "").upper()
    if runtime_state in CLOSED_STATES and row.recap_status == RECAP_NONE:
        row.recap_status = RECAP_DRAFT
        row.updated_at = now_utc()
        return True
    return False


def _public_structure_summary(org: Optional[Organization]) -> Optional[dict]:
    if org is None:
        return None
    settings = _visibility_settings(org)
    if (org.visibility or "PRIVATE").upper() != "PUBLIC" or settings["page"] != "PUBLIC":
        return None
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "logoUrl": org.logo_url,
        "type": org.org_type,
    }


def _host_org(db: Session, event: Event) -> Optional[Organization]:
    if (event.host_type or "").lower() != "orga" or not event.host_id:
        return None
    try:
        return db.get(Organization, int(event.host_id))
    except (TypeError, ValueError):
        return None


def _organizer_payload(db: Session, event: Event) -> dict:
    org = _host_org(db, event)
    public = _public_structure_summary(org)
    if public is not None:
        return public
    return {
        "id": None,
        "name": event.host_display_name or "Organisateur TORÈ",
        "slug": None,
        "logoUrl": None,
        "type": None,
    }


def _cohost_payloads(db: Session, row: Optional[ForumEventPage], *, public_only: bool) -> list[dict]:
    if row is None or not isinstance(row.cohost_structure_ids_json, list):
        return []
    items: list[dict] = []
    seen: set[int] = set()
    for raw_id in row.cohost_structure_ids_json:
        try:
            org_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if org_id in seen:
            continue
        seen.add(org_id)
        org = db.get(Organization, org_id)
        if org is None:
            continue
        public = _public_structure_summary(org)
        if public_only:
            if public is not None:
                items.append(public)
        else:
            items.append(public or {
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "logoUrl": org.logo_url,
                "type": org.org_type,
            })
    return items


def _is_public_event(event: Optional[Event]) -> bool:
    return bool(
        event
        and (event.visibility or "PRIVATE").upper() == "PUBLIC"
        and (event.publication_status or "DRAFT").upper() == "PUBLISHED"
    )


def _resolve_public_event(db: Session, slug: str) -> tuple[Event, Optional[ForumEventPage]]:
    row = db.query(ForumEventPage).filter(ForumEventPage.slug == slug).first()
    if row is not None:
        event = db.get(Event, row.event_id)
        if not _is_public_event(event):
            raise HTTPException(status_code=404, detail="Event not found")
        return event, row

    match = re.search(r"-(\d+)$", slug)
    if match is None:
        raise HTTPException(status_code=404, detail="Event not found")
    event = db.get(Event, int(match.group(1)))
    if not _is_public_event(event):
        raise HTTPException(status_code=404, detail="Event not found")
    if slug not in {_event_slug(event), _legacy_event_slug(event)}:
        raise HTTPException(status_code=404, detail="Event not found")
    return event, db.query(ForumEventPage).filter(ForumEventPage.event_id == event.id).first()


def _edition_link(db: Session, event_id: Optional[int]) -> Optional[dict]:
    if event_id is None:
        return None
    event = db.get(Event, event_id)
    if not _is_public_event(event):
        return None
    return {
        "id": event.id,
        "title": event.name,
        "slug": _event_slug(event),
        "path": f"/forum/events/{_event_slug(event)}",
        "startsAt": event.starts_at.isoformat() if event.starts_at else None,
    }


def _public_recap(db: Session, event: Event, row: Optional[ForumEventPage]) -> Optional[dict]:
    if row is None or row.recap_status != RECAP_PUBLISHED:
        return None

    album_payload = None
    if row.recap_album_id is not None:
        album = db.get(StructureAlbum, row.recap_album_id)
        if (
            album is not None
            and album.event_id == event.id
            and (album.status or "DRAFT").upper() == "PUBLISHED"
            and (album.visibility or "STRUCTURE_MEMBERS").upper() == "PUBLIC"
        ):
            album_payload = _album_payload(db, album, include_media=True)

    stats = row.recap_stats_json if isinstance(row.recap_stats_json, list) else []
    return {
        "status": RECAP_PUBLISHED,
        "summary": row.recap_summary,
        "album": album_payload,
        "stats": stats,
        "publishedAt": row.recap_published_at.isoformat() if row.recap_published_at else None,
        "previousEdition": _edition_link(db, row.previous_event_id),
        "nextEdition": _edition_link(db, row.next_event_id),
    }


def _public_payload(db: Session, event: Event, row: Optional[ForumEventPage]) -> dict:
    organizer = _organizer_payload(db, event)
    cohosts = _cohost_payloads(db, row, public_only=True)
    structures: list[dict] = []
    if organizer.get("slug"):
        structures.append(organizer)
    structures.extend(item for item in cohosts if item.get("slug"))
    recap = _public_recap(db, event, row)
    return {
        "id": event.id,
        "slug": _event_slug(event),
        "canonicalPath": f"/forum/events/{_event_slug(event)}",
        "title": event.name,
        "coverUrl": event.banner_url,
        "startsAt": event.starts_at.isoformat() if event.starts_at else None,
        "endsAt": event.ends_at.isoformat() if event.ends_at else None,
        "venue": event.venue,
        "address": event.address,
        "city": event.city,
        "description": event.public_description,
        "organizer": organizer,
        "cohosts": cohosts,
        "structures": structures,
        "capacity": event.capacity if row is not None and row.capacity_public else None,
        "entryPriceCents": event.entry_price_cents,
        "currency": event.currency or "EUR",
        "appCtaPath": f"/rejoindre?event={event.id}",
        "appDeepLink": f"tore://event/{event.id}",
        "lifecycleStatus": RECAP_PUBLISHED if recap is not None else get_event_runtime_state(db, event.id),
        "recap": recap,
    }


def _private_payload(db: Session, event: Event, row: ForumEventPage) -> dict:
    album = db.get(StructureAlbum, row.recap_album_id) if row.recap_album_id is not None else None
    return {
        "event": {
            "id": event.id,
            "title": event.name,
            "slug": _event_slug(event),
            "runtimeState": get_event_runtime_state(db, event.id),
            "visibility": (event.visibility or "PRIVATE").upper(),
            "publicationStatus": (event.publication_status or "DRAFT").upper(),
        },
        "page": {
            "capacityPublic": bool(row.capacity_public),
            "cohosts": _cohost_payloads(db, row, public_only=False),
            "previousEventId": row.previous_event_id,
            "nextEventId": row.next_event_id,
        },
        "recap": {
            "status": row.recap_status,
            "summary": row.recap_summary,
            "album": _album_payload(db, album, include_media=True) if album is not None else None,
            "stats": row.recap_stats_json if isinstance(row.recap_stats_json, list) else [],
            "publishedAt": row.recap_published_at.isoformat() if row.recap_published_at else None,
        },
    }


def _validate_related_event(db: Session, org_id: int, current_event_id: int, candidate_id: Optional[int]) -> Optional[int]:
    if candidate_id is None:
        return None
    if candidate_id == current_event_id:
        raise HTTPException(status_code=422, detail={"reason": "EDITION_CANNOT_REFERENCE_ITSELF"})
    _event_for_org(db, org_id, candidate_id)
    return candidate_id


@router.get("/events/{slug}")
def get_public_event_page(slug: str, db: Session = Depends(get_db)):
    event, row = _resolve_public_event(db, slug)
    return _public_payload(db, event, row)


@router.get("/structures/{slug}/events/{event_id}/recap")
def get_private_event_recap(
    slug: str,
    event_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    require_capability(db, org.id, user, "event.recap.manage")
    event = _event_for_org(db, org.id, event_id)
    row = _page_for_event(db, event, create=True)
    assert row is not None
    changed = _sync_recap_draft(db, event, row)
    if changed:
        db.commit()
        db.refresh(row)
    return _private_payload(db, event, row)


@router.put("/structures/{slug}/events/{event_id}/public-page")
def replace_event_page_settings(
    slug: str,
    event_id: int,
    payload: EventPageSettingsIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    org = _structure_or_404(db, slug)
    actor = require_capability(db, org.id, user, "event.manage")
    event = _event_for_org(db, org.id, event_id)
    action_key = f"forum_event_page_settings:{event.id}"
    key, previous = _write_idem(db, user, action_key, idempotency_key)
    if previous is not None:
        return previous

    normalized_cohosts: list[int] = []
    for cohost_id in payload.cohost_structure_ids:
        if cohost_id == org.id or cohost_id in normalized_cohosts:
            continue
        if db.get(Organization, cohost_id) is None:
            raise HTTPException(status_code=422, detail={"reason": "COHOST_STRUCTURE_NOT_FOUND", "structureId": cohost_id})
        normalized_cohosts.append(cohost_id)

    row = _page_for_event(db, event, create=True)
    assert row is not None
    row.capacity_public = payload.capacity_public
    row.cohost_structure_ids_json = normalized_cohosts
    row.previous_event_id = _validate_related_event(db, org.id, event.id, payload.previous_event_id)
    row.next_event_id = _validate_related_event(db, org.id, event.id, payload.next_event_id)
    row.updated_at = now_utc()
    response = _private_payload(db, event, row)
    _save_idem(db, user, action_key, key, response)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="forum.event.public_page.update",
        entity_type="event",
        entity_id=str(event.id),
        event_id=event.id,
        committee_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={
            "structure_id": org.id,
            "capacity_public": row.capacity_public,
            "cohost_structure_ids": normalized_cohosts,
            "previous_event_id": row.previous_event_id,
            "next_event_id": row.next_event_id,
        },
    )
    db.commit()
    return response


@router.put("/structures/{slug}/events/{event_id}/recap")
def replace_event_recap_draft(
    slug: str,
    event_id: int,
    payload: RecapDraftIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    org = _structure_or_404(db, slug)
    actor = require_capability(db, org.id, user, "event.recap.manage")
    event = _event_for_org(db, org.id, event_id)
    if (get_event_runtime_state(db, event.id) or "").upper() not in CLOSED_STATES:
        raise HTTPException(status_code=409, detail={"reason": "EVENT_NOT_CLOSED"})

    action_key = f"forum_event_recap_draft:{event.id}"
    key, previous = _write_idem(db, user, action_key, idempotency_key)
    if previous is not None:
        return previous

    row = _page_for_event(db, event, create=True)
    assert row is not None
    _sync_recap_draft(db, event, row)
    if row.recap_status == RECAP_PUBLISHED:
        raise HTTPException(status_code=409, detail={"reason": "RECAP_ALREADY_PUBLISHED"})

    album = None
    if payload.album_id is not None:
        album = db.get(StructureAlbum, payload.album_id)
        if album is None or album.organization_id != org.id or album.event_id != event.id:
            raise HTTPException(status_code=422, detail={"reason": "RECAP_ALBUM_INVALID"})
    row.recap_summary = payload.summary.strip() if payload.summary else None
    row.recap_album_id = album.id if album is not None else None
    row.recap_stats_json = [{"label": stat.label.strip(), "value": stat.value.strip()} for stat in payload.stats]
    row.updated_at = now_utc()
    response = _private_payload(db, event, row)
    _save_idem(db, user, action_key, key, response)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="forum.event.recap.update",
        entity_type="event",
        entity_id=str(event.id),
        event_id=event.id,
        committee_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={"structure_id": org.id, "stat_count": len(row.recap_stats_json), "album_id": row.recap_album_id},
    )
    db.commit()
    return response


@router.post("/structures/{slug}/events/{event_id}/recap/publish")
def publish_event_recap(
    slug: str,
    event_id: int,
    payload: RecapPublishIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    org = _structure_or_404(db, slug)
    actor = require_capability(db, org.id, user, "event.recap.manage")
    require_capability(db, org.id, user, "event.publish")
    event = _event_for_org(db, org.id, event_id)
    if (get_event_runtime_state(db, event.id) or "").upper() not in CLOSED_STATES:
        raise HTTPException(status_code=409, detail={"reason": "EVENT_NOT_CLOSED"})
    if not payload.confirm_publish:
        raise HTTPException(status_code=409, detail={"reason": "RECAP_PUBLICATION_CONFIRMATION_REQUIRED"})

    action_key = f"forum_event_recap_publish:{event.id}"
    key, previous = _write_idem(db, user, action_key, idempotency_key)
    if previous is not None:
        return previous

    row = _page_for_event(db, event, create=True)
    assert row is not None
    _sync_recap_draft(db, event, row)
    if row.recap_status != RECAP_DRAFT:
        raise HTTPException(status_code=409, detail={"reason": "RECAP_NOT_DRAFT", "status": row.recap_status})

    if row.recap_album_id is not None:
        album = db.get(StructureAlbum, row.recap_album_id)
        if album is None or (album.status or "DRAFT").upper() != "PUBLISHED" or (album.visibility or "").upper() != "PUBLIC":
            raise HTTPException(status_code=409, detail={"reason": "RECAP_ALBUM_MUST_BE_PUBLIC_AND_PUBLISHED"})

    row.recap_status = RECAP_PUBLISHED
    row.recap_published_at = now_utc()
    row.updated_at = now_utc()
    response = _private_payload(db, event, row)
    _save_idem(db, user, action_key, key, response)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="forum.event.recap.publish",
        entity_type="event",
        entity_id=str(event.id),
        event_id=event.id,
        committee_id=None,
        bar_id=None,
        idempotency_key=key,
        payload={"structure_id": org.id, "recap_status": row.recap_status},
    )
    db.commit()
    return response
