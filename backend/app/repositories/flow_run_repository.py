"""Repository for flow run data access."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flow_run import FlowRun, FlowRunStatus


class FlowRunRepository:
    """Repository for flow run CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        project_id: UUID,
        flow_definition_id: UUID,
        created_by: UUID,
        initial_state: dict | None = None,
    ) -> FlowRun:
        """Create a new flow run."""
        obj = FlowRun(
            project_id=project_id,
            flow_definition_id=flow_definition_id,
            initial_state=initial_state,
            created_by=created_by,
        )
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def get_by_id(self, run_id: UUID) -> FlowRun | None:
        """Get a flow run by ID."""
        result = await self.session.execute(
            select(FlowRun).where(FlowRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: UUID) -> list[FlowRun]:
        """List flow runs for a project."""
        result = await self.session.execute(
            select(FlowRun)
            .where(FlowRun.project_id == project_id)
            .order_by(FlowRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_flow(self, flow_definition_id: UUID) -> list[FlowRun]:
        """List flow runs for a specific flow definition."""
        result = await self.session.execute(
            select(FlowRun)
            .where(FlowRun.flow_definition_id == flow_definition_id)
            .order_by(FlowRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        run_id: UUID,
        status: FlowRunStatus,
        status_message: str | None = None,
    ) -> FlowRun | None:
        """Update run status and optional message."""
        run = await self.get_by_id(run_id)
        if not run:
            return None
        run.status = status
        if status_message is not None:
            run.status_message = status_message
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def update_state(
        self,
        run_id: UUID,
        current_state: dict | None,
        current_node: str | None,
        status: FlowRunStatus,
        thread_id: str | None = None,
        status_message: str | None = None,
    ) -> FlowRun | None:
        """Update run state after graph invocation."""
        run = await self.get_by_id(run_id)
        if not run:
            return None
        run.current_state = current_state
        run.current_node = current_node
        run.status = status
        if thread_id is not None:
            run.thread_id = thread_id
        if status_message is not None:
            run.status_message = status_message
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def delete(self, run_id: UUID) -> bool:
        """Delete a flow run."""
        run = await self.get_by_id(run_id)
        if not run:
            return False
        await self.session.delete(run)
        await self.session.commit()
        return True
