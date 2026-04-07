"""Models for extraction evaluation runs — scoring extraction results against ground truth."""
from datetime import datetime
from uuid import UUID, uuid4
import enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExtractionEvalRunStatus(str, enum.Enum):
    """Extraction evaluation run lifecycle status."""
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ExtractionEvalRun(Base):
    """An evaluation run comparing extraction results against a ground truth set."""
    __tablename__ = "extraction_eval_runs"

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
    ground_truth_set_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("extraction_ground_truth_sets.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default='{}'
    )
    status: Mapped[ExtractionEvalRunStatus] = mapped_column(
        Enum(ExtractionEvalRunStatus, name='extraction_eval_run_status', create_type=False),
        nullable=False,
        default=ExtractionEvalRunStatus.pending,
        server_default='pending'
    )
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_completed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    items_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
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
    project: Mapped["Project"] = relationship()
    ground_truth_set: Mapped["ExtractionGroundTruthSet"] = relationship()
    user: Mapped["User"] = relationship()
    results: Mapped[list["ExtractionEvalResult"]] = relationship(
        back_populates="eval_run",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        sa.Index('ix_extraction_eval_runs_project_id', 'project_id'),
        sa.Index('ix_extraction_eval_runs_gt_set_id', 'ground_truth_set_id'),
        sa.Index('ix_extraction_eval_runs_created_at', 'created_at'),
    )


class ExtractionEvalResult(Base):
    """Per-document scoring result within an extraction evaluation run."""
    __tablename__ = "extraction_eval_results"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text('gen_random_uuid()')
    )
    eval_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("extraction_eval_runs.id", ondelete="CASCADE"),
        nullable=False
    )
    extraction_result_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("extraction_results.id", ondelete="CASCADE"),
        nullable=False
    )
    ground_truth_item_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("extraction_ground_truth_items.id", ondelete="CASCADE"),
        nullable=False
    )
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    field_scores: Mapped[dict] = mapped_column(JSON, nullable=False)
    line_items_score: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evaluation_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text('NOW()')
    )

    # Relationships
    eval_run: Mapped["ExtractionEvalRun"] = relationship(back_populates="results")
    extraction_result: Mapped["ExtractionResult"] = relationship()
    ground_truth_item: Mapped["ExtractionGroundTruthItem"] = relationship()

    __table_args__ = (
        sa.UniqueConstraint('eval_run_id', 'ground_truth_item_id', name='uq_extraction_eval_results_run_item'),
        sa.Index('ix_extraction_eval_results_run_id', 'eval_run_id'),
        sa.Index('ix_extraction_eval_results_gt_item_id', 'ground_truth_item_id'),
    )
