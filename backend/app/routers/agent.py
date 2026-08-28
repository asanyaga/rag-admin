"""Agent API router — agent definitions and agent run endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.agent_definition_repository import AgentDefinitionRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.extraction_schema_repository import ExtractionSchemaRepository
from app.schemas.agent import (
    AgentToolResponse,
    AgentDefinitionCreate,
    AgentDefinitionUpdate,
    AgentDefinitionResponse,
    StartAgentRunRequest,
    StartExtractRunRequest,
    StartParseRunRequest,
    ResumeAgentRunRequest,
    AgentRunResponse,
    AgentRunListItem,
)
from app.services.agent.agent_run_service import AgentRunService
from app.services.agent.extract_run_service import ExtractRunService
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
    return [
        AgentToolResponse(
            slug=t.slug, name=t.name, category=t.category, description=t.description,
            runtimeInputs=[{"key": f.key, "label": f.label, "widget": f.widget,
                            "source": f.source} for f in t.runtime_inputs],
            outputs=t.outputs,
            configSchema=t.config_schema,
            configPanel=t.config_panel,
        )
        for t in list_tools()
    ]


# --- Agent Definitions ---

@router.get(
    "/agent/projects/{project_id}/definitions",
    response_model=list[AgentDefinitionResponse],
    summary="List agent definitions for a project",
)
async def list_definitions(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = AgentDefinitionRepository(db)
    definitions = await repo.list_by_project(project_id)
    return [AgentDefinitionResponse.from_orm_model(d) for d in definitions]


@router.post(
    "/agent/projects/{project_id}/definitions",
    response_model=AgentDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an agent definition",
)
async def create_definition(
    project_id: UUID,
    body: AgentDefinitionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.exc import IntegrityError

    repo = AgentDefinitionRepository(db)
    try:
        definition = await repo.create(
            project_id=project_id,
            name=body.name,
            description=body.description,
            definition=body.definition,
            created_by=current_user.id,
        )
    except IntegrityError as e:
        error_str = str(e).lower()
        if 'uq_agent_definitions_project_name' in error_str:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An agent named '{body.name}' already exists in this project",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create agent definition",
        )
    return AgentDefinitionResponse.from_orm_model(definition)


@router.get(
    "/agent/definitions/{definition_id}",
    response_model=AgentDefinitionResponse,
    summary="Get an agent definition",
)
async def get_definition(
    definition_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = AgentDefinitionRepository(db)
    definition = await repo.get_by_id(definition_id)
    if not definition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent definition not found")
    return AgentDefinitionResponse.from_orm_model(definition)


@router.put(
    "/agent/definitions/{definition_id}",
    response_model=AgentDefinitionResponse,
    summary="Update an agent definition",
)
async def update_definition(
    definition_id: UUID,
    body: AgentDefinitionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.exc import IntegrityError

    repo = AgentDefinitionRepository(db)
    try:
        definition = await repo.update(
            agent_id=definition_id,
            name=body.name,
            description=body.description,
            definition=body.definition,
        )
    except IntegrityError as e:
        error_str = str(e).lower()
        if 'uq_agent_definitions_project_name' in error_str:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An agent named '{body.name}' already exists in this project",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update agent definition",
        )
    if not definition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent definition not found")
    return AgentDefinitionResponse.from_orm_model(definition)


@router.delete(
    "/agent/definitions/{definition_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an agent definition",
)
async def delete_definition(
    definition_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = AgentDefinitionRepository(db)
    deleted = await repo.delete(definition_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent definition not found")


# --- Agent Runs ---

def get_agent_run_service(
    db: AsyncSession = Depends(get_db),
) -> AgentRunService:
    """Dependency to create AgentRunService with checkpointer from app state."""
    from app.main import app
    checkpointer = app.state.agent_checkpointer

    return AgentRunService(
        agent_run_repo=AgentRunRepository(db),
        agent_def_repo=AgentDefinitionRepository(db),
        checkpointer=checkpointer,
    )


@router.post(
    "/agent/projects/{project_id}/runs",
    response_model=AgentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start an agent run",
)
async def start_run(
    project_id: UUID,
    body: StartAgentRunRequest,
    current_user: User = Depends(get_current_active_user),
    service: AgentRunService = Depends(get_agent_run_service),
):
    try:
        return await service.start_run(
            project_id=project_id,
            agent_definition_id=body.agent_definition_id,
            initial_state=body.initial_state,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/agent/projects/{project_id}/runs",
    response_model=list[AgentRunListItem],
    summary="List agent runs for a project",
)
async def list_runs(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: AgentRunService = Depends(get_agent_run_service),
):
    return await service.list_runs(project_id)


@router.get(
    "/agent/runs/{run_id}",
    response_model=AgentRunResponse,
    summary="Get an agent run",
)
async def get_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: AgentRunService = Depends(get_agent_run_service),
):
    try:
        return await service.get_run(run_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/agent/runs/{run_id}/resume",
    response_model=AgentRunResponse,
    summary="Resume an interrupted agent run",
)
async def resume_run(
    run_id: UUID,
    body: ResumeAgentRunRequest,
    current_user: User = Depends(get_current_active_user),
    service: AgentRunService = Depends(get_agent_run_service),
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
    summary="Delete an agent run",
)
async def delete_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = AgentRunRepository(db)
    deleted = await repo.delete(run_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")


# --- Extract Runs ---

def get_extract_run_service(
    db: AsyncSession = Depends(get_db),
) -> ExtractRunService:
    from app.main import app
    checkpointer = app.state.agent_checkpointer
    return ExtractRunService(
        agent_run_service=AgentRunService(
            agent_run_repo=AgentRunRepository(db),
            agent_def_repo=AgentDefinitionRepository(db),
            checkpointer=checkpointer,
        ),
        document_repo=DocumentRepository(db),
        schema_repo=ExtractionSchemaRepository(db),
    )


@router.post(
    "/agent/extract/projects/{project_id}/runs",
    response_model=AgentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start an extract agent run",
)
async def start_extract_run(
    project_id: UUID,
    body: StartExtractRunRequest,
    current_user: User = Depends(get_current_active_user),
    service: ExtractRunService = Depends(get_extract_run_service),
):
    try:
        return await service.start_extract_run(
            project_id=project_id,
            agent_definition_id=body.agent_definition_id,
            document_id=body.document_id,
            extraction_schema_id=body.extraction_schema_id,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Parse Runs ---

def get_parse_run_service(
    db: AsyncSession = Depends(get_db),
) -> "ParseRunService":
    from app.main import app
    from app.repositories.provider_key_repository import ProviderKeyRepository
    from app.repositories.source_document_repository import SourceDocumentRepository
    from app.services.agent.parse_run_service import ParseRunService

    checkpointer = app.state.agent_checkpointer
    return ParseRunService(
        agent_run_service=AgentRunService(
            agent_run_repo=AgentRunRepository(db),
            agent_def_repo=AgentDefinitionRepository(db),
            checkpointer=checkpointer,
        ),
        source_doc_repo=SourceDocumentRepository(db),
        provider_key_repo=ProviderKeyRepository(db),
    )


@router.post(
    "/agent/parse/projects/{project_id}/runs",
    response_model=AgentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a parse agent run",
)
async def start_parse_run(
    project_id: UUID,
    body: StartParseRunRequest,
    current_user: User = Depends(get_current_active_user),
    service: "ParseRunService" = Depends(get_parse_run_service),
):
    try:
        return await service.start_parse_run(
            project_id=project_id,
            agent_definition_id=body.agent_definition_id,
            source_document_id=body.source_document_id,
            parser=body.parser,
            representation_kind=body.representation_kind,
            parse_config=body.parse_config,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
