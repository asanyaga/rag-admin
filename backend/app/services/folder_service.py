from uuid import UUID

from app.repositories.folder_repository import FolderRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.folder import FolderCreate, FolderUpdate, FolderResponse
from app.services.exceptions import NotFoundError


class FolderService:
    def __init__(self, folder_repo: FolderRepository, project_repo: ProjectRepository):
        self.folder_repo = folder_repo
        self.project_repo = project_repo

    async def create_folder(
        self, user_id: UUID, project_id: UUID, data: FolderCreate
    ) -> FolderResponse:
        project = await self.project_repo.get_by_id(project_id, user_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found")
        folder = await self.folder_repo.create(project_id, user_id, data)
        return FolderResponse.model_validate({**folder.__dict__, "document_count": 0})

    async def list_folders(self, user_id: UUID, project_id: UUID) -> list[FolderResponse]:
        rows = await self.folder_repo.list_by_project(project_id, user_id)
        results = []
        for folder, count in rows:
            data = {**folder.__dict__, "document_count": count}
            results.append(FolderResponse.model_validate(data))
        return results

    async def update_folder(
        self, folder_id: UUID, user_id: UUID, data: FolderUpdate
    ) -> FolderResponse:
        folder = await self.folder_repo.update(folder_id, user_id, data)
        if not folder:
            raise NotFoundError(f"Folder {folder_id} not found")
        return FolderResponse.model_validate({**folder.__dict__, "document_count": 0})

    async def delete_folder(self, folder_id: UUID, user_id: UUID) -> None:
        deleted = await self.folder_repo.delete(folder_id, user_id)
        if not deleted:
            raise NotFoundError(f"Folder {folder_id} not found")
