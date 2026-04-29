from datetime import datetime
from uuid import UUID, uuid4
import enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class IndexStatus(str, enum.Enum):
    """Index processing status enum."""
    created = "created"  # Config defined, not yet processed
    processing = "processing"  # Background task is running
    ready = "ready"  # Processing complete, queryable
    failed = "failed"  # Processing encountered an error


class Index(Base):
    """Index model for storing document chunking and embedding configurations.

    An Index represents a processed, searchable representation of a set of documents.
    It defines how documents are chunked and embedded, and contains the resulting chunks.

    Key design decisions:
    - Config is stored as JSON for schema flexibility across phases
    - Config becomes immutable once processing begins (status != CREATED)
    - Stats are computed after processing and cached for fast display
    """
    __tablename__ = "indexes"

    # Identity
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

    # Metadata
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Configuration (JSONB for flexibility)
    # Schema validated at application layer via Pydantic
    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default='{}'
    )

    # Statistics (computed after processing)
    stats: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    # Status
    status: Mapped[IndexStatus] = mapped_column(
        Enum(IndexStatus, name='index_status', create_type=False),
        nullable=False,
        default=IndexStatus.created,
        server_default='created'
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # CDM pipeline binding and versioning
    version: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=1,
        server_default='1'
    )
    parser: Mapped[str | None] = mapped_column(
        sa.String(100),
        nullable=True
    )
    parse_config_hash: Mapped[str | None] = mapped_column(
        sa.String(64),
        nullable=True
    )
    config_dirty: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        server_default='false'
    )

    # Audit
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
    project: Mapped["Project"] = relationship(back_populates="indexes")
    user: Mapped["User"] = relationship()
    index_documents: Mapped[list["IndexDocument"]] = relationship(
        back_populates="index",
        cascade="all, delete-orphan"
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="index",
        cascade="all, delete-orphan"
    )
    index_events: Mapped[list["IndexEvent"]] = relationship(
        "IndexEvent",
        back_populates="index",
        cascade="all, delete-orphan",
        order_by="IndexEvent.version"
    )

    __table_args__ = (
        sa.UniqueConstraint('project_id', 'name', name='uq_indexes_project_name'),
        sa.Index('ix_indexes_project_id', 'project_id'),
        sa.Index('ix_indexes_status', 'status'),
        sa.Index('ix_indexes_created_at', 'created_at'),
    )
