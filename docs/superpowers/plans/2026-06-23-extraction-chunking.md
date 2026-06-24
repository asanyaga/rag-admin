# Extraction Chunking & Composable Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make large-document LLM extraction reliable via token-budgeted chunking, configurable citation granularity, and rate-limit/truncation resilience, behind a composable per-run pipeline config.

**Architecture:** A new `PipelineExtractor` implements the existing `DataExtractor` port and wraps the unchanged `LLMExtractor`. Per call it runs preprocess → chunk → inner-extract-per-chunk (bounded concurrency + 429 backoff) → merge. Chunks are *derived* `ParsedDocument`s (immutable source untouched). Chunking strategies and preprocess stages are small registries mirroring the existing extractor registry.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2 (frozen CDM models), `anthropic` async SDK, pytest (`uv run python -m pytest -o "addopts="`).

## Global Constraints

- Backend tests run with: `uv run --directory backend python -m pytest -o "addopts=" <path> -v`
- Never use `cd X && Y`; use absolute paths or tool `--directory`/`-C` flags.
- CDM models (`backend/app/cdm/models.py`) are frozen (`extra="forbid"`); never mutate — derive with `model_copy(update=...)`.
- Absent `chunking`/`preprocess` config → behavior byte-identical to today.
- Data flow: router → service → adapter. Extractors implement `app.ports.data_extraction.DataExtractor`.
- Spec: `docs/superpowers/specs/2026-06-23-extraction-chunking-design.md`. Issue: #98.

---

## File Structure

- `backend/app/services/llm/types.py` — add `stop_reason` to `CompletionResult`; add `LLMRateLimitError`.
- `backend/app/services/llm/anthropic_adapter.py` — populate `stop_reason`; translate 429 to `LLMRateLimitError`.
- `backend/app/adapters/extraction/llm_context.py` — `augment_schema_with_sources(schema, level)`.
- `backend/app/adapters/extraction/llm.py` — read `citation_level`; truncation detection via `stop_reason`.
- `backend/app/adapters/extraction/chunking/base.py` — `DocumentChunk`, `ChunkStrategy`.
- `backend/app/adapters/extraction/chunking/token_budget.py` — `TokenBudgetPagesStrategy`, `estimate_tokens`.
- `backend/app/adapters/extraction/chunking/registry.py` — strategy catalogue.
- `backend/app/adapters/extraction/chunking/citation_policy.py` — `resolve_level`.
- `backend/app/adapters/extraction/chunking/merge.py` — `merge_outputs`.
- `backend/app/adapters/extraction/preprocess/base.py` — stage protocol + registry.
- `backend/app/adapters/extraction/preprocess/block_filter.py` — `block_filter` + `category_filter` seam.
- `backend/app/adapters/extraction/pipeline.py` — `PipelineExtractor`, `run_with_retry`.
- `backend/app/schemas/extraction_result.py` — `preprocess`/`chunking` request fields.
- `backend/app/routers/extraction.py` — build `PipelineExtractor` when pipeline config present.

---

## Task 1: `stop_reason` + typed rate-limit error

**Files:**
- Modify: `backend/app/services/llm/types.py`
- Modify: `backend/app/services/llm/anthropic_adapter.py`
- Test: `backend/tests/services/llm/test_anthropic_adapter.py`

**Interfaces:**
- Produces: `CompletionResult.stop_reason: str | None`; `class LLMRateLimitError(Exception)` with `.retry_after: float | None`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/services/llm/test_anthropic_adapter.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from anthropic import RateLimitError
from app.services.llm.anthropic_adapter import AnthropicAdapter
from app.services.llm.types import LLMConfig, LLMRateLimitError


def _fake_response(stop_reason="end_turn"):
    resp = MagicMock()
    resp.content = [MagicMock(text='{"ok": true}')]
    resp.usage = MagicMock(input_tokens=10, output_tokens=5)
    resp.stop_reason = stop_reason
    return resp


@pytest.mark.asyncio
async def test_complete_threads_stop_reason():
    adapter = AnthropicAdapter(api_key="k")
    adapter.client.messages.create = AsyncMock(return_value=_fake_response("max_tokens"))
    cfg = LLMConfig(provider="anthropic", model="claude-x", structured_output_mode="json_mode")
    result = await adapter.complete([{"role": "user", "content": "hi"}], cfg)
    assert result.stop_reason == "max_tokens"


@pytest.mark.asyncio
async def test_complete_translates_429():
    adapter = AnthropicAdapter(api_key="k")
    err = RateLimitError("rate", response=MagicMock(headers={"retry-after": "3"}), body=None)
    adapter.client.messages.create = AsyncMock(side_effect=err)
    cfg = LLMConfig(provider="anthropic", model="claude-x", structured_output_mode="json_mode")
    with pytest.raises(LLMRateLimitError) as exc:
        await adapter.complete([{"role": "user", "content": "hi"}], cfg)
    assert exc.value.retry_after == 3.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/llm/test_anthropic_adapter.py::test_complete_threads_stop_reason tests/services/llm/test_anthropic_adapter.py::test_complete_translates_429 -v`
Expected: FAIL (`CompletionResult` has no `stop_reason`; `LLMRateLimitError` undefined).

- [ ] **Step 3: Write minimal implementation**

In `backend/app/services/llm/types.py`, add field and error:

```python
@dataclass
class CompletionResult:
    """Full result from a non-streaming completion."""
    content: str
    usage: TokenUsage
    latency_ms: float
    model: str
    provider: str
    stop_reason: str | None = None


class LLMRateLimitError(Exception):
    """Raised when an LLM provider returns HTTP 429."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after
```

In `backend/app/services/llm/anthropic_adapter.py`, import and use. Update the imports line:

```python
from app.services.llm.types import (
    LLMConfig, TokenUsage, CompletionResult, StreamResponse, LLMConnectionError,
    LLMRateLimitError,
)
from anthropic import AsyncAnthropic, BadRequestError, APIConnectionError, RateLimitError
```

Wrap the `complete()` call site to translate 429 (add to the existing `try`/`except` around `self.client.messages.create`):

```python
        try:
            response = await self.client.messages.create(**kwargs)
        except RateLimitError as e:
            retry_after = None
            header = getattr(getattr(e, "response", None), "headers", {}) or {}
            if header.get("retry-after"):
                retry_after = float(header["retry-after"])
            raise LLMRateLimitError(str(e), retry_after=retry_after) from e
        except BadRequestError as e:
            retried = _strip_deprecated(kwargs, str(e))
            if retried is not None:
                logger.warning("Anthropic deprecated param stripped, retrying: %s", e)
                response = await self.client.messages.create(**retried)
            else:
                raise
        except APIConnectionError as exc:
            raise LLMConnectionError(str(exc)) from exc
```

Set `stop_reason` on the returned result:

```python
        return CompletionResult(
            content=content,
            usage=TokenUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            ),
            latency_ms=latency,
            model=config.model,
            provider="anthropic",
            stop_reason=getattr(response, "stop_reason", None),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/llm/test_anthropic_adapter.py -v`
Expected: PASS (existing tests still green; two new pass).

- [ ] **Step 5: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/services/llm/types.py backend/app/services/llm/anthropic_adapter.py backend/tests/services/llm/test_anthropic_adapter.py
git -C /c/Repos/rag-admin commit -m "feat(llm): thread stop_reason and typed 429 error through Anthropic adapter"
```

---

## Task 2: Citation-level schema augmentation + truncation detection

**Files:**
- Modify: `backend/app/adapters/extraction/llm_context.py`
- Modify: `backend/app/adapters/extraction/llm.py`
- Test: `backend/tests/adapters/extraction/test_llm_context.py` (create), `backend/tests/adapters/extraction/test_llm_extractor.py`

**Interfaces:**
- Consumes: `CompletionResult.stop_reason` (Task 1).
- Produces: `augment_schema_with_sources(schema, level="full")` where `level: Literal["full","page_only","off"]`; `LLMExtractor` reads `config["citation_level"]` (default `"full"`) and raises `ExtractionError` on `stop_reason == "max_tokens"`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/adapters/extraction/test_llm_context.py`:

```python
from app.adapters.extraction.llm_context import augment_schema_with_sources

_SCHEMA = {"type": "object", "properties": {"sku": {"type": "string"}}}


def test_full_level_includes_block_id():
    out = augment_schema_with_sources(_SCHEMA, level="full")
    props = out["properties"]["sku__source"]["properties"]
    assert "page_index" in props and "block_id" in props


def test_page_only_level_drops_block_id():
    out = augment_schema_with_sources(_SCHEMA, level="page_only")
    props = out["properties"]["sku__source"]["properties"]
    assert "page_index" in props and "block_id" not in props


def test_off_level_adds_no_sources():
    out = augment_schema_with_sources(_SCHEMA, level="off")
    assert "sku__source" not in out["properties"]
```

Add to `backend/tests/adapters/extraction/test_llm_extractor.py` (adapt the file's existing fixtures for a fake adapter that returns a `CompletionResult`):

```python
import pytest
from app.ports.data_extraction import ExtractionError
from app.services.llm.types import CompletionResult, TokenUsage


@pytest.mark.asyncio
async def test_truncated_response_raises_clear_error(make_extractor, parsed_doc, schema):
    # make_extractor builds an LLMExtractor whose adapter returns the given result
    truncated = CompletionResult(
        content='{"products": [', usage=TokenUsage(10, 4096, 4106),
        latency_ms=1.0, model="m", provider="anthropic", stop_reason="max_tokens",
    )
    extractor = make_extractor(truncated)
    with pytest.raises(ExtractionError) as exc:
        await extractor.extract(parsed_doc, schema, {"structured_output_mode": "json_mode"})
    assert "truncated" in str(exc.value).lower()
```

> If `make_extractor`/`parsed_doc`/`schema` fixtures do not exist, add them to the test module using a minimal fake adapter exposing `async def complete(self, messages, config)` that returns the injected `CompletionResult`, a `ParsedDocument` with one page/one block, and `{"type":"object","properties":{"products":{"type":"array","items":{"type":"object","properties":{"sku":{"type":"string"}}}}}}`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/test_llm_context.py tests/adapters/extraction/test_llm_extractor.py -v`
Expected: FAIL (`augment_schema_with_sources` takes no `level`; no truncation check).

- [ ] **Step 3: Write minimal implementation**

In `backend/app/adapters/extraction/llm_context.py`, thread a `level` through:

```python
from typing import Any, Literal

CitationLevel = Literal["full", "page_only", "off"]


def augment_schema_with_sources(
    schema: dict[str, Any], level: CitationLevel = "full"
) -> dict[str, Any]:
    """Add __source sibling fields to every leaf property in a JSON Schema."""
    if level == "off":
        return schema
    return _augment_recursive(schema, level)


def _augment_recursive(schema: dict[str, Any], level: CitationLevel) -> dict[str, Any]:
    if schema.get("type") == "object" and "properties" in schema:
        new_props: dict[str, Any] = {}
        new_required = list(schema.get("required") or [])

        for key, value in schema["properties"].items():
            new_props[key] = _augment_recursive(value, level)
            if value.get("type") not in ("object", "array"):
                source_key = f"{key}__source"
                new_props[source_key] = _source_schema(level)
                if source_key not in new_required:
                    new_required.append(source_key)

        result = {**schema, "properties": new_props, "additionalProperties": False}
        if new_required:
            result["required"] = new_required
        return result

    if schema.get("type") == "array" and "items" in schema:
        return {**schema, "items": _augment_recursive(schema["items"], level)}

    return schema


def _source_schema(level: CitationLevel) -> dict[str, Any]:
    if level == "page_only":
        return {
            "type": ["object", "null"],
            "properties": {"page_index": {"type": "integer"}},
            "required": ["page_index"],
            "additionalProperties": False,
        }
    return {
        "type": ["object", "null"],
        "properties": {
            "page_index": {"type": "integer"},
            "block_id": {"type": ["string", "null"]},
        },
        "required": ["page_index", "block_id"],
        "additionalProperties": False,
    }
```

In `backend/app/adapters/extraction/llm.py`, read the level and detect truncation. Replace the augment call and add the check after `result` is obtained:

```python
        citation_level = cfg.get("citation_level", "full")
        context = build_extraction_context(parsed_document, cfg.get("inject_block_ids", False))
        aug_schema = augment_schema_with_sources(schema, level=citation_level)
```

After `latency_ms = ...` and before `json.loads`:

```python
        if result.stop_reason == "max_tokens":
            raise ExtractionError(
                "LLM response truncated at max_tokens "
                f"(completion_tokens={result.usage.completion_tokens if result.usage else '?'}). "
                "Lower chunking maxInputTokens or raise max_tokens.",
                raw_response=result.content,
                metadata={
                    "model": llm_config.model,
                    "provider": llm_config.provider,
                    "latency_ms": latency_ms,
                    "stop_reason": result.stop_reason,
                },
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/test_llm_context.py tests/adapters/extraction/test_llm_extractor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/adapters/extraction/llm_context.py backend/app/adapters/extraction/llm.py backend/tests/adapters/extraction/test_llm_context.py backend/tests/adapters/extraction/test_llm_extractor.py
git -C /c/Repos/rag-admin commit -m "feat(extraction): citation-level schema augmentation + truncation detection"
```

---

## Task 3: `DocumentChunk` + `ChunkStrategy` base

**Files:**
- Create: `backend/app/adapters/extraction/chunking/__init__.py`
- Create: `backend/app/adapters/extraction/chunking/base.py`
- Test: `backend/tests/adapters/extraction/chunking/test_base.py` (and `__init__.py` for the test package)

**Interfaces:**
- Produces: `class DocumentChunk(document: ParsedDocument, chunk_index: int, page_indices: list[int])`; `class ChunkStrategy(Protocol)` with `split(self, parsed_doc, schema, config) -> list[DocumentChunk]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/adapters/extraction/chunking/__init__.py` (empty) and `backend/tests/adapters/extraction/chunking/test_base.py`:

```python
from app.adapters.extraction.chunking.base import DocumentChunk
from app.cdm.models import ParsedDocument


def _doc():
    return ParsedDocument(
        id="d1", source_document_id="s1", parse_run_id="p1",
        page_count=1, pages=[], blocks=[],
    )


def test_document_chunk_holds_derived_doc_and_indices():
    chunk = DocumentChunk(document=_doc(), chunk_index=0, page_indices=[0, 1])
    assert chunk.chunk_index == 0
    assert chunk.page_indices == [0, 1]
    assert chunk.document.parse_run_id == "p1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/chunking/test_base.py -v`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/adapters/extraction/chunking/__init__.py` (empty). Create `backend/app/adapters/extraction/chunking/base.py`:

```python
"""Chunking primitives: DocumentChunk view + strategy protocol."""
from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from app.cdm.models import ParsedDocument


class DocumentChunk(BaseModel):
    """A derived, non-destructive view over a slice of a ParsedDocument.

    `document` is built via ParsedDocument.model_copy; the source is never mutated.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    document: ParsedDocument
    chunk_index: int
    page_indices: list[int]


class ChunkStrategy(Protocol):
    """Splits a ParsedDocument into ordered DocumentChunks."""

    def split(
        self,
        parsed_doc: ParsedDocument,
        schema: dict[str, Any],
        config: dict[str, Any],
    ) -> list[DocumentChunk]:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/chunking/test_base.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/adapters/extraction/chunking/ backend/tests/adapters/extraction/chunking/
git -C /c/Repos/rag-admin commit -m "feat(chunking): add DocumentChunk view and ChunkStrategy protocol"
```

---

## Task 4: `token_budget_pages` splitter

**Files:**
- Create: `backend/app/adapters/extraction/chunking/token_budget.py`
- Test: `backend/tests/adapters/extraction/chunking/test_token_budget.py`

**Interfaces:**
- Consumes: `DocumentChunk` (Task 3); `ParsedDocument`, `Page`, `Block` (CDM).
- Produces: `estimate_tokens(text: str) -> int`; `TokenBudgetPagesStrategy(max_input_tokens, page_overlap=0)` with `.split(...)`. Each chunk's `document` is a derived `ParsedDocument` (subset pages+blocks, `page_count` recomputed, `derived_from`/`derivation` set).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/adapters/extraction/chunking/test_token_budget.py`:

```python
from app.adapters.extraction.chunking.token_budget import (
    TokenBudgetPagesStrategy, estimate_tokens,
)
from app.cdm.models import Block, BlockRole, Page, ParsedDocument


def _doc(n_pages: int, chars_per_page: int = 400) -> ParsedDocument:
    pages, blocks = [], []
    for i in range(n_pages):
        blocks.append(Block(
            id=f"b{i}", role=BlockRole.PARAGRAPH, native_type="text",
            text="x" * chars_per_page, markdown="x" * chars_per_page,
            page_index=i, reading_order=0,
        ))
        pages.append(Page(index=i, block_ids=[f"b{i}"]))
    return ParsedDocument(
        id="d1", source_document_id="s1", parse_run_id="p1",
        page_count=n_pages, pages=pages, blocks=blocks,
    )


def test_estimate_tokens_uses_char_quarter():
    assert estimate_tokens("x" * 400) == 100


def test_single_chunk_when_under_budget():
    strat = TokenBudgetPagesStrategy(max_input_tokens=10_000)
    chunks = strat.split(_doc(3), {}, {})
    assert len(chunks) == 1
    assert chunks[0].page_indices == [0, 1, 2]
    assert chunks[0].document.page_count == 3


def test_packs_pages_to_budget_without_splitting_a_page():
    # each page ~100 tokens; budget 250 -> 2 pages per chunk
    strat = TokenBudgetPagesStrategy(max_input_tokens=250)
    chunks = strat.split(_doc(5), {}, {})
    assert [c.page_indices for c in chunks] == [[0, 1], [2, 3], [4]]
    assert all(c.document.derived_from == "p1" for c in chunks)
    assert chunks[0].document.derivation == "chunk:pages=0-1"


def test_overlap_repeats_trailing_pages():
    strat = TokenBudgetPagesStrategy(max_input_tokens=250, page_overlap=1)
    chunks = strat.split(_doc(5), {}, {})
    assert [c.page_indices for c in chunks] == [[0, 1], [1, 2, 3], [3, 4]]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/chunking/test_token_budget.py -v`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/adapters/extraction/chunking/token_budget.py`:

```python
"""Token-budgeted page-packing chunk strategy."""
from __future__ import annotations

from typing import Any

from app.adapters.extraction.chunking.base import DocumentChunk
from app.cdm.models import Block, Page, ParsedDocument

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Cheap heuristic token estimate."""
    return len(text) // _CHARS_PER_TOKEN


def _page_tokens(doc: ParsedDocument, page_index: int) -> int:
    total = 0
    for block in doc.blocks:
        if block.page_index == page_index:
            total += estimate_tokens(block.markdown or block.text or "")
    return total


class TokenBudgetPagesStrategy:
    """Pack whole pages into chunks until an input-token budget is reached."""

    def __init__(self, max_input_tokens: int, page_overlap: int = 0) -> None:
        self.max_input_tokens = max_input_tokens
        self.page_overlap = page_overlap

    def split(
        self,
        parsed_doc: ParsedDocument,
        schema: dict[str, Any],
        config: dict[str, Any],
    ) -> list[DocumentChunk]:
        page_indices = sorted({p.index for p in parsed_doc.pages}) or \
            sorted({b.page_index for b in parsed_doc.blocks})
        if not page_indices:
            return [DocumentChunk(document=parsed_doc, chunk_index=0, page_indices=[])]

        groups: list[list[int]] = []
        current: list[int] = []
        current_tokens = 0
        for idx in page_indices:
            pt = _page_tokens(parsed_doc, idx)
            if current and current_tokens + pt > self.max_input_tokens:
                groups.append(current)
                overlap = current[-self.page_overlap:] if self.page_overlap else []
                current = list(overlap)
                current_tokens = sum(_page_tokens(parsed_doc, i) for i in current)
            current.append(idx)
            current_tokens += pt
        if current:
            groups.append(current)

        return [
            DocumentChunk(
                document=self._derive(parsed_doc, group),
                chunk_index=i,
                page_indices=group,
            )
            for i, group in enumerate(groups)
        ]

    @staticmethod
    def _derive(doc: ParsedDocument, page_group: list[int]) -> ParsedDocument:
        keep = set(page_group)
        pages = [p for p in doc.pages if p.index in keep]
        blocks = [b for b in doc.blocks if b.page_index in keep]
        return doc.model_copy(update={
            "pages": pages,
            "blocks": blocks,
            "page_count": len(pages) or len(keep),
            "derived_from": doc.parse_run_id,
            "derivation": f"chunk:pages={page_group[0]}-{page_group[-1]}",
        })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/chunking/test_token_budget.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/adapters/extraction/chunking/token_budget.py backend/tests/adapters/extraction/chunking/test_token_budget.py
git -C /c/Repos/rag-admin commit -m "feat(chunking): token-budgeted page-packing splitter"
```

---

## Task 5: Chunking strategy registry

**Files:**
- Create: `backend/app/adapters/extraction/chunking/registry.py`
- Test: `backend/tests/adapters/extraction/chunking/test_registry.py`

**Interfaces:**
- Consumes: `TokenBudgetPagesStrategy` (Task 4), `DocumentChunk` (Task 3).
- Produces: `get_chunk_strategies() -> list[dict]` (catalogue with `config_schema`); `build_strategy(name: str, config: dict) -> ChunkStrategy | None` (returns `None` for `"none"`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/adapters/extraction/chunking/test_registry.py`:

```python
import pytest
from app.adapters.extraction.chunking.registry import build_strategy, get_chunk_strategies
from app.adapters.extraction.chunking.token_budget import TokenBudgetPagesStrategy


def test_catalogue_lists_none_and_token_budget():
    names = {s["strategy"] for s in get_chunk_strategies()}
    assert {"none", "token_budget_pages"} <= names
    tb = next(s for s in get_chunk_strategies() if s["strategy"] == "token_budget_pages")
    assert "maxInputTokens" in tb["config_schema"]["properties"]


def test_build_none_returns_none():
    assert build_strategy("none", {}) is None


def test_build_token_budget_uses_config():
    strat = build_strategy("token_budget_pages", {"maxInputTokens": 5000, "pageOverlap": 2})
    assert isinstance(strat, TokenBudgetPagesStrategy)
    assert strat.max_input_tokens == 5000
    assert strat.page_overlap == 2


def test_build_unknown_raises():
    with pytest.raises(ValueError):
        build_strategy("nope", {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/chunking/test_registry.py -v`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/adapters/extraction/chunking/registry.py`:

```python
"""Chunking strategy catalogue + factory (mirrors the extractor registry)."""
from __future__ import annotations

from typing import Any

from app.adapters.extraction.chunking.base import ChunkStrategy
from app.adapters.extraction.chunking.token_budget import TokenBudgetPagesStrategy

_DEFAULT_MAX_INPUT_TOKENS = 8000


def get_chunk_strategies() -> list[dict]:
    return [
        {"strategy": "none", "name": "None (single-shot)",
         "description": "Send the whole document in one request.",
         "config_schema": {"type": "object", "properties": {}}},
        {"strategy": "token_budget_pages", "name": "Token-budgeted pages",
         "description": "Pack whole pages until an input-token budget is reached.",
         "config_schema": {
             "type": "object",
             "properties": {
                 "maxInputTokens": {"type": "integer", "default": _DEFAULT_MAX_INPUT_TOKENS},
                 "pageOverlap": {"type": "integer", "default": 0},
                 "dedupeKey": {"type": "string"},
             },
         }},
    ]


def build_strategy(name: str, config: dict[str, Any]) -> ChunkStrategy | None:
    if name == "none":
        return None
    if name == "token_budget_pages":
        return TokenBudgetPagesStrategy(
            max_input_tokens=int(config.get("maxInputTokens", _DEFAULT_MAX_INPUT_TOKENS)),
            page_overlap=int(config.get("pageOverlap", 0)),
        )
    raise ValueError(f"Unknown chunking strategy: {name!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/chunking/test_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/adapters/extraction/chunking/registry.py backend/tests/adapters/extraction/chunking/test_registry.py
git -C /c/Repos/rag-admin commit -m "feat(chunking): strategy registry with none + token_budget_pages"
```

---

## Task 6: Citation policy (`auto` resolution)

**Files:**
- Create: `backend/app/adapters/extraction/chunking/citation_policy.py`
- Test: `backend/tests/adapters/extraction/chunking/test_citation_policy.py`

**Interfaces:**
- Produces: `resolve_level(level: str, estimated_tokens: int) -> Literal["full","page_only","off"]`. Constant `AUTO_PAGE_ONLY_THRESHOLD_TOKENS`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/adapters/extraction/chunking/test_citation_policy.py`:

```python
from app.adapters.extraction.chunking.citation_policy import (
    AUTO_PAGE_ONLY_THRESHOLD_TOKENS, resolve_level,
)


def test_explicit_levels_pass_through():
    assert resolve_level("full", 1) == "full"
    assert resolve_level("page_only", 10**9) == "page_only"
    assert resolve_level("off", 1) == "off"


def test_auto_small_doc_is_full():
    assert resolve_level("auto", AUTO_PAGE_ONLY_THRESHOLD_TOKENS - 1) == "full"


def test_auto_large_doc_is_page_only_never_off():
    assert resolve_level("auto", AUTO_PAGE_ONLY_THRESHOLD_TOKENS + 1) == "page_only"
    assert resolve_level("auto", 10**9) == "page_only"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/chunking/test_citation_policy.py -v`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/adapters/extraction/chunking/citation_policy.py`:

```python
"""Resolve citation granularity, including size-based `auto`."""
from __future__ import annotations

from typing import Literal

CitationLevel = Literal["full", "page_only", "off"]

# Above this estimated document size, `auto` degrades to page-only provenance.
AUTO_PAGE_ONLY_THRESHOLD_TOKENS = 6000


def resolve_level(level: str, estimated_tokens: int) -> CitationLevel:
    """Map a requested level (incl. `auto`) to a concrete level.

    `auto` never selects `off`: provenance is only fully dropped on request.
    """
    if level in ("full", "page_only", "off"):
        return level  # type: ignore[return-value]
    if level == "auto":
        return "page_only" if estimated_tokens >= AUTO_PAGE_ONLY_THRESHOLD_TOKENS else "full"
    raise ValueError(f"Unknown citation level: {level!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/chunking/test_citation_policy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/adapters/extraction/chunking/citation_policy.py backend/tests/adapters/extraction/chunking/test_citation_policy.py
git -C /c/Repos/rag-admin commit -m "feat(chunking): citation-level policy with size-based auto"
```

---

## Task 7: Merge per-chunk outputs

**Files:**
- Create: `backend/app/adapters/extraction/chunking/merge.py`
- Test: `backend/tests/adapters/extraction/chunking/test_merge.py`

**Interfaces:**
- Consumes: `ExtractionOutput`, `FieldCitation` (`app.ports.data_extraction`).
- Produces: `merge_outputs(outputs: list[ExtractionOutput], schema: dict, dedupe_key: str | None) -> ExtractionOutput`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/adapters/extraction/chunking/test_merge.py`:

```python
from uuid import uuid4
from app.adapters.extraction.chunking.merge import merge_outputs
from app.ports.data_extraction import ExtractionOutput, FieldCitation

_RUN = uuid4()
_SCHEMA = {
    "type": "object",
    "properties": {
        "currency": {"type": "string"},
        "products": {"type": "array", "items": {"type": "object",
            "properties": {"sku": {"type": "string"}, "price": {"type": "number"}}}},
    },
}


def _out(data, citations=None):
    return ExtractionOutput(
        structured_data=data, source_parse_run_id=_RUN,
        citations=citations or [], provider_response_raw=None,
        extraction_metadata={"usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}},
    )


def test_arrays_concatenate_in_order():
    merged = merge_outputs(
        [_out({"products": [{"sku": "A"}]}), _out({"products": [{"sku": "B"}]})],
        _SCHEMA, dedupe_key=None,
    )
    assert [p["sku"] for p in merged.structured_data["products"]] == ["A", "B"]


def test_dedupe_key_removes_duplicate_records():
    merged = merge_outputs(
        [_out({"products": [{"sku": "A"}]}), _out({"products": [{"sku": "A"}, {"sku": "B"}]})],
        _SCHEMA, dedupe_key="sku",
    )
    assert [p["sku"] for p in merged.structured_data["products"]] == ["A", "B"]


def test_scalar_first_non_null_wins_and_records_conflict():
    merged = merge_outputs(
        [_out({"currency": None}), _out({"currency": "EUR"}), _out({"currency": "USD"})],
        _SCHEMA, dedupe_key=None,
    )
    assert merged.structured_data["currency"] == "EUR"
    conflicts = merged.extraction_metadata["scalarConflicts"]
    assert conflicts == [{"path": "currency", "kept": "EUR", "discarded": "USD"}]


def test_citations_repathed_to_merged_array_positions():
    c0 = FieldCitation(field_path="products[0].sku", page_index=1, block_ids=None, text_spans=None)
    c1 = FieldCitation(field_path="products[0].sku", page_index=4, block_ids=None, text_spans=None)
    merged = merge_outputs(
        [_out({"products": [{"sku": "A"}]}, [c0]),
         _out({"products": [{"sku": "B"}]}, [c1])],
        _SCHEMA, dedupe_key=None,
    )
    paths = sorted(c.field_path for c in merged.citations)
    assert paths == ["products[0].sku", "products[1].sku"]


def test_usage_is_summed():
    merged = merge_outputs([_out({"products": []}), _out({"products": []})], _SCHEMA, dedupe_key=None)
    assert merged.extraction_metadata["usage"]["total_tokens"] == 6
    assert merged.extraction_metadata["chunkCount"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/chunking/test_merge.py -v`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/adapters/extraction/chunking/merge.py`:

```python
"""Schema-guided merge of per-chunk extraction outputs."""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from app.ports.data_extraction import ExtractionOutput, FieldCitation

_ARRAY_HEAD_RE = re.compile(r"^([A-Za-z_][\w]*)\[(\d+)\]")


def merge_outputs(
    outputs: list[ExtractionOutput],
    schema: dict[str, Any],
    dedupe_key: str | None,
) -> ExtractionOutput:
    props = schema.get("properties") or {}
    array_fields = {k for k, v in props.items() if v.get("type") == "array"}

    merged_data: dict[str, Any] = {}
    scalar_conflicts: list[dict[str, Any]] = []
    # offset[field] = how many records already merged into that array
    offsets: dict[str, int] = {f: 0 for f in array_fields}
    citations: list[FieldCitation] = []
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for out in outputs:
        data = out.structured_data or {}
        # arrays: concat with optional dedupe
        for field in array_fields:
            incoming = data.get(field) or []
            bucket = merged_data.setdefault(field, [])
            base = offsets[field]
            added = 0
            for rec in incoming:
                if dedupe_key and isinstance(rec, dict):
                    if any(isinstance(e, dict) and e.get(dedupe_key) == rec.get(dedupe_key)
                           for e in bucket):
                        continue
                if not dedupe_key and rec in bucket:
                    continue
                bucket.append(rec)
                added += 1
            # citations for this chunk's array entries shift by `base`
            _repath_array_citations(out.citations or [], field, base, citations)
            offsets[field] = base + added

        # scalars / objects: first non-null wins
        for key, value in data.items():
            if key in array_fields:
                continue
            if value is None:
                continue
            if key not in merged_data or merged_data[key] is None:
                merged_data[key] = value
            elif merged_data[key] != value:
                scalar_conflicts.append(
                    {"path": key, "kept": merged_data[key], "discarded": value}
                )

        # non-array citations pass straight through
        for c in out.citations or []:
            if not _ARRAY_HEAD_RE.match(c.field_path):
                citations.append(c)

        u = ((out.extraction_metadata or {}).get("usage")) or {}
        for k in usage:
            usage[k] += int(u.get(k, 0) or 0)

    metadata: dict[str, Any] = {"usage": usage, "chunkCount": len(outputs)}
    if scalar_conflicts:
        metadata["scalarConflicts"] = scalar_conflicts

    return ExtractionOutput(
        structured_data=merged_data,
        source_parse_run_id=outputs[0].source_parse_run_id,
        citations=citations,
        provider_response_raw=None,
        extraction_metadata=metadata,
    )


def _repath_array_citations(
    chunk_citations: list[FieldCitation],
    field: str,
    base: int,
    out: list[FieldCitation],
) -> None:
    for c in chunk_citations:
        m = _ARRAY_HEAD_RE.match(c.field_path)
        if not m or m.group(1) != field:
            continue
        old_idx = int(m.group(2))
        new_path = f"{field}[{base + old_idx}]" + c.field_path[m.end():]
        out.append(replace(c, field_path=new_path))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/chunking/test_merge.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/adapters/extraction/chunking/merge.py backend/tests/adapters/extraction/chunking/test_merge.py
git -C /c/Repos/rag-admin commit -m "feat(chunking): schema-guided merge of per-chunk outputs"
```

---

## Task 8: Preprocess stages (`block_filter` + `category_filter` seam)

**Files:**
- Create: `backend/app/adapters/extraction/preprocess/__init__.py`
- Create: `backend/app/adapters/extraction/preprocess/base.py`
- Create: `backend/app/adapters/extraction/preprocess/block_filter.py`
- Test: `backend/tests/adapters/extraction/preprocess/__init__.py`, `backend/tests/adapters/extraction/preprocess/test_block_filter.py`

**Interfaces:**
- Consumes: `ParsedDocument`, `Block`, `BlockRole` (CDM).
- Produces: `apply_preprocess(doc, stages: list[dict]) -> ParsedDocument`; registry `get_preprocess_stages() -> list[dict]`. `block_filter` drops blocks whose `role` is in `config["drop"]`; `category_filter` raises `NotImplementedError`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/adapters/extraction/preprocess/__init__.py` (empty) and `backend/tests/adapters/extraction/preprocess/test_block_filter.py`:

```python
import pytest
from app.adapters.extraction.preprocess.base import apply_preprocess, get_preprocess_stages
from app.cdm.models import Block, BlockRole, Page, ParsedDocument


def _doc():
    blocks = [
        Block(id="h", role=BlockRole.HEADER, native_type="t", text="hdr", page_index=0),
        Block(id="p", role=BlockRole.PARAGRAPH, native_type="t", text="body", page_index=0),
        Block(id="f", role=BlockRole.FOOTER, native_type="t", text="ftr", page_index=0),
    ]
    return ParsedDocument(
        id="d1", source_document_id="s1", parse_run_id="p1",
        page_count=1, pages=[Page(index=0, block_ids=["h", "p", "f"])], blocks=blocks,
    )


def test_block_filter_drops_named_roles_preserves_order():
    out = apply_preprocess(_doc(), [{"stage": "block_filter", "config": {"drop": ["header", "footer"]}}])
    assert [b.id for b in out.blocks] == ["p"]
    assert out.parse_run_id == "p1"  # source identity preserved on derived doc


def test_empty_stages_returns_same_doc():
    doc = _doc()
    assert apply_preprocess(doc, []) is doc


def test_catalogue_lists_block_filter_and_category_filter():
    names = {s["stage"] for s in get_preprocess_stages()}
    assert {"block_filter", "category_filter"} <= names


def test_category_filter_not_implemented():
    with pytest.raises(NotImplementedError):
        apply_preprocess(_doc(), [{"stage": "category_filter", "config": {"categories": ["spec"]}}])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/preprocess/test_block_filter.py -v`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/adapters/extraction/preprocess/__init__.py` (empty). Create `backend/app/adapters/extraction/preprocess/block_filter.py`:

```python
"""Preprocess stages that drop blocks before extraction."""
from __future__ import annotations

from typing import Any

from app.cdm.models import ParsedDocument


def block_filter(doc: ParsedDocument, config: dict[str, Any]) -> ParsedDocument:
    """Return a derived doc with blocks of the named roles removed."""
    drop = {r.lower() for r in (config.get("drop") or [])}
    if not drop:
        return doc
    kept = [b for b in doc.blocks if b.role.value.lower() not in drop]
    return doc.model_copy(update={
        "blocks": kept,
        "derived_from": doc.parse_run_id,
        "derivation": "preprocess:block_filter",
    })


def category_filter(doc: ParsedDocument, config: dict[str, Any]) -> ParsedDocument:
    """SEAM (deferred): scope doc to pages/blocks in classification regions.

    Implemented in a follow-up spec; will read an upstream classificationRunId.
    """
    raise NotImplementedError(
        "category_filter is not yet implemented. It will scope the document to "
        "pages matching the configured categories using an upstream classification run."
    )
```

Create `backend/app/adapters/extraction/preprocess/base.py`:

```python
"""Preprocess stage registry + runner."""
from __future__ import annotations

from typing import Any, Callable

from app.adapters.extraction.preprocess.block_filter import block_filter, category_filter
from app.cdm.models import ParsedDocument

_STAGES: dict[str, Callable[[ParsedDocument, dict[str, Any]], ParsedDocument]] = {
    "block_filter": block_filter,
    "category_filter": category_filter,
}


def get_preprocess_stages() -> list[dict]:
    return [
        {"stage": "block_filter", "name": "Block filter",
         "description": "Drop blocks by role (headers, footers, page numbers, …).",
         "config_schema": {"type": "object", "properties": {
             "drop": {"type": "array", "items": {"type": "string"}}}}},
        {"stage": "category_filter", "name": "Category filter (coming soon)",
         "description": "Scope to pages in an upstream classification run's categories.",
         "config_schema": {"type": "object", "properties": {
             "classificationRunId": {"type": "string"},
             "categories": {"type": "array", "items": {"type": "string"}}}}},
    ]


def apply_preprocess(doc: ParsedDocument, stages: list[dict]) -> ParsedDocument:
    for stage in stages or []:
        name = stage.get("stage")
        fn = _STAGES.get(name)
        if fn is None:
            raise ValueError(f"Unknown preprocess stage: {name!r}")
        doc = fn(doc, stage.get("config") or {})
    return doc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/preprocess/test_block_filter.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/adapters/extraction/preprocess/ backend/tests/adapters/extraction/preprocess/
git -C /c/Repos/rag-admin commit -m "feat(extraction): block_filter preprocess stage + category_filter seam"
```

---

## Task 9: `PipelineExtractor` orchestrator (with retry + concurrency)

**Files:**
- Create: `backend/app/adapters/extraction/pipeline.py`
- Test: `backend/tests/adapters/extraction/test_pipeline.py`

**Interfaces:**
- Consumes: `DataExtractor`/`ExtractionOutput`/`ExtractionError` (port); `apply_preprocess` (Task 8); `build_strategy` (Task 5); `merge_outputs` (Task 7); `resolve_level` (Task 6); `estimate_tokens` (Task 4); `LLMRateLimitError` (Task 1).
- Produces: `PipelineExtractor(inner: DataExtractor, preprocess: list[dict] | None, chunking: dict | None, max_concurrency: int = 3, max_retries: int = 3)` implementing `DataExtractor`; `async run_with_retry(coro_factory, max_retries) -> Any`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/adapters/extraction/test_pipeline.py`:

```python
import asyncio
import pytest
from uuid import uuid4

from app.adapters.extraction.pipeline import PipelineExtractor
from app.ports.data_extraction import DataExtractor, ExtractionError, ExtractionOutput
from app.services.llm.types import LLMRateLimitError
from app.cdm.models import Block, BlockRole, Page, ParsedDocument

_RUN = uuid4()
_SCHEMA = {"type": "object", "properties": {
    "products": {"type": "array", "items": {"type": "object",
        "properties": {"sku": {"type": "string"}}}}}}


def _doc(n_pages: int, chars=400):
    pages, blocks = [], []
    for i in range(n_pages):
        blocks.append(Block(id=f"b{i}", role=BlockRole.PARAGRAPH, native_type="t",
                            text="x" * chars, markdown="x" * chars, page_index=i))
        pages.append(Page(index=i, block_ids=[f"b{i}"]))
    return ParsedDocument(id="d", source_document_id="s", parse_run_id=str(_RUN),
                          page_count=n_pages, pages=pages, blocks=blocks)


class _FakeInner(DataExtractor):
    extractor_type = "fake"

    def __init__(self, behavior=None):
        self.calls = []
        self._behavior = behavior or (lambda doc, cfg: ExtractionOutput(
            structured_data={"products": [{"sku": f"p{doc.pages[0].index}"}]},
            source_parse_run_id=_RUN, citations=[], provider_response_raw=None,
            extraction_metadata={"usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
        ))

    async def extract(self, parsed_document, schema, config=None):
        self.calls.append(config)
        return self._behavior(parsed_document, config or {})


@pytest.mark.asyncio
async def test_none_strategy_is_single_call_passthrough():
    inner = _FakeInner()
    px = PipelineExtractor(inner=inner, preprocess=None, chunking=None)
    out = await px.extract(_doc(3), _SCHEMA)
    assert len(inner.calls) == 1
    assert [p["sku"] for p in out.structured_data["products"]] == ["p0"]


@pytest.mark.asyncio
async def test_chunking_merges_multiple_chunks():
    inner = _FakeInner()
    px = PipelineExtractor(inner=inner, preprocess=None,
                           chunking={"strategy": "token_budget_pages",
                                     "config": {"maxInputTokens": 150}})
    out = await px.extract(_doc(3), _SCHEMA)
    assert len(inner.calls) == 3
    assert {p["sku"] for p in out.structured_data["products"]} == {"p0", "p1", "p2"}


@pytest.mark.asyncio
async def test_resolved_citation_level_passed_to_inner():
    inner = _FakeInner()
    px = PipelineExtractor(inner=inner, preprocess=None,
                           chunking={"strategy": "none", "citationLevel": "page_only"})
    await px.extract(_doc(1), _SCHEMA)
    assert inner.calls[0]["citation_level"] == "page_only"


@pytest.mark.asyncio
async def test_failed_chunk_fails_whole_extraction():
    def boom(doc, cfg):
        if doc.pages[0].index == 1:
            raise ExtractionError("truncated chunk")
        return ExtractionOutput(structured_data={"products": []}, source_parse_run_id=_RUN,
                                citations=[], provider_response_raw=None, extraction_metadata={})
    inner = _FakeInner(behavior=boom)
    px = PipelineExtractor(inner=inner, preprocess=None,
                           chunking={"strategy": "token_budget_pages", "config": {"maxInputTokens": 150}})
    with pytest.raises(ExtractionError):
        await px.extract(_doc(3), _SCHEMA)


@pytest.mark.asyncio
async def test_retries_on_rate_limit_then_succeeds():
    state = {"n": 0}
    def flaky(doc, cfg):
        state["n"] += 1
        if state["n"] == 1:
            raise LLMRateLimitError("429", retry_after=0)
        return ExtractionOutput(structured_data={"products": [{"sku": "ok"}]},
                                source_parse_run_id=_RUN, citations=[], provider_response_raw=None,
                                extraction_metadata={})
    inner = _FakeInner(behavior=flaky)
    px = PipelineExtractor(inner=inner, preprocess=None, chunking=None, max_retries=2)
    out = await px.extract(_doc(1), _SCHEMA)
    assert out.structured_data["products"] == [{"sku": "ok"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/test_pipeline.py -v`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/adapters/extraction/pipeline.py`:

```python
"""Composable extraction pipeline: preprocess -> chunk -> inner -> merge."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable
from uuid import UUID

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
        return merge_outputs(list(results), schema, dedupe_key)


def _doc_tokens(doc) -> int:
    return sum(estimate_tokens(b.markdown or b.text or "") for b in doc.blocks)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction/test_pipeline.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/adapters/extraction/pipeline.py backend/tests/adapters/extraction/test_pipeline.py
git -C /c/Repos/rag-admin commit -m "feat(extraction): PipelineExtractor orchestrator with retry + concurrency"
```

---

## Task 10: Request schema + router wiring

**Files:**
- Modify: `backend/app/schemas/extraction_result.py:64-73`
- Modify: `backend/app/routers/extraction.py:158-217`
- Test: `backend/tests/routers/test_extraction_pipeline_wiring.py` (create)

**Interfaces:**
- Consumes: `PipelineExtractor` (Task 9).
- Produces: `RunExtractionRequest.preprocess: list[dict] | None`, `RunExtractionRequest.chunking: dict | None`; router wraps the LLM extractor in `PipelineExtractor` when either is present.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/routers/test_extraction_pipeline_wiring.py`:

```python
from app.adapters.extraction.pipeline import PipelineExtractor
from app.adapters.extraction.llm import LLMExtractor
from app.routers.extraction import _maybe_wrap_pipeline   # helper added in Step 3


class _FakeAdapter:
    async def complete(self, messages, config):  # pragma: no cover - not called here
        raise AssertionError("not called")


def test_wrap_returns_pipeline_when_chunking_present():
    inner = LLMExtractor(adapter=_FakeAdapter(), provider="anthropic")
    wrapped = _maybe_wrap_pipeline(inner, preprocess=None,
                                   chunking={"strategy": "token_budget_pages", "config": {}})
    assert isinstance(wrapped, PipelineExtractor)


def test_wrap_returns_inner_when_no_pipeline_config():
    inner = LLMExtractor(adapter=_FakeAdapter(), provider="anthropic")
    assert _maybe_wrap_pipeline(inner, preprocess=None, chunking=None) is inner
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/routers/test_extraction_pipeline_wiring.py -v`
Expected: FAIL (`_maybe_wrap_pipeline` undefined).

- [ ] **Step 3: Write minimal implementation**

In `backend/app/schemas/extraction_result.py`, add fields to `RunExtractionRequest`:

```python
class RunExtractionRequest(BaseModel):
    """Request to run an extraction against a CDM ParsedDocument."""
    parse_run_id: UUID = Field(..., alias="parseRunId")
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")
    extraction_method: str = Field(..., alias="extractionMethod")
    config: dict | None = None
    llm_config: PromptConfig | None = Field(None, alias="llmConfig")
    user_prompt_template: str | None = Field(None, alias="userPromptTemplate")
    preprocess: list[dict] | None = None
    chunking: dict | None = None

    model_config = ConfigDict(populate_by_name=True)
```

In `backend/app/routers/extraction.py`, add the helper near the top (after imports):

```python
from app.adapters.extraction.pipeline import PipelineExtractor
from app.ports.data_extraction import DataExtractor


def _maybe_wrap_pipeline(
    inner: DataExtractor,
    preprocess: list[dict] | None,
    chunking: dict | None,
) -> DataExtractor:
    """Wrap inner extractor in a PipelineExtractor when pipeline config is present."""
    if not preprocess and not chunking:
        return inner
    return PipelineExtractor(inner=inner, preprocess=preprocess, chunking=chunking)
```

In `run_extraction`, after the `extractor` is built in both branches, wrap it before scheduling. Change the end of the `if body.extraction_method == "llm":` / `else:` block so that after `extractor = get_extractor(...)` you apply:

```python
        extractor = _maybe_wrap_pipeline(extractor, body.preprocess, body.chunking)
```

(Place this single line immediately before `result = await service.run_extraction(...)`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/routers/test_extraction_pipeline_wiring.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/schemas/extraction_result.py backend/app/routers/extraction.py backend/tests/routers/test_extraction_pipeline_wiring.py
git -C /c/Repos/rag-admin commit -m "feat(extraction): accept preprocess/chunking config and wire PipelineExtractor"
```

---

## Task 11: Full regression + lint gate

**Files:** none (verification only)

- [ ] **Step 1: Run the extraction-related suite**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/adapters/extraction tests/services/llm tests/routers/test_extraction_pipeline_wiring.py -v`
Expected: PASS (all green).

- [ ] **Step 2: Run the full backend suite**

Run: `uv run --directory backend python -m pytest -o "addopts="`
Expected: PASS (no regressions). Investigate any failure before proceeding.

- [ ] **Step 3: Commit any test-fixture adjustments** (only if Step 1/2 required touching shared fixtures)

```bash
git -C /c/Repos/rag-admin add -A
git -C /c/Repos/rag-admin commit -m "test(extraction): stabilize fixtures for chunking pipeline"
```

---

## Self-Review Notes

- **Spec coverage:** request shape (T10), token_budget_pages (T4), DocumentChunk derived view (T3/T4), strategy registry (T5), merge incl. scalarConflicts + citation re-path (T7), citation levels + auto (T2/T6), block_filter (T8), category_filter seam (T8), concurrency + 429 backoff (T9), truncation detection (T2), stop_reason (T1), PipelineExtractor implements port / background task unchanged (T9/T10), tests (every task). All spec sections map to a task.
- **Backward compatibility:** `_maybe_wrap_pipeline` returns the bare inner extractor when no pipeline config is present (T10); `citation_level` defaults to `"full"` (T2). No migration.
- **Type consistency:** `build_strategy` (T5) returns the `ChunkStrategy`/`None` consumed in T9; `merge_outputs(outputs, schema, dedupe_key)` signature matches T9's call; `resolve_level(level, estimated_tokens)` matches T9; `augment_schema_with_sources(schema, level)` matches T2 usage.
