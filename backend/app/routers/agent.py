"""Agent API router — agent configs, flow definitions, and flow run endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.agent_config_repository import AgentConfigRepository
from app.repositories.flow_definition_repository import FlowDefinitionRepository
from app.repositories.flow_run_repository import FlowRunRepository
from app.schemas.agent import (
    AgentToolResponse,
    AgentConfigCreate,
    AgentConfigResponse,
    FlowDefinitionCreate,
    FlowDefinitionUpdate,
    FlowDefinitionResponse,
    StartFlowRunRequest,
    ResumeFlowRunRequest,
    FlowRunResponse,
    FlowRunListItem,
)
from app.services.agent.flow_run_service import FlowRunService
from app.services.agent.tools import list_tools
from app.services.exceptions import NotFoundError


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
    summary="Enable an agent config for a project",
)
async def create_config(
    project_id: UUID,
    body: AgentConfigCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
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
    from sqlalchemy.exc import IntegrityError

    repo = FlowDefinitionRepository(db)
    try:
        flow = await repo.create(
            project_id=project_id,
            name=body.name,
            description=body.description,
            definition=body.definition,
            created_by=current_user.id,
        )
    except IntegrityError as e:
        error_str = str(e).lower()
        if 'uq_flow_definitions_project_name' in error_str:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A flow named '{body.name}' already exists in this project",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create flow definition",
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
    from sqlalchemy.exc import IntegrityError

    repo = FlowDefinitionRepository(db)
    try:
        flow = await repo.update(
            flow_id=flow_id,
            name=body.name,
            description=body.description,
            definition=body.definition,
        )
    except IntegrityError as e:
        error_str = str(e).lower()
        if 'uq_flow_definitions_project_name' in error_str:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A flow named '{body.name}' already exists in this project",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update flow definition",
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


# --- Flow Runs ---

def get_flow_run_service(
    db: AsyncSession = Depends(get_db),
) -> FlowRunService:
    """Dependency to create FlowRunService with checkpointer from app state."""
    from app.main import app
    checkpointer = app.state.agent_checkpointer

    return FlowRunService(
        flow_run_repo=FlowRunRepository(db),
        flow_def_repo=FlowDefinitionRepository(db),
        checkpointer=checkpointer,
    )


@router.post(
    "/agent/projects/{project_id}/runs",
    response_model=FlowRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a flow run",
)
async def start_flow_run(
    project_id: UUID,
    body: StartFlowRunRequest,
    current_user: User = Depends(get_current_active_user),
    service: FlowRunService = Depends(get_flow_run_service),
):
    try:
        return await service.start_run(
            project_id=project_id,
            flow_definition_id=body.flow_definition_id,
            initial_state=body.initial_state,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/agent/projects/{project_id}/runs",
    response_model=list[FlowRunListItem],
    summary="List flow runs for a project",
)
async def list_flow_runs(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: FlowRunService = Depends(get_flow_run_service),
):
    return await service.list_runs(project_id)


@router.get(
    "/agent/runs/{run_id}",
    response_model=FlowRunResponse,
    summary="Get a flow run",
)
async def get_flow_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: FlowRunService = Depends(get_flow_run_service),
):
    try:
        return await service.get_run(run_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/agent/runs/{run_id}/resume",
    response_model=FlowRunResponse,
    summary="Resume an interrupted flow run",
)
async def resume_flow_run(
    run_id: UUID,
    body: ResumeFlowRunRequest,
    current_user: User = Depends(get_current_active_user),
    service: FlowRunService = Depends(get_flow_run_service),
):
    try:
        return await service.resume_run(
            run_id=run_id,
            resume_value=body.resume_value,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/agent/runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a flow run",
)
async def delete_flow_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = FlowRunRepository(db)
    deleted = await repo.delete(run_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
