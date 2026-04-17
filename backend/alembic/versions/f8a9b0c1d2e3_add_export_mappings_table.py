"""add_export_mappings_table

Revision ID: f8a9b0c1d2e3
Revises: e6f7a8b9c0d1
Create Date: 2026-04-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'export_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('data_store_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('project_data_stores.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('field_mapping', sa.JSON, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
    )
    op.create_unique_constraint(
        'uq_export_mappings_project_store_name',
        'export_mappings',
        ['project_id', 'data_store_id', 'name']
    )
    op.create_index(
        'ix_export_mappings_project_store',
        'export_mappings',
        ['project_id', 'data_store_id']
    )


def downgrade() -> None:
    op.drop_index('ix_export_mappings_project_store', table_name='export_mappings')
    op.drop_constraint('uq_export_mappings_project_store_name', 'export_mappings')
    op.drop_table('export_mappings')
