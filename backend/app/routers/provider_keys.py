"""Provider Keys API router for BYOK (Bring Your Own Key) functionality."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.provider_key_repository import ProviderKeyRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.provider_key import (
    ProviderKeyCreate,
    ProviderKeyResponse,
    ProviderKeyListResponse,
    ProviderListResponse,
)
from app.services.provider_key_service import ProviderKeyService
from app.services.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/settings/provider-keys", tags=["provider-keys"])


def get_provider_key_service(db: AsyncSession = Depends(get_db)) -> ProviderKeyService:
    """Dependency to create ProviderKeyService."""
    provider_key_repo = ProviderKeyRepository(db)
    return ProviderKeyService(provider_key_repo)


def get_project_repo(db: AsyncSession = Depends(get_db)) -> ProjectRepository:
    """Dependency to get ProjectRepository for verification."""
    return ProjectRepository(db)


# ---------------------------------------------------------------------------
# Providers Info
# ---------------------------------------------------------------------------

@router.get(
    "/providers",
    response_model=ProviderListResponse,
    summary="List supported providers",
    description="Get list of all supported embedding providers and their available models.",
)
async def list_providers(
    service: ProviderKeyService = Depends(get_provider_key_service),
):
    """List all supported embedding providers."""
    return service.list_providers()


# ---------------------------------------------------------------------------
# Account-Level Keys
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=ProviderKeyListResponse,
    summary="List account keys",
    description="List all account-level provider API keys (masked).",
)
async def list_account_keys(
    current_user: User = Depends(get_current_active_user),
    service: ProviderKeyService = Depends(get_provider_key_service),
):
    """List account-level API keys."""
    return await service.list_account_keys(current_user.id)


@router.post(
    "",
    response_model=ProviderKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Set account key",
    description="Set or update an account-level API key for a provider.",
)
async def set_account_key(
    data: ProviderKeyCreate,
    current_user: User = Depends(get_current_active_user),
    service: ProviderKeyService = Depends(get_provider_key_service),
):
    """Set an account-level API key."""
    try:
        return await service.set_account_key(current_user.id, data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete(
    "/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete account key",
    description="Delete an account-level API key for a provider.",
)
async def delete_account_key(
    provider: str,
    current_user: User = Depends(get_current_active_user),
    service: ProviderKeyService = Depends(get_provider_key_service),
):
    """Delete an account-level API key."""
    try:
        await service.delete_account_key(current_user.id, provider)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# ---------------------------------------------------------------------------
# Project-Level Keys
# ---------------------------------------------------------------------------

project_router = APIRouter(
    prefix="/projects/{project_id}/settings/provider-keys",
    tags=["provider-keys"]
)


@project_router.get(
    "",
    response_model=ProviderKeyListResponse,
    summary="List project keys",
    description="List all project-level provider API keys (masked).",
)
async def list_project_keys(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ProviderKeyService = Depends(get_provider_key_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """List project-level API keys."""
    # Verify project belongs to user
    project = await project_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )

    return await service.list_project_keys(current_user.id, project_id)


@project_router.post(
    "",
    response_model=ProviderKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Set project key",
    description="Set or update a project-level API key for a provider.",
)
async def set_project_key(
    project_id: UUID,
    data: ProviderKeyCreate,
    current_user: User = Depends(get_current_active_user),
    service: ProviderKeyService = Depends(get_provider_key_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Set a project-level API key."""
    # Verify project belongs to user
    project = await project_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )

    try:
        return await service.set_project_key(current_user.id, project_id, data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@project_router.delete(
    "/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project key",
    description="Delete a project-level API key for a provider.",
)
async def delete_project_key(
    project_id: UUID,
    provider: str,
    current_user: User = Depends(get_current_active_user),
    service: ProviderKeyService = Depends(get_provider_key_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Delete a project-level API key."""
    # Verify project belongs to user
    project = await project_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )

    try:
        await service.delete_project_key(current_user.id, project_id, provider)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
