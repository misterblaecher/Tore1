"""create auth_otp_codes table

Revision ID: 0005_auth_otp_codes
Revises: 0004_app_user_account_mode
Create Date: 2026-02-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "0005_auth_otp_codes"
down_revision = "0004_app_user_account_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    tables = set(inspector.get_table_names())
    if "auth_otp_codes" not in tables:
        op.create_table(
            "auth_otp_codes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("code_hash", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
            sa.Column("request_ip", sa.String(length=64), nullable=True),
            sa.Column("request_id", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    indexes = {index["name"] for index in inspector.get_indexes("auth_otp_codes")}
    if "ix_auth_otp_codes_email" not in indexes:
        op.create_index("ix_auth_otp_codes_email", "auth_otp_codes", ["email"], unique=False)
    if "ix_auth_otp_codes_code_hash" not in indexes:
        op.create_index("ix_auth_otp_codes_code_hash", "auth_otp_codes", ["code_hash"], unique=False)
    if "ix_auth_otp_codes_user_id" not in indexes:
        op.create_index("ix_auth_otp_codes_user_id", "auth_otp_codes", ["user_id"], unique=False)
    if "ix_auth_otp_codes_expires_at" not in indexes:
        op.create_index("ix_auth_otp_codes_expires_at", "auth_otp_codes", ["expires_at"], unique=False)
    if "ix_auth_otp_codes_used_at" not in indexes:
        op.create_index("ix_auth_otp_codes_used_at", "auth_otp_codes", ["used_at"], unique=False)
    if "ix_auth_otp_codes_created_at" not in indexes:
        op.create_index("ix_auth_otp_codes_created_at", "auth_otp_codes", ["created_at"], unique=False)

    op.execute("CREATE INDEX IF NOT EXISTS ix_auth_otp_email_created_at ON auth_otp_codes (email, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_auth_otp_email_used_at ON auth_otp_codes (email, used_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_auth_otp_expires_at ON auth_otp_codes (expires_at)")


def downgrade() -> None:
    op.drop_table("auth_otp_codes")
