"""Repository for evaluation run data access."""
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import EvalRun, EvalRunStatus, EvalRunResult


class EvalRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # EvalRun CRUD
    # ------------------------------------------------------------------

    async def create(
        self,
        project_id: UUID,
        golden_set_id: UUID,
        index_id: UUID,
        name: str,
        config: dict,
        user_id: UUID,
        mode: str = "retrieval_only",
        generation_config: dict | None = None,
        judge_config: dict | None = None,
        experiment_id: UUID | None = None,
        variant_label: str | None = None,
    ) -> EvalRun:
        run = EvalRun(
            project_id=project_id,
            golden_set_id=golden_set_id,
            index_id=index_id,
            name=name,
            config=config,
            created_by=user_id,
            mode=mode,
            generation_config=generation_config,
            judge_config=judge_config,
            experiment_id=experiment_id,
            variant_label=variant_label,
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get_by_id(self, run_id: UUID, project_id: UUID) -> EvalRun | None:
        result = await self.session.execute(
            select(EvalRun)
            .options(
                selectinload(EvalRun.golden_set),
                selectinload(EvalRun.index),
                selectinload(EvalRun.experiment),
            )
            .where(
                EvalRun.id == run_id,
                EvalRun.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: UUID) -> list[EvalRun]:
        result = await self.session.execute(
            select(EvalRun)
            .options(
                selectinload(EvalRun.golden_set),
                selectinload(EvalRun.index),
                selectinload(EvalRun.experiment),
            )
            .where(EvalRun.project_id == project_id)
            .order_by(EvalRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete(self, run_id: UUID, project_id: UUID) -> bool:
        result = await self.session.execute(
            delete(EvalRun).where(
                EvalRun.id == run_id,
                EvalRun.project_id == project_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def update_status(
        self,
        run_id: UUID,
        status: EvalRunStatus,
        error_message: str | None = None,
    ) -> EvalRun | None:
        result = await self.session.execute(
            select(EvalRun).where(EvalRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            return None
        run.status = status
        run.error_message = error_message
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def update_metrics(self, run_id: UUID, metrics: dict) -> EvalRun | None:
        result = await self.session.execute(
            select(EvalRun).where(EvalRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            return None
        run.metrics = metrics
        run.status = EvalRunStatus.completed
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def update_progress(
        self,
        run_id: UUID,
        items_completed: int,
        failed_item_count: int = 0,
    ) -> None:
        """Update progress counters for a running eval run."""
        result = await self.session.execute(
            select(EvalRun).where(EvalRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if run:
            run.items_completed = items_completed
            run.failed_item_count = failed_item_count
            await self.session.commit()

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    async def create_result(
        self,
        eval_run_id: UUID,
        query_id: UUID,
        precision: float,
        recall: float,
        f1: float,
        retrieved_chunks: list[dict],
        generated_answer: str | None = None,
        faithfulness_score: float | None = None,
        relevance_score: float | None = None,
        claim_breakdown: list[dict] | None = None,
        judge_error: str | None = None,
        generation_error: str | None = None,
        trace_data: dict | None = None,
    ) -> EvalRunResult:
        result = EvalRunResult(
            eval_run_id=eval_run_id,
            query_id=query_id,
            precision=precision,
            recall=recall,
            f1=f1,
            retrieved_chunks=retrieved_chunks,
            generated_answer=generated_answer,
            faithfulness_score=faithfulness_score,
            relevance_score=relevance_score,
            claim_breakdown=claim_breakdown,
            judge_error=judge_error,
            generation_error=generation_error,
            trace_data=trace_data,
        )
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def get_results(
        self,
        eval_run_id: UUID,
        filter_type: str | None = None,
    ) -> list[EvalRunResult]:
        query = (
            select(EvalRunResult)
            .options(selectinload(EvalRunResult.query))
            .where(EvalRunResult.eval_run_id == eval_run_id)
        )

        if filter_type == "low_faithfulness":
            query = query.where(
                EvalRunResult.faithfulness_score.isnot(None),
                EvalRunResult.faithfulness_score < 0.5,
            )
        elif filter_type == "low_relevance":
            query = query.where(
                EvalRunResult.relevance_score.isnot(None),
                EvalRunResult.relevance_score < 0.5,
            )
        elif filter_type == "retrieval_miss":
            query = query.where(EvalRunResult.recall < 0.5)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_for_comparison(
        self,
        run_id_1: UUID,
        run_id_2: UUID,
        project_id: UUID,
    ) -> tuple[EvalRun | None, EvalRun | None]:
        """Load two runs with their results for comparison."""
        run1 = await self.session.execute(
            select(EvalRun)
            .options(
                selectinload(EvalRun.results).selectinload(EvalRunResult.query),
                selectinload(EvalRun.golden_set),
                selectinload(EvalRun.index),
                selectinload(EvalRun.experiment),
            )
            .where(EvalRun.id == run_id_1, EvalRun.project_id == project_id)
        )
        run2 = await self.session.execute(
            select(EvalRun)
            .options(
                selectinload(EvalRun.results).selectinload(EvalRunResult.query),
                selectinload(EvalRun.golden_set),
                selectinload(EvalRun.index),
                selectinload(EvalRun.experiment),
            )
            .where(EvalRun.id == run_id_2, EvalRun.project_id == project_id)
        )
        return run1.scalar_one_or_none(), run2.scalar_one_or_none()
