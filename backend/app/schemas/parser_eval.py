"""Pydantic schemas for the parser-eval API."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.cdm.models import ParserKind


class TargetInput(BaseModel):
    dimension: str
    expected: dict

    @model_validator(mode="after")
    def _validate_expected(self):
        if self.dimension == "text":
            pages = self.expected.get("pages")
            if not isinstance(pages, list) or not all(isinstance(p, str) for p in pages):
                raise ValueError("text target requires expected.pages: list[str]")
        return self


class CaseCreate(BaseModel):
    name: str
    doc_type: str | None = None
    source_document_id: UUID
    targets: list[TargetInput]


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    doc_type: str | None
    source_document_id: UUID
    source_filename: str | None
    created_at: datetime


class RunCreate(BaseModel):
    name: str | None = None
    case_ids: list[UUID]
    parsers: list[str]

    @field_validator("parsers")
    @classmethod
    def _validate_parsers(cls, value: list[str]) -> list[str]:
        valid = {p.value for p in ParserKind}
        invalid = [p for p in value if p not in valid]
        if invalid:
            raise ValueError(
                f"Invalid parser name(s): {invalid}. Valid parsers: {sorted(valid)}"
            )
        return value


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    status: str
    parsers: list[str]
    error_message: str | None = None
    created_at: datetime


class ResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    case_id: UUID
    parser: str
    dimension: str
    score: float
    details: dict | None
    cost: dict | None
    latency_ms: int | None
