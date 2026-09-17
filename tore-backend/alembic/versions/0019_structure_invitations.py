"""Structure member invitations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
revision="0019_structure_invitations"
down_revision="0018_structure_claim_workflow"
branch_labels=None
depends_on=None

def upgrade():
    if inspect(op.get_bind()).has_table("structure_invitations"): return
    op.create_table("structure_invitations",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("structure_id",sa.Integer(),sa.ForeignKey("organizations.id"),nullable=False),
        sa.Column("email",sa.String(255),nullable=False),
        sa.Column("token_hash",sa.String(64),nullable=False,unique=True),
        sa.Column("invited_role",sa.String(64),nullable=False,server_default="MEMBER"),
        sa.Column("invited_role_id",sa.Integer(),sa.ForeignKey("structure_roles.id")),
        sa.Column("invited_by",sa.String(),sa.ForeignKey("app_users.id"),nullable=False),
        sa.Column("expires_at",sa.DateTime(),nullable=False),
        sa.Column("accepted_at",sa.DateTime()),sa.Column("declined_at",sa.DateTime()),sa.Column("revoked_at",sa.DateTime()),sa.Column("created_at",sa.DateTime(),nullable=False))
    op.create_index("ix_structure_invitations_structure_email","structure_invitations",["structure_id","email"])
    op.create_index("ix_structure_invitations_token_hash","structure_invitations",["token_hash"],unique=True)

def downgrade():
    if inspect(op.get_bind()).has_table("structure_invitations"): op.drop_table("structure_invitations")
