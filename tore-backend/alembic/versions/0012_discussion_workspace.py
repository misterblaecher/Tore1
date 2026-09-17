"""Persistent discussion threads, document references and reactions."""
from alembic import op
import sqlalchemy as sa

revision = "0012_discussion_workspace"
down_revision = "0011_shared_profile_oripeaux"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("structure_discussion_posts")}
    if "parent_id" not in columns:
        op.add_column("structure_discussion_posts", sa.Column("parent_id", sa.Integer(), nullable=True))
    if "document_ids" not in columns:
        op.add_column("structure_discussion_posts", sa.Column("document_ids", sa.JSON(), nullable=True))
    if "structure_discussion_reactions" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("structure_discussion_reactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("post_id", sa.Integer(), sa.ForeignKey("structure_discussion_posts.id"), nullable=False),
            sa.Column("user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("emoji", sa.String(16), nullable=False),
            sa.UniqueConstraint("post_id", "user_id", "emoji", name="uq_discussion_reaction"))
        op.create_index("ix_structure_discussion_reactions_post_id", "structure_discussion_reactions", ["post_id"])


def downgrade():
    op.drop_table("structure_discussion_reactions")
    op.drop_column("structure_discussion_posts", "document_ids")
    op.drop_column("structure_discussion_posts", "parent_id")
