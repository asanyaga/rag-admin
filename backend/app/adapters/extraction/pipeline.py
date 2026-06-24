"""Composable extraction pipeline: preprocess -> chunk -> inner -> merge."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from app.adapters.extraction.chunking.citation_policy import resolve_level
from app.adapters.extraction.chunking.merge import merge_outputs
from app.adapters.extraction.chunking.registry import build_strategy
from app.adapters.extraction.chunking.token_budget import estimate_tokens
from app.adapters.extraction.preprocess.base import apply_preprocess
from app.ports.data_extraction import DataExtractor, ExtractionOutput
from app.services.llm.types import LLMRateLimitError


async def run_with_retry(
    factory: Callable[[], Awaitable[Any]],
    max_retries: int,
) -> Any:
    """Call `factory()` retrying on LLMRateLimitError with backoff."""
    attempt = 0
    while True:
        try:
            return await factory()
        except LLMRateLimitError as e:
            attempt += 1
            if attempt > max_retries:
                raise
            delay = e.retry_after if e.retry_after is not None else min(2 ** attempt, 30)
            await asyncio.sleep(delay)


class PipelineExtractor(DataExtractor):
    """Wraps an inner DataExtractor with preprocess, chunking, and merge."""

    extractor_type = "pipeline"

    def __init__(
        self,
        inner: DataExtractor,
        preprocess: list[dict] | None = None,
        chunking: dict | None = None,
        max_concurrency: int = 3,
        max_retries: int = 3,
    ) -> None:
        self._inner = inner
        self._preprocess = preprocess or []
        self._chunking = chunking or {}
        self._max_concurrency = max_concurrency
        self._max_retries = max_retries

    async def extract(
        self,
        parsed_document: Any,
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ExtractionOutput:
        cfg = dict(config or {})
        doc = apply_preprocess(parsed_document, self._preprocess)

        # Resolve citation level once, from whole-doc size, and pass to inner.
        est = estimate_tokens(doc.full_markdown or doc.full_text or "") or _doc_tokens(doc)
        level = resolve_level(self._chunking.get("citationLevel", "full"), est)
        cfg["citation_level"] = level

        strategy = build_strategy(
            self._chunking.get("strategy", "none"),
            self._chunking.get("config", {}),
        )
        if strategy is None:
            return await run_with_retry(
                lambda: self._inner.extract(doc, schema, cfg), self._max_retries
            )

        chunks = strategy.split(doc, schema, self._chunking.get("config", {}))
        if len(chunks) == 1:
            return await run_with_retry(
                lambda: self._inner.extract(chunks[0].document, schema, cfg),
                self._max_retries,
            )

        sem = asyncio.Semaphore(self._max_concurrency)

        async def _run_chunk(chunk) -> ExtractionOutput:
            async with sem:
                return await run_with_retry(
                    lambda: self._inner.extract(chunk.document, schema, cfg),
                    self._max_retries,
                )

        # asyncio.gather raises the first ExtractionError -> whole result fails.
        results = await asyncio.gather(*[_run_chunk(c) for c in chunks])
        dedupe_key = self._chunking.get("config", {}).get("dedupeKey")
        return merge_outputs(list(results), schema, dedupe_key, chunks=chunks)


def _doc_tokens(doc) -> int:
    return sum(estimate_tokens(b.markdown or b.text or "") for b in doc.blocks)
