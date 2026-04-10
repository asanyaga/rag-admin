"""add_agent_configs_table

Revision ID: 1d64baf5d740
Revises: 0b92f2f67990
Create Date: 2026-04-10 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1d64baf5d740'
down_revision: Union[str, None] = '0b92f2f67990'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'agent_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_type', sa.String(length=64), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'agent_type', name='uq_agent_configs_project_type'),
    )
    op.create_index('ix_agent_configs_project_id', 'agent_configs', ['project_id'])


def downgrade() -> None:
    op.drop_index('ix_agent_configs_project_id', table_name='agent_configs')
    op.drop_table('agent_configs')
