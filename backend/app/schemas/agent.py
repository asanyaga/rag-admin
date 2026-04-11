"""Pydantic schemas for the agent module."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.agent_run import AgentRunStatus


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


# --- Agent Definition schemas ---

class AgentNodeSchema(BaseModel):
    """A node in an agent definition."""
    id: str
    tool: str
    config: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] | None = None  # {x, y} for canvas layout

    model_config = ConfigDict(populate_by_name=True)


class AgentEdgeSchema(BaseModel):
    """A simple edge in an agent definition."""
    source: str
    target: str


class AgentConditionalEdgeSchema(BaseModel):
    """A conditional edge in an agent definition."""
    source: str
    router: str
    targets: list[str]


class AgentDefinitionCreate(BaseModel):
    """Request to create an agent definition."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    definition: dict[str, Any]

    model_config = ConfigDict(populate_by_name=True)


class AgentDefinitionUpdate(BaseModel):
    """Request to update an agent definition."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    definition: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class AgentDefinitionResponse(BaseModel):
    """Agent definition response."""
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
    def from_orm_model(cls, obj) -> "AgentDefinitionResponse":
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


# --- Agent Run schemas ---

class StartExtractRunRequest(BaseModel):
    """Request to start an extract agent run."""
    agent_definition_id: UUID = Field(..., alias="agentDefinitionId")
    document_id: UUID = Field(..., alias="documentId")
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")

    model_config = ConfigDict(populate_by_name=True)


class StartAgentRunRequest(BaseModel):
    """Request to start an agent run."""
    agent_definition_id: UUID = Field(..., alias="agentDefinitionId")
    initial_state: dict[str, Any] = Field(default_factory=dict, alias="initialState")

    model_config = ConfigDict(populate_by_name=True)


class ResumeAgentRunRequest(BaseModel):
    """Request to resume an interrupted agent run."""
    resume_value: dict[str, Any] = Field(..., alias="resumeValue")

    model_config = ConfigDict(populate_by_name=True)


class AgentRunResponse(BaseModel):
    """Full agent run response."""
    id: UUID
    project_id: UUID = Field(..., alias="projectId")
    agent_definition_id: UUID = Field(..., alias="agentDefinitionId")
    status: AgentRunStatus
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
    def from_orm_model(cls, obj) -> "AgentRunResponse":
        return cls(
            id=obj.id,
            projectId=obj.project_id,
            agentDefinitionId=obj.agent_definition_id,
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


class AgentRunListItem(BaseModel):
    """Summary agent run for list endpoint."""
    id: UUID
    agent_definition_id: UUID = Field(..., alias="agentDefinitionId")
    status: AgentRunStatus
    status_message: str | None = Field(None, alias="statusMessage")
    current_node: str | None = Field(None, alias="currentNode")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_model(cls, obj) -> "AgentRunListItem":
        return cls(
            id=obj.id,
            agentDefinitionId=obj.agent_definition_id,
            status=obj.status,
            statusMessage=obj.status_message,
            currentNode=obj.current_node,
            createdAt=obj.created_at,
        )
