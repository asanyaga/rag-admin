"""Uniform citation schema returned with every search result.

Fields are populated based on the chunk's `source_type`:
- text-based (`raw_text`, `full_text`): start_char, end_char, page_numbers
- markdown-based (`full_markdown`): start_char, end_char, heading_path
- block-based (`block`): block_ids, page_indices, block_roles, bboxes, confidence

Block fields are resolved at query time by re-fetching the parsed document.
If the parse run has been deleted, block fields stay null — the caller can
detect resolution failure rather than render stale references.
"""
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChunkCitation(BaseModel):
    chunk_id: UUID = Field(..., alias="chunkId")
    document_id: UUID = Field(..., alias="documentId")
    document_title: str = Field(..., alias="documentTitle")
    index_id: UUID = Field(..., alias="indexId")
    index_version: int = Field(..., alias="indexVersion")
    parse_run_id: UUID | None = Field(None, alias="parseRunId")
    source_type: str = Field(..., alias="sourceType")

    # Text-based
    start_char: int | None = Field(None, alias="startChar")
    end_char: int | None = Field(None, alias="endChar")
    page_numbers: list[int] = Field(default_factory=list, alias="pageNumbers")
    heading_path: list[str] | None = Field(None, alias="headingPath")

    # Block-based
    block_ids: list[str] | None = Field(None, alias="blockIds")
    page_indices: list[int] | None = Field(None, alias="pageIndices")
    block_roles: list[str] | None = Field(None, alias="blockRoles")
    bboxes: list[dict | None] | None = None
    confidence: float | None = None

    model_config = ConfigDict(populate_by_name=True)
