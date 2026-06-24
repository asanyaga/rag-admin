"""Models for extraction results — structured data extracted from documents."""
from datetime import datetime
from uuid import UUID, uuid4
import enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExtractionResultStatus(str, enum.Enum):
    """Extraction result lifecycle status."""
    pending = "pending"
    completed = "completed"
    failed = "failed"


class ExtractionResult(Base):
    """A structured data extraction result from a document."""
    __tablename__ = "extraction_results"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text('gen_random_uuid()')
    )
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False
    )
    extraction_schema_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("extraction_schemas.id", ondelete="CASCADE"),
        nullable=False
    )
    schema_definition_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(30), nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    structured_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extraction_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[ExtractionResultStatus] = mapped_column(
        Enum(ExtractionResultStatus, name='extraction_result_status', create_type=False),
        nullable=False,
        default=ExtractionResultStatus.pending,
        server_default='pending'
    )
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    timeout_minutes: Mapped[int | None] = mapped_column(
        sa.Integer(), nullable=True
    )
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    provider_response_raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_parse_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parse_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[UUID] = mapped_column(
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=sa.text('NOW()')
    )

    # Relationships
    document: Mapped["Document"] = relationship()
    extraction_schema: Mapped["ExtractionSchema"] = relationship(
        back_populates="extraction_results"
    )
    user: Mapped["User"] = relationship()

    __table_args__ = (
        sa.Index('ix_extraction_results_document_schema', 'document_id', 'extraction_schema_id'),
        sa.Index('ix_extraction_results_document_id', 'document_id'),
        sa.Index('ix_extraction_results_status', 'status'),
        sa.Index('ix_extraction_results_parse_run', 'source_parse_run_id'),
    )
