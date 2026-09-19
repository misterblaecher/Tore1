"""Restore workspace schema skipped by the retired public-event lineage."""

from alembic import op
import sqlalchemy as sa


revision = "0029_legacy_workspace_parity"
down_revision = "0028_merge_retired_public_event_lineage"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "structure_discussion_posts" in tables:
        columns = {
            column["name"]
            for column in sa.inspect(op.get_bind()).get_columns("structure_discussion_posts")
        }
        if "parent_id" not in columns:
            op.add_column(
                "structure_discussion_posts",
                sa.Column("parent_id", sa.Integer(), nullable=True),
            )
        if "document_ids" not in columns:
            op.add_column(
                "structure_discussion_posts",
                sa.Column("document_ids", sa.JSON(), nullable=True),
            )

    if "structure_discussion_reactions" not in _tables():
        op.create_table(
            "structure_discussion_reactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "post_id",
                sa.Integer(),
                sa.ForeignKey("structure_discussion_posts.id"),
                nullable=False,
            ),
            sa.Column("user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("emoji", sa.String(16), nullable=False),
            sa.UniqueConstraint("post_id", "user_id", "emoji", name="uq_discussion_reaction"),
        )
        op.create_index(
            "ix_structure_discussion_reactions_post_id",
            "structure_discussion_reactions",
            ["post_id"],
        )

    if "structure_notifications" not in _tables():
        op.create_table(
            "structure_notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("user_id", sa.String(120), nullable=False),
            sa.Column("type", sa.String(32), nullable=False),
            sa.Column("title", sa.String(180), nullable=False),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("target_path", sa.String(500), nullable=True),
            sa.Column("target_permission", sa.String(64), nullable=True),
            sa.Column("target_id", sa.String(120), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("read_at", sa.DateTime(), nullable=True),
        )
        for name, columns in (
            ("ix_structure_notifications_organization_id", ["organization_id"]),
            ("ix_structure_notifications_user_id", ["user_id"]),
            ("ix_structure_notifications_type", ["type"]),
            ("ix_structure_notifications_created_at", ["created_at"]),
            ("ix_structure_notifications_read_at", ["read_at"]),
        ):
            op.create_index(name, "structure_notifications", columns)


def downgrade() -> None:
    # This parity migration may repair pre-existing objects, so destructive
    # downgrade operations would risk deleting user data.
    pass
