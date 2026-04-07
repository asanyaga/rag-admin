"""Extraction Ground Truth API router."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.extraction_ground_truth_repository import ExtractionGroundTruthRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.extraction_ground_truth import (
    GroundTruthSetCreate,
    GroundTruthSetUpdate,
    GroundTruthSetResponse,
    GroundTruthItemCreate,
    GroundTruthItemUpdate,
    GroundTruthItemResponse,
    BulkImportRequest,
    BulkImportResponse,
)
from app.services.extraction_ground_truth_service import ExtractionGroundTruthService
from app.services.exceptions import NotFoundError

router = APIRouter(tags=["extraction_ground_truth"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_service(db: AsyncSession = Depends(get_db)) -> ExtractionGroundTruthService:
    return ExtractionGroundTruthService(
        repo=ExtractionGroundTruthRepository(db),
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
# Set routes (project-scoped)
# ---------------------------------------------------------------------------

@router.post(
    "/projects/{project_id}/extraction-ground-truth-sets",
    response_model=GroundTruthSetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ground_truth_set(
    project_id: UUID,
    data: GroundTruthSetCreate,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionGroundTruthService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.create_set(project_id, current_user.id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/projects/{project_id}/extraction-ground-truth-sets",
    response_model=list[GroundTruthSetResponse],
)
async def list_ground_truth_sets(
    project_id: UUID,
    extraction_schema_id: UUID | None = Query(None, alias="extractionSchemaId"),
    current_user: User = Depends(get_current_active_user),
    service: ExtractionGroundTruthService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    return await service.list_sets(project_id, extraction_schema_id)


# ---------------------------------------------------------------------------
# Set routes (direct by ID)
# ---------------------------------------------------------------------------

@router.get(
    "/extraction-ground-truth-sets/{set_id}",
    response_model=GroundTruthSetResponse,
)
async def get_ground_truth_set(
    set_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionGroundTruthService = Depends(get_service),
):
    try:
        return await service.get_set(set_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put(
    "/extraction-ground-truth-sets/{set_id}",
    response_model=GroundTruthSetResponse,
)
async def update_ground_truth_set(
    set_id: UUID,
    data: GroundTruthSetUpdate,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionGroundTruthService = Depends(get_service),
):
    try:
        return await service.update_set(set_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/extraction-ground-truth-sets/{set_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_ground_truth_set(
    set_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionGroundTruthService = Depends(get_service),
):
    try:
        await service.delete_set(set_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ---------------------------------------------------------------------------
# Item routes (set-scoped)
# ---------------------------------------------------------------------------

@router.post(
    "/extraction-ground-truth-sets/{set_id}/items",
    response_model=GroundTruthItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ground_truth_item(
    set_id: UUID,
    data: GroundTruthItemCreate,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionGroundTruthService = Depends(get_service),
):
    try:
        return await service.create_item(set_id, current_user.id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/extraction-ground-truth-sets/{set_id}/items/bulk",
    response_model=BulkImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bulk_create_ground_truth_items(
    set_id: UUID,
    data: BulkImportRequest,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionGroundTruthService = Depends(get_service),
):
    try:
        return await service.bulk_create_items(set_id, current_user.id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/extraction-ground-truth-sets/{set_id}/items",
    response_model=list[GroundTruthItemResponse],
)
async def list_ground_truth_items(
    set_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionGroundTruthService = Depends(get_service),
):
    return await service.list_items(set_id)


# ---------------------------------------------------------------------------
# Item routes (direct by ID)
# ---------------------------------------------------------------------------

@router.get(
    "/extraction-ground-truth-items/{item_id}",
    response_model=GroundTruthItemResponse,
)
async def get_ground_truth_item(
    item_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionGroundTruthService = Depends(get_service),
):
    try:
        return await service.get_item(item_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put(
    "/extraction-ground-truth-items/{item_id}",
    response_model=GroundTruthItemResponse,
)
async def update_ground_truth_item(
    item_id: UUID,
    data: GroundTruthItemUpdate,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionGroundTruthService = Depends(get_service),
):
    try:
        return await service.update_item(item_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/extraction-ground-truth-items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_ground_truth_item(
    item_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionGroundTruthService = Depends(get_service),
):
    try:
        await service.delete_item(item_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
