"""Pydantic schemas for extraction ground truth sets and items."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Ground Truth Set
# ---------------------------------------------------------------------------

class GroundTruthSetCreate(BaseModel):
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")
    name: str = Field(..., max_length=255)
    description: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class GroundTruthSetUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class GroundTruthSetResponse(BaseModel):
    id: UUID
    project_id: UUID = Field(..., alias="projectId")
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")
    extraction_schema_name: str = Field("", alias="extractionSchemaName")
    name: str
    description: str | None = None
    item_count: int = Field(0, alias="itemCount")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---------------------------------------------------------------------------
# Ground Truth Item
# ---------------------------------------------------------------------------

class GroundTruthItemCreate(BaseModel):
    document_id: UUID = Field(..., alias="documentId")
    expected_data: dict = Field(..., alias="expectedData")
    annotations: dict | None = None

    model_config = ConfigDict(populate_by_name=True)


class GroundTruthItemUpdate(BaseModel):
    expected_data: dict | None = Field(None, alias="expectedData")
    annotations: dict | None = None

    model_config = ConfigDict(populate_by_name=True)


class GroundTruthItemResponse(BaseModel):
    id: UUID
    ground_truth_set_id: UUID = Field(..., alias="groundTruthSetId")
    document_id: UUID = Field(..., alias="documentId")
    document_title: str = Field("", alias="documentTitle")
    expected_data: dict = Field(..., alias="expectedData")
    annotations: dict | None = None
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------

class BulkItemCreate(BaseModel):
    document_id: UUID = Field(..., alias="documentId")
    expected_data: dict = Field(..., alias="expectedData")
    annotations: dict | None = None

    model_config = ConfigDict(populate_by_name=True)


class BulkImportRequest(BaseModel):
    items: list[BulkItemCreate]

    model_config = ConfigDict(populate_by_name=True)


class BulkImportResponse(BaseModel):
    created: int
    errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)
