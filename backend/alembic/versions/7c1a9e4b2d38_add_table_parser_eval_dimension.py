"""add table parser_eval_dimension value

Revision ID: 7c1a9e4b2d38
Revises: 9f3b7c2e1a04
Create Date: 2026-07-07 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '7c1a9e4b2d38'
down_revision: Union[str, None] = '9f3b7c2e1a04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE parser_eval_dimension ADD VALUE IF NOT EXISTS 'table'")


def downgrade() -> None:
    # PostgreSQL cannot drop an enum value without recreating the type; no-op.
    pass
