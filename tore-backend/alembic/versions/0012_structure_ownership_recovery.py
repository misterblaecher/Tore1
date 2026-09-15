"""secure structure ownership, transfers, recovery and freezes

Revision ID: 0012_structure_ownership_recovery
Revises: 0011_shared_profile_oripeaux
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0012_structure_ownership_recovery"
down_revision = "0011_shared_profile_oripeaux"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("structure_ownership"):
        op.create_table(
            "structure_ownership",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("primary_owner_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("recovery_owner_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=True),
            sa.Column("is_frozen", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("keep_public_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("frozen_reason", sa.Text(), nullable=True),
            sa.Column("frozen_at", sa.DateTime(), nullable=True),
            sa.Column("frozen_by", sa.String(length=120), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("organization_id", name="uq_structure_ownership_org"),
        )
        op.create_index("ix_structure_ownership_organization_id", "structure_ownership", ["organization_id"])
        op.create_index("ix_structure_ownership_primary", "structure_ownership", ["primary_owner_user_id"])
        op.create_index("ix_structure_ownership_recovery", "structure_ownership", ["recovery_owner_user_id"])
        op.create_index("ix_structure_ownership_is_frozen", "structure_ownership", ["is_frozen"])
        op.create_index("ix_structure_ownership_frozen_at", "structure_ownership", ["frozen_at"])
        op.create_index("ix_structure_ownership_updated_at", "structure_ownership", ["updated_at"])

    if not _has_table("structure_ownership_transfers"):
        op.create_table(
            "structure_ownership_transfers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("from_owner_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("to_owner_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("requested_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="REQUESTED"),
            sa.Column("requested_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
            sa.Column("cancelled_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=True),
        )
        op.create_index("ix_structure_ownership_transfers_organization_id", "structure_ownership_transfers", ["organization_id"])
        op.create_index("ix_structure_ownership_transfers_status", "structure_ownership_transfers", ["status"])
        op.create_index("ix_structure_transfer_org_status", "structure_ownership_transfers", ["organization_id", "status"])
        op.create_index("ix_structure_transfer_target_status", "structure_ownership_transfers", ["to_owner_user_id", "status"])
        op.create_index("ix_structure_ownership_transfers_expires_at", "structure_ownership_transfers", ["expires_at"])

    if not _has_table("structure_recovery_requests"):
        op.create_table(
            "structure_recovery_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("requested_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="REQUESTED"),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("requested_at", sa.DateTime(), nullable=False),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=True),
            sa.Column("resolved_by_admin", sa.String(length=120), nullable=True),
            sa.Column("resolution_reason", sa.Text(), nullable=True),
        )
        op.create_index("ix_structure_recovery_requests_organization_id", "structure_recovery_requests", ["organization_id"])
        op.create_index("ix_structure_recovery_requests_requested_by_user_id", "structure_recovery_requests", ["requested_by_user_id"])
        op.create_index("ix_structure_recovery_requests_status", "structure_recovery_requests", ["status"])
        op.create_index("ix_structure_recovery_org_status", "structure_recovery_requests", ["organization_id", "status"])
        op.create_index("ix_structure_recovery_requester_status", "structure_recovery_requests", ["requested_by_user_id", "status"])


def downgrade() -> None:
    for table in ("structure_recovery_requests", "structure_ownership_transfers", "structure_ownership"):
        if _has_table(table):
            op.drop_table(table)
