"""Pydantic schemas for chunk inspection and browsing."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChunkResponse(BaseModel):
    """Full chunk details for detail view."""
    id: UUID
    index_id: UUID = Field(..., alias="indexId")
    document_id: UUID = Field(..., alias="documentId")
    content: str
    chunk_index: int = Field(..., alias="chunkIndex")
    token_count: int = Field(..., alias="tokenCount")
    char_count: int = Field(..., alias="charCount")
    chunk_metadata: dict = Field(..., alias="metadata")
    created_at: datetime = Field(..., alias="createdAt")

    # Document info for context
    document_title: str | None = Field(None, alias="documentTitle")
    document_filename: str | None = Field(None, alias="documentFilename")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class ChunkListItem(BaseModel):
    """Simplified chunk for list views."""
    id: UUID
    document_id: UUID = Field(..., alias="documentId")
    content_preview: str = Field(..., alias="contentPreview")  # First ~200 chars
    chunk_index: int = Field(..., alias="chunkIndex")
    token_count: int = Field(..., alias="tokenCount")
    char_count: int = Field(..., alias="charCount")
    document_title: str | None = Field(None, alias="documentTitle")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class ChunkListResponse(BaseModel):
    """Paginated chunk list response."""
    items: list[ChunkListItem]
    total: int
    page: int
    page_size: int = Field(..., alias="pageSize")
    total_pages: int = Field(..., alias="totalPages")

    model_config = ConfigDict(populate_by_name=True)


class ChunkSearchRequest(BaseModel):
    """Schema for searching chunks within an index."""
    query: str = Field(..., min_length=1, max_length=500)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100, alias="pageSize")

    model_config = ConfigDict(populate_by_name=True)
