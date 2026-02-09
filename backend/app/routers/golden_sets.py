"""Golden Sets API router."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.golden_set_repository import GoldenSetRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.golden_set import (
    GoldenSetCreate,
    GoldenSetUpdate,
    GoldenSetResponse,
    GoldenSetDetailResponse,
    QueryCreate,
    QueryUpdate,
    QueryResponse,
    SourceCreate,
    SourceResponse,
)
from app.services.golden_set_service import GoldenSetService
from app.services.exceptions import NotFoundError, ValidationError

router = APIRouter(
    prefix="/projects/{project_id}/golden-sets",
    tags=["golden_sets"],
)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_golden_set_service(db: AsyncSession = Depends(get_db)) -> GoldenSetService:
    return GoldenSetService(
        golden_set_repo=GoldenSetRepository(db),
        document_repo=DocumentRepository(db),
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
# Golden Set CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=list[GoldenSetResponse])
async def list_golden_sets(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    return await service.list(project_id)


@router.post("", response_model=GoldenSetResponse, status_code=status.HTTP_201_CREATED)
async def create_golden_set(
    project_id: UUID,
    data: GoldenSetCreate,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    return await service.create(project_id, current_user.id, data)


@router.get("/{gs_id}", response_model=GoldenSetDetailResponse)
async def get_golden_set(
    project_id: UUID,
    gs_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.get(gs_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{gs_id}", response_model=GoldenSetResponse)
async def update_golden_set(
    project_id: UUID,
    gs_id: UUID,
    data: GoldenSetUpdate,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.update(gs_id, project_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{gs_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_golden_set(
    project_id: UUID,
    gs_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        await service.delete(gs_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ---------------------------------------------------------------------------
# Query CRUD
# ---------------------------------------------------------------------------

@router.post("/{gs_id}/queries", response_model=QueryResponse, status_code=status.HTTP_201_CREATED)
async def add_query(
    project_id: UUID,
    gs_id: UUID,
    data: QueryCreate,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.add_query(gs_id, project_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{gs_id}/queries/{query_id}", response_model=QueryResponse)
async def update_query(
    project_id: UUID,
    gs_id: UUID,
    query_id: UUID,
    data: QueryUpdate,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.update_query(gs_id, project_id, query_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{gs_id}/queries/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_query(
    project_id: UUID,
    gs_id: UUID,
    query_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        await service.delete_query(gs_id, project_id, query_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ---------------------------------------------------------------------------
# Source CRUD
# ---------------------------------------------------------------------------

@router.post(
    "/{gs_id}/queries/{query_id}/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_source(
    project_id: UUID,
    gs_id: UUID,
    query_id: UUID,
    data: SourceCreate,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.add_source(gs_id, project_id, query_id, current_user.id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{gs_id}/queries/{query_id}/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_source(
    project_id: UUID,
    gs_id: UUID,
    query_id: UUID,
    source_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        await service.delete_source(gs_id, project_id, query_id, source_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
