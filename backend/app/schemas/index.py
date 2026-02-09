"""Pydantic schemas for the Index feature.

These schemas define the request/response formats for index operations,
as well as the configuration and statistics structures stored as JSON.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# -----------------------------------------------------------------------------
# Index Configuration Schema
# -----------------------------------------------------------------------------

class IndexConfig(BaseModel):
    """Configuration for how documents are chunked and embedded.

    This schema is stored as JSON in the index.config column.
    Config becomes immutable once processing begins.
    """
    # Chunking configuration
    chunking_strategy: Literal["fixed_size", "recursive_character"] = Field(
        default="recursive_character",
        alias="chunkingStrategy",
        description="How documents are split into chunks"
    )
    chunk_size: int = Field(
        default=512,
        ge=100,
        le=8000,
        alias="chunkSize",
        description="Target size per chunk (in specified unit)"
    )
    chunk_overlap: int = Field(
        default=50,
        ge=0,
        alias="chunkOverlap",
        description="Overlap between consecutive chunks"
    )
    chunk_unit: Literal["tokens", "characters"] = Field(
        default="characters",
        alias="chunkUnit",
        description="Whether size is measured in tokens or characters"
    )

    # Embedding configuration
    embedding_provider: str = Field(
        default="openai",
        alias="embeddingProvider",
        description="Which embedding provider to use"
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        alias="embeddingModel",
        description="Specific model from the provider"
    )
    embedding_dimensions: int | None = Field(
        default=None,
        alias="embeddingDimensions",
        description="Vector dimensionality (None = model default)"
    )

    # Reserved for future phases
    parsing_strategy: Literal["static"] = Field(
        default="static",
        alias="parsingStrategy",
        description="Document parsing strategy (static for Phase 1)"
    )

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("chunk_overlap")
    @classmethod
    def validate_overlap(cls, v: int, info) -> int:
        """Ensure overlap is at most half of chunk_size."""
        # Access chunk_size from the data being validated
        data = info.data
        chunk_size = data.get("chunk_size", 512)
        max_overlap = chunk_size // 2
        if v > max_overlap:
            raise ValueError(f"chunk_overlap must be at most {max_overlap} (half of chunk_size)")
        return v


# -----------------------------------------------------------------------------
# Index Statistics Schema
# -----------------------------------------------------------------------------

class IndexStats(BaseModel):
    """Statistics computed after index processing completes.

    Stored in index.stats JSON column and cached for fast display.
    """
    total_chunks: int = Field(..., alias="totalChunks")
    total_documents: int = Field(..., alias="totalDocuments")
    avg_chunk_size_chars: float = Field(..., alias="avgChunkSizeChars")
    avg_chunk_size_tokens: float = Field(..., alias="avgChunkSizeTokens")
    min_chunk_size_chars: int = Field(..., alias="minChunkSizeChars")
    max_chunk_size_chars: int = Field(..., alias="maxChunkSizeChars")
    total_tokens: int = Field(..., alias="totalTokens")
    embedding_dimensions: int = Field(..., alias="embeddingDimensions")
    processed_at: datetime = Field(..., alias="processedAt")

    model_config = ConfigDict(populate_by_name=True)


# -----------------------------------------------------------------------------
# Index Document Status Schema
# -----------------------------------------------------------------------------

class IndexDocumentStatusResponse(BaseModel):
    """Status of a single document within an index."""
    document_id: UUID = Field(..., alias="documentId")
    status: str
    chunks_created: int | None = Field(None, alias="chunksCreated")
    error_message: str | None = Field(None, alias="errorMessage")
    processed_at: datetime | None = Field(None, alias="processedAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


# -----------------------------------------------------------------------------
# Index CRUD Schemas
# -----------------------------------------------------------------------------

class IndexCreate(BaseModel):
    """Schema for creating a new index."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    document_ids: list[UUID] = Field(
        default_factory=list,
        alias="documentIds",
        description="Documents to include in this index"
    )
    config: IndexConfig = Field(default_factory=IndexConfig)
    auto_process: bool = Field(
        default=False,
        alias="autoProcess",
        description="Start processing immediately after creation"
    )

    model_config = ConfigDict(populate_by_name=True)


class IndexUpdate(BaseModel):
    """Schema for updating an existing index.

    Note: Only name and description can be updated, and only when status is 'created'.
    Config is immutable once processing begins.
    """
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)

    model_config = ConfigDict(populate_by_name=True)


class IndexResponse(BaseModel):
    """Schema for index API responses."""
    id: UUID
    project_id: UUID = Field(..., alias="projectId")
    name: str
    description: str | None
    config: IndexConfig
    stats: IndexStats | None
    status: str
    error_message: str | None = Field(None, alias="errorMessage")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    # Computed fields for convenience
    document_count: int = Field(0, alias="documentCount")
    chunk_count: int = Field(0, alias="chunkCount")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class IndexListResponse(BaseModel):
    """Simplified index response for list views."""
    id: UUID
    project_id: UUID = Field(..., alias="projectId")
    name: str
    description: str | None
    status: str
    document_count: int = Field(0, alias="documentCount")
    chunk_count: int = Field(0, alias="chunkCount")
    embedding_model: str | None = Field(None, alias="embeddingModel")
    chunking_strategy: str | None = Field(None, alias="chunkingStrategy")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


# -----------------------------------------------------------------------------
# Processing Schemas
# -----------------------------------------------------------------------------

class IndexProcessingStatusResponse(BaseModel):
    """Detailed processing status for an index."""
    status: str
    total_documents: int = Field(..., alias="totalDocuments")
    processed_documents: int = Field(..., alias="processedDocuments")
    failed_documents: int = Field(..., alias="failedDocuments")
    progress_percent: int = Field(..., alias="progressPercent")
    started_at: datetime | None = Field(None, alias="startedAt")
    documents: list[IndexDocumentStatusResponse]

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class AddDocumentsRequest(BaseModel):
    """Schema for adding documents to an existing index."""
    document_ids: list[UUID] = Field(..., alias="documentIds", min_length=1)

    model_config = ConfigDict(populate_by_name=True)


# -----------------------------------------------------------------------------
# Chunk Preview Schemas
# -----------------------------------------------------------------------------

class ChunkPreviewRequest(BaseModel):
    """Schema for previewing chunks before processing."""
    document_id: UUID = Field(..., alias="documentId")
    config: IndexConfig
    max_chunks: int = Field(default=5, ge=1, le=20, alias="maxChunks")

    model_config = ConfigDict(populate_by_name=True)


class ChunkPreview(BaseModel):
    """A single chunk in the preview response."""
    index: int
    content: str
    char_count: int = Field(..., alias="charCount")
    token_count: int = Field(..., alias="tokenCount")
    overlap_start_chars: int = Field(..., alias="overlapStartChars")
    overlap_end_chars: int = Field(..., alias="overlapEndChars")

    model_config = ConfigDict(populate_by_name=True)


class ChunkPreviewResponse(BaseModel):
    """Response from chunk preview endpoint."""
    total_chunks_estimate: int = Field(..., alias="totalChunksEstimate")
    avg_chunk_size_chars: float = Field(..., alias="avgChunkSizeChars")
    avg_chunk_size_tokens: float = Field(..., alias="avgChunkSizeTokens")
    min_chunk_size_chars: int = Field(..., alias="minChunkSizeChars")
    max_chunk_size_chars: int = Field(..., alias="maxChunkSizeChars")
    preview_chunks: list[ChunkPreview] = Field(..., alias="previewChunks")

    model_config = ConfigDict(populate_by_name=True)
