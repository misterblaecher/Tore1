"""add account_requests table

Revision ID: 0003_account_requests
Revises: 0002_event_costs_simple
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_account_requests"
down_revision = "0002_event_costs_simple"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("account_requests"):
        return

    op.create_table(
        "account_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("is_whatsapp", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("committee_name", sa.String(length=180), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="new"),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_requests_created_at", "account_requests", ["created_at"])
    op.create_index("ix_account_requests_email", "account_requests", ["email"])
    op.create_index("ix_account_requests_ip_hash", "account_requests", ["ip_hash"])
    op.create_index("ix_account_requests_role", "account_requests", ["role"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("account_requests"):
        return

    index_names = {idx["name"] for idx in inspector.get_indexes("account_requests")}
    for index_name in [
        "ix_account_requests_role",
        "ix_account_requests_ip_hash",
        "ix_account_requests_email",
        "ix_account_requests_created_at",
    ]:
        if index_name in index_names:
            op.drop_index(index_name, table_name="account_requests")
    op.drop_table("account_requests")
