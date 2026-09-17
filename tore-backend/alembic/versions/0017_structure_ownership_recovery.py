"""Structure ownership, transfers, recovery and freeze state."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0017_structure_ownership_recovery"
down_revision = "0016_public_event_recap"
branch_labels = None
depends_on = None


def _has(name):
    return inspect(op.get_bind()).has_table(name)


def upgrade():
    if not _has("structure_ownership"):
        op.create_table("structure_ownership",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, unique=True),
            sa.Column("primary_owner_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("recovery_owner_user_id", sa.String(), sa.ForeignKey("app_users.id")),
            sa.Column("is_frozen", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("keep_public_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("frozen_reason", sa.Text()), sa.Column("frozen_at", sa.DateTime()),
            sa.Column("frozen_by", sa.String(120)), sa.Column("updated_at", sa.DateTime(), nullable=False))
    if not _has("structure_ownership_transfers"):
        op.create_table("structure_ownership_transfers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("from_owner_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("to_owner_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("requested_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="REQUESTED"),
            sa.Column("requested_at", sa.DateTime(), nullable=False), sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("confirmed_at", sa.DateTime()), sa.Column("completed_at", sa.DateTime()),
            sa.Column("cancelled_at", sa.DateTime()), sa.Column("cancelled_by_user_id", sa.String(), sa.ForeignKey("app_users.id")))
    if not _has("structure_recovery_requests"):
        op.create_table("structure_recovery_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("requested_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="REQUESTED"), sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("requested_at", sa.DateTime(), nullable=False), sa.Column("resolved_at", sa.DateTime()),
            sa.Column("resolved_by_user_id", sa.String(), sa.ForeignKey("app_users.id")), sa.Column("resolved_by_admin", sa.String(120)),
            sa.Column("resolution_reason", sa.Text()))


def downgrade():
    for name in ("structure_recovery_requests", "structure_ownership_transfers", "structure_ownership"):
        if _has(name): op.drop_table(name)
