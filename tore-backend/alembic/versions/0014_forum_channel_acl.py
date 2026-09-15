"""Persistent per-channel role/capability/member ACLs.

Revision ID: 0014_forum_channel_acl
Revises: 0013_forum_backend_foundation
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0014_forum_channel_acl"
down_revision = "0013_forum_backend_foundation"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _indexes(table_name: str) -> set[str]:
    if table_name not in _tables():
        return set()
    return {
        str(index.get("name"))
        for index in inspect(op.get_bind()).get_indexes(table_name)
        if index.get("name")
    }


def _index(name: str, table_name: str, columns: list[str]) -> None:
    if name not in _indexes(table_name):
        op.create_index(name, table_name, columns)


def upgrade() -> None:
    if "structure_channel_acls" not in _tables():
        op.create_table(
            "structure_channel_acls",
            sa.Column("channel_id", sa.Integer(), sa.ForeignKey("structure_discussion_channels.id"), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("updated_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    _index("ix_structure_channel_acls_organization_id", "structure_channel_acls", ["organization_id"])
    _index("ix_structure_channel_acls_enabled", "structure_channel_acls", ["enabled"])
    _index("ix_structure_channel_acls_updated_at", "structure_channel_acls", ["updated_at"])
    _index("ix_structure_channel_acls_org_enabled", "structure_channel_acls", ["organization_id", "enabled"])

    if "structure_channel_acl_grants" not in _tables():
        op.create_table(
            "structure_channel_acl_grants",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("channel_id", sa.Integer(), sa.ForeignKey("structure_discussion_channels.id"), nullable=False),
            sa.Column("subject_type", sa.String(16), nullable=False),
            sa.Column("subject_key", sa.String(160), nullable=False),
            sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "channel_id", "subject_type", "subject_key",
                name="uq_structure_channel_acl_grant_subject",
            ),
            sa.CheckConstraint(
                "subject_type IN ('ROLE','CAPABILITY','MEMBER')",
                name="ck_structure_channel_acl_grant_subject_type",
            ),
        )
    _index("ix_structure_channel_acl_grants_organization_id", "structure_channel_acl_grants", ["organization_id"])
    _index("ix_structure_channel_acl_grants_channel_id", "structure_channel_acl_grants", ["channel_id"])
    _index("ix_structure_channel_acl_grants_subject_type", "structure_channel_acl_grants", ["subject_type"])
    _index("ix_structure_channel_acl_grants_subject_key", "structure_channel_acl_grants", ["subject_key"])
    _index("ix_structure_channel_acl_grants_created_at", "structure_channel_acl_grants", ["created_at"])
    _index(
        "ix_structure_channel_acl_grants_lookup",
        "structure_channel_acl_grants",
        ["organization_id", "channel_id", "subject_type"],
    )


def downgrade() -> None:
    tables = _tables()
    if "structure_channel_acl_grants" in tables:
        op.drop_table("structure_channel_acl_grants")
    if "structure_channel_acls" in tables:
        op.drop_table("structure_channel_acls")
