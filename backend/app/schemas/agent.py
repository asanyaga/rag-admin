"""Pydantic schemas for the agent module."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.agent_receipt import AgentReceiptStatus
from app.models.flow_run import FlowRunStatus


# --- Agent Tool schemas ---

class AgentToolResponse(BaseModel):
    """A reusable tool from the tool registry."""
    slug: str
    name: str
    category: str
    description: str
    input_keys: list[str] = Field(..., alias="inputKeys")
    output_keys: list[str] = Field(..., alias="outputKeys")
    config_schema: dict[str, Any] = Field(default_factory=dict, alias="configSchema")

    model_config = ConfigDict(populate_by_name=True)


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


# --- Flow Definition schemas ---

class FlowNodeSchema(BaseModel):
    """A node in a flow definition."""
    id: str
    tool: str
    config: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] | None = None  # {x, y} for canvas layout

    model_config = ConfigDict(populate_by_name=True)


class FlowEdgeSchema(BaseModel):
    """A simple edge in a flow definition."""
    source: str
    target: str


class FlowConditionalEdgeSchema(BaseModel):
    """A conditional edge in a flow definition."""
    source: str
    router: str
    targets: list[str]


class FlowDefinitionCreate(BaseModel):
    """Request to create a flow definition."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    definition: dict[str, Any]

    model_config = ConfigDict(populate_by_name=True)


class FlowDefinitionUpdate(BaseModel):
    """Request to update a flow definition."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    definition: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class FlowDefinitionResponse(BaseModel):
    """Flow definition response."""
    id: UUID
    project_id: UUID = Field(..., alias="projectId")
    name: str
    description: str | None = None
    definition: dict[str, Any]
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_model(cls, obj) -> "FlowDefinitionResponse":
        return cls(
            id=obj.id,
            projectId=obj.project_id,
            name=obj.name,
            description=obj.description,
            definition=obj.definition,
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


# --- Flow Run schemas ---

class StartExtractRunRequest(BaseModel):
    """Request to start an extract flow run."""
    flow_definition_id: UUID = Field(..., alias="flowDefinitionId")
    document_id: UUID = Field(..., alias="documentId")
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")

    model_config = ConfigDict(populate_by_name=True)


class StartFlowRunRequest(BaseModel):
    """Request to start a flow run."""
    flow_definition_id: UUID = Field(..., alias="flowDefinitionId")
    initial_state: dict[str, Any] = Field(default_factory=dict, alias="initialState")

    model_config = ConfigDict(populate_by_name=True)


class ResumeFlowRunRequest(BaseModel):
    """Request to resume an interrupted flow run."""
    resume_value: dict[str, Any] = Field(..., alias="resumeValue")

    model_config = ConfigDict(populate_by_name=True)


class FlowRunResponse(BaseModel):
    """Full flow run response."""
    id: UUID
    project_id: UUID = Field(..., alias="projectId")
    flow_definition_id: UUID = Field(..., alias="flowDefinitionId")
    status: FlowRunStatus
    status_message: str | None = Field(None, alias="statusMessage")
    initial_state: dict[str, Any] | None = Field(None, alias="initialState")
    current_state: dict[str, Any] | None = Field(None, alias="currentState")
    current_node: str | None = Field(None, alias="currentNode")
    thread_id: str | None = Field(None, alias="threadId")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_model(cls, obj) -> "FlowRunResponse":
        return cls(
            id=obj.id,
            projectId=obj.project_id,
            flowDefinitionId=obj.flow_definition_id,
            status=obj.status,
            statusMessage=obj.status_message,
            initialState=obj.initial_state,
            currentState=obj.current_state,
            currentNode=obj.current_node,
            threadId=obj.thread_id,
            createdBy=obj.created_by,
            createdAt=obj.created_at,
            updatedAt=obj.updated_at,
        )


class FlowRunListItem(BaseModel):
    """Summary flow run for list endpoint."""
    id: UUID
    flow_definition_id: UUID = Field(..., alias="flowDefinitionId")
    status: FlowRunStatus
    status_message: str | None = Field(None, alias="statusMessage")
    current_node: str | None = Field(None, alias="currentNode")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_model(cls, obj) -> "FlowRunListItem":
        return cls(
            id=obj.id,
            flowDefinitionId=obj.flow_definition_id,
            status=obj.status,
            statusMessage=obj.status_message,
            currentNode=obj.current_node,
            createdAt=obj.created_at,
        )
