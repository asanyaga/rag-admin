"""Repository for agent definition data access."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_definition import AgentDefinition


class AgentDefinitionRepository:
    """Repository for agent definition CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        project_id: UUID,
        name: str,
        definition: dict,
        created_by: UUID,
        description: str | None = None,
    ) -> AgentDefinition:
        """Create a new agent definition."""
        obj = AgentDefinition(
            project_id=project_id,
            name=name,
            description=description,
            definition=definition,
            created_by=created_by,
        )
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def get_by_id(self, agent_id: UUID) -> AgentDefinition | None:
        """Get an agent definition by ID."""
        result = await self.session.execute(
            select(AgentDefinition).where(AgentDefinition.id == agent_id)
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: UUID) -> list[AgentDefinition]:
        """List agent definitions for a project."""
        result = await self.session.execute(
            select(AgentDefinition)
            .where(AgentDefinition.project_id == project_id)
            .order_by(AgentDefinition.created_at)
        )
        return list(result.scalars().all())

    async def update(
        self,
        agent_id: UUID,
        name: str | None = None,
        description: str | None = None,
        definition: dict | None = None,
    ) -> AgentDefinition | None:
        """Update an agent definition. Only provided fields are changed."""
        agent = await self.get_by_id(agent_id)
        if not agent:
            return None
        if name is not None:
            agent.name = name
        if description is not None:
            agent.description = description
        if definition is not None:
            agent.definition = definition
        await self.session.commit()
        await self.session.refresh(agent)
        return agent

    async def delete(self, agent_id: UUID) -> bool:
        """Delete an agent definition."""
        agent = await self.get_by_id(agent_id)
        if not agent:
            return False
        await self.session.delete(agent)
        await self.session.commit()
        return True
