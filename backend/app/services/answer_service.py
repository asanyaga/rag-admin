"""Answer service orchestrating retrieve -> prompt -> stream for the playground."""

import json
import time
import logging
from typing import AsyncIterator
from uuid import UUID

from app.schemas.query import QueryRequest, RetrievalResult
from app.schemas.playground import PlaygroundAnswerRequest
from app.services.query_service import QueryService
from app.services.llm.types import LLMConfig, TokenUsage
from app.services.llm.openai_adapter import OpenAIAdapter
from app.services.llm.prompt import build_rag_prompt
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
    ) -> AsyncIterator[str]:
        """Generate SSE events for the answer pipeline.

        Yields formatted SSE event strings:
          event: chunks   -> retrieved chunk results
          event: token    -> individual content tokens
          event: done     -> final metadata (usage, latency)
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
                index_id, project_id, user_id, query_request
            )
        except Exception as e:
            yield _sse_event("error", {"error": str(e), "code": "retrieval_error"})
            return

        # Send chunks to the client
        chunks_data = [
            r.model_dump(by_alias=True) for r in query_response.results
        ]
        yield _sse_event("chunks", chunks_data)

        if not query_response.results:
            yield _sse_event("error", {
                "error": "No chunks retrieved. Try adjusting retrieval parameters.",
                "code": "no_chunks",
            })
            return

        # Phase 2: Build prompt
        messages = build_rag_prompt(
            query=request.query,
            chunks=query_response.results,
            instructions=request.instructions,
        )

        # Phase 3: Stream LLM response
        llm_config = LLMConfig(
            provider=request.llm_config.provider,
            model=request.llm_config.model,
            temperature=request.llm_config.temperature,
            max_tokens=request.llm_config.max_tokens,
        )

        try:
            adapter = OpenAIAdapter(api_key=api_key)
            token_count = 0

            async for token in adapter.stream_completion(messages, llm_config):
                token_count += 1
                yield _sse_event("token", {"content": token})

            latency_ms = (time.monotonic() - start) * 1000

            # Token counts from streaming are approximate — we count yielded tokens
            # but don't have exact prompt token count without an extra API call.
            # For Phase 1 this is acceptable; the done event uses estimates.
            yield _sse_event("done", {
                "usage": {
                    "promptTokens": 0,  # not available in streaming mode
                    "completionTokens": token_count,
                    "totalTokens": token_count,
                },
                "latencyMs": round(latency_ms, 1),
            })

        except Exception as e:
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
