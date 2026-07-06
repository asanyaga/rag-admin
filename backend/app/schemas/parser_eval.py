"""Pydantic schemas for the parser-eval API (canonical model, camelCase JSON)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.cdm.models import ParserKind

_CAMEL = ConfigDict(populate_by_name=True)
_CAMEL_ORM = ConfigDict(from_attributes=True, populate_by_name=True)


class CaseCreate(BaseModel):
    source_document_id: UUID = Field(..., alias="sourceDocumentId")
    dimension: str
    expected: dict
    source_method: str | None = Field(None, alias="sourceMethod")
    review_status: str | None = Field(None, alias="reviewStatus")

    model_config = _CAMEL

    @model_validator(mode="after")
    def _validate_expected(self):
        if self.dimension == "text":
            pages = self.expected.get("pages")
            if not isinstance(pages, list) or not all(isinstance(p, str) for p in pages):
                raise ValueError("text case requires expected.pages: list[str]")
        return self


class CaseResponse(BaseModel):
    id: UUID
    source_document_id: UUID = Field(..., alias="sourceDocumentId")
    dimension: str
    source_method: str = Field(..., alias="sourceMethod")
    review_status: str = Field(..., alias="reviewStatus")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = _CAMEL_ORM


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None

    model_config = _CAMEL


class DatasetResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime = Field(..., alias="createdAt")

    model_config = _CAMEL_ORM


class VariantInput(BaseModel):
    adapter: str
    config: dict = {}

    model_config = _CAMEL

    @field_validator("adapter")
    @classmethod
    def _validate_adapter(cls, value: str) -> str:
        valid = {p.value for p in ParserKind}
        if value not in valid:
            raise ValueError(f"Invalid adapter '{value}'. Valid: {sorted(valid)}")
        return value


class RunCreate(BaseModel):
    name: str | None = None
    variants: list[VariantInput]
    eval_case_ids: list[UUID] = Field(default_factory=list, alias="evalCaseIds")
    dataset_id: UUID | None = Field(None, alias="datasetId")

    model_config = _CAMEL


class RunResponse(BaseModel):
    id: UUID
    name: str
    status: str
    variants: list[dict]
    dataset_id: UUID | None = Field(None, alias="datasetId")
    error_message: str | None = Field(None, alias="errorMessage")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = _CAMEL_ORM


class ResultResponse(BaseModel):
    eval_case_id: UUID = Field(..., alias="evalCaseId")
    adapter: str
    config: dict
    variant_key: str = Field(..., alias="variantKey")
    metrics: dict
    primary_metric: str | None = Field(None, alias="primaryMetric")
    details: dict | None
    cost: dict | None
    latency_ms: int | None = Field(None, alias="latencyMs")

    model_config = _CAMEL_ORM
