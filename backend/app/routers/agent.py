"""Agent API router — agent configs, types, and receipt processing endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.agent_config_repository import AgentConfigRepository
from app.repositories.agent_receipt_repository import AgentReceiptRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.extraction_schema_repository import ExtractionSchemaRepository
from app.repositories.flow_definition_repository import FlowDefinitionRepository
from app.schemas.agent import (
    AgentToolResponse,
    AgentTypeResponse,
    AgentConfigCreate,
    AgentConfigResponse,
    FlowDefinitionCreate,
    FlowDefinitionUpdate,
    FlowDefinitionResponse,
    StartProcessingRequest,
    SubmitReviewRequest,
    AgentReceiptResponse,
    AgentReceiptListItem,
)
from app.services.agent.service import AgentService
from app.services.agent.tools import list_tools
from app.services.agent.types import list_agent_types, get_agent_type
from app.services.exceptions import NotFoundError, ConflictError


router = APIRouter(tags=["agent"])


# --- Agent Tools ---

@router.get(
    "/agent/tools",
    response_model=list[AgentToolResponse],
    summary="List available agent tools",
)
async def list_agent_tools(
    current_user: User = Depends(get_current_active_user),
):
    tools = list_tools()
    return [
        AgentToolResponse(
            slug=t.slug,
            name=t.name,
            category=t.category,
            description=t.description,
            inputKeys=t.input_keys,
            outputKeys=t.output_keys,
            configSchema=t.config_schema,
        )
        for t in tools
    ]


def get_agent_service(
    db: AsyncSession = Depends(get_db),
) -> AgentService:
    """Dependency to create AgentService with checkpointer from app state."""
    from app.main import app
    checkpointer = app.state.agent_checkpointer

    return AgentService(
        receipt_repo=AgentReceiptRepository(db),
        document_repo=DocumentRepository(db),
        schema_repo=ExtractionSchemaRepository(db),
        checkpointer=checkpointer,
    )


# --- Agent Types ---

@router.get(
    "/agent/types",
    response_model=list[AgentTypeResponse],
    summary="List available agent types",
)
async def list_types(
    current_user: User = Depends(get_current_active_user),
):
    types = list_agent_types()
    return [
        AgentTypeResponse(
            slug=t.slug,
            name=t.name,
            description=t.description,
            nodes=t.nodes,
            configSchema=t.config_schema,
        )
        for t in types
    ]


# --- Agent Configs ---

@router.get(
    "/agent/projects/{project_id}/configs",
    response_model=list[AgentConfigResponse],
    summary="List agent configs for a project",
)
async def list_configs(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = AgentConfigRepository(db)
    configs = await repo.list_by_project(project_id)
    return [AgentConfigResponse.from_orm_model(c) for c in configs]


@router.post(
    "/agent/projects/{project_id}/configs",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enable an agent type for a project",
)
async def create_config(
    project_id: UUID,
    body: AgentConfigCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate agent type exists
    agent_type = get_agent_type(body.agent_type)
    if not agent_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown agent type: {body.agent_type}",
        )

    repo = AgentConfigRepository(db)

    # Check for duplicate
    existing = await repo.get_by_project_and_type(project_id, body.agent_type)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent type '{body.agent_type}' already configured for this project",
        )

    config = await repo.create(
        project_id=project_id,
        agent_type=body.agent_type,
        created_by=current_user.id,
        config=body.config,
    )

    # Seed default flow definition if the agent type has one
    if agent_type.flow_definition:
        flow_repo = FlowDefinitionRepository(db)
        await flow_repo.create(
            project_id=project_id,
            name=agent_type.name,
            description=agent_type.description,
            definition=agent_type.flow_definition,
            created_by=current_user.id,
        )

    return AgentConfigResponse.from_orm_model(config)


@router.delete(
    "/agent/configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an agent config",
)
async def delete_config(
    config_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = AgentConfigRepository(db)
    deleted = await repo.delete(config_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")


# --- Flow Definitions ---

@router.get(
    "/agent/projects/{project_id}/flows",
    response_model=list[FlowDefinitionResponse],
    summary="List flow definitions for a project",
)
async def list_flows(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = FlowDefinitionRepository(db)
    flows = await repo.list_by_project(project_id)
    return [FlowDefinitionResponse.from_orm_model(f) for f in flows]


@router.post(
    "/agent/projects/{project_id}/flows",
    response_model=FlowDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a flow definition",
)
async def create_flow(
    project_id: UUID,
    body: FlowDefinitionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = FlowDefinitionRepository(db)
    flow = await repo.create(
        project_id=project_id,
        name=body.name,
        description=body.description,
        definition=body.definition,
        created_by=current_user.id,
    )
    return FlowDefinitionResponse.from_orm_model(flow)


@router.get(
    "/agent/flows/{flow_id}",
    response_model=FlowDefinitionResponse,
    summary="Get a flow definition",
)
async def get_flow(
    flow_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = FlowDefinitionRepository(db)
    flow = await repo.get_by_id(flow_id)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    return FlowDefinitionResponse.from_orm_model(flow)


@router.put(
    "/agent/flows/{flow_id}",
    response_model=FlowDefinitionResponse,
    summary="Update a flow definition",
)
async def update_flow(
    flow_id: UUID,
    body: FlowDefinitionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = FlowDefinitionRepository(db)
    flow = await repo.update(
        flow_id=flow_id,
        name=body.name,
        description=body.description,
        definition=body.definition,
    )
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    return FlowDefinitionResponse.from_orm_model(flow)


@router.delete(
    "/agent/flows/{flow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a flow definition",
)
async def delete_flow(
    flow_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = FlowDefinitionRepository(db)
    deleted = await repo.delete(flow_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")


# --- Receipt Processing ---

@router.post(
    "/agent/projects/{project_id}/receipts",
    response_model=AgentReceiptResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start processing a receipt",
)
async def start_processing(
    project_id: UUID,
    body: StartProcessingRequest,
    current_user: User = Depends(get_current_active_user),
    service: AgentService = Depends(get_agent_service),
):
    try:
        return await service.start_processing(
            project_id=project_id,
            document_id=body.document_id,
            extraction_schema_id=body.extraction_schema_id,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/agent/projects/{project_id}/receipts",
    response_model=list[AgentReceiptListItem],
    summary="List receipts for a project",
)
async def list_receipts(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: AgentService = Depends(get_agent_service),
):
    return await service.list_receipts(project_id)


@router.get(
    "/agent/receipts/{receipt_id}",
    response_model=AgentReceiptResponse,
    summary="Get a receipt",
)
async def get_receipt(
    receipt_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: AgentService = Depends(get_agent_service),
):
    try:
        return await service.get_receipt(receipt_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/agent/receipts/{receipt_id}/review",
    response_model=AgentReceiptResponse,
    summary="Submit review for a receipt",
)
async def submit_review(
    receipt_id: UUID,
    body: SubmitReviewRequest,
    current_user: User = Depends(get_current_active_user),
    service: AgentService = Depends(get_agent_service),
):
    try:
        return await service.submit_review(
            receipt_id=receipt_id,
            action=body.action,
            data=body.data,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
