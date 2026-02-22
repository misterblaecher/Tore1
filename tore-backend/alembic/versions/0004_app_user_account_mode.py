"""add app_users.account_mode

Revision ID: 0004_app_user_account_mode
Revises: 0003_account_requests
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_app_user_account_mode'
down_revision = '0003_account_requests'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('app_users', sa.Column('account_mode', sa.String(length=16), nullable=True, server_default='user'))
    op.execute("UPDATE app_users SET account_mode='user' WHERE account_mode IS NULL OR account_mode = ''")
    op.alter_column('app_users', 'account_mode', server_default=None)
    op.create_index('ix_app_users_account_mode', 'app_users', ['account_mode'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_app_users_account_mode', table_name='app_users')
    op.drop_column('app_users', 'account_mode')
