"""eval inference alignment — replace flat model columns with generation_config + judge_config

Revision ID: 0c1d2e3f4a5b
Revises: a9b0c1d2e3f4
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0c1d2e3f4a5b'
down_revision = 'a9b0c1d2e3f4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('eval_runs', sa.Column('generation_config', sa.JSON(), nullable=True))
    op.add_column('eval_runs', sa.Column('judge_config', sa.JSON(), nullable=True))

    # Migrate existing data: pack flat columns + llm_config into the new JSON columns.
    # Uses jsonb_strip_nulls so rows with NULL llm_config don't get a null system_prompt key.
    op.execute("""
        UPDATE eval_runs
        SET generation_config = jsonb_strip_nulls(jsonb_build_object(
            'provider', generation_model_provider,
            'model', generation_model_id,
            'temperature', (llm_config->>'temperature')::float,
            'max_tokens', (llm_config->>'max_tokens')::int,
            'system_prompt', llm_config->>'system_prompt'
        ))
        WHERE generation_model_provider IS NOT NULL
    """)
    op.execute("""
        UPDATE eval_runs
        SET judge_config = jsonb_strip_nulls(jsonb_build_object(
            'provider', judge_model_provider,
            'model', judge_model_id
        ))
        WHERE judge_model_provider IS NOT NULL
    """)

    op.drop_column('eval_runs', 'generation_model_provider')
    op.drop_column('eval_runs', 'generation_model_id')
    op.drop_column('eval_runs', 'judge_model_provider')
    op.drop_column('eval_runs', 'judge_model_id')
    op.drop_column('eval_runs', 'llm_config')


def downgrade() -> None:
    op.add_column('eval_runs', sa.Column('generation_model_provider', sa.String(50), nullable=True))
    op.add_column('eval_runs', sa.Column('generation_model_id', sa.String(100), nullable=True))
    op.add_column('eval_runs', sa.Column('judge_model_provider', sa.String(50), nullable=True))
    op.add_column('eval_runs', sa.Column('judge_model_id', sa.String(100), nullable=True))
    op.add_column('eval_runs', sa.Column('llm_config', sa.JSON(), nullable=True))

    op.execute("""
        UPDATE eval_runs
        SET
            generation_model_provider = generation_config->>'provider',
            generation_model_id = generation_config->>'model',
            judge_model_provider = judge_config->>'provider',
            judge_model_id = judge_config->>'model',
            llm_config = jsonb_strip_nulls(jsonb_build_object(
                'temperature', (generation_config->>'temperature')::float,
                'max_tokens', (generation_config->>'max_tokens')::int,
                'system_prompt', generation_config->>'system_prompt'
            ))
        WHERE generation_config IS NOT NULL
    """)

    op.drop_column('eval_runs', 'generation_config')
    op.drop_column('eval_runs', 'judge_config')
