"""create parse_agent_run tables

Revision ID: 12035df46d0d
Revises: 7c1a9e4b2d38
Create Date: 2026-07-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "12035df46d0d"
down_revision: Union[str, None] = "7c1a9e4b2d38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parse_agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_parse_agent_runs_project_id", "parse_agent_runs", ["project_id"])
    op.create_index("ix_parse_agent_runs_status", "parse_agent_runs", ["status"])

    op.create_table(
        "parse_agent_run_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("parse_agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("node", sa.Text(), nullable=False),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("input_keys", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("output_keys", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("state_delta", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "ix_parse_agent_run_steps_run_id_seq",
        "parse_agent_run_steps",
        ["run_id", "seq"],
    )


def downgrade() -> None:
    op.drop_index("ix_parse_agent_run_steps_run_id_seq", table_name="parse_agent_run_steps")
    op.drop_table("parse_agent_run_steps")

    op.drop_index("ix_parse_agent_runs_status", table_name="parse_agent_runs")
    op.drop_index("ix_parse_agent_runs_project_id", table_name="parse_agent_runs")
    op.drop_table("parse_agent_runs")
