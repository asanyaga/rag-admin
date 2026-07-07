"""Repository for parser evaluation data access (canonical model)."""
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parser_eval import (
    ParserEvalCase, ParserEvalDataset, ParserEvalDatasetCase,
    ParserEvalRun, ParserEvalResult, ParserEvalDimension,
    ParserEvalSourceMethod, ParserEvalReviewStatus, ParserEvalRunStatus,
)


class ParserEvalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- cases ---
    async def create_case(self, project_id: UUID, source_document_id: UUID,
                          dimension: ParserEvalDimension, expected: dict, user_id: UUID,
                          source_method: ParserEvalSourceMethod = ParserEvalSourceMethod.human,
                          review_status: ParserEvalReviewStatus = ParserEvalReviewStatus.draft
                          ) -> ParserEvalCase:
        case = ParserEvalCase(project_id=project_id, source_document_id=source_document_id,
                              dimension=dimension, expected=expected, created_by=user_id,
                              source_method=source_method, review_status=review_status)
        self.session.add(case)
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def get_case(self, case_id: UUID) -> ParserEvalCase | None:
        res = await self.session.execute(
            select(ParserEvalCase).where(ParserEvalCase.id == case_id))
        return res.scalar_one_or_none()

    async def list_cases(self, project_id: UUID) -> list[ParserEvalCase]:
        res = await self.session.execute(
            select(ParserEvalCase).where(ParserEvalCase.project_id == project_id)
            .order_by(ParserEvalCase.created_at.desc()))
        return list(res.scalars().all())

    async def get_cases_by_ids(self, ids: list[UUID]) -> list[ParserEvalCase]:
        if not ids:
            return []
        res = await self.session.execute(
            select(ParserEvalCase).where(ParserEvalCase.id.in_(ids)))
        return list(res.scalars().all())

    async def get_case_by_doc_dimension(self, source_document_id: UUID,
                                        dimension: ParserEvalDimension) -> ParserEvalCase | None:
        res = await self.session.execute(
            select(ParserEvalCase).where(
                ParserEvalCase.source_document_id == source_document_id,
                ParserEvalCase.dimension == dimension))
        return res.scalar_one_or_none()

    async def update_case_review_status(self, case_id: UUID,
                                        review_status: ParserEvalReviewStatus
                                        ) -> ParserEvalCase | None:
        case = await self.get_case(case_id)
        if case is None:
            return None
        case.review_status = review_status
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def delete_case(self, case_id: UUID) -> bool:
        case = await self.get_case(case_id)
        if case is None:
            return False
        await self.session.delete(case)
        await self.session.commit()
        return True

    # --- datasets ---
    async def create_dataset(self, project_id: UUID, name: str, description: str | None,
                             user_id: UUID) -> ParserEvalDataset:
        ds = ParserEvalDataset(project_id=project_id, name=name, description=description,
                               created_by=user_id)
        self.session.add(ds)
        await self.session.commit()
        await self.session.refresh(ds)
        return ds

    async def get_dataset(self, dataset_id: UUID) -> ParserEvalDataset | None:
        res = await self.session.execute(
            select(ParserEvalDataset).where(ParserEvalDataset.id == dataset_id))
        return res.scalar_one_or_none()

    async def list_datasets(self, project_id: UUID) -> list[ParserEvalDataset]:
        res = await self.session.execute(
            select(ParserEvalDataset).where(ParserEvalDataset.project_id == project_id)
            .order_by(ParserEvalDataset.created_at.desc()))
        return list(res.scalars().all())

    async def add_case_to_dataset(self, dataset_id: UUID, eval_case_id: UUID) -> None:
        exists = await self.session.execute(
            select(ParserEvalDatasetCase).where(
                ParserEvalDatasetCase.dataset_id == dataset_id,
                ParserEvalDatasetCase.eval_case_id == eval_case_id))
        if exists.scalar_one_or_none() is None:
            self.session.add(ParserEvalDatasetCase(dataset_id=dataset_id, eval_case_id=eval_case_id))
            await self.session.commit()

    async def remove_case_from_dataset(self, dataset_id: UUID, eval_case_id: UUID) -> None:
        await self.session.execute(
            delete(ParserEvalDatasetCase).where(
                ParserEvalDatasetCase.dataset_id == dataset_id,
                ParserEvalDatasetCase.eval_case_id == eval_case_id))
        await self.session.commit()

    async def list_dataset_case_ids(self, dataset_id: UUID) -> list[UUID]:
        res = await self.session.execute(
            select(ParserEvalDatasetCase.eval_case_id)
            .where(ParserEvalDatasetCase.dataset_id == dataset_id))
        return list(res.scalars().all())

    # --- runs / results ---
    async def create_run(self, project_id: UUID, name: str, variants: list[dict],
                         eval_case_ids: list[str], user_id: UUID,
                         dataset_id: UUID | None = None) -> ParserEvalRun:
        run = ParserEvalRun(project_id=project_id, name=name, variants=variants,
                            eval_case_ids=eval_case_ids, dataset_id=dataset_id, created_by=user_id)
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

    async def insert_result(self, run_id: UUID, eval_case_id: UUID, adapter: str, config: dict,
                            variant_key: str, metrics: dict, primary_metric: str | None,
                            details: dict | None, cost: dict, latency_ms: int | None) -> None:
        # Append-only: Results are immutable facts (a probabilistic variant may produce a
        # different output each execution). The unique (run_id, eval_case_id, variant_key)
        # constraint is a safety net; retry = a new run. Variance sampling within one run
        # (a trial_index axis) is a deferred seam.
        self.session.add(ParserEvalResult(
            run_id=run_id, eval_case_id=eval_case_id, adapter=adapter, config=config,
            variant_key=variant_key, metrics=metrics, primary_metric=primary_metric,
            details=details, cost=cost, latency_ms=latency_ms))
        await self.session.commit()

    async def get_results(self, run_id: UUID) -> list[ParserEvalResult]:
        res = await self.session.execute(
            select(ParserEvalResult).where(ParserEvalResult.run_id == run_id)
            .order_by(ParserEvalResult.eval_case_id, ParserEvalResult.variant_key))
        return list(res.scalars().all())
