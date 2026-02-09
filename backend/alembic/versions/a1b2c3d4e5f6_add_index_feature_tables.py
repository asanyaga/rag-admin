"""add_index_feature_tables

Revision ID: a1b2c3d4e5f6
Revises: 83260626cf13
Create Date: 2026-02-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '6beb61a969e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension for vector similarity search
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create enum types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE index_status AS ENUM ('created', 'processing', 'ready', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE index_document_status AS ENUM ('pending', 'processing', 'completed', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create indexes table
    op.create_table(
        'indexes',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('stats', sa.JSON(), nullable=True),
        sa.Column('status', postgresql.ENUM('created', 'processing', 'ready', 'failed', name='index_status', create_type=False), nullable=False, server_default='created'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'name', name='uq_indexes_project_name')
    )

    # Create indexes table indexes
    op.create_index('ix_indexes_project_id', 'indexes', ['project_id'], unique=False)
    op.create_index('ix_indexes_status', 'indexes', ['status'], unique=False)
    op.create_index('ix_indexes_created_at', 'indexes', ['created_at'], unique=False)

    # Create index_documents join table
    op.create_table(
        'index_documents',
        sa.Column('index_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('processing_status', postgresql.ENUM('pending', 'processing', 'completed', 'failed', name='index_document_status', create_type=False), nullable=False, server_default='pending'),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('chunks_created', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['index_id'], ['indexes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('index_id', 'document_id')
    )

    # Create index_documents indexes
    op.create_index('ix_index_documents_index_id', 'index_documents', ['index_id'], unique=False)
    op.create_index('ix_index_documents_document_id', 'index_documents', ['document_id'], unique=False)
    op.create_index('ix_index_documents_status', 'index_documents', ['processing_status'], unique=False)

    # Create chunks table with vector embedding column
    op.create_table(
        'chunks',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('index_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=False),  # Will be converted to vector type
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False),
        sa.Column('char_count', sa.Integer(), nullable=False),
        sa.Column('chunk_metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['index_id'], ['indexes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Convert embedding column to vector type for pgvector
    # Using a large dimension (3072) to support most embedding models
    # text-embedding-3-small: 1536, text-embedding-3-large: 3072
    op.execute('ALTER TABLE chunks ALTER COLUMN embedding TYPE vector USING embedding::vector')

    # Create chunks indexes
    op.create_index('ix_chunks_index_id', 'chunks', ['index_id'], unique=False)
    op.create_index('ix_chunks_document_id', 'chunks', ['document_id'], unique=False)
    op.create_index('ix_chunks_index_document', 'chunks', ['index_id', 'document_id'], unique=False)
    op.create_index('ix_chunks_chunk_index', 'chunks', ['chunk_index'], unique=False)

    # Note: HNSW index requires fixed vector dimensions, but we support multiple
    # embedding models with different dimensions. For production with many chunks,
    # consider adding partial HNSW indexes per embedding dimension, e.g.:
    # CREATE INDEX ix_chunks_embedding_hnsw_1536 ON chunks
    #   USING hnsw (embedding vector_cosine_ops) WHERE array_length(embedding, 1) = 1536

    # Create GIN index on content for full-text search
    # This enables BM25-style keyword search via pg_trgm or ParadeDB
    op.execute('''
        CREATE INDEX ix_chunks_content_gin ON chunks
        USING gin (to_tsvector('english', content))
    ''')

    # Create provider_keys table
    op.create_table(
        'provider_keys',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=True),  # NULL = account-level
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'project_id', 'provider', name='uq_provider_keys_user_project_provider')
    )

    # Create provider_keys indexes
    op.create_index('ix_provider_keys_user_id', 'provider_keys', ['user_id'], unique=False)
    op.create_index('ix_provider_keys_project_id', 'provider_keys', ['project_id'], unique=False)
    op.create_index('ix_provider_keys_user_provider', 'provider_keys', ['user_id', 'provider'], unique=False)


def downgrade() -> None:
    # Drop provider_keys indexes
    op.drop_index('ix_provider_keys_user_provider', table_name='provider_keys')
    op.drop_index('ix_provider_keys_project_id', table_name='provider_keys')
    op.drop_index('ix_provider_keys_user_id', table_name='provider_keys')
    op.drop_table('provider_keys')

    # Drop chunks indexes
    op.execute('DROP INDEX IF EXISTS ix_chunks_content_gin')
    op.drop_index('ix_chunks_chunk_index', table_name='chunks')
    op.drop_index('ix_chunks_index_document', table_name='chunks')
    op.drop_index('ix_chunks_document_id', table_name='chunks')
    op.drop_index('ix_chunks_index_id', table_name='chunks')
    op.drop_table('chunks')

    # Drop index_documents indexes
    op.drop_index('ix_index_documents_status', table_name='index_documents')
    op.drop_index('ix_index_documents_document_id', table_name='index_documents')
    op.drop_index('ix_index_documents_index_id', table_name='index_documents')
    op.drop_table('index_documents')

    # Drop indexes table indexes
    op.drop_index('ix_indexes_created_at', table_name='indexes')
    op.drop_index('ix_indexes_status', table_name='indexes')
    op.drop_index('ix_indexes_project_id', table_name='indexes')
    op.drop_table('indexes')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS index_document_status')
    op.execute('DROP TYPE IF EXISTS index_status')

    # Note: We don't drop the vector extension as other things might use it
