"""Models for extraction schemas — user-defined JSON schemas for data extraction."""
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExtractionSchema(Base):
    """A user-defined JSON Schema for structured data extraction."""
    __tablename__ = "extraction_schemas"

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
    schema_definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    extraction_target: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PER_DOC", server_default="PER_DOC"
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
    extraction_results: Mapped[list["ExtractionResult"]] = relationship(
        back_populates="extraction_schema",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        sa.UniqueConstraint('project_id', 'name', name='uq_extraction_schemas_project_name'),
        sa.Index('ix_extraction_schemas_project_id', 'project_id'),
    )
