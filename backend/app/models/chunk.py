from datetime import datetime
from uuid import UUID, uuid4
import json

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VectorType(TypeDecorator):
    """Custom type for storing vector embeddings.

    Uses pgvector's VECTOR type in PostgreSQL for efficient similarity search.
    Falls back to JSON storage in SQLite for testing.

    Note: pgvector HNSW indexes require uniform dimensions per index.
    Since config is immutable per index and all chunks in an index share
    the same embedding model, this constraint is naturally satisfied.
    """
    impl = Text
    cache_ok = True

    def __init__(self, dimensions: int | None = None):
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            # Import pgvector type dynamically to avoid import errors
            # when pgvector is not installed
            try:
                from pgvector.sqlalchemy import Vector
                return dialect.type_descriptor(Vector(self.dimensions))
            except ImportError:
                # Fallback to text if pgvector not available
                return dialect.type_descriptor(Text())
        else:
            # SQLite and other databases: store as JSON text
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == 'postgresql':
            # pgvector handles the conversion
            return value
        else:
            # Convert list to JSON string for SQLite
            return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == 'postgresql':
            # pgvector returns a numpy array; convert to plain list
            return list(value)
        else:
            # Parse JSON string back to list for SQLite
            return json.loads(value) if value else None


class Chunk(Base):
    """Chunk model for storing document segments with embeddings.

    A chunk is the fundamental unit of retrieval in the RAG system.
    Each chunk contains:
    - The text content from a portion of a document
    - A vector embedding for similarity search
    - Metadata about its position and source

    Key design decisions:
    - Chunks belong to exactly one index (different indexes may chunk differently)
    - Chunks reference their source document for traceability
    - Embeddings are stored as vectors for efficient pgvector operations
    - Metadata is flexible JSON to accommodate varying extraction info
    """
    __tablename__ = "chunks"

    # Identity
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text('gen_random_uuid()')
    )
    index_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("indexes.id", ondelete="CASCADE"),
        nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False
    )

    # Content
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    # Embedding vector
    # Note: dimensions vary by embedding model (e.g., 1536 for text-embedding-3-small)
    # The actual dimension is determined by the index config
    embedding: Mapped[list[float]] = mapped_column(
        VectorType(),
        nullable=False
    )

    # Position information
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )  # Position within source document (0-indexed)

    # Size metrics
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    char_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # Flexible metadata (source location, page numbers, etc.)
    chunk_metadata: Mapped[dict] = mapped_column(
        sa.JSON,
        nullable=False,
        default=dict,
        server_default='{}'
    )

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text('NOW()')
    )

    # Relationships
    index: Mapped["Index"] = relationship(back_populates="chunks")
    document: Mapped["Document"] = relationship(back_populates="chunks")

    __table_args__ = (
        sa.Index('ix_chunks_index_id', 'index_id'),
        sa.Index('ix_chunks_document_id', 'document_id'),
        sa.Index('ix_chunks_index_document', 'index_id', 'document_id'),
        sa.Index('ix_chunks_chunk_index', 'chunk_index'),
    )
