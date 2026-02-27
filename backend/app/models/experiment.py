"""Models for experiments — grouping eval runs into hypothesis-driven collections."""
from datetime import datetime
from uuid import UUID, uuid4
import enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExperimentStatus(str, enum.Enum):
    """Experiment lifecycle status."""
    active = "active"
    concluded = "concluded"


class Experiment(Base):
    """An experiment that groups eval runs into a hypothesis-driven collection."""
    __tablename__ = "experiments"

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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    baseline_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="SET NULL"),
        nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ExperimentStatus] = mapped_column(
        Enum(ExperimentStatus, name='experiment_status', create_type=False),
        nullable=False,
        default=ExperimentStatus.active,
        server_default='active'
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
    user: Mapped["User"] = relationship()
    baseline_run: Mapped["EvalRun"] = relationship(
        foreign_keys=[baseline_run_id],
    )
    runs: Mapped[list["EvalRun"]] = relationship(
        back_populates="experiment",
        foreign_keys="EvalRun.experiment_id",
    )

    __table_args__ = (
        sa.Index('ix_experiments_project_id', 'project_id'),
    )
