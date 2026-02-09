"""Eval Runs API router."""
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.eval_run_repository import EvalRunRepository
from app.repositories.golden_set_repository import GoldenSetRepository
from app.repositories.index_repository import IndexRepository
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.provider_key_repository import ProviderKeyRepository
from app.schemas.eval_run import (
    EvalRunCreate,
    EvalRunResponse,
    EvalRunResultResponse,
    RunComparisonResponse,
)
from app.services.eval_service import EvalService
from app.services.query_service import QueryService
from app.services.exceptions import NotFoundError, ValidationError

router = APIRouter(
    prefix="/projects/{project_id}/eval-runs",
    tags=["eval_runs"],
)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_eval_service(db: AsyncSession = Depends(get_db)) -> EvalService:
    eval_run_repo = EvalRunRepository(db)
    golden_set_repo = GoldenSetRepository(db)
    query_service = QueryService(
        index_repo=IndexRepository(db),
        chunk_repo=ChunkRepository(db),
        provider_key_repo=ProviderKeyRepository(db),
    )
    return EvalService(eval_run_repo, golden_set_repo, query_service)


def get_project_repo(db: AsyncSession = Depends(get_db)) -> ProjectRepository:
    return ProjectRepository(db)


async def verify_project_access(
    project_id: UUID,
    current_user: User,
    project_repo: ProjectRepository,
) -> None:
    project = await project_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )


# ---------------------------------------------------------------------------
# Background task helper
# ---------------------------------------------------------------------------

async def execute_eval_run_background(
    db: AsyncSession,
    run_id: UUID,
    project_id: UUID,
    user_id: UUID,
) -> None:
    """Background task to execute an eval run."""
    eval_run_repo = EvalRunRepository(db)
    golden_set_repo = GoldenSetRepository(db)
    query_service = QueryService(
        index_repo=IndexRepository(db),
        chunk_repo=ChunkRepository(db),
        provider_key_repo=ProviderKeyRepository(db),
    )
    service = EvalService(eval_run_repo, golden_set_repo, query_service)
    await service.execute_eval_run(run_id, project_id, user_id)


# ---------------------------------------------------------------------------
# Routes — compare must come before /{run_id}
# ---------------------------------------------------------------------------

@router.get("/compare", response_model=RunComparisonResponse)
async def compare_runs(
    project_id: UUID,
    run_ids: str = Query(..., alias="runIds", description="Comma-separated run IDs"),
    current_user: User = Depends(get_current_active_user),
    service: EvalService = Depends(get_eval_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)

    ids = [s.strip() for s in run_ids.split(",")]
    if len(ids) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly 2 run IDs required",
        )

    try:
        return await service.compare_runs(
            project_id, UUID(ids[0]), UUID(ids[1])
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=list[EvalRunResponse])
async def list_eval_runs(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: EvalService = Depends(get_eval_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    return await service.list_runs(project_id)


@router.post("", response_model=EvalRunResponse, status_code=status.HTTP_201_CREATED)
async def create_eval_run(
    project_id: UUID,
    data: EvalRunCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    service: EvalService = Depends(get_eval_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id, current_user, project_repo)

    try:
        run = await service.create_run(project_id, current_user.id, data)

        # Execute in background
        background_tasks.add_task(
            execute_eval_run_background,
            db=db,
            run_id=run.id,
            project_id=project_id,
            user_id=current_user.id,
        )

        return run
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{run_id}", response_model=EvalRunResponse)
async def get_eval_run(
    project_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: EvalService = Depends(get_eval_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.get_run(run_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_eval_run(
    project_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: EvalService = Depends(get_eval_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        await service.delete_run(run_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{run_id}/results", response_model=list[EvalRunResultResponse])
async def get_eval_run_results(
    project_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: EvalService = Depends(get_eval_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.get_results(run_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
