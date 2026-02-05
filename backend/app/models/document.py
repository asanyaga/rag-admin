from datetime import datetime
from uuid import UUID, uuid4
import enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentStatus(str, enum.Enum):
    """Document processing status enum."""
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    # Identity
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text('gen_random_uuid()')
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False
    )

    # Source tracking
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    source_identifier: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    # Universal metadata
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Content (for RAG)
    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Source-specific details (JSON)
    source_metadata: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default='{}'
    )

    # Processing metadata (JSON)
    processing_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        server_default='{}'
    )

    # Status
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name='document_status', create_type=False),
        nullable=False,
        default=DocumentStatus.processing,
        server_default='processing'
    )
    status_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Audit
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
    project: Mapped["Project"] = relationship(back_populates="documents")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        sa.UniqueConstraint('project_id', 'source_type', 'source_identifier', name='uq_documents_project_source'),
        sa.Index('ix_documents_project_id', 'project_id'),
        sa.Index('ix_documents_source_type', 'source_type'),
        sa.Index('ix_documents_status', 'status'),
        sa.Index('ix_documents_created_at', 'created_at'),
    )
