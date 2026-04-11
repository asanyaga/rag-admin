"""Model for generic agent execution runs."""
import enum
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AgentRunStatus(str, enum.Enum):
    """Status of an agent run."""
    pending = "pending"
    running = "running"
    waiting_for_input = "waiting_for_input"
    completed = "completed"
    failed = "failed"


class AgentRun(Base):
    """A single execution of an agent definition."""
    __tablename__ = "agent_runs"

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
    agent_definition_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_definitions.id", ondelete="CASCADE"),
        nullable=False
    )
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(AgentRunStatus, name='agent_run_status', create_type=False),
        nullable=False,
        default=AgentRunStatus.pending,
        server_default='pending'
    )
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    initial_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_node: Mapped[str | None] = mapped_column(String(255), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
    agent_definition: Mapped["AgentDefinition"] = relationship()
    user: Mapped["User"] = relationship()

    __table_args__ = (
        sa.Index('ix_agent_runs_project_id', 'project_id'),
        sa.Index('ix_agent_runs_status', 'status'),
        sa.Index('ix_agent_runs_agent_definition_id', 'agent_definition_id'),
        sa.Index('ix_agent_runs_thread_id', 'thread_id'),
    )
