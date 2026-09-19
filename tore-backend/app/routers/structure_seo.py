from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.legacy.monolith import get_current_user, get_db
from app.routers.forum import _structure_or_404, _visibility_settings
from app.services.structure_rbac import require_capability
from app.routers.forum_events import _event_slug, _is_public_event, _public_payload
from app.services.audit_service import write_audit_log
from models import AppUser, Event, Organization

router = APIRouter(prefix="/forum/seo", tags=["forum-seo"])
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED = {"admin", "api", "events", "forum", "login", "structures"}


class StructureSeoPatchIn(BaseModel):
    slug: Optional[str] = Field(default=None, min_length=2, max_length=160)
    indexable: Optional[bool] = None
    title: Optional[str] = Field(default=None, max_length=180)
    description: Optional[str] = Field(default=None, max_length=320)
    image_url: Optional[str] = Field(default=None, max_length=1000)


def _seo_config(org: Organization) -> dict:
    public = org.public_content_json if isinstance(org.public_content_json, dict) else {}
    raw = public.get("seo") if isinstance(public.get("seo"), dict) else {}
    return {
        "indexable": bool(raw.get("indexable", False)),
        "title": raw.get("title"),
        "description": raw.get("description"),
        "imageUrl": raw.get("image_url"),
    }


def _slug_history(org: Organization) -> list[str]:
    public = org.public_content_json if isinstance(org.public_content_json, dict) else {}
    values = public.get("slug_history") if isinstance(public.get("slug_history"), list) else []
    return [str(value) for value in values if value]


def _public_org(org: Organization) -> bool:
    return (org.visibility or "PRIVATE").upper() == "PUBLIC" and _visibility_settings(org).get("page") == "PUBLIC"


def _find_history_owner(db: Session, slug: str) -> Optional[Organization]:
    for org in db.query(Organization).all():
        if slug in _slug_history(org):
            return org
    return None


@router.patch("/structures/{slug}")
def patch_structure_seo(
    slug: str,
    payload: StructureSeoPatchIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    actor = require_capability(db, org.id, user, "structure.publish")
    public = dict(org.public_content_json or {})
    old_slug = org.slug

    if payload.slug is not None:
        next_slug = payload.slug.strip().lower()
        if not SLUG_RE.fullmatch(next_slug) or next_slug in RESERVED:
            raise HTTPException(status_code=422, detail={"reason": "INVALID_STRUCTURE_SLUG"})
        current_conflict = db.query(Organization).filter(Organization.slug == next_slug, Organization.id != org.id).first()
        history_conflict = _find_history_owner(db, next_slug)
        if current_conflict is not None or (history_conflict is not None and history_conflict.id != org.id):
            raise HTTPException(status_code=409, detail={"reason": "STRUCTURE_SLUG_TAKEN"})
        if next_slug != org.slug:
            history = _slug_history(org)
            if org.slug not in history:
                history.append(org.slug)
            public["slug_history"] = history[-20:]
            org.slug = next_slug

    seo = dict(public.get("seo") or {})
    values = payload.model_dump(exclude_none=True)
    if "indexable" in values:
        seo["indexable"] = bool(values["indexable"])
    if "title" in values:
        seo["title"] = values["title"].strip()
    if "description" in values:
        seo["description"] = values["description"].strip()
    if "image_url" in values:
        seo["image_url"] = values["image_url"].strip()
    public["seo"] = seo
    org.public_content_json = public

    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="forum.seo.update",
        entity_type="organization",
        entity_id=str(org.id),
        event_id=None,
        committee_id=None,
        bar_id=None,
        idempotency_key=None,
        payload={"old_slug": old_slug, "new_slug": org.slug, "indexable": seo.get("indexable", False)},
    )
    db.commit()
    return {"slug": org.slug, "previousSlug": old_slug if old_slug != org.slug else None, "seo": _seo_config(org)}


@router.get("/structures/{slug}/settings")
def get_structure_seo_settings(
    slug: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    require_capability(db, org.id, user, "structure.publish")
    seo = _seo_config(org)
    return {
        "slug": org.slug,
        "name": org.name,
        "description": seo.get("description") or org.description,
        "imageUrl": seo.get("imageUrl") or org.banner_url or org.logo_url,
        "title": seo.get("title") or f"{org.name} — TORÈ",
        "indexable": bool(seo.get("indexable")),
        "city": org.city,
    }


@router.get("/structures/{slug}")
def get_structure_seo(slug: str, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.slug == slug).first()
    if org is None:
        historical = _find_history_owner(db, slug)
        if historical is not None and _public_org(historical):
            return {"redirectTo": historical.slug, "permanent": True}
        raise HTTPException(status_code=404, detail="Structure not found")
    if not _public_org(org):
        raise HTTPException(status_code=404, detail="Structure not found")
    seo = _seo_config(org)
    return {
        "slug": org.slug,
        "name": org.name,
        "description": seo.get("description") or org.description,
        "imageUrl": seo.get("imageUrl") or org.banner_url or org.logo_url,
        "title": seo.get("title") or f"{org.name} — TORÈ",
        "indexable": bool(seo.get("indexable")),
        "city": org.city,
    }


@router.get("/structures")
def list_structure_seo(db: Session = Depends(get_db)):
    items = []
    for org in db.query(Organization).all():
        if not _public_org(org):
            continue
        seo = _seo_config(org)
        if seo.get("indexable"):
            items.append({"slug": org.slug})
    return {"items": items}


@router.get("/events/{slug}")
def get_event_seo(slug: str, db: Session = Depends(get_db)):
    from app.models.forum_events import ForumEventPage

    row = db.query(ForumEventPage).filter(ForumEventPage.slug == slug).first()
    event = db.get(Event, row.event_id) if row is not None else None
    if event is None:
        match = re.search(r"-(\d+)$", slug)
        event = db.get(Event, int(match.group(1))) if match else None
    if not _is_public_event(event) or _event_slug(event) != slug:
        raise HTTPException(status_code=404, detail="Event not found")
    assert event is not None
    payload = _public_payload(db, event, row)
    organizer_slug = payload.get("organizer", {}).get("slug")
    organizer = db.query(Organization).filter(Organization.slug == organizer_slug).first() if organizer_slug else None
    indexable = bool(organizer and _seo_config(organizer).get("indexable"))
    return {**payload, "indexable": indexable}


@router.get("/events")
def list_event_seo(db: Session = Depends(get_db)):
    from app.models.forum_events import ForumEventPage

    items = []
    for event in db.query(Event).all():
        if not _is_public_event(event):
            continue
        org = None
        if (event.host_type or "").lower() == "orga" and event.host_id:
            try:
                org = db.get(Organization, int(event.host_id))
            except (TypeError, ValueError):
                org = None
        if org is None or not _public_org(org) or not _seo_config(org).get("indexable"):
            continue
        row = db.query(ForumEventPage).filter(ForumEventPage.event_id == event.id).first()
        items.append({"slug": _event_slug(event)})
    return {"items": items}
