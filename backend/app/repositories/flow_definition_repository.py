"""Repository for flow definition data access."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flow_definition import FlowDefinition


class FlowDefinitionRepository:
    """Repository for flow definition CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        project_id: UUID,
        name: str,
        definition: dict,
        created_by: UUID,
        description: str | None = None,
    ) -> FlowDefinition:
        """Create a new flow definition."""
        obj = FlowDefinition(
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

    async def get_by_id(self, flow_id: UUID) -> FlowDefinition | None:
        """Get a flow definition by ID."""
        result = await self.session.execute(
            select(FlowDefinition).where(FlowDefinition.id == flow_id)
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: UUID) -> list[FlowDefinition]:
        """List flow definitions for a project."""
        result = await self.session.execute(
            select(FlowDefinition)
            .where(FlowDefinition.project_id == project_id)
            .order_by(FlowDefinition.created_at)
        )
        return list(result.scalars().all())

    async def update(
        self,
        flow_id: UUID,
        name: str | None = None,
        description: str | None = None,
        definition: dict | None = None,
    ) -> FlowDefinition | None:
        """Update a flow definition. Only provided fields are changed."""
        flow = await self.get_by_id(flow_id)
        if not flow:
            return None
        if name is not None:
            flow.name = name
        if description is not None:
            flow.description = description
        if definition is not None:
            flow.definition = definition
        await self.session.commit()
        await self.session.refresh(flow)
        return flow

    async def delete(self, flow_id: UUID) -> bool:
        """Delete a flow definition."""
        flow = await self.get_by_id(flow_id)
        if not flow:
            return False
        await self.session.delete(flow)
        await self.session.commit()
        return True
