from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.legacy.monolith import get_current_user, get_db
from app.routers.forum import _structure_or_404
from app.services.audit_service import write_audit_log
from app.services.event_cohosting_service import (
    COHOST_PERMISSION_FIELDS, ROLE_RANK, active_structure_membership,
    effective_permission, ensure_owner_relation, migrate_legacy_cohosts_for_event,
    relation_permissions, require_structure_event_relation,
)
from app.services.event_staff_invitation_service import create_secure_event_invitation
from app.services.idempotency_service import ensure_idempotency_key
from db import now_utc
from models import (
    AppUser, Event, EventCost, EventManagerSettings, EventStaff, EventStaffInviteCode,
    EventStructure, Order, Organization, StoredFile, StructureAlbum, StructureDocument,
)

router = APIRouter(prefix="/forum", tags=["event-manager"])


class TariffIn(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    price_cents: int = Field(ge=0, le=1_000_000)
    description: Optional[str] = Field(default=None, max_length=280)


class EventManagerCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=10_000)
    starts_at: datetime
    ends_at: datetime
    venue: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    capacity: Optional[int] = Field(default=None, ge=1, le=1_000_000)
    entry_price_cents: int = Field(default=0, ge=0, le=1_000_000)
    tariffs: list[TariffIn] = Field(default_factory=list, max_length=50)
    modules_on: dict[str, bool] = Field(default_factory=dict)
    visibility: Literal["PUBLIC", "PRIVATE"] = "PRIVATE"
    publication_status: Literal["DRAFT", "PUBLISHED"] = "DRAFT"
    banner_file_id: Optional[str] = None


class EventManagerPatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=10_000)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    venue: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    capacity: Optional[int] = Field(default=None, ge=1, le=1_000_000)
    entry_price_cents: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    tariffs: Optional[list[TariffIn]] = Field(default=None, max_length=50)
    modules_on: Optional[dict[str, bool]] = None
    visibility: Optional[Literal["PUBLIC", "PRIVATE"]] = None
    publication_status: Optional[Literal["DRAFT", "PUBLISHED"]] = None
    banner_file_id: Optional[str] = None
    clear_banner: bool = False


class CohostPermissionsIn(BaseModel):
    edit: bool = False
    publish: bool = False
    staff: bool = False
    documents: bool = False
    finance: bool = False
    recap: bool = False


class CohostCreateIn(BaseModel):
    structure_id: int
    permissions: CohostPermissionsIn = Field(default_factory=CohostPermissionsIn)


class CohostPatchIn(BaseModel):
    permissions: CohostPermissionsIn


class EventDocumentCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=5000)
    file_id: str = Field(min_length=8, max_length=64)
    visibility: str = Field(default="STRUCTURE_MEMBERS", pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")


class EventAlbumCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=5000)
    visibility: str = Field(default="STRUCTURE_MEMBERS", pattern="^(PUBLIC|TORE_USERS|STRUCTURE_MEMBERS|STAFF|OFFICE|TREASURY|ADMINS)$")


class StaffInviteIn(BaseModel):
    target_user_id: str = Field(min_length=1, max_length=120)
    role: Literal["ENTRY", "HELPER", "MANAGER", "BAR"] = "HELPER"
    expires_in_hours: int = Field(default=12, ge=1, le=168)


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo else value


def _settings(db: Session, event_id: int) -> EventManagerSettings:
    row = db.get(EventManagerSettings, event_id)
    if row is None:
        row = EventManagerSettings(event_id=event_id, pricing_json=[], updated_at=now_utc())
        db.add(row); db.flush()
    return row


def _rank(membership) -> int:
    return ROLE_RANK.get((membership.role or "MEMBER").upper(), 0)


def _owner_guard(db: Session, org: Organization, event: Event, user: AppUser):
    relation = ensure_owner_relation(db, event, created_by_user_id=user.id)
    member = active_structure_membership(db, organization_id=org.id, user_id=user.id)
    if relation is None or relation.organization_id != org.id or relation.role != "OWNER" or member is None or _rank(member) < ROLE_RANK["MANAGER"]:
        raise HTTPException(403, detail={"reason": "EVENT_OWNER_REQUIRED"})
    return relation, member


def _relation(db: Session, row: EventStructure) -> dict:
    org = db.get(Organization, row.organization_id)
    return {
        "id": row.id, "role": (row.role or "COHOST").upper(),
        "permissions": relation_permissions(row),
        "structure": {"id": row.organization_id, "slug": org.slug if org else None, "name": org.name if org else f"Structure #{row.organization_id}", "type": (org.org_type or "OTHER").upper() if org else "OTHER", "city": org.city if org else None},
    }


def _finance(db: Session, event_id: int) -> dict:
    revenue = int(db.scalar(select(func.coalesce(func.sum(Order.total_cents), 0)).where(Order.event_id == event_id)) or 0)
    costs = int(db.scalar(select(func.coalesce(func.sum(EventCost.amount_cents), 0)).where(EventCost.event_id == event_id)) or 0)
    return {"revenueCents": revenue, "costsCents": costs, "resultCents": revenue - costs}


def _payload(db: Session, event: Event, link: EventStructure, member, resources: bool = True) -> dict:
    settings = _settings(db, event.id)
    perms = {"read": effective_permission(link, member, "read"), **{name: effective_permission(link, member, name) for name in COHOST_PERMISSION_FIELDS}}
    links = db.query(EventStructure).filter(EventStructure.event_id == event.id).all()
    org_ids = [row.organization_id for row in links]
    banner = db.get(StoredFile, settings.banner_file_id) if settings.banner_file_id else None
    staff = None
    if resources and perms["staff"]:
        staff_rows = db.query(EventStaff, AppUser).outerjoin(AppUser, AppUser.id == EventStaff.user_id).filter(EventStaff.event_id == event.id).all()
        invites = db.query(EventStaffInviteCode).filter(EventStaffInviteCode.event_id == event.id, EventStaffInviteCode.token_hash.is_not(None)).all()
        staff = {"items": [{"userId": row.user_id, "displayName": user.display_name if user else None, "role": (row.role or "helper").upper(), "status": "REVOKED" if row.revoked_at else "ACTIVE"} for row, user in staff_rows], "invitations": [{"id": row.id, "targetUserId": row.target_user_id, "role": (row.role or "HELPER").upper(), "status": row.status} for row in invites]}
    documents = None
    if resources and perms["documents"]:
        rows = db.query(StructureDocument).filter(StructureDocument.event_id == event.id, StructureDocument.archived_at.is_(None), StructureDocument.organization_id.in_(org_ids or [-1])).all()
        documents = [{"id": row.id, "title": row.title, "fileUrl": row.file_url, "visibility": row.visibility, "structureId": row.organization_id} for row in rows if perms["finance"] or (row.visibility or "").upper() not in {"TREASURY", "ADMINS"}]
    albums = None
    if resources and perms["recap"]:
        rows = db.query(StructureAlbum).filter(StructureAlbum.event_id == event.id, StructureAlbum.organization_id.in_(org_ids or [-1])).all()
        albums = [{"id": row.id, "title": row.title, "status": row.status, "visibility": row.visibility, "structureId": row.organization_id} for row in rows]
    return {
        "id": event.id, "name": event.name, "description": event.public_description,
        "startsAt": event.starts_at.isoformat() if event.starts_at else None, "endsAt": event.ends_at.isoformat() if event.ends_at else None,
        "venue": event.venue, "city": event.city, "capacity": event.capacity, "entryPriceCents": event.entry_price_cents,
        "tariffs": list(settings.pricing_json or []),
        "banner": ({"fileId": banner.id, "name": banner.original_name, "mime": banner.mime_type, "size": banner.size_bytes, "visibility": banner.visibility, "structureId": banner.organization_id} if banner and banner.deleted_at is None else None),
        "modulesOn": dict(event.modules_on or {}), "visibility": (event.visibility or "PRIVATE").upper(),
        "publicationStatus": (event.publication_status or "DRAFT").upper(), "eventState": (event.event_state or "DRAFT").upper(),
        "relation": _relation(db, link), "effectivePermissions": perms,
        "owner": next((_relation(db, row) for row in links if row.role == "OWNER"), None),
        "cohosts": [_relation(db, row) for row in links if row.role == "COHOST"],
        "staff": staff, "documents": documents, "albums": albums,
        "finance": _finance(db, event.id) if resources and perms["finance"] else None, "canReadFinance": bool(perms["finance"]),
    }


def _banner_guard(db: Session, file_id: str, org_ids: set[int]):
    row = db.get(StoredFile, file_id)
    if row is None or row.deleted_at is not None or row.organization_id not in org_ids or not row.mime_type.startswith("image/") or (row.purpose or "").upper() not in {"BANNER", "IMAGE"}:
        raise HTTPException(400, detail={"reason": "INVALID_EVENT_BANNER_FILE"})


@router.get("/structures/{slug}/event-manager")
def list_managed_events(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    member = active_structure_membership(db, organization_id=org.id, user_id=user.id)
    if member is None: raise HTTPException(403, detail={"reason": "FORUM_PERMISSION_DENIED"})
    for event in db.query(Event).filter(Event.host_type == "orga", Event.host_id == str(org.id)).all(): migrate_legacy_cohosts_for_event(db, event)
    items = []
    for link in db.query(EventStructure).filter(EventStructure.organization_id == org.id).all():
        event = db.get(Event, link.event_id)
        if event and effective_permission(link, member, "read"): items.append(_payload(db, event, link, member, False))
    db.commit(); items.sort(key=lambda item: (item.get("startsAt") or "", item["id"]))
    return {"items": items}


@router.post("/structures/{slug}/event-manager", status_code=201)
def create_managed_event(slug: str, payload: EventManagerCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); member = active_structure_membership(db, organization_id=org.id, user_id=user.id)
    if member is None or _rank(member) < ROLE_RANK["MANAGER"]: raise HTTPException(403, detail={"reason": "FORUM_PERMISSION_DENIED"})
    start, end = _naive(payload.starts_at), _naive(payload.ends_at)
    if end <= start: raise HTTPException(400, detail={"reason": "INVALID_EVENT_DATES"})
    event = Event(host_type="orga", host_id=str(org.id), host_display_name=org.name, name=payload.name.strip(), public_description=payload.description, starts_at=start, ends_at=end, venue=payload.venue, city=payload.city or org.city, capacity=payload.capacity, entry_price_cents=payload.entry_price_cents, modules_on=dict(payload.modules_on), visibility=payload.visibility, publication_status=payload.publication_status, event_state="DRAFT", created_by=f"app:{user.id}", last_state_updated_at=now_utc(), last_updated_at=now_utc())
    db.add(event); db.flush(); link = ensure_owner_relation(db, event, created_by_user_id=user.id); settings = _settings(db, event.id)
    settings.pricing_json = [row.model_dump() for row in payload.tariffs]; settings.updated_by_user_id = user.id
    if payload.banner_file_id: _banner_guard(db, payload.banner_file_id, {org.id}); settings.banner_file_id = payload.banner_file_id
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=member.role, action="event.manager.create", entity_type="event", entity_id=str(event.id), event_id=event.id, committee_id=None, bar_id=event.bar_id, payload={"structure_id": org.id})
    db.commit(); return _payload(db, event, link, member)


@router.get("/structures/{slug}/cohost-structure-search")
def search_structures(slug: str, q: str = Query(min_length=1, max_length=120), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); member = active_structure_membership(db, organization_id=org.id, user_id=user.id)
    if member is None or _rank(member) < ROLE_RANK["MANAGER"]: raise HTTPException(403, detail={"reason": "FORUM_PERMISSION_DENIED"})
    needle = f"%{q.strip().lower()}%"
    rows = db.query(Organization).filter(Organization.id != org.id, or_(func.lower(Organization.name).like(needle), func.lower(Organization.slug).like(needle), func.lower(func.coalesce(Organization.city, "")).like(needle))).order_by(Organization.name).limit(12).all()
    return {"items": [{"id": row.id, "slug": row.slug, "name": row.name, "type": (row.org_type or "OTHER").upper(), "city": row.city} for row in rows]}


@router.get("/structures/{slug}/event-manager/{event_id}")
def get_managed_event(slug: str, event_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); event, link, member = require_structure_event_relation(db, organization_id=org.id, event_id=event_id, user=user, permission="read")
    db.commit(); return _payload(db, event, link, member)


@router.patch("/structures/{slug}/event-manager/{event_id}")
def patch_managed_event(slug: str, event_id: int, payload: EventManagerPatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); event, link, member = require_structure_event_relation(db, organization_id=org.id, event_id=event_id, user=user, permission="read"); data = payload.model_dump(exclude_unset=True)
    if set(data) - {"publication_status"} and not effective_permission(link, member, "edit"): raise HTTPException(403, detail={"reason": "EVENT_COHOST_PERMISSION_DENIED", "permission": "edit"})
    if "publication_status" in data and not effective_permission(link, member, "publish"): raise HTTPException(403, detail={"reason": "EVENT_COHOST_PERMISSION_DENIED", "permission": "publish"})
    mapping = {"name": "name", "description": "public_description", "venue": "venue", "city": "city", "capacity": "capacity", "entry_price_cents": "entry_price_cents", "modules_on": "modules_on", "visibility": "visibility", "publication_status": "publication_status"}
    for key, attr in mapping.items():
        if key in data: setattr(event, attr, data[key].strip() if key == "name" and data[key] else data[key])
    if "starts_at" in data: event.starts_at = _naive(payload.starts_at)
    if "ends_at" in data: event.ends_at = _naive(payload.ends_at)
    if event.ends_at <= event.starts_at: raise HTTPException(400, detail={"reason": "INVALID_EVENT_DATES"})
    settings = _settings(db, event.id)
    if payload.tariffs is not None: settings.pricing_json = [row.model_dump() for row in payload.tariffs]
    if payload.clear_banner: settings.banner_file_id = None
    elif payload.banner_file_id is not None:
        org_ids = {row.organization_id for row in db.query(EventStructure).filter(EventStructure.event_id == event.id).all()}; _banner_guard(db, payload.banner_file_id, org_ids); settings.banner_file_id = payload.banner_file_id
    settings.updated_by_user_id = user.id; settings.updated_at = now_utc(); event.last_updated_at = now_utc()
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=member.role, action="event.manager.publish" if "publication_status" in data else "event.manager.update", entity_type="event", entity_id=str(event.id), event_id=event.id, committee_id=None, bar_id=event.bar_id, payload={"structure_id": org.id, "fields": sorted(data)})
    db.commit(); return _payload(db, event, link, member)


@router.get("/structures/{slug}/event-manager/{event_id}/preview")
def preview_event(slug: str, event_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); event, link, member = require_structure_event_relation(db, organization_id=org.id, event_id=event_id, user=user, permission="read"); data = _payload(db, event, link, member, False)
    return {"preview": True, "event": {key: data[key] for key in ("id", "name", "description", "startsAt", "endsAt", "venue", "city", "capacity", "entryPriceCents", "tariffs", "banner", "modulesOn", "visibility", "publicationStatus", "eventState")}, "organizers": [data["owner"], *data["cohosts"]]}


@router.post("/structures/{slug}/event-manager/{event_id}/cohosts", status_code=201)
def add_cohost(slug: str, event_id: int, payload: CohostCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); event = db.get(Event, event_id)
    if event is None: raise HTTPException(404, "Event not found")
    _, member = _owner_guard(db, org, event, user); target = db.get(Organization, payload.structure_id)
    if target is None: raise HTTPException(404, "Structure not found")
    if target.id == org.id: raise HTTPException(400, detail={"reason": "OWNER_CANNOT_BE_COHOST"})
    if db.query(EventStructure).filter(EventStructure.event_id == event_id, EventStructure.organization_id == target.id).first(): raise HTTPException(409, detail={"reason": "EVENT_STRUCTURE_ALREADY_LINKED"})
    values = payload.permissions.model_dump(); row = EventStructure(event_id=event_id, organization_id=target.id, role="COHOST", created_by_user_id=user.id, created_at=now_utc(), updated_at=now_utc(), **{field: values[name] for name, field in COHOST_PERMISSION_FIELDS.items()}); db.add(row); db.flush()
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=member.role, action="event.cohost.add", entity_type="event_structure", entity_id=str(row.id), event_id=event.id, committee_id=None, bar_id=event.bar_id, payload={"structure_id": org.id, "cohost_structure_id": target.id, "permissions": values}); db.commit(); return _relation(db, row)


@router.patch("/structures/{slug}/event-manager/{event_id}/cohosts/{structure_id}")
def patch_cohost(slug: str, event_id: int, structure_id: int, payload: CohostPatchIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); event = db.get(Event, event_id)
    if event is None: raise HTTPException(404, "Event not found")
    _, member = _owner_guard(db, org, event, user); row = db.query(EventStructure).filter(EventStructure.event_id == event_id, EventStructure.organization_id == structure_id, EventStructure.role == "COHOST").first()
    if row is None: raise HTTPException(404, "Cohost not found")
    before = relation_permissions(row); values = payload.permissions.model_dump()
    for name, field in COHOST_PERMISSION_FIELDS.items(): setattr(row, field, values[name])
    row.updated_at = now_utc(); write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=member.role, action="event.cohost.permissions", entity_type="event_structure", entity_id=str(row.id), event_id=event.id, committee_id=None, bar_id=event.bar_id, payload={"structure_id": org.id, "cohost_structure_id": structure_id, "before": before, "after": values}); db.commit(); return _relation(db, row)


@router.delete("/structures/{slug}/event-manager/{event_id}/cohosts/{structure_id}")
def remove_cohost(slug: str, event_id: int, structure_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); event = db.get(Event, event_id)
    if event is None: raise HTTPException(404, "Event not found")
    _, member = _owner_guard(db, org, event, user); row = db.query(EventStructure).filter(EventStructure.event_id == event_id, EventStructure.organization_id == structure_id, EventStructure.role == "COHOST").first()
    if row is None: raise HTTPException(404, "Cohost not found")
    row_id = row.id; db.delete(row); write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=member.role, action="event.cohost.remove", entity_type="event_structure", entity_id=str(row_id), event_id=event.id, committee_id=None, bar_id=event.bar_id, payload={"structure_id": org.id, "cohost_structure_id": structure_id}); db.commit(); return {"ok": True}


@router.get("/structures/{slug}/event-manager/{event_id}/finance")
def get_finance(slug: str, event_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); event, _, _ = require_structure_event_relation(db, organization_id=org.id, event_id=event_id, user=user, permission="finance"); return {"eventId": event.id, "canReadFinance": True, **_finance(db, event.id)}


@router.post("/structures/{slug}/event-manager/{event_id}/documents", status_code=201)
def add_document(slug: str, event_id: int, payload: EventDocumentCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); event, _, member = require_structure_event_relation(db, organization_id=org.id, event_id=event_id, user=user, permission="documents"); stored = db.get(StoredFile, payload.file_id)
    if stored is None or stored.deleted_at is not None or stored.organization_id != org.id: raise HTTPException(400, detail={"reason": "INVALID_EVENT_DOCUMENT_FILE"})
    row = StructureDocument(organization_id=org.id, title=payload.title.strip(), description=payload.description, file_url=f"/forum/structures/{org.slug}/files/{stored.id}/content", visibility=payload.visibility, uploaded_by_user_id=user.id, event_id=event.id, created_at=now_utc(), updated_at=now_utc()); db.add(row); db.flush()
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=member.role, action="event.manager.document.add", entity_type="structure_document", entity_id=str(row.id), event_id=event.id, committee_id=None, bar_id=event.bar_id, payload={"structure_id": org.id, "file_id": stored.id}); db.commit(); return {"id": row.id, "title": row.title, "fileUrl": row.file_url, "visibility": row.visibility, "structureId": org.id}


@router.post("/structures/{slug}/event-manager/{event_id}/albums", status_code=201)
def add_album(slug: str, event_id: int, payload: EventAlbumCreateIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); event, _, member = require_structure_event_relation(db, organization_id=org.id, event_id=event_id, user=user, permission="recap")
    row = StructureAlbum(organization_id=org.id, title=payload.title.strip(), description=payload.description, visibility=payload.visibility, status="DRAFT", created_by_user_id=user.id, event_id=event.id, created_at=now_utc(), updated_at=now_utc()); db.add(row); db.flush()
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=member.role, action="event.manager.album.create", entity_type="structure_album", entity_id=str(row.id), event_id=event.id, committee_id=None, bar_id=event.bar_id, payload={"structure_id": org.id}); db.commit(); return {"id": row.id, "title": row.title, "status": row.status, "visibility": row.visibility, "structureId": org.id}


@router.post("/structures/{slug}/event-manager/{event_id}/staff-invitations", status_code=201)
def invite_staff(slug: str, event_id: int, payload: StaffInviteIn, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); require_structure_event_relation(db, organization_id=org.id, event_id=event_id, user=user, permission="staff")
    return create_secure_event_invitation(db, actor=user, event_id=event_id, target_user_id=payload.target_user_id, role=payload.role, expires_in_hours=payload.expires_in_hours, idempotency_key=ensure_idempotency_key(idempotency_key))
