"""Repository for extraction evaluation run data access."""
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.extraction_eval import (
    ExtractionEvalRun,
    ExtractionEvalRunStatus,
    ExtractionEvalResult,
)
from app.models.extraction_ground_truth import ExtractionGroundTruthItem


class ExtractionEvalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # EvalRun CRUD
    # ------------------------------------------------------------------

    async def create_run(
        self,
        project_id: UUID,
        ground_truth_set_id: UUID,
        name: str,
        config: dict,
        user_id: UUID,
        items_total: int = 0,
    ) -> ExtractionEvalRun:
        run = ExtractionEvalRun(
            project_id=project_id,
            ground_truth_set_id=ground_truth_set_id,
            name=name,
            config=config,
            created_by=user_id,
            items_total=items_total,
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get_run_by_id(self, run_id: UUID) -> ExtractionEvalRun | None:
        result = await self.session.execute(
            select(ExtractionEvalRun)
            .options(selectinload(ExtractionEvalRun.ground_truth_set))
            .where(ExtractionEvalRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_runs_by_project(
        self,
        project_id: UUID,
        ground_truth_set_id: UUID | None = None,
    ) -> list[ExtractionEvalRun]:
        query = (
            select(ExtractionEvalRun)
            .options(selectinload(ExtractionEvalRun.ground_truth_set))
            .where(ExtractionEvalRun.project_id == project_id)
        )
        if ground_truth_set_id:
            query = query.where(
                ExtractionEvalRun.ground_truth_set_id == ground_truth_set_id
            )
        query = query.order_by(ExtractionEvalRun.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete_run(self, run_id: UUID) -> bool:
        result = await self.session.execute(
            delete(ExtractionEvalRun).where(ExtractionEvalRun.id == run_id)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def update_status(
        self,
        run_id: UUID,
        status: ExtractionEvalRunStatus,
        error_message: str | None = None,
    ) -> None:
        result = await self.session.execute(
            select(ExtractionEvalRun).where(ExtractionEvalRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            return
        run.status = status
        if error_message is not None:
            run.error_message = error_message
        await self.session.commit()

    async def update_progress(self, run_id: UUID, items_completed: int) -> None:
        result = await self.session.execute(
            select(ExtractionEvalRun).where(ExtractionEvalRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if run:
            run.items_completed = items_completed
            await self.session.commit()

    async def update_metrics(self, run_id: UUID, metrics: dict) -> None:
        result = await self.session.execute(
            select(ExtractionEvalRun).where(ExtractionEvalRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if run:
            run.metrics = metrics
            run.status = ExtractionEvalRunStatus.completed
            await self.session.commit()

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    async def create_result(
        self,
        eval_run_id: UUID,
        extraction_result_id: UUID,
        ground_truth_item_id: UUID,
        overall_score: float,
        field_scores: dict,
        line_items_score: dict | None = None,
        evaluation_metadata: dict | None = None,
    ) -> ExtractionEvalResult:
        result = ExtractionEvalResult(
            eval_run_id=eval_run_id,
            extraction_result_id=extraction_result_id,
            ground_truth_item_id=ground_truth_item_id,
            overall_score=overall_score,
            field_scores=field_scores,
            line_items_score=line_items_score,
            evaluation_metadata=evaluation_metadata,
        )
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def get_results_by_run(self, run_id: UUID) -> list[ExtractionEvalResult]:
        result = await self.session.execute(
            select(ExtractionEvalResult)
            .options(
                selectinload(ExtractionEvalResult.ground_truth_item)
                .selectinload(ExtractionGroundTruthItem.document),
                selectinload(ExtractionEvalResult.extraction_result),
            )
            .where(ExtractionEvalResult.eval_run_id == run_id)
            .order_by(ExtractionEvalResult.overall_score.asc())
        )
        return list(result.scalars().all())

    async def get_result_by_id(self, result_id: UUID) -> ExtractionEvalResult | None:
        result = await self.session.execute(
            select(ExtractionEvalResult)
            .options(
                selectinload(ExtractionEvalResult.ground_truth_item)
                .selectinload(ExtractionGroundTruthItem.document),
                selectinload(ExtractionEvalResult.extraction_result),
            )
            .where(ExtractionEvalResult.id == result_id)
        )
        return result.scalar_one_or_none()
