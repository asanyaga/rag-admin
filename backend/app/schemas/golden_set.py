"""Pydantic schemas for golden sets."""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Source Locator — discriminated union
# ---------------------------------------------------------------------------

class PageLocator(BaseModel):
    """Locator for page-based sources (PDFs)."""
    type: Literal["page"] = "page"
    pages: list[int] = Field(..., min_length=1)

    model_config = ConfigDict(populate_by_name=True)


# Only page type for now; extend this union for future locator types
SourceLocator = Annotated[PageLocator, Field(discriminator="type")]


# ---------------------------------------------------------------------------
# Source schemas
# ---------------------------------------------------------------------------

class SourceCreate(BaseModel):
    """Request to add a source to a query."""
    document_id: UUID = Field(..., alias="documentId")
    locator: PageLocator

    model_config = ConfigDict(populate_by_name=True)


class SourceResponse(BaseModel):
    """Response for a golden set source."""
    id: UUID
    document_id: UUID = Field(..., alias="documentId")
    document_name: str = Field("", alias="documentName")
    locator: dict
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---------------------------------------------------------------------------
# Query schemas
# ---------------------------------------------------------------------------

class QueryCreate(BaseModel):
    """Request to add a query to a golden set."""
    query_text: str = Field(..., min_length=1, max_length=5000, alias="queryText")

    model_config = ConfigDict(populate_by_name=True)


class QueryUpdate(BaseModel):
    """Request to update a query."""
    query_text: str | None = Field(None, min_length=1, max_length=5000, alias="queryText")
    review_status: str | None = Field(None, alias="reviewStatus")
    reference_answer: str | None = Field(None, max_length=10000, alias="referenceAnswer")

    model_config = ConfigDict(populate_by_name=True)


class QueryResponse(BaseModel):
    """Response for a golden set query with sources."""
    id: UUID
    query_text: str = Field(..., alias="queryText")
    source_method: str = Field("manual", alias="sourceMethod")
    review_status: str = Field("accepted", alias="reviewStatus")
    reasoning: str | None = None
    question_type: str | None = Field(None, alias="questionType")
    reference_answer: str | None = Field(None, alias="referenceAnswer")
    has_results: bool = Field(False, alias="hasResults")
    sources: list[SourceResponse] = Field(default_factory=list)
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---------------------------------------------------------------------------
# Golden Set schemas
# ---------------------------------------------------------------------------

class GoldenSetCreate(BaseModel):
    """Request to create a golden set."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)

    model_config = ConfigDict(populate_by_name=True)


class GoldenSetUpdate(BaseModel):
    """Request to update a golden set."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    status: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class GenerationProgress(BaseModel):
    """Progress info for auto-generation."""
    total_windows: int = Field(0, alias="totalWindows")
    completed_windows: int = Field(0, alias="completedWindows")
    error_message: str | None = Field(None, alias="errorMessage")

    model_config = ConfigDict(populate_by_name=True)


class GoldenSetResponse(BaseModel):
    """Response for a golden set in list views."""
    id: UUID
    name: str
    description: str | None
    status: str
    query_count: int = Field(0, alias="queryCount")
    document_count: int = Field(0, alias="documentCount")
    generation_status: str | None = Field(None, alias="generationStatus")
    generation_progress: GenerationProgress | None = Field(None, alias="generationProgress")
    generation_config: dict | None = Field(None, alias="generationConfig")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class GoldenSetDetailResponse(GoldenSetResponse):
    """Response for a golden set with all queries and sources."""
    queries: list[QueryResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Generation request/response schemas
# ---------------------------------------------------------------------------

class GenerateGoldenSetRequest(BaseModel):
    """Request to trigger auto-generation of golden set queries."""
    document_ids: list[UUID] = Field(..., min_length=1, alias="documentIds")
    llm_provider: str = Field("openai", alias="llmProvider")
    llm_model: str = Field("gpt-4o", alias="llmModel")
    queries_per_document: int = Field(5, ge=1, le=30, alias="queriesPerDocument")
    question_types: list[str] = Field(
        default_factory=lambda: ["factual"],
        alias="questionTypes",
    )
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    system_prompt: str | None = Field(None, alias="systemPrompt")

    model_config = ConfigDict(populate_by_name=True)


class BulkReviewRequest(BaseModel):
    """Request to bulk accept or reject queries."""
    action: Literal["accept", "reject"]
    query_ids: list[UUID] = Field(..., min_length=1, alias="queryIds")

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Import schemas
# ---------------------------------------------------------------------------

class ImportParsedSource(BaseModel):
    """A source resolved during import parsing."""
    document_name: str = Field(..., alias="documentName")
    document_id: UUID | None = Field(None, alias="documentId")
    pages: list[int] = Field(default_factory=list)
    resolved: bool = False

    model_config = ConfigDict(populate_by_name=True)


class ImportValidQuery(BaseModel):
    """A valid query from the parsed file."""
    row: int
    query_text: str = Field(..., alias="queryText")
    sources: list[ImportParsedSource] = Field(default_factory=list)
    is_duplicate: bool = Field(False, alias="isDuplicate")

    model_config = ConfigDict(populate_by_name=True)


class ImportParseError(BaseModel):
    """An error from parsing."""
    row: int
    query_text: str = Field("", alias="queryText")
    error: str

    model_config = ConfigDict(populate_by_name=True)


class ImportDuplicate(BaseModel):
    """A duplicate query detected during parsing."""
    row: int
    query_text: str = Field(..., alias="queryText")
    existing_query_id: str | None = Field(None, alias="existingQueryId")

    model_config = ConfigDict(populate_by_name=True)


class ImportParseSummary(BaseModel):
    """Summary counts for the parse result."""
    total_rows: int = Field(..., alias="totalRows")
    valid_count: int = Field(..., alias="validCount")
    error_count: int = Field(..., alias="errorCount")
    duplicate_count: int = Field(..., alias="duplicateCount")

    model_config = ConfigDict(populate_by_name=True)


class ImportParseResponse(BaseModel):
    """Response from the parse/preview endpoint."""
    valid_queries: list[ImportValidQuery] = Field(..., alias="validQueries")
    errors: list[ImportParseError] = Field(default_factory=list)
    duplicates: list[ImportDuplicate] = Field(default_factory=list)
    summary: ImportParseSummary

    model_config = ConfigDict(populate_by_name=True)


class ImportConfirmSource(BaseModel):
    """A source to create during import confirmation."""
    document_id: UUID = Field(..., alias="documentId")
    locator: dict = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class ImportConfirmQuery(BaseModel):
    """A query to create during import confirmation."""
    query_text: str = Field(..., min_length=1, alias="queryText")
    sources: list[ImportConfirmSource] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class ImportConfirmRequest(BaseModel):
    """Request to confirm and execute the import."""
    queries: list[ImportConfirmQuery] = Field(..., min_length=1)

    model_config = ConfigDict(populate_by_name=True)


class ImportConfirmResponse(BaseModel):
    """Response from the confirm/import endpoint."""
    imported_count: int = Field(..., alias="importedCount")

    model_config = ConfigDict(populate_by_name=True)
