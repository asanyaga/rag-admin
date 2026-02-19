"""add_imported_source_method

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE source_method_enum ADD VALUE IF NOT EXISTS 'imported'")


def downgrade() -> None:
    # Cannot remove enum values in PostgreSQL without recreating the type
    pass
