"""Public structure directory API with server-side filters and pagination."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from db import now_utc
from models import Event, Organization, OrganizationMembership
from app.legacy.monolith import get_db
from app.routers.forum import (
    STRUCTURE_TYPES,
    _event_payload,
    _structure_payload,
    _visibility_settings,
)


router = APIRouter(prefix="/forum", tags=["forum"])

_TYPE_DB_VALUES = {
    "COMMITTEE": {"COMMITTEE", "COMITE", "COMITÉ"},
    "CIRCLE": {"CIRCLE", "CERCLE"},
    "ORDER": {"ORDER", "ORDRE"},
    "ASSOCIATION": {"ASSOCIATION"},
    "BAR": {"BAR"},
    "PARTNER": {"PARTNER", "PARTENAIRE"},
    "OTHER": {"OTHER", "AUTRE"},
}


def _canonical_requested_type(value: Optional[str]) -> Optional[str]:
    if not value or not value.strip():
        return None
    candidate = value.strip().upper()
    aliases = {"COMITE": "COMMITTEE", "COMITÉ": "COMMITTEE", "CERCLE": "CIRCLE", "ORDRE": "ORDER", "PARTENAIRE": "PARTNER"}
    candidate = aliases.get(candidate, candidate)
    return candidate if candidate in STRUCTURE_TYPES else None


def _next_public_event(db: Session, org: Organization) -> Optional[Event]:
    if _visibility_settings(org).get("events") != "PUBLIC":
        return None
    return (
        db.query(Event)
        .filter(
            Event.host_type == "orga",
            Event.host_id == str(org.id),
            func.upper(func.coalesce(Event.visibility, "PRIVATE")) == "PUBLIC",
            func.upper(func.coalesce(Event.publication_status, "DRAFT")) == "PUBLISHED",
            Event.starts_at >= now_utc(),
        )
        .order_by(Event.starts_at.asc(), Event.id.asc())
        .first()
    )


@router.get("/structures", name="list_structures")
def list_structures(
    q: Optional[str] = Query(default=None, max_length=120),
    type: Optional[str] = Query(default=None, max_length=64),
    city: Optional[str] = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=48),
    db: Session = Depends(get_db),
):
    query = db.query(Organization).filter(func.upper(Organization.visibility) == "PUBLIC")

    # Keep the legacy q/type behavior as the canonical filters used by the public UI.
    if q and q.strip():
        needle = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Organization.name).like(needle),
                func.lower(func.coalesce(Organization.city, "")).like(needle),
            )
        )

    requested_type = _canonical_requested_type(type)
    if requested_type:
        query = query.filter(func.upper(Organization.org_type).in_(_TYPE_DB_VALUES[requested_type]))

    if city and city.strip():
        city_needle = f"%{city.strip().lower()}%"
        query = query.filter(func.lower(func.coalesce(Organization.city, "")).like(city_needle))

    total = query.count()
    total_pages = (total + page_size - 1) // page_size if total else 0
    rows = (
        query.order_by(Organization.name.asc(), Organization.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    member_counts: dict[int, int] = {}
    if rows:
        member_counts = {
            int(org_id): int(count)
            for org_id, count in (
                db.query(OrganizationMembership.organization_id, func.count(OrganizationMembership.id))
                .filter(
                    OrganizationMembership.organization_id.in_([org.id for org in rows]),
                    OrganizationMembership.status == "ACTIVE",
                    OrganizationMembership.revoked_at.is_(None),
                )
                .group_by(OrganizationMembership.organization_id)
                .all()
            )
        }

    upcoming_events: dict[int, Event] = {}
    if rows:
        now = now_utc()
        candidates = (
            db.query(Event)
            .filter(
                Event.host_type == "orga",
                Event.host_id.in_([str(org.id) for org in rows]),
                func.upper(func.coalesce(Event.visibility, "PRIVATE")) == "PUBLIC",
                func.upper(func.coalesce(Event.publication_status, "DRAFT")) == "PUBLISHED",
                Event.starts_at >= now,
            )
            .order_by(Event.starts_at.asc(), Event.id.asc())
            .all()
        )
        for event in candidates:
            org_id = int(event.host_id)
            if org_id not in upcoming_events:
                upcoming_events[org_id] = event

    items = []
    for org in rows:
        settings = _visibility_settings(org)
        next_event = upcoming_events.get(org.id) if settings.get("events") == "PUBLIC" else None
        items.append(
            {
                **_structure_payload(org),
                "memberCount": member_counts.get(org.id, 0) if settings.get("stats") == "PUBLIC" else None,
                "nextPublicEvent": _event_payload(next_event) if next_event else None,
            }
        )

    return {
        "items": items,
        "page": page,
        "pageSize": page_size,
        "total": total,
        "totalPages": total_pages,
    }
