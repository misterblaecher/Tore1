"""Persistent Event↔Structure cohosting and manager settings."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
revision="0021_event_structure_cohosting"
down_revision="0020_forum_channel_acl"
branch_labels=None
depends_on=None

def _tables(): return set(inspect(op.get_bind()).get_table_names())
def upgrade():
    if "event_structures" not in _tables():
        op.create_table("event_structures",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("event_id",sa.Integer(),sa.ForeignKey("events.id",ondelete="CASCADE"),nullable=False),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("role",sa.String(16),nullable=False,server_default="COHOST"),sa.Column("can_edit",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("can_publish",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("can_staff",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("can_documents",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("can_finance",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("can_recap",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("created_by_user_id",sa.String(),sa.ForeignKey("app_users.id")),sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("updated_at",sa.DateTime(),nullable=False),sa.UniqueConstraint("event_id","organization_id",name="uq_event_structures_event_org"),sa.CheckConstraint("role IN ('OWNER','COHOST')",name="ck_event_structures_role"))
        op.create_index("ix_event_structures_org_role","event_structures",["organization_id","role"])
        op.create_index("ix_event_structures_event_id","event_structures",["event_id"])
    if "event_manager_settings" not in _tables():
        op.create_table("event_manager_settings",sa.Column("event_id",sa.Integer(),sa.ForeignKey("events.id",ondelete="CASCADE"),primary_key=True),sa.Column("pricing_json",sa.JSON(),nullable=False,server_default="[]"),sa.Column("banner_file_id",sa.String(),sa.ForeignKey("stored_files.id")),sa.Column("updated_by_user_id",sa.String(),sa.ForeignKey("app_users.id")),sa.Column("updated_at",sa.DateTime(),nullable=False))

def downgrade():
    if "event_manager_settings" in _tables(): op.drop_table("event_manager_settings")
    if "event_structures" in _tables(): op.drop_table("event_structures")
