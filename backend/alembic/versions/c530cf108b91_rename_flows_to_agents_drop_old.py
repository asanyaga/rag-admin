"""Rename flow tables to agent tables and drop old agent prototype tables.

Revision ID: c530cf108b91
Revises: 23528140ed0b
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c530cf108b91'
down_revision: Union[str, None] = '23528140ed0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old agent prototype tables
    op.drop_table("agent_receipts")
    op.drop_table("agent_configs")
    op.execute("DROP TYPE IF EXISTS agent_receipt_status")

    # Rename flow tables to agent
    op.rename_table("flow_definitions", "agent_definitions")
    op.rename_table("flow_runs", "agent_runs")

    # Rename flow_run_status enum to agent_run_status
    op.execute("ALTER TYPE flow_run_status RENAME TO agent_run_status")

    # Rename FK column in agent_runs
    op.alter_column("agent_runs", "flow_definition_id", new_column_name="agent_definition_id")

    # Rename indexes on agent_definitions
    op.execute("ALTER INDEX ix_flow_definitions_project_id RENAME TO ix_agent_definitions_project_id")
    op.execute(
        "ALTER TABLE agent_definitions RENAME CONSTRAINT "
        "uq_flow_definitions_project_name TO uq_agent_definitions_project_name"
    )

    # Rename indexes on agent_runs
    op.execute("ALTER INDEX ix_flow_runs_project_id RENAME TO ix_agent_runs_project_id")
    op.execute("ALTER INDEX ix_flow_runs_status RENAME TO ix_agent_runs_status")
    op.execute("ALTER INDEX ix_flow_runs_flow_definition_id RENAME TO ix_agent_runs_agent_definition_id")
    op.execute("ALTER INDEX ix_flow_runs_thread_id RENAME TO ix_agent_runs_thread_id")

    # Rename FK constraints on agent_runs
    op.execute(
        "ALTER TABLE agent_runs RENAME CONSTRAINT "
        "flow_runs_flow_definition_id_fkey TO agent_runs_agent_definition_id_fkey"
    )
    op.execute(
        "ALTER TABLE agent_runs RENAME CONSTRAINT "
        "flow_runs_project_id_fkey TO agent_runs_project_id_fkey"
    )
    op.execute(
        "ALTER TABLE agent_runs RENAME CONSTRAINT "
        "flow_runs_created_by_fkey TO agent_runs_created_by_fkey"
    )
    op.execute(
        "ALTER TABLE agent_runs RENAME CONSTRAINT "
        "flow_runs_pkey TO agent_runs_pkey"
    )

    # Rename FK constraints on agent_definitions
    op.execute(
        "ALTER TABLE agent_definitions RENAME CONSTRAINT "
        "flow_definitions_project_id_fkey TO agent_definitions_project_id_fkey"
    )
    op.execute(
        "ALTER TABLE agent_definitions RENAME CONSTRAINT "
        "flow_definitions_created_by_fkey TO agent_definitions_created_by_fkey"
    )
    op.execute(
        "ALTER TABLE agent_definitions RENAME CONSTRAINT "
        "flow_definitions_pkey TO agent_definitions_pkey"
    )


def downgrade() -> None:
    # Reverse PK constraints
    op.execute(
        "ALTER TABLE agent_definitions RENAME CONSTRAINT "
        "agent_definitions_pkey TO flow_definitions_pkey"
    )
    op.execute(
        "ALTER TABLE agent_definitions RENAME CONSTRAINT "
        "agent_definitions_created_by_fkey TO flow_definitions_created_by_fkey"
    )
    op.execute(
        "ALTER TABLE agent_definitions RENAME CONSTRAINT "
        "agent_definitions_project_id_fkey TO flow_definitions_project_id_fkey"
    )
    op.execute(
        "ALTER TABLE agent_runs RENAME CONSTRAINT "
        "agent_runs_pkey TO flow_runs_pkey"
    )
    op.execute(
        "ALTER TABLE agent_runs RENAME CONSTRAINT "
        "agent_runs_created_by_fkey TO flow_runs_created_by_fkey"
    )
    op.execute(
        "ALTER TABLE agent_runs RENAME CONSTRAINT "
        "agent_runs_project_id_fkey TO flow_runs_project_id_fkey"
    )
    op.execute(
        "ALTER TABLE agent_runs RENAME CONSTRAINT "
        "agent_runs_agent_definition_id_fkey TO flow_runs_flow_definition_id_fkey"
    )

    # Reverse index renames
    op.execute("ALTER INDEX ix_agent_runs_thread_id RENAME TO ix_flow_runs_thread_id")
    op.execute("ALTER INDEX ix_agent_runs_agent_definition_id RENAME TO ix_flow_runs_flow_definition_id")
    op.execute("ALTER INDEX ix_agent_runs_status RENAME TO ix_flow_runs_status")
    op.execute("ALTER INDEX ix_agent_runs_project_id RENAME TO ix_flow_runs_project_id")
    op.execute(
        "ALTER TABLE agent_definitions RENAME CONSTRAINT "
        "uq_agent_definitions_project_name TO uq_flow_definitions_project_name"
    )
    op.execute("ALTER INDEX ix_agent_definitions_project_id RENAME TO ix_flow_definitions_project_id")

    # Reverse column rename
    op.alter_column("agent_runs", "agent_definition_id", new_column_name="flow_definition_id")

    # Reverse enum rename
    op.execute("ALTER TYPE agent_run_status RENAME TO flow_run_status")

    # Reverse table renames
    op.rename_table("agent_runs", "flow_runs")
    op.rename_table("agent_definitions", "flow_definitions")

    # Note: old agent_configs and agent_receipts tables are NOT recreated in downgrade
