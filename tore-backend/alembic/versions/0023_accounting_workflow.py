"""Structure accounting budgets, entries and review lock workflow."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0023_accounting_workflow"
down_revision = "0022_forum_per_block_visibility"
branch_labels = None
depends_on = None

def _has_table(name):
    return inspect(op.get_bind()).has_table(name)

def _index(name, table, columns):
    indexes = {row["name"] for row in inspect(op.get_bind()).get_indexes(table)}
    if name not in indexes:
        op.create_index(name, table, columns)

def upgrade():
    if not _has_table("structure_budgets"):
        op.create_table("structure_budgets", sa.Column("id", sa.Integer, primary_key=True), sa.Column("organization_id", sa.Integer, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(180), nullable=False), sa.Column("period", sa.String(32), nullable=False, server_default="ANNUAL"), sa.Column("status", sa.String(16), nullable=False, server_default="COLLECTING"), sa.Column("notes", sa.Text), sa.Column("created_by_user_id", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime, nullable=False), sa.Column("updated_at", sa.DateTime, nullable=False), sa.Column("locked_at", sa.DateTime))
    _index("ix_structure_budgets_organization_id", "structure_budgets", ["organization_id"])
    _index("ix_structure_budgets_status", "structure_budgets", ["status"])
    if not _has_table("budget_categories"):
        op.create_table("budget_categories", sa.Column("id", sa.Integer, primary_key=True), sa.Column("budget_id", sa.Integer, sa.ForeignKey("structure_budgets.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("budget_cents", sa.Integer, nullable=False, server_default="0"), sa.Column("notes", sa.Text))
    _index("ix_budget_categories_budget_id", "budget_categories", ["budget_id"])
    if not _has_table("accounting_entries"):
        op.create_table("accounting_entries", sa.Column("id", sa.Integer, primary_key=True), sa.Column("organization_id", sa.Integer, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False), sa.Column("budget_id", sa.Integer, sa.ForeignKey("structure_budgets.id", ondelete="SET NULL")), sa.Column("event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="SET NULL")), sa.Column("category", sa.String(120), nullable=False), sa.Column("entry_type", sa.String(16), nullable=False), sa.Column("amount_cents", sa.Integer, nullable=False), sa.Column("entry_date", sa.DateTime, nullable=False), sa.Column("notes", sa.Text), sa.Column("attachment_url", sa.String(1000)), sa.Column("created_by_user_id", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime, nullable=False))
    for name, table, cols in [("ix_accounting_entries_organization_id", "accounting_entries", ["organization_id"]), ("ix_accounting_entries_budget_id", "accounting_entries", ["budget_id"]), ("ix_accounting_entries_event_id", "accounting_entries", ["event_id"])]: _index(name, table, cols)

def downgrade():
    op.drop_table("accounting_entries"); op.drop_table("budget_categories"); op.drop_table("structure_budgets")
