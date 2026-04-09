"""Service for extraction evaluation run orchestration."""
import logging
import statistics
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_eval import ExtractionEvalRunStatus
from app.models.extraction_result import ExtractionResult, ExtractionResultStatus
from app.repositories.extraction_eval_repository import ExtractionEvalRepository
from app.repositories.extraction_ground_truth_repository import ExtractionGroundTruthRepository
from app.schemas.extraction_eval import (
    ExtractionEvalRunCreate,
    ExtractionEvalRunResponse,
    ExtractionEvalResultResponse,
)
from app.services.extraction_eval.engine import EvalConfig, score_document
from app.services.extraction.normaliser import normalise
from app.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class ExtractionEvalService:
    def __init__(
        self,
        eval_repo: ExtractionEvalRepository,
        gt_repo: ExtractionGroundTruthRepository,
        session: AsyncSession,
    ):
        self.eval_repo = eval_repo
        self.gt_repo = gt_repo
        self.session = session

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_run(
        self, project_id: UUID, user_id: UUID, data: ExtractionEvalRunCreate
    ) -> ExtractionEvalRunResponse:
        # Validate ground truth set exists
        gt_set = await self.gt_repo.get_set_with_items(data.ground_truth_set_id)
        if not gt_set:
            raise NotFoundError(f"Ground truth set {data.ground_truth_set_id} not found")

        items_total = len(gt_set.items) if gt_set.items else 0
        name = data.name or f"Eval: {gt_set.name}"
        config = data.config.model_dump(by_alias=True) if data.config else {}

        run = await self.eval_repo.create_run(
            project_id=project_id,
            ground_truth_set_id=data.ground_truth_set_id,
            name=name,
            config=config,
            user_id=user_id,
            items_total=items_total,
        )
        run = await self.eval_repo.get_run_by_id(run.id)
        return self._run_to_response(run)

    async def get_run(self, run_id: UUID) -> ExtractionEvalRunResponse:
        run = await self.eval_repo.get_run_by_id(run_id)
        if not run:
            raise NotFoundError(f"Extraction eval run {run_id} not found")
        return self._run_to_response(run)

    async def list_runs(
        self, project_id: UUID, ground_truth_set_id: UUID | None = None
    ) -> list[ExtractionEvalRunResponse]:
        runs = await self.eval_repo.list_runs_by_project(project_id, ground_truth_set_id)
        return [self._run_to_response(r) for r in runs]

    async def delete_run(self, run_id: UUID) -> None:
        deleted = await self.eval_repo.delete_run(run_id)
        if not deleted:
            raise NotFoundError(f"Extraction eval run {run_id} not found")

    async def get_results(self, run_id: UUID) -> list[ExtractionEvalResultResponse]:
        run = await self.eval_repo.get_run_by_id(run_id)
        if not run:
            raise NotFoundError(f"Extraction eval run {run_id} not found")

        results = await self.eval_repo.get_results_by_run(run_id)
        return [self._result_to_response(r) for r in results]

    async def get_result(self, result_id: UUID) -> ExtractionEvalResultResponse:
        result = await self.eval_repo.get_result_by_id(result_id)
        if not result:
            raise NotFoundError(f"Extraction eval result {result_id} not found")
        return self._result_to_response(result)

    # ------------------------------------------------------------------
    # Execution (background task)
    # ------------------------------------------------------------------

    async def execute_eval_run(self, run_id: UUID) -> None:
        """Execute an evaluation run (called from background task)."""
        try:
            await self.eval_repo.update_status(run_id, ExtractionEvalRunStatus.running)

            run = await self.eval_repo.get_run_by_id(run_id)
            if not run:
                return

            eval_config = EvalConfig.from_dict(run.config)

            # Load ground truth set with items
            gt_set = await self.gt_repo.get_set_with_items(run.ground_truth_set_id)
            if not gt_set or not gt_set.items:
                await self.eval_repo.update_status(
                    run_id, ExtractionEvalRunStatus.failed,
                    error_message="Ground truth set has no items",
                )
                return

            extraction_schema_id = gt_set.extraction_schema_id
            overall_scores = []
            field_accuracy: dict[str, list[float]] = {}
            line_items_f1s = []
            perfect_count = 0
            items_completed = 0

            for gt_item in gt_set.items:
                # Find the most recent completed extraction result for this document + schema
                extraction_result = await self._find_extraction_result(
                    gt_item.document_id, extraction_schema_id
                )

                if not extraction_result:
                    logger.warning(
                        f"No extraction result for document {gt_item.document_id}, skipping"
                    )
                    items_completed += 1
                    await self.eval_repo.update_progress(run_id, items_completed)
                    continue

                # Normalise predicted data into canonical form
                predicted = normalise(
                    structured_data=extraction_result.structured_data,
                    extraction_method=extraction_result.extraction_method,
                    schema_definition=extraction_result.schema_definition_snapshot,
                )
                expected = gt_item.expected_data or {}

                # Score the document
                doc_score = score_document(predicted, expected, eval_config)

                # Save result
                await self.eval_repo.create_result(
                    eval_run_id=run_id,
                    extraction_result_id=extraction_result.id,
                    ground_truth_item_id=gt_item.id,
                    overall_score=doc_score.overall_score,
                    field_scores=doc_score.field_scores,
                    line_items_score=doc_score.line_items_score,
                    evaluation_metadata=doc_score.evaluation_metadata,
                )

                # Accumulate for aggregate metrics
                overall_scores.append(doc_score.overall_score)
                if doc_score.overall_score >= 0.99:
                    perfect_count += 1

                for field_name, field_data in doc_score.field_scores.items():
                    field_accuracy.setdefault(field_name, []).append(field_data["score"])

                if doc_score.line_items_score:
                    line_items_f1s.append(doc_score.line_items_score["f1"])

                items_completed += 1
                await self.eval_repo.update_progress(run_id, items_completed)

            # Compute aggregate metrics
            if not overall_scores:
                await self.eval_repo.update_status(
                    run_id, ExtractionEvalRunStatus.failed,
                    error_message="No extraction results found for any ground truth items",
                )
                return

            metrics = {
                "overallScoreMean": round(statistics.mean(overall_scores), 4),
                "overallScoreMedian": round(statistics.median(overall_scores), 4),
                "fieldAccuracy": {
                    name: {
                        "exactMatchRate": round(
                            sum(1 for s in scores if s >= 1.0) / len(scores), 4
                        ),
                        "avgScore": round(statistics.mean(scores), 4),
                    }
                    for name, scores in field_accuracy.items()
                },
                "lineItemsF1Mean": round(statistics.mean(line_items_f1s), 4) if line_items_f1s else None,
                "documentsEvaluated": len(overall_scores),
                "documentsPerfect": perfect_count,
            }

            await self.eval_repo.update_metrics(run_id, metrics)

        except Exception as e:
            logger.error(f"Extraction eval run {run_id} failed: {e}")
            await self.eval_repo.update_status(
                run_id, ExtractionEvalRunStatus.failed,
                error_message=str(e),
            )

    async def _find_extraction_result(
        self, document_id: UUID, extraction_schema_id: UUID
    ) -> ExtractionResult | None:
        """Find the most recent completed extraction result for a document + schema."""
        result = await self.session.execute(
            select(ExtractionResult)
            .where(
                ExtractionResult.document_id == document_id,
                ExtractionResult.extraction_schema_id == extraction_schema_id,
                ExtractionResult.status == ExtractionResultStatus.completed,
            )
            .order_by(ExtractionResult.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _run_to_response(run) -> ExtractionEvalRunResponse:
        gt_name = run.ground_truth_set.name if run.ground_truth_set else ""
        return ExtractionEvalRunResponse(
            id=run.id,
            project_id=run.project_id,
            ground_truth_set_id=run.ground_truth_set_id,
            ground_truth_set_name=gt_name,
            name=run.name,
            config=run.config,
            status=run.status.value if hasattr(run.status, "value") else run.status,
            metrics=run.metrics,
            error_message=run.error_message,
            items_completed=run.items_completed,
            items_total=run.items_total,
            created_by=run.created_by,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    @staticmethod
    def _result_to_response(result) -> ExtractionEvalResultResponse:
        doc_id = result.ground_truth_item.document_id if result.ground_truth_item else None
        doc_title = ""
        if result.ground_truth_item and result.ground_truth_item.document:
            doc_title = result.ground_truth_item.document.title or ""
        expected_data = (
            result.ground_truth_item.expected_data
            if result.ground_truth_item else None
        )
        # Normalise predicted data so the UI sees the same canonical form
        # that the eval engine scored against
        predicted_data = None
        if result.extraction_result:
            predicted_data = normalise(
                structured_data=result.extraction_result.structured_data,
                extraction_method=result.extraction_result.extraction_method,
                schema_definition=result.extraction_result.schema_definition_snapshot,
            )
        return ExtractionEvalResultResponse(
            id=result.id,
            eval_run_id=result.eval_run_id,
            extraction_result_id=result.extraction_result_id,
            ground_truth_item_id=result.ground_truth_item_id,
            document_id=doc_id,
            document_title=doc_title,
            overall_score=result.overall_score,
            field_scores=result.field_scores,
            line_items_score=result.line_items_score,
            expected_data=expected_data,
            predicted_data=predicted_data,
            evaluation_metadata=result.evaluation_metadata,
            created_at=result.created_at,
        )
