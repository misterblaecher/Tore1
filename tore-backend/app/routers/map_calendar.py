from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from db import now_utc
from models import Bar, Event, EventMapIdempotency, EventMapSettings, EventNavettesSettings
from partner_auth import current_identity
from app.services.authz_service import ensure_partner_role
from app.services.audit_service import write_audit_log

router = APIRouter(tags=["map-calendar"])


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


def _require_orga_manager_identity(identity=Depends(current_identity)):
    ensure_partner_role(identity, {"manager", "owner"})
    return identity


def _require_idempotency(idempotency_key: str | None) -> str:
    key = (idempotency_key or "").strip()
    if len(key) < 4:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency-Key required"})
    return key


def _event_for_identity(db: Session, event_id: int, identity: dict) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail={"reason": "event_not_found"})
    if event.bar_id != identity.get("bar_id"):
        raise HTTPException(status_code=403, detail={"reason": "forbidden"})
    return event


def _is_map_module_on(event: Event) -> bool:
    modules = event.modules_on or {}
    return modules.get("map") is True


def _get_or_create_map_settings(db: Session, event_id: int) -> EventMapSettings:
    row = db.query(EventMapSettings).filter(EventMapSettings.event_id == event_id).first()
    if row:
        return row
    row = EventMapSettings(event_id=event_id, enabled=False)
    db.add(row)
    db.flush()
    return row


def _get_or_create_navettes_settings(db: Session, event_id: int) -> EventNavettesSettings:
    row = db.query(EventNavettesSettings).filter(EventNavettesSettings.event_id == event_id).first()
    if row:
        return row
    row = EventNavettesSettings(event_id=event_id, enabled=False)
    db.add(row)
    db.flush()
    return row


def _map_payload(event: Event, settings: EventMapSettings, navettes: EventNavettesSettings | None) -> dict:
    return {
        "enabled": bool(settings.enabled),
        "venueName": settings.venue_name or event.venue,
        "address": settings.address,
        "lat": settings.lat,
        "lng": settings.lng,
        "tecLink": settings.tec_link,
        "wazeLink": settings.waze_link,
        "navettes": {
            "enabled": bool(navettes.enabled) if navettes else False,
            "address": navettes.address if navettes else None,
            "lastReturnTime": navettes.last_return_time if navettes else None,
            "notes": navettes.notes if navettes else None,
        },
    }


def _iso_utc_compact(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return normalized.strftime("%Y%m%dT%H%M%SZ")


def _escape_ics(text: str | None) -> str:
    if not text:
        return ""
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


@router.get("/events/{event_id}/map")
def get_event_map(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail={"reason": "event_not_found"})
    if not _is_map_module_on(event):
        raise HTTPException(status_code=404, detail={"reason": "MODULE_OFF", "message": "Map module is disabled"})
    settings = _get_or_create_map_settings(db, event_id)
    navettes = db.query(EventNavettesSettings).filter(EventNavettesSettings.event_id == event_id).first()
    return _map_payload(event, settings, navettes)


@router.get("/calendar/events")
def get_public_calendar_events(
    from_: datetime = Query(alias="from"),
    to: datetime = Query(),
    scope: str = Query(default="public"),
    limit: int = Query(default=100, ge=1, le=200),
    cursor: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if scope != "public":
        raise HTTPException(status_code=400, detail={"reason": "invalid_scope"})

    q = (
        db.query(Event, Bar)
        .join(Bar, Bar.id == Event.bar_id, isouter=True)
        .filter(Event.starts_at <= to, Event.ends_at >= from_)
        .order_by(Event.starts_at.asc(), Event.id.asc())
    )
    if cursor:
        q = q.filter(Event.id > cursor)
    rows = q.limit(limit + 1).all()

    now = now_utc()
    items = []
    for event, bar in rows[:limit]:
        if event.starts_at <= now <= event.ends_at:
            status = "LIVE"
        elif event.starts_at.date() == now.date():
            status = "TODAY"
        else:
            status = "UPCOMING"
        items.append(
            {
                "id": event.id,
                "name": event.name,
                "startAt": event.starts_at,
                "endAt": event.ends_at,
                "venue": event.venue,
                "address": event.venue,
                "barId": event.bar_id,
                "barName": bar.name if bar else None,
                "status": status,
            }
        )

    next_cursor = rows[limit][0].id if len(rows) > limit else None
    return {"items": items, "nextCursor": next_cursor}


@router.get("/calendar/events/{event_id}.ics", response_class=PlainTextResponse)
def get_calendar_event_ics(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail={"reason": "event_not_found"})

    starts = _iso_utc_compact(event.starts_at) or ""
    ends = _iso_utc_compact(event.ends_at) or starts
    summary = _escape_ics(event.name)
    location = _escape_ics(event.venue)

    body = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//TORE//Event Calendar//FR",
            "BEGIN:VEVENT",
            f"UID:tore-event-{event.id}@tore.app",
            f"DTSTAMP:{_iso_utc_compact(now_utc())}",
            f"DTSTART:{starts}",
            f"DTEND:{ends}",
            f"SUMMARY:{summary}",
            f"LOCATION:{location}",
            f"URL:tore://event/{event.id}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    return PlainTextResponse(content=body, media_type="text/calendar; charset=utf-8")


@router.get("/partner/portal/orga/events/{event_id}/map/settings")
def orga_get_event_map_settings(
    event_id: int,
    identity=Depends(_require_orga_manager_identity),
    db: Session = Depends(get_db),
):
    event = _event_for_identity(db, event_id, identity)
    settings = _get_or_create_map_settings(db, event_id)
    navettes = _get_or_create_navettes_settings(db, event_id)
    return _map_payload(event, settings, navettes)


@router.put("/partner/portal/orga/events/{event_id}/map/settings")
def orga_put_event_map_settings(
    event_id: int,
    payload: dict,
    identity=Depends(_require_orga_manager_identity),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = _require_idempotency(idempotency_key)
    _event_for_identity(db, event_id, identity)

    existing = (
        db.query(EventMapIdempotency)
        .filter(EventMapIdempotency.event_id == event_id, EventMapIdempotency.idempotency_key == key)
        .first()
    )
    if existing:
        return existing.response_json

    settings = _get_or_create_map_settings(db, event_id)
    navettes = _get_or_create_navettes_settings(db, event_id)

    if "enabled" in payload:
        settings.enabled = bool(payload.get("enabled"))
    if "venueName" in payload:
        settings.venue_name = payload.get("venueName")
    if "address" in payload:
        settings.address = payload.get("address")
    if "lat" in payload:
        settings.lat = float(payload.get("lat")) if payload.get("lat") is not None else None
    if "lng" in payload:
        settings.lng = float(payload.get("lng")) if payload.get("lng") is not None else None
    if "tecLink" in payload:
        settings.tec_link = payload.get("tecLink")
    if "wazeLink" in payload:
        settings.waze_link = payload.get("wazeLink")
    settings.updated_at = now_utc()
    settings.updated_by = identity.get("user_id")

    nav_payload = payload.get("navettes") if isinstance(payload.get("navettes"), dict) else {}
    if "enabled" in nav_payload:
        navettes.enabled = bool(nav_payload.get("enabled"))
    if "address" in nav_payload:
        navettes.address = nav_payload.get("address")
    if "lastReturnTime" in nav_payload:
        navettes.last_return_time = nav_payload.get("lastReturnTime")
    if "notes" in nav_payload:
        navettes.notes = nav_payload.get("notes")
    navettes.updated_at = now_utc()
    navettes.updated_by = identity.get("user_id")

    db.add(settings)
    db.add(navettes)
    event = db.get(Event, event_id)
    response = _map_payload(event, settings, navettes)
    db.add(EventMapIdempotency(event_id=event_id, idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=identity.get("user_id"),
        actor_role=identity.get("role"),
        action="orga.map.settings.update",
        entity_type="event_map_settings",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=identity.get("bar_id"),
        payload={"message": "updated map settings", "event_id": event_id},
        idempotency_key=key,
    )
    db.commit()
    return response
