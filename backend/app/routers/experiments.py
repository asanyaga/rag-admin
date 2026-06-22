"""Experiments API router."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.experiment_repository import ExperimentRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentUpdate,
    ExperimentResponse,
    ExperimentDetailResponse,
)
from app.schemas.experiment_comparison import ExperimentComparisonResponse
from app.services.experiment_service import ExperimentService
from app.services.exceptions import NotFoundError

router = APIRouter(
    prefix="/projects/{project_id}/experiments",
    tags=["experiments"],
)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_experiment_service(db: AsyncSession = Depends(get_db)) -> ExperimentService:
    return ExperimentService(ExperimentRepository(db))


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
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ExperimentResponse])
async def list_experiments(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExperimentService = Depends(get_experiment_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    return await service.list_by_project(project_id)


@router.post("", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    project_id: UUID,
    data: ExperimentCreate,
    current_user: User = Depends(get_current_active_user),
    service: ExperimentService = Depends(get_experiment_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    return await service.create(project_id, current_user.id, data)


@router.get("/{experiment_id}/compare", response_model=ExperimentComparisonResponse)
async def compare_experiment(
    project_id: UUID,
    experiment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExperimentService = Depends(get_experiment_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.compare(experiment_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{experiment_id}", response_model=ExperimentDetailResponse)
async def get_experiment(
    project_id: UUID,
    experiment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExperimentService = Depends(get_experiment_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.get_detail(experiment_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    project_id: UUID,
    experiment_id: UUID,
    data: ExperimentUpdate,
    current_user: User = Depends(get_current_active_user),
    service: ExperimentService = Depends(get_experiment_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.update(experiment_id, project_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_experiment(
    project_id: UUID,
    experiment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExperimentService = Depends(get_experiment_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        await service.delete(experiment_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
