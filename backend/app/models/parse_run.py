"""ORM model for ParseRun — execution + provenance layer."""
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ParseRun(Base):
    __tablename__ = "parse_runs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    source_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    parser: Mapped[str] = mapped_column(Text, nullable=False)
    parser_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    representation_kind: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default=sa.text("'{}'")
    )
    config_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default=sa.text("'{}'")
    )
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default=sa.text("'[]'")
    )
    failed_pages: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default=sa.text("'[]'")
    )
    provider_refs: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default=sa.text("'{}'")
    )
    raw_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=datetime.utcnow, server_default=sa.text("NOW()"),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "source_document_id", "representation_kind", "config_hash",
            name="ux_parse_runs_content_config",
        ),
        sa.Index("ix_parse_runs_status", "status"),
        sa.Index("ix_parse_runs_source_document_id", "source_document_id"),
    )
