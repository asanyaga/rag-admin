# Page Boundaries — Eval Metrics Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thread page char-offset information from the LlamaIndex (simple) parser through to chunk metadata so that retrieval evaluation precision/recall/F1 are non-zero for full_text and full_markdown indices.

**Architecture:** Add `start_char`/`end_char` to the CDM `Page` model, populate them in `SimpleTextAdapter`, surface them from `SourceResolutionService` via a new `page_boundaries` field on `TextSource`, and pass them through `ChunkingDispatcher` to the existing `chunking_service.chunk_text()` call (which already handles `page_boundaries` correctly). LlamaParse and LandingAI are block-native and untouched. No DB migration is needed — parsed document content is stored as JSON.

**Tech Stack:** Python 3.12, Pydantic v2, SQLAlchemy async, pytest + pytest-asyncio. Run tests with `uv run python -m pytest -o "addopts=" <path>` from the `backend/` directory.

---

## File Map

| File | Action | What changes |
|------|--------|--------------|
| `backend/app/cdm/models.py` | Modify | Add `start_char: Optional[int]` and `end_char: Optional[int]` to `Page` |
| `backend/app/cdm/adapters/simple_text.py` | Modify | Populate `start_char`/`end_char` on `Page` from boundary dicts |
| `backend/app/services/source_resolution_service.py` | Modify | Add `page_boundaries: list[dict]` to `TextSource`; extract from CDM pages |
| `backend/app/services/chunking_dispatcher.py` | Modify | Pass `source.page_boundaries` instead of hardcoded `None` |
| `backend/tests/cdm/adapters/test_simple_text_adapter.py` | Modify | Assert `start_char`/`end_char` on pages; assert fallback pages have `None` |
| `backend/tests/services/test_source_resolution_service.py` | Modify | Assert `TextSource.page_boundaries` is populated from stored CDM content |
| `backend/tests/services/test_chunking_dispatcher.py` | Modify | Assert chunks from a paged `TextSource` carry `page_numbers` metadata |

---

## Task 1: Add `start_char` / `end_char` to the CDM `Page` model

**Files:**
- Modify: `backend/app/cdm/models.py:121-129`
- Modify: `backend/tests/cdm/test_models.py`

### Background

`Page` is a frozen Pydantic v2 model. LlamaParse and LandingAI leave these fields `None` — they are block-native and never need char offsets. The simple text adapter will be the only populator.

- [ ] **Step 1: Write a failing test**

Add to `backend/tests/cdm/test_models.py`:

```python
from app.cdm.models import Page


def test_page_accepts_char_offsets():
    page = Page(index=0, start_char=0, end_char=500)
    assert page.start_char == 0
    assert page.end_char == 500


def test_page_char_offsets_default_to_none():
    page = Page(index=0)
    assert page.start_char is None
    assert page.end_char is None
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run python -m pytest -o "addopts=" tests/cdm/test_models.py::test_page_accepts_char_offsets -v
```

Expected: `FAILED` — `Page` does not accept `start_char`.

- [ ] **Step 3: Add the fields to `Page`**

In `backend/app/cdm/models.py`, replace the `Page` class (lines 121-129):

```python
class Page(_Frozen):
    index: int
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    width: Optional[float] = None
    height: Optional[float] = None
    unit: Optional[str] = None
    rotation: int = 0
    block_ids: List[str] = []
    quality: Optional[Quality] = None
    parser_extras: Dict[str, Any] = {}
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run python -m pytest -o "addopts=" tests/cdm/test_models.py::test_page_accepts_char_offsets tests/cdm/test_models.py::test_page_char_offsets_default_to_none -v
```

Expected: both `PASSED`.

- [ ] **Step 5: Run full CDM test suite to check for regressions**

```
uv run python -m pytest -o "addopts=" tests/cdm/ -v
```

Expected: all passing (the new optional fields have defaults, so nothing existing breaks).

- [ ] **Step 6: Commit**

```
git add backend/app/cdm/models.py backend/tests/cdm/test_models.py
git commit -m "feat(cdm): add start_char/end_char to Page model"
```

---

## Task 2: Populate `start_char`/`end_char` in `SimpleTextAdapter`

**Files:**
- Modify: `backend/app/cdm/adapters/simple_text.py:42-45`
- Modify: `backend/tests/cdm/adapters/test_simple_text_adapter.py`

### Background

`SimpleTextAdapter.adapt()` already iterates `boundaries` — a list of `{"page": N, "start_char": M, "end_char": K}` dicts — and has `start_char`/`end_char` in local scope when building each `Page`. They just need to be written in. The fallback path (no boundaries) produces a single page spanning the whole text.

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/cdm/adapters/test_simple_text_adapter.py`:

```python
def test_pages_carry_char_offsets_when_boundaries_provided():
    doc = SimpleTextAdapter().adapt(TWO_PAGE_RAW, SOURCE_META)
    assert doc.pages[0].start_char == 0
    assert doc.pages[0].end_char == 20
    assert doc.pages[1].start_char == 22
    assert doc.pages[1].end_char == 40


def test_fallback_page_carries_char_offsets_spanning_full_text():
    raw = {"text": "some text", "page_count": 1, "page_boundaries": []}
    doc = SimpleTextAdapter().adapt(raw, SOURCE_META)
    assert doc.pages[0].start_char == 0
    assert doc.pages[0].end_char == len("some text")
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run python -m pytest -o "addopts=" tests/cdm/adapters/test_simple_text_adapter.py::test_pages_carry_char_offsets_when_boundaries_provided tests/cdm/adapters/test_simple_text_adapter.py::test_fallback_page_carries_char_offsets_spanning_full_text -v
```

Expected: both `FAILED` — `Page.start_char` is `None`.

- [ ] **Step 3: Populate char offsets in the boundaries branch**

Replace the `pages.append(...)` call inside the `for pb in boundaries:` loop in `backend/app/cdm/adapters/simple_text.py` (currently lines 42-45):

```python
                pages.append(Page(
                    index=page_index,
                    block_ids=[block_id],
                    start_char=start_char,
                    end_char=end_char,
                ))
```

- [ ] **Step 4: Populate char offsets in the fallback branch**

Replace the fallback `pages = [Page(...)]` (currently lines 56-59):

```python
            pages = [Page(
                index=0,
                block_ids=[block_id],
                start_char=0,
                end_char=len(full_text),
            )]
```

- [ ] **Step 5: Run the new tests to verify they pass**

```
uv run python -m pytest -o "addopts=" tests/cdm/adapters/test_simple_text_adapter.py -v
```

Expected: all `PASSED` (existing tests still pass; two new ones now pass too).

- [ ] **Step 6: Commit**

```
git add backend/app/cdm/adapters/simple_text.py backend/tests/cdm/adapters/test_simple_text_adapter.py
git commit -m "feat(cdm): SimpleTextAdapter stores start_char/end_char on Page"
```

---

## Task 3: Add `page_boundaries` to `TextSource` and populate it in `SourceResolutionService`

**Files:**
- Modify: `backend/app/services/source_resolution_service.py`
- Modify: `backend/tests/services/test_source_resolution_service.py`

### Background

`SourceResolutionService.resolve()` reads `parsed_doc.content` (a JSON blob equal to `cdm_doc.model_dump()`). After Task 2, that JSON includes `pages[*].start_char` and `pages[*].end_char`. We extract those into a `page_boundaries` list and attach it to `TextSource`. Documents parsed before this fix will have `start_char: null` in their pages — the extraction filters those out so old data silently produces an empty list (no page matching), exactly the pre-fix behaviour.

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/services/test_source_resolution_service.py`:

```python
@pytest.fixture
async def seeded_parsed_document_with_pages(test_db: AsyncSession) -> ParsedDocumentORM:
    """ParsedDocument whose CDM content includes pages with char offsets."""
    src, run = await _seed_source_and_run(test_db)
    blocks = [
        {"id": "b1", "role": "paragraph", "text": "page one text", "page_index": 0,
         "native_type": "text", "children_ids": [], "spans": [], "parser_extras": {},
         "is_continuation": False},
        {"id": "b2", "role": "paragraph", "text": "page two text", "page_index": 1,
         "native_type": "text", "children_ids": [], "spans": [], "parser_extras": {},
         "is_continuation": False},
    ]
    pages = [
        {"index": 0, "start_char": 0, "end_char": 13, "block_ids": ["b1"],
         "rotation": 0, "parser_extras": {}},
        {"index": 1, "start_char": 15, "end_char": 28, "block_ids": ["b2"],
         "rotation": 0, "parser_extras": {}},
    ]
    content = {
        "id": str(uuid4()), "source_document_id": str(src.id),
        "parse_run_id": str(run.id), "page_count": 2, "block_count": 2,
        "pages": pages, "blocks": blocks, "labels": [],
        "schema_version": "1.0",
    }
    pd = ParsedDocumentORM(
        parse_run_id=run.id,
        source_document_id=src.id,
        full_text="page one text\npage two text",
        full_markdown=None,
        page_count=2,
        block_count=2,
        content=content,
    )
    test_db.add(pd)
    await test_db.commit()
    await test_db.refresh(pd)
    return pd


@pytest.mark.asyncio
async def test_resolve_full_text_with_pages_populates_page_boundaries(
    seeded_parsed_document_with_pages, test_db
):
    svc = SourceResolutionService(test_db)
    result = await svc.resolve(
        parsed_document_id=seeded_parsed_document_with_pages.parse_run_id,
        source_representation="full_text",
    )
    assert isinstance(result, TextSource)
    assert result.page_boundaries == [
        {"page": 1, "start_char": 0, "end_char": 13},
        {"page": 2, "start_char": 15, "end_char": 28},
    ]


@pytest.mark.asyncio
async def test_resolve_full_text_without_page_offsets_returns_empty_boundaries(
    seeded_parsed_document, test_db
):
    """seeded_parsed_document fixture has pages without start_char — empty boundaries expected."""
    svc = SourceResolutionService(test_db)
    result = await svc.resolve(
        parsed_document_id=seeded_parsed_document.parse_run_id,
        source_representation="full_text",
    )
    assert isinstance(result, TextSource)
    assert result.page_boundaries == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run python -m pytest -o "addopts=" tests/services/test_source_resolution_service.py::test_resolve_full_text_with_pages_populates_page_boundaries tests/services/test_source_resolution_service.py::test_resolve_full_text_without_page_offsets_returns_empty_boundaries -v
```

Expected: `FAILED` — `TextSource` has no `page_boundaries` attribute.

- [ ] **Step 3: Add `page_boundaries` to `TextSource` and the extraction helper**

Replace the full contents of `backend/app/services/source_resolution_service.py`:

```python
"""Source resolution: parsed-doc handle + segment -> chunkable source.

Single shared seam used by both chunk preview and index processing so that
a preview always reflects the same bytes the save path will chunk.

The seam carries only the bytes/blocks. Metadata (source_document_id,
source_filename) flows through the dispatcher's call site so that the save
path's chunk metadata stays byte-identical with the pre-refactor behaviour
(which sourced filename from `Document.source_metadata.filename`).
"""
from dataclasses import dataclass, field
from typing import Literal, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.services.exceptions import NotFoundError, ValidationError


SourceRepresentation = Literal["full_text", "full_markdown", "block"]


@dataclass(frozen=True)
class TextSource:
    """Text-shaped source (full_text or full_markdown)."""
    text: str
    page_boundaries: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class BlocksSource:
    """Block-shaped source. Block chunking is not yet implemented."""
    blocks: list[dict]


ChunkSource = Union[TextSource, BlocksSource]


def _extract_page_boundaries(content: dict) -> list[dict]:
    """Extract 1-based page boundaries from CDM content pages.

    Pages without start_char/end_char (old parse runs or block-native parsers)
    are silently skipped, returning an empty list.
    """
    pages = content.get("pages") or []
    result = []
    for p in pages:
        start = p.get("start_char")
        end = p.get("end_char")
        if start is not None and end is not None:
            result.append({
                "page": p["index"] + 1,  # CDM index is 0-based; chunking_service expects 1-based
                "start_char": start,
                "end_char": end,
            })
    return result


class SourceResolutionService:
    """Resolve a parsed-document handle + segment into a ChunkSource."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve(
        self,
        *,
        parsed_document_id: UUID,
        source_representation: SourceRepresentation,
    ) -> ChunkSource:
        parsed_doc_repo = ParsedDocumentRepository(self.session)

        # Under the current 1:1 schema, parsed_documents.parse_run_id is the PK.
        parsed_doc = await parsed_doc_repo.get_by_run(parsed_document_id)
        if parsed_doc is None:
            raise NotFoundError(
                f"Parsed document {parsed_document_id} not found"
            )

        content = parsed_doc.content or {}

        if source_representation == "full_text":
            if parsed_doc.full_text is None:
                raise ValidationError(
                    f"Parsed document {parsed_document_id} has no full_text"
                )
            return TextSource(
                text=parsed_doc.full_text,
                page_boundaries=_extract_page_boundaries(content),
            )

        if source_representation == "full_markdown":
            if parsed_doc.full_markdown is None:
                raise ValidationError(
                    f"Parsed document {parsed_document_id} has no full_markdown. "
                    "Re-parse with a configuration that outputs markdown."
                )
            return TextSource(
                text=parsed_doc.full_markdown,
                page_boundaries=_extract_page_boundaries(content),
            )

        # block
        blocks = content.get("blocks") or []
        if not blocks:
            raise ValidationError(
                f"Parsed document {parsed_document_id} has no blocks"
            )
        return BlocksSource(blocks=blocks)
```

- [ ] **Step 4: Run the new tests to verify they pass**

```
uv run python -m pytest -o "addopts=" tests/services/test_source_resolution_service.py -v
```

Expected: all `PASSED`.

- [ ] **Step 5: Commit**

```
git add backend/app/services/source_resolution_service.py backend/tests/services/test_source_resolution_service.py
git commit -m "feat(chunking): TextSource carries page_boundaries from CDM pages"
```

---

## Task 4: Pass `page_boundaries` through `ChunkingDispatcher`

**Files:**
- Modify: `backend/app/services/chunking_dispatcher.py:57-63`
- Modify: `backend/tests/services/test_chunking_dispatcher.py`

### Background

`chunking_service.chunk_text()` already accepts `page_boundaries` and, when provided, computes a `page_numbers` list for each chunk by checking which pages each chunk's char range overlaps (see `chunking_service._get_page_numbers()`). The dispatcher just needs to stop hardcoding `None` and pass the value from `TextSource`. The markdown path also receives a `TextSource` — it does not use page boundaries (markdown chunking is heading-driven), so we leave it untouched.

- [ ] **Step 1: Write a failing test**

Add to `backend/tests/services/test_chunking_dispatcher.py`:

```python
def test_text_source_with_page_boundaries_produces_chunks_with_page_numbers():
    """Full-text chunks from a paged source must have page_numbers in metadata."""
    # 200 chars on page 1 (0-199), 200 chars on page 2 (200-399)
    text = "a " * 100 + "b " * 100        # 400 chars total
    src = TextSource(
        text=text,
        page_boundaries=[
            {"page": 1, "start_char": 0,   "end_char": 200},
            {"page": 2, "start_char": 200, "end_char": 400},
        ],
    )
    chunks = ChunkingDispatcher().dispatch(
        source=src,
        config=_config("full_text"),
        source_document_id=str(uuid4()),
        source_filename="paged.pdf",
    )
    assert chunks, "expected at least one chunk"
    # Every chunk must carry a non-empty page_numbers list
    for chunk in chunks:
        assert chunk.metadata.get("page_numbers"), (
            f"chunk missing page_numbers: {chunk.metadata}"
        )


def test_text_source_without_page_boundaries_produces_chunks_without_page_numbers():
    """Backward compat: empty page_boundaries → no page_numbers on chunks."""
    text = "content " * 100
    src = TextSource(text=text, page_boundaries=[])
    chunks = ChunkingDispatcher().dispatch(
        source=src,
        config=_config("full_text"),
        source_document_id=str(uuid4()),
        source_filename="nopages.pdf",
    )
    assert chunks
    for chunk in chunks:
        assert not chunk.metadata.get("page_numbers"), (
            f"unexpected page_numbers: {chunk.metadata}"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run python -m pytest -o "addopts=" tests/services/test_chunking_dispatcher.py::test_text_source_with_page_boundaries_produces_chunks_with_page_numbers tests/services/test_chunking_dispatcher.py::test_text_source_without_page_boundaries_produces_chunks_without_page_numbers -v
```

Expected: first test `FAILED` — chunks have no `page_numbers`. Second test `PASSED` (already the case, confirms backward compat baseline).

- [ ] **Step 3: Replace the hardcoded `None` in `ChunkingDispatcher.dispatch()`**

In `backend/app/services/chunking_dispatcher.py`, replace lines 57-63:

```python
            # full_text uses the plain-text chunker.
            return self.chunking_service.chunk_text(
                text=source.text,
                config=config,
                source_document_id=source_document_id,
                source_filename=source_filename,
                page_boundaries=source.page_boundaries or None,
            )
```

- [ ] **Step 4: Run the dispatcher tests to verify they pass**

```
uv run python -m pytest -o "addopts=" tests/services/test_chunking_dispatcher.py -v
```

Expected: all `PASSED`.

- [ ] **Step 5: Commit**

```
git add backend/app/services/chunking_dispatcher.py backend/tests/services/test_chunking_dispatcher.py
git commit -m "fix(chunking): pass page_boundaries from TextSource to chunk_text"
```

---

## Task 5: Integration smoke test — end-to-end page numbers in eval matching

**Files:**
- Modify: `backend/tests/services/test_eval_service.py`

### Background

This test verifies the complete path: given a golden set source with a page locator and a retrieved chunk whose `page_numbers` metadata matches, `_process_single_query` must return non-zero precision/recall/F1. It mocks `query_service.query_index` to return a controlled `QueryResponse` so no real DB or embedding calls are needed.

- [ ] **Step 1: Add imports to the top of `test_eval_service.py`**

The existing import block already has `from unittest.mock import AsyncMock, MagicMock` — add the query schema imports:

```python
from app.schemas.query import QueryResponse, RetrievalResult, RetrievalResultMetadata
from app.schemas.eval_run import EvalRunConfig
```

- [ ] **Step 2: Write the test helpers and tests**

Add to `backend/tests/services/test_eval_service.py`:

```python
# ---------------------------------------------------------------------------
# _process_single_query metric calculation tests
# ---------------------------------------------------------------------------

def _make_query_service_mock(doc_id: str, page_numbers: list[int]):
    """Return a mock query_service whose query_index returns one chunk on the given pages."""
    meta = RetrievalResultMetadata(
        documentId=doc_id,
        documentName="test.pdf",
        page=page_numbers[0] if page_numbers else None,
        pageNumbers=page_numbers or None,
        chunkIndex=0,
        tokenCount=50,
        charCount=200,
    )
    result = RetrievalResult(
        chunkId="chunk-1",
        rank=1,
        score=0.9,
        content="relevant content",
        metadata=meta,
    )
    response = QueryResponse(
        query="test query",
        results=[result],
        totalResults=1,
        searchType="semantic",
        executionTimeMs=10.0,
    )
    mock_qs = MagicMock()
    mock_qs.query_index = AsyncMock(return_value=response)
    return mock_qs


def _make_eval_service_for_metric_test(eval_run_repo, golden_set_repo, doc_id, page_numbers):
    """Build an EvalService with mocked query_service and mocked create_result.

    create_result is mocked to avoid a DB insert with a dangling FK —
    these tests are purely about the metric calculation, not persistence.
    """
    query_service = _make_query_service_mock(doc_id=doc_id, page_numbers=page_numbers)
    svc = EvalService(eval_run_repo, golden_set_repo, query_service=query_service)
    svc.eval_repo.create_result = AsyncMock()
    return svc


def _make_run_stub(test_index, test_project, test_user):
    run = MagicMock()
    run.index_id = test_index.id
    run.project_id = test_project.id
    run.created_by = test_user.id
    run.mode = "retrieval_only"
    run.generation_config = None
    run.judge_config = None
    return run


def _make_query_stub(doc_id: str, pages: list[int]):
    source = MagicMock()
    source.document_id = doc_id   # str; service calls str() on it
    source.locator = {"type": "page", "pages": pages}
    query = MagicMock()
    query.id = uuid4()
    query.query_text = "test query"
    query.sources = [source]
    return query


@pytest.mark.asyncio
async def test_process_single_query_returns_nonzero_metrics_when_pages_match(
    eval_run_repo, golden_set_repo, test_project, test_index, test_user
):
    """When chunk page_numbers overlap the golden set source locator, metrics must be > 0."""
    doc_id = str(uuid4())
    svc = _make_eval_service_for_metric_test(eval_run_repo, golden_set_repo, doc_id, page_numbers=[2])
    run = _make_run_stub(test_index, test_project, test_user)
    query = _make_query_stub(doc_id=doc_id, pages=[2])
    config = EvalRunConfig(searchType="semantic", topK=5, similarityThreshold=0.0)

    result = await svc._process_single_query(
        run=run, query=query, config=config,
        run_id=uuid4(), user_id=test_user.id, is_answer_mode=False,
    )

    assert result["precision"] > 0, "precision should be non-zero when pages match"
    assert result["recall"] > 0, "recall should be non-zero when pages match"
    assert result["f1"] > 0, "F1 should be non-zero when pages match"


@pytest.mark.asyncio
async def test_process_single_query_returns_zero_metrics_when_chunk_has_no_page_numbers(
    eval_run_repo, golden_set_repo, test_project, test_index, test_user
):
    """When chunk has no page_numbers, metrics must be zero (documents the bug state)."""
    doc_id = str(uuid4())
    svc = _make_eval_service_for_metric_test(eval_run_repo, golden_set_repo, doc_id, page_numbers=[])
    run = _make_run_stub(test_index, test_project, test_user)
    query = _make_query_stub(doc_id=doc_id, pages=[2])
    config = EvalRunConfig(searchType="semantic", topK=5, similarityThreshold=0.0)

    result = await svc._process_single_query(
        run=run, query=query, config=config,
        run_id=uuid4(), user_id=test_user.id, is_answer_mode=False,
    )

    assert result["precision"] == 0.0
    assert result["recall"] == 0.0
    assert result["f1"] == 0.0
```

- [ ] **Step 2: Run tests to verify the matching test passes and the zero test passes**

```
uv run python -m pytest -o "addopts=" tests/services/test_eval_service.py::test_process_single_query_returns_nonzero_metrics_when_pages_match tests/services/test_eval_service.py::test_process_single_query_returns_zero_metrics_when_pages_dont_match -v
```

Expected: both `PASSED`. The matching test documents the correct behaviour; the zero test documents the known limitation when chunks lack page info.

- [ ] **Step 3: Run full service test suite to check for regressions**

```
uv run python -m pytest -o "addopts=" tests/services/ -v
```

Expected: all `PASSED`.

- [ ] **Step 4: Commit**

```
git add backend/tests/services/test_eval_service.py
git commit -m "test(eval): document eval metric behaviour with and without page_numbers"
```

---

## Task 6: Full backend test suite + final verification

- [ ] **Step 1: Run the full backend test suite**

```
uv run python -m pytest -o "addopts=" tests/ -v
```

Expected: all `PASSED`. If any test fails due to the `TextSource` dataclass gaining a new field (tests that construct `TextSource(text=...)` positionally), update them to use `TextSource(text=..., page_boundaries=[])` — the field has a default so keyword construction always works.

- [ ] **Step 2: Confirm existing dispatcher tests still pass without changes**

The pre-existing tests in `test_chunking_dispatcher.py` all construct `TextSource(text=...)` without `page_boundaries`. Because `page_boundaries` defaults to `[]`, and `[] or None` evaluates to `None`, those tests produce the same behaviour as before (no page_numbers on chunks). No changes to existing tests are required.

- [ ] **Step 3: Commit and push**

```
git add -p   # review any stray changes
git commit -m "chore: full test pass after page_boundaries threading"
```

---

## Re-indexing note

Documents already indexed before this fix will continue to produce zero metrics until re-indexed. Re-indexing requires a fresh parse run (so the `ParsedDocument.content` is regenerated with `start_char`/`end_char` on pages) followed by re-indexing that document. No migration or back-fill is needed — the architecture gracefully degrades to zero metrics for old parse runs, identical to today's behaviour.
