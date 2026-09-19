"""Add lifecycle state while preserving historical structure publication.

Existing organizations are backfilled as ACTIVE so their current visibility remains
unchanged. New organizations are created as SETUP/private by the application layer.
"""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "0013_structure_lifecycle_private_defaults"
down_revision = "0012_discussion_workspace"
branch_labels = None
depends_on = "0015_legacy_forum_bridge"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "organization_lifecycle_states" not in inspector.get_table_names():
        op.create_table(
            "organization_lifecycle_states",
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="SETUP"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_organization_lifecycle_states_status",
            "organization_lifecycle_states",
            ["status"],
        )
        op.create_index(
            "ix_organization_lifecycle_states_created_at",
            "organization_lifecycle_states",
            ["created_at"],
        )
        op.create_index(
            "ix_organization_lifecycle_states_updated_at",
            "organization_lifecycle_states",
            ["updated_at"],
        )

    lifecycle = sa.table(
        "organization_lifecycle_states",
        sa.column("organization_id", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    organizations = sa.table("organizations", sa.column("id", sa.Integer()))
    existing = set(bind.execute(sa.select(lifecycle.c.organization_id)).scalars().all())
    stamp = datetime.now(timezone.utc).replace(tzinfo=None)
    for organization_id in bind.execute(sa.select(organizations.c.id)).scalars().all():
        if organization_id in existing:
            continue
        # Retro-compatible invariant: every structure that existed before this migration
        # keeps behaving as an ACTIVE historical structure. Its existing visibility and
        # block settings are intentionally not modified.
        bind.execute(
            lifecycle.insert().values(
                organization_id=organization_id,
                status="ACTIVE",
                created_at=stamp,
                updated_at=stamp,
            )
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if "organization_lifecycle_states" in inspector.get_table_names():
        op.drop_table("organization_lifecycle_states")
