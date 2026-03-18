"""Pydantic schemas for parse results."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.parse_result import ParseResultStatus


class ParseResultResponse(BaseModel):
    """Full parse result response with camelCase aliases."""
    id: UUID = Field(..., alias="id")
    document_id: UUID = Field(..., alias="documentId")
    parser_type: str = Field(..., alias="parserType")
    fidelity: str
    parser_config: dict | None = Field(None, alias="parserConfig")
    raw_text: str | None = Field(None, alias="rawText")
    markdown: str | None = None
    pages: list[dict] | None = None
    document_structure: dict | None = Field(None, alias="documentStructure")
    diagnostics: dict | None = None
    metadata: dict | None = Field(None, alias="metadata")
    status: ParseResultStatus
    status_message: str | None = Field(None, alias="statusMessage")
    started_at: datetime | None = Field(None, alias="startedAt")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

    @classmethod
    def from_orm_model(cls, obj: "ParseResult") -> "ParseResultResponse":
        """Create response from ORM model, handling metadata_ column alias."""
        return cls(
            id=obj.id,
            documentId=obj.document_id,
            parserType=obj.parser_type,
            fidelity=obj.fidelity,
            parserConfig=obj.parser_config,
            rawText=obj.raw_text,
            markdown=obj.markdown,
            pages=obj.pages,
            documentStructure=obj.document_structure,
            diagnostics=obj.diagnostics,
            metadata=obj.metadata_,
            status=obj.status,
            statusMessage=obj.status_message,
            startedAt=obj.started_at,
            createdBy=obj.created_by,
            createdAt=obj.created_at,
            updatedAt=obj.updated_at,
        )


class ParseResultListResponse(BaseModel):
    """Summary parse result for list endpoint."""
    id: UUID = Field(..., alias="id")
    document_id: UUID = Field(..., alias="documentId")
    parser_type: str = Field(..., alias="parserType")
    fidelity: str
    status: ParseResultStatus
    status_message: str | None = Field(None, alias="statusMessage")
    diagnostics: dict | None = None
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

    @classmethod
    def from_orm_model(cls, obj: "ParseResult") -> "ParseResultListResponse":
        return cls(
            id=obj.id,
            documentId=obj.document_id,
            parserType=obj.parser_type,
            fidelity=obj.fidelity,
            status=obj.status,
            statusMessage=obj.status_message,
            diagnostics=obj.diagnostics,
            createdAt=obj.created_at,
        )


class ParseRequest(BaseModel):
    """Request to (re-)parse a document."""
    parser_type: str = Field(..., alias="parserType")
    config: dict | None = None

    model_config = ConfigDict(populate_by_name=True)


class ParserInfoResponse(BaseModel):
    """Available parser information."""
    parser_type: str = Field(..., alias="parserType")
    name: str
    description: str
    supported_file_types: list[str] = Field(..., alias="supportedFileTypes")
    config_schema: dict | None = Field(None, alias="configSchema")

    model_config = ConfigDict(populate_by_name=True)
