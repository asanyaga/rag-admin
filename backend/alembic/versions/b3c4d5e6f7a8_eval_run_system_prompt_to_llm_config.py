"""eval_run_system_prompt_to_llm_config

Revision ID: b3c4d5e6f7a8
Revises: a7b8c9d0e1f2
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('eval_runs', sa.Column('llm_config', sa.JSON(), nullable=True))
    op.execute(
        "UPDATE eval_runs "
        "SET llm_config = jsonb_build_object('system_prompt', system_prompt) "
        "WHERE system_prompt IS NOT NULL"
    )
    op.drop_column('eval_runs', 'system_prompt')


def downgrade() -> None:
    op.add_column('eval_runs', sa.Column('system_prompt', sa.Text(), nullable=True))
    op.execute(
        "UPDATE eval_runs "
        "SET system_prompt = llm_config->>'system_prompt' "
        "WHERE llm_config IS NOT NULL AND llm_config ? 'system_prompt'"
    )
    op.drop_column('eval_runs', 'llm_config')
