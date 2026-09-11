from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


VisibilityLevel = Literal["PUBLIC", "TORE", "MEMBERS", "STAFF", "BUREAU", "TREASURY", "PRIVATE"]
StructureStatus = Literal["REQUESTED", "SETUP", "ACTIVE", "LOCKED", "ARCHIVED"]
PublicPageStatus = Literal["DRAFT", "PUBLISHED", "HIDDEN", "SUSPENDED", "ARCHIVED"]
EventLifecycleStatus = Literal["DRAFT", "PUBLISHED", "SYNCED_TO_APP", "LIVE", "CLOSED", "RECAP_DRAFT", "RECAP_PUBLISHED", "ARCHIVED"]


class StructureCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    slug: Optional[str] = Field(default=None, min_length=2, max_length=160)
    org_type: str = Field(default="OTHER", min_length=2, max_length=64)
    description: Optional[str] = Field(default=None, max_length=10000)
    city: Optional[str] = Field(default=None, max_length=120)


class StructurePatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=140)
    description: Optional[str] = Field(default=None, max_length=10000)
    org_type: Optional[str] = Field(default=None, min_length=2, max_length=64)
    city: Optional[str] = Field(default=None, max_length=120)
    primary_color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    contact_email: Optional[str] = Field(default=None, max_length=255)
    contact_phone: Optional[str] = Field(default=None, max_length=64)
    seo_title: Optional[str] = Field(default=None, max_length=180)
    seo_description: Optional[str] = Field(default=None, max_length=320)


class StructureOut(BaseModel):
    id: int
    slug: str
    name: str
    type: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    status: str
    public_page_status: str
    owner_user_id: Optional[str] = None
    primary_color: Optional[str] = None


class PublicPagePatchIn(BaseModel):
    status: PublicPageStatus
    seo_enabled: Optional[bool] = None
    indexable: Optional[bool] = None


class RoleCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    audience_level: VisibilityLevel = "MEMBERS"
    permissions: list[str] = Field(default_factory=list, max_length=80)


class RolePatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    audience_level: Optional[VisibilityLevel] = None
    permissions: Optional[list[str]] = Field(default=None, max_length=80)


class RoleOut(BaseModel):
    id: int
    name: str
    system_role: bool
    audience_level: str
    permissions: list[str]


class MemberPatchIn(BaseModel):
    role_id: Optional[int] = None
    status: Optional[Literal["INVITED", "ACTIVE", "FORMER", "REVOKED"]] = None
    title: Optional[str] = Field(default=None, max_length=120)
    team: Optional[str] = Field(default=None, max_length=120)
    public_profile: Optional[bool] = None
    mandate_start: Optional[datetime] = None
    mandate_end: Optional[datetime] = None


class OwnershipTransferIn(BaseModel):
    new_owner_user_id: str = Field(min_length=3, max_length=120)


class InvitationCreateIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role_id: int
    expires_in_hours: int = Field(default=72, ge=1, le=24 * 30)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Invalid email")
        return value


class InvitationAcceptIn(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class ClaimCreateIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=3000)


class ClaimReviewIn(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    transfer_ownership: bool = False


class VisibilityPolicyIn(BaseModel):
    resource_type: str = Field(min_length=2, max_length=48)
    resource_id: str = Field(default="__section__", min_length=1, max_length=80)
    level: VisibilityLevel


class EventCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    starts_at: datetime
    ends_at: datetime
    venue: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=10000)
    visibility: Literal["PUBLIC", "PRIVATE"] = "PRIVATE"
    capacity: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    entry_price_cents: int = Field(default=0, ge=0, le=10_000_000)
    co_host_structure_ids: list[int] = Field(default_factory=list, max_length=20)

    @field_validator("ends_at")
    @classmethod
    def nonempty_end(cls, value: datetime) -> datetime:
        return value


class EventPatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    venue: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=10000)
    visibility: Optional[Literal["PUBLIC", "PRIVATE"]] = None
    capacity: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    entry_price_cents: Optional[int] = Field(default=None, ge=0, le=10_000_000)


class EventTransitionIn(BaseModel):
    target: EventLifecycleStatus


class AccountingEntryCreateIn(BaseModel):
    event_id: Optional[int] = None
    entry_type: Literal["INCOME", "EXPENSE"]
    category: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=180)
    amount_cents: int = Field(ge=0, le=2_000_000_000)
    supplier: Optional[str] = Field(default=None, max_length=180)
    paid: bool = False
    notes: Optional[str] = Field(default=None, max_length=5000)


class AccountingEntryPatchIn(BaseModel):
    category: Optional[str] = Field(default=None, min_length=1, max_length=80)
    label: Optional[str] = Field(default=None, min_length=1, max_length=180)
    amount_cents: Optional[int] = Field(default=None, ge=0, le=2_000_000_000)
    supplier: Optional[str] = Field(default=None, max_length=180)
    paid: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=5000)
    status: Optional[Literal["DRAFT", "VALIDATED"]] = None


class ChannelCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    visibility: VisibilityLevel = "MEMBERS"


class ChannelPatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    visibility: Optional[VisibilityLevel] = None
    archived: Optional[bool] = None


class MessageCreateIn(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    title: Optional[str] = Field(default=None, max_length=180)
    parent_message_id: Optional[int] = None
    document_ids: list[int] = Field(default_factory=list, max_length=8)


class DocumentCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=5000)
    folder: Optional[str] = Field(default=None, max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=20)
    visibility: VisibilityLevel = "MEMBERS"
    event_id: Optional[int] = None


class AlbumCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=5000)
    visibility: VisibilityLevel = "MEMBERS"
    event_id: Optional[int] = None


class AlbumPatchIn(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=5000)
    visibility: Optional[VisibilityLevel] = None
    status: Optional[Literal["DRAFT", "PUBLISHED", "ARCHIVED"]] = None
    cover_media_id: Optional[int] = None


class MediaOrderIn(BaseModel):
    media_ids: list[int] = Field(min_length=1, max_length=500)


class FolklorePageCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    slug: Optional[str] = Field(default=None, max_length=180)
    content: str = Field(default="", max_length=200000)
    category: str = Field(default="OTHER", max_length=24)
    visibility: VisibilityLevel = "MEMBERS"
    published: bool = False


class FolklorePagePatchIn(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=180)
    content: Optional[str] = Field(default=None, max_length=200000)
    category: Optional[str] = Field(default=None, max_length=24)
    visibility: Optional[VisibilityLevel] = None
    published: Optional[bool] = None


class FolkloreRestoreIn(BaseModel):
    version_number: int = Field(ge=1)


class PublicPostCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    body: str = Field(min_length=1, max_length=20000)
    event_id: Optional[int] = None
    media_id: Optional[int] = None
    status: Literal["DRAFT", "SCHEDULED", "PUBLISHED"] = "DRAFT"
    visibility: VisibilityLevel = "PUBLIC"
    publish_at: Optional[datetime] = None


class PublicPostPatchIn(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=180)
    body: Optional[str] = Field(default=None, min_length=1, max_length=20000)
    event_id: Optional[int] = None
    media_id: Optional[int] = None
    status: Optional[Literal["DRAFT", "SCHEDULED", "PUBLISHED", "ARCHIVED"]] = None
    visibility: Optional[VisibilityLevel] = None
    publish_at: Optional[datetime] = None


class PublicSummaryOut(BaseModel):
    event_id: int
    entries: int
    scans: int
    capacity: Optional[int] = None
    occupancy_percent: Optional[int] = None
    published_at: datetime
