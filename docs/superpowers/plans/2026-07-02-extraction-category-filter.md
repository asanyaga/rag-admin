# Extraction `category_filter` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optionally scope an LLM extraction run to the page/block regions of a completed classification run, completing the pre-existing `category_filter` preprocess seam.

**Architecture:** Resolve-then-filter. The extraction router resolves the user's `{classificationRunId, categories, granularity}` selection into a concrete keep-set (validating parse-run match, completion, and non-empty result — failing fast with HTTP 400/404) *before* building the pipeline. The pure `category_filter` preprocess stage then reconstructs a whole, self-consistent `ParsedDocument` from that keep-set. The frontend adds an optional filter section to the LLM extraction config.

**Tech Stack:** Python 3.12, FastAPI (async), SQLAlchemy 2.0, Pydantic v2 (`_Frozen` CDM models), pytest; React 18, TypeScript, Vite, vitest.

## Global Constraints

- Data flow: router → service → repository. Services/resolvers raise exceptions; routers map them to HTTP responses (`NotFoundError`→404, `ValueError`→400 are already wired in `routers/extraction.py`).
- Preprocess stages are **pure functions** `(doc: ParsedDocument, config: dict) -> ParsedDocument` — no DB/IO access.
- All DB operations async with type hints.
- CDM models are frozen Pydantic models (`_Frozen`); derive new instances with `.model_copy(update={...})`.
- Page numbering: **preserve original page indices** (never renumber); `page_count` = number of retained pages.
- Strict parse-run coupling: only classification runs with `status == "completed"` and `parse_run_id == extraction parse_run_id` are eligible.
- TDD: write the failing test first, watch it fail, implement minimally, watch it pass, commit.
- Backend test command: `cd backend && uv run python -m pytest -o "addopts=" <path> -v`
- Frontend test command: `cd frontend && npx vitest run <path>`

---

### Task 1: `category_filter` pure function + reconstruction

**Files:**
- Create: `backend/app/adapters/extraction/preprocess/category_filter.py`
- Modify: `backend/app/adapters/extraction/preprocess/base.py` (import + catalogue entry)
- Modify: `backend/app/adapters/extraction/preprocess/block_filter.py` (remove the `category_filter` stub)
- Test: `backend/tests/adapters/extraction/preprocess/test_category_filter.py`
- Modify test: `backend/tests/adapters/extraction/preprocess/test_block_filter.py` (drop the `test_category_filter_not_implemented` test)

**Interfaces:**
- Consumes: nothing from other tasks. Reads resolved config keys `keepPages: list[int]`, `keepBlockIds: list[str]`, and (for provenance) `categories: list[str]`.
- Produces: `category_filter(doc: ParsedDocument, config: dict[str, Any]) -> ParsedDocument`, registered under stage name `"category_filter"`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/adapters/extraction/preprocess/test_category_filter.py`:

```python
from app.adapters.extraction.preprocess.base import apply_preprocess
from app.cdm.models import Block, BlockRole, Page, ParsedDocument


def _doc():
    blocks = [
        Block(id="a", role=BlockRole.TEXT, native_type="t", text="alpha", markdown="alpha", page_index=0),
        Block(id="b", role=BlockRole.TEXT, native_type="t", text="bravo", markdown="bravo", page_index=1),
        Block(id="c", role=BlockRole.TEXT, native_type="t", text="charlie", markdown="charlie", page_index=1),
        Block(id="d", role=BlockRole.TEXT, native_type="t", text="delta", markdown="delta", page_index=2),
    ]
    return ParsedDocument(
        id="d1", source_document_id="s1", parse_run_id="p1",
        page_count=3,
        pages=[
            Page(index=0, block_ids=["a"]),
            Page(index=1, block_ids=["b", "c"]),
            Page(index=2, block_ids=["d"]),
        ],
        blocks=blocks,
        full_text="alpha\n\nbravo\n\ncharlie\n\ndelta",
        full_markdown="alpha\n\nbravo\n\ncharlie\n\ndelta",
    )


def _run(config):
    return apply_preprocess(_doc(), [{"stage": "category_filter", "config": config}])


def test_page_mode_keeps_whole_pages_and_reconstructs():
    out = _run({"keepPages": [1], "keepBlockIds": [], "categories": ["fin"]})
    assert [b.id for b in out.blocks] == ["b", "c"]
    assert [p.index for p in out.pages] == [1]           # original index preserved (sparse)
    assert out.pages[0].block_ids == ["b", "c"]
    assert out.page_count == 1
    assert out.full_markdown == "bravo\n\ncharlie"        # regenerated from kept blocks
    assert out.full_text == "bravo\n\ncharlie"
    assert out.blocks[0].page_index == 1                  # original page_index preserved
    assert out.derived_from == "p1"
    assert out.derivation == "preprocess:category_filter"
    assert any(l.name == "fin" and l.source == "classifier" for l in out.labels)


def test_block_mode_keeps_named_blocks_across_pages():
    out = _run({"keepPages": [], "keepBlockIds": ["a", "c"], "categories": ["x"]})
    assert [b.id for b in out.blocks] == ["a", "c"]
    assert [p.index for p in out.pages] == [0, 1]         # pages 0 and 1 retained
    assert out.pages[1].block_ids == ["c"]                # 'b' pruned from page 1
    assert out.page_count == 2


def test_block_mode_with_page_fallback_union():
    # keepBlockIds from attributed regions + keepPages from a fallback region
    out = _run({"keepPages": [2], "keepBlockIds": ["a"], "categories": ["x"]})
    assert [b.id for b in out.blocks] == ["a", "d"]
    assert [p.index for p in out.pages] == [0, 2]


def test_empty_keepset_yields_empty_doc():
    out = _run({"keepPages": [], "keepBlockIds": [], "categories": []})
    assert out.blocks == []
    assert out.pages == []
    assert out.page_count == 0
    assert out.full_markdown is None
```

Also delete the now-obsolete test in `backend/tests/adapters/extraction/preprocess/test_block_filter.py`:

```python
def test_category_filter_not_implemented():
    with pytest.raises(NotImplementedError):
        apply_preprocess(_doc(), [{"stage": "category_filter", "config": {"categories": ["spec"]}}])
```

(Remove that function. Keep `test_catalogue_lists_block_filter_and_category_filter`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/adapters/extraction/preprocess/test_category_filter.py -v`
Expected: FAIL — `category_filter` still raises `NotImplementedError` (imported from `block_filter`).

- [ ] **Step 3: Create the `category_filter` module**

Create `backend/app/adapters/extraction/preprocess/category_filter.py`:

```python
"""Preprocess stage: reconstruct a whole ParsedDocument scoped to a keep-set.

Config is produced by resolve_category_filter_stages (services.classification):
it carries the original selection (classificationRunId, categories, granularity)
plus the resolved keepPages / keepBlockIds. This function is pure — no DB access.
"""
from __future__ import annotations

from typing import Any

from app.cdm.models import Label, ParsedDocument


def category_filter(doc: ParsedDocument, config: dict[str, Any]) -> ParsedDocument:
    keep_pages = {int(p) for p in (config.get("keepPages") or [])}
    keep_block_ids = {str(b) for b in (config.get("keepBlockIds") or [])}

    kept = [
        b for b in doc.blocks
        if b.page_index in keep_pages or str(b.id) in keep_block_ids
    ]
    kept_ids = {str(b.id) for b in kept}
    kept_page_indices = {b.page_index for b in kept}

    pages = [
        p.model_copy(update={"block_ids": [bid for bid in p.block_ids if bid in kept_ids]})
        for p in doc.pages
        if p.index in kept_page_indices
    ]

    full_markdown = "\n\n".join(
        (b.markdown if b.markdown else b.text) for b in kept if (b.markdown or b.text)
    ) or None
    full_text = "\n\n".join(b.text for b in kept if b.text) or None

    categories = config.get("categories") or []
    labels = list(doc.labels) + [
        Label(name=c, scope="document", source="classifier") for c in categories
    ]

    return doc.model_copy(update={
        "blocks": kept,
        "pages": pages,
        "page_count": len(pages),
        "full_markdown": full_markdown,
        "full_text": full_text,
        "labels": labels,
        "derived_from": doc.parse_run_id,
        "derivation": "preprocess:category_filter",
    })
```

- [ ] **Step 4: Remove the stub and wire the registry**

In `backend/app/adapters/extraction/preprocess/block_filter.py`, delete the `category_filter` function (the `NotImplementedError` stub) entirely — leave `block_filter` untouched.

In `backend/app/adapters/extraction/preprocess/base.py`, update the imports and catalogue:

```python
from app.adapters.extraction.preprocess.block_filter import block_filter
from app.adapters.extraction.preprocess.category_filter import category_filter
```

```python
{"stage": "category_filter", "name": "Category filter",
 "description": "Scope extraction to pages/blocks in an upstream classification run's categories.",
 "config_schema": {"type": "object", "properties": {
     "classificationRunId": {"type": "string"},
     "categories": {"type": "array", "items": {"type": "string"}},
     "granularity": {"type": "string", "enum": ["page", "block"], "default": "page"}}}},
```

(The `_STAGES` dict entry `"category_filter": category_filter` already exists — the import now resolves to the new module.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/adapters/extraction/preprocess/ -v`
Expected: PASS (new `test_category_filter.py` + existing `test_block_filter.py` without the removed test).

- [ ] **Step 6: Commit**

```bash
git add backend/app/adapters/extraction/preprocess/ backend/tests/adapters/extraction/preprocess/
git commit -m "feat(extraction): implement category_filter preprocess stage"
```

---

### Task 2: `resolve_category_filter_stages` resolver

**Files:**
- Create: `backend/app/services/classification/category_filter_resolver.py`
- Test: `backend/tests/services/classification/test_category_filter_resolver.py`

**Interfaces:**
- Consumes: `ClassificationRunRepository` (`async get(run_id) -> run|None` where `run.status: str`, `run.parse_run_id: UUID`; `async get_regions(run_id) -> list[ClassificationRegion]` where each region has `.label: str`, `.page_start: int`, `.page_end: int`, `.block_ids: list[str]`).
- Produces:
  ```python
  async def resolve_category_filter_stages(
      preprocess: list[dict] | None,
      parse_run_id: UUID,
      repo: ClassificationRunRepository,
  ) -> tuple[list[dict], dict | None]
  ```
  Returns `(resolved_preprocess, applied_filter_summary)`. Each `category_filter` stage's config is augmented with `keepPages: list[int]` and `keepBlockIds: list[str]`. Summary shape: `{classificationRunId, categories, granularity, keptPages, keptBlocks}` or `None` when no `category_filter` stage present.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/services/classification/test_category_filter_resolver.py`:

```python
from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.services.classification.category_filter_resolver import resolve_category_filter_stages
from app.services.exceptions import NotFoundError


@dataclass
class _Region:
    label: str
    page_start: int
    page_end: int
    block_ids: list


@dataclass
class _Run:
    status: str
    parse_run_id: object


class _Repo:
    def __init__(self, run, regions):
        self._run = run
        self._regions = regions

    async def get(self, run_id):
        return self._run

    async def get_regions(self, run_id):
        return self._regions


def _stage(run_id, categories, granularity):
    return [{"stage": "category_filter", "config": {
        "classificationRunId": str(run_id), "categories": categories, "granularity": granularity}}]


@pytest.mark.asyncio
async def test_no_category_filter_stage_returns_none_summary():
    pre = [{"stage": "block_filter", "config": {"drop": ["header"]}}]
    resolved, summary = await resolve_category_filter_stages(pre, uuid4(), _Repo(None, []))
    assert resolved == pre
    assert summary is None


@pytest.mark.asyncio
async def test_page_mode_resolves_page_union():
    parse_id = uuid4()
    run = _Run(status="completed", parse_run_id=parse_id)
    regions = [_Region("fin", 1, 2, ["b"]), _Region("other", 5, 5, ["z"])]
    resolved, summary = await resolve_category_filter_stages(
        _stage(uuid4(), ["fin"], "page"), parse_id, _Repo(run, regions))
    cfg = resolved[0]["config"]
    assert cfg["keepPages"] == [1, 2]
    assert cfg["keepBlockIds"] == []
    assert summary["keptPages"] == 2 and summary["keptBlocks"] == 0


@pytest.mark.asyncio
async def test_block_mode_resolves_block_ids_with_page_fallback():
    parse_id = uuid4()
    run = _Run(status="completed", parse_run_id=parse_id)
    regions = [_Region("fin", 1, 1, ["b", "c"]), _Region("fin", 4, 5, [])]  # 2nd has no blocks
    resolved, _ = await resolve_category_filter_stages(
        _stage(uuid4(), ["fin"], "block"), parse_id, _Repo(run, regions))
    cfg = resolved[0]["config"]
    assert cfg["keepBlockIds"] == ["b", "c"]
    assert cfg["keepPages"] == [4, 5]


@pytest.mark.asyncio
async def test_missing_run_raises_not_found():
    with pytest.raises(NotFoundError):
        await resolve_category_filter_stages(
            _stage(uuid4(), ["fin"], "page"), uuid4(), _Repo(None, []))


@pytest.mark.asyncio
async def test_not_completed_raises_value_error():
    run = _Run(status="running", parse_run_id=uuid4())
    with pytest.raises(ValueError):
        await resolve_category_filter_stages(
            _stage(uuid4(), ["fin"], "page"), run.parse_run_id, _Repo(run, []))


@pytest.mark.asyncio
async def test_parse_run_mismatch_raises_value_error():
    run = _Run(status="completed", parse_run_id=uuid4())
    with pytest.raises(ValueError):
        await resolve_category_filter_stages(
            _stage(uuid4(), ["fin"], "page"), uuid4(), _Repo(run, []))


@pytest.mark.asyncio
async def test_empty_match_raises_value_error():
    parse_id = uuid4()
    run = _Run(status="completed", parse_run_id=parse_id)
    regions = [_Region("other", 1, 1, ["z"])]
    with pytest.raises(ValueError):
        await resolve_category_filter_stages(
            _stage(uuid4(), ["fin"], "page"), parse_id, _Repo(run, regions))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/classification/test_category_filter_resolver.py -v`
Expected: FAIL — module `category_filter_resolver` does not exist.

- [ ] **Step 3: Implement the resolver**

Create `backend/app/services/classification/category_filter_resolver.py`:

```python
"""Resolve category_filter preprocess stages into concrete keep-sets.

Runs at extraction request time (router layer) so misconfiguration fails fast
with HTTP 400/404 before any LLM tokens are spent. Keeps the preprocess stage
itself a pure function.
"""
from __future__ import annotations

from uuid import UUID

from app.repositories.classification_run_repository import ClassificationRunRepository
from app.services.exceptions import NotFoundError


async def resolve_category_filter_stages(
    preprocess: list[dict] | None,
    parse_run_id: UUID,
    repo: ClassificationRunRepository,
) -> tuple[list[dict], dict | None]:
    if not preprocess:
        return preprocess or [], None

    resolved: list[dict] = []
    summary: dict | None = None

    for stage in preprocess:
        if stage.get("stage") != "category_filter":
            resolved.append(stage)
            continue

        cfg = dict(stage.get("config") or {})
        run_id_raw = cfg.get("classificationRunId")
        if not run_id_raw:
            raise ValueError("category_filter requires classificationRunId")
        categories = cfg.get("categories") or []
        if not categories:
            raise ValueError("category_filter requires at least one category")
        granularity = cfg.get("granularity") or "page"
        if granularity not in ("page", "block"):
            raise ValueError(f"Invalid category_filter granularity: {granularity!r}")

        run_id = UUID(str(run_id_raw))
        run = await repo.get(run_id)
        if run is None:
            raise NotFoundError(f"Classification run {run_id} not found")
        if run.status != "completed":
            raise ValueError(
                f"Classification run {run_id} is not completed (status={run.status})"
            )
        if str(run.parse_run_id) != str(parse_run_id):
            raise ValueError(
                "Classification run was produced from a different parse; "
                "its page/block IDs would not align with this extraction"
            )

        wanted = set(categories)
        selected = [r for r in await repo.get_regions(run_id) if r.label in wanted]

        keep_pages: set[int] = set()
        keep_block_ids: set[str] = set()
        if granularity == "page":
            for r in selected:
                keep_pages.update(range(r.page_start, r.page_end + 1))
        else:
            for r in selected:
                if r.block_ids:
                    keep_block_ids.update(str(b) for b in r.block_ids)
                else:
                    keep_pages.update(range(r.page_start, r.page_end + 1))

        if not keep_pages and not keep_block_ids:
            raise ValueError(
                f"Selected categories matched no content in classification run {run_id}"
            )

        cfg["keepPages"] = sorted(keep_pages)
        cfg["keepBlockIds"] = sorted(keep_block_ids)
        resolved.append({"stage": "category_filter", "config": cfg})
        summary = {
            "classificationRunId": str(run_id),
            "categories": list(categories),
            "granularity": granularity,
            "keptPages": len(keep_pages),
            "keptBlocks": len(keep_block_ids),
        }

    return resolved, summary
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/classification/test_category_filter_resolver.py -v`
Expected: PASS (all 7 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/classification/category_filter_resolver.py backend/tests/services/classification/test_category_filter_resolver.py
git commit -m "feat(extraction): add category_filter resolver with strict parse-run validation"
```

---

### Task 3: Wire the resolver into the extraction router

**Files:**
- Modify: `backend/app/routers/extraction.py` (imports + `run_extraction` handler, ~lines 217-228)
- Test: `backend/tests/routers/test_extraction_pipeline_wiring.py`

**Interfaces:**
- Consumes: `resolve_category_filter_stages(preprocess, parse_run_id, repo)` from Task 2; `ClassificationRunRepository`.
- Produces: resolved preprocess passed to `_maybe_wrap_pipeline`; `applied_filter` summary folded into the persisted `config`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/routers/test_extraction_pipeline_wiring.py` (mirror the existing test style in that file for constructing the request/app; adapt fixture names to those already present):

```python
import pytest


@pytest.mark.asyncio
async def test_category_filter_mismatched_parse_run_returns_400(async_client, seed_llm_extraction):
    """A category_filter referencing a run from a different parse fails fast (400), no dispatch."""
    ctx = seed_llm_extraction  # provides: document, parse_run_id, schema_id, and a completed
                               # classification run bound to a DIFFERENT parse_run_id -> run_id
    resp = await async_client.post("/extractions/run", json={
        "parseRunId": str(ctx.parse_run_id),
        "extractionSchemaId": str(ctx.schema_id),
        "extractionMethod": "llm",
        "llmConfig": ctx.llm_config,
        "preprocess": [{
            "stage": "category_filter",
            "config": {"classificationRunId": str(ctx.other_parse_run_classification_id),
                       "categories": ["fin"], "granularity": "page"},
        }],
    })
    assert resp.status_code == 400
    assert "different parse" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_category_filter_empty_match_returns_400(async_client, seed_llm_extraction):
    ctx = seed_llm_extraction  # completed run on SAME parse_run_id, but no regions for "nope"
    resp = await async_client.post("/extractions/run", json={
        "parseRunId": str(ctx.parse_run_id),
        "extractionSchemaId": str(ctx.schema_id),
        "extractionMethod": "llm",
        "llmConfig": ctx.llm_config,
        "preprocess": [{
            "stage": "category_filter",
            "config": {"classificationRunId": str(ctx.same_parse_run_classification_id),
                       "categories": ["nope"], "granularity": "page"},
        }],
    })
    assert resp.status_code == 400
    assert "matched no content" in resp.json()["detail"]
```

> Note for the implementer: `test_extraction_pipeline_wiring.py` already sets up an app/client and seeds parse runs + schemas. Extend its existing fixture (or add a `seed_llm_extraction` fixture beside it) to also create a completed `ClassificationRun` + `ClassificationRegion` rows — one bound to the same `parse_run_id`, one to a different `parse_run_id`. Use `ClassificationRunRepository` / `ClassificationRegion` ORM directly, matching `tests/repositories/test_classification_run_repository.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/routers/test_extraction_pipeline_wiring.py -v -k category_filter`
Expected: FAIL — resolver not wired; request currently succeeds (202) or errors differently.

- [ ] **Step 3: Wire the resolver into the router**

In `backend/app/routers/extraction.py`, add imports near the other service/repo imports:

```python
from app.repositories.classification_run_repository import ClassificationRunRepository
from app.services.classification.category_filter_resolver import resolve_category_filter_stages
```

In the `run_extraction` handler, replace the block that wraps the pipeline and calls the service (currently lines ~217-228):

```python
        resolved_preprocess, applied_filter = await resolve_category_filter_stages(
            body.preprocess, body.parse_run_id, ClassificationRunRepository(db)
        )
        extractor = _maybe_wrap_pipeline(extractor, resolved_preprocess, body.chunking)

        run_config = dict(body.config or {})
        if applied_filter is not None:
            run_config["applied_filter"] = applied_filter

        result = await service.run_extraction(
            parse_run_id=body.parse_run_id,
            extraction_schema_id=body.extraction_schema_id,
            extraction_method=body.extraction_method,
            user_id=current_user.id,
            config=run_config,
            llm_config=body.llm_config,
            user_prompt_template=body.user_prompt_template,
            timeout_minutes=body.timeout_minutes,
        )
```

The existing `except NotFoundError → 404` / `except ValueError → 400` handlers at the end of the function already cover the resolver's error contract — no new handlers needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/routers/test_extraction_pipeline_wiring.py -v`
Expected: PASS (new category_filter tests + existing wiring tests unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/extraction.py backend/tests/routers/test_extraction_pipeline_wiring.py
git commit -m "feat(extraction): resolve category_filter in run_extraction router"
```

---

### Task 4: Frontend hook — compose the `category_filter` stage

**Files:**
- Create: `frontend/src/hooks/useCategoryFilter.ts`
- Test: `frontend/src/hooks/useCategoryFilter.test.ts`

**Interfaces:**
- Consumes: `ClassificationRun` (`{ id, parseRunId, status, regions: { label }[] }`) from `@/types/classification`; `PreprocessStage` from `@/types/extraction`.
- Produces:
  ```ts
  interface CategoryFilterState {
    eligibleRun: ClassificationRun | null
    availableCategories: string[]
    selectedCategories: string[]
    granularity: 'page' | 'block'
    setSelectedCategories: (c: string[]) => void
    setGranularity: (g: 'page' | 'block') => void
    toPreprocessStage: () => PreprocessStage | null
  }
  function useCategoryFilter(runs: ClassificationRun[], parseRunId: string | null): CategoryFilterState
  ```
  `toPreprocessStage()` returns `null` when no eligible run or no categories selected; otherwise `{ stage: 'category_filter', config: { classificationRunId, categories, granularity } }`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/hooks/useCategoryFilter.test.ts`:

```ts
import { renderHook, act } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useCategoryFilter } from './useCategoryFilter'
import type { ClassificationRun } from '@/types/classification'

function run(overrides: Partial<ClassificationRun>): ClassificationRun {
  return {
    id: 'r1', parseRunId: 'p1', documentId: 'd1', labelsRequested: [],
    classifierType: 'llm', classifierConfig: {}, status: 'completed',
    error: null, inputTokens: 0, outputTokens: 0, durationMs: 0,
    createdAt: '', regions: [{ label: 'fin' } as never, { label: 'legal' } as never],
    ...overrides,
  } as ClassificationRun
}

describe('useCategoryFilter', () => {
  it('picks the latest completed run matching the parse and exposes its categories', () => {
    const runs = [
      run({ id: 'old', parseRunId: 'p1', status: 'completed' }),
      run({ id: 'wrongparse', parseRunId: 'pX', status: 'completed' }),
      run({ id: 'notdone', parseRunId: 'p1', status: 'running' }),
    ]
    const { result } = renderHook(() => useCategoryFilter(runs, 'p1'))
    expect(result.current.eligibleRun?.id).toBe('old')
    expect(result.current.availableCategories).toEqual(['fin', 'legal'])
    expect(result.current.granularity).toBe('page')
  })

  it('returns null stage when nothing selected, and composes a stage when selected', () => {
    const runs = [run({ id: 'r1', parseRunId: 'p1' })]
    const { result } = renderHook(() => useCategoryFilter(runs, 'p1'))
    expect(result.current.toPreprocessStage()).toBeNull()
    act(() => result.current.setSelectedCategories(['fin']))
    expect(result.current.toPreprocessStage()).toEqual({
      stage: 'category_filter',
      config: { classificationRunId: 'r1', categories: ['fin'], granularity: 'page' },
    })
  })

  it('has no eligible run when parseRunId is null', () => {
    const runs = [run({ id: 'r1', parseRunId: 'p1' })]
    const { result } = renderHook(() => useCategoryFilter(runs, null))
    expect(result.current.eligibleRun).toBeNull()
    expect(result.current.toPreprocessStage()).toBeNull()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/hooks/useCategoryFilter.test.ts`
Expected: FAIL — `useCategoryFilter` does not exist.

- [ ] **Step 3: Implement the hook**

Create `frontend/src/hooks/useCategoryFilter.ts`:

```ts
import { useMemo, useState } from 'react'
import type { ClassificationRun } from '@/types/classification'
import type { PreprocessStage } from '@/types/extraction'

export interface CategoryFilterState {
  eligibleRun: ClassificationRun | null
  availableCategories: string[]
  selectedCategories: string[]
  granularity: 'page' | 'block'
  setSelectedCategories: (c: string[]) => void
  setGranularity: (g: 'page' | 'block') => void
  toPreprocessStage: () => PreprocessStage | null
}

export function useCategoryFilter(
  runs: ClassificationRun[],
  parseRunId: string | null,
): CategoryFilterState {
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])
  const [granularity, setGranularity] = useState<'page' | 'block'>('page')

  // runs arrive newest-first (see useDocumentClassificationRuns); take the first
  // completed run bound to this parse.
  const eligibleRun = useMemo<ClassificationRun | null>(() => {
    if (!parseRunId) return null
    return (
      runs.find((r) => r.status === 'completed' && r.parseRunId === parseRunId) ?? null
    )
  }, [runs, parseRunId])

  const availableCategories = useMemo<string[]>(() => {
    if (!eligibleRun) return []
    return Array.from(new Set(eligibleRun.regions.map((r) => r.label)))
  }, [eligibleRun])

  const toPreprocessStage = (): PreprocessStage | null => {
    if (!eligibleRun || selectedCategories.length === 0) return null
    return {
      stage: 'category_filter',
      config: {
        classificationRunId: eligibleRun.id,
        categories: selectedCategories,
        granularity,
      },
    }
  }

  return {
    eligibleRun,
    availableCategories,
    selectedCategories,
    granularity,
    setSelectedCategories,
    setGranularity,
    toPreprocessStage,
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/hooks/useCategoryFilter.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useCategoryFilter.ts frontend/src/hooks/useCategoryFilter.test.ts
git commit -m "feat(extraction): add useCategoryFilter hook"
```

---

### Task 5: Frontend — filter section + wire into New Extraction Run page

**Files:**
- Create: `frontend/src/components/extraction/CategoryFilterSection.tsx`
- Create: `frontend/src/components/extraction/CategoryFilterSection.test.tsx`
- Modify: `frontend/src/pages/NewExtractionRunPage.tsx` (render section in the LLM branch; add composed stage to `extractionConfig.preprocess`)

**Interfaces:**
- Consumes: `useCategoryFilter` (Task 4); `useDocumentClassificationRuns(documentId)` from `@/hooks/useClassificationRuns`; `PreprocessStage` from `@/types/extraction`.
- Produces: `<CategoryFilterSection state={CategoryFilterState} />` (presentational: category checkboxes + granularity toggle + blank state). The page passes `state.toPreprocessStage()` into `extractionConfig.preprocess`.

- [ ] **Step 1: Write the failing component test**

Create `frontend/src/components/extraction/CategoryFilterSection.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { CategoryFilterSection } from './CategoryFilterSection'
import type { CategoryFilterState } from '@/hooks/useCategoryFilter'

function state(overrides: Partial<CategoryFilterState>): CategoryFilterState {
  return {
    eligibleRun: { id: 'r1' } as never,
    availableCategories: ['fin', 'legal'],
    selectedCategories: [],
    granularity: 'page',
    setSelectedCategories: vi.fn(),
    setGranularity: vi.fn(),
    toPreprocessStage: () => null,
    ...overrides,
  }
}

describe('CategoryFilterSection', () => {
  it('renders a checkbox per available category', () => {
    render(<CategoryFilterSection state={state({})} />)
    expect(screen.getByText('fin')).toBeInTheDocument()
    expect(screen.getByText('legal')).toBeInTheDocument()
  })

  it('shows blank state when no eligible run', () => {
    render(<CategoryFilterSection state={state({ eligibleRun: null, availableCategories: [] })} />)
    expect(screen.getByText(/no completed classification/i)).toBeInTheDocument()
  })

  it('toggles a category selection', () => {
    const setSelected = vi.fn()
    render(<CategoryFilterSection state={state({ setSelectedCategories: setSelected })} />)
    fireEvent.click(screen.getByLabelText('fin'))
    expect(setSelected).toHaveBeenCalledWith(['fin'])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/extraction/CategoryFilterSection.test.tsx`
Expected: FAIL — component does not exist.

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/extraction/CategoryFilterSection.tsx`:

```tsx
import type { CategoryFilterState } from '@/hooks/useCategoryFilter'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'

interface Props {
  state: CategoryFilterState
}

export function CategoryFilterSection({ state }: Props) {
  const {
    eligibleRun, availableCategories, selectedCategories,
    granularity, setSelectedCategories, setGranularity,
  } = state

  if (!eligibleRun) {
    return (
      <p className="text-sm text-muted-foreground">
        No completed classification run exists for this parse. Run classification on
        this document first to filter extraction by category.
      </p>
    )
  }

  const toggle = (cat: string) => {
    setSelectedCategories(
      selectedCategories.includes(cat)
        ? selectedCategories.filter((c) => c !== cat)
        : [...selectedCategories, cat],
    )
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {availableCategories.map((cat) => (
          <div key={cat} className="flex items-center gap-2">
            <Checkbox
              id={`cat-${cat}`}
              checked={selectedCategories.includes(cat)}
              onCheckedChange={() => toggle(cat)}
            />
            <Label htmlFor={`cat-${cat}`}>{cat}</Label>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Label htmlFor="granularity">Granularity</Label>
        <select
          id="granularity"
          className="rounded border px-2 py-1 text-sm"
          value={granularity}
          onChange={(e) => setGranularity(e.target.value as 'page' | 'block')}
        >
          <option value="page">Page</option>
          <option value="block">Block</option>
        </select>
      </div>
    </div>
  )
}
```

> Implementer note: confirm `@/components/ui/checkbox` and `label` exist (they are standard shadcn/ui). If the project's shadcn checkbox uses a different import path, match the path used by an existing component such as `ClassificationLabelSection.tsx`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/extraction/CategoryFilterSection.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Wire into `NewExtractionRunPage.tsx`**

Add near the other hooks at the top of the component:

```tsx
import { useDocumentClassificationRuns } from '@/hooks/useClassificationRuns'
import { useCategoryFilter } from '@/hooks/useCategoryFilter'
import { CategoryFilterSection } from '@/components/extraction/CategoryFilterSection'
import { findMatchingParseRunId } from '@/hooks/useExtractionSubmit' // if exported; else recompute inline
```

Derive the parse run id the extraction will actually use, then the filter state:

```tsx
const { runs: classificationRuns } = useDocumentClassificationRuns(documentId)
// Resolve the parse run that matches the current parse config among existing runs.
// If no match exists (a new parse would be created), there can be no eligible
// classification run yet, so pass null.
const matchedParseRunId = useMemo(
  () => parseRuns.find(
    (r) => r.parser === parserType && r.representationKind === REPRESENTATION_KIND
      && (r.status === 'succeeded' || r.status === 'partial'),
  )?.id ?? null,
  [parseRuns, parserType],
)
const categoryFilter = useCategoryFilter(classificationRuns, matchedParseRunId)
```

Render the section inside the LLM extraction config block (near the chunking controls):

```tsx
{extractionMethod === 'llm' && (
  <CategoryFilterSection state={categoryFilter} />
)}
```

In the LLM branch of the submit handler (the `extractionConfig = { ... }` at ~line 239), add the composed stage:

```tsx
      const categoryStage = categoryFilter.toPreprocessStage()
      extractionConfig = {
        extractionSchemaId: schemaId,
        extractionMethod,
        config: { structured_output_mode: structuredOutputMode, inject_block_ids: injectBlockIds },
        llmConfig: promptConfig,
        userPromptTemplate: userPromptTemplate.trim() || undefined,
        ...(chunking ? { chunking } : {}),
        ...(categoryStage ? { preprocess: [categoryStage] } : {}),
        ...(!Number.isNaN(tm) && tm >= 1 ? { timeoutMinutes: Math.min(tm, 120) } : {}),
      }
```

> Implementer note: the exact `parseRuns` / `parserType` / `REPRESENTATION_KIND` variable names already exist in this file (see the parse config state and `useExtractionSubmit` matching logic). Reuse them; do not introduce new parse-matching logic beyond the `matchedParseRunId` memo.

- [ ] **Step 6: Run lint, build, and the full frontend suite**

Run: `cd frontend && npm run lint && npx vitest run src/hooks/useCategoryFilter.test.ts src/components/extraction/CategoryFilterSection.test.tsx && npm run build`
Expected: lint clean, tests PASS, build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/extraction/CategoryFilterSection.tsx frontend/src/components/extraction/CategoryFilterSection.test.tsx frontend/src/pages/NewExtractionRunPage.tsx
git commit -m "feat(extraction): add classification category filter to extraction config UI"
```

---

## Self-Review

**Spec coverage:**
- Complete `category_filter` seam → Task 1.
- Resolve-then-filter architecture / pure stage → Tasks 1 (pure fn) + 2 (resolver) + 3 (router wiring).
- Configurable granularity (page default, block + page fallback) → Tasks 1, 2 (tests cover page, block, fallback).
- Strict parse-run coupling + completed status → Task 2 (`test_parse_run_mismatch`, `test_not_completed`) + Task 3 (400 route test).
- Fail fast on empty match → Task 2 (`test_empty_match`) + Task 3 (400 route test).
- Whole-doc reconstruction (regenerated full_text/full_markdown, pruned pages) → Task 1 (`test_page_mode_keeps_whole_pages_and_reconstructs`).
- Preserve original page indices; page_count = retained count → Task 1 assertions.
- Provenance: `applied_filter` in config + doc labels/derivation → Task 1 (labels/derivation) + Task 3 (`applied_filter`).
- Catalogue entry updated (drop "coming soon", add granularity) → Task 1 Step 4.
- Frontend select-only section, eligible-run filtering, blank state, granularity default page → Tasks 4 + 5.

**Placeholder scan:** No TBD/TODO; every code step shows complete code. Two `Implementer note` callouts point at existing patterns to match (fixtures, shadcn import paths) rather than leaving logic unspecified.

**Type consistency:** `category_filter(doc, config)` config keys `keepPages`/`keepBlockIds`/`categories` are produced by the resolver (Task 2) and consumed by the pure fn (Task 1) — names match. `toPreprocessStage()` output `{ stage, config: { classificationRunId, categories, granularity } }` matches the resolver's expected input keys. `CategoryFilterState` is defined in Task 4 and consumed in Task 5.

**Assumption carried from spec:** select-only (no inline classification trigger); LLM extraction path only (preprocess is only wired for the `llm` method today).
