"""add public event pages and recap workflow

Revision ID: 0013_public_event_recap
Revises: 0012_secure_managed_uploads
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0013_public_event_recap"
down_revision = "0012_secure_managed_uploads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "forum_event_pages" in inspector.get_table_names():
        return
    op.create_table(
        "forum_event_pages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("capacity_public", sa.Boolean(), nullable=False),
        sa.Column("cohost_structure_ids_json", sa.JSON(), nullable=False),
        sa.Column("recap_status", sa.String(length=24), nullable=False),
        sa.Column("recap_summary", sa.Text(), nullable=True),
        sa.Column("recap_album_id", sa.Integer(), nullable=True),
        sa.Column("recap_stats_json", sa.JSON(), nullable=False),
        sa.Column("previous_event_id", sa.Integer(), nullable=True),
        sa.Column("next_event_id", sa.Integer(), nullable=True),
        sa.Column("recap_published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["recap_album_id"], ["structure_albums.id"]),
        sa.ForeignKeyConstraint(["previous_event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["next_event_id"], ["events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_forum_event_pages_event"),
        sa.UniqueConstraint("slug", name="uq_forum_event_pages_slug"),
    )
    op.create_index("ix_forum_event_pages_event_id", "forum_event_pages", ["event_id"], unique=False)
    op.create_index("ix_forum_event_pages_slug", "forum_event_pages", ["slug"], unique=False)
    op.create_index("ix_forum_event_pages_recap_status", "forum_event_pages", ["recap_status"], unique=False)
    op.create_index("ix_forum_event_pages_recap_album_id", "forum_event_pages", ["recap_album_id"], unique=False)
    op.create_index("ix_forum_event_pages_previous_event_id", "forum_event_pages", ["previous_event_id"], unique=False)
    op.create_index("ix_forum_event_pages_next_event_id", "forum_event_pages", ["next_event_id"], unique=False)
    op.create_index("ix_forum_event_pages_recap_published_at", "forum_event_pages", ["recap_published_at"], unique=False)
    op.create_index("ix_forum_event_pages_created_at", "forum_event_pages", ["created_at"], unique=False)
    op.create_index("ix_forum_event_pages_updated_at", "forum_event_pages", ["updated_at"], unique=False)


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "forum_event_pages" in inspector.get_table_names():
        op.drop_table("forum_event_pages")
