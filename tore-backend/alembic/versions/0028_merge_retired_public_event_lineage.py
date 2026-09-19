"""Merge the retired public-event revision into the canonical Forum lineage."""

revision = "0028_merge_retired_public_event_lineage"
down_revision = (
    "0027_legacy_forum_schema_parity",
    "0013_public_event_recap",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
