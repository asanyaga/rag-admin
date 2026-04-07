"""Extraction Evaluation API router."""
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.extraction_eval_repository import ExtractionEvalRepository
from app.repositories.extraction_ground_truth_repository import ExtractionGroundTruthRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.extraction_eval import (
    ExtractionEvalRunCreate,
    ExtractionEvalRunResponse,
    ExtractionEvalResultResponse,
)
from app.services.extraction_eval.service import ExtractionEvalService
from app.services.exceptions import NotFoundError

router = APIRouter(tags=["extraction_eval"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_service(db: AsyncSession = Depends(get_db)) -> ExtractionEvalService:
    return ExtractionEvalService(
        eval_repo=ExtractionEvalRepository(db),
        gt_repo=ExtractionGroundTruthRepository(db),
        session=db,
    )


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
# Background task
# ---------------------------------------------------------------------------

async def execute_eval_run_background(
    db: AsyncSession,
    run_id: UUID,
) -> None:
    """Background task to execute an extraction eval run."""
    service = ExtractionEvalService(
        eval_repo=ExtractionEvalRepository(db),
        gt_repo=ExtractionGroundTruthRepository(db),
        session=db,
    )
    await service.execute_eval_run(run_id)


# ---------------------------------------------------------------------------
# Project-scoped routes
# ---------------------------------------------------------------------------

@router.post(
    "/projects/{project_id}/extraction-eval-runs",
    response_model=ExtractionEvalRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_extraction_eval_run(
    project_id: UUID,
    data: ExtractionEvalRunCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        run = await service.create_run(project_id, current_user.id, data)
        background_tasks.add_task(execute_eval_run_background, db=db, run_id=run.id)
        return run
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/projects/{project_id}/extraction-eval-runs",
    response_model=list[ExtractionEvalRunResponse],
)
async def list_extraction_eval_runs(
    project_id: UUID,
    ground_truth_set_id: UUID | None = Query(None, alias="groundTruthSetId"),
    current_user: User = Depends(get_current_active_user),
    service: ExtractionEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    return await service.list_runs(project_id, ground_truth_set_id)


# ---------------------------------------------------------------------------
# Direct by ID routes
# ---------------------------------------------------------------------------

@router.get(
    "/extraction-eval-runs/{run_id}",
    response_model=ExtractionEvalRunResponse,
)
async def get_extraction_eval_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionEvalService = Depends(get_service),
):
    try:
        return await service.get_run(run_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/extraction-eval-runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_extraction_eval_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionEvalService = Depends(get_service),
):
    try:
        await service.delete_run(run_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/extraction-eval-runs/{run_id}/results",
    response_model=list[ExtractionEvalResultResponse],
)
async def get_extraction_eval_run_results(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionEvalService = Depends(get_service),
):
    try:
        return await service.get_results(run_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/extraction-eval-results/{result_id}",
    response_model=ExtractionEvalResultResponse,
)
async def get_extraction_eval_result(
    result_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionEvalService = Depends(get_service),
):
    try:
        return await service.get_result(result_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
