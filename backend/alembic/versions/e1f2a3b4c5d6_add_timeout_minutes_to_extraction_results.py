"""add_timeout_minutes_to_extraction_results

Revision ID: e1f2a3b4c5d6
Revises: aed9d6c56057
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "aed9d6c56057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "extraction_results",
        sa.Column("timeout_minutes", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("extraction_results", "timeout_minutes")
