"""Answer service orchestrating retrieve -> prompt -> stream for the playground."""

import json
import time
import logging
from typing import AsyncIterator
from uuid import UUID

from app.schemas.query import QueryRequest, RetrievalResult
from app.schemas.playground import PlaygroundAnswerRequest
from app.services.query_service import QueryService
from app.services.trace_collector import TraceCollector
from app.services.llm.factory import create_adapter
from app.services.llm.prompt import build_rag_prompt
from app.services.llm.prompt_config import resolve_llm_config
from app.utils.encryption import decrypt

logger = logging.getLogger(__name__)


class AnswerService:
    """Orchestrates the full RAG answer pipeline: retrieve -> build prompt -> stream."""

    def __init__(self, query_service: QueryService):
        self.query_service = query_service

    async def stream_answer(
        self,
        index_id: UUID,
        project_id: UUID,
        user_id: UUID,
        request: PlaygroundAnswerRequest,
        api_key: str,
        collector: TraceCollector | None = None,
    ) -> AsyncIterator[str]:
        """Generate SSE events for the answer pipeline.

        Yields formatted SSE event strings:
          event: chunks   -> retrieved chunk results
          event: token    -> individual content tokens
          event: done     -> final metadata (usage, latency)
          event: trace    -> query trace (when collector is provided)
          event: error    -> error details
        """
        start = time.monotonic()

        # Phase 1: Retrieve chunks using existing QueryService
        try:
            query_request = QueryRequest(
                query=request.query,
                search_type=request.retrieval_config.search_type,
                top_k=request.retrieval_config.top_k,
                similarity_threshold=request.retrieval_config.similarity_threshold,
            )
            query_response = await self.query_service.query_index(
                index_id, project_id, user_id, query_request, collector
            )
        except Exception as e:
            yield _sse_event("error", {"error": str(e), "code": "retrieval_error"})
            return

        # Send chunks to the client
        chunks_data = [
            r.model_dump(by_alias=True, mode="json") for r in query_response.results
        ]
        yield _sse_event("chunks", chunks_data)

        if not query_response.results:
            yield _sse_event("error", {
                "error": "No chunks retrieved. Try adjusting retrieval parameters.",
                "code": "no_chunks",
            })
            return

        # Phase 2: Build prompt
        system_prompt = request.llm_config.system_prompt if request.llm_config else None
        if collector:
            with collector.span("prompt_building", "Build RAG Prompt", input={
                "chunk_count": len(query_response.results),
                "has_system_prompt": bool(system_prompt),
            }) as s:
                messages = build_rag_prompt(
                    query=request.query,
                    chunks=query_response.results,
                    system_prompt=system_prompt,
                )
                total_chars = sum(len(m.get("content", "")) for m in messages)
                s.output = {"message_count": len(messages), "total_chars": total_chars}
                s.metrics.char_count = total_chars
        else:
            messages = build_rag_prompt(
                query=request.query,
                chunks=query_response.results,
                system_prompt=system_prompt,
            )

        # Phase 3: Stream LLM response
        llm_config = resolve_llm_config(
            request.llm_config,
            default_provider="openai",
            default_model="gpt-4o",
        )

        try:
            adapter = create_adapter(llm_config.provider, api_key)
            token_count = 0

            if collector:
                llm_span_ctx = collector.span("llm_generation", f"LLM Generation ({llm_config.model})", input={
                    "model": llm_config.model,
                    "provider": llm_config.provider,
                    "temperature": llm_config.temperature,
                    "max_tokens": llm_config.max_tokens,
                    "messages": messages,
                })
                llm_span = llm_span_ctx.__enter__()
            else:
                llm_span_ctx = None
                llm_span = None

            try:
                async for token in adapter.stream_completion(messages, llm_config):
                    token_count += 1
                    yield _sse_event("token", {"content": token})
            finally:
                if llm_span is not None and llm_span_ctx is not None:
                    llm_span.metrics.completion_tokens = token_count
                    llm_span.metrics.total_tokens = token_count
                    llm_span.metrics.model = llm_config.model
                    llm_span.metrics.provider = llm_config.provider
                    llm_span.output = {"completion_tokens": token_count}
                    llm_span_ctx.__exit__(None, None, None)

            latency_ms = (time.monotonic() - start) * 1000

            yield _sse_event("done", {
                "usage": {
                    "promptTokens": 0,
                    "completionTokens": token_count,
                    "totalTokens": token_count,
                },
                "latencyMs": round(latency_ms, 1),
            })

            # Emit trace event after done
            if collector:
                trace = collector.build_trace()
                yield _sse_event("trace", trace.model_dump(by_alias=True, mode="json"))

        except Exception as e:
            if llm_span is not None and llm_span_ctx is not None:
                llm_span.status = "error"
                llm_span.error = str(e)
                llm_span_ctx.__exit__(type(e), e, e.__traceback__)

            logger.error(f"LLM streaming error: {e}", exc_info=True)
            error_msg = str(e)
            code = "llm_error"
            if "rate" in error_msg.lower():
                code = "llm_rate_limit"
            elif "auth" in error_msg.lower() or "api key" in error_msg.lower():
                code = "llm_auth_error"
            yield _sse_event("error", {"error": error_msg, "code": code})


def _sse_event(event_type: str, data: dict | list) -> str:
    """Format a single SSE event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
