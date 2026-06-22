"""add_project_id_to_parse_runs

Revision ID: aed9d6c56057
Revises: 0c1d2e3f4a5b
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'aed9d6c56057'
down_revision: Union[str, None] = '0c1d2e3f4a5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'parse_runs',
        sa.Column(
            'project_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('projects.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.create_index('ix_parse_runs_project_id', 'parse_runs', ['project_id'])


def downgrade() -> None:
    op.drop_index('ix_parse_runs_project_id', table_name='parse_runs')
    op.drop_column('parse_runs', 'project_id')
