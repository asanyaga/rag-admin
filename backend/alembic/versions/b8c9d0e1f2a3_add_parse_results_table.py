"""add_parse_results_table

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-03-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create parse_result_status enum (idempotent)
    op.execute(sa.text(
        "DO $$ BEGIN "
        "CREATE TYPE parse_result_status AS ENUM ('pending', 'completed', 'failed'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$"
    ))

    op.create_table(
        'parse_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('parser_type', sa.String(50), nullable=False),
        sa.Column('fidelity', sa.String(20), server_default='text', nullable=False),
        sa.Column('parser_config', sa.JSON(), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('markdown', sa.Text(), nullable=True),
        sa.Column('pages', sa.JSON(), nullable=True),
        sa.Column('document_structure', sa.JSON(), nullable=True),
        sa.Column('diagnostics', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'completed', 'failed', name='parse_result_status', create_type=False), server_default='pending', nullable=False),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_parse_results_document_parser', 'parse_results', ['document_id', 'parser_type'])
    op.create_index('ix_parse_results_document_id', 'parse_results', ['document_id'])


def downgrade() -> None:
    op.drop_index('ix_parse_results_document_id', table_name='parse_results')
    op.drop_index('ix_parse_results_document_parser', table_name='parse_results')
    op.drop_table('parse_results')

    # Drop enum type
    parse_result_status = postgresql.ENUM(
        'pending', 'completed', 'failed',
        name='parse_result_status',
    )
    parse_result_status.drop(op.get_bind(), checkfirst=True)
