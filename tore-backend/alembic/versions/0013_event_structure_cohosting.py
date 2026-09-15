"""add persistent event structure cohosting and manager settings

Revision ID: 0013_event_structure_cohosting
Revises: 0012_secure_managed_uploads
Create Date: 2026-09-15
"""

from __future__ import annotations

import json
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0013_event_structure_cohosting"
down_revision = "0012_secure_managed_uploads"
branch_labels = None
depends_on = None


PERMISSION_COLUMNS = (
    "can_edit",
    "can_publish",
    "can_staff",
    "can_documents",
    "can_finance",
    "can_recap",
)


def _rules_dict(raw):
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            value = json.loads(raw)
            return dict(value) if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _resolve_org(value, by_id, by_slug, by_name):
    if isinstance(value, dict):
        for key in ("id", "structure_id", "organization_id"):
            raw_id = value.get(key)
            if raw_id is not None and str(raw_id).isdigit():
                found = by_id.get(int(raw_id))
                if found is not None:
                    return found
        value = value.get("slug") or value.get("name")
    if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
        return by_id.get(int(value))
    if not isinstance(value, str) or not value.strip():
        return None
    needle = value.strip().lower()
    return by_slug.get(needle) or by_name.get(needle)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "event_structures" not in tables:
        op.create_table(
            "event_structures",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("event_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=16), nullable=False, server_default="COHOST"),
            sa.Column("can_edit", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("can_publish", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("can_staff", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("can_documents", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("can_finance", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("can_recap", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by_user_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["app_users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_id", "organization_id", name="uq_event_structures_event_org"),
            sa.CheckConstraint("role IN ('OWNER', 'COHOST')", name="ck_event_structures_role"),
        )
        op.create_index("ix_event_structures_event_id", "event_structures", ["event_id"], unique=False)
        op.create_index("ix_event_structures_organization_id", "event_structures", ["organization_id"], unique=False)
        op.create_index("ix_event_structures_role", "event_structures", ["role"], unique=False)
        op.create_index("ix_event_structures_created_at", "event_structures", ["created_at"], unique=False)
        op.create_index("ix_event_structures_updated_at", "event_structures", ["updated_at"], unique=False)
        op.create_index("ix_event_structures_org_role", "event_structures", ["organization_id", "role"], unique=False)

    if "event_manager_settings" not in tables:
        op.create_table(
            "event_manager_settings",
            sa.Column("event_id", sa.Integer(), nullable=False),
            sa.Column("pricing_json", sa.JSON(), nullable=False),
            sa.Column("banner_file_id", sa.String(length=36), nullable=True),
            sa.Column("updated_by_user_id", sa.String(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["banner_file_id"], ["stored_files.id"]),
            sa.ForeignKeyConstraint(["updated_by_user_id"], ["app_users.id"]),
            sa.PrimaryKeyConstraint("event_id"),
        )
        op.create_index("ix_event_manager_settings_banner_file_id", "event_manager_settings", ["banner_file_id"], unique=False)
        op.create_index("ix_event_manager_settings_updated_at", "event_manager_settings", ["updated_at"], unique=False)

    # Idempotent backfill for canonical OWNER links and legacy co_organizers.
    metadata = sa.MetaData()
    events = sa.Table("events", metadata, autoload_with=bind)
    organizations = sa.Table("organizations", metadata, autoload_with=bind)
    links = sa.Table("event_structures", metadata, autoload_with=bind)

    org_rows = bind.execute(sa.select(organizations.c.id, organizations.c.slug, organizations.c.name)).mappings().all()
    by_id = {int(row["id"]): row for row in org_rows}
    by_slug = {str(row["slug"] or "").lower(): row for row in org_rows if row["slug"]}
    by_name = {str(row["name"] or "").lower(): row for row in org_rows if row["name"]}
    existing = {
        (int(row["event_id"]), int(row["organization_id"]))
        for row in bind.execute(sa.select(links.c.event_id, links.c.organization_id)).mappings().all()
    }

    event_rows = bind.execute(sa.select(events.c.id, events.c.host_type, events.c.host_id, events.c.rules_flags)).mappings().all()
    inserts = []
    rules_updates = []
    now = datetime.utcnow()
    for event in event_rows:
        event_id = int(event["id"])
        owner_id = None
        if str(event["host_type"] or "").lower() == "orga" and str(event["host_id"] or "").isdigit():
            owner_id = int(event["host_id"])
            if owner_id in by_id and (event_id, owner_id) not in existing:
                inserts.append({
                    "event_id": event_id,
                    "organization_id": owner_id,
                    "role": "OWNER",
                    "can_edit": True,
                    "can_publish": True,
                    "can_staff": True,
                    "can_documents": True,
                    "can_finance": True,
                    "can_recap": True,
                    "created_by_user_id": None,
                    "created_at": now,
                    "updated_at": now,
                })
                existing.add((event_id, owner_id))

        rules = _rules_dict(event["rules_flags"])
        legacy = rules.pop("co_organizers", None)
        if legacy is None:
            continue
        values = legacy if isinstance(legacy, list) else [legacy]
        unresolved = []
        for value in values:
            org = _resolve_org(value, by_id, by_slug, by_name)
            if org is None:
                unresolved.append(str(value))
                continue
            org_id = int(org["id"])
            if owner_id == org_id or (event_id, org_id) in existing:
                continue
            inserts.append({
                "event_id": event_id,
                "organization_id": org_id,
                "role": "COHOST",
                "can_edit": False,
                "can_publish": False,
                "can_staff": False,
                "can_documents": False,
                "can_finance": False,
                "can_recap": False,
                "created_by_user_id": None,
                "created_at": now,
                "updated_at": now,
            })
            existing.add((event_id, org_id))
        if unresolved:
            rules["legacy_unresolved_co_organizers"] = unresolved
        else:
            rules.pop("legacy_unresolved_co_organizers", None)
        rules_updates.append((event_id, rules))

    if inserts:
        bind.execute(sa.insert(links), inserts)
    for event_id, rules in rules_updates:
        bind.execute(sa.update(events).where(events.c.id == event_id).values(rules_flags=rules))


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "event_manager_settings" in tables:
        op.drop_table("event_manager_settings")
    if "event_structures" in tables:
        op.drop_table("event_structures")
