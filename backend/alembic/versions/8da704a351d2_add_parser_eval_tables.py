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
    dimension = postgresql.ENUM('text', name='parser_eval_dimension', create_type=False)
    dimension.create(op.get_bind(), checkfirst=True)
    source_method = postgresql.ENUM('human', 'generated', 'bootstrapped',
                                    name='parser_eval_source_method', create_type=False)
    source_method.create(op.get_bind(), checkfirst=True)
    review_status = postgresql.ENUM('draft', 'verified',
                                    name='parser_eval_review_status', create_type=False)
    review_status.create(op.get_bind(), checkfirst=True)
    run_status = postgresql.ENUM('pending', 'running', 'completed', 'failed',
                                 name='parser_eval_run_status', create_type=False)
    run_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'parser_eval_cases',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('dimension', postgresql.ENUM('text', name='parser_eval_dimension', create_type=False), nullable=False),
        sa.Column('expected', sa.JSON(), nullable=False),
        sa.Column('source_method', postgresql.ENUM('human', 'generated', 'bootstrapped', name='parser_eval_source_method', create_type=False), server_default='human', nullable=False),
        sa.Column('review_status', postgresql.ENUM('draft', 'verified', name='parser_eval_review_status', create_type=False), server_default='draft', nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_document_id'], ['source_documents.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.UniqueConstraint('source_document_id', 'dimension', name='uq_parser_eval_cases_source_dim'),
    )
    op.create_index('ix_parser_eval_cases_project_id', 'parser_eval_cases', ['project_id'])

    op.create_table(
        'parser_eval_datasets',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    )
    op.create_index('ix_parser_eval_datasets_project_id', 'parser_eval_datasets', ['project_id'])

    op.create_table(
        'parser_eval_dataset_cases',
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('eval_case_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint('dataset_id', 'eval_case_id'),
        sa.ForeignKeyConstraint(['dataset_id'], ['parser_eval_datasets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['eval_case_id'], ['parser_eval_cases.id'], ondelete='CASCADE'),
    )

    op.create_table(
        'parser_eval_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('variants', sa.JSON(), server_default='[]', nullable=False),
        sa.Column('eval_case_ids', sa.JSON(), server_default='[]', nullable=False),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'completed', 'failed', name='parser_eval_run_status', create_type=False), server_default='pending', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dataset_id'], ['parser_eval_datasets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    )
    op.create_index('ix_parser_eval_runs_project_id', 'parser_eval_runs', ['project_id'])

    op.create_table(
        'parser_eval_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('eval_case_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('adapter', sa.String(64), nullable=False),
        sa.Column('config', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('variant_key', sa.String(128), nullable=False),
        sa.Column('metrics', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('primary_metric', sa.String(64), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('cost', sa.JSON(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['run_id'], ['parser_eval_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['eval_case_id'], ['parser_eval_cases.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('run_id', 'eval_case_id', 'variant_key', name='uq_parser_eval_results_run_case_variant'),
    )
    op.create_index('ix_parser_eval_results_run_id', 'parser_eval_results', ['run_id'])


def downgrade() -> None:
    op.drop_table('parser_eval_results')
    op.drop_table('parser_eval_runs')
    op.drop_table('parser_eval_dataset_cases')
    op.drop_table('parser_eval_datasets')
    op.drop_table('parser_eval_cases')
    op.execute('DROP TYPE IF EXISTS parser_eval_run_status')
    op.execute('DROP TYPE IF EXISTS parser_eval_review_status')
    op.execute('DROP TYPE IF EXISTS parser_eval_source_method')
    op.execute('DROP TYPE IF EXISTS parser_eval_dimension')
