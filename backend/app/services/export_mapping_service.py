# backend/app/services/export_mapping_service.py
from uuid import UUID

from app.repositories.export_mapping_repository import ExportMappingRepository
from app.schemas.export_mapping import (
    ExportMappingCreate,
    ExportMappingResponse,
    ExportMappingUpdate,
)
from app.services.exceptions import ConflictError, NotFoundError


class ExportMappingService:
    def __init__(self, repo: ExportMappingRepository):
        self.repo = repo

    async def list_by_store(
        self, project_id: UUID, data_store_id: UUID
    ) -> list[ExportMappingResponse]:
        mappings = await self.repo.list_by_store(project_id, data_store_id)
        return [ExportMappingResponse.model_validate(m) for m in mappings]

    async def create(
        self, project_id: UUID, data: ExportMappingCreate
    ) -> ExportMappingResponse:
        if await self.repo.name_exists(project_id, data.data_store_id, data.name):
            raise ConflictError(f"A mapping named '{data.name}' already exists for this data store.")
        mapping = await self.repo.create(project_id, data)
        return ExportMappingResponse.model_validate(mapping)

    async def update(
        self, mapping_id: UUID, project_id: UUID, data: ExportMappingUpdate
    ) -> ExportMappingResponse:
        mapping = await self.repo.get_by_id(mapping_id, project_id)
        if not mapping:
            raise NotFoundError(f"Export mapping {mapping_id} not found.")
        if data.name and data.name != mapping.name:
            if await self.repo.name_exists(
                project_id, mapping.data_store_id, data.name, exclude_id=mapping_id
            ):
                raise ConflictError(f"A mapping named '{data.name}' already exists for this data store.")
        updated = await self.repo.update(mapping, data)
        return ExportMappingResponse.model_validate(updated)

    async def delete(self, mapping_id: UUID, project_id: UUID) -> None:
        deleted = await self.repo.delete(mapping_id, project_id)
        if not deleted:
            raise NotFoundError(f"Export mapping {mapping_id} not found.")
