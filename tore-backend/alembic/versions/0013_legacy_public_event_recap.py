"""Recognize databases stamped by the retired public-event migration lineage.

The historical ``0013_public_event_recap`` migration was renumbered to
``0016_public_event_recap`` when the Forum branches were consolidated.  Some
local and deployed databases had already recorded the old revision.  Keeping
this no-op compatibility node lets Alembic reconnect those databases to the
current graph; the modern, idempotent migration supplies any missing schema.
"""

revision = "0013_public_event_recap"
down_revision = "0012_discussion_workspace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
