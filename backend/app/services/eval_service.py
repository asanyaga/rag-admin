"""Service for evaluation run execution and comparison."""
import logging
from uuid import UUID

from app.models import EvalRunStatus
from app.repositories.eval_run_repository import EvalRunRepository
from app.repositories.golden_set_repository import GoldenSetRepository
from app.schemas.eval_run import (
    EvalRunCreate,
    EvalRunConfig,
    EvalRunResponse,
    EvalRunResultResponse,
    RetrievedChunkInfo,
    ExpectedSourceInfo,
    QueryComparisonItem,
    QueryComparisonMetrics,
    ComparisonSummary,
    RunComparisonResponse,
)
from app.schemas.query import QueryRequest
from app.services.query_service import QueryService
from app.services.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class EvalService:
    def __init__(
        self,
        eval_run_repo: EvalRunRepository,
        golden_set_repo: GoldenSetRepository,
        query_service: QueryService,
    ):
        self.eval_repo = eval_run_repo
        self.gs_repo = golden_set_repo
        self.query_service = query_service

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_run(
        self, project_id: UUID, user_id: UUID, data: EvalRunCreate
    ) -> EvalRunResponse:
        # Validate golden set exists
        gs = await self.gs_repo.get_by_id(data.golden_set_id, project_id)
        if not gs:
            raise NotFoundError(f"Golden set {data.golden_set_id} not found")

        name = data.name or f"Eval: {gs.name}"
        run = await self.eval_repo.create(
            project_id=project_id,
            golden_set_id=data.golden_set_id,
            index_id=data.index_id,
            name=name,
            config=data.config.model_dump(by_alias=True),
            user_id=user_id,
        )
        # Reload with relationships
        run = await self.eval_repo.get_by_id(run.id, project_id)
        return self._to_response(run)

    async def get_run(self, run_id: UUID, project_id: UUID) -> EvalRunResponse:
        run = await self.eval_repo.get_by_id(run_id, project_id)
        if not run:
            raise NotFoundError(f"Eval run {run_id} not found")
        return self._to_response(run)

    async def list_runs(self, project_id: UUID) -> list[EvalRunResponse]:
        runs = await self.eval_repo.list_by_project(project_id)
        return [self._to_response(r) for r in runs]

    async def delete_run(self, run_id: UUID, project_id: UUID) -> None:
        deleted = await self.eval_repo.delete(run_id, project_id)
        if not deleted:
            raise NotFoundError(f"Eval run {run_id} not found")

    async def get_results(
        self, run_id: UUID, project_id: UUID
    ) -> list[EvalRunResultResponse]:
        run = await self.eval_repo.get_by_id(run_id, project_id)
        if not run:
            raise NotFoundError(f"Eval run {run_id} not found")

        results = await self.eval_repo.get_results(run_id)

        # Build expected sources map from golden set
        gs = await self.gs_repo.get_with_queries(run.golden_set_id, project_id)
        expected_map: dict[UUID, list[ExpectedSourceInfo]] = {}
        if gs:
            for q in (gs.queries or []):
                expected_map[q.id] = []
                for s in (q.sources or []):
                    doc = s.document
                    doc_name = ""
                    if doc:
                        doc_name = doc.source_metadata.get("filename") or doc.title or "Unknown"
                    expected_map[q.id].append(ExpectedSourceInfo(
                        document_id=str(s.document_id),
                        document_name=doc_name,
                        locator=s.locator,
                    ))

        return [
            EvalRunResultResponse(
                id=r.id,
                query_id=r.query_id,
                query_text=r.query.query_text if r.query else "",
                precision=r.precision,
                recall=r.recall,
                f1=r.f1,
                retrieved_chunks=[
                    RetrievedChunkInfo(**c) for c in (r.retrieved_chunks or [])
                ],
                expected_sources=expected_map.get(r.query_id, []),
            )
            for r in results
        ]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute_eval_run(
        self, run_id: UUID, project_id: UUID, user_id: UUID
    ) -> None:
        """Execute an evaluation run (called from background task)."""
        try:
            await self.eval_repo.update_status(run_id, EvalRunStatus.running)

            run = await self.eval_repo.get_by_id(run_id, project_id)
            if not run:
                return

            config = EvalRunConfig(**run.config)

            # Load golden set with all queries + sources
            gs = await self.gs_repo.get_with_queries(run.golden_set_id, project_id)
            if not gs or not gs.queries:
                await self.eval_repo.update_status(
                    run_id, EvalRunStatus.failed,
                    error_message="Golden set has no queries"
                )
                return

            precisions = []
            recalls = []
            f1s = []

            for query in gs.queries:
                try:
                    # Build relevance set from golden set sources
                    relevance_set: set[tuple[str, int]] = set()
                    for source in (query.sources or []):
                        locator = source.locator or {}
                        if locator.get("type") == "page":
                            for page in locator.get("pages", []):
                                relevance_set.add((str(source.document_id), page))

                    # Query the index
                    query_request = QueryRequest(
                        query=query.query_text,
                        search_type=config.search_type,
                        top_k=config.top_k,
                        similarity_threshold=config.similarity_threshold,
                    )
                    response = await self.query_service.query_index(
                        run.index_id, project_id, user_id, query_request
                    )

                    # Evaluate retrieved chunks
                    retrieved_chunks_info = []
                    relevant_retrieved = 0
                    matched_relevant: set[tuple[str, int]] = set()
                    for result in response.results:
                        doc_id = result.metadata.document_id
                        page = result.metadata.page
                        page_numbers = result.metadata.page_numbers or ([page] if page is not None else [])
                        is_relevant = any((doc_id, p) in relevance_set for p in page_numbers)
                        if is_relevant:
                            relevant_retrieved += 1
                            for p in page_numbers:
                                if (doc_id, p) in relevance_set:
                                    matched_relevant.add((doc_id, p))

                        retrieved_chunks_info.append({
                            "chunkId": result.chunk_id,
                            "rank": result.rank,
                            "score": result.score,
                            "content": result.content[:500],
                            "documentId": doc_id,
                            "documentName": result.metadata.document_name,
                            "page": page,
                            "isRelevant": is_relevant,
                        })

                    # Compute metrics
                    k = len(response.results) or 1
                    relevance_size = len(relevance_set) or 1
                    precision = relevant_retrieved / k
                    recall = len(matched_relevant) / relevance_size
                    f1 = (
                        2 * precision * recall / (precision + recall)
                        if (precision + recall) > 0
                        else 0.0
                    )

                    precisions.append(precision)
                    recalls.append(recall)
                    f1s.append(f1)

                    await self.eval_repo.create_result(
                        eval_run_id=run_id,
                        query_id=query.id,
                        precision=round(precision, 4),
                        recall=round(recall, 4),
                        f1=round(f1, 4),
                        retrieved_chunks=retrieved_chunks_info,
                    )

                except Exception as e:
                    logger.warning(f"Error evaluating query {query.id}: {e}")
                    # Store zero metrics for failed queries
                    precisions.append(0.0)
                    recalls.append(0.0)
                    f1s.append(0.0)
                    await self.eval_repo.create_result(
                        eval_run_id=run_id,
                        query_id=query.id,
                        precision=0.0,
                        recall=0.0,
                        f1=0.0,
                        retrieved_chunks=[],
                    )

            # Aggregate metrics
            n = len(precisions) or 1
            metrics = {
                "avgPrecision": round(sum(precisions) / n, 4),
                "avgRecall": round(sum(recalls) / n, 4),
                "avgF1": round(sum(f1s) / n, 4),
                "queriesBelowThreshold": sum(1 for f in f1s if f < 0.5),
            }

            await self.eval_repo.update_metrics(run_id, metrics)

        except Exception as e:
            logger.error(f"Eval run {run_id} failed: {e}")
            await self.eval_repo.update_status(
                run_id, EvalRunStatus.failed,
                error_message=str(e)
            )

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    async def compare_runs(
        self, project_id: UUID, run_id_1: UUID, run_id_2: UUID
    ) -> RunComparisonResponse:
        run1, run2 = await self.eval_repo.get_for_comparison(
            run_id_1, run_id_2, project_id
        )
        if not run1:
            raise NotFoundError(f"Eval run {run_id_1} not found")
        if not run2:
            raise NotFoundError(f"Eval run {run_id_2} not found")

        if run1.golden_set_id != run2.golden_set_id:
            raise ValidationError("Both runs must use the same golden set")

        # Build result maps by query_id
        results_1 = {r.query_id: r for r in run1.results}
        results_2 = {r.query_id: r for r in run2.results}

        all_query_ids = set(results_1.keys()) | set(results_2.keys())

        per_query = []
        delta_precisions = []
        delta_recalls = []
        delta_f1s = []
        improved = 0
        degraded = 0
        unchanged = 0

        for qid in all_query_ids:
            r1 = results_1.get(qid)
            r2 = results_2.get(qid)

            b_p = r1.precision if r1 else 0.0
            b_r = r1.recall if r1 else 0.0
            b_f1 = r1.f1 if r1 else 0.0
            c_p = r2.precision if r2 else 0.0
            c_r = r2.recall if r2 else 0.0
            c_f1 = r2.f1 if r2 else 0.0

            delta = round(c_f1 - b_f1, 4)
            delta_precisions.append(c_p - b_p)
            delta_recalls.append(c_r - b_r)
            delta_f1s.append(delta)

            if delta > 0.001:
                improved += 1
            elif delta < -0.001:
                degraded += 1
            else:
                unchanged += 1

            query_text = ""
            if r1 and r1.query:
                query_text = r1.query.query_text
            elif r2 and r2.query:
                query_text = r2.query.query_text

            per_query.append(QueryComparisonItem(
                query_id=qid,
                query_text=query_text,
                baseline=QueryComparisonMetrics(precision=b_p, recall=b_r, f1=b_f1),
                challenger=QueryComparisonMetrics(precision=c_p, recall=c_r, f1=c_f1),
                delta_f1=delta,
            ))

        n = len(per_query) or 1
        summary = ComparisonSummary(
            avg_delta_precision=round(sum(delta_precisions) / n, 4),
            avg_delta_recall=round(sum(delta_recalls) / n, 4),
            avg_delta_f1=round(sum(delta_f1s) / n, 4),
            improved_queries=improved,
            degraded_queries=degraded,
            unchanged_queries=unchanged,
        )

        return RunComparisonResponse(
            baseline_run=self._to_response(run1),
            challenger_run=self._to_response(run2),
            per_query_comparison=per_query,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_response(run) -> EvalRunResponse:
        gs_name = run.golden_set.name if run.golden_set else ""
        idx_name = run.index.name if run.index else ""
        return EvalRunResponse(
            id=run.id,
            name=run.name,
            golden_set_id=run.golden_set_id,
            golden_set_name=gs_name,
            index_id=run.index_id,
            index_name=idx_name,
            config=run.config,
            status=run.status.value if hasattr(run.status, 'value') else run.status,
            metrics=run.metrics,
            error_message=run.error_message,
            created_by=run.created_by,
            created_at=run.created_at,
        )
