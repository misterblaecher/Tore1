from __future__ import annotations

import io
import json
import re
import zipfile
from typing import Iterator, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.services.audit_service import write_audit_log
from app.services.authz_service import ensure_partner_role
from app.services.p3_common import decode_cursor, encode_cursor, ensure_event_action_allowed
from db import now_utc
from models import Bar, Event, Zone
from partner_auth import current_identity

router = APIRouter(tags=["zones"])


def get_db() -> Iterator[Session]:
    from app.legacy.monolith import get_db as _get_db

    yield from _get_db()


class ZoneOut(BaseModel):
    id: int
    bar_id: int
    event_id: Optional[int]
    name: str
    slug: str
    enabled: bool
    qr_payload: str
    created_at: str


class ZonePageOut(BaseModel):
    items: list[ZoneOut]
    next_cursor: Optional[str] = None


class ZoneCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=120)
    event_id: Optional[int] = None
    enabled: bool = True


class ZonePatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    enabled: Optional[bool] = None


class ZoneBulkIn(BaseModel):
    zone_ids: list[int] = Field(min_length=1)
    action: Literal["enable", "disable", "delete"]


class ZoneBulkOut(BaseModel):
    ok: bool
    updated: int
    action: str


def _slugify(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return s[:120] or "zone"


def _zone_qr_payload(zone: Zone) -> str:
    payload = f"tore://menu?bar_id={zone.bar_id}&zone_id={zone.id}"
    if zone.event_id is not None:
        payload += f"&event_id={zone.event_id}"
    return payload


def _ensure_zone_event_scope(db: Session, bar_id: int, event_id: Optional[int]) -> None:
    if event_id is None:
        return
    event = db.get(Event, event_id)
    if not event or event.bar_id != bar_id:
        raise HTTPException(404, "Event not found")
    ensure_event_action_allowed(db, event_id, "orders_enabled", write=True)


def _zone_out(zone: Zone) -> ZoneOut:
    return ZoneOut(
        id=zone.id,
        bar_id=zone.bar_id,
        event_id=zone.event_id,
        name=zone.name,
        slug=zone.slug,
        enabled=zone.enabled,
        qr_payload=_zone_qr_payload(zone),
        created_at=zone.created_at.isoformat(),
    )


@router.get("/bars/{bar_id}/zones", response_model=ZonePageOut)
def list_zones(
    bar_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[str] = None,
    q: Optional[str] = None,
    identity=Depends(current_identity),
    db: Session = Depends(get_db),
):
    if identity["bar_id"] != bar_id:
        raise HTTPException(403, {"reason": "forbidden", "message": "Forbidden"})
    ensure_partner_role(identity, {"manager", "bartender"})
    if not db.get(Bar, bar_id):
        raise HTTPException(404, "Bar not found")

    cursor_ts, cursor_id = decode_cursor(cursor)
    query = db.query(Zone).filter(Zone.bar_id == bar_id)
    if q and q.strip():
        needle = f"%{q.strip()}%"
        query = query.filter(or_(Zone.name.ilike(needle), Zone.slug.ilike(needle)))

    if cursor_ts and cursor_id:
        query = query.filter(or_(Zone.created_at < cursor_ts, and_(Zone.created_at == cursor_ts, Zone.id < cursor_id)))

    rows = query.order_by(Zone.created_at.desc(), Zone.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(last.created_at, last.id)

    return ZonePageOut(items=[_zone_out(row) for row in items], next_cursor=next_cursor)


@router.post("/bars/{bar_id}/zones", response_model=ZoneOut)
def create_zone(
    bar_id: int,
    payload: ZoneCreateIn,
    identity=Depends(current_identity),
    db: Session = Depends(get_db),
):
    if identity["bar_id"] != bar_id:
        raise HTTPException(403, {"reason": "forbidden", "message": "Forbidden"})
    ensure_partner_role(identity, {"manager", "bartender"})
    if identity["role"] not in {"manager", "bartender"}:
        raise HTTPException(403, "Forbidden")
    if not db.get(Bar, bar_id):
        raise HTTPException(404, "Bar not found")

    _ensure_zone_event_scope(db, bar_id, payload.event_id)

    base_slug = _slugify(payload.slug or payload.name)
    slug = base_slug
    idx = 2
    while db.query(Zone).filter(Zone.bar_id == bar_id, Zone.slug == slug).first():
        slug = f"{base_slug}-{idx}"
        idx += 1

    zone = Zone(
        bar_id=bar_id,
        event_id=payload.event_id,
        name=payload.name.strip(),
        slug=slug,
        enabled=payload.enabled,
    )
    db.add(zone)
    db.flush()

    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="zones.create",
        entity_type="zone",
        entity_id=str(zone.id),
        event_id=zone.event_id,
        bar_id=bar_id,
        payload={"name": zone.name, "slug": zone.slug, "enabled": zone.enabled},
    )
    db.commit()
    db.refresh(zone)
    return _zone_out(zone)


@router.patch("/zones/{zone_id}", response_model=ZoneOut)
def patch_zone(
    zone_id: int,
    payload: ZonePatchIn,
    identity=Depends(current_identity),
    db: Session = Depends(get_db),
):
    zone = db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(404, "Zone not found")
    if zone.bar_id != identity["bar_id"]:
        raise HTTPException(403, {"reason": "forbidden", "message": "Forbidden"})
    ensure_partner_role(identity, {"manager", "bartender"})

    _ensure_zone_event_scope(db, zone.bar_id, zone.event_id)

    before = {"name": zone.name, "enabled": zone.enabled}
    if payload.name is not None:
        zone.name = payload.name.strip()
    if payload.enabled is not None:
        zone.enabled = bool(payload.enabled)
    db.add(zone)

    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="zones.update",
        entity_type="zone",
        entity_id=str(zone.id),
        event_id=zone.event_id,
        bar_id=zone.bar_id,
        payload={"before": before, "after": {"name": zone.name, "enabled": zone.enabled}},
    )

    db.commit()
    db.refresh(zone)
    return _zone_out(zone)


@router.post("/bars/{bar_id}/zones/bulk", response_model=ZoneBulkOut)
def bulk_zones(
    bar_id: int,
    payload: ZoneBulkIn,
    identity=Depends(current_identity),
    db: Session = Depends(get_db),
):
    if identity["bar_id"] != bar_id:
        raise HTTPException(403, "Forbidden")

    rows = (
        db.query(Zone)
        .filter(Zone.bar_id == bar_id, Zone.id.in_(payload.zone_ids))
        .order_by(Zone.id.asc())
        .all()
    )
    if not rows:
        return ZoneBulkOut(ok=True, updated=0, action=payload.action)

    for row in rows:
        _ensure_zone_event_scope(db, bar_id, row.event_id)

    if payload.action == "enable":
        for row in rows:
            row.enabled = True
            db.add(row)
    elif payload.action == "disable":
        for row in rows:
            row.enabled = False
            db.add(row)
    else:
        for row in rows:
            db.delete(row)

    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="zones.bulk",
        entity_type="zone",
        entity_id=None,
        event_id=None,
        bar_id=bar_id,
        payload={"action": payload.action, "zone_ids": [r.id for r in rows], "count": len(rows)},
    )
    db.commit()
    return ZoneBulkOut(ok=True, updated=len(rows), action=payload.action)


@router.post("/bars/{bar_id}/zones/export_pack")
def export_zone_pack(
    bar_id: int,
    format: Literal["zip", "pdf"] = Query(default="zip"),
    event_id: Optional[int] = Query(default=None),
    identity=Depends(current_identity),
    db: Session = Depends(get_db),
):
    if identity["bar_id"] != bar_id:
        raise HTTPException(403, "Forbidden")

    query = db.query(Zone).filter(Zone.bar_id == bar_id)
    if event_id is not None:
        query = query.filter(Zone.event_id == event_id)
    rows = query.order_by(Zone.created_at.asc(), Zone.id.asc()).all()

    if format == "pdf":
        # Lightweight fallback: returns PDF-like payload without heavy deps.
        content = ["TORÈ ZONES PACK", ""]
        for row in rows:
            content.append(f"[{row.id}] {row.name} ({'ON' if row.enabled else 'OFF'})")
            content.append(_zone_qr_payload(row))
            content.append("")
        body = "\n".join(content).encode("utf-8")
        stream = io.BytesIO(body)
        media = "application/pdf"
        filename = f"zones_pack_bar_{bar_id}.pdf"
    else:
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            manifest = []
            for row in rows:
                payload = _zone_qr_payload(row)
                safe = _slugify(row.slug)
                svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='900' height='500'>
  <rect width='100%' height='100%' fill='white' stroke='black'/>
  <text x='20' y='70' font-size='42' font-family='monospace'>TORÈ — {row.name}</text>
  <text x='20' y='130' font-size='28' font-family='monospace'>Zone #{row.id} / {row.slug}</text>
  <text x='20' y='190' font-size='20' font-family='monospace'>{payload}</text>
  <text x='20' y='230' font-size='16' font-family='monospace'>Status: {'ENABLED' if row.enabled else 'DISABLED'}</text>
</svg>
"""
                zf.writestr(f"stickers/{row.id:04d}_{safe}.svg", svg)
                manifest.append({"id": row.id, "name": row.name, "slug": row.slug, "enabled": row.enabled, "qr_payload": payload})
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        mem.seek(0)
        stream = mem
        media = "application/zip"
        filename = f"zones_pack_bar_{bar_id}.zip"

    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="zones.export",
        entity_type="zone",
        entity_id=None,
        event_id=event_id,
        bar_id=bar_id,
        payload={"format": format, "count": len(rows)},
    )
    db.commit()

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(stream, media_type=media, headers=headers)
