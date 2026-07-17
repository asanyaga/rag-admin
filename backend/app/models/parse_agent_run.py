"""ORM models for the parse agent: orchestration run + append-only trace steps."""
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ParseAgentRunStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class ParseAgentRun(Base):
    __tablename__ = "parse_agent_runs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
    )
    source_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=datetime.utcnow, server_default=sa.text("NOW()"),
    )

    __table_args__ = (
        sa.Index("ix_parse_agent_runs_project_id", "project_id"),
        sa.Index("ix_parse_agent_runs_status", "status"),
    )


class ParseAgentRunStep(Base):
    __tablename__ = "parse_agent_run_steps"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parse_agent_runs.id", ondelete="CASCADE"), nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    node: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    input_keys: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default=sa.text("'[]'"))
    output_keys: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default=sa.text("'[]'"))
    state_delta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default=sa.text("'{}'"))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=datetime.utcnow, server_default=sa.text("NOW()"),
    )

    __table_args__ = (
        sa.Index("ix_parse_agent_run_steps_run_id_seq", "run_id", "seq"),
    )
