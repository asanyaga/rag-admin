"""Pydantic schemas for the parser-eval API (canonical model)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.cdm.models import ParserKind


class CaseCreate(BaseModel):
    source_document_id: UUID
    dimension: str
    expected: dict
    source_method: str | None = None
    review_status: str | None = None

    @model_validator(mode="after")
    def _validate_expected(self):
        if self.dimension == "text":
            pages = self.expected.get("pages")
            if not isinstance(pages, list) or not all(isinstance(p, str) for p in pages):
                raise ValueError("text case requires expected.pages: list[str]")
        return self


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_document_id: UUID
    dimension: str
    source_method: str
    review_status: str
    created_at: datetime


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    created_at: datetime


class VariantInput(BaseModel):
    adapter: str
    config: dict = {}

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
    eval_case_ids: list[UUID] = []
    dataset_id: UUID | None = None


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    status: str
    variants: list[dict]
    dataset_id: UUID | None = None
    error_message: str | None = None
    created_at: datetime


class ResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    eval_case_id: UUID
    adapter: str
    config: dict
    variant_key: str
    metrics: dict
    primary_metric: str | None
    details: dict | None
    cost: dict | None
    latency_ms: int | None
