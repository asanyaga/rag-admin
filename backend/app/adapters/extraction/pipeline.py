"""Composable extraction pipeline: preprocess -> chunk -> inner -> merge."""
from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any, Awaitable, Callable

from app.adapters.extraction.chunking.citation_policy import resolve_level
from app.adapters.extraction.chunking.merge import merge_outputs
from app.adapters.extraction.chunking.registry import build_strategy
from app.adapters.extraction.chunking.token_budget import estimate_tokens
from app.adapters.extraction.preprocess.base import apply_preprocess
from app.ports.data_extraction import DataExtractor, ExtractionOutput
from app.services.llm.types import LLMRateLimitError


class _Reservation:
    """Mutable entry in the TPM sliding window."""
    __slots__ = ('ts', 'tokens')

    def __init__(self, ts: float, tokens: int) -> None:
        self.ts = ts
        self.tokens = tokens


class TpmThrottle:
    """Sliding-window tokens-per-minute rate limiter for async chunk dispatch.

    Call `await throttle(estimated)` before dispatching a chunk to reserve
    capacity. Call `replace_reservation(r, actual)` once the chunk completes
    to swap the estimate for real usage and keep the rolling average calibrated.
    """

    def __init__(self, max_tpm: int, default_estimate: int = 8_000) -> None:
        self._max = max_tpm
        self._default = default_estimate
        self._log: deque[_Reservation] = deque()
        self._lock = asyncio.Lock()
        self._actuals: list[int] = []

    @property
    def rolling_estimate(self) -> int:
        if not self._actuals:
            return self._default
        return int(sum(self._actuals) / len(self._actuals))

    def _evict(self, now: float) -> None:
        while self._log and now - self._log[0].ts >= 60.0:
            self._log.popleft()

    def _used(self) -> int:
        return sum(r.tokens for r in self._log)

    async def throttle(self, estimated_tokens: int) -> _Reservation:
        """Block until capacity exists, then reserve estimated_tokens."""
        while True:
            async with self._lock:
                now = time.monotonic()
                self._evict(now)
                if not self._log or self._used() + estimated_tokens <= self._max:
                    r = _Reservation(now, estimated_tokens)
                    self._log.append(r)
                    return r
                wait = max(0.1, 60.0 - (now - self._log[0].ts))
            await asyncio.sleep(wait)

    def replace_reservation(self, reservation: _Reservation, actual_tokens: int) -> None:
        """Swap estimate for actual usage; update rolling average (capped at 10)."""
        reservation.tokens = actual_tokens
        self._actuals.append(actual_tokens)
        if len(self._actuals) > 10:
            self._actuals.pop(0)


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
