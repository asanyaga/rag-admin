# backend/app/schemas/data_store.py
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ALLOWED_COLUMN_TYPES = {"text", "integer", "numeric", "boolean", "timestamptz"}


class ColumnDefinition(BaseModel):
    """A single column in a data store schema."""
    name: str = Field(..., min_length=1, max_length=63, pattern=r'^[a-z][a-z0-9_]*$')
    type: str = Field(...)
    nullable: bool = Field(default=True)
    description: str = Field(default="", max_length=500)


class DataStoreCreate(BaseModel):
    """Schema for creating a new data store."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    schema_definition: list[ColumnDefinition] = Field(..., min_length=1)


class DataStoreUpdate(BaseModel):
    """Schema for updating an existing data store."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    schema_definition: list[ColumnDefinition] | None = None


class DataStoreResponse(BaseModel):
    """Schema for data store API responses."""
    id: UUID
    project_id: UUID = Field(..., alias="projectId")
    name: str
    description: str | None
    table_name: str = Field(..., alias="tableName")
    schema_definition: list[ColumnDefinition] = Field(..., alias="schemaDefinition")
    row_count: int = Field(..., alias="rowCount")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class DataStoreRowResponse(BaseModel):
    """Schema for a single row in a data store."""
    id: UUID
    data: dict
    source_metadata: dict | None = Field(None, alias="sourceMetadata")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class DataStoreRowsResponse(BaseModel):
    """Paginated list of rows."""
    rows: list[DataStoreRowResponse]
    total: int
    limit: int
    offset: int


class CsvImportResponse(BaseModel):
    """Response from CSV import."""
    rows_imported: int = Field(..., alias="rowsImported")

    model_config = ConfigDict(populate_by_name=True)


class ExportPreviewRequest(BaseModel):
    """Request body for preview-export endpoint."""
    source_data: dict = Field(..., alias="sourceData")
    field_mapping: dict[str, str] = Field(..., alias="fieldMapping")

    model_config = ConfigDict(populate_by_name=True)


class ExportPreviewResponse(BaseModel):
    """Response from preview-export endpoint."""
    rows: list[dict]
    row_count: int = Field(..., alias="rowCount")

    model_config = ConfigDict(populate_by_name=True)


class ExportExecuteResponse(BaseModel):
    """Response from execute-export endpoint."""
    rows_imported: int = Field(..., alias="rowsImported")

    model_config = ConfigDict(populate_by_name=True)
