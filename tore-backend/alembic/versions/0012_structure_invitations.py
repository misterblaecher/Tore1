"""Add structure member invitations.

Revision ID: 0012_structure_invitations
Revises: 0011_shared_profile_oripeaux
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_structure_invitations"
down_revision = "0011_shared_profile_oripeaux"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "structure_invitations",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("structure_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_role", sa.String(length=32), nullable=False, server_default="MEMBER"),
        sa.Column("invited_by", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("declined_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_structure_invitations_structure_id", "structure_invitations", ["structure_id"])
    op.create_index("ix_structure_invitations_email", "structure_invitations", ["email"])
    op.create_index("ix_structure_invitations_token_hash", "structure_invitations", ["token_hash"], unique=True)
    op.create_index("ix_structure_invitations_invited_role", "structure_invitations", ["invited_role"])
    op.create_index("ix_structure_invitations_invited_by", "structure_invitations", ["invited_by"])
    op.create_index("ix_structure_invitations_expires_at", "structure_invitations", ["expires_at"])
    op.create_index("ix_structure_invitations_accepted_at", "structure_invitations", ["accepted_at"])
    op.create_index("ix_structure_invitations_declined_at", "structure_invitations", ["declined_at"])
    op.create_index("ix_structure_invitations_revoked_at", "structure_invitations", ["revoked_at"])
    op.create_index("ix_structure_invitations_created_at", "structure_invitations", ["created_at"])
    op.create_index("ix_structure_invitations_structure_email", "structure_invitations", ["structure_id", "email"])


def downgrade() -> None:
    op.drop_index("ix_structure_invitations_structure_email", table_name="structure_invitations")
    op.drop_index("ix_structure_invitations_created_at", table_name="structure_invitations")
    op.drop_index("ix_structure_invitations_revoked_at", table_name="structure_invitations")
    op.drop_index("ix_structure_invitations_declined_at", table_name="structure_invitations")
    op.drop_index("ix_structure_invitations_accepted_at", table_name="structure_invitations")
    op.drop_index("ix_structure_invitations_expires_at", table_name="structure_invitations")
    op.drop_index("ix_structure_invitations_invited_by", table_name="structure_invitations")
    op.drop_index("ix_structure_invitations_invited_role", table_name="structure_invitations")
    op.drop_index("ix_structure_invitations_token_hash", table_name="structure_invitations")
    op.drop_index("ix_structure_invitations_email", table_name="structure_invitations")
    op.drop_index("ix_structure_invitations_structure_id", table_name="structure_invitations")
    op.drop_table("structure_invitations")
