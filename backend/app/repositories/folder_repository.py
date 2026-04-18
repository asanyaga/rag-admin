from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder
from app.models.document import Document
from app.models.project import Project
from app.schemas.folder import FolderCreate, FolderUpdate


class FolderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, project_id: UUID, user_id: UUID, data: FolderCreate) -> Folder:
        folder = Folder(
            project_id=project_id,
            created_by=user_id,
            name=data.name,
            description=data.description,
            tags=data.tags,
        )
        self.session.add(folder)
        await self.session.commit()
        await self.session.refresh(folder)
        return folder

    async def get_by_id(self, folder_id: UUID, user_id: UUID) -> Folder | None:
        result = await self.session.execute(
            select(Folder)
            .join(Folder.project)
            .where(
                and_(
                    Folder.id == folder_id,
                    Project.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: UUID, user_id: UUID) -> list[tuple[Folder, int]]:
        """Return (Folder, document_count) tuples ordered by name."""
        result = await self.session.execute(
            select(Folder, func.count(Document.id).label("document_count"))
            .join(Folder.project)
            .outerjoin(Document, Document.folder_id == Folder.id)
            .where(
                and_(
                    Folder.project_id == project_id,
                    Project.user_id == user_id,
                )
            )
            .group_by(Folder.id)
            .order_by(Folder.name)
        )
        return list(result.all())

    async def update(self, folder_id: UUID, user_id: UUID, data: FolderUpdate) -> Folder | None:
        folder = await self.get_by_id(folder_id, user_id)
        if not folder:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(folder, key, value)
        await self.session.commit()
        await self.session.refresh(folder)
        return folder

    async def delete(self, folder_id: UUID, user_id: UUID) -> bool:
        folder = await self.get_by_id(folder_id, user_id)
        if not folder:
            return False
        await self.session.delete(folder)
        await self.session.commit()
        return True
