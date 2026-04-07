"""Models for extraction ground truth — expected structured data for evaluation."""
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExtractionGroundTruthSet(Base):
    """A collection of documents with expected extraction output for a schema."""
    __tablename__ = "extraction_ground_truth_sets"

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
    extraction_schema_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("extraction_schemas.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    extraction_schema: Mapped["ExtractionSchema"] = relationship()
    user: Mapped["User"] = relationship()
    items: Mapped[list["ExtractionGroundTruthItem"]] = relationship(
        back_populates="ground_truth_set",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        sa.UniqueConstraint('project_id', 'name', name='uq_extraction_gt_sets_project_name'),
        sa.Index('ix_extraction_gt_sets_project_id', 'project_id'),
        sa.Index('ix_extraction_gt_sets_schema_id', 'extraction_schema_id'),
    )


class ExtractionGroundTruthItem(Base):
    """A single document's expected extraction output within a ground truth set."""
    __tablename__ = "extraction_ground_truth_items"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text('gen_random_uuid()')
    )
    ground_truth_set_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("extraction_ground_truth_sets.id", ondelete="CASCADE"),
        nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False
    )
    expected_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    annotations: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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
    ground_truth_set: Mapped["ExtractionGroundTruthSet"] = relationship(back_populates="items")
    document: Mapped["Document"] = relationship()
    user: Mapped["User"] = relationship()

    __table_args__ = (
        sa.UniqueConstraint('ground_truth_set_id', 'document_id', name='uq_extraction_gt_items_set_doc'),
        sa.Index('ix_extraction_gt_items_set_id', 'ground_truth_set_id'),
        sa.Index('ix_extraction_gt_items_document_id', 'document_id'),
    )
