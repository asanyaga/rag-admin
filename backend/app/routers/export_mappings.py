# backend/app/routers/export_mappings.py
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.export_mapping_repository import ExportMappingRepository
from app.schemas.export_mapping import (
    ExportMappingCreate,
    ExportMappingResponse,
    ExportMappingUpdate,
)
from app.services.export_mapping_service import ExportMappingService
from app.services.exceptions import ConflictError, NotFoundError

router = APIRouter(
    prefix="/projects/{project_id}/export-mappings",
    tags=["export-mappings"],
)


def get_service(db: AsyncSession = Depends(get_db)) -> ExportMappingService:
    return ExportMappingService(ExportMappingRepository(db))


@router.get("", response_model=list[ExportMappingResponse])
async def list_export_mappings(
    project_id: UUID,
    data_store_id: UUID = Query(...),
    current_user: User = Depends(get_current_active_user),
    service: ExportMappingService = Depends(get_service),
):
    return await service.list_by_store(project_id, data_store_id)


@router.post("", response_model=ExportMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_export_mapping(
    project_id: UUID,
    data: ExportMappingCreate,
    current_user: User = Depends(get_current_active_user),
    service: ExportMappingService = Depends(get_service),
):
    try:
        return await service.create(project_id, data)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.put("/{mapping_id}", response_model=ExportMappingResponse)
async def update_export_mapping(
    project_id: UUID,
    mapping_id: UUID,
    data: ExportMappingUpdate,
    current_user: User = Depends(get_current_active_user),
    service: ExportMappingService = Depends(get_service),
):
    try:
        return await service.update(mapping_id, project_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_export_mapping(
    project_id: UUID,
    mapping_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExportMappingService = Depends(get_service),
):
    try:
        await service.delete(mapping_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
