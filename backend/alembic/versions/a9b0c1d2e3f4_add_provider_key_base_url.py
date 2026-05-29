"""add_provider_key_base_url

Revision ID: a9b0c1d2e3f4
Revises: extraction_llm_method
Create Date: 2026-05-28 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a9b0c1d2e3f4'
down_revision: Union[str, None] = 'extraction_llm_method'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('provider_keys', sa.Column('base_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('provider_keys', 'base_url')
