# backend/app/routers/data_stores.py
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.data_store_repository import DataStoreRepository
from app.schemas.data_store import (
    DataStoreCreate,
    DataStoreUpdate,
    DataStoreResponse,
    DataStoreRowResponse,
    DataStoreRowsResponse,
    CsvImportResponse,
    ExportPreviewRequest,
    ExportPreviewResponse,
    ExportExecuteResponse,
)
from app.services.data_store_service import DataStoreService
from app.services.exceptions import ConflictError, NotFoundError, ValidationError

router = APIRouter(
    prefix="/projects/{project_id}/data-stores",
    tags=["data-stores"],
)


def get_data_store_service(db: AsyncSession = Depends(get_db)) -> DataStoreService:
    repo = DataStoreRepository(db)
    return DataStoreService(repo)


# ── Store CRUD ─────────────────────────────────────────────────────

@router.post("", response_model=DataStoreResponse, status_code=status.HTTP_201_CREATED)
async def create_data_store(
    project_id: UUID,
    data: DataStoreCreate,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Create a new data store for the project."""
    try:
        return await service.create_store(project_id, data)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=list[DataStoreResponse])
async def list_data_stores(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """List all data stores for the project."""
    return await service.list_stores(project_id)


@router.get("/{store_id}", response_model=DataStoreResponse)
async def get_data_store(
    project_id: UUID,
    store_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Get a data store by ID."""
    try:
        return await service.get_store(store_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{store_id}", response_model=DataStoreResponse)
async def update_data_store(
    project_id: UUID,
    store_id: UUID,
    data: DataStoreUpdate,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Update a data store."""
    try:
        return await service.update_store(store_id, project_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_store(
    project_id: UUID,
    store_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Delete a data store and its underlying table."""
    try:
        await service.delete_store(store_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ── Row CRUD ───────────────────────────────────────────────────────

@router.get("/{store_id}/rows", response_model=DataStoreRowsResponse)
async def list_rows(
    project_id: UUID,
    store_id: UUID,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """List paginated rows from a data store."""
    try:
        return await service.get_rows(store_id, project_id, limit, offset)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{store_id}/rows", response_model=DataStoreRowResponse, status_code=status.HTTP_201_CREATED)
async def insert_row(
    project_id: UUID,
    store_id: UUID,
    data: dict,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Insert a single row into a data store."""
    try:
        return await service.insert_row(store_id, project_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{store_id}/rows/{row_id}", response_model=DataStoreRowResponse)
async def get_row(
    project_id: UUID,
    store_id: UUID,
    row_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Get a single row by ID."""
    try:
        return await service.get_row(store_id, project_id, row_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{store_id}/rows/{row_id}", response_model=DataStoreRowResponse)
async def update_row(
    project_id: UUID,
    store_id: UUID,
    row_id: UUID,
    data: dict,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Update a single row."""
    try:
        return await service.update_row(store_id, project_id, row_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{store_id}/rows/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_row(
    project_id: UUID,
    store_id: UUID,
    row_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Delete a single row."""
    try:
        await service.delete_row(store_id, project_id, row_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ── CSV Import ─────────────────────────────────────────────────────

@router.post("/{store_id}/import", response_model=CsvImportResponse)
async def import_csv(
    project_id: UUID,
    store_id: UUID,
    file: UploadFile = File(...),
    column_mapping: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Import rows from a CSV file.

    column_mapping is a JSON string: {"csv_header": "store_column", ...}
    """
    import json

    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )

    try:
        mapping = json.loads(column_mapping)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="column_mapping must be valid JSON"
        )

    content = await file.read()
    csv_text = content.decode("utf-8")

    try:
        return await service.import_csv(store_id, project_id, csv_text, mapping, filename=file.filename)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── Export Preview/Execute ────────────────────────────────────────

@router.post("/{store_id}/preview-export", response_model=ExportPreviewResponse)
async def preview_export(
    project_id: UUID,
    store_id: UUID,
    data: ExportPreviewRequest,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Preview export: validate mapping and return flattened rows without inserting."""
    try:
        return await service.preview_export(store_id, project_id, data.source_data, data.field_mapping)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{store_id}/execute-export", response_model=ExportExecuteResponse)
async def execute_export(
    project_id: UUID,
    store_id: UUID,
    data: ExportPreviewRequest,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Execute export: validate, flatten, and insert rows into the data store."""
    try:
        count = await service.execute_export(store_id, project_id, data.source_data, data.field_mapping)
        return ExportExecuteResponse(rows_imported=count)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
