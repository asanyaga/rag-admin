# backend/app/repositories/export_mapping_repository.py
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.export_mapping import ExportMapping
from app.schemas.export_mapping import ExportMappingCreate, ExportMappingUpdate


class ExportMappingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_store(
        self, project_id: UUID, data_store_id: UUID
    ) -> list[ExportMapping]:
        result = await self.session.execute(
            select(ExportMapping)
            .where(
                ExportMapping.project_id == project_id,
                ExportMapping.data_store_id == data_store_id,
            )
            .order_by(ExportMapping.name)
        )
        return list(result.scalars().all())

    async def get_by_id(
        self, mapping_id: UUID, project_id: UUID
    ) -> ExportMapping | None:
        result = await self.session.execute(
            select(ExportMapping).where(
                ExportMapping.id == mapping_id,
                ExportMapping.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()

    async def name_exists(
        self, project_id: UUID, data_store_id: UUID, name: str, exclude_id: UUID | None = None
    ) -> bool:
        q = select(ExportMapping).where(
            ExportMapping.project_id == project_id,
            ExportMapping.data_store_id == data_store_id,
            ExportMapping.name == name,
        )
        if exclude_id:
            q = q.where(ExportMapping.id != exclude_id)
        result = await self.session.execute(q)
        return result.scalar_one_or_none() is not None

    async def create(
        self, project_id: UUID, data: ExportMappingCreate
    ) -> ExportMapping:
        mapping = ExportMapping(
            project_id=project_id,
            data_store_id=data.data_store_id,
            name=data.name,
            field_mapping=data.field_mapping,
        )
        self.session.add(mapping)
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping

    async def update(
        self, mapping: ExportMapping, data: ExportMappingUpdate
    ) -> ExportMapping:
        if data.name is not None:
            mapping.name = data.name
        if data.field_mapping is not None:
            mapping.field_mapping = data.field_mapping
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping

    async def delete(self, mapping_id: UUID, project_id: UUID) -> bool:
        result = await self.session.execute(
            delete(ExportMapping).where(
                ExportMapping.id == mapping_id,
                ExportMapping.project_id == project_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0
