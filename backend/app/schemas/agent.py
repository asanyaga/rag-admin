"""Pydantic schemas for the agent module."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.agent_receipt import AgentReceiptStatus


# --- Agent Type schemas ---

class AgentTypeResponse(BaseModel):
    """Available agent type from the registry."""
    slug: str
    name: str
    description: str
    nodes: list[dict[str, str]]
    config_schema: dict[str, Any] = Field(default_factory=dict, alias="configSchema")

    model_config = ConfigDict(populate_by_name=True)


# --- Agent Config schemas ---

class AgentConfigCreate(BaseModel):
    """Request to enable an agent type for a project."""
    agent_type: str = Field(..., alias="agentType")
    config: dict | None = None

    model_config = ConfigDict(populate_by_name=True)


class AgentConfigResponse(BaseModel):
    """Agent config response."""
    id: UUID
    project_id: UUID = Field(..., alias="projectId")
    agent_type: str = Field(..., alias="agentType")
    config: dict | None = None
    enabled: bool
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_model(cls, obj) -> "AgentConfigResponse":
        return cls(
            id=obj.id,
            projectId=obj.project_id,
            agentType=obj.agent_type,
            config=obj.config,
            enabled=obj.enabled,
            createdBy=obj.created_by,
            createdAt=obj.created_at,
            updatedAt=obj.updated_at,
        )


class StartProcessingRequest(BaseModel):
    """Request to start processing a receipt."""
    document_id: UUID = Field(..., alias="documentId")
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")

    model_config = ConfigDict(populate_by_name=True)


class SubmitReviewRequest(BaseModel):
    """Request to submit a review decision."""
    action: Literal["approve", "edit", "reject"]
    data: dict | None = None

    model_config = ConfigDict(populate_by_name=True)


class AgentReceiptResponse(BaseModel):
    """Full agent receipt response."""
    id: UUID
    project_id: UUID = Field(..., alias="projectId")
    document_id: UUID = Field(..., alias="documentId")
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")
    status: AgentReceiptStatus
    status_message: str | None = Field(None, alias="statusMessage")
    extracted_data: dict | None = Field(None, alias="extractedData")
    reviewed_data: dict | None = Field(None, alias="reviewedData")
    thread_id: str | None = Field(None, alias="threadId")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_model(cls, obj) -> "AgentReceiptResponse":
        return cls(
            id=obj.id,
            projectId=obj.project_id,
            documentId=obj.document_id,
            extractionSchemaId=obj.extraction_schema_id,
            status=obj.status,
            statusMessage=obj.status_message,
            extractedData=obj.extracted_data,
            reviewedData=obj.reviewed_data,
            threadId=obj.thread_id,
            createdBy=obj.created_by,
            createdAt=obj.created_at,
            updatedAt=obj.updated_at,
        )


class AgentReceiptListItem(BaseModel):
    """Summary agent receipt for list endpoint."""
    id: UUID
    document_id: UUID = Field(..., alias="documentId")
    status: AgentReceiptStatus
    status_message: str | None = Field(None, alias="statusMessage")
    extracted_data: dict | None = Field(None, alias="extractedData")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_model(cls, obj) -> "AgentReceiptListItem":
        return cls(
            id=obj.id,
            documentId=obj.document_id,
            status=obj.status,
            statusMessage=obj.status_message,
            extractedData=obj.extracted_data,
            createdAt=obj.created_at,
        )
