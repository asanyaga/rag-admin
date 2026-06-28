"""Pydantic schemas for result-transform endpoints."""
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class TransformPreviewRequest(BaseModel):
    source_result_ids: list[UUID] = Field(..., alias="sourceResultIds", min_length=1)
    transform_type: str = Field(..., alias="transformType")
    config: dict

    model_config = ConfigDict(populate_by_name=True)


class TransformApplyRequest(TransformPreviewRequest):
    target_schema_id: UUID | None = Field(None, alias="targetSchemaId")


class TransformPreviewResponse(BaseModel):
    rows: list[dict]
    flags: list[dict]
