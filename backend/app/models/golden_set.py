"""Models for golden sets — ground-truth query + expected source pairs for evaluation."""
from datetime import datetime
from uuid import UUID, uuid4
import enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GoldenSetStatus(str, enum.Enum):
    """Golden set lifecycle status."""
    draft = "draft"
    completed = "completed"


class GoldenSet(Base):
    """A collection of queries with expected retrieval sources for evaluation."""
    __tablename__ = "golden_sets"

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
    status: Mapped[GoldenSetStatus] = mapped_column(
        Enum(GoldenSetStatus, name='golden_set_status', create_type=False),
        nullable=False,
        default=GoldenSetStatus.draft,
        server_default='draft'
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
    queries: Mapped[list["GoldenSetQuery"]] = relationship(
        back_populates="golden_set",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        sa.Index('ix_golden_sets_project_id', 'project_id'),
        sa.Index('ix_golden_sets_created_at', 'created_at'),
    )


class GoldenSetQuery(Base):
    """A single query within a golden set."""
    __tablename__ = "golden_set_queries"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text('gen_random_uuid()')
    )
    golden_set_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("golden_sets.id", ondelete="CASCADE"),
        nullable=False
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
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
    golden_set: Mapped["GoldenSet"] = relationship(back_populates="queries")
    sources: Mapped[list["GoldenSetSource"]] = relationship(
        back_populates="query",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        sa.Index('ix_golden_set_queries_golden_set_id', 'golden_set_id'),
    )


class GoldenSetSource(Base):
    """An expected source (document + locator) for a golden set query."""
    __tablename__ = "golden_set_sources"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text('gen_random_uuid()')
    )
    query_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("golden_set_queries.id", ondelete="CASCADE"),
        nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False
    )
    locator: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default='{}'
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text('NOW()')
    )

    # Relationships
    query: Mapped["GoldenSetQuery"] = relationship(back_populates="sources")
    document: Mapped["Document"] = relationship()

    __table_args__ = (
        sa.Index('ix_golden_set_sources_query_id', 'query_id'),
        sa.Index('ix_golden_set_sources_document_id', 'document_id'),
    )
