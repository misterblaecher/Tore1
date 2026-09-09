"""add the incremental Forum Structure layer

Revision ID: 0010_forum_structure_mvp
Revises: 0009_scoped_operational_access
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0010_forum_structure_mvp"
down_revision = "0009_scoped_operational_access"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}


def _add_columns(table_name: str, columns: list[sa.Column]) -> None:
    existing = _columns(table_name)
    for column in columns:
        if column.name not in existing:
            op.add_column(table_name, column)


def _index(name: str, table: str, columns: list[str]) -> None:
    if name not in _indexes(table):
        op.create_index(name, table, columns)


def _create_table(name: str, *columns: sa.Column, indexes: list[tuple[str, list[str]]] | None = None, uniques: list[sa.UniqueConstraint] | None = None) -> None:
    if inspect(op.get_bind()).has_table(name):
        return
    op.create_table(name, *columns, *(uniques or []))
    for index_name, index_columns in indexes or []:
        op.create_index(index_name, name, index_columns)


def upgrade() -> None:
    _add_columns("organizations", [
        sa.Column("logo_url", sa.String(length=512), nullable=True),
        sa.Column("banner_url", sa.String(length=512), nullable=True),
        sa.Column("primary_color", sa.String(length=7), nullable=True),
        sa.Column("secondary_color", sa.String(length=7), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=64), nullable=True),
        sa.Column("social_links_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("public_content_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("visibility_settings_json", sa.JSON(), nullable=False, server_default="{}"),
    ])

    _create_table(
        "structure_discussion_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        uniques=[sa.UniqueConstraint("organization_id", "slug", name="uq_structure_discussion_category_slug")],
        indexes=[
            ("ix_structure_discussion_categories_organization_id", ["organization_id"]),
            ("ix_structure_discussion_categories_org_order", ["organization_id", "order_index"]),
            ("ix_structure_discussion_categories_is_archived", ["is_archived"]),
        ],
    )
    _create_table(
        "structure_discussion_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("structure_discussion_categories.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("visibility", sa.String(length=24), nullable=False, server_default="STRUCTURE_MEMBERS"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        uniques=[sa.UniqueConstraint("organization_id", "slug", name="uq_structure_discussion_channel_slug")],
        indexes=[
            ("ix_structure_discussion_channels_organization_id", ["organization_id"]),
            ("ix_structure_discussion_channels_category", ["category_id", "is_archived"]),
            ("ix_structure_discussion_channels_visibility", ["visibility"]),
        ],
    )
    _create_table(
        "structure_discussion_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("structure_discussion_channels.id"), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        indexes=[
            ("ix_structure_discussion_posts_organization_id", ["organization_id"]),
            ("ix_structure_discussion_posts_channel_id", ["channel_id"]),
            ("ix_structure_discussion_posts_feed", ["organization_id", "channel_id", "is_archived", "created_at"]),
        ],
    )
    _create_table(
        "structure_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_url", sa.String(length=1000), nullable=False),
        sa.Column("folder", sa.String(length=120), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("visibility", sa.String(length=24), nullable=False, server_default="STRUCTURE_MEMBERS"),
        sa.Column("uploaded_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        indexes=[
            ("ix_structure_documents_organization_id", ["organization_id"]),
            ("ix_structure_documents_org_visibility", ["organization_id", "visibility", "archived_at"]),
            ("ix_structure_documents_org_folder", ["organization_id", "folder"]),
            ("ix_structure_documents_event_id", ["event_id"]),
        ],
    )
    _create_table(
        "structure_albums",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.String(length=1000), nullable=True),
        sa.Column("visibility", sa.String(length=24), nullable=False, server_default="STRUCTURE_MEMBERS"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        indexes=[
            ("ix_structure_albums_organization_id", ["organization_id"]),
            ("ix_structure_albums_org_status", ["organization_id", "status", "visibility"]),
            ("ix_structure_albums_event_id", ["event_id"]),
        ],
    )
    _create_table(
        "structure_media",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("album_id", sa.Integer(), sa.ForeignKey("structure_albums.id"), nullable=False),
        sa.Column("media_url", sa.String(length=1000), nullable=False),
        sa.Column("media_type", sa.String(length=24), nullable=False, server_default="IMAGE"),
        sa.Column("caption", sa.String(length=280), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        indexes=[
            ("ix_structure_media_album_id", ["album_id"]),
            ("ix_structure_media_album_order", ["album_id", "sort_order"]),
        ],
    )
    _create_table(
        "structure_pages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("visibility", sa.String(length=24), nullable=False, server_default="STRUCTURE_MEMBERS"),
        sa.Column("category", sa.String(length=24), nullable=False, server_default="OTHER"),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        uniques=[sa.UniqueConstraint("organization_id", "slug", name="uq_structure_pages_org_slug")],
        indexes=[
            ("ix_structure_pages_organization_id", ["organization_id"]),
            ("ix_structure_pages_org_visibility", ["organization_id", "visibility", "published_at"]),
            ("ix_structure_pages_category", ["category"]),
        ],
    )


def downgrade() -> None:
    for table, indexes in [
        ("structure_pages", ["ix_structure_pages_category", "ix_structure_pages_org_visibility", "ix_structure_pages_organization_id"]),
        ("structure_media", ["ix_structure_media_album_order", "ix_structure_media_album_id"]),
        ("structure_albums", ["ix_structure_albums_event_id", "ix_structure_albums_org_status", "ix_structure_albums_organization_id"]),
        ("structure_documents", ["ix_structure_documents_event_id", "ix_structure_documents_org_folder", "ix_structure_documents_org_visibility", "ix_structure_documents_organization_id"]),
        ("structure_discussion_posts", ["ix_structure_discussion_posts_feed", "ix_structure_discussion_posts_channel_id", "ix_structure_discussion_posts_organization_id"]),
        ("structure_discussion_channels", ["ix_structure_discussion_channels_visibility", "ix_structure_discussion_channels_category", "ix_structure_discussion_channels_organization_id"]),
        ("structure_discussion_categories", ["ix_structure_discussion_categories_is_archived", "ix_structure_discussion_categories_org_order", "ix_structure_discussion_categories_organization_id"]),
    ]:
        if inspect(op.get_bind()).has_table(table):
            for name in indexes:
                if name in _indexes(table):
                    op.drop_index(name, table_name=table)
            op.drop_table(table)
    for name in [
        "visibility_settings_json", "public_content_json", "social_links_json",
        "contact_phone", "contact_email", "address", "secondary_color",
        "primary_color", "banner_url", "logo_url",
    ]:
        if name in _columns("organizations"):
            op.drop_column("organizations", name)
