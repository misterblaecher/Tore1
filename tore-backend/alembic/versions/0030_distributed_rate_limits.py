"""Add shared rate-limit buckets for multi-instance production enforcement."""

from alembic import op
import sqlalchemy as sa


revision = "0030_distributed_rate_limits"
down_revision = "0029_legacy_workspace_parity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "rate_limit_buckets" not in inspector.get_table_names():
        op.create_table(
            "rate_limit_buckets",
            sa.Column("bucket_key", sa.String(length=128), nullable=False),
            sa.Column("window_started_at_ms", sa.BigInteger(), nullable=False),
            sa.Column("request_count", sa.Integer(), nullable=False),
            sa.Column("updated_at_ms", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("bucket_key"),
        )
        inspector = sa.inspect(bind)

    index_names = {item["name"] for item in inspector.get_indexes("rate_limit_buckets")}
    if "ix_rate_limit_buckets_updated_at_ms" not in index_names:
        op.create_index(
            "ix_rate_limit_buckets_updated_at_ms",
            "rate_limit_buckets",
            ["updated_at_ms"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "rate_limit_buckets" not in inspector.get_table_names():
        return
    index_names = {item["name"] for item in inspector.get_indexes("rate_limit_buckets")}
    if "ix_rate_limit_buckets_updated_at_ms" in index_names:
        op.drop_index("ix_rate_limit_buckets_updated_at_ms", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
