"""Restore the historical Forum foundation lineage.

Revision ID: 0013_forum_backend_foundation
Revises: 0012_discussion_workspace

This revision was recovered from the local Git object database.  Its original
schema has since been superseded by the capability-RBAC migrations.  Databases
which carry its descendant already contain its objects; new databases get the
current schema from the ORM baseline.  Keeping this revision as a lineage
anchor lets Alembic reason about both histories without replaying obsolete
tables into new installations.
"""

revision = "0013_forum_backend_foundation"
down_revision = "0012_discussion_workspace"
branch_labels = ("legacy_forum",)
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
