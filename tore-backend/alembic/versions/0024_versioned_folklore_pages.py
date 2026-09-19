"""Append-only revisions for structure wiki pages."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
revision = "0024_versioned_folklore_pages"
down_revision = "0023_accounting_workflow"
branch_labels = None
depends_on = None
def upgrade():
    if not inspect(op.get_bind()).has_table("structure_page_revisions"):
        op.create_table("structure_page_revisions", sa.Column("id", sa.Integer, primary_key=True), sa.Column("page_id", sa.Integer, sa.ForeignKey("structure_pages.id", ondelete="CASCADE"), nullable=False), sa.Column("version", sa.Integer, nullable=False), sa.Column("content", sa.Text, nullable=False, server_default=""), sa.Column("author_user_id", sa.String(120), nullable=False), sa.Column("message", sa.String(500)), sa.Column("created_at", sa.DateTime, nullable=False))
    indexes = {row["name"] for row in inspect(op.get_bind()).get_indexes("structure_page_revisions")}
    if "ix_structure_page_revisions_page_id" not in indexes: op.create_index("ix_structure_page_revisions_page_id", "structure_page_revisions", ["page_id"])
    if "ix_structure_page_revisions_created_at" not in indexes: op.create_index("ix_structure_page_revisions_created_at", "structure_page_revisions", ["created_at"])
def downgrade():
    op.drop_table("structure_page_revisions")
