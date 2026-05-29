"""Service for evaluation run execution and comparison."""
import asyncio
import logging
from uuid import UUID

from sqlalchemy import select as sa_select

from app.models import EvalRunStatus
from app.models.eval_run import EvalRun as EvalRunModel
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
    EvalRunProgress,
)
from app.schemas.query import QueryRequest
from app.services.query_service import QueryService
from app.services.trace_collector import TraceCollector
from app.services.judge_service import JudgeService, JUDGE_PROMPT_TEMPLATE
from app.services.answer_generation_service import generate_answer
from app.schemas.prompt_config import PromptConfig as PromptConfigSchema
from app.services.llm.prompt import DEFAULT_RAG_SYSTEM_PROMPT
from app.services.llm.prompt_config import resolve_llm_config
from app.services.llm.types import LLMConfig
from app.services.llm.port import LLMPort
from app.services.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class EvalService:
    def __init__(
        self,
        eval_run_repo: EvalRunRepository,
        golden_set_repo: GoldenSetRepository,
        query_service: QueryService,
        judge_service: JudgeService | None = None,
        generation_adapter: LLMPort | None = None,
        judge_adapter: LLMPort | None = None,
    ):
        self.eval_repo = eval_run_repo
        self.gs_repo = golden_set_repo
        self.query_service = query_service
        self.judge_service = judge_service or JudgeService()
        self._generation_adapter = generation_adapter
        self._judge_adapter = judge_adapter

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
            mode=data.mode,
            generation_config=data.generation_config.model_dump(by_alias=False, mode="json") if data.generation_config else None,
            judge_config=data.judge_config.model_dump(by_alias=False, mode="json") if data.judge_config else None,
            experiment_id=data.experiment_id,
            variant_label=data.variant_label,
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

    async def get_run_config(self, run_id: UUID, project_id: UUID) -> dict:
        """Return the full config of a run for the clone feature."""
        run = await self.eval_repo.get_by_id(run_id, project_id)
        if not run:
            raise NotFoundError(f"Eval run {run_id} not found")

        return {
            "goldenSetId": str(run.golden_set_id),
            "indexId": str(run.index_id),
            "name": run.name,
            "config": run.config,
            "mode": run.mode,
            "generationConfig": run.generation_config,
            "judgeConfig": run.judge_config,
            "experimentId": str(run.experiment_id) if run.experiment_id else None,
            "variantLabel": run.variant_label,
        }

    async def get_results(
        self, run_id: UUID, project_id: UUID, filter_type: str | None = None
    ) -> list[EvalRunResultResponse]:
        run = await self.eval_repo.get_by_id(run_id, project_id)
        if not run:
            raise NotFoundError(f"Eval run {run_id} not found")

        results = await self.eval_repo.get_results(run_id, filter_type=filter_type)

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
                generated_answer=r.generated_answer,
                faithfulness_score=r.faithfulness_score,
                relevance_score=r.relevance_score,
                claim_breakdown=r.claim_breakdown,
                judge_error=r.judge_error,
                generation_error=r.generation_error,
                trace_data=r.trace_data,
            )
            for r in results
        ]

    async def get_progress(
        self, run_id: UUID, project_id: UUID
    ) -> EvalRunProgress:
        run = await self.eval_repo.get_by_id(run_id, project_id)
        if not run:
            raise NotFoundError(f"Eval run {run_id} not found")

        # Get total query count from golden set
        gs = await self.gs_repo.get_with_queries(run.golden_set_id, project_id)
        items_total = len(gs.queries) if gs and gs.queries else 0

        return EvalRunProgress(
            status=run.status.value if hasattr(run.status, 'value') else run.status,
            items_total=items_total,
            items_completed=run.items_completed,
            failed_item_count=run.failed_item_count,
        )

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

            is_answer_mode = run.mode == "retrieval_and_answer"

            precisions = []
            recalls = []
            f1s = []
            faithfulness_scores = []
            relevance_scores = []
            items_completed = 0
            failed_item_count = 0

            # Use semaphore for concurrency control in answer mode
            semaphore = asyncio.Semaphore(3)

            async def process_query(query):
                nonlocal items_completed, failed_item_count
                async with semaphore:
                    return await self._process_single_query(
                        run=run,
                        query=query,
                        config=config,
                        run_id=run_id,
                        user_id=user_id,
                        is_answer_mode=is_answer_mode,
                    )

            # Process queries sequentially for retrieval-only (cheaper),
            # with concurrency for answer mode (I/O bound on LLM calls)
            if is_answer_mode:
                tasks = [process_query(q) for q in gs.queries]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    items_completed += 1
                    if isinstance(result, Exception):
                        logger.warning(f"Error processing query {gs.queries[i].id}: {result}")
                        failed_item_count += 1
                        precisions.append(0.0)
                        recalls.append(0.0)
                        f1s.append(0.0)
                    else:
                        precisions.append(result["precision"])
                        recalls.append(result["recall"])
                        f1s.append(result["f1"])
                        if result.get("faithfulness_score") is not None:
                            faithfulness_scores.append(result["faithfulness_score"])
                        if result.get("relevance_score") is not None:
                            relevance_scores.append(result["relevance_score"])
                        if result.get("had_error"):
                            failed_item_count += 1
                    await self.eval_repo.update_progress(
                        run_id, items_completed, failed_item_count
                    )
            else:
                for query in gs.queries:
                    try:
                        result = await self._process_single_query(
                            run=run,
                            query=query,
                            config=config,
                            run_id=run_id,
                            user_id=user_id,
                            is_answer_mode=False,
                        )
                        precisions.append(result["precision"])
                        recalls.append(result["recall"])
                        f1s.append(result["f1"])
                    except Exception as e:
                        logger.warning(f"Error evaluating query {query.id}: {e}")
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
                        failed_item_count += 1

                    items_completed += 1
                    await self.eval_repo.update_progress(
                        run_id, items_completed, failed_item_count
                    )

            # Aggregate metrics
            n = len(precisions) or 1
            metrics = {
                "avgPrecision": round(sum(precisions) / n, 4),
                "avgRecall": round(sum(recalls) / n, 4),
                "avgF1": round(sum(f1s) / n, 4),
                "queriesBelowThreshold": sum(1 for f in f1s if f < 0.5),
            }

            if faithfulness_scores:
                metrics["avgFaithfulness"] = round(
                    sum(faithfulness_scores) / len(faithfulness_scores), 4
                )
            if relevance_scores:
                metrics["avgRelevance"] = round(
                    sum(relevance_scores) / len(relevance_scores), 4
                )

            if failed_item_count > 0:
                await self.eval_repo.update_status(
                    run_id, EvalRunStatus.partial_failure
                )
                # Still save metrics
                result = await self.eval_repo.session.execute(
                    sa_select(EvalRunModel).where(EvalRunModel.id == run_id)
                )
                eval_run = result.scalar_one_or_none()
                if eval_run:
                    eval_run.metrics = metrics
                    await self.eval_repo.session.commit()
            else:
                await self.eval_repo.update_metrics(run_id, metrics)

        except Exception as e:
            logger.error(f"Eval run {run_id} failed: {e}")
            await self.eval_repo.update_status(
                run_id, EvalRunStatus.failed,
                error_message=str(e)
            )

    async def _process_single_query(
        self, run, query, config, run_id, user_id, is_answer_mode
    ) -> dict:
        """Process a single query: retrieval + optional generation + judge."""
        # Build relevance set from golden set sources
        relevance_set: set[tuple[str, int]] = set()
        for source in (query.sources or []):
            locator = source.locator or {}
            if locator.get("type") == "page":
                for page in locator.get("pages", []):
                    relevance_set.add((str(source.document_id), page))

        # Create trace collector for this query
        collector = TraceCollector(
            query=query.query_text,
            search_type=config.search_type,
        )

        # Query the index (with tracing)
        query_request = QueryRequest(
            query=query.query_text,
            search_type=config.search_type,
            top_k=config.top_k,
            similarity_threshold=config.similarity_threshold,
        )
        response = await self.query_service.query_index(
            run.index_id, run.project_id, run.created_by, query_request,
            collector,
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

        # Compute retrieval metrics
        k = len(response.results) or 1
        relevance_size = len(relevance_set) or 1
        precision = relevant_retrieved / k
        recall = len(matched_relevant) / relevance_size
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        # Answer eval fields
        generated_answer = None
        faithfulness_score = None
        relevance_score = None
        claim_breakdown = None
        judge_error = None
        generation_error = None
        had_error = False

        if is_answer_mode and self._generation_adapter and self._judge_adapter:
            gen_pc = PromptConfigSchema.model_validate(run.generation_config) if run.generation_config else None
            resolved = resolve_llm_config(
                gen_pc,
                default_provider="openai",
                default_model="gpt-4o",
                default_temperature=0.0,
                default_max_tokens=1024,
            )
            gen_config = LLMConfig(
                provider=resolved.provider,
                model=resolved.model,
                temperature=resolved.temperature,
                max_tokens=resolved.max_tokens,
            )
            sys_prompt = (
                gen_pc.system_prompt
                if gen_pc and gen_pc.system_prompt
                else DEFAULT_RAG_SYSTEM_PROMPT
            )
            gen_context = "\n\n".join(
                f"[{i + 1}] {chunk.get('content', '')}"
                for i, chunk in enumerate(retrieved_chunks_info)
            )
            gen_messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Context:\n{gen_context}\n\nQuestion: {query.query_text}"},
            ]

            # Generate answer (with tracing)
            try:
                with collector.span("llm_generation", f"Answer Generation ({gen_config.model})", input={
                    "model": gen_config.model,
                    "provider": gen_config.provider,
                    "temperature": gen_config.temperature,
                    "max_tokens": gen_config.max_tokens,
                    "messages": gen_messages,
                }) as gen_span:
                    generated_answer = await generate_answer(
                        question=query.query_text,
                        chunks=retrieved_chunks_info,
                        generation_adapter=self._generation_adapter,
                        generation_config=gen_config,
                        prompt_config=prompt_config,
                    )
                    gen_span.output = {
                        "answer_length": len(generated_answer),
                    }
                    gen_span.metrics.model = gen_config.model
                    gen_span.metrics.provider = gen_config.provider
            except Exception as e:
                logger.warning(f"Generation failed for query {query.id}: {e}")
                generation_error = str(e)
                had_error = True

            # Judge answer (only if generation succeeded)
            if generated_answer and not generation_error:
                try:
                    resolved_judge = resolve_llm_config(
                        PromptConfigSchema.model_validate(run.judge_config) if run.judge_config else None,
                        default_provider="openai",
                        default_model="gpt-4o",
                    )
                    judge_config = LLMConfig(
                        provider=resolved_judge.provider,
                        model=resolved_judge.model,
                    )
                    # Build the judge messages (mirrors judge_service logic)
                    judge_prompt = JUDGE_PROMPT_TEMPLATE.format(
                        question=query.query_text,
                        context=gen_context,
                        answer=generated_answer,
                    )
                    judge_messages = [
                        {"role": "user", "content": judge_prompt},
                    ]
                    with collector.span("llm_judge", f"Judge Evaluation ({judge_config.model})", input={
                        "model": judge_config.model,
                        "provider": judge_config.provider,
                        "messages": judge_messages,
                    }) as judge_span:
                        judge_result = await self.judge_service.evaluate(
                            question=query.query_text,
                            chunks=retrieved_chunks_info,
                            answer=generated_answer,
                            judge_adapter=self._judge_adapter,
                            judge_config=judge_config,
                        )
                        if judge_result.error:
                            judge_error = judge_result.error
                            had_error = True
                            judge_span.status = "error"
                            judge_span.error = judge_result.error
                        else:
                            faithfulness_score = judge_result.faithfulness_score
                            relevance_score = judge_result.relevance_score
                            claim_breakdown = [
                                {"text": c.text, "label": c.label, "source": c.source}
                                for c in judge_result.claims
                            ]
                            judge_span.output = {
                                "faithfulness_score": faithfulness_score,
                                "relevance_score": relevance_score,
                                "claim_count": len(claim_breakdown),
                            }
                        judge_span.metrics.model = judge_config.model
                        judge_span.metrics.provider = judge_config.provider
                except Exception as e:
                    logger.warning(f"Judge failed for query {query.id}: {e}")
                    judge_error = str(e)
                    had_error = True

        # Build and serialize the trace
        trace = collector.build_trace()
        trace_data = trace.model_dump(by_alias=True)

        await self.eval_repo.create_result(
            eval_run_id=run_id,
            query_id=query.id,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            retrieved_chunks=retrieved_chunks_info,
            generated_answer=generated_answer,
            faithfulness_score=faithfulness_score,
            relevance_score=relevance_score,
            claim_breakdown=claim_breakdown,
            judge_error=judge_error,
            generation_error=generation_error,
            trace_data=trace_data,
        )

        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "faithfulness_score": faithfulness_score,
            "relevance_score": relevance_score,
            "had_error": had_error,
        }

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

        exp_name = None
        if hasattr(run, 'experiment') and run.experiment:
            exp_name = run.experiment.name

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
            mode=run.mode,
            generationConfig=run.generation_config,
            judgeConfig=run.judge_config,
            items_completed=run.items_completed,
            failed_item_count=run.failed_item_count,
            experiment_id=run.experiment_id,
            experiment_name=exp_name,
            variant_label=run.variant_label,
        )
