"""add_flow_definitions_table

Revision ID: 1bd1c32cd72c
Revises: 1d64baf5d740
Create Date: 2026-04-10 21:19:21.255111

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1bd1c32cd72c'
down_revision: Union[str, None] = '1d64baf5d740'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('flow_definitions',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('definition', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'name', name='uq_flow_definitions_project_name'),
    )
    op.create_index('ix_flow_definitions_project_id', 'flow_definitions', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_flow_definitions_project_id', table_name='flow_definitions')
    op.drop_table('flow_definitions')
