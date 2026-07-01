"""rename local_pipeline to custom_pipeline in parse_runs.parser

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE parse_runs SET parser = 'custom_pipeline' WHERE parser = 'local_pipeline'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE parse_runs SET parser = 'local_pipeline' WHERE parser = 'custom_pipeline'"
        )
    )
