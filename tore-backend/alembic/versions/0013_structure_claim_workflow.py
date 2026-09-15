"""Add reviewed ownership claims for existing structures."""

from alembic import op
import sqlalchemy as sa


revision = "0013_structure_claim_workflow"
down_revision = "0012_discussion_workspace"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "structure_claims" in inspector.get_table_names():
        return

    op.create_table(
        "structure_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "structure_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "claimant_user_id",
            sa.String(),
            sa.ForeignKey("app_users.id"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "reviewer_user_id",
            sa.String(),
            sa.ForeignKey("app_users.id"),
            nullable=True,
        ),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING','NEEDS_INFO','APPROVED','REJECTED','CANCELLED')",
            name="ck_structure_claims_status",
        ),
    )
    op.create_index(
        "ix_structure_claims_structure_id",
        "structure_claims",
        ["structure_id"],
    )
    op.create_index(
        "ix_structure_claims_claimant_user_id",
        "structure_claims",
        ["claimant_user_id"],
    )
    op.create_index(
        "ix_structure_claims_reviewer_user_id",
        "structure_claims",
        ["reviewer_user_id"],
    )
    op.create_index(
        "ix_structure_claims_status",
        "structure_claims",
        ["status"],
    )
    op.create_index(
        "ix_structure_claims_structure_status",
        "structure_claims",
        ["structure_id", "status"],
    )
    op.create_index(
        "ix_structure_claims_claimant_status",
        "structure_claims",
        ["claimant_user_id", "status"],
    )
    op.create_index(
        "ix_structure_claims_created_at",
        "structure_claims",
        ["created_at"],
    )
    op.create_index(
        "ix_structure_claims_updated_at",
        "structure_claims",
        ["updated_at"],
    )
    op.create_index(
        "ix_structure_claims_reviewed_at",
        "structure_claims",
        ["reviewed_at"],
    )
    op.create_index(
        "ix_structure_claims_decided_at",
        "structure_claims",
        ["decided_at"],
    )
    op.create_index(
        "ix_structure_claims_cancelled_at",
        "structure_claims",
        ["cancelled_at"],
    )


def downgrade():
    if "structure_claims" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("structure_claims")
