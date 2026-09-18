"""Forum editorial data, handovers, budgets and media withdrawal requests.

Recovered from the historical ``feature/forum-v3.4.1`` Git state.  Creation is
guarded because historical databases may also have received these tables from
the ORM bootstrap before their Alembic revision was recorded.
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_forum_p1"
down_revision = "0013_forum_backend_foundation"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "forum_event_editorial" not in tables:
        op.create_table(
            "forum_event_editorial",
            sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("content", sa.JSON(), nullable=False),
        )
    if "forum_handovers" not in tables:
        op.create_table(
            "forum_handovers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("snapshot", sa.JSON(), nullable=False),
            sa.UniqueConstraint("organization_id", "year", name="uq_forum_handover_year"),
        )
    if "forum_accounting_plans" not in tables:
        op.create_table(
            "forum_accounting_plans",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=True),
            sa.Column("category", sa.String(80), nullable=False),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=False),
        )
    if "forum_media_reports" not in tables:
        op.create_table(
            "forum_media_reports",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("media_id", sa.Integer(), sa.ForeignKey("structure_media_assets.id"), nullable=False, index=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
        )


def downgrade() -> None:
    for name in ("forum_media_reports", "forum_accounting_plans", "forum_handovers", "forum_event_editorial"):
        if name in _tables():
            op.drop_table(name)
