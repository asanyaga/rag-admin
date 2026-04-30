"""cascade delete legacy raw_text indexes

Revision ID: 6f02c749d220
Revises: 4a24c798e847
Create Date: 2026-04-30 16:58:22.029233

CDM Index Unit 3 cleanup: deletes any `indexes` row that has at least one
`index_documents` row with `parse_run_id IS NULL`. Those rows pre-date the
parsed-document model and would fail post-Unit-3 schema validation.

The cascade is via existing FK ON DELETE CASCADE on `index_documents`,
`chunks`, and `index_events` against `indexes.id`.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '6f02c749d220'
down_revision: str | None = '4a24c798e847'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM indexes
        WHERE id IN (
            SELECT DISTINCT index_id FROM index_documents
            WHERE parse_run_id IS NULL
        )
        """
    )


def downgrade() -> None:
    """No-op.

    Data deletion is not reversible — downgrading this migration restores no
    data. The schema is unchanged in either direction.
    """
    pass
