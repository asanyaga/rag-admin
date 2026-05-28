"""Pydantic schemas for extraction schemas and results."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.extraction_result import ExtractionResultStatus
from app.schemas.prompt_config import PromptConfig


# --- Extraction Schema schemas ---

class ExtractionSchemaCreate(BaseModel):
    """Request to create an extraction schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    schema_definition: dict = Field(..., alias="schemaDefinition")
    extraction_target: str = Field("PER_DOC", alias="extractionTarget")

    model_config = ConfigDict(populate_by_name=True)


class ExtractionSchemaUpdate(BaseModel):
    """Request to update an extraction schema."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    schema_definition: dict | None = Field(None, alias="schemaDefinition")
    extraction_target: str | None = Field(None, alias="extractionTarget")

    model_config = ConfigDict(populate_by_name=True)


class ExtractionSchemaResponse(BaseModel):
    """Full extraction schema response."""
    id: UUID = Field(..., alias="id")
    project_id: UUID = Field(..., alias="projectId")
    name: str
    description: str | None = None
    schema_definition: dict = Field(..., alias="schemaDefinition")
    extraction_target: str = Field(..., alias="extractionTarget")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_model(cls, obj) -> "ExtractionSchemaResponse":
        return cls(
            id=obj.id,
            projectId=obj.project_id,
            name=obj.name,
            description=obj.description,
            schemaDefinition=obj.schema_definition,
            extractionTarget=obj.extraction_target,
            createdBy=obj.created_by,
            createdAt=obj.created_at,
            updatedAt=obj.updated_at,
        )


# --- Extraction Result schemas ---

class RunExtractionRequest(BaseModel):
    """Request to run an extraction against a CDM ParsedDocument."""
    parse_run_id: UUID = Field(..., alias="parseRunId")
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")
    extraction_method: str = Field(..., alias="extractionMethod")
    config: dict | None = None
    llm_config: PromptConfig | None = Field(None, alias="llmConfig")
    user_prompt_template: str | None = Field(None, alias="userPromptTemplate")

    model_config = ConfigDict(populate_by_name=True)


class ExtractionResultResponse(BaseModel):
    """Full extraction result response."""
    id: UUID = Field(..., alias="id")
    document_id: UUID = Field(..., alias="documentId")
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")
    schema_definition_snapshot: dict = Field(..., alias="schemaDefinitionSnapshot")
    extraction_method: str = Field(..., alias="extractionMethod")
    config: dict | None = None
    structured_data: dict | None = Field(None, alias="structuredData")
    citations: list | None = Field(None, alias="citations")
    provider_response_raw: dict | None = Field(None, alias="providerResponseRaw")
    extraction_metadata: dict | None = Field(None, alias="extractionMetadata")
    status: ExtractionResultStatus
    status_message: str | None = Field(None, alias="statusMessage")
    started_at: datetime | None = Field(None, alias="startedAt")
    source_parse_run_id: UUID | None = Field(None, alias="sourceParseRunId")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_model(cls, obj) -> "ExtractionResultResponse":
        return cls(
            id=obj.id,
            documentId=obj.document_id,
            extractionSchemaId=obj.extraction_schema_id,
            schemaDefinitionSnapshot=obj.schema_definition_snapshot,
            extractionMethod=obj.extraction_method,
            config=obj.config,
            structuredData=obj.structured_data,
            citations=obj.citations,
            providerResponseRaw=obj.provider_response_raw,
            extractionMetadata=obj.extraction_metadata,
            status=obj.status,
            statusMessage=obj.status_message,
            startedAt=obj.started_at,
            sourceParseRunId=obj.source_parse_run_id,
            createdBy=obj.created_by,
            createdAt=obj.created_at,
            updatedAt=obj.updated_at,
        )


class ExtractionResultListResponse(BaseModel):
    """Summary extraction result for list endpoint."""
    id: UUID = Field(..., alias="id")
    document_id: UUID = Field(..., alias="documentId")
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")
    extraction_method: str = Field(..., alias="extractionMethod")
    status: ExtractionResultStatus
    status_message: str | None = Field(None, alias="statusMessage")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_model(cls, obj) -> "ExtractionResultListResponse":
        return cls(
            id=obj.id,
            documentId=obj.document_id,
            extractionSchemaId=obj.extraction_schema_id,
            extractionMethod=obj.extraction_method,
            status=obj.status,
            statusMessage=obj.status_message,
            createdAt=obj.created_at,
        )


class ExtractorInfoResponse(BaseModel):
    """Available extractor information."""
    extraction_method: str = Field(..., alias="extractionMethod")
    name: str
    description: str
    config_schema: dict | None = Field(None, alias="configSchema")
    configured: bool = Field(False, alias="configured")

    model_config = ConfigDict(populate_by_name=True)
