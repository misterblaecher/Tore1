from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.legacy.monolith import get_current_user
from app.deps.db import get_db
from app.models.event_cohosting import EventManagerSettings
from app.routers.forum import _active_membership, _can_view, _structure_or_404
from app.services.audit_service import write_audit_log
from app.services.structure_lifecycle import structure_is_published
from app.services.structure_rbac import capabilities_for_membership, require_capability
from app.services.storage_service import (
    ALLOWED_PURPOSES,
    build_storage_key,
    get_storage_backend,
    validate_upload,
)
from db import now_utc
from models import AppUser, Event, Organization, StoredFile, StructureAlbum, StructureDocument, StructureMedia


router = APIRouter(prefix="/forum", tags=["storage"])


class VisibilityIn(BaseModel):
    visibility: Literal["PRIVATE", "PUBLIC"]
    confirm_public: bool = Field(default=False)


def _payload(row: StoredFile) -> dict:
    return {
        "id": row.id,
        "ownerId": row.owner_user_id,
        "structureId": row.organization_id,
        "originalName": row.original_name,
        "mime": row.mime_type,
        "size": row.size_bytes,
        "storageKey": row.storage_key,
        "storageBackend": row.storage_backend,
        "visibility": row.visibility,
        "checksum": row.checksum_sha256,
        "purpose": row.purpose,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _file_for_structure(db: Session, *, organization_id: int, file_id: str) -> StoredFile:
    row = db.get(StoredFile, file_id)
    # Tenant mismatch is intentionally indistinguishable from a missing id.
    if row is None or row.deleted_at is not None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Stored file not found")
    return row


def _url_references_file(value: str | None, file_id: str) -> bool:
    path = (value or "").split("?", 1)[0].rstrip("/")
    return path.endswith(f"/files/{file_id}/content") or path.endswith(f"/public/files/{file_id}")


def _file_parents(db: Session, row: StoredFile) -> tuple[list[StructureDocument], list[StructureAlbum], list[StructureAlbum], list[Event]]:
    documents = [
        item for item in db.query(StructureDocument).filter(
            StructureDocument.organization_id == row.organization_id,
            StructureDocument.archived_at.is_(None),
        ).all()
        if _url_references_file(item.file_url, row.id)
    ]
    albums = db.query(StructureAlbum).filter(
        StructureAlbum.organization_id == row.organization_id,
        StructureAlbum.archived_at.is_(None),
    ).all()
    cover_albums = [item for item in albums if _url_references_file(item.cover_url, row.id)]
    media_album_ids = {
        item.album_id for item in db.query(StructureMedia).filter(
            StructureMedia.album_id.in_([album.id for album in albums] or [-1])
        ).all()
        if _url_references_file(item.media_url, row.id)
    }
    media_albums = [item for item in albums if item.id in media_album_ids]
    banner_event_ids = [item[0] for item in db.query(EventManagerSettings.event_id).filter(
        EventManagerSettings.banner_file_id == row.id
    ).all()]
    events = db.query(Event).filter(
        Event.id.in_(banner_event_ids or [-1]),
        Event.host_type == "orga",
        Event.host_id == str(row.organization_id),
    ).all()
    return documents, cover_albums, media_albums, events


def _audience_allowed(db: Session, visibility: str, membership) -> bool:
    level = (visibility or "STRUCTURE_MEMBERS").upper()
    capabilities = capabilities_for_membership(db, membership)
    if level in {"PUBLIC", "TORE_USERS"}:
        return True
    if level == "STRUCTURE_MEMBERS":
        return "structure.read" in capabilities
    if level == "TREASURY":
        return "finance.read" in capabilities
    if level == "OFFICE":
        return "member.manage" in capabilities or _can_view(level, membership)
    if level == "STAFF":
        return bool(capabilities & {
            "structure.edit", "member.manage", "discussion.manage", "event.manage",
            "document.manage", "album.manage", "page.manage", "finance.read",
        }) or _can_view(level, membership)
    if level == "ADMINS":
        return "member.role.manage" in capabilities and "audit.read" in capabilities
    return False


def _private_read_allowed(db: Session, row: StoredFile, user: AppUser) -> None:
    membership = _active_membership(db, row.organization_id, user.id)
    if membership is None:
        raise HTTPException(status_code=403, detail={"reason": "FILE_ACCESS_DENIED"})
    capabilities = capabilities_for_membership(db, membership)
    documents, cover_albums, media_albums, events = _file_parents(db, row)
    has_parent = bool(documents or cover_albums or media_albums or events)
    if any("document.read" in capabilities and _audience_allowed(db, item.visibility, membership) for item in documents):
        return
    if any(
        "album.read" in capabilities
        and _audience_allowed(db, item.visibility, membership)
        and ((item.status or "DRAFT").upper() != "DRAFT" or item.created_by_user_id == user.id or "album.manage" in capabilities)
        for item in [*cover_albums, *media_albums]
    ):
        return
    if events and "event.read" in capabilities:
        return
    if has_parent:
        raise HTTPException(status_code=403, detail={"reason": "FILE_PARENT_ACCESS_DENIED"})
    if row.owner_user_id == user.id:
        return
    required = {
        "DOCUMENT": "document.manage",
        "ALBUM_MEDIA": "album.manage",
        "BANNER": "structure.edit",
        "LOGO": "structure.edit",
        "IMAGE": "structure.edit",
    }.get((row.purpose or "DOCUMENT").upper(), "structure.edit")
    if required not in capabilities:
        raise HTTPException(status_code=403, detail={"reason": "FILE_ACCESS_DENIED", "capability": required})


def _public_read_allowed(db: Session, row: StoredFile) -> None:
    documents, cover_albums, media_albums, events = _file_parents(db, row)
    has_parent = bool(documents or cover_albums or media_albums or events)
    # Standalone branding/assets are governed by the StoredFile publication bit.
    # Once a file is attached to a resource, that parent's policy becomes authoritative.
    if not has_parent:
        return
    org = db.get(Organization, row.organization_id)
    if org is None or not structure_is_published(db, org):
        raise HTTPException(status_code=404, detail="Stored file not found")
    if any((item.visibility or "").upper() == "PUBLIC" for item in documents):
        return
    if any(
        (item.visibility or "").upper() == "PUBLIC" and (item.status or "DRAFT").upper() == "PUBLISHED"
        for item in [*cover_albums, *media_albums]
    ):
        return
    if any(
        (item.visibility or "").upper() == "PUBLIC" and (item.publication_status or "DRAFT").upper() == "PUBLISHED"
        for item in events
    ):
        return
    raise HTTPException(status_code=404, detail="Stored file not found")


def _secure_content_response(row: StoredFile, content: bytes, *, public: bool) -> Response:
    disposition = "inline" if row.mime_type.startswith("image/") or row.mime_type == "application/pdf" else "attachment"
    return Response(
        content=content,
        media_type=row.mime_type,
        headers={
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "public, max-age=300" if public else "private, no-store",
            "ETag": f'"sha256-{row.checksum_sha256}"',
        },
    )


@router.post("/structures/{slug}/files", status_code=201)
async def upload_structure_file(
    slug: str,
    file: UploadFile = File(...),
    purpose: str = Form("DOCUMENT"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    normalized_purpose = purpose.strip().upper()
    if normalized_purpose not in ALLOWED_PURPOSES:
        raise HTTPException(status_code=422, detail={"reason": "INVALID_FILE_PURPOSE"})
    manage_capability = {
        "DOCUMENT": "document.manage",
        "ALBUM_MEDIA": "album.manage",
        "IMAGE": "structure.edit",
        "LOGO": "structure.edit",
        "BANNER": "structure.edit",
    }[normalized_purpose]
    actor = require_capability(db, org.id, user, manage_capability)

    validated = await validate_upload(file)
    file_id = str(uuid.uuid4())
    visibility = "PRIVATE"
    storage = get_storage_backend()
    storage_key = build_storage_key(
        organization_id=org.id,
        file_id=file_id,
        visibility=visibility,
        mime_type=validated.mime_type,
    )
    storage.put(
        storage_key,
        validated.data,
        mime_type=validated.mime_type,
        checksum_sha256=validated.checksum_sha256,
    )

    row = StoredFile(
        id=file_id,
        owner_user_id=user.id,
        organization_id=org.id,
        original_name=validated.original_name,
        mime_type=validated.mime_type,
        size_bytes=validated.size_bytes,
        storage_key=storage_key,
        storage_backend=storage.name,
        visibility=visibility,
        checksum_sha256=validated.checksum_sha256,
        purpose=normalized_purpose,
    )
    db.add(row)
    try:
        db.flush()
        write_audit_log(
            db,
            actor_partner_id=None,
            actor_user_id=user.id,
            actor_role=actor.role,
            action="storage.file.upload",
            entity_type="stored_file",
            entity_id=row.id,
            event_id=None,
            committee_id=None,
            bar_id=None,
            payload={
                "structure_id": org.id,
                "mime": row.mime_type,
                "size": row.size_bytes,
                "visibility": row.visibility,
                "checksum": row.checksum_sha256,
                "purpose": row.purpose,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(storage_key)
        raise
    return _payload(row)


@router.get("/structures/{slug}/files/{file_id}")
def get_structure_file_metadata(
    slug: str,
    file_id: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    row = _file_for_structure(db, organization_id=org.id, file_id=file_id)
    _private_read_allowed(db, row, user)
    return _payload(row)


@router.get("/structures/{slug}/files/{file_id}/content")
def get_private_or_member_file_content(
    slug: str,
    file_id: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    row = _file_for_structure(db, organization_id=org.id, file_id=file_id)
    _private_read_allowed(db, row, user)
    content = get_storage_backend(row.storage_backend).read(row.storage_key)
    return _secure_content_response(row, content, public=False)


@router.get("/public/files/{file_id}")
def get_public_file_content(file_id: str, db: Session = Depends(get_db)):
    row = db.get(StoredFile, file_id)
    if row is None or row.deleted_at is not None or row.visibility != "PUBLIC":
        raise HTTPException(status_code=404, detail="Stored file not found")
    _public_read_allowed(db, row)
    content = get_storage_backend(row.storage_backend).read(row.storage_key)
    return _secure_content_response(row, content, public=True)


@router.patch("/structures/{slug}/files/{file_id}/visibility")
def set_structure_file_visibility(
    slug: str,
    file_id: str,
    payload: VisibilityIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    row = _file_for_structure(db, organization_id=org.id, file_id=file_id)
    target = payload.visibility.upper()
    capability = {
        "DOCUMENT": "document.publish" if target == "PUBLIC" else "document.manage",
        "ALBUM_MEDIA": "album.publish" if target == "PUBLIC" else "album.manage",
        "IMAGE": "structure.publish" if target == "PUBLIC" else "structure.edit",
        "LOGO": "structure.publish" if target == "PUBLIC" else "structure.edit",
        "BANNER": "structure.publish" if target == "PUBLIC" else "structure.edit",
    }.get((row.purpose or "DOCUMENT").upper(), "structure.publish" if target == "PUBLIC" else "structure.edit")
    actor = require_capability(db, org.id, user, capability)
    if target == "PUBLIC" and not payload.confirm_public:
        raise HTTPException(status_code=409, detail={"reason": "PUBLICATION_CONFIRMATION_REQUIRED"})
    if row.visibility == target:
        return _payload(row)

    storage = get_storage_backend(row.storage_backend)
    content = storage.read(row.storage_key)
    new_key = build_storage_key(
        organization_id=org.id,
        file_id=row.id,
        visibility=target,
        mime_type=row.mime_type,
    )
    storage.put(new_key, content, mime_type=row.mime_type, checksum_sha256=row.checksum_sha256)
    old_key = row.storage_key
    row.storage_key = new_key
    row.visibility = target
    row.updated_at = now_utc()
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=actor.role,
        action="storage.file.visibility",
        entity_type="stored_file",
        entity_id=row.id,
        event_id=None,
        committee_id=None,
        bar_id=None,
        payload={"structure_id": org.id, "visibility": target},
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(new_key)
        raise
    storage.delete(old_key)
    return _payload(row)


@router.delete("/structures/{slug}/files/{file_id}")
def delete_structure_file(
    slug: str,
    file_id: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    row = _file_for_structure(db, organization_id=org.id, file_id=file_id)
    membership = _active_membership(db, org.id, user.id)
    if membership is None:
        raise HTTPException(status_code=403, detail={"reason": "FILE_DELETE_DENIED"})
    capabilities = capabilities_for_membership(db, membership)
    manage_capability = {
        "DOCUMENT": "document.manage",
        "ALBUM_MEDIA": "album.manage",
        "IMAGE": "structure.edit",
        "LOGO": "structure.edit",
        "BANNER": "structure.edit",
    }.get((row.purpose or "DOCUMENT").upper(), "structure.edit")
    may_manage = manage_capability in capabilities
    if row.owner_user_id != user.id and not may_manage:
        raise HTTPException(status_code=403, detail={"reason": "FILE_DELETE_DENIED"})

    get_storage_backend(row.storage_backend).delete(row.storage_key)
    row.deleted_at = now_utc()
    row.updated_at = row.deleted_at
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role=membership.role if membership else None,
        action="storage.file.delete",
        entity_type="stored_file",
        entity_id=row.id,
        event_id=None,
        committee_id=None,
        bar_id=None,
        payload={"structure_id": org.id, "storage_key": row.storage_key},
    )
    db.commit()
    return {"ok": True, "id": row.id}
