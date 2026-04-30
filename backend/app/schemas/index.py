"""Pydantic schemas for the Index feature.

These schemas define the request/response formats for index operations,
as well as the configuration and statistics structures stored as JSON.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# -----------------------------------------------------------------------------
# Index Configuration Schema
# -----------------------------------------------------------------------------

class IndexConfig(BaseModel):
    """Configuration for how documents are chunked and embedded."""

    # Parse source binding
    parser: str | None = Field(default=None)
    parse_config_hash: str | None = Field(default=None, alias="parseConfigHash")
    source_representation: Literal["raw_text", "full_text", "full_markdown", "block"] = Field(
        default="raw_text", alias="sourceRepresentation"
    )

    # Chunking strategy
    chunking_strategy: Literal[
        "fixed_size",
        "recursive_character",
        "markdown_heading",
        "block",
        "classified_block",
    ] = Field(
        default="recursive_character",
        alias="chunkingStrategy",
        description="How documents are split into chunks",
    )

    # Text-based config (fixed_size, recursive_character)
    chunk_size: int = Field(default=512, ge=100, le=8000, alias="chunkSize")
    chunk_overlap: int = Field(default=50, ge=0, alias="chunkOverlap")
    chunk_unit: Literal["tokens", "characters"] = Field(default="characters", alias="chunkUnit")

    # Markdown-based config (markdown_heading)
    split_heading_level: int = Field(default=2, ge=1, le=3, alias="splitHeadingLevel")
    max_section_chars: int = Field(default=4000, ge=500, le=16000, alias="maxSectionChars")

    # Embedding config (unchanged)
    embedding_provider: str = Field(default="openai", alias="embeddingProvider")
    embedding_model: str = Field(default="text-embedding-3-small", alias="embeddingModel")
    embedding_dimensions: int | None = Field(default=None, alias="embeddingDimensions")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("chunk_overlap")
    @classmethod
    def validate_overlap(cls, v: int, info) -> int:
        chunk_size = info.data.get("chunk_size", 512)
        max_overlap = chunk_size // 2
        if v > max_overlap:
            raise ValueError(f"chunk_overlap must be at most {max_overlap}")
        return v

    @model_validator(mode="after")
    def validate_representation_and_strategy(self) -> "IndexConfig":
        rep = self.source_representation
        strategy = self.chunking_strategy

        # Validate strategy is compatible with representation
        text_strategies = {"fixed_size", "recursive_character"}
        allowed: dict[str, set[str]] = {
            "raw_text": text_strategies,
            "full_text": text_strategies,
            "full_markdown": {"markdown_heading"},
            "block": {"block", "classified_block"},
        }
        if strategy not in allowed.get(rep, set()):
            raise ValueError(
                f"chunking_strategy='{strategy}' is not compatible with "
                f"source_representation='{rep}'. "
                f"Allowed: {sorted(allowed[rep])}"
            )
        return self


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

    version: int = Field(default=1)
    config_dirty: bool = Field(default=False, alias="configDirty")

    # Computed fields for convenience
    document_count: int = Field(0, alias="documentCount")
    chunk_count: int = Field(0, alias="chunkCount")
    document_ids: list[UUID] = Field(default_factory=list, alias="documentIds")

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
    parse_run_ids: dict[UUID, UUID] | None = Field(
        default=None,
        alias="parseRunIds",
        description="Map of document_id → parse_run_id. Required per document when source_representation != raw_text.",
    )

    model_config = ConfigDict(populate_by_name=True)


# -----------------------------------------------------------------------------
# Chunk Preview Schemas
# -----------------------------------------------------------------------------

class ChunkPreviewRequest(BaseModel):
    """Schema for previewing chunks before processing.

    Exactly one of `document_id` (legacy raw_text path / slice-2 wizard bridge)
    or `parsed_document_id` (CDM path, matches the eventual spec shape) must be
    supplied. `document_id` is removed in Unit 3.
    """
    document_id: UUID | None = Field(default=None, alias="documentId")
    parsed_document_id: UUID | None = Field(default=None, alias="parsedDocumentId")
    config: IndexConfig
    max_chunks: int = Field(default=5, ge=1, le=20, alias="maxChunks")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def exactly_one_handle(self) -> "ChunkPreviewRequest":
        provided = [self.document_id is not None, self.parsed_document_id is not None]
        if sum(provided) != 1:
            raise ValueError(
                "Exactly one of documentId or parsedDocumentId must be provided"
            )
        return self


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
