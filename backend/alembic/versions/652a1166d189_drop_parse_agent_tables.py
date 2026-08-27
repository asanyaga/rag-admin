"""drop parse_agent tables

Revision ID: 652a1166d189
Revises: 12035df46d0d
Create Date: 2026-08-26 15:25:08.015780

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '652a1166d189'
down_revision: Union[str, None] = '12035df46d0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Dropping the table cascades its indexes on Postgres; drop the child
    # (FK-referencing) table before the parent to satisfy the FK constraint.
    op.drop_table("parse_agent_run_steps")
    op.drop_table("parse_agent_runs")


def downgrade() -> None:
    # Recreation is intentionally not supported — the parse-agent stack is retired.
    raise NotImplementedError("parse_agent tables are retired; no downgrade")
