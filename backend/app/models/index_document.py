from datetime import datetime
from uuid import UUID
import enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class IndexDocumentStatus(str, enum.Enum):
    """Per-document processing status within an index."""
    pending = "pending"  # Not yet processed
    processing = "processing"  # Currently being chunked/embedded
    completed = "completed"  # Successfully processed
    failed = "failed"  # Processing failed for this document


class IndexDocument(Base):
    """Join table tracking document inclusion and processing status in an index.

    This table enables:
    - Many-to-many relationship between indexes and documents
    - Per-document processing status tracking for granular error reporting
    - Incremental processing (only new docs are chunked/embedded)
    """
    __tablename__ = "index_documents"

    # Composite primary key
    index_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("indexes.id", ondelete="CASCADE"),
        primary_key=True
    )
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True
    )

    # Processing status
    processing_status: Mapped[IndexDocumentStatus] = mapped_column(
        Enum(IndexDocumentStatus, name='index_document_status', create_type=False),
        nullable=False,
        default=IndexDocumentStatus.pending,
        server_default='pending'
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Processing metrics (populated after successful processing)
    chunks_created: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True
    )

    # Relationships
    index: Mapped["Index"] = relationship(back_populates="index_documents")
    document: Mapped["Document"] = relationship(back_populates="index_documents")

    __table_args__ = (
        sa.Index('ix_index_documents_index_id', 'index_id'),
        sa.Index('ix_index_documents_document_id', 'document_id'),
        sa.Index('ix_index_documents_status', 'processing_status'),
    )
