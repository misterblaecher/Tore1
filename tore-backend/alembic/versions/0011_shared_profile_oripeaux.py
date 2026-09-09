"""add shared folkloric profile data

Revision ID: 0011_shared_profile_oripeaux
Revises: 0010_forum_structure_mvp
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0011_shared_profile_oripeaux"
down_revision = "0010_forum_structure_mvp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("app_users")}
    if "oripeaux" not in columns:
        op.add_column("app_users", sa.Column("oripeaux", sa.Text(), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("app_users")}
    if "oripeaux" in columns:
        op.drop_column("app_users", "oripeaux")
