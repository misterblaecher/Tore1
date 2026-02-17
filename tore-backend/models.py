from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import (
    Integer,
    Float,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Text,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base, now_utc

class Bar(Base):
    __tablename__ = "bars"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    city: Mapped[str] = mapped_column(String, default="")

    # Localisation (V1: floats, sans PostGIS)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    partner_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)

    events: Mapped[List["Event"]] = relationship(back_populates="bar")

    partner_accesses: Mapped[List["PartnerBarAccess"]] = relationship(
        back_populates="bar", cascade="all, delete-orphan"
    )
    menu_categories: Mapped[List["MenuCategory"]] = relationship(
        back_populates="bar", cascade="all, delete-orphan"
    )
    menu_items: Mapped[List["MenuItem"]] = relationship(
        back_populates="bar", cascade="all, delete-orphan"
    )


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bars.id"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    ends_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc() + timedelta(hours=6))

    entry_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    ticket_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    ticket_value_cents: Mapped[int] = mapped_column(Integer, default=200)

    allow_self_ticket_adjust: Mapped[bool] = mapped_column(Boolean, default=True)
    event_code: Mapped[Optional[str]] = mapped_column(String(16), unique=True, index=True, nullable=True)
    charter_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    charter_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    charter_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    venue: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Brussels")
    event_state: Mapped[str] = mapped_column(String(24), default="LIVE", index=True)
    modules_on: Mapped[dict] = mapped_column(JSON, default=dict)
    rules_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    last_state_updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    last_updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    host_type: Mapped[str] = mapped_column(String(16), default="user", index=True)
    host_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    host_display_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    visibility: Mapped[str] = mapped_column(String(16), default="PRIVATE", index=True)
    publication_status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)

    bar: Mapped["Bar"] = relationship(back_populates="events")
    drinks: Mapped[List["EventDrink"]] = relationship(back_populates="event")




class EventCreateIdempotency(Base):
    __tablename__ = "event_create_idempotency"
    __table_args__ = (
        UniqueConstraint("bar_id", "idempotency_key", name="uq_event_create_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bars.id"), index=True, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventQrToken(Base):
    __tablename__ = "event_qr_tokens"
    __table_args__ = (
        UniqueConstraint("token_id", name="uq_event_qr_tokens_token_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    qr_type: Mapped[str] = mapped_column(String(32), index=True)
    role: Mapped[Optional[str]] = mapped_column(String(24), nullable=True, index=True)
    assignment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("event_staff_assignments.id"), nullable=True, index=True)
    token_id: Mapped[str] = mapped_column(String(64), index=True)
    nonce: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text)
    signature: Mapped[str] = mapped_column(String(128))
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)


class EventStaffAssignment(Base):
    __tablename__ = "event_staff_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    role: Mapped[str] = mapped_column(String(24), index=True)
    label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("partner_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)


class EventStaffAssignmentIdempotency(Base):
    __tablename__ = "event_staff_assignment_idempotency"
    __table_args__ = (
        UniqueConstraint("event_id", "idempotency_key", name="uq_event_staff_assignment_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("event_staff_assignments.id"), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventStaffInviteCode(Base):
    __tablename__ = "event_staff_invite_codes"
    __table_args__ = (
        UniqueConstraint("event_id", "code", name="uq_event_staff_invite_event_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    role: Mapped[str] = mapped_column(String(24), index=True)
    code: Mapped[str] = mapped_column(String(24), index=True)
    label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_reason: Mapped[Optional[str]] = mapped_column(String(280), nullable=True)


class EventStaffInviteIdempotency(Base):
    __tablename__ = "event_staff_invite_idempotency"
    __table_args__ = (
        UniqueConstraint("event_id", "action", "actor_user_id", "idempotency_key", name="uq_event_staff_invite_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    invite_id: Mapped[Optional[int]] = mapped_column(ForeignKey("event_staff_invite_codes.id"), nullable=True, index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventStaffBackupCode(Base):
    __tablename__ = "event_staff_backup_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    role: Mapped[str] = mapped_column(String(24), index=True)
    code_hash: Mapped[str] = mapped_column(String(128), index=True)
    suffix4: Mapped[str] = mapped_column(String(4), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    used_by: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    revoked_reason: Mapped[Optional[str]] = mapped_column(String(280), nullable=True)


class EventStaffBackupIdempotency(Base):
    __tablename__ = "event_staff_backup_idempotency"
    __table_args__ = (
        UniqueConstraint("event_id", "action", "actor_user_id", "idempotency_key", name="uq_event_staff_backup_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    code_id: Mapped[Optional[int]] = mapped_column(ForeignKey("event_staff_backup_codes.id"), nullable=True, index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventQrPackIdempotency(Base):
    __tablename__ = "event_qr_pack_idempotency"
    __table_args__ = (
        UniqueConstraint("event_id", "idempotency_key", name="uq_event_qr_pack_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    pack_json: Mapped[dict] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventAppWriteIdempotency(Base):
    __tablename__ = "event_app_write_idempotency"
    __table_args__ = (
        UniqueConstraint("actor_user_id", "action", "idempotency_key", name="uq_event_app_write_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventIncident(Base):
    __tablename__ = "event_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    title: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), default="info", index=True)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    location: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("partner_users.id"), index=True)
    assigned_to_staff_assignment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("event_staff_assignments.id"), nullable=True, index=True)
    assigned_to_role: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventIncidentLog(Base):
    __tablename__ = "event_incident_logs"
    __table_args__ = (
        Index("ix_event_incident_logs_incident_created", "incident_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("event_incidents.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(24), default="comment", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    actor_id: Mapped[int] = mapped_column(ForeignKey("partner_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventIncidentCreateIdempotency(Base):
    __tablename__ = "event_incident_create_idempotency"
    __table_args__ = (
        UniqueConstraint("event_id", "idempotency_key", name="uq_event_incident_create_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("event_incidents.id"), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventIncidentActionIdempotency(Base):
    __tablename__ = "event_incident_action_idempotency"
    __table_args__ = (
        UniqueConstraint("incident_id", "action_type", "idempotency_key", name="uq_event_incident_action_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("event_incidents.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(24), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventModuleConfig(Base):
    __tablename__ = "event_module_configs"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_module_config_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    orders_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    market_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    battles_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    hunt_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    polymarket_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    entry_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    checkins_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    wifi_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    safety_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("partner_users.id"), nullable=True
    )




class EventRuntimeState(Base):
    __tablename__ = "event_runtime_states"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_runtime_state_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    state: Mapped[str] = mapped_column(String(24), default="LIVE")
    reason: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)


class EventWifiSettings(Base):
    __tablename__ = "event_wifi_settings"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_wifi_settings_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ssid: Mapped[str] = mapped_column(String(180), default="")
    password: Mapped[str] = mapped_column(String(240), default="")
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)


class EventWifiToken(Base):
    __tablename__ = "event_wifi_tokens"
    __table_args__ = (UniqueConstraint("token_id", name="uq_event_wifi_tokens_token_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    token_id: Mapped[str] = mapped_column(String(64), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    revoked_by: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)
    revoke_reason: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    issued_to_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)


class EventWifiIdempotency(Base):
    __tablename__ = "event_wifi_idempotency"
    __table_args__ = (
        UniqueConstraint("event_id", "action", "idempotency_key", name="uq_event_wifi_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventMapSettings(Base):
    __tablename__ = "event_map_settings"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_map_settings_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    venue_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tec_link: Mapped[Optional[str]] = mapped_column(String(600), nullable=True)
    waze_link: Mapped[Optional[str]] = mapped_column(String(600), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)


class EventNavettesSettings(Base):
    __tablename__ = "event_navettes_settings"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_navettes_settings_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_return_time: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)


class EventMapIdempotency(Base):
    __tablename__ = "event_map_idempotency"
    __table_args__ = (
        UniqueConstraint("event_id", "idempotency_key", name="uq_event_map_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)

class Hunt(Base):
    __tablename__ = "hunts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bars.id"), index=True, nullable=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(180), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    reward_tickets: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class HuntPoint(Base):
    __tablename__ = "hunt_points"
    __table_args__ = (
        UniqueConstraint("secret_code", name="uq_hunt_points_secret_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hunt_id: Mapped[int] = mapped_column(ForeignKey("hunts.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), default="")
    hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    secret_code: Mapped[str] = mapped_column(String(64), index=True)


class HuntScan(Base):
    __tablename__ = "hunt_scans"
    __table_args__ = (
        UniqueConstraint("point_id", "user_id", name="uq_hunt_scans_point_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hunt_id: Mapped[int] = mapped_column(ForeignKey("hunts.id"), index=True)
    point_id: Mapped[int] = mapped_column(ForeignKey("hunt_points.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventHunt(Base):
    __tablename__ = "event_hunts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    title: Mapped[str] = mapped_column(String(180), default="")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    rules_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("partner_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventHuntCheckpoint(Base):
    __tablename__ = "event_hunt_checkpoints"
    __table_args__ = (
        UniqueConstraint("hunt_id", "order_index", name="uq_event_hunt_checkpoint_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hunt_id: Mapped[int] = mapped_column(ForeignKey("event_hunts.id"), index=True)
    label: Mapped[str] = mapped_column(String(180), default="")
    points: Mapped[int] = mapped_column(Integer, default=1)
    reward_tickets: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    qr_token_id: Mapped[str] = mapped_column(String(64), index=True)
    qr_token_hash: Mapped[str] = mapped_column(String(64), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class EventHuntClaim(Base):
    __tablename__ = "event_hunt_claims"
    __table_args__ = (
        UniqueConstraint("checkpoint_id", "user_id", name="uq_event_hunt_claim_checkpoint_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hunt_id: Mapped[int] = mapped_column(ForeignKey("event_hunts.id"), index=True)
    checkpoint_id: Mapped[int] = mapped_column(ForeignKey("event_hunt_checkpoints.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    points_awarded: Mapped[int] = mapped_column(Integer, default=0)


class EventHuntScore(Base):
    __tablename__ = "event_hunt_scores"
    __table_args__ = (
        UniqueConstraint("hunt_id", "user_id", name="uq_event_hunt_score_hunt_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hunt_id: Mapped[int] = mapped_column(ForeignKey("event_hunts.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventHuntIdempotency(Base):
    __tablename__ = "event_hunt_idempotency"
    __table_args__ = (
        UniqueConstraint("event_id", "action", "idempotency_key", name="uq_event_hunt_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventHuntSteal(Base):
    __tablename__ = "event_hunt_steals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hunt_id: Mapped[int] = mapped_column(ForeignKey("event_hunts.id"), index=True)
    attacker_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    victim_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str] = mapped_column(String(32), default="OK", index=True)
    audit: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class Drink(Base):
    __tablename__ = "drinks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    type: Mapped[str] = mapped_column(String, default="beer")


class EventDrink(Base):
    __tablename__ = "event_drinks"
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), primary_key=True)
    drink_id: Mapped[int] = mapped_column(ForeignKey("drinks.id"), primary_key=True)

    base_price_cents: Mapped[int] = mapped_column(Integer, default=250)
    override_price_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Market price (effective if no override)
    current_price_cents: Mapped[int] = mapped_column(Integer, default=250)
    last_price_update: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    event: Mapped["Event"] = relationship(back_populates="drinks")
    drink: Mapped["Drink"] = relationship()


class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    drink_id: Mapped[int] = mapped_column(Integer, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    price_cents: Mapped[int] = mapped_column(Integer)


class DrinkMarketConfig(Base):
    __tablename__ = "drink_market_configs"
    __table_args__ = (UniqueConstraint("bar_id", "event_id", name="uq_drink_market_config_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False)
    ticket_value_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price_floor_cents: Mapped[int] = mapped_column(Integer, default=50)
    price_cap_cents: Mapped[int] = mapped_column(Integer, default=2000)
    step_cents: Mapped[int] = mapped_column(Integer, default=10)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class DrinkMarketItem(Base):
    __tablename__ = "drink_market_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("drink_market_configs.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    base_price_cents: Mapped[int] = mapped_column(Integer)
    current_price_cents: Mapped[int] = mapped_column(Integer)
    unit: Mapped[str] = mapped_column(String(40), default="unit")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class DrinkPriceTick(Base):
    __tablename__ = "drink_price_ticks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("drink_market_items.id"), index=True)
    price_cents: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)
    ref_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)


class DrinkPriceTickIdempotency(Base):
    __tablename__ = "drink_price_tick_idempotency"
    __table_args__ = (UniqueConstraint("item_id", "idempotency_key", name="uq_market_price_idempotency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("drink_market_items.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    tick_id: Mapped[int] = mapped_column(ForeignKey("drink_price_ticks.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class TicketBalance(Base):
    __tablename__ = "ticket_balances"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)


class Ban(Base):
    __tablename__ = "bans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    reason: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class Entry(Base):
    __tablename__ = "entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    pay_mode: Mapped[str] = mapped_column(String, default="manual")
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class EntryLog(Base):
    __tablename__ = "entry_logs"
    __table_args__ = (
        UniqueConstraint("event_id", "idempotency_key", name="uq_entry_logs_event_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    delta: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String, default="scan")
    staff_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    device_id: Mapped[str] = mapped_column(String, default="")
    idempotency_key: Mapped[str] = mapped_column(String, default="")
    raw_qr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class EntryScanLog(Base):
    __tablename__ = "entry_scan_logs"
    __table_args__ = (
        UniqueConstraint("event_id", "payload_hash", name="uq_entry_scan_logs_event_payload"),
        UniqueConstraint("event_id", "scan_id", name="uq_entry_scan_logs_event_scan_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    scan_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    payload_raw: Mapped[str] = mapped_column(Text, default="")
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    decision: Mapped[str] = mapped_column(String(12), default="DENY")
    reason: Mapped[str] = mapped_column(String(120), default="invalid")
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("partner_users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    token_id: Mapped[Optional[int]] = mapped_column(ForeignKey("entry_tokens.id"), nullable=True, index=True)
    token_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)


class EntryToken(Base):
    __tablename__ = "entry_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_entry_tokens_token_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    used_by_partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)
    used_scan_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(12), default="ACTIVE", index=True)


class EventStaff(Base):
    __tablename__ = "event_staff"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_staff_event_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[str] = mapped_column(String, default="entry")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class EventJoin(Base):
    __tablename__ = "event_joins"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_joins_event_user"),
        UniqueConstraint("event_id", "idempotency_key", name="uq_event_joins_event_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    accepted_charter_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)


class EventCharterAcceptance(Base):
    __tablename__ = "event_charter_acceptances"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", "charter_version", name="uq_event_charter_acceptance"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    charter_version: Mapped[str] = mapped_column(String(32), default="v1")
    accepted_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class StaffInviteToken(Base):
    __tablename__ = "staff_invite_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    role: Mapped[str] = mapped_column(String, default="entry")
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class EventAuditLog(Base):
    __tablename__ = "event_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class EventConfig(Base):
    __tablename__ = "event_configs"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_config_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    menu_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    wallet_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    entry_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    checkin_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    battles_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    hunt_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    report_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_user_bets: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    updated_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Bet(Base):
    __tablename__ = "polymarket_bets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(16), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    question: Mapped[str] = mapped_column(String(280), default="")
    kind: Mapped[str] = mapped_column(String(16), default="OBJECTIVE")
    status: Mapped[str] = mapped_column(String(16), default="LIVE")

    deadline_at: Mapped[datetime] = mapped_column(DateTime)
    resolver_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    rules_text: Mapped[str] = mapped_column(Text, default="")
    dispute_window_minutes: Mapped[int] = mapped_column(Integer, default=60)
    created_by_user_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_outcome: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    pool_yes_tickets: Mapped[int] = mapped_column(Integer, default=0)
    pool_no_tickets: Mapped[int] = mapped_column(Integer, default=0)

    positions: Mapped[List["BetPosition"]] = relationship(
        back_populates="bet", cascade="all, delete-orphan"
    )


class BetPosition(Base):
    __tablename__ = "polymarket_positions"
    __table_args__ = (
        UniqueConstraint("bet_id", "user_id", "idempotency_key", name="uq_bet_positions_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bet_id: Mapped[int] = mapped_column(ForeignKey("polymarket_bets.id"), index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    side: Mapped[str] = mapped_column(String(8))
    stake_tickets: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    bet: Mapped["Bet"] = relationship(back_populates="positions")


class BetResolutionLog(Base):
    __tablename__ = "polymarket_resolution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bet_id: Mapped[int] = mapped_column(ForeignKey("polymarket_bets.id"), index=True)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String(20), default="resolve")
    outcome: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class PolymarketEventIdempotency(Base):
    __tablename__ = "polymarket_event_idempotency"
    __table_args__ = (
        UniqueConstraint("event_id", "action", "idempotency_key", name="uq_polymarket_event_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    market_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(24), index=True)
    actor_user_id: Mapped[str] = mapped_column(String, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class BetDispute(Base):
    __tablename__ = "polymarket_disputes"
    __table_args__ = (
        UniqueConstraint("bet_id", "user_id", name="uq_polymarket_dispute_bet_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bet_id: Mapped[int] = mapped_column(ForeignKey("polymarket_bets.id"), index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class EventConfigLog(Base):
    __tablename__ = "event_config_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    changed_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    changes_json: Mapped[str] = mapped_column(Text, default="{}")


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    bar: Mapped["Bar"] = relationship(back_populates="menu_categories")
    items: Mapped[List["MenuItem"]] = relationship(back_populates="category")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("menu_categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    image_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    stock_status: Mapped[str] = mapped_column(String(8), default="IN")
    version: Mapped[int] = mapped_column(Integer, default=1)
    last_price_change_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    alcohol: Mapped[bool] = mapped_column(Boolean, default=False)
    vegan: Mapped[bool] = mapped_column(Boolean, default=False)
    allergens: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    bar: Mapped["Bar"] = relationship(back_populates="menu_items")
    category: Mapped["MenuCategory"] = relationship(back_populates="items")
    variants: Mapped[List["MenuItemVariant"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class MenuItemVariant(Base):
    __tablename__ = "menu_item_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    price_delta_cents: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    item: Mapped["MenuItem"] = relationship(back_populates="variants")


class MenuTrackEvent(Base):
    __tablename__ = "menu_track_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("menu_items.id"), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(16), default="view")
    device_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    changes_json: Mapped[str] = mapped_column(Text, default="{}")


class MenuAdminIdempotency(Base):
    __tablename__ = "menu_admin_idempotency"
    __table_args__ = (UniqueConstraint("event_id", "idempotency_key", name="uq_menu_admin_idempotency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventCost(Base):
    __tablename__ = "event_costs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    label: Mapped[str] = mapped_column(String, default="")
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String, default="other")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class EventCostSimple(Base):
    __tablename__ = "event_costs_simple"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_costs_simple_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    costs_tickets: Mapped[int] = mapped_column(Integer, default=0)
    breakdown_json: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventCostSimpleIdempotency(Base):
    __tablename__ = "event_costs_simple_idempotency"
    __table_args__ = (
        UniqueConstraint("event_id", "idempotency_key", name="uq_event_costs_simple_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_event_created", "event_id", "created_at"),
        Index("ix_orders_event_status_created", "event_id", "status", "created_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bars.id"), index=True, nullable=True)
    event_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    zone_id: Mapped[Optional[int]] = mapped_column(ForeignKey("zones.id"), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="NEW", index=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="menu_qr")
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    total_tickets: Mapped[int] = mapped_column(Integer, default=0)
    payment_status: Mapped[str] = mapped_column(String(20), default="UNPAID", index=True)
    pay_mode: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_gift: Mapped[bool] = mapped_column(Boolean, default=False)
    gift_to_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    items: Mapped[List["OrderItem"]] = relationship(back_populates="order")


class OrderStatusTransitionIdempotency(Base):
    __tablename__ = "order_status_transition_idempotency"
    __table_args__ = (
        UniqueConstraint("order_id", "action", "idempotency_key", name="uq_order_status_transition_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    action: Mapped[str] = mapped_column(String(24), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    from_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20))
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    menu_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("menu_items.id"), index=True, nullable=True)
    variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("menu_item_variants.id"), index=True, nullable=True)
    name_snapshot: Mapped[str] = mapped_column(String(180), default="")
    price_cents_snapshot: Mapped[int] = mapped_column(Integer, default=0)
    qty: Mapped[int] = mapped_column(Integer, default=1)
    line_total_cents: Mapped[int] = mapped_column(Integer, default=0)
    drink_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    unit_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    market_item_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="items")


# --- Untappd-like MVP ---


class Beer(Base):
    __tablename__ = "beers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    barcode: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, default="")
    brewery: Mapped[str] = mapped_column(String, default="")
    style: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class Checkin(Base):
    __tablename__ = "checkins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    beer_id: Mapped[int] = mapped_column(ForeignKey("beers.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer, default=0)  # store *10 as int for sqlite simplicity
    comment: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    beer: Mapped["Beer"] = relationship()


# --- Battles (Afond) MVP ---


class Battle(Base):
    __tablename__ = "battles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bars.id"), index=True, nullable=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(180), default="Battle")
    mode: Mapped[str] = mapped_column(String(16), default="teams")
    status: Mapped[str] = mapped_column(String(16), default="OPEN")
    join_code: Mapped[Optional[str]] = mapped_column(String(16), index=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    winner_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class BattleParticipant(Base):
    __tablename__ = "battle_participants"
    __table_args__ = (UniqueConstraint("battle_id", "user_id", name="uq_battle_participant_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    battle_id: Mapped[int] = mapped_column(ForeignKey("battles.id"), index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class BattleTeam(Base):
    __tablename__ = "battle_teams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    battle_id: Mapped[int] = mapped_column(ForeignKey("battles.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class BattleJoin(Base):
    __tablename__ = "battle_joins"
    __table_args__ = (UniqueConstraint("battle_id", "user_id", name="uq_battle_join_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    battle_id: Mapped[int] = mapped_column(ForeignKey("battles.id"), index=True)
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("battle_teams.id"), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class BattleAction(Base):
    __tablename__ = "battle_actions"
    __table_args__ = (UniqueConstraint("battle_id", "idempotency_key", name="uq_battle_action_idempotency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    battle_id: Mapped[int] = mapped_column(ForeignKey("battles.id"), index=True)
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("battle_teams.id"), nullable=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(16), default="AFFOND")
    delta: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

# --- Partner authentication / bar backoffice ---


class PartnerUser(Base):
    __tablename__ = "partner_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # PIN-based partner auth (nom d'affichage + code PIN hashé)
    display_name: Mapped[str] = mapped_column(String(80), index=True, default="")
    pin_hash: Mapped[str] = mapped_column(String, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    memberships: Mapped[List["PartnerMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    bar_accesses: Mapped[List["PartnerBarAccess"]] = relationship(
        back_populates="partner_user", cascade="all, delete-orphan"
    )



class PartnerBarAccess(Base):
    __tablename__ = "partner_bar_access"
    __table_args__ = (
        UniqueConstraint("partner_user_id", "bar_id", name="uq_partner_user_bar"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    partner_user_id: Mapped[int] = mapped_column(ForeignKey("partner_users.id"), index=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)

    role: Mapped[str] = mapped_column(String, default="owner")  # owner, manager, staff, ...
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    partner_user: Mapped["PartnerUser"] = relationship(back_populates="bar_accesses")
    bar: Mapped["Bar"] = relationship(back_populates="partner_accesses")


class PartnerMagicLinkToken(Base):
    __tablename__ = "partner_magic_link_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    partner_user_id: Mapped[int] = mapped_column(ForeignKey("partner_users.id"), index=True)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    partner_user: Mapped["PartnerUser"] = relationship()

class PartnerMembership(Base):
    __tablename__ = "partner_memberships"
    __table_args__ = (
        UniqueConstraint("bar_id", "display_name", name="uq_membership_bar_display_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("partner_users.id"), index=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)

    role: Mapped[str] = mapped_column(String(20), default="bartender")  # manager | bartender
    display_name: Mapped[str] = mapped_column(String(80), default="")

    user: Mapped["PartnerUser"] = relationship(back_populates="memberships")
    bar: Mapped["Bar"] = relationship()


class PartnerTokenRevocation(Base):
    __tablename__ = "partner_token_revocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    revoked_by_partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)


class PartnerInvite(Base):
    __tablename__ = "partner_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)

    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(20), default="bartender")
    max_uses: Mapped[int] = mapped_column(Integer, default=25)
    uses_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    bar: Mapped["Bar"] = relationship()


# ---------------------------------------------------------------------
# App users (guest auth) — V1
# ---------------------------------------------------------------------

class AppUser(Base):
    __tablename__ = "app_users"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid string
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    display_name: Mapped[str] = mapped_column(String, default="")
    avatar_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    address_text: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    instagram_handle: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    profile_visibility: Mapped[str] = mapped_column(String(16), default="PUBLIC", index=True)

    show_address: Mapped[bool] = mapped_column(Boolean, default=False)
    show_avatar: Mapped[bool] = mapped_column(Boolean, default=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    anonymized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    tokens: Mapped[List["AppToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Wallet(Base):
    __tablename__ = "wallets"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), primary_key=True)
    balance_tickets: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())

    user: Mapped["AppUser"] = relationship()


class WalletTx(Base):
    __tablename__ = "wallet_txs"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_wallet_txs_user_idempotency"),
        Index("ix_wallet_txs_user_ts", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="CREDIT")
    amount_tickets: Mapped[int] = mapped_column(Integer)
    ref_type: Mapped[str] = mapped_column(String(20), default="TOPUP_QR")
    ref_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("partner_users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    user: Mapped["AppUser"] = relationship()


class WalletLedgerEntry(Base):
    __tablename__ = "wallet_ledger_entries"
    __table_args__ = (
        UniqueConstraint("event_id", "idempotency_key", name="uq_wallet_ledger_event_idempotency"),
        Index("ix_wallet_ledger_event_ts", "event_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    amount_tickets: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(255), default="")
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("partner_users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class WalletGift(Base):
    __tablename__ = "wallet_gifts"
    __table_args__ = (
        UniqueConstraint("from_user_id", "idempotency_key", name="uq_wallet_gifts_sender_idempotency"),
        Index("ix_wallet_gifts_from_ts", "from_user_id", "created_at"),
        Index("ix_wallet_gifts_to_ts", "to_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    from_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    to_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    amount_tickets: Mapped[int] = mapped_column(Integer)
    message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class TicketTransfer(Base):
    __tablename__ = "ticket_transfers"
    __table_args__ = (
        Index("ix_ticket_transfers_from_ts", "from_user_id", "created_at"),
        Index("ix_ticket_transfers_to_ts", "to_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    to_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class TicketTransferIdempotency(Base):
    __tablename__ = "ticket_transfer_idempotency"
    __table_args__ = (
        UniqueConstraint("from_user_id", "idempotency_key", name="uq_ticket_transfer_sender_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey("ticket_transfers.id"), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class UserGiftCode(Base):
    __tablename__ = "user_gift_codes"
    __table_args__ = (UniqueConstraint("code", name="uq_user_gift_codes_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class Committee(Base):
    __tablename__ = "committees"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_committees_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    slug: Mapped[str] = mapped_column(String(120), index=True)
    description_public: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeYear(Base):
    __tablename__ = "committee_years"
    __table_args__ = (
        UniqueConstraint("committee_id", "year_label", name="uq_committee_years_label"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    year_label: Mapped[str] = mapped_column(String(32), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeMembership(Base):
    __tablename__ = "committee_memberships"
    __table_args__ = (
        UniqueConstraint("committee_id", "user_id", name="uq_committee_membership_user"),
        Index("ix_committee_memberships_committee_active", "committee_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    role: Mapped[str] = mapped_column(String(24), default="MEMBER", index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class CommitteeInviteCode(Base):
    __tablename__ = "committee_invite_codes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_committee_invite_codes_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    code: Mapped[str] = mapped_column(String(24), index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    uses_left: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeRolePermission(Base):
    __tablename__ = "committee_role_permissions"
    __table_args__ = (
        UniqueConstraint("committee_id", "role", name="uq_committee_role_permissions"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    role: Mapped[str] = mapped_column(String(24), index=True)
    permissions_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeAdminIdempotency(Base):
    __tablename__ = "committee_admin_idempotency"
    __table_args__ = (
        UniqueConstraint("committee_id", "action", "idempotency_key", name="uq_committee_admin_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeForumCategory(Base):
    __tablename__ = "committee_forum_categories"
    __table_args__ = (
        UniqueConstraint("committee_id", "year_id", "slug", name="uq_committee_forum_category_slug"),
        Index("ix_committee_forum_categories_committee_year_order", "committee_id", "year_id", "order_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    year_id: Mapped[int] = mapped_column(ForeignKey("committee_years.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeForumPost(Base):
    __tablename__ = "committee_forum_posts"
    __table_args__ = (
        Index("ix_committee_forum_posts_feed", "committee_id", "year_id", "category_id", "is_deleted", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    year_id: Mapped[int] = mapped_column(ForeignKey("committee_years.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("committee_forum_categories.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    deleted_by: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)


class CommitteeLedgerEntry(Base):
    __tablename__ = "committee_ledger_entries"
    __table_args__ = (
        Index("ix_committee_ledger_entries_feed", "committee_id", "year_id", "occurred_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    year_id: Mapped[int] = mapped_column(ForeignKey("committee_years.id"), index=True)
    entry_type: Mapped[str] = mapped_column(String(16), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    category: Mapped[str] = mapped_column(String(120), index=True)
    occurred_at: Mapped[str] = mapped_column(String(10), index=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachment_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeLedgerIdempotency(Base):
    __tablename__ = "committee_ledger_idempotency"
    __table_args__ = (
        UniqueConstraint("committee_id", "idempotency_key", name="uq_committee_ledger_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeBudgetBucket(Base):
    __tablename__ = "committee_budget_buckets"
    __table_args__ = (
        UniqueConstraint("committee_id", "year_id", "month", "category", name="uq_committee_budget_bucket"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    year_id: Mapped[int] = mapped_column(ForeignKey("committee_years.id"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    category: Mapped[str] = mapped_column(String(120), index=True)
    budget_cents: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeBaptemeCampaign(Base):
    __tablename__ = "committee_bapteme_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    year_id: Mapped[int] = mapped_column(ForeignKey("committee_years.id"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeBaptemeInvite(Base):
    __tablename__ = "committee_bapteme_invites"
    __table_args__ = (UniqueConstraint("invite_code", name="uq_committee_bapteme_invite_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("committee_bapteme_campaigns.id"), index=True)
    invite_code: Mapped[str] = mapped_column(String(32), index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    blue_display_name: Mapped[str] = mapped_column(String(180), index=True)
    status: Mapped[str] = mapped_column(String(16), default="INVITED", index=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeBaptemeSlot(Base):
    __tablename__ = "committee_bapteme_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("committee_bapteme_campaigns.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    location: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeBaptemeAssignment(Base):
    __tablename__ = "committee_bapteme_assignments"
    __table_args__ = (UniqueConstraint("invite_id", "slot_id", name="uq_committee_bapteme_assignment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invite_id: Mapped[int] = mapped_column(ForeignKey("committee_bapteme_invites.id"), index=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("committee_bapteme_slots.id"), index=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeBaptemeIncident(Base):
    __tablename__ = "committee_bapteme_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("committee_bapteme_campaigns.id"), index=True)
    invite_id: Mapped[Optional[int]] = mapped_column(ForeignKey("committee_bapteme_invites.id"), nullable=True, index=True)
    incident_type: Mapped[str] = mapped_column(String(48), index=True)
    note: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeBaptemeIdempotency(Base):
    __tablename__ = "committee_bapteme_idempotency"
    __table_args__ = (
        UniqueConstraint("committee_id", "action", "idempotency_key", name="uq_committee_bapteme_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    action: Mapped[str] = mapped_column(String(48), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class CommitteeGlossarySettings(Base):
    __tablename__ = "committee_glossary_settings"
    __table_args__ = (
        UniqueConstraint("committee_id", name="uq_committee_glossary_settings_committee"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    public_enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_by: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)


class CommitteeGlossaryTerm(Base):
    __tablename__ = "committee_glossary_terms"
    __table_args__ = (
        Index("ix_committee_glossary_terms_feed", "committee_id", "status", "year_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    year_id: Mapped[Optional[int]] = mapped_column(ForeignKey("committee_years.id"), nullable=True, index=True)
    term: Mapped[str] = mapped_column(String(140), index=True)
    definition: Mapped[str] = mapped_column(Text)
    examples: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags_json: Mapped[list] = mapped_column(JSON, default=list)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_by: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)


class CommitteeGlossaryIdempotency(Base):
    __tablename__ = "committee_glossary_idempotency"
    __table_args__ = (
        UniqueConstraint("committee_id", "action", "idempotency_key", name="uq_committee_glossary_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    action: Mapped[str] = mapped_column(String(48), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        Index("ix_organizations_city_type", "city", "org_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(140), index=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    org_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    website_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    instagram_handle: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    visibility: Mapped[str] = mapped_column(String(16), default="PUBLIC", index=True)
    join_mode: Mapped[str] = mapped_column(String(24), default="OPEN_MEMBERSHIP", index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_memberships_org_user"),
        Index("ix_organization_memberships_user_role", "user_id", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="MEMBER", index=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)


class OrganizationInviteCode(Base):
    __tablename__ = "organization_invite_codes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_organization_invite_codes_code"),
        Index("ix_organization_invite_codes_org_expires", "organization_id", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    role: Mapped[str] = mapped_column(String(16), default="MEMBER", index=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=100)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class OrganizationWriteIdempotency(Base):
    __tablename__ = "organization_write_idempotency"
    __table_args__ = (
        UniqueConstraint("actor_user_id", "action", "idempotency_key", name="uq_organization_write_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    action: Mapped[str] = mapped_column(String(48), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class OrgaPost(Base):
    __tablename__ = "organization_posts"
    __table_args__ = (
        Index("ix_organization_posts_feed", "organization_id", "deleted_at", "pinned", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    author_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_event_ts", "event_id", "ts"),
        Index("ix_audit_logs_actor_user_ts", "actor_user_id", "ts"),
        Index("ix_audit_logs_committee_ts", "committee_id", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    actor_partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True, index=True)
    actor_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), default="")
    entity_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    committee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("committees.id"), nullable=True, index=True)
    bar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bars.id"), nullable=True, index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class UserPrivacyDeleteRequest(Base):
    __tablename__ = "user_privacy_delete_requests"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_user_privacy_delete_req_idem"),
        Index("ix_user_privacy_delete_req_effective", "status", "effective_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)


class UserSanction(Base):
    __tablename__ = "user_sanctions"
    __table_args__ = (
        Index("ix_user_sanctions_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", index=True)
    type: Mapped[str] = mapped_column(String(16), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    reason: Mapped[str] = mapped_column(String(255), default="")
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    revoked_by: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)


class GlobalFeatureFlag(Base):
    __tablename__ = "global_feature_flags"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)


class EventMusicSetting(Base):
    __tablename__ = "event_music_settings"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_music_settings_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    dj_override_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_mixed: Mapped[bool] = mapped_column(Boolean, default=True)
    provider_default: Mapped[str] = mapped_column(String(24), default="spotify")
    round_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    round_status: Mapped[str] = mapped_column(String(16), default="IDLE")
    round_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    round_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    round_duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    round_locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    now_playing_candidate_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    winner_candidate_key: Mapped[Optional[str]] = mapped_column(String(420), nullable=True)
    winner_candidate_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    winner_decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    winner_votes_count: Mapped[int] = mapped_column(Integer, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)


class EventMusicCandidate(Base):
    __tablename__ = "event_music_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    candidate_key: Mapped[str] = mapped_column(String(420), index=True)
    provider: Mapped[str] = mapped_column(String(24), index=True)
    external_url: Mapped[str] = mapped_column(String(512))
    title: Mapped[str] = mapped_column(String(180), default="")
    artist: Mapped[str] = mapped_column(String(180), default="")
    artwork_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventMusicVote(Base):
    __tablename__ = "event_music_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    candidate_key: Mapped[str] = mapped_column(String(420), index=True)
    provider: Mapped[str] = mapped_column(String(24), index=True)
    external_url: Mapped[str] = mapped_column(String(512))
    title: Mapped[str] = mapped_column(String(180), default="")
    artist: Mapped[str] = mapped_column(String(180), default="")
    artwork_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventMusicActionIdempotency(Base):
    __tablename__ = "event_music_vote_idempotency"
    __table_args__ = (
        UniqueConstraint("event_id", "action_type", "actor_user_id", "idempotency_key", name="uq_event_music_vote_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(32), default="vote")
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventMusicAdminIdempotency(Base):
    __tablename__ = "event_music_admin_idempotency"
    __table_args__ = (
        UniqueConstraint("event_id", "action_type", "actor_partner_id", "idempotency_key", name="uq_event_music_admin_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(32), index=True)
    actor_partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventBattleRound(Base):
    __tablename__ = "event_battle_rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    title: Mapped[str] = mapped_column(String(180), default="")
    kind: Mapped[str] = mapped_column(String(24), default="PARTICIPATION", index=True)
    optionA_label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    optionB_label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="IDLE", index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    winner: Mapped[str] = mapped_column(String(12), default="NONE")
    winner_count_a: Mapped[int] = mapped_column(Integer, default=0)
    winner_count_b: Mapped[int] = mapped_column(Integer, default=0)


class EventBattleVote(Base):
    __tablename__ = "event_battle_votes"
    __table_args__ = (UniqueConstraint("round_id", "user_id", name="uq_event_battle_vote_round_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("event_battle_rounds.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    choice: Mapped[str] = mapped_column(String(16), default="PARTICIPATE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventBattleScore(Base):
    __tablename__ = "event_battle_scores"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_battle_score_event_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventBattleIdempotency(Base):
    __tablename__ = "event_battle_idempotency"
    __table_args__ = (
        UniqueConstraint("event_id", "action_type", "actor_id", "idempotency_key", name="uq_event_battle_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(32), index=True)
    actor_id: Mapped[str] = mapped_column(String(120), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventBroadcast(Base):
    __tablename__ = "event_broadcasts"
    __table_args__ = (
        UniqueConstraint("event_id", "author_id", "idempotency_key", name="uq_event_broadcast_idem"),
        Index("ix_event_broadcasts_event_created", "event_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("partner_users.id"), index=True)
    message: Mapped[str] = mapped_column(String(240), default="")
    level: Mapped[str] = mapped_column(String(16), default="info")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class BarPrivacySetting(Base):
    __tablename__ = "bar_privacy_settings"
    __table_args__ = (UniqueConstraint("bar_id", name="uq_bar_privacy_settings_bar"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    staff_identity_consent_required: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class AppUserPrivacySetting(Base):
    __tablename__ = "app_user_privacy_settings"
    __table_args__ = (UniqueConstraint("user_id", name="uq_app_user_privacy_settings_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    show_identity_to_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    visibility: Mapped[str] = mapped_column(String(16), default="public")
    show_identity_in_bar: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class OrderClientQrScan(Base):
    __tablename__ = "order_client_qr_scans"
    __table_args__ = (
        UniqueConstraint("bar_id", "idempotency_key", name="uq_order_client_qr_scan_bar_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    staff_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class BattleSubmit(Base):
    __tablename__ = "battle_submits"
    __table_args__ = (
        UniqueConstraint("battle_id", "scan_id", name="uq_battle_submit_scan"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    battle_id: Mapped[int] = mapped_column(ForeignKey("battles.id"), index=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    scan_id: Mapped[str] = mapped_column(String(120), index=True)
    target_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    points: Mapped[int] = mapped_column(Integer, default=1)
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    validated_by_partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class DrinkCheckin(Base):
    __tablename__ = "drink_checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    drink_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drinks.id"), index=True, nullable=True)
    name_snapshot: Mapped[str] = mapped_column(String(180), default="")
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    bar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bars.id"), index=True, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)




class Zone(Base):
    __tablename__ = "zones"
    __table_args__ = (
        UniqueConstraint("bar_id", "slug", name="uq_zones_bar_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    slug: Mapped[str] = mapped_column(String(120), default="", index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)

class WifiConfig(Base):
    __tablename__ = "wifi_configs"
    __table_args__ = (UniqueConstraint("bar_id", "event_id", name="uq_wifi_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bar_id: Mapped[int] = mapped_column(ForeignKey("bars.id"), index=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    ssid: Mapped[str] = mapped_column(String(120), default="")
    password_enc: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("partner_users.id"))
    updated_by: Mapped[int] = mapped_column(ForeignKey("partner_users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())


class SafetyBuddySession(Base):
    __tablename__ = "safety_buddy_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    buddy_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class EventSafetySettings(Base):
    __tablename__ = "event_safety_settings"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_safety_settings_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    orga_phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    message_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True)


class EventSafetyBuddy(Base):
    __tablename__ = "event_safety_buddies"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_safety_buddy_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    buddy_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class EventSafetyCheckin(Base):
    __tablename__ = "event_safety_checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    type: Mapped[str] = mapped_column(String(16), default="OK", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    resolved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True, index=True)
    resolve_reason: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partner_users.id"), nullable=True, index=True)


class EventSafetyIdempotency(Base):
    __tablename__ = "event_safety_idempotency"
    __table_args__ = (
        UniqueConstraint("event_id", "action", "actor_scope", "actor_id", "idempotency_key", name="uq_event_safety_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    actor_scope: Mapped[str] = mapped_column(String(16), default="user")
    actor_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class AppToken(Base):
    __tablename__ = "app_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)

    # ✅ SHA256 hex = 64 chars
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc())
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["AppUser"] = relationship(back_populates="tokens")


class AuthMagicLink(Base):
    __tablename__ = "auth_magic_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    request_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    request_device: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: now_utc(), index=True)
