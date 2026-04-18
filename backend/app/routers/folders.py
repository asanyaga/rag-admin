from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.folder_repository import FolderRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.folder import FolderCreate, FolderUpdate, FolderResponse
from app.services.folder_service import FolderService
from app.services.exceptions import ConflictError, NotFoundError

router = APIRouter(prefix="/projects/{project_id}/folders", tags=["folders"])


def get_folder_service(db: AsyncSession = Depends(get_db)) -> FolderService:
    folder_repo = FolderRepository(db)
    project_repo = ProjectRepository(db)
    return FolderService(folder_repo=folder_repo, project_repo=project_repo)


@router.get("", response_model=list[FolderResponse])
async def list_folders(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    folder_service: FolderService = Depends(get_folder_service),
):
    return await folder_service.list_folders(user_id=current_user.id, project_id=project_id)


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    project_id: UUID,
    data: FolderCreate,
    current_user: User = Depends(get_current_active_user),
    folder_service: FolderService = Depends(get_folder_service),
):
    try:
        return await folder_service.create_folder(
            user_id=current_user.id, project_id=project_id, data=data
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    project_id: UUID,
    folder_id: UUID,
    data: FolderUpdate,
    current_user: User = Depends(get_current_active_user),
    folder_service: FolderService = Depends(get_folder_service),
):
    try:
        return await folder_service.update_folder(
            folder_id=folder_id, user_id=current_user.id, data=data
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    project_id: UUID,
    folder_id: UUID,
    current_user: User = Depends(get_current_active_user),
    folder_service: FolderService = Depends(get_folder_service),
):
    try:
        await folder_service.delete_folder(folder_id=folder_id, user_id=current_user.id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
