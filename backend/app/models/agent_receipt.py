"""Models for agent receipt processing pipeline."""
from datetime import datetime
from uuid import UUID, uuid4
import enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AgentReceiptStatus(str, enum.Enum):
    """Receipt processing pipeline status."""
    pending = "pending"
    extracting = "extracting"
    reviewing = "reviewing"
    approved = "approved"
    exported = "exported"
    failed = "failed"


class AgentReceipt(Base):
    """A receipt being processed through the LangGraph agent pipeline."""
    __tablename__ = "agent_receipts"

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
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False
    )
    extraction_schema_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("extraction_schemas.id"),
        nullable=False
    )
    status: Mapped[AgentReceiptStatus] = mapped_column(
        Enum(AgentReceiptStatus, name='agent_receipt_status', create_type=False),
        nullable=False,
        default=AgentReceiptStatus.pending,
        server_default='pending'
    )
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reviewed_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
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
    project: Mapped["Project"] = relationship()
    document: Mapped["Document"] = relationship()
    extraction_schema: Mapped["ExtractionSchema"] = relationship()
    user: Mapped["User"] = relationship()

    __table_args__ = (
        sa.Index('ix_agent_receipts_project_id', 'project_id'),
        sa.Index('ix_agent_receipts_status', 'status'),
    )
