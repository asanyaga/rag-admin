# backend/app/repositories/parse_agent_run_repository.py
"""Repository for parse-agent runs and their append-only trace steps."""
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_agent_run import ParseAgentRun, ParseAgentRunStatus, ParseAgentRunStep


@dataclass
class StepCreate:
    run_id: UUID
    seq: int
    node: str
    phase: str
    status: str
    input_keys: list[str]
    output_keys: list[str]
    state_delta: dict
    message: str | None = None
    duration_ms: int | None = None


class ParseAgentRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_run(
        self, *, project_id: UUID, source_document_id: UUID, started_at: datetime,
    ) -> ParseAgentRun:
        run = ParseAgentRun(
            project_id=project_id,
            source_document_id=source_document_id,
            status=ParseAgentRunStatus.running.value,
            started_at=started_at,
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def append_step(self, dto: StepCreate) -> ParseAgentRunStep:
        step = ParseAgentRunStep(
            run_id=dto.run_id, seq=dto.seq, node=dto.node, phase=dto.phase,
            status=dto.status, input_keys=dto.input_keys, output_keys=dto.output_keys,
            state_delta=dto.state_delta, message=dto.message, duration_ms=dto.duration_ms,
        )
        self.session.add(step)
        await self.session.commit()
        await self.session.refresh(step)
        return step

    async def finish_run(
        self, run_id: UUID, *, status: str, finished_at: datetime, error: str | None = None,
    ) -> None:
        run = await self.get_run(run_id)
        if run is None:
            raise ValueError(f"ParseAgentRun {run_id} not found")
        run.status = status
        run.finished_at = finished_at
        if error is not None:
            run.error = error
        await self.session.commit()

    async def get_run(self, run_id: UUID) -> ParseAgentRun | None:
        result = await self.session.execute(
            select(ParseAgentRun).where(ParseAgentRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_steps(self, run_id: UUID) -> list[ParseAgentRunStep]:
        result = await self.session.execute(
            select(ParseAgentRunStep)
            .where(ParseAgentRunStep.run_id == run_id)
            .order_by(ParseAgentRunStep.seq)
        )
        return list(result.scalars().all())
