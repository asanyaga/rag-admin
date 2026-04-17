# backend/app/schemas/export_mapping.py
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ExportMappingCreate(BaseModel):
    data_store_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    field_mapping: list[dict]


class ExportMappingUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    field_mapping: list[dict] | None = None


class ExportMappingResponse(BaseModel):
    id: UUID
    project_id: UUID
    data_store_id: UUID
    name: str
    field_mapping: list[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
