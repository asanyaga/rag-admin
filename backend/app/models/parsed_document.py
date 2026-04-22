"""ORM model for ParsedDocument — content blob layer."""
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ParsedDocument(Base):
    __tablename__ = "parsed_documents"

    parse_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parse_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    block_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=datetime.utcnow, server_default=sa.text("NOW()"),
    )

    __table_args__ = (
        sa.Index("ix_parsed_documents_source_document_id", "source_document_id"),
    )
