"""add_flow_runs_table

Revision ID: 23528140ed0b
Revises: 1bd1c32cd72c
Create Date: 2026-04-11 11:24:55.731039

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '23528140ed0b'
down_revision: Union[str, None] = '1bd1c32cd72c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'flow_run_status') THEN
                CREATE TYPE flow_run_status AS ENUM (
                    'pending', 'running', 'waiting_for_input', 'completed', 'failed'
                );
            END IF;
        END
        $$;
    """)

    op.create_table('flow_runs',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('flow_definition_id', sa.UUID(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'waiting_for_input', 'completed', 'failed', name='flow_run_status', create_type=False), server_default='pending', nullable=False),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('initial_state', sa.JSON(), nullable=True),
        sa.Column('current_state', sa.JSON(), nullable=True),
        sa.Column('current_node', sa.String(length=255), nullable=True),
        sa.Column('thread_id', sa.String(length=64), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['flow_definition_id'], ['flow_definitions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_flow_runs_project_id', 'flow_runs', ['project_id'], unique=False)
    op.create_index('ix_flow_runs_status', 'flow_runs', ['status'], unique=False)
    op.create_index('ix_flow_runs_flow_definition_id', 'flow_runs', ['flow_definition_id'], unique=False)
    op.create_index('ix_flow_runs_thread_id', 'flow_runs', ['thread_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_flow_runs_thread_id', table_name='flow_runs')
    op.drop_index('ix_flow_runs_flow_definition_id', table_name='flow_runs')
    op.drop_index('ix_flow_runs_status', table_name='flow_runs')
    op.drop_index('ix_flow_runs_project_id', table_name='flow_runs')
    op.drop_table('flow_runs')
    op.execute("DROP TYPE IF EXISTS flow_run_status")
