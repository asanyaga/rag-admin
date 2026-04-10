"""Repository for agent config data access."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_config import AgentConfig


class AgentConfigRepository:
    """Repository for agent config data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        project_id: UUID,
        agent_type: str,
        created_by: UUID,
        config: dict | None = None,
    ) -> AgentConfig:
        agent_config = AgentConfig(
            project_id=project_id,
            agent_type=agent_type,
            config=config,
            created_by=created_by,
        )
        self.session.add(agent_config)
        await self.session.commit()
        await self.session.refresh(agent_config)
        return agent_config

    async def get_by_id(self, config_id: UUID) -> AgentConfig | None:
        result = await self.session.execute(
            select(AgentConfig).where(AgentConfig.id == config_id)
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: UUID) -> list[AgentConfig]:
        result = await self.session.execute(
            select(AgentConfig)
            .where(AgentConfig.project_id == project_id)
            .order_by(AgentConfig.created_at)
        )
        return list(result.scalars().all())

    async def get_by_project_and_type(
        self, project_id: UUID, agent_type: str
    ) -> AgentConfig | None:
        result = await self.session.execute(
            select(AgentConfig)
            .where(AgentConfig.project_id == project_id)
            .where(AgentConfig.agent_type == agent_type)
        )
        return result.scalar_one_or_none()

    async def update_enabled(
        self, config_id: UUID, enabled: bool
    ) -> AgentConfig | None:
        config = await self.get_by_id(config_id)
        if not config:
            return None
        config.enabled = enabled
        await self.session.commit()
        await self.session.refresh(config)
        return config

    async def delete(self, config_id: UUID) -> bool:
        config = await self.get_by_id(config_id)
        if not config:
            return False
        await self.session.delete(config)
        await self.session.commit()
        return True
