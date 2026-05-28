"""classification_provider_refactor

Revision ID: cdc883e9de71
Revises: 6962180e11cf
Create Date: 2026-05-28 11:25:44.597368

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'cdc883e9de71'
down_revision: Union[str, None] = '6962180e11cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns as nullable first
    op.add_column('classification_runs', sa.Column('classifier_type', sa.Text(), nullable=True))
    op.add_column('classification_runs', sa.Column('classifier_config', sa.JSON(), nullable=True))

    # Migrate existing rows — all previous runs used the LLM classifier
    op.execute("""
        UPDATE classification_runs
        SET
            classifier_type = 'llm',
            classifier_config = json_build_object(
                'provider', llm_provider,
                'model', llm_model,
                'batch_size', batch_size,
                'batch_overlap', batch_overlap,
                'llm_config', '{}'::json
            )
    """)

    # Make non-nullable
    op.alter_column('classification_runs', 'classifier_type', nullable=False)
    op.alter_column('classification_runs', 'classifier_config', nullable=False)

    # Drop replaced columns
    op.drop_column('classification_runs', 'llm_provider')
    op.drop_column('classification_runs', 'llm_model')
    op.drop_column('classification_runs', 'batch_size')
    op.drop_column('classification_runs', 'batch_overlap')


def downgrade() -> None:
    op.add_column('classification_runs', sa.Column('llm_provider', sa.Text(), nullable=True))
    op.add_column('classification_runs', sa.Column('llm_model', sa.Text(), nullable=True))
    op.add_column('classification_runs', sa.Column('batch_size', sa.Integer(), nullable=True))
    op.add_column('classification_runs', sa.Column('batch_overlap', sa.Integer(), nullable=True))

    op.execute("""
        UPDATE classification_runs
        SET
            llm_provider = classifier_config->>'provider',
            llm_model = classifier_config->>'model',
            batch_size = (classifier_config->>'batch_size')::int,
            batch_overlap = (classifier_config->>'batch_overlap')::int
        WHERE classifier_type = 'llm'
    """)

    op.drop_column('classification_runs', 'classifier_type')
    op.drop_column('classification_runs', 'classifier_config')
