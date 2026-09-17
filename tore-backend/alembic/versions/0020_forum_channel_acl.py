"""Persistent per-channel role/capability/member ACLs."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
revision="0020_forum_channel_acl"
down_revision="0019_structure_invitations"
branch_labels=None
depends_on=None

def _tables(): return set(inspect(op.get_bind()).get_table_names())
def _indexes(table): return {str(x.get("name")) for x in inspect(op.get_bind()).get_indexes(table) if x.get("name")} if table in _tables() else set()
def _index(name,table,cols):
    if name not in _indexes(table): op.create_index(name,table,cols)

def upgrade():
    if "structure_channel_acls" not in _tables():
        op.create_table("structure_channel_acls",sa.Column("channel_id",sa.Integer(),sa.ForeignKey("structure_discussion_channels.id"),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("enabled",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("updated_by_user_id",sa.String(),sa.ForeignKey("app_users.id")),sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("updated_at",sa.DateTime(),nullable=False))
    _index("ix_structure_channel_acls_org_enabled","structure_channel_acls",["organization_id","enabled"])
    if "structure_channel_acl_grants" not in _tables():
        op.create_table("structure_channel_acl_grants",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("channel_id",sa.Integer(),sa.ForeignKey("structure_discussion_channels.id"),nullable=False),sa.Column("subject_type",sa.String(16),nullable=False),sa.Column("subject_key",sa.String(160),nullable=False),sa.Column("created_by_user_id",sa.String(),sa.ForeignKey("app_users.id")),sa.Column("created_at",sa.DateTime(),nullable=False),sa.UniqueConstraint("channel_id","subject_type","subject_key",name="uq_structure_channel_acl_grant_subject"),sa.CheckConstraint("subject_type IN ('ROLE','CAPABILITY','MEMBER')",name="ck_structure_channel_acl_grant_subject_type"))
    _index("ix_structure_channel_acl_grants_lookup","structure_channel_acl_grants",["organization_id","channel_id","subject_type"])
    _index("ix_structure_channel_acl_grants_subject_key","structure_channel_acl_grants",["subject_key"])

def downgrade():
    if "structure_channel_acl_grants" in _tables(): op.drop_table("structure_channel_acl_grants")
    if "structure_channel_acls" in _tables(): op.drop_table("structure_channel_acls")
