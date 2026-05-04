"""drop ux_parse_runs_content_config unique constraint

Revision ID: 9a8b7c6d5e4f
Revises: 6f02c749d220
Create Date: 2026-05-04

Failed parse runs occupied the unique slot permanently, preventing retries.
The cache check in ParsingService already prevents redundant paid API calls.
"""
from alembic import op

revision = '9a8b7c6d5e4f'
down_revision = '6f02c749d220'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ux_parse_runs_content_config", table_name="parse_runs")


def downgrade() -> None:
    op.create_index(
        "ux_parse_runs_content_config",
        "parse_runs",
        ["source_document_id", "representation_kind", "config_hash"],
        unique=True,
    )
