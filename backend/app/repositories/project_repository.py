from uuid import UUID
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: UUID, data: ProjectCreate) -> Project:
        """Create a new project for the specified user."""
        project = Project(
            user_id=user_id,
            name=data.name,
            description=data.description,
            tags=data.tags
        )
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def get_by_id(self, project_id: UUID, user_id: UUID) -> Project | None:
        """Get a project by ID, scoped to the user."""
        result = await self.session.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, user_id: UUID, name: str) -> Project | None:
        """Get a project by name, scoped to the user."""
        result = await self.session.execute(
            select(Project).where(
                Project.user_id == user_id,
                Project.name == name
            )
        )
        return result.scalar_one_or_none()

    async def list_all(self, user_id: UUID, include_archived: bool = False) -> list[Project]:
        """List all projects for a user, optionally including archived."""
        query = select(Project).where(Project.user_id == user_id)

        if not include_archived:
            query = query.where(Project.is_archived == False)

        query = query.order_by(Project.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, project_id: UUID, user_id: UUID, data: ProjectUpdate) -> Project | None:
        """Update a project, scoped to the user."""
        project = await self.get_by_id(project_id, user_id)
        if not project:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(project, key, value)

        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def archive(self, project_id: UUID, user_id: UUID) -> Project | None:
        """Archive a project, scoped to the user."""
        project = await self.get_by_id(project_id, user_id)
        if not project:
            return None

        project.is_archived = True
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def unarchive(self, project_id: UUID, user_id: UUID) -> Project | None:
        """Unarchive a project, scoped to the user."""
        project = await self.get_by_id(project_id, user_id)
        if not project:
            return None

        project.is_archived = False
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def delete(self, project_id: UUID, user_id: UUID) -> bool:
        """Delete a project, scoped to the user. Returns True if deleted, False if not found."""
        result = await self.session.execute(
            delete(Project).where(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def get_default_project(self, user_id: UUID) -> Project | None:
        """Get user's default project."""
        result = await self.session.execute(
            select(Project).where(
                Project.user_id == user_id,
                Project.is_default == True
            )
        )
        return result.scalar_one_or_none()

    async def set_as_default(self, user_id: UUID, project_id: UUID) -> None:
        """Set a project as the user's default."""
        # Clear existing default
        await self.session.execute(
            update(Project)
            .where(Project.user_id == user_id)
            .values(is_default=False)
        )

        # Set new default
        await self.session.execute(
            update(Project)
            .where(
                Project.user_id == user_id,
                Project.id == project_id
            )
            .values(is_default=True)
        )
        await self.session.commit()
