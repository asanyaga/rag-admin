"""add_extraction_tables

Revision ID: c1d2e3f4a5b6
Revises: b8c9d0e1f2a3
Create Date: 2026-03-19 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create extraction_result_status enum
    op.execute(sa.text(
        "DO $$ BEGIN "
        "CREATE TYPE extraction_result_status AS ENUM ('pending', 'completed', 'failed'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$"
    ))

    # Create extraction_schemas table
    op.create_table(
        'extraction_schemas',
        sa.Column('id', postgresql.UUID(as_uuid=True),
                  server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('schema_definition', sa.JSON(), nullable=False),
        sa.Column('extraction_target', sa.String(length=30),
                  server_default='PER_DOC', nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'name', name='uq_extraction_schemas_project_name'),
    )
    op.create_index('ix_extraction_schemas_project_id', 'extraction_schemas', ['project_id'])

    # Create extraction_results table
    op.create_table(
        'extraction_results',
        sa.Column('id', postgresql.UUID(as_uuid=True),
                  server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('extraction_schema_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('schema_definition_snapshot', sa.JSON(), nullable=False),
        sa.Column('extraction_method', sa.String(length=30), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('structured_data', sa.JSON(), nullable=True),
        sa.Column('extraction_metadata', sa.JSON(), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'completed', 'failed',
                  name='extraction_result_status', create_type=False),
                  server_default='pending', nullable=False),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['extraction_schema_id'], ['extraction_schemas.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_extraction_results_document_schema', 'extraction_results',
                    ['document_id', 'extraction_schema_id'])
    op.create_index('ix_extraction_results_document_id', 'extraction_results', ['document_id'])
    op.create_index('ix_extraction_results_status', 'extraction_results', ['status'])


def downgrade() -> None:
    op.drop_index('ix_extraction_results_status', table_name='extraction_results')
    op.drop_index('ix_extraction_results_document_id', table_name='extraction_results')
    op.drop_index('ix_extraction_results_document_schema', table_name='extraction_results')
    op.drop_table('extraction_results')

    op.drop_index('ix_extraction_schemas_project_id', table_name='extraction_schemas')
    op.drop_table('extraction_schemas')

    extraction_result_status = postgresql.ENUM('pending', 'completed', 'failed',
                                                name='extraction_result_status')
    extraction_result_status.drop(op.get_bind(), checkfirst=True)
