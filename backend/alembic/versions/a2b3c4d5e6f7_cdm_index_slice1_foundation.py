"""cdm_index_slice1_foundation

Revision ID: a2b3c4d5e6f7
Revises: f9b0c1d2e3a4
Create Date: 2026-04-28 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'f9b0c1d2e3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # indexes — versioning and CDM binding
    op.add_column('indexes', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('indexes', sa.Column('parser', sa.String(), nullable=True))
    op.add_column('indexes', sa.Column('parse_config_hash', sa.String(), nullable=True))
    op.add_column('indexes', sa.Column('config_dirty', sa.Boolean(), nullable=False, server_default='false'))

    # index_documents — per-document parse run binding
    op.add_column('index_documents', sa.Column(
        'parse_run_id',
        sa.UUID(),
        sa.ForeignKey('parse_runs.id', ondelete='SET NULL'),
        nullable=True
    ))
    op.create_index('ix_index_documents_parse_run_id', 'index_documents', ['parse_run_id'])

    # chunks — provenance fields
    op.add_column('chunks', sa.Column('index_version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('chunks', sa.Column('parse_run_id', sa.UUID(), nullable=True))
    op.add_column('chunks', sa.Column('source_type', sa.String(), nullable=False, server_default='raw_text'))
    op.create_index('ix_chunks_source_type', 'chunks', ['source_type'])

    # index_events — write-once audit trail
    op.create_table(
        'index_events',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('index_id', sa.UUID(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('config_snapshot', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('document_bindings', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('triggered_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['index_id'], ['indexes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_index_events_index_id', 'index_events', ['index_id'])
    op.create_index('ix_index_events_index_version', 'index_events', ['index_id', 'version'])


def downgrade() -> None:
    op.drop_table('index_events')
    op.drop_index('ix_chunks_source_type', 'chunks')
    op.drop_column('chunks', 'source_type')
    op.drop_column('chunks', 'parse_run_id')
    op.drop_column('chunks', 'index_version')
    op.drop_index('ix_index_documents_parse_run_id', 'index_documents')
    op.drop_column('index_documents', 'parse_run_id')
    op.drop_column('indexes', 'config_dirty')
    op.drop_column('indexes', 'parse_config_hash')
    op.drop_column('indexes', 'parser')
    op.drop_column('indexes', 'version')
