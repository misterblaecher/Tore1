"""add music + committee v1 tables for prod migration

Revision ID: 0006_music_committee_v1_tables
Revises: 0005_auth_otp_codes
Create Date: 2026-02-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0006_music_committee_v1_tables"
down_revision = "0005_auth_otp_codes"
branch_labels = None
depends_on = None


def _index_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "event_music_suggestions" not in tables:
        op.create_table(
            "event_music_suggestions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("event_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("provider", sa.String(length=24), nullable=False),
            sa.Column("external_url", sa.String(length=512), nullable=False),
            sa.Column("title", sa.String(length=180), nullable=False, server_default=""),
            sa.Column("artist", sa.String(length=180), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    names = _index_names("event_music_suggestions")
    if "ix_event_music_suggestions_event_id" not in names:
        op.create_index("ix_event_music_suggestions_event_id", "event_music_suggestions", ["event_id"], unique=False)
    if "ix_event_music_suggestions_user_id" not in names:
        op.create_index("ix_event_music_suggestions_user_id", "event_music_suggestions", ["user_id"], unique=False)
    if "ix_event_music_suggestions_provider" not in names:
        op.create_index("ix_event_music_suggestions_provider", "event_music_suggestions", ["provider"], unique=False)
    if "ix_event_music_suggestions_created_at" not in names:
        op.create_index("ix_event_music_suggestions_created_at", "event_music_suggestions", ["created_at"], unique=False)
    op.execute("CREATE INDEX IF NOT EXISTS ix_event_music_suggestions_event_created ON event_music_suggestions (event_id, created_at)")

    if "event_music_suggestion_votes" not in tables:
        op.create_table(
            "event_music_suggestion_votes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("event_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("suggestion_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
            sa.ForeignKeyConstraint(["suggestion_id"], ["event_music_suggestions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_id", "user_id", "suggestion_id", name="uq_event_music_suggestion_vote"),
        )
    names = _index_names("event_music_suggestion_votes")
    if "ix_event_music_suggestion_votes_event_id" not in names:
        op.create_index("ix_event_music_suggestion_votes_event_id", "event_music_suggestion_votes", ["event_id"], unique=False)
    if "ix_event_music_suggestion_votes_user_id" not in names:
        op.create_index("ix_event_music_suggestion_votes_user_id", "event_music_suggestion_votes", ["user_id"], unique=False)
    if "ix_event_music_suggestion_votes_suggestion_id" not in names:
        op.create_index("ix_event_music_suggestion_votes_suggestion_id", "event_music_suggestion_votes", ["suggestion_id"], unique=False)
    if "ix_event_music_suggestion_votes_created_at" not in names:
        op.create_index("ix_event_music_suggestion_votes_created_at", "event_music_suggestion_votes", ["created_at"], unique=False)
    op.execute("CREATE INDEX IF NOT EXISTS ix_event_music_suggestion_votes_event_created ON event_music_suggestion_votes (event_id, created_at)")

    if "event_music_rounds" not in tables:
        op.create_table(
            "event_music_rounds",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("event_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="OPEN"),
            sa.Column("duration_sec", sa.Integer(), nullable=False, server_default="120"),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("ends_at", sa.DateTime(), nullable=False),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
            sa.Column("winner_candidate_id", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
            sa.ForeignKeyConstraint(["winner_candidate_id"], ["event_music_candidates.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    names = _index_names("event_music_rounds")
    for index_name, cols in [
        ("ix_event_music_rounds_event_id", ["event_id"]),
        ("ix_event_music_rounds_status", ["status"]),
        ("ix_event_music_rounds_started_at", ["started_at"]),
        ("ix_event_music_rounds_ends_at", ["ends_at"]),
        ("ix_event_music_rounds_closed_at", ["closed_at"]),
        ("ix_event_music_rounds_winner_candidate_id", ["winner_candidate_id"]),
        ("ix_event_music_rounds_created_at", ["created_at"]),
    ]:
        if index_name not in names:
            op.create_index(index_name, "event_music_rounds", cols, unique=False)
    op.execute("CREATE INDEX IF NOT EXISTS ix_event_music_rounds_event_created ON event_music_rounds (event_id, created_at)")

    if "committee_posts" not in tables:
        op.create_table(
            "committee_posts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("committee_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_by", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["committee_id"], ["committees.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["app_users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    names = _index_names("committee_posts")
    for index_name, cols in [
        ("ix_committee_posts_committee_id", ["committee_id"]),
        ("ix_committee_posts_is_pinned", ["is_pinned"]),
        ("ix_committee_posts_is_deleted", ["is_deleted"]),
        ("ix_committee_posts_created_by", ["created_by"]),
        ("ix_committee_posts_created_at", ["created_at"]),
        ("ix_committee_posts_updated_at", ["updated_at"]),
        ("ix_committee_posts_feed", ["committee_id", "is_deleted", "is_pinned", "created_at"]),
    ]:
        if index_name not in names:
            op.create_index(index_name, "committee_posts", cols, unique=False)
    op.execute("CREATE INDEX IF NOT EXISTS ix_committee_posts_committee_created ON committee_posts (committee_id, created_at)")

    if "committee_calendar_items" not in tables:
        op.create_table(
            "committee_calendar_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("committee_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("date", sa.String(length=10), nullable=False),
            sa.Column("location", sa.String(length=180), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["committee_id"], ["committees.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["app_users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    names = _index_names("committee_calendar_items")
    for index_name, cols in [
        ("ix_committee_calendar_items_committee_id", ["committee_id"]),
        ("ix_committee_calendar_items_date", ["date"]),
        ("ix_committee_calendar_items_created_by", ["created_by"]),
        ("ix_committee_calendar_items_created_at", ["created_at"]),
        ("ix_committee_calendar_items_updated_at", ["updated_at"]),
        ("ix_committee_calendar_items_feed", ["committee_id", "date", "id"]),
    ]:
        if index_name not in names:
            op.create_index(index_name, "committee_calendar_items", cols, unique=False)
    op.execute("CREATE INDEX IF NOT EXISTS ix_committee_calendar_items_committee_date ON committee_calendar_items (committee_id, date)")

    if "committee_expenses" not in tables:
        op.create_table(
            "committee_expenses",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("committee_id", sa.Integer(), nullable=False),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(length=180), nullable=False),
            sa.Column("category", sa.String(length=120), nullable=False),
            sa.Column("date", sa.String(length=10), nullable=False),
            sa.Column("created_by", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["committee_id"], ["committees.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["app_users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    names = _index_names("committee_expenses")
    for index_name, cols in [
        ("ix_committee_expenses_committee_id", ["committee_id"]),
        ("ix_committee_expenses_category", ["category"]),
        ("ix_committee_expenses_date", ["date"]),
        ("ix_committee_expenses_created_by", ["created_by"]),
        ("ix_committee_expenses_created_at", ["created_at"]),
        ("ix_committee_expenses_updated_at", ["updated_at"]),
        ("ix_committee_expenses_feed", ["committee_id", "date", "id"]),
    ]:
        if index_name not in names:
            op.create_index(index_name, "committee_expenses", cols, unique=False)
    op.execute("CREATE INDEX IF NOT EXISTS ix_committee_expenses_committee_date ON committee_expenses (committee_id, date)")


def downgrade() -> None:
    for table_name in [
        "committee_expenses",
        "committee_calendar_items",
        "committee_posts",
        "event_music_rounds",
        "event_music_suggestion_votes",
        "event_music_suggestions",
    ]:
        op.drop_table(table_name)
