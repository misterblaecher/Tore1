"""add public event content and bar branding

Revision ID: 0007_public_content_branding
Revises: 0006_music_committee_v1_tables
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0007_public_content_branding"
down_revision = "0006_music_committee_v1_tables"
branch_labels = None
depends_on = None


def _add_missing_columns(table_name: str, columns: list[sa.Column]) -> None:
    existing = {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table_name, column)


def _add_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    existing = {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    _add_missing_columns("events", [
        sa.Column("public_description", sa.Text(), nullable=True),
        sa.Column("short_description", sa.String(length=280), nullable=True),
        sa.Column("banner_url", sa.String(length=512), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=512), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("access_type", sa.String(length=24), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="EUR"),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
    ])
    _add_missing_columns("bars", [
        sa.Column("public_description", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.String(length=512), nullable=True),
        sa.Column("banner_url", sa.String(length=512), nullable=True),
        sa.Column("primary_color", sa.String(length=7), nullable=True),
        sa.Column("secondary_color", sa.String(length=7), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("practical_info", sa.Text(), nullable=True),
        sa.Column("map_url", sa.String(length=512), nullable=True),
        sa.Column("public_modules", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("partner_status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("public_visibility", sa.String(length=16), nullable=False, server_default="PUBLIC"),
    ])
    _add_index_if_missing("bars", "ix_bars_partner_status", ["partner_status"])
    _add_index_if_missing("bars", "ix_bars_public_visibility", ["public_visibility"])


def downgrade() -> None:
    for index_name in ["ix_bars_public_visibility", "ix_bars_partner_status"]:
        op.drop_index(index_name, table_name="bars")
    for column in [
        "public_visibility", "partner_status", "public_modules", "map_url",
        "practical_info", "address", "secondary_color", "primary_color",
        "banner_url", "logo_url", "public_description",
    ]:
        op.drop_column("bars", column)
    for column in [
        "lng", "lat", "city", "address", "currency", "access_type", "capacity",
        "event_type", "thumbnail_url", "banner_url", "short_description", "public_description",
    ]:
        op.drop_column("events", column)
