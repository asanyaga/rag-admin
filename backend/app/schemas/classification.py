from __future__ import annotations
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClassificationRunCreateRequest(BaseModel):
    parse_run_id: UUID
    labels: list[str]
    classifier_type: str | None = None
    classifier_config: dict | None = None


class ClassificationRegionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    label: str
    page_start: int = Field(..., alias="pageStart")
    page_end: int = Field(..., alias="pageEnd")
    block_ids: list[str] = Field(..., alias="blockIds")
    confidence: float | None = None
    reasoning: str | None = None
    source: str


class ClassificationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    parse_run_id: UUID = Field(..., alias="parseRunId")
    document_id: UUID = Field(..., alias="documentId")
    labels_requested: list[str] = Field(..., alias="labelsRequested")
    classifier_type: str = Field(..., alias="classifierType")
    classifier_config: dict = Field(..., alias="classifierConfig")
    status: str
    error: str | None = None
    input_tokens: int | None = Field(None, alias="inputTokens")
    output_tokens: int | None = Field(None, alias="outputTokens")
    duration_ms: int | None = Field(None, alias="durationMs")
    created_at: datetime = Field(..., alias="createdAt")
    regions: list[ClassificationRegionResponse] = []


class AnnotatedBlockResponse(BaseModel):
    blockId: str
    pageIndex: int
    role: str
    text: str
    markdown: str | None
    label: str | None
