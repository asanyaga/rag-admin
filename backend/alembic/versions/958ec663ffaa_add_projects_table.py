"""add_projects_table

Revision ID: 958ec663ffaa
Revises: 6386c45a01f0
Create Date: 2026-02-03 14:43:41.158139

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '958ec663ffaa'
down_revision: Union[str, None] = '6386c45a01f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.Text()), nullable=False, server_default='{}'),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_projects_user_name')
    )

    # Create indexes
    op.create_index('ix_projects_user_id', 'projects', ['user_id'], unique=False)
    op.create_index('ix_projects_is_archived', 'projects', ['is_archived'], unique=False)
    op.create_index('ix_projects_created_at', 'projects', ['created_at'], unique=False)
    op.create_index('ix_projects_user_active', 'projects', ['user_id', 'is_archived'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_projects_user_active', table_name='projects')
    op.drop_index('ix_projects_created_at', table_name='projects')
    op.drop_index('ix_projects_is_archived', table_name='projects')
    op.drop_index('ix_projects_user_id', table_name='projects')

    # Drop table
    op.drop_table('projects')
