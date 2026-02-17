"""add_golden_set_generation_fields

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'f2913476b229'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE generation_status_enum AS ENUM ('pending', 'generating', 'completed', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE source_method_enum AS ENUM ('manual', 'auto_generated');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE review_status_enum AS ENUM ('pending', 'accepted', 'rejected', 'edited');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Add columns to golden_sets
    op.add_column('golden_sets', sa.Column('generation_config', sa.JSON(), nullable=True))
    op.add_column('golden_sets', sa.Column(
        'generation_status',
        sa.Enum('pending', 'generating', 'completed', 'failed', name='generation_status_enum', create_type=False),
        nullable=True,
    ))
    op.add_column('golden_sets', sa.Column('generation_progress', sa.JSON(), nullable=True))

    # Add columns to golden_set_queries
    op.add_column('golden_set_queries', sa.Column(
        'source_method',
        sa.Enum('manual', 'auto_generated', name='source_method_enum', create_type=False),
        nullable=False,
        server_default='manual',
    ))
    op.add_column('golden_set_queries', sa.Column(
        'review_status',
        sa.Enum('pending', 'accepted', 'rejected', 'edited', name='review_status_enum', create_type=False),
        nullable=False,
        server_default='accepted',
    ))
    op.add_column('golden_set_queries', sa.Column('reasoning', sa.Text(), nullable=True))
    op.add_column('golden_set_queries', sa.Column('question_type', sa.String(50), nullable=True))
    op.add_column('golden_set_queries', sa.Column('reference_answer', sa.Text(), nullable=True))
    op.add_column('golden_set_queries', sa.Column('answer_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Drop columns from golden_set_queries
    op.drop_column('golden_set_queries', 'answer_metadata')
    op.drop_column('golden_set_queries', 'reference_answer')
    op.drop_column('golden_set_queries', 'question_type')
    op.drop_column('golden_set_queries', 'reasoning')
    op.drop_column('golden_set_queries', 'review_status')
    op.drop_column('golden_set_queries', 'source_method')

    # Drop columns from golden_sets
    op.drop_column('golden_sets', 'generation_progress')
    op.drop_column('golden_sets', 'generation_status')
    op.drop_column('golden_sets', 'generation_config')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS review_status_enum')
    op.execute('DROP TYPE IF EXISTS source_method_enum')
    op.execute('DROP TYPE IF EXISTS generation_status_enum')
