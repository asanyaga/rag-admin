"""Models for parser evaluation — canonical eval entity model.

Eval Case = (source document, dimension, ground-truth `expected`). Dataset is an M:N
container over cases. A Run executes variants=(adapter, config) over a snapshot of cases;
each Result is one (run, case, variant) cell holding a metrics map.
"""
from datetime import datetime
from uuid import UUID, uuid4
import enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ParserEvalDimension(str, enum.Enum):
    text = "text"          # seam #1: table/reading_order/roles added later


class ParserEvalSourceMethod(str, enum.Enum):
    human = "human"
    generated = "generated"
    bootstrapped = "bootstrapped"


class ParserEvalReviewStatus(str, enum.Enum):
    draft = "draft"
    verified = "verified"


class ParserEvalRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ParserEvalCase(Base):
    """Input + ground truth: one asserted dimension of one source document."""
    __tablename__ = "parser_eval_cases"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    source_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="RESTRICT"), nullable=False)
    dimension: Mapped[ParserEvalDimension] = mapped_column(
        Enum(ParserEvalDimension, name='parser_eval_dimension', create_type=False), nullable=False)
    expected: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_method: Mapped[ParserEvalSourceMethod] = mapped_column(
        Enum(ParserEvalSourceMethod, name='parser_eval_source_method', create_type=False),
        nullable=False, default=ParserEvalSourceMethod.human, server_default='human')
    review_status: Mapped[ParserEvalReviewStatus] = mapped_column(
        Enum(ParserEvalReviewStatus, name='parser_eval_review_status', create_type=False),
        nullable=False, default=ParserEvalReviewStatus.draft, server_default='draft')
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=datetime.utcnow, server_default=sa.text('NOW()'))

    __table_args__ = (
        sa.UniqueConstraint('source_document_id', 'dimension', name='uq_parser_eval_cases_source_dim'),
        sa.Index('ix_parser_eval_cases_project_id', 'project_id'),
    )


class ParserEvalDataset(Base):
    """A curated container over eval cases (M:N)."""
    __tablename__ = "parser_eval_datasets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=datetime.utcnow, server_default=sa.text('NOW()'))

    cases: Mapped[list["ParserEvalCase"]] = relationship(
        secondary="parser_eval_dataset_cases", lazy="selectin")

    __table_args__ = (
        sa.Index('ix_parser_eval_datasets_project_id', 'project_id'),
    )


class ParserEvalDatasetCase(Base):
    """M:N membership of an eval case in a dataset."""
    __tablename__ = "parser_eval_dataset_cases"

    dataset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_datasets.id", ondelete="CASCADE"),
        primary_key=True)
    eval_case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_cases.id", ondelete="CASCADE"),
        primary_key=True)


class ParserEvalRun(Base):
    """One execution of variants=(adapter, config) over a snapshot of cases."""
    __tablename__ = "parser_eval_runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    variants: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default='[]')
    eval_case_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default='[]')
    dataset_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_datasets.id", ondelete="SET NULL"), nullable=True)
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
    """One score cell: (run, eval_case, variant) -> metrics map + attribution + cost/latency.

    Append-only / immutable: a probabilistic variant may produce a different output per
    execution, so results are never overwritten. Retry = a new run.
    """
    __tablename__ = "parser_eval_results"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_runs.id", ondelete="CASCADE"), nullable=False)
    eval_case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_cases.id", ondelete="CASCADE"), nullable=False)
    adapter: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default='{}')
    variant_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default='{}')
    primary_metric: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cost: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=datetime.utcnow, server_default=sa.text('NOW()'))

    run: Mapped["ParserEvalRun"] = relationship(back_populates="results")

    __table_args__ = (
        sa.UniqueConstraint('run_id', 'eval_case_id', 'variant_key',
                            name='uq_parser_eval_results_run_case_variant'),
        sa.Index('ix_parser_eval_results_run_id', 'run_id'),
    )
