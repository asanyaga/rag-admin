"""Models for evaluation runs — executing golden set queries against an index."""
from datetime import datetime
from uuid import UUID, uuid4
import enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EvalRunStatus(str, enum.Enum):
    """Evaluation run lifecycle status."""
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    partial_failure = "partial_failure"


class EvalRun(Base):
    """An evaluation run that tests retrieval quality against a golden set."""
    __tablename__ = "eval_runs"

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
    golden_set_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("golden_sets.id", ondelete="CASCADE"),
        nullable=False
    )
    index_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("indexes.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default='{}'
    )
    status: Mapped[EvalRunStatus] = mapped_column(
        Enum(EvalRunStatus, name='eval_run_status', create_type=False),
        nullable=False,
        default=EvalRunStatus.pending,
        server_default='pending'
    )
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Answer eval fields
    mode: Mapped[str] = mapped_column(
        String(30), nullable=False, default="retrieval_only",
        server_default="retrieval_only"
    )
    generation_model_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    generation_model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    judge_model_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    judge_model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_completed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    failed_item_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # Experiment fields
    experiment_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="SET NULL"),
        nullable=True
    )
    variant_label: Mapped[str | None] = mapped_column(String(255), nullable=True)

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
    golden_set: Mapped["GoldenSet"] = relationship()
    index: Mapped["Index"] = relationship()
    user: Mapped["User"] = relationship()
    experiment: Mapped["Experiment"] = relationship(
        back_populates="runs",
        foreign_keys=[experiment_id],
    )
    results: Mapped[list["EvalRunResult"]] = relationship(
        back_populates="eval_run",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        sa.Index('ix_eval_runs_project_id', 'project_id'),
        sa.Index('ix_eval_runs_golden_set_id', 'golden_set_id'),
        sa.Index('ix_eval_runs_index_id', 'index_id'),
        sa.Index('ix_eval_runs_created_at', 'created_at'),
        sa.Index('ix_eval_runs_experiment_id', 'experiment_id'),
    )


class EvalRunResult(Base):
    """Per-query result within an evaluation run."""
    __tablename__ = "eval_run_results"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text('gen_random_uuid()')
    )
    eval_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False
    )
    query_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("golden_set_queries.id", ondelete="CASCADE"),
        nullable=False
    )
    precision: Mapped[float] = mapped_column(Float, nullable=False)
    recall: Mapped[float] = mapped_column(Float, nullable=False)
    f1: Mapped[float] = mapped_column(Float, nullable=False)
    retrieved_chunks: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default='[]'
    )

    # Answer eval fields
    generated_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    faithfulness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    claim_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    judge_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Query trace data
    trace_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text('NOW()')
    )

    # Relationships
    eval_run: Mapped["EvalRun"] = relationship(back_populates="results")
    query: Mapped["GoldenSetQuery"] = relationship()

    __table_args__ = (
        sa.Index('ix_eval_run_results_eval_run_id', 'eval_run_id'),
        sa.Index('ix_eval_run_results_query_id', 'query_id'),
    )
