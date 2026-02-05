from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus


class DocumentCreate(BaseModel):
    """Schema for creating a new document."""
    project_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class DocumentUpdate(BaseModel):
    """Schema for updating an existing document."""
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class DocumentResponse(BaseModel):
    """Schema for document API responses with camelCase fields."""
    id: UUID = Field(..., alias="id")
    project_id: UUID = Field(..., alias="projectId")
    source_type: str = Field(..., alias="sourceType")
    source_identifier: str = Field(..., alias="sourceIdentifier")
    title: str
    description: str | None
    extracted_text: str | None = Field(None, alias="extractedText")
    source_metadata: dict = Field(..., alias="sourceMetadata")
    processing_metadata: dict | None = Field(None, alias="processingMetadata")
    status: DocumentStatus
    status_message: str | None = Field(None, alias="statusMessage")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class DocumentListResponse(BaseModel):
    """Schema for document list API responses with camelCase fields."""
    id: UUID = Field(..., alias="id")
    project_id: UUID = Field(..., alias="projectId")
    source_type: str = Field(..., alias="sourceType")
    title: str
    description: str | None
    status: DocumentStatus
    status_message: str | None = Field(None, alias="statusMessage")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
