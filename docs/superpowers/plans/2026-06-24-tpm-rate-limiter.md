# TPM Rate Limiter for PipelineExtractor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a proactive tokens-per-minute rate limiter to `PipelineExtractor` so large document extractions don't burst over provider TPM limits.

**Architecture:** A `TpmThrottle` class (sliding window + async lock) lives in `pipeline.py`. Before each chunk fires, it waits until the 60-second rolling window has capacity and pre-reserves an estimated token cost. After the chunk completes, the estimate is swapped for actual usage, and a rolling average is updated so subsequent estimates improve over time. `PipelineExtractor` accepts `max_tokens_per_minute: int | None = None`; the router extracts `maxTokensPerMinute` from the `chunking` dict. The frontend adds a "Rate limit (TPM)" numeric input to the "Large document handling" collapsible.

**Tech Stack:** Python 3.12 asyncio, React 18, TypeScript, shadcn/ui

## Global Constraints

- No new Python dependencies — use only `asyncio`, `time`, `collections.deque`
- `None` for `max_tokens_per_minute` preserves existing behaviour exactly (no throttle)
- Backend tests run with: `uv run --directory backend python -m pytest -o "addopts="`
- Frontend build: `npm --prefix frontend run build`
- No database schema changes

---

### Task 1: TpmThrottle class

**Files:**
- Modify: `backend/app/adapters/extraction/pipeline.py` — add `_Reservation` and `TpmThrottle` before `PipelineExtractor`
- Modify: `backend/tests/adapters/extraction/test_pipeline.py` — unit tests for `TpmThrottle`

**Interfaces:**
- Produces:
  ```python
  class _Reservation:
      ts: float    # time.monotonic() at reservation
      tokens: int  # mutable — updated by replace_reservation

  class TpmThrottle:
      def __init__(self, max_tpm: int, default_estimate: int = 8_000) -> None
      @property
      def rolling_estimate(self) -> int   # default_estimate until first replacement
      async def throttle(self, estimated_tokens: int) -> _Reservation
      def replace_reservation(self, reservation: _Reservation, actual_tokens: int) -> None
  ```

- [ ] **Step 1: Write failing tests**

Add to the bottom of `backend/tests/adapters/extraction/test_pipeline.py`:

```python
import asyncio as _asyncio
from app.adapters.extraction.pipeline import TpmThrottle


async def test_tpm_throttle_allows_within_budget():
    throttle = TpmThrottle(max_tpm=10_000)
    r = await throttle.throttle(5_000)
    assert r.tokens == 5_000


async def test_tpm_throttle_blocks_when_budget_full():
    """Second throttle call must block when the window is saturated."""
    throttle = TpmThrottle(max_tpm=5_000)
    await throttle.throttle(5_000)  # saturate window
    with pytest.raises(_asyncio.TimeoutError):
        await _asyncio.wait_for(throttle.throttle(1_000), timeout=0.05)


async def test_tpm_throttle_oversized_chunk_fires_when_window_empty():
    """A single chunk larger than max_tpm still fires (window is empty)."""
    throttle = TpmThrottle(max_tpm=1_000)
    r = await throttle.throttle(5_000)
    assert r.tokens == 5_000


async def test_tpm_throttle_replace_reservation_mutates_tokens():
    throttle = TpmThrottle(max_tpm=10_000)
    r = await throttle.throttle(5_000)
    throttle.replace_reservation(r, 3_200)
    assert r.tokens == 3_200


async def test_tpm_throttle_rolling_estimate_starts_at_default():
    throttle = TpmThrottle(max_tpm=30_000, default_estimate=8_000)
    assert throttle.rolling_estimate == 8_000


async def test_tpm_throttle_rolling_estimate_adapts_after_replacement():
    throttle = TpmThrottle(max_tpm=30_000, default_estimate=8_000)
    r = await throttle.throttle(8_000)
    throttle.replace_reservation(r, 5_000)
    assert throttle.rolling_estimate == 5_000
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_pipeline.py -k "tpm_throttle" -v -o "addopts="
```

Expected: `ImportError` — `TpmThrottle` not yet defined.

- [ ] **Step 3: Implement TpmThrottle**

At the top of `backend/app/adapters/extraction/pipeline.py`, add to imports:

```python
import time
from collections import deque
```

(`asyncio` is already imported.) Then add these two classes before `run_with_retry`:

```python
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
```

- [ ] **Step 4: Run to confirm pass**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_pipeline.py -k "tpm_throttle" -v -o "addopts="
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/adapters/extraction/pipeline.py backend/tests/adapters/extraction/test_pipeline.py
git commit -m "feat(extraction): add TpmThrottle sliding-window rate limiter"
```

---

### Task 2: Wire TpmThrottle into PipelineExtractor and the router

**Files:**
- Modify: `backend/app/adapters/extraction/pipeline.py` — `max_tokens_per_minute` param on `PipelineExtractor`; use throttle in `_run_chunk`; add `_extract_total_tokens` helper
- Modify: `backend/app/routers/extraction.py` — extract `maxTokensPerMinute` from chunking dict in `_maybe_wrap_pipeline`
- Modify: `backend/tests/adapters/extraction/test_pipeline.py` — integration test

**Interfaces:**
- Consumes: `TpmThrottle`, `_Reservation` from Task 1
- Produces: `PipelineExtractor(max_tokens_per_minute=30_000)` processes all chunks and returns correct merged output

- [ ] **Step 1: Write failing integration test**

Add to `backend/tests/adapters/extraction/test_pipeline.py`:

```python
async def test_pipeline_with_tpm_throttle_processes_all_chunks():
    """TPM throttle enabled with a high budget must not affect output correctness."""
    inner = _FakeInner()
    px = PipelineExtractor(
        inner=inner,
        preprocess=None,
        chunking={"strategy": "token_budget_pages", "config": {"maxInputTokens": 150}},
        max_tokens_per_minute=100_000,
    )
    out = await px.extract(_doc(3), _SCHEMA)
    assert len(inner.calls) == 3
    assert {p["sku"] for p in out.structured_data["products"]} == {"p0", "p1", "p2"}
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_pipeline.py::test_pipeline_with_tpm_throttle_processes_all_chunks -v -o "addopts="
```

Expected: `TypeError` — `PipelineExtractor.__init__` does not accept `max_tokens_per_minute`.

- [ ] **Step 3: Update PipelineExtractor**

In `backend/app/adapters/extraction/pipeline.py`, replace the `PipelineExtractor` class with:

```python
def _extract_total_tokens(output: ExtractionOutput) -> int:
    meta = output.extraction_metadata or {}
    usage = meta.get("usage") or {}
    return int(usage.get("total_tokens") or 0)


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
        max_tokens_per_minute: int | None = None,
    ) -> None:
        self._inner = inner
        self._preprocess = preprocess or []
        self._chunking = chunking or {}
        self._max_concurrency = max_concurrency
        self._max_retries = max_retries
        self._throttle: TpmThrottle | None = (
            TpmThrottle(max_tokens_per_minute) if max_tokens_per_minute else None
        )

    async def extract(
        self,
        parsed_document: Any,
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ExtractionOutput:
        cfg = dict(config or {})
        doc = apply_preprocess(parsed_document, self._preprocess)

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
            reservation = None
            estimated = 0
            if self._throttle is not None:
                estimated = self._throttle.rolling_estimate
                reservation = await self._throttle.throttle(estimated)
            async with sem:
                result = await run_with_retry(
                    lambda: self._inner.extract(chunk.document, schema, cfg),
                    self._max_retries,
                )
            if self._throttle is not None and reservation is not None:
                actual = _extract_total_tokens(result)
                self._throttle.replace_reservation(reservation, actual or estimated)
            return result

        results = await asyncio.gather(*[_run_chunk(c) for c in chunks])
        dedupe_key = self._chunking.get("config", {}).get("dedupeKey")
        return merge_outputs(list(results), schema, dedupe_key, chunks=chunks)
```

- [ ] **Step 4: Update _maybe_wrap_pipeline in the router**

In `backend/app/routers/extraction.py`, replace `_maybe_wrap_pipeline`:

```python
def _maybe_wrap_pipeline(
    inner: DataExtractor,
    preprocess: list[dict] | None,
    chunking: dict | None,
) -> DataExtractor:
    """Wrap inner extractor in a PipelineExtractor when pipeline config is present."""
    if not preprocess and not chunking:
        return inner
    max_tpm = (chunking or {}).get("maxTokensPerMinute")
    return PipelineExtractor(
        inner=inner,
        preprocess=preprocess,
        chunking=chunking,
        max_tokens_per_minute=int(max_tpm) if max_tpm is not None else None,
    )
```

- [ ] **Step 5: Run all pipeline tests**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_pipeline.py -v -o "addopts="
```

Expected: All tests PASS (existing + new).

- [ ] **Step 6: Commit**

```bash
git add backend/app/adapters/extraction/pipeline.py backend/app/routers/extraction.py backend/tests/adapters/extraction/test_pipeline.py
git commit -m "feat(extraction): wire TpmThrottle into PipelineExtractor and extraction router"
```

---

### Task 3: Frontend — type and UI field

**Files:**
- Modify: `frontend/src/types/extraction.ts` — add `maxTokensPerMinute?: number` to `ChunkingConfig`
- Modify: `frontend/src/components/extraction/ExtractionForm.tsx` — add state + input field in "Large document handling" collapsible

**Interfaces:**
- Consumes: updated `ChunkingConfig` from `extraction.ts`
- Produces: `chunking.maxTokensPerMinute` (integer, optional) included in `RunExtractionRequest` sent to `POST /extractions/run`

- [ ] **Step 1: Update ChunkingConfig type**

In `frontend/src/types/extraction.ts`, change `ChunkingConfig` to:

```typescript
export interface ChunkingConfig {
  strategy: string
  config?: Record<string, unknown>
  citationLevel?: 'auto' | 'full' | 'page_only' | 'off'
  maxTokensPerMinute?: number
}
```

- [ ] **Step 2: Add state variable to ExtractionForm**

In `frontend/src/components/extraction/ExtractionForm.tsx`, add alongside the other chunk-related state (near `dedupeKey`):

```typescript
const [maxTokensPerMinute, setMaxTokensPerMinute] = useState('')
```

- [ ] **Step 3: Wire maxTokensPerMinute into handleRun**

In `handleRun`, inside the `if (chunkStrategy !== 'none')` branch, the current chunking build is:

```typescript
chunking = { strategy: chunkStrategy, config: cfg, citationLevel }
```

Replace with:

```typescript
const tpm = parseInt(maxTokensPerMinute, 10)
chunking = {
  strategy: chunkStrategy,
  config: cfg,
  citationLevel,
  ...(!Number.isNaN(tpm) && tpm > 0 ? { maxTokensPerMinute: tpm } : {}),
}
```

- [ ] **Step 4: Add the UI field**

In `ExtractionForm.tsx`, inside the `{chunkStrategy === 'token_budget_pages' && (` block, the current grid is `grid-cols-3`. Change it to `grid-cols-2` and add a fourth row below (two columns each), or expand to `grid-cols-4` if screen width allows. The simplest addition: keep the existing `grid-cols-3` and add a new full-width row below it:

```tsx
{chunkStrategy === 'token_budget_pages' && (
  <>
    <div className="grid grid-cols-3 gap-3">
      <div className="space-y-1.5">
        <Label className="text-xs">Max input tokens</Label>
        <Input type="number" value={maxInputTokens} onChange={(e) => setMaxInputTokens(e.target.value)} className="h-9" />
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Page overlap</Label>
        <Input type="number" value={pageOverlap} onChange={(e) => setPageOverlap(e.target.value)} className="h-9" />
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Dedupe key</Label>
        <Input value={dedupeKey} onChange={(e) => setDedupeKey(e.target.value)} placeholder="e.g. sku" className="h-9" />
      </div>
    </div>
    <div className="space-y-1.5">
      <Label className="text-xs">Rate limit (TPM)</Label>
      <Input
        type="number"
        value={maxTokensPerMinute}
        onChange={(e) => setMaxTokensPerMinute(e.target.value)}
        placeholder="e.g. 30000 for OpenAI tier 1"
        className="h-9"
      />
    </div>
  </>
)}
```

- [ ] **Step 5: Build to verify no TypeScript errors**

```bash
npm --prefix frontend run build
```

Expected: Build exits 0 with no type errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/extraction.ts frontend/src/components/extraction/ExtractionForm.tsx
git commit -m "feat(extraction): add maxTokensPerMinute field to chunking config and extraction form"
```

---

## Self-Review

### Spec coverage

| Spec requirement | Task covering it |
|---|---|
| Sliding 60s window with eviction | Task 1 — `TpmThrottle._evict` |
| Async-safe (lock around check + reserve) | Task 1 — `asyncio.Lock` in `throttle()` |
| Pre-reservation before dispatch | Task 1 — `throttle()` returns `_Reservation`; appended to `_log` before lock releases |
| Replace estimate with actual after chunk | Task 1 — `replace_reservation` mutates `_Reservation.tokens` in-place |
| Rolling adaptive estimate (last 10) | Task 1 — `_actuals` list, capped at 10 |
| Oversized-chunk-fires-when-window-empty | Task 1 — `not self._log` condition in `throttle()` |
| No usage data → fall back to estimate | Task 2 — `actual or estimated` in `_run_chunk` |
| `None` = no throttling, preserves existing behaviour | Task 2 — `self._throttle = ... if max_tokens_per_minute else None` |
| Single-chunk fast-path bypasses throttle | Task 2 — `len(chunks) == 1` path calls `run_with_retry` directly, not `_run_chunk` |
| `maxTokensPerMinute` in `chunking` dict (API) | Task 2 — `_maybe_wrap_pipeline` extracts it |
| `ChunkingConfig` TypeScript type | Task 3 |
| Frontend input in chunking section | Task 3 |

### Placeholder scan

None found.

### Type consistency

- `_Reservation` defined Task 1, used as return type of `throttle()` and param of `replace_reservation()` — consistent across Tasks 1 and 2
- `TpmThrottle` defined Task 1, instantiated in Task 2 as `TpmThrottle(max_tokens_per_minute)` — consistent
- `_extract_total_tokens(result: ExtractionOutput) -> int` defined and called in Task 2 — consistent
- `ChunkingConfig.maxTokensPerMinute` added Task 3, consumed in `handleRun` Task 3 — consistent
