"""add_source_metadata_column

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-04-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add source_metadata to all existing dynamic tables
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT table_name FROM project_data_stores"))
    for row in result:
        table_name = row[0]
        op.add_column(table_name, sa.Column('source_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT table_name FROM project_data_stores"))
    for row in result:
        table_name = row[0]
        op.drop_column(table_name, 'source_metadata')
