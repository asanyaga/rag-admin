"""add_extraction_eval_tables

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-03-19 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create extraction_eval_run_status enum
    extraction_eval_run_status = postgresql.ENUM(
        'pending', 'running', 'completed', 'failed',
        name='extraction_eval_run_status',
        create_type=False,
    )
    extraction_eval_run_status.create(op.get_bind(), checkfirst=True)

    # extraction_ground_truth_sets
    op.create_table(
        'extraction_ground_truth_sets',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('extraction_schema_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['extraction_schema_id'], ['extraction_schemas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.UniqueConstraint('project_id', 'name', name='uq_extraction_gt_sets_project_name'),
    )
    op.create_index('ix_extraction_gt_sets_project_id', 'extraction_ground_truth_sets', ['project_id'])
    op.create_index('ix_extraction_gt_sets_schema_id', 'extraction_ground_truth_sets', ['extraction_schema_id'])

    # extraction_ground_truth_items
    op.create_table(
        'extraction_ground_truth_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('ground_truth_set_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('expected_data', sa.JSON(), nullable=False),
        sa.Column('annotations', sa.JSON(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['ground_truth_set_id'], ['extraction_ground_truth_sets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.UniqueConstraint('ground_truth_set_id', 'document_id', name='uq_extraction_gt_items_set_doc'),
    )
    op.create_index('ix_extraction_gt_items_set_id', 'extraction_ground_truth_items', ['ground_truth_set_id'])
    op.create_index('ix_extraction_gt_items_document_id', 'extraction_ground_truth_items', ['document_id'])

    # extraction_eval_runs
    op.create_table(
        'extraction_eval_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ground_truth_set_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('config', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'completed', 'failed', name='extraction_eval_run_status', create_type=False), server_default='pending', nullable=False),
        sa.Column('metrics', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('items_completed', sa.Integer(), server_default='0', nullable=False),
        sa.Column('items_total', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ground_truth_set_id'], ['extraction_ground_truth_sets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    )
    op.create_index('ix_extraction_eval_runs_project_id', 'extraction_eval_runs', ['project_id'])
    op.create_index('ix_extraction_eval_runs_gt_set_id', 'extraction_eval_runs', ['ground_truth_set_id'])
    op.create_index('ix_extraction_eval_runs_created_at', 'extraction_eval_runs', ['created_at'])

    # extraction_eval_results
    op.create_table(
        'extraction_eval_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('eval_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('extraction_result_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ground_truth_item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('field_scores', sa.JSON(), nullable=False),
        sa.Column('line_items_score', sa.JSON(), nullable=True),
        sa.Column('evaluation_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['eval_run_id'], ['extraction_eval_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['extraction_result_id'], ['extraction_results.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ground_truth_item_id'], ['extraction_ground_truth_items.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('eval_run_id', 'ground_truth_item_id', name='uq_extraction_eval_results_run_item'),
    )
    op.create_index('ix_extraction_eval_results_run_id', 'extraction_eval_results', ['eval_run_id'])
    op.create_index('ix_extraction_eval_results_gt_item_id', 'extraction_eval_results', ['ground_truth_item_id'])


def downgrade() -> None:
    op.drop_table('extraction_eval_results')
    op.drop_table('extraction_eval_runs')
    op.drop_table('extraction_ground_truth_items')
    op.drop_table('extraction_ground_truth_sets')
    op.execute('DROP TYPE IF EXISTS extraction_eval_run_status')
