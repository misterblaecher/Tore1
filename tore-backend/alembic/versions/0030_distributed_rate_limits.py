"""Add shared rate-limit buckets for multi-instance production enforcement."""

from alembic import op
import sqlalchemy as sa


revision = "0030_distributed_rate_limits"
down_revision = "0029_legacy_workspace_parity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("bucket_key", sa.String(length=128), nullable=False),
        sa.Column("window_started_at_ms", sa.BigInteger(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("updated_at_ms", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("bucket_key"),
    )
    op.create_index(
        "ix_rate_limit_buckets_updated_at_ms",
        "rate_limit_buckets",
        ["updated_at_ms"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_rate_limit_buckets_updated_at_ms", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
