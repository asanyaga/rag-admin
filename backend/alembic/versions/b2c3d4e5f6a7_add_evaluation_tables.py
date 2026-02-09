"""add_evaluation_tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-09 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE golden_set_status AS ENUM ('draft', 'completed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE eval_run_status AS ENUM ('pending', 'running', 'completed', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create golden_sets table
    op.create_table(
        'golden_sets',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM('draft', 'completed', name='golden_set_status', create_type=False), nullable=False, server_default='draft'),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_golden_sets_project_id', 'golden_sets', ['project_id'], unique=False)
    op.create_index('ix_golden_sets_created_at', 'golden_sets', ['created_at'], unique=False)

    # Create golden_set_queries table
    op.create_table(
        'golden_set_queries',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('golden_set_id', sa.UUID(), nullable=False),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['golden_set_id'], ['golden_sets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_golden_set_queries_golden_set_id', 'golden_set_queries', ['golden_set_id'], unique=False)

    # Create golden_set_sources table
    op.create_table(
        'golden_set_sources',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('query_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('locator', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['query_id'], ['golden_set_queries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_golden_set_sources_query_id', 'golden_set_sources', ['query_id'], unique=False)
    op.create_index('ix_golden_set_sources_document_id', 'golden_set_sources', ['document_id'], unique=False)

    # Create eval_runs table
    op.create_table(
        'eval_runs',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('golden_set_id', sa.UUID(), nullable=False),
        sa.Column('index_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'completed', 'failed', name='eval_run_status', create_type=False), nullable=False, server_default='pending'),
        sa.Column('metrics', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['golden_set_id'], ['golden_sets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['index_id'], ['indexes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_eval_runs_project_id', 'eval_runs', ['project_id'], unique=False)
    op.create_index('ix_eval_runs_golden_set_id', 'eval_runs', ['golden_set_id'], unique=False)
    op.create_index('ix_eval_runs_index_id', 'eval_runs', ['index_id'], unique=False)
    op.create_index('ix_eval_runs_created_at', 'eval_runs', ['created_at'], unique=False)

    # Create eval_run_results table
    op.create_table(
        'eval_run_results',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('eval_run_id', sa.UUID(), nullable=False),
        sa.Column('query_id', sa.UUID(), nullable=False),
        sa.Column('precision', sa.Float(), nullable=False),
        sa.Column('recall', sa.Float(), nullable=False),
        sa.Column('f1', sa.Float(), nullable=False),
        sa.Column('retrieved_chunks', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['eval_run_id'], ['eval_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['query_id'], ['golden_set_queries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_eval_run_results_eval_run_id', 'eval_run_results', ['eval_run_id'], unique=False)
    op.create_index('ix_eval_run_results_query_id', 'eval_run_results', ['query_id'], unique=False)


def downgrade() -> None:
    # Drop eval_run_results
    op.drop_index('ix_eval_run_results_query_id', table_name='eval_run_results')
    op.drop_index('ix_eval_run_results_eval_run_id', table_name='eval_run_results')
    op.drop_table('eval_run_results')

    # Drop eval_runs
    op.drop_index('ix_eval_runs_created_at', table_name='eval_runs')
    op.drop_index('ix_eval_runs_index_id', table_name='eval_runs')
    op.drop_index('ix_eval_runs_golden_set_id', table_name='eval_runs')
    op.drop_index('ix_eval_runs_project_id', table_name='eval_runs')
    op.drop_table('eval_runs')

    # Drop golden_set_sources
    op.drop_index('ix_golden_set_sources_document_id', table_name='golden_set_sources')
    op.drop_index('ix_golden_set_sources_query_id', table_name='golden_set_sources')
    op.drop_table('golden_set_sources')

    # Drop golden_set_queries
    op.drop_index('ix_golden_set_queries_golden_set_id', table_name='golden_set_queries')
    op.drop_table('golden_set_queries')

    # Drop golden_sets
    op.drop_index('ix_golden_sets_created_at', table_name='golden_sets')
    op.drop_index('ix_golden_sets_project_id', table_name='golden_sets')
    op.drop_table('golden_sets')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS eval_run_status')
    op.execute('DROP TYPE IF EXISTS golden_set_status')
