"""add secure scoped operational access metadata

Revision ID: 0009_scoped_operational_access
Revises: 0008_unified_profile_affiliations
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0009_scoped_operational_access"
down_revision = "0008_unified_profile_affiliations"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}


def _add_missing(table_name: str, columns: list[sa.Column]) -> None:
    existing = _columns(table_name)
    for column in columns:
        if column.name not in existing:
            op.add_column(table_name, column)


def _add_index(table_name: str, name: str, columns: list[str], *, unique: bool = False) -> None:
    if name not in _indexes(table_name):
        op.create_index(name, table_name, columns, unique=unique)


def upgrade() -> None:
    _add_missing("event_staff_invite_codes", [
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("target_user_id", sa.String(), nullable=True),
        sa.Column("actions_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("accepted_by_user_id", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    ])
    op.execute("UPDATE event_staff_invite_codes SET updated_at = COALESCE(updated_at, created_at)")
    _add_index("event_staff_invite_codes", "ix_event_staff_invite_codes_token_hash", ["token_hash"], unique=True)
    _add_index("event_staff_invite_codes", "ix_event_staff_invite_codes_target_user_id", ["target_user_id"])
    _add_index("event_staff_invite_codes", "ix_event_staff_invite_codes_accepted_at", ["accepted_at"])
    _add_index("event_staff_invite_codes", "ix_event_staff_invite_codes_accepted_by_user_id", ["accepted_by_user_id"])
    _add_index("event_staff_invite_codes", "ix_event_staff_invite_codes_updated_at", ["updated_at"])

    _add_missing("partner_bar_access", [
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("actions_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="PARTNER_ADMIN"),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by_user_id", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    ])
    op.execute("UPDATE partner_bar_access SET updated_at = COALESCE(updated_at, created_at)")
    for name, columns in [
        ("ix_partner_bar_access_status", ["status"]),
        ("ix_partner_bar_access_starts_at", ["starts_at"]),
        ("ix_partner_bar_access_expires_at", ["expires_at"]),
        ("ix_partner_bar_access_source", ["source"]),
        ("ix_partner_bar_access_revoked_at", ["revoked_at"]),
        ("ix_partner_bar_access_updated_at", ["updated_at"]),
    ]:
        _add_index("partner_bar_access", name, columns)


def downgrade() -> None:
    for name in [
        "ix_partner_bar_access_updated_at", "ix_partner_bar_access_revoked_at",
        "ix_partner_bar_access_source", "ix_partner_bar_access_expires_at",
        "ix_partner_bar_access_starts_at", "ix_partner_bar_access_status",
    ]:
        op.drop_index(name, table_name="partner_bar_access")
    with op.batch_alter_table("partner_bar_access") as batch:
        for name in [
            "updated_at", "revoked_by_user_id", "revoked_at", "source",
            "expires_at", "starts_at", "actions_json", "status",
        ]:
            batch.drop_column(name)

    for name in [
        "ix_event_staff_invite_codes_updated_at",
        "ix_event_staff_invite_codes_accepted_by_user_id",
        "ix_event_staff_invite_codes_accepted_at",
        "ix_event_staff_invite_codes_target_user_id",
        "ix_event_staff_invite_codes_token_hash",
    ]:
        op.drop_index(name, table_name="event_staff_invite_codes")
    with op.batch_alter_table("event_staff_invite_codes") as batch:
        for name in [
            "updated_at", "accepted_by_user_id", "accepted_at", "used_count",
            "max_uses", "actions_json", "target_user_id", "token_hash",
        ]:
            batch.drop_column(name)
