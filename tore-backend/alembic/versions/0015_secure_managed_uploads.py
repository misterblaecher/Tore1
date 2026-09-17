"""add secure managed uploads

Revision ID: 0015_secure_managed_uploads
Revises: 0014_structure_capability_rbac
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0015_secure_managed_uploads"
down_revision = "0014_structure_capability_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "stored_files" in inspector.get_table_names():
        return
    op.create_table(
        "stored_files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=127), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("storage_backend", sa.String(length=16), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_stored_files_storage_key"),
    )
    op.create_index("ix_stored_files_organization_id", "stored_files", ["organization_id"], unique=False)
    op.create_index("ix_stored_files_mime_type", "stored_files", ["mime_type"], unique=False)
    op.create_index("ix_stored_files_visibility", "stored_files", ["visibility"], unique=False)
    op.create_index("ix_stored_files_checksum_sha256", "stored_files", ["checksum_sha256"], unique=False)
    op.create_index("ix_stored_files_purpose", "stored_files", ["purpose"], unique=False)
    op.create_index("ix_stored_files_created_at", "stored_files", ["created_at"], unique=False)
    op.create_index("ix_stored_files_updated_at", "stored_files", ["updated_at"], unique=False)
    op.create_index("ix_stored_files_deleted_at", "stored_files", ["deleted_at"], unique=False)
    op.create_index("ix_stored_files_org_visibility", "stored_files", ["organization_id", "visibility", "deleted_at"], unique=False)
    op.create_index("ix_stored_files_owner", "stored_files", ["owner_user_id", "deleted_at"], unique=False)


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "stored_files" in inspector.get_table_names():
        op.drop_table("stored_files")
