"""add_answer_eval_fields

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'partial_failure' to eval_run_status enum
    op.execute("ALTER TYPE eval_run_status ADD VALUE IF NOT EXISTS 'partial_failure'")

    # Add columns to eval_runs
    op.add_column('eval_runs', sa.Column(
        'mode', sa.String(30), nullable=False, server_default='retrieval_only'
    ))
    op.add_column('eval_runs', sa.Column(
        'generation_model_provider', sa.String(50), nullable=True
    ))
    op.add_column('eval_runs', sa.Column(
        'generation_model_id', sa.String(100), nullable=True
    ))
    op.add_column('eval_runs', sa.Column(
        'judge_model_provider', sa.String(50), nullable=True
    ))
    op.add_column('eval_runs', sa.Column(
        'judge_model_id', sa.String(100), nullable=True
    ))
    op.add_column('eval_runs', sa.Column(
        'system_prompt', sa.Text(), nullable=True
    ))
    op.add_column('eval_runs', sa.Column(
        'items_completed', sa.Integer(), nullable=False, server_default='0'
    ))
    op.add_column('eval_runs', sa.Column(
        'failed_item_count', sa.Integer(), nullable=False, server_default='0'
    ))

    # Add columns to eval_run_results
    op.add_column('eval_run_results', sa.Column(
        'generated_answer', sa.Text(), nullable=True
    ))
    op.add_column('eval_run_results', sa.Column(
        'faithfulness_score', sa.Float(), nullable=True
    ))
    op.add_column('eval_run_results', sa.Column(
        'relevance_score', sa.Float(), nullable=True
    ))
    op.add_column('eval_run_results', sa.Column(
        'claim_breakdown', sa.JSON(), nullable=True
    ))
    op.add_column('eval_run_results', sa.Column(
        'judge_error', sa.Text(), nullable=True
    ))
    op.add_column('eval_run_results', sa.Column(
        'generation_error', sa.Text(), nullable=True
    ))


def downgrade() -> None:
    # Drop columns from eval_run_results
    op.drop_column('eval_run_results', 'generation_error')
    op.drop_column('eval_run_results', 'judge_error')
    op.drop_column('eval_run_results', 'claim_breakdown')
    op.drop_column('eval_run_results', 'relevance_score')
    op.drop_column('eval_run_results', 'faithfulness_score')
    op.drop_column('eval_run_results', 'generated_answer')

    # Drop columns from eval_runs
    op.drop_column('eval_runs', 'failed_item_count')
    op.drop_column('eval_runs', 'items_completed')
    op.drop_column('eval_runs', 'system_prompt')
    op.drop_column('eval_runs', 'judge_model_id')
    op.drop_column('eval_runs', 'judge_model_provider')
    op.drop_column('eval_runs', 'generation_model_id')
    op.drop_column('eval_runs', 'generation_model_provider')
    op.drop_column('eval_runs', 'mode')

    # Note: Cannot remove enum values in PostgreSQL without recreating the type
