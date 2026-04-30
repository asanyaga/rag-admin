"""Response schemas for the parsed-document selector API.

Used by:
  GET /projects/{project_id}/parse-runs/configs   → list[ParseConfigOption]
  GET /projects/{project_id}/parsed-documents     → list[ParsedDocumentListItem]
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ParseConfigOption(BaseModel):
    """One distinct (parser, parse_config_hash) family available to a project."""
    parser: str
    parse_config_hash: str = Field(..., alias="parseConfigHash")
    config: dict[str, Any]
    parsed_document_count: int = Field(..., alias="parsedDocumentCount")
    has_full_markdown: bool = Field(..., alias="hasFullMarkdown")
    latest_parsed_at: datetime = Field(..., alias="latestParsedAt")

    model_config = ConfigDict(populate_by_name=True)


class ParsedDocumentListItem(BaseModel):
    """One picker row for the parsed-document selector.

    Note: under the current 1:1 schema, `id` and `parseRunId` carry the same
    UUID — the parsed_document is keyed on parse_run_id. When the schema later
    grows a distinct `id` (for derived parsed-docs), `id` and `parseRunId`
    diverge but the wire shape stays the same.
    """
    id: UUID
    parse_run_id: UUID = Field(..., alias="parseRunId")
    parser: str
    parse_config_hash: str = Field(..., alias="parseConfigHash")
    source_document_id: UUID = Field(..., alias="sourceDocumentId")
    source_filename: str | None = Field(None, alias="sourceFilename")
    has_full_markdown: bool = Field(..., alias="hasFullMarkdown")
    block_count: int = Field(..., alias="blockCount")
    parsed_at: datetime = Field(..., alias="parsedAt")

    model_config = ConfigDict(populate_by_name=True)
