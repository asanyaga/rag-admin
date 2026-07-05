"""Models for parser evaluation — scoring parser CDM output against per-dimension ground truth."""
from datetime import datetime
from uuid import UUID, uuid4
import enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ParserEvalDimension(str, enum.Enum):
    text = "text"          # first slice; table/reading_order/roles added later (seam #1)


class ParserEvalRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ParserEvalCase(Base):
    """A benchmark document plus its per-dimension ground-truth targets."""
    __tablename__ = "parser_eval_cases"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="RESTRICT"), nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=datetime.utcnow, server_default=sa.text('NOW()'))

    targets: Mapped[list["ParserEvalTarget"]] = relationship(
        back_populates="case", cascade="all, delete-orphan")

    __table_args__ = (
        sa.Index('ix_parser_eval_cases_project_id', 'project_id'),
    )


class ParserEvalTarget(Base):
    """One asserted dimension + its ground-truth payload for a case."""
    __tablename__ = "parser_eval_targets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_cases.id", ondelete="CASCADE"), nullable=False)
    dimension: Mapped[ParserEvalDimension] = mapped_column(
        Enum(ParserEvalDimension, name='parser_eval_dimension', create_type=False), nullable=False)
    expected: Mapped[dict] = mapped_column(JSON, nullable=False)

    case: Mapped["ParserEvalCase"] = relationship(back_populates="targets")

    __table_args__ = (
        sa.UniqueConstraint('case_id', 'dimension', name='uq_parser_eval_targets_case_dim'),
        sa.Index('ix_parser_eval_targets_case_id', 'case_id'),
    )


class ParserEvalRun(Base):
    """One execution over selected cases × parsers."""
    __tablename__ = "parser_eval_runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parsers: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default='[]')
    case_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default='[]')  # UUID strings
    status: Mapped[ParserEvalRunStatus] = mapped_column(
        Enum(ParserEvalRunStatus, name='parser_eval_run_status', create_type=False),
        nullable=False, default=ParserEvalRunStatus.pending, server_default='pending')
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=datetime.utcnow, server_default=sa.text('NOW()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=datetime.utcnow, onupdate=datetime.utcnow,
                                                 server_default=sa.text('NOW()'))

    results: Mapped[list["ParserEvalResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        sa.Index('ix_parser_eval_runs_project_id', 'project_id'),
    )


class ParserEvalResult(Base):
    """One score cell: (run, case, parser, dimension) -> score + details + cost/latency."""
    __tablename__ = "parser_eval_results"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_runs.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_cases.id", ondelete="CASCADE"), nullable=False)
    parser: Mapped[str] = mapped_column(String(64), nullable=False)
    dimension: Mapped[ParserEvalDimension] = mapped_column(
        Enum(ParserEvalDimension, name='parser_eval_dimension', create_type=False), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cost: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=datetime.utcnow, server_default=sa.text('NOW()'))

    run: Mapped["ParserEvalRun"] = relationship(back_populates="results")

    __table_args__ = (
        sa.UniqueConstraint('run_id', 'case_id', 'parser', 'dimension',
                            name='uq_parser_eval_results_run_case_parser_dim'),
        sa.Index('ix_parser_eval_results_run_id', 'run_id'),
    )
