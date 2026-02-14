"""Initial schema baseline for production Postgres

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-02-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

from db import Base
import models  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
