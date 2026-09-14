from __future__ import annotations

"""Private object-storage abstraction for Forum files.

The local driver is intentionally a development driver.  It never returns a
public permanent URL: clients download through an authorized API endpoint.
S3/R2 can implement the same interface with short-lived signed URLs later.
"""

import hashlib
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from fastapi import HTTPException, UploadFile


MAX_FILE_SIZE = int(os.getenv("FORUM_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
ALLOWED_MIME_PREFIXES = ("image/", "text/")
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/json",
    "application/zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


@dataclass(frozen=True)
class StoredObject:
    storage_key: str
    size_bytes: int
    checksum_sha256: str
    mime_type: str
    original_name: str


class StorageService(Protocol):
    async def save_upload(self, *, organization_id: int, namespace: str, upload: UploadFile) -> StoredObject: ...
    def local_path(self, storage_key: str) -> Path: ...
    def delete(self, storage_key: str) -> None: ...


def validate_mime(mime_type: str) -> None:
    normalized = (mime_type or "application/octet-stream").lower().strip()
    if normalized in ALLOWED_MIME_TYPES or any(normalized.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES):
        return
    raise HTTPException(status_code=422, detail={"reason": "FILE_TYPE_NOT_ALLOWED", "mimeType": normalized})


class LocalPrivateStorage:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or os.getenv("FORUM_STORAGE_ROOT") or Path(__file__).resolve().parents[2] / "data" / "forum_storage").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        env = (os.getenv("TORE_ENV") or os.getenv("ENV") or "DEV").strip().upper()
        if env in {"PROD", "PRODUCTION"} and (os.getenv("FORUM_STORAGE_DRIVER") or "local").lower() == "local":
            raise RuntimeError("FORUM_STORAGE_DRIVER=local is forbidden in production; configure S3/R2-compatible private storage")

    def _safe_path(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        if self.root not in candidate.parents:
            raise HTTPException(status_code=400, detail={"reason": "INVALID_STORAGE_KEY"})
        return candidate

    async def save_upload(self, *, organization_id: int, namespace: str, upload: UploadFile) -> StoredObject:
        mime = (upload.content_type or "application/octet-stream").lower()
        validate_mime(mime)
        original = (upload.filename or "file").replace("/", "_").replace("\\", "_")[:255]
        token = secrets.token_urlsafe(24)
        storage_key = f"structures/{organization_id}/{namespace}/{token}"
        path = self._safe_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        total = 0
        try:
            with path.open("wb") as handle:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_FILE_SIZE:
                        raise HTTPException(status_code=413, detail={"reason": "FILE_TOO_LARGE", "maxBytes": MAX_FILE_SIZE})
                    digest.update(chunk)
                    handle.write(chunk)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()
        return StoredObject(
            storage_key=storage_key,
            size_bytes=total,
            checksum_sha256=digest.hexdigest(),
            mime_type=mime,
            original_name=original,
        )

    def local_path(self, storage_key: str) -> Path:
        path = self._safe_path(storage_key)
        if not path.is_file():
            raise HTTPException(status_code=404, detail={"reason": "FILE_NOT_FOUND"})
        return path

    def delete(self, storage_key: str) -> None:
        self._safe_path(storage_key).unlink(missing_ok=True)


def get_forum_storage() -> LocalPrivateStorage:
    driver = (os.getenv("FORUM_STORAGE_DRIVER") or "local").lower().strip()
    if driver != "local":
        raise RuntimeError(
            f"FORUM_STORAGE_DRIVER={driver!r} is configured but the deployment adapter is not installed. "
            "Implement the StorageService protocol for S3/R2 and keep buckets private."
        )
    return LocalPrivateStorage()
