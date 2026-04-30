"""tighten index_documents.parse_run_id FK to cascade

Revision ID: 4a24c798e847
Revises: a2b3c4d5e6f7
Create Date: 2026-04-30 10:22:10.718047

In the parsed-document-centric model introduced by Unit 1 of the parsed-document
refactor, an `index_documents` row references the parse_run that produced its
content blob (`parsed_documents` is keyed 1:1 on `parse_run_id`). When the
parse_run is deleted, the parsed_document is gone and the index_documents row
has nothing left to read — cascade-delete the row instead of leaving it with
parse_run_id NULL (the prior `SET NULL` behaviour).

Legacy raw_text rows (which already have `parse_run_id IS NULL`) are unaffected.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '4a24c798e847'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FK_NAME = "index_documents_parse_run_id_fkey"


def upgrade() -> None:
    op.drop_constraint(FK_NAME, "index_documents", type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        "index_documents",
        "parse_runs",
        ["parse_run_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(FK_NAME, "index_documents", type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        "index_documents",
        "parse_runs",
        ["parse_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
