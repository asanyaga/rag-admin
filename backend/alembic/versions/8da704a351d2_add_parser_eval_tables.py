"""add_parser_eval_tables

Revision ID: 8da704a351d2
Revises: 30add7b93531
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


revision: str = '8da704a351d2'
down_revision: Union[str, None] = '30add7b93531'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create parser_eval_dimension enum (shared by parser_eval_targets and parser_eval_results)
    parser_eval_dimension = postgresql.ENUM(
        'text',
        name='parser_eval_dimension',
        create_type=False,
    )
    parser_eval_dimension.create(op.get_bind(), checkfirst=True)

    # Create parser_eval_run_status enum
    parser_eval_run_status = postgresql.ENUM(
        'pending', 'running', 'completed', 'failed',
        name='parser_eval_run_status',
        create_type=False,
    )
    parser_eval_run_status.create(op.get_bind(), checkfirst=True)

    # parser_eval_cases
    op.create_table(
        'parser_eval_cases',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('doc_type', sa.String(64), nullable=True),
        sa.Column('source_document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_filename', sa.String(512), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_document_id'], ['source_documents.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    )
    op.create_index('ix_parser_eval_cases_project_id', 'parser_eval_cases', ['project_id'])

    # parser_eval_targets
    op.create_table(
        'parser_eval_targets',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('dimension', postgresql.ENUM('text', name='parser_eval_dimension', create_type=False), nullable=False),
        sa.Column('expected', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['case_id'], ['parser_eval_cases.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('case_id', 'dimension', name='uq_parser_eval_targets_case_dim'),
    )
    op.create_index('ix_parser_eval_targets_case_id', 'parser_eval_targets', ['case_id'])

    # parser_eval_runs
    op.create_table(
        'parser_eval_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('parsers', sa.JSON(), server_default='[]', nullable=False),
        sa.Column('case_ids', sa.JSON(), server_default='[]', nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'completed', 'failed', name='parser_eval_run_status', create_type=False), server_default='pending', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    )
    op.create_index('ix_parser_eval_runs_project_id', 'parser_eval_runs', ['project_id'])

    # parser_eval_results
    op.create_table(
        'parser_eval_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('parser', sa.String(64), nullable=False),
        sa.Column('dimension', postgresql.ENUM('text', name='parser_eval_dimension', create_type=False), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('cost', sa.JSON(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['run_id'], ['parser_eval_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['case_id'], ['parser_eval_cases.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('run_id', 'case_id', 'parser', 'dimension', name='uq_parser_eval_results_run_case_parser_dim'),
    )
    op.create_index('ix_parser_eval_results_run_id', 'parser_eval_results', ['run_id'])


def downgrade() -> None:
    op.drop_table('parser_eval_results')
    op.drop_table('parser_eval_runs')
    op.drop_table('parser_eval_targets')
    op.drop_table('parser_eval_cases')
    op.execute('DROP TYPE IF EXISTS parser_eval_run_status')
    op.execute('DROP TYPE IF EXISTS parser_eval_dimension')
