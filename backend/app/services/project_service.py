from uuid import UUID
from sqlalchemy.exc import IntegrityError

from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.services.exceptions import ConflictError, NotFoundError, ValidationError


class ProjectService:
    def __init__(self, project_repo: ProjectRepository):
        self.project_repo = project_repo

    async def create_project(self, user_id: UUID, data: ProjectCreate) -> ProjectResponse:
        """
        Create a new project for the user.

        Raises:
        - ConflictError: Project name already exists for this user
        """
        try:
            project = await self.project_repo.create(user_id, data)
            return ProjectResponse.model_validate(project)
        except IntegrityError as e:
            error_str = str(e).lower()
            if 'uq_projects_user_name' in error_str or \
               ('projects.user_id' in error_str and 'projects.name' in error_str):
                raise ConflictError(f"Project with name '{data.name}' already exists")
            raise

    async def get_project(self, project_id: UUID, user_id: UUID) -> ProjectResponse:
        """
        Get a project by ID.

        Raises:
        - NotFoundError: Project not found or doesn't belong to user
        """
        project = await self.project_repo.get_by_id(project_id, user_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found")
        return ProjectResponse.model_validate(project)

    async def list_projects(self, user_id: UUID, include_archived: bool = False) -> list[ProjectResponse]:
        """List all projects for the user."""
        projects = await self.project_repo.list_all(user_id, include_archived)
        return [ProjectResponse.model_validate(p) for p in projects]

    async def get_default_project(self, user_id: UUID) -> ProjectResponse:
        """
        Get the user's default project.

        Raises:
        - NotFoundError: No default project found
        """
        project = await self.project_repo.get_default_project(user_id)
        if not project:
            raise NotFoundError("No default project found")
        return ProjectResponse.model_validate(project)

    async def update_project(
        self,
        project_id: UUID,
        user_id: UUID,
        data: ProjectUpdate
    ) -> ProjectResponse:
        """
        Update a project.

        Raises:
        - NotFoundError: Project not found or doesn't belong to user
        - ConflictError: New name conflicts with existing project
        """
        # Check if project exists
        existing = await self.project_repo.get_by_id(project_id, user_id)
        if not existing:
            raise NotFoundError(f"Project {project_id} not found")

        # If updating name, check for conflicts
        if data.name and data.name != existing.name:
            conflicting = await self.project_repo.get_by_name(user_id, data.name)
            if conflicting:
                raise ConflictError(f"Project with name '{data.name}' already exists")

        try:
            project = await self.project_repo.update(project_id, user_id, data)
            if not project:
                raise NotFoundError(f"Project {project_id} not found")
            return ProjectResponse.model_validate(project)
        except IntegrityError as e:
            error_str = str(e).lower()
            if 'uq_projects_user_name' in error_str or \
               ('projects.user_id' in error_str and 'projects.name' in error_str):
                raise ConflictError(f"Project with name '{data.name}' already exists")
            raise

    async def archive_project(self, project_id: UUID, user_id: UUID) -> ProjectResponse:
        """
        Archive a project.

        Raises:
        - NotFoundError: Project not found or doesn't belong to user
        """
        project = await self.project_repo.archive(project_id, user_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found")
        return ProjectResponse.model_validate(project)

    async def unarchive_project(self, project_id: UUID, user_id: UUID) -> ProjectResponse:
        """
        Unarchive a project.

        Raises:
        - NotFoundError: Project not found or doesn't belong to user
        """
        project = await self.project_repo.unarchive(project_id, user_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found")
        return ProjectResponse.model_validate(project)

    async def delete_project(self, project_id: UUID, user_id: UUID) -> None:
        """
        Delete a project permanently.

        Business Rules:
        - Project must be archived first
        - Project must have no related documents (future-proof)

        Raises:
        - NotFoundError: Project not found or doesn't belong to user
        - ValidationError: Project is not archived or has related documents
        """
        # Check if project exists and get its state
        project = await self.project_repo.get_by_id(project_id, user_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found")

        # Enforce archive-before-delete rule
        if not project.is_archived:
            raise ValidationError("Project must be archived before it can be deleted")

        # Future-proof: Check for related documents
        # When documents are implemented, add this check:
        # document_count = await self.document_repo.count_by_project(project_id)
        # if document_count > 0:
        #     raise ValidationError("Cannot delete project with related documents")

        # Delete the project
        deleted = await self.project_repo.delete(project_id, user_id)
        if not deleted:
            raise NotFoundError(f"Project {project_id} not found")
