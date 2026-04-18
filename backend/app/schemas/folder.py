from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class FolderUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] | None = None


class FolderResponse(BaseModel):
    id: UUID
    project_id: UUID = Field(..., alias="projectId")
    name: str
    description: str | None
    tags: list[str]
    document_count: int = Field(0, alias="documentCount")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
