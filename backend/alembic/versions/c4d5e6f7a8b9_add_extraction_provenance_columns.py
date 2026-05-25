"""add_extraction_provenance_columns

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a1
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b2c3d4e5f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "extraction_results",
        sa.Column("citations", sa.JSON(), nullable=True),
    )
    op.add_column(
        "extraction_results",
        sa.Column("provider_response_raw", sa.JSON(), nullable=True),
    )
    op.add_column(
        "extraction_results",
        sa.Column("source_parse_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_extraction_results_source_parse_run_id",
        "extraction_results",
        "parse_runs",
        ["source_parse_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_extraction_results_parse_run",
        "extraction_results",
        ["source_parse_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_extraction_results_parse_run", table_name="extraction_results")
    op.drop_constraint(
        "fk_extraction_results_source_parse_run_id",
        "extraction_results",
        type_="foreignkey",
    )
    op.drop_column("extraction_results", "source_parse_run_id")
    op.drop_column("extraction_results", "provider_response_raw")
    op.drop_column("extraction_results", "citations")
