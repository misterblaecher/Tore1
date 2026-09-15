from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.legacy.monolith import get_current_user, get_db
from app.routers.forum import ROLE_RANK, _active_membership, _require_role, _structure_or_404
from app.services.audit_service import write_audit_log
from app.services.storage_service import (
    ALLOWED_PURPOSES,
    build_storage_key,
    get_storage_backend,
    validate_upload,
)
from db import now_utc
from models import AppUser, StoredFile


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


def _private_read_allowed(db: Session, row: StoredFile, user: AppUser) -> None:
    if row.visibility == "PUBLIC":
        return
    if _active_membership(db, row.organization_id, user.id) is None:
        raise HTTPException(status_code=403, detail={"reason": "FILE_ACCESS_DENIED"})


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
    actor = _require_role(db, org.id, user, "STAFF")
    normalized_purpose = purpose.strip().upper()
    if normalized_purpose not in ALLOWED_PURPOSES:
        raise HTTPException(status_code=422, detail={"reason": "INVALID_FILE_PURPOSE"})

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
    actor = _require_role(db, org.id, user, "MANAGER")
    row = _file_for_structure(db, organization_id=org.id, file_id=file_id)
    target = payload.visibility.upper()
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
    membership = _active_membership(db, org.id, user.id)
    row = _file_for_structure(db, organization_id=org.id, file_id=file_id)
    if membership is None:
        raise HTTPException(status_code=403, detail={"reason": "FILE_DELETE_DENIED"})
    role_rank = ROLE_RANK.get((membership.role or "MEMBER").upper(), 0)
    may_manage = role_rank >= ROLE_RANK["MANAGER"]
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
