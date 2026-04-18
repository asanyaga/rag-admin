"""add_folders

Revision ID: a8b9c0d1e2f3
Revises: f8a9b0c1d2e3
Create Date: 2026-04-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'folders',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'name', name='uq_folders_project_name'),
    )
    op.create_index('ix_folders_project_id', 'folders', ['project_id'])

    op.add_column(
        'documents',
        sa.Column('folder_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_documents_folder_id',
        'documents', 'folders',
        ['folder_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_documents_folder_id', 'documents', ['folder_id'])


def downgrade() -> None:
    op.drop_index('ix_documents_folder_id', table_name='documents')
    op.drop_constraint('fk_documents_folder_id', 'documents', type_='foreignkey')
    op.drop_column('documents', 'folder_id')

    op.drop_index('ix_folders_project_id', table_name='folders')
    op.drop_table('folders')
