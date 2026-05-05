"""add classification tables

Revision ID: a1b2c3d4e5f6
Revises: 9a8b7c6d5e4f
Create Date: 2026-05-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9a8b7c6d5e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "classification_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("parse_run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("parse_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("labels_requested", postgresql.JSONB(), nullable=False),
        sa.Column("llm_provider", sa.Text(), nullable=False),
        sa.Column("llm_model", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("batch_overlap", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_classification_runs_parse_run_id", "classification_runs", ["parse_run_id"])
    op.create_index("ix_classification_runs_document_id", "classification_runs", ["document_id"])
    op.create_index("ix_classification_runs_status", "classification_runs", ["status"])

    op.create_table(
        "classification_regions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("classification_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("block_ids", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="llm"),
    )
    op.create_index("ix_classification_regions_run_id", "classification_regions", ["run_id"])
    op.create_index("ix_classification_regions_label", "classification_regions", ["label"])


def downgrade() -> None:
    op.drop_index("ix_classification_regions_label", table_name="classification_regions")
    op.drop_index("ix_classification_regions_run_id", table_name="classification_regions")
    op.drop_table("classification_regions")

    op.drop_index("ix_classification_runs_status", table_name="classification_runs")
    op.drop_index("ix_classification_runs_document_id", table_name="classification_runs")
    op.drop_index("ix_classification_runs_parse_run_id", table_name="classification_runs")
    op.drop_table("classification_runs")
