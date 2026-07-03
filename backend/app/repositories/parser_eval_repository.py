"""Repository for parser evaluation data access."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.parser_eval import (
    ParserEvalCase, ParserEvalTarget, ParserEvalRun, ParserEvalResult,
    ParserEvalDimension, ParserEvalRunStatus,
)


class ParserEvalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- cases / targets ---
    async def create_case(self, project_id: UUID, name: str, doc_type: str | None,
                          source_document_id: UUID, source_filename: str | None,
                          user_id: UUID) -> ParserEvalCase:
        case = ParserEvalCase(project_id=project_id, name=name, doc_type=doc_type,
                              source_document_id=source_document_id,
                              source_filename=source_filename, created_by=user_id)
        self.session.add(case)
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def add_target(self, case_id: UUID, dimension: ParserEvalDimension,
                         expected: dict) -> ParserEvalTarget:
        target = ParserEvalTarget(case_id=case_id, dimension=dimension, expected=expected)
        self.session.add(target)
        await self.session.commit()
        await self.session.refresh(target)
        return target

    async def get_case(self, case_id: UUID) -> ParserEvalCase | None:
        res = await self.session.execute(
            select(ParserEvalCase).options(selectinload(ParserEvalCase.targets))
            .where(ParserEvalCase.id == case_id))
        return res.scalar_one_or_none()

    async def list_cases(self, project_id: UUID) -> list[ParserEvalCase]:
        res = await self.session.execute(
            select(ParserEvalCase).options(selectinload(ParserEvalCase.targets))
            .where(ParserEvalCase.project_id == project_id)
            .order_by(ParserEvalCase.created_at.desc()))
        return list(res.scalars().all())

    # --- runs / results ---
    async def create_run(self, project_id: UUID, name: str, parsers: list[str],
                         case_ids: list[str], user_id: UUID) -> ParserEvalRun:
        run = ParserEvalRun(project_id=project_id, name=name, parsers=parsers,
                            case_ids=case_ids, created_by=user_id)
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get_run(self, run_id: UUID) -> ParserEvalRun | None:
        res = await self.session.execute(
            select(ParserEvalRun).where(ParserEvalRun.id == run_id))
        return res.scalar_one_or_none()

    async def list_runs(self, project_id: UUID) -> list[ParserEvalRun]:
        res = await self.session.execute(
            select(ParserEvalRun).where(ParserEvalRun.project_id == project_id)
            .order_by(ParserEvalRun.created_at.desc()))
        return list(res.scalars().all())

    async def set_run_status(self, run_id: UUID, status: ParserEvalRunStatus,
                             error_message: str | None = None) -> None:
        run = await self.get_run(run_id)
        if run is None:
            return
        run.status = status
        if error_message is not None:
            run.error_message = error_message
        await self.session.commit()

    async def upsert_result(self, run_id: UUID, case_id: UUID, parser: str,
                            dimension: ParserEvalDimension, score: float, details: dict,
                            cost: dict, latency_ms: int | None) -> None:
        res = await self.session.execute(
            select(ParserEvalResult).where(
                ParserEvalResult.run_id == run_id, ParserEvalResult.case_id == case_id,
                ParserEvalResult.parser == parser, ParserEvalResult.dimension == dimension))
        existing = res.scalar_one_or_none()
        if existing is None:
            self.session.add(ParserEvalResult(
                run_id=run_id, case_id=case_id, parser=parser, dimension=dimension,
                score=score, details=details, cost=cost, latency_ms=latency_ms))
        else:
            existing.score, existing.details = score, details
            existing.cost, existing.latency_ms = cost, latency_ms
        await self.session.commit()

    async def get_results(self, run_id: UUID) -> list[ParserEvalResult]:
        res = await self.session.execute(
            select(ParserEvalResult).where(ParserEvalResult.run_id == run_id)
            .order_by(ParserEvalResult.case_id, ParserEvalResult.parser))
        return list(res.scalars().all())
