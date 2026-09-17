"""Reviewed claims for existing structures."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision="0018_structure_claim_workflow"
down_revision="0017_structure_ownership_recovery"
branch_labels=None
depends_on=None

def upgrade():
    if inspect(op.get_bind()).has_table("structure_claims"): return
    op.create_table("structure_claims",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("structure_id",sa.Integer(),sa.ForeignKey("organizations.id"),nullable=False),
        sa.Column("claimant_user_id",sa.String(),sa.ForeignKey("app_users.id"),nullable=False),
        sa.Column("reason",sa.Text(),nullable=False),sa.Column("evidence_json",sa.JSON(),nullable=False),
        sa.Column("status",sa.String(16),nullable=False,server_default="PENDING"),
        sa.Column("reviewer_user_id",sa.String(),sa.ForeignKey("app_users.id")),sa.Column("review_notes",sa.Text()),
        sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("updated_at",sa.DateTime(),nullable=False),
        sa.Column("reviewed_at",sa.DateTime()),sa.Column("decided_at",sa.DateTime()),sa.Column("cancelled_at",sa.DateTime()),
        sa.CheckConstraint("status IN ('PENDING','NEEDS_INFO','APPROVED','REJECTED','CANCELLED')",name="ck_structure_claims_status"))
    for name,cols in (("ix_structure_claims_structure_status",["structure_id","status"]),("ix_structure_claims_claimant_status",["claimant_user_id","status"]),("ix_structure_claims_created_at",["created_at"])):
        op.create_index(name,"structure_claims",cols)

def downgrade():
    if inspect(op.get_bind()).has_table("structure_claims"): op.drop_table("structure_claims")
