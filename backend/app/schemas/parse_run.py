"""Response schemas for CDM ParseRun + ParsedDocument viewer endpoints."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.parse_run import ParseRun as ParseRunORM
from app.models.parsed_document import ParsedDocument as ParsedDocumentORM


class ParseRunResponse(BaseModel):
    """Execution row for a parser invocation."""

    id: UUID
    source_document_id: UUID = Field(..., alias="sourceDocumentId")
    parser: str
    parser_version: str | None = Field(None, alias="parserVersion")
    representation_kind: str = Field(..., alias="representationKind")
    status: str
    started_at: datetime = Field(..., alias="startedAt")
    finished_at: datetime | None = Field(None, alias="finishedAt")
    duration_ms: int | None = Field(None, alias="durationMs")
    input_tokens: int | None = Field(None, alias="inputTokens")
    output_tokens: int | None = Field(None, alias="outputTokens")
    cost: dict[str, Any]
    warnings: list[str]
    failed_pages: list[int] = Field(..., alias="failedPages")
    provider_refs: dict[str, Any] = Field(..., alias="providerRefs")
    error: str | None
    config: dict[str, Any]
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_row(cls, row: ParseRunORM) -> "ParseRunResponse":
        return cls.model_validate(row)


class ParsedDocumentResponse(BaseModel):
    """Content blob for a successful (or partial) ParseRun."""

    parse_run_id: UUID = Field(..., alias="parseRunId")
    source_document_id: UUID = Field(..., alias="sourceDocumentId")
    page_count: int = Field(..., alias="pageCount")
    block_count: int = Field(..., alias="blockCount")
    full_text: str | None = Field(None, alias="fullText")
    full_markdown: str | None = Field(None, alias="fullMarkdown")
    content: dict[str, Any]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_row(cls, row: ParsedDocumentORM) -> "ParsedDocumentResponse":
        return cls.model_validate(row)
