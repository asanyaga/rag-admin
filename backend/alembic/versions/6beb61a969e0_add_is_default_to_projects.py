"""add_is_default_to_projects

Revision ID: 6beb61a969e0
Revises: 83260626cf13
Create Date: 2026-02-05 13:10:04.501905

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6beb61a969e0'
down_revision: Union[str, None] = '83260626cf13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_default column
    op.add_column('projects', sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'))

    # Create index on (user_id, is_default)
    op.create_index('ix_projects_user_default', 'projects', ['user_id', 'is_default'], unique=False)


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_projects_user_default', table_name='projects')

    # Drop column
    op.drop_column('projects', 'is_default')
