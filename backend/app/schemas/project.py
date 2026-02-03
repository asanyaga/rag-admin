from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    tags: list[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    """Schema for updating an existing project."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    tags: list[str] | None = None


class ProjectResponse(BaseModel):
    """Schema for project API responses with camelCase fields."""
    id: UUID = Field(..., alias="id")
    user_id: UUID = Field(..., alias="userId")
    name: str
    description: str | None
    tags: list[str]
    is_archived: bool = Field(..., alias="isArchived")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
