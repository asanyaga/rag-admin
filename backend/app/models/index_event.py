from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class IndexEvent(Base):
    """Write-once audit record capturing a snapshot of index configuration at a point in time.

    Each IndexEvent records the full config and document bindings at the moment a
    processing run is triggered. Events are immutable — they are never updated.
    """
    __tablename__ = "index_events"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text('gen_random_uuid()')
    )
    index_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("indexes.id", ondelete="CASCADE"),
        nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    config_snapshot: Mapped[dict] = mapped_column(
        sa.JSON, nullable=False, default=dict, server_default='{}'
    )
    document_bindings: Mapped[dict] = mapped_column(
        sa.JSON, nullable=False, default=dict, server_default='{}'
    )
    triggered_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text('NOW()')
    )

    # Relationship to Index — back_populates added in Task 3 when Index gains index_events
    index: Mapped["Index"] = relationship(foreign_keys=[index_id])

    __table_args__ = (
        sa.Index('ix_index_events_index_id', 'index_id'),
        sa.Index('ix_index_events_index_version', 'index_id', 'version'),
    )
