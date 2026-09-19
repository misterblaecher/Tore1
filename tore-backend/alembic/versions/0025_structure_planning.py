"""Structure planning calendar and member assignments."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
revision = "0025_structure_planning"
down_revision = "0024_versioned_folklore_pages"
branch_labels = None
depends_on = None
def upgrade():
    bind = op.get_bind()
    if not inspect(bind).has_table("structure_planning_items"):
        op.create_table("structure_planning_items", sa.Column("id", sa.Integer, primary_key=True), sa.Column("organization_id", sa.Integer, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False), sa.Column("event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="SET NULL")), sa.Column("title", sa.String(180), nullable=False), sa.Column("kind", sa.String(16), nullable=False, server_default="OTHER"), sa.Column("starts_at", sa.DateTime, nullable=False), sa.Column("ends_at", sa.DateTime), sa.Column("recurrence", sa.String(32)), sa.Column("reminder_minutes", sa.Integer), sa.Column("notes", sa.Text), sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("created_by_user_id", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime, nullable=False), sa.Column("updated_at", sa.DateTime, nullable=False))
    if not inspect(bind).has_table("structure_planning_assignees"):
        op.create_table("structure_planning_assignees", sa.Column("id", sa.Integer, primary_key=True), sa.Column("planning_item_id", sa.Integer, sa.ForeignKey("structure_planning_items.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.String(120), nullable=False))
    item_indexes = {row["name"] for row in inspect(bind).get_indexes("structure_planning_items")}
    assignee_indexes = {row["name"] for row in inspect(bind).get_indexes("structure_planning_assignees")}
    if "ix_structure_planning_items_organization_id" not in item_indexes: op.create_index("ix_structure_planning_items_organization_id", "structure_planning_items", ["organization_id"])
    if "ix_structure_planning_items_starts_at" not in item_indexes: op.create_index("ix_structure_planning_items_starts_at", "structure_planning_items", ["starts_at"])
    if "ix_structure_planning_assignees_planning_item_id" not in assignee_indexes: op.create_index("ix_structure_planning_assignees_planning_item_id", "structure_planning_assignees", ["planning_item_id"])
def downgrade():
    op.drop_table("structure_planning_assignees"); op.drop_table("structure_planning_items")
