from __future__ import annotations

import hashlib
import io
import os
import re
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fastapi import HTTPException, UploadFile


DEFAULT_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024

MIME_EXTENSIONS: dict[str, set[str]] = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/gif": {".gif"},
    "image/webp": {".webp"},
    "application/pdf": {".pdf"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {".xlsx"},
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": {".pptx"},
}

CANONICAL_EXTENSION = {mime: sorted(exts)[0] for mime, exts in MIME_EXTENSIONS.items()}
ALLOWED_PURPOSES = {"IMAGE", "DOCUMENT", "LOGO", "BANNER", "ALBUM_MEDIA"}


@dataclass(frozen=True)
class ValidatedUpload:
    data: bytes
    original_name: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str


class StorageBackend(Protocol):
    name: str

    def put(self, key: str, data: bytes, *, mime_type: str, checksum_sha256: str) -> None: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStorageBackend:
    name = "local"

    def __init__(self, root: str | Path | None = None):
        configured = root or os.getenv("TORE_UPLOAD_LOCAL_ROOT") or "data/uploads"
        self.root = Path(configured).expanduser().resolve()

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise RuntimeError("Unsafe storage key") from exc
        return candidate

    def put(self, key: str, data: bytes, *, mime_type: str, checksum_sha256: str) -> None:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        with open(tmp, "xb") as handle:
            handle.write(data)
        os.chmod(tmp, 0o600)
        os.replace(tmp, target)
        os.chmod(target, 0o600)

    def read(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Stored file content not found") from exc

    def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            path.unlink()
        except FileNotFoundError:
            return
        parent = path.parent
        while parent != self.root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent


class S3StorageBackend:
    name = "s3"

    def __init__(self):
        bucket = (os.getenv("TORE_STORAGE_BUCKET") or "").strip()
        if not bucket:
            raise RuntimeError("TORE_STORAGE_BUCKET is required when TORE_STORAGE_BACKEND=s3")
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - deployment/config failure
            raise RuntimeError("boto3 is required for the S3 storage backend") from exc

        self.bucket = bucket
        kwargs: dict[str, str] = {}
        endpoint = (os.getenv("TORE_STORAGE_S3_ENDPOINT") or "").strip()
        region = (os.getenv("TORE_STORAGE_S3_REGION") or "").strip()
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        if region:
            kwargs["region_name"] = region
        self.client = boto3.client("s3", **kwargs)

    def put(self, key: str, data: bytes, *, mime_type: str, checksum_sha256: str) -> None:
        params = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": data,
            "ContentType": mime_type,
            "ContentDisposition": "attachment",
            "Metadata": {"sha256": checksum_sha256},
        }
        sse = (os.getenv("TORE_STORAGE_S3_SSE") or "AES256").strip()
        if sse:
            params["ServerSideEncryption"] = sse
        self.client.put_object(**params)

    def read(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except Exception as exc:  # pragma: no cover - provider-specific
            code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
            if code in {"NoSuchKey", "NotFound", "404"}:
                raise HTTPException(status_code=404, detail="Stored file content not found") from exc
            raise

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def get_storage_backend(backend_name: str | None = None) -> StorageBackend:
    env_name = (os.getenv("TORE_ENV") or os.getenv("ENV") or "DEV").strip().upper()
    configured = backend_name or os.getenv("TORE_STORAGE_BACKEND")
    if configured:
        backend = configured.strip().lower()
    else:
        backend = "s3" if env_name in {"PROD", "PRODUCTION"} else "local"
    if backend == "local":
        if env_name in {"PROD", "PRODUCTION"}:
            raise RuntimeError("Local managed-upload storage is disabled in production")
        return LocalStorageBackend()
    if backend in {"s3", "object", "object-storage"}:
        return S3StorageBackend()
    raise RuntimeError(f"Unsupported TORE_STORAGE_BACKEND: {backend}")


def max_upload_bytes() -> int:
    raw = (os.getenv("TORE_UPLOAD_MAX_BYTES") or str(DEFAULT_MAX_UPLOAD_BYTES)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("TORE_UPLOAD_MAX_BYTES must be an integer") from exc
    if value < 1:
        raise RuntimeError("TORE_UPLOAD_MAX_BYTES must be >= 1")
    return value


def sanitize_filename(filename: str | None) -> str:
    raw = unicodedata.normalize("NFKC", filename or "upload")
    raw = raw.replace("\\", "/").split("/")[-1]
    raw = re.sub(r"[\x00-\x1f\x7f]+", "", raw)
    raw = re.sub(r"[^\w.()\- ]+", "_", raw, flags=re.UNICODE).strip(" .")
    raw = re.sub(r"\.{2,}", ".", raw)
    if not raw:
        raw = "upload"
    return raw[:255]


def _detect_ooxml(data: bytes) -> str | None:
    if not data.startswith(b"PK\x03\x04"):
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, RuntimeError):
        return None
    if "[Content_Types].xml" not in names:
        return None
    if "word/document.xml" in names:
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if "xl/workbook.xml" in names:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if "ppt/presentation.xml" in names:
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return None


def detect_mime(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    return _detect_ooxml(data)


async def validate_upload(upload: UploadFile) -> ValidatedUpload:
    limit = max_upload_bytes()
    body = bytearray()
    while True:
        chunk = await upload.read(READ_CHUNK_BYTES)
        if not chunk:
            break
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(
                status_code=413,
                detail={"reason": "FILE_TOO_LARGE", "maxBytes": limit},
            )
    data = bytes(body)
    if not data:
        raise HTTPException(status_code=400, detail={"reason": "EMPTY_FILE"})

    detected = detect_mime(data)
    if detected not in MIME_EXTENSIONS:
        raise HTTPException(status_code=415, detail={"reason": "MIME_NOT_ALLOWED"})

    original_name = sanitize_filename(upload.filename)
    suffix = Path(original_name).suffix.lower()
    if suffix not in MIME_EXTENSIONS[detected]:
        raise HTTPException(
            status_code=415,
            detail={
                "reason": "FILE_EXTENSION_MISMATCH",
                "detectedMime": detected,
            },
        )

    return ValidatedUpload(
        data=data,
        original_name=original_name,
        mime_type=detected,
        size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
    )


def build_storage_key(*, organization_id: int, file_id: str, visibility: str, mime_type: str) -> str:
    scope = "public" if visibility.upper() == "PUBLIC" else "private"
    extension = CANONICAL_EXTENSION[mime_type]
    # Only server-generated components reach this path. Original client names never do.
    return f"{scope}/structures/{organization_id}/{file_id}{extension}"
