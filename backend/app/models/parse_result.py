"""Models for parse results — document parsing via various parsers."""
from datetime import datetime
from uuid import UUID, uuid4
import enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ParseResultStatus(str, enum.Enum):
    """Parse result lifecycle status."""
    pending = "pending"
    completed = "completed"
    failed = "failed"


class ParseResult(Base):
    """A parser's description of a document."""
    __tablename__ = "parse_results"

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
    parser_type: Mapped[str] = mapped_column(String(50), nullable=False)
    fidelity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="text", server_default="text"
    )
    parser_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    pages: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    document_structure: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    diagnostics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    status: Mapped[ParseResultStatus] = mapped_column(
        Enum(ParseResultStatus, name='parse_result_status', create_type=False),
        nullable=False,
        default=ParseResultStatus.pending,
        server_default='pending'
    )
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    user: Mapped["User"] = relationship()

    __table_args__ = (
        sa.Index('ix_parse_results_document_parser', 'document_id', 'parser_type'),
        sa.Index('ix_parse_results_document_id', 'document_id'),
    )
