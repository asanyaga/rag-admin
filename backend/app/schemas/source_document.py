from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SourceDocumentResponse(BaseModel):
    id: UUID
    sha256: str
    filename: str | None
    mime_type: str | None = Field(None, alias="mimeType")
    byte_size: int | None = Field(None, alias="byteSize")
    created_at: datetime = Field(..., alias="createdAt")
    project_count: int = Field(..., alias="projectCount")

    model_config = ConfigDict(populate_by_name=True)
