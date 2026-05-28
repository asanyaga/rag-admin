"""extraction_method_ollama_to_llm

Revision ID: extraction_llm_method
Revises: cdc883e9de71
Create Date: 2026-05-28 14:51:57.122052

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'extraction_llm_method'
down_revision: Union[str, None] = 'cdc883e9de71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE extraction_results SET extraction_method = 'llm' "
        "WHERE extraction_method = 'ollama'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE extraction_results SET extraction_method = 'ollama' "
        "WHERE extraction_method = 'llm'"
    )
