"""add event_costs_simple tables

Revision ID: 0002_event_costs_simple
Revises: 0001_initial_schema
Create Date: 2026-02-15
"""
from alembic import op
import sqlalchemy as sa


revision = '0002_event_costs_simple'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'event_costs_simple',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('costs_tickets', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('breakdown_json', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['events.id']),
        sa.ForeignKeyConstraint(['updated_by'], ['partner_users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', name='uq_event_costs_simple_event'),
    )
    op.create_index('ix_event_costs_simple_event_id', 'event_costs_simple', ['event_id'])
    op.create_index('ix_event_costs_simple_updated_at', 'event_costs_simple', ['updated_at'])

    op.create_table(
        'event_costs_simple_idempotency',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('idempotency_key', sa.String(length=120), nullable=False),
        sa.Column('response_json', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['events.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'idempotency_key', name='uq_event_costs_simple_idem'),
    )
    op.create_index('ix_event_costs_simple_idempotency_event_id', 'event_costs_simple_idempotency', ['event_id'])
    op.create_index('ix_event_costs_simple_idempotency_idempotency_key', 'event_costs_simple_idempotency', ['idempotency_key'])


def downgrade() -> None:
    op.drop_index('ix_event_costs_simple_idempotency_idempotency_key', table_name='event_costs_simple_idempotency')
    op.drop_index('ix_event_costs_simple_idempotency_event_id', table_name='event_costs_simple_idempotency')
    op.drop_table('event_costs_simple_idempotency')
    op.drop_index('ix_event_costs_simple_updated_at', table_name='event_costs_simple')
    op.drop_index('ix_event_costs_simple_event_id', table_name='event_costs_simple')
    op.drop_table('event_costs_simple')
