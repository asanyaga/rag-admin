"""add_documents_table

Revision ID: 83260626cf13
Revises: 958ec663ffaa
Create Date: 2026-02-05 09:36:14.955325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '83260626cf13'
down_revision: Union[str, None] = '958ec663ffaa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create document_status enum type
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE document_status AS ENUM ('processing', 'ready', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_identifier', sa.String(length=500), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('source_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('processing_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('status', postgresql.ENUM('processing', 'ready', 'failed', name='document_status', create_type=False), nullable=False, server_default='processing'),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'source_type', 'source_identifier', name='uq_documents_project_source')
    )

    # Create indexes
    op.create_index('ix_documents_project_id', 'documents', ['project_id'], unique=False)
    op.create_index('ix_documents_source_type', 'documents', ['source_type'], unique=False)
    op.create_index('ix_documents_status', 'documents', ['status'], unique=False)
    op.create_index('ix_documents_created_at', 'documents', ['created_at'], unique=False)
    op.create_index('ix_documents_source_metadata', 'documents', ['source_metadata'], unique=False, postgresql_using='gin')
    op.create_index('ix_documents_processing_metadata', 'documents', ['processing_metadata'], unique=False, postgresql_using='gin')


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_documents_processing_metadata', table_name='documents')
    op.drop_index('ix_documents_source_metadata', table_name='documents')
    op.drop_index('ix_documents_created_at', table_name='documents')
    op.drop_index('ix_documents_status', table_name='documents')
    op.drop_index('ix_documents_source_type', table_name='documents')
    op.drop_index('ix_documents_project_id', table_name='documents')

    # Drop table
    op.drop_table('documents')

    # Drop enum type
    op.execute('DROP TYPE IF EXISTS document_status')
