"""add_agent_receipts_table

Revision ID: 0b92f2f67990
Revises: d2e3f4a5b6c7
Create Date: 2026-04-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0b92f2f67990'
down_revision: Union[str, None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enum type
    agent_receipt_status = postgresql.ENUM(
        'pending', 'extracting', 'reviewing', 'approved', 'exported', 'failed',
        name='agent_receipt_status',
        create_type=True,
    )
    agent_receipt_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'agent_receipts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('extraction_schema_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('pending', 'extracting', 'reviewing', 'approved', 'exported', 'failed', name='agent_receipt_status', create_type=False), server_default='pending', nullable=False),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('extracted_data', sa.JSON(), nullable=True),
        sa.Column('reviewed_data', sa.JSON(), nullable=True),
        sa.Column('thread_id', sa.String(length=64), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['extraction_schema_id'], ['extraction_schemas.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_receipts_project_id', 'agent_receipts', ['project_id'])
    op.create_index('ix_agent_receipts_status', 'agent_receipts', ['status'])
    op.create_index('ix_agent_receipts_thread_id', 'agent_receipts', ['thread_id'])


def downgrade() -> None:
    op.drop_index('ix_agent_receipts_thread_id', table_name='agent_receipts')
    op.drop_index('ix_agent_receipts_status', table_name='agent_receipts')
    op.drop_index('ix_agent_receipts_project_id', table_name='agent_receipts')
    op.drop_table('agent_receipts')
    sa.Enum(name='agent_receipt_status').drop(op.get_bind(), checkfirst=True)
