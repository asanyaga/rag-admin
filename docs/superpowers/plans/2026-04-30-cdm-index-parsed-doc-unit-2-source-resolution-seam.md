# CDM Index — Unit 2: Source-Resolution Seam + Chunk Preview Fix

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [`docs/superpowers/specs/2026-04-29-cdm-index-parser-config-selector.md`](../specs/2026-04-29-cdm-index-parser-config-selector.md) §5
**Depends on:** Unit 1 (parsed-doc reads + ORM tighten — PR #47) merged into `main`. Slice-2 (markdown chunking — PR #45) merged into `main`. Both are precursors to this branch.
**Issue:** TBD (created in pre-implementation gate)

**Goal:** Replace the duplicated source-resolution logic between chunk preview and index processing with a single, shared `resolve_source(parsed_document_id, source_representation) → ChunkSource` seam. Lift the `2a0cfa1` band-aid so `Preview Chunks` works for `full_markdown` (and produces the *same* text the save path will chunk).

**Architecture:** Pure-refactor backend slice plus a small frontend follow-through. A new `SourceResolutionService` extracts the "given a parsed-doc + segment, return the bytes to chunk" decision out of `IndexProcessingService.process_index()` and the `/preview-chunks` endpoint. Both call sites then share the same resolver. A `ChunkingDispatcher` routes a resolved `ChunkSource` plus an `IndexConfig` to the existing `ChunkingService` / `MarkdownChunkingService`. The preview endpoint is widened to accept `parsedDocumentId` per spec while keeping a temporary `documentId` bridge so the slice-2 wizard (which has no parsed-doc picker yet — that's Unit 4) can still preview against the latest parsed-doc for a chosen document. Unit 3 removes the bridge and the legacy `raw_text` path together.

**Tech Stack:** Python 3.12 · FastAPI async · SQLAlchemy 2.0 async · Pydantic v2 · pytest · React 18 · TypeScript · Vitest

---

## Scope and bridge decisions

| Concern | Unit 2 behaviour | Reason |
|---|---|---|
| `full_text` / `full_markdown` source resolution | Goes through the new seam | Spec §5; required to lift band-aid |
| `block` source resolution | Resolver returns `BlocksSource`; chunker dispatch raises `NotImplementedError` | Block chunking is a future unit; resolver is the only piece needed by Unit 2 tests |
| `persist(...)` extraction | **Not factored** — chunk persistence stays inline in `IndexProcessingService.process_index()` | Spec §5 names `persist` as a conceptual step in the save flow, not a mandated function. Single caller; YAGNI. Extract when a second caller appears. |
| `raw_text` preview | **Untouched** — legacy `document.extracted_text` branch retained inside the preview endpoint | `raw_text` removal is Unit 3's job per Unit 1's "Out of scope" |
| `raw_text` save | **Untouched** — legacy branch in `IndexProcessingService` retained | Same reason |
| `ChunkPreviewRequest` shape | Adds `parsedDocumentId` (optional); `documentId` becomes optional; validator: exactly one required | Spec §5 makes `parsedDocumentId` the new shape; bridge keeps slice-2 wizard working until Unit 4 |
| Frontend wizard | Lifts the band-aid; for CDM modes, sends `documentId` (bridge); for `raw_text`, unchanged | Slice-2 wizard has no parsed-doc picker; bridge is removed in Unit 4 when picker lands |
| DB schema | No changes | Unit 2 is a service-layer refactor only |

---

## Pre-implementation gate

- [ ] **Step P1 — Create the GitHub issue and confirm with user.**

```bash
gh issue create \
  --title "feat(index): source-resolution seam + chunk preview fix (Unit 2)" \
  --body "$(cat <<'EOF'
## Summary
Second unit of the CDM-index parsed-document refactor. Extracts source
resolution (`parsed_document_id + source_representation -> bytes/blocks`) into
a shared service so chunk preview and index processing read the same source
for the same parsed-doc. Lifts the `2a0cfa1` band-aid so `Preview Chunks`
works for `full_markdown`.

## Acceptance criteria
- [ ] `SourceResolutionService.resolve(parsed_document_id, source_representation)` returns a `TextSource` for `full_text`/`full_markdown` and a `BlocksSource` for `block`. Errors when the parsed-doc is missing or the requested segment is null.
- [ ] `ChunkingDispatcher.dispatch(source, config, ...)` produces the same chunks the existing inline branches produce for `full_text` and `full_markdown`. Raises `NotImplementedError` for `BlocksSource`.
- [ ] `IndexProcessingService.process_index()` uses `SourceResolutionService` + `ChunkingDispatcher` for CDM branches. The legacy `raw_text` branch is retained byte-identical for now.
- [ ] `POST /projects/{id}/indexes/preview-chunks` accepts `parsedDocumentId` and produces accurate chunks for `full_text`, `full_markdown`. The `2a0cfa1` band-aid (`disabled={... sourceRepresentation === 'full_markdown'}`) is removed in `IndexCreateDialog` and `CreateIndexPage`.
- [ ] Bridge: when only `documentId` is supplied with a CDM `source_representation`, the endpoint resolves the latest succeeded parsed-doc for the document and runs through the seam. (Removed in Unit 3.)
- [ ] Existing index processing and preview tests still pass; new tests cover the seam, the dispatcher, and the `full_markdown` preview path.

## Spec
docs/superpowers/specs/2026-04-29-cdm-index-parser-config-selector.md (§5)

## Plan
docs/superpowers/plans/2026-04-30-cdm-index-parsed-doc-unit-2-source-resolution-seam.md
EOF
)" \
  --label "feature,backend,frontend"
```

After the issue is created, confirm the number with the user, then update this file's `**Issue:**` line with `#<n>` before continuing.

---

## File map

| Action | Path | What changes |
|---|---|---|
| **Create** | `backend/app/services/source_resolution_service.py` | `TextSource`, `BlocksSource`, `ChunkSource`, `SourceResolutionService` |
| **Create** | `backend/app/services/chunking_dispatcher.py` | `ChunkingDispatcher.dispatch(source, config, ...)` routing to existing chunkers |
| Modify | `backend/app/repositories/parsed_document_repository.py` | Add `get_latest_for_document(document_id)` (bridge helper, removed in Unit 3) |
| Modify | `backend/app/services/index_processing_service.py:170-235` | Replace CDM dispatch block with seam calls; keep `raw_text` branch as-is |
| Modify | `backend/app/schemas/index.py:247-253` | `ChunkPreviewRequest`: add `parsed_document_id` (alias `parsedDocumentId`), make `document_id` optional, add validator (exactly one required) |
| Modify | `backend/app/routers/indexes.py:585-621` | Preview endpoint: route through seam when `parsed_document_id` (or CDM `source_representation`) is in play; legacy `raw_text + document_id` branch retained |
| Modify | `backend/app/services/exceptions.py` | (only if `ParsedDocumentNotFoundError` / `SegmentMissingError` are needed; otherwise reuse `NotFoundError` + `ValidationError`) |
| **Create** | `backend/tests/services/test_source_resolution_service.py` | Resolver tests (full_text / full_markdown / block / errors) |
| **Create** | `backend/tests/services/test_chunking_dispatcher.py` | Dispatcher tests (text→chunking_service, markdown→markdown_chunking_service, blocks→NotImplementedError) |
| Modify | `backend/tests/services/test_index_processing_cdm.py` | Update assertions if dispatch internals changed; add a test pinning the seam call |
| **Create** | `backend/tests/routers/test_preview_chunks_router.py` (or extend existing) | Preview endpoint with `parsedDocumentId`, with `documentId` (bridge), validator behaviour, full_markdown happy path |
| Modify | `backend/tests/repositories/test_parsed_document_repository_listing.py` (or new file) | Add `get_latest_for_document` tests |
| Modify | `frontend/src/types/index.ts:146-150` | `ChunkPreviewRequest`: add `parsedDocumentId?: string`; make `documentId?: string` |
| Modify | `frontend/src/api/indexes.ts:151-170` | Send `parsedDocumentId` when present; otherwise send `documentId`; pass full `IndexConfig` (incl. `sourceRepresentation`, `parser`, `parseConfigHash`, markdown fields) instead of the trimmed config |
| Modify | `frontend/src/components/indexes/IndexCreateDialog.tsx:454-462` | Remove `config.sourceRepresentation === 'full_markdown'` from `disabled` prop on `<ChunkPreviewPanel>` |
| Modify | `frontend/src/pages/CreateIndexPage.tsx` | Same band-aid lift as `IndexCreateDialog` (the standalone-page parity from `b7ab522`) |
| Modify | `frontend/src/components/indexes/IndexCreateDialog.test.tsx` (and any matching `CreateIndexPage` test) | Update tests asserting the disabled state for `full_markdown` |

No Alembic migration. No model changes. No new routers.

---

## Implementation tasks (TDD)

### Task 1 — `SourceResolutionService` (resolver only)

**Files:**
- Create: `backend/app/services/source_resolution_service.py`
- Create: `backend/tests/services/test_source_resolution_service.py`

- [ ] **1.1 Write failing tests (red).** `backend/tests/services/test_source_resolution_service.py`:

```python
"""Tests for SourceResolutionService."""
import pytest
from uuid import uuid4

from app.services.source_resolution_service import (
    SourceResolutionService,
    TextSource,
    BlocksSource,
)
from app.services.exceptions import NotFoundError, ValidationError


@pytest.mark.asyncio
async def test_resolve_full_text_returns_text_source(seeded_parsed_document, db_session):
    svc = SourceResolutionService(db_session)
    result = await svc.resolve(
        parsed_document_id=seeded_parsed_document.parse_run_id,
        source_representation="full_text",
    )
    assert isinstance(result, TextSource)
    assert result.text == seeded_parsed_document.full_text


@pytest.mark.asyncio
async def test_resolve_full_markdown_returns_text_source(seeded_parsed_document_with_markdown, db_session):
    svc = SourceResolutionService(db_session)
    result = await svc.resolve(
        parsed_document_id=seeded_parsed_document_with_markdown.parse_run_id,
        source_representation="full_markdown",
    )
    assert isinstance(result, TextSource)
    assert result.text == seeded_parsed_document_with_markdown.full_markdown


@pytest.mark.asyncio
async def test_resolve_block_returns_blocks_source(seeded_parsed_document, db_session):
    svc = SourceResolutionService(db_session)
    result = await svc.resolve(
        parsed_document_id=seeded_parsed_document.parse_run_id,
        source_representation="block",
    )
    assert isinstance(result, BlocksSource)
    assert len(result.blocks) >= 1


@pytest.mark.asyncio
async def test_resolve_missing_parsed_document_raises_not_found(db_session):
    svc = SourceResolutionService(db_session)
    with pytest.raises(NotFoundError, match="Parsed document"):
        await svc.resolve(
            parsed_document_id=uuid4(),
            source_representation="full_text",
        )


@pytest.mark.asyncio
async def test_resolve_full_markdown_missing_segment_raises_validation(seeded_parsed_document, db_session):
    """seeded_parsed_document fixture has full_markdown=None."""
    svc = SourceResolutionService(db_session)
    with pytest.raises(ValidationError, match="full_markdown"):
        await svc.resolve(
            parsed_document_id=seeded_parsed_document.parse_run_id,
            source_representation="full_markdown",
        )
```

If the `seeded_parsed_document` / `seeded_parsed_document_with_markdown` fixtures don't exist yet, copy the existing seeding pattern from `backend/tests/services/test_index_processing_cdm.py` (a `ParseRun` + `ParsedDocument` pair under a project's `Document` + `SourceDocument`). For `seeded_parsed_document`, leave `full_markdown=None`. For `seeded_parsed_document_with_markdown`, populate it.

- [ ] **1.2 Run tests to verify red.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/services/test_source_resolution_service.py -o "addopts=" -v
```
Expected: `ModuleNotFoundError: No module named 'app.services.source_resolution_service'`.

- [ ] **1.3 Implement the resolver (green).** `backend/app/services/source_resolution_service.py`:

```python
"""Source resolution: parsed-doc handle + segment -> chunkable source.

Single shared seam used by both chunk preview and index processing so that
a preview always reflects the same bytes the save path will chunk.

The seam carries only the bytes/blocks. Metadata (source_document_id,
source_filename) flows through the dispatcher's call site so that the save
path's chunk metadata stays byte-identical with the pre-refactor behaviour
(which sourced filename from `Document.source_metadata.filename`).
"""
from dataclasses import dataclass
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


@dataclass(frozen=True)
class BlocksSource:
    """Block-shaped source. Block chunking is not yet implemented."""
    blocks: list[dict]


ChunkSource = Union[TextSource, BlocksSource]


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
        # Unit 1's `**Note on identifier choice**` calls this out explicitly.
        parsed_doc = await parsed_doc_repo.get_by_run(parsed_document_id)
        if parsed_doc is None:
            raise NotFoundError(
                f"Parsed document {parsed_document_id} not found"
            )

        if source_representation == "full_text":
            if parsed_doc.full_text is None:
                raise ValidationError(
                    f"Parsed document {parsed_document_id} has no full_text"
                )
            return TextSource(text=parsed_doc.full_text)

        if source_representation == "full_markdown":
            if parsed_doc.full_markdown is None:
                raise ValidationError(
                    f"Parsed document {parsed_document_id} has no full_markdown. "
                    "Re-parse with a configuration that outputs markdown."
                )
            return TextSource(text=parsed_doc.full_markdown)

        # block
        blocks = parsed_doc.content.get("blocks") if parsed_doc.content else []
        if not blocks:
            raise ValidationError(
                f"Parsed document {parsed_document_id} has no blocks"
            )
        return BlocksSource(blocks=blocks)
```

- [ ] **1.4 Run tests — verify green.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/services/test_source_resolution_service.py -o "addopts=" -v
```
Expected: 6 passing.

- [ ] **1.5 Commit.**

```bash
git -C /home/asa/rag-admin add \
  backend/app/services/source_resolution_service.py \
  backend/tests/services/test_source_resolution_service.py
git -C /home/asa/rag-admin commit -m "feat(services): SourceResolutionService — parsed-doc + segment to ChunkSource"
```

---

### Task 2 — `ChunkingDispatcher`

**Files:**
- Create: `backend/app/services/chunking_dispatcher.py`
- Create: `backend/tests/services/test_chunking_dispatcher.py`

- [ ] **2.1 Write failing tests (red).** `backend/tests/services/test_chunking_dispatcher.py`:

```python
"""Tests for ChunkingDispatcher."""
from uuid import uuid4

import pytest

from app.schemas.index import IndexConfig
from app.services.chunking_dispatcher import ChunkingDispatcher
from app.services.source_resolution_service import TextSource, BlocksSource


def _config(source_rep: str = "full_text", chunking_strategy: str = "recursive_character") -> IndexConfig:
    return IndexConfig.model_validate({
        "source_representation": source_rep,
        "chunking_strategy": chunking_strategy,
        "chunk_size": 200,
        "chunk_overlap": 20,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
    })


def test_dispatch_text_source_full_text_routes_to_chunking_service():
    src = TextSource(text="abcdef " * 200)
    chunks = ChunkingDispatcher().dispatch(
        source=src,
        config=_config("full_text"),
        source_document_id=str(uuid4()),
        source_filename="acme.pdf",
    )
    assert chunks
    # Plain text chunker emits no heading_path metadata
    assert "heading_path" not in chunks[0].metadata


def test_dispatch_text_source_full_markdown_routes_to_markdown_service():
    md = "# Title\n\nbody " * 200
    src = TextSource(text=md)
    config = _config("full_markdown", chunking_strategy="markdown_heading")
    chunks = ChunkingDispatcher().dispatch(
        source=src,
        config=config,
        source_document_id=str(uuid4()),
        source_filename="acme.md",
    )
    assert chunks
    assert chunks[0].metadata.get("heading_path") == ["Title"]


def test_dispatch_text_source_passes_metadata_through():
    sdid = uuid4()
    src = TextSource(text="content " * 100)
    chunks = ChunkingDispatcher().dispatch(
        source=src,
        config=_config("full_text"),
        source_document_id=str(sdid),
        source_filename="acme.pdf",
    )
    assert chunks[0].metadata["source_filename"] == "acme.pdf"
    assert chunks[0].metadata["source_document_id"] == str(sdid)


def test_dispatch_blocks_source_raises_not_implemented():
    src = BlocksSource(blocks=[{"text": "foo"}])
    with pytest.raises(NotImplementedError, match="block"):
        ChunkingDispatcher().dispatch(
            source=src,
            config=_config("block"),
            source_document_id=str(uuid4()),
            source_filename=None,
        )


def test_dispatch_empty_text_returns_empty_list():
    src = TextSource(text="   ")
    assert ChunkingDispatcher().dispatch(
        source=src,
        config=_config("full_text"),
        source_document_id=str(uuid4()),
        source_filename=None,
    ) == []
```

- [ ] **2.2 Run tests — verify red.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/services/test_chunking_dispatcher.py -o "addopts=" -v
```

- [ ] **2.3 Implement (green).** `backend/app/services/chunking_dispatcher.py`:

```python
"""Dispatch a resolved ChunkSource + IndexConfig to the right chunker."""
from app.schemas.index import IndexConfig
from app.services.chunking_service import (
    ChunkResult,
    ChunkingService,
    get_chunking_service,
)
from app.services.markdown_chunking_service import (
    MarkdownChunkingService,
    get_markdown_chunking_service,
)
from app.services.source_resolution_service import (
    BlocksSource,
    ChunkSource,
    TextSource,
)


class ChunkingDispatcher:
    """Routes a `ChunkSource` to the right chunker based on the config."""

    def __init__(
        self,
        chunking_service: ChunkingService | None = None,
        markdown_chunking_service: MarkdownChunkingService | None = None,
    ) -> None:
        self.chunking_service = chunking_service or get_chunking_service()
        self.markdown_chunking_service = (
            markdown_chunking_service or get_markdown_chunking_service()
        )

    def dispatch(
        self,
        *,
        source: ChunkSource,
        config: IndexConfig,
        source_document_id: str | None = None,
        source_filename: str | None = None,
    ) -> list[ChunkResult]:
        if isinstance(source, TextSource):
            if config.source_representation == "full_markdown":
                return self.markdown_chunking_service.chunk_markdown(
                    markdown=source.text,
                    config=config,
                    source_document_id=source_document_id,
                    source_filename=source_filename,
                )
            return self.chunking_service.chunk_text(
                text=source.text,
                config=config,
                source_document_id=source_document_id,
                source_filename=source_filename,
                page_boundaries=None,  # CDM page boundaries: see Unit 6 notes
            )
        if isinstance(source, BlocksSource):
            raise NotImplementedError(
                "block-based chunking is not yet implemented"
            )
        raise TypeError(f"Unsupported ChunkSource type: {type(source).__name__}")
```

- [ ] **2.4 Run tests — verify green.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/services/test_chunking_dispatcher.py -o "addopts=" -v
```
Expected: 5 passing.

- [ ] **2.5 Commit.**

```bash
git -C /home/asa/rag-admin add \
  backend/app/services/chunking_dispatcher.py \
  backend/tests/services/test_chunking_dispatcher.py
git -C /home/asa/rag-admin commit -m "feat(services): ChunkingDispatcher — route ChunkSource through existing chunkers"
```

---

### Task 3 — Wire `IndexProcessingService` through the seam (CDM branches)

**Files:**
- Modify: `backend/app/services/index_processing_service.py:170-235` (the dispatch block inside `process_index()`)
- Modify: `backend/tests/services/test_index_processing_cdm.py`

- [ ] **3.1 Pin existing CDM test behaviour (red, then green by refactor).** Read `backend/tests/services/test_index_processing_cdm.py` and identify the tests that exercise `full_text` and `full_markdown` save paths. Run them before refactor:

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/services/test_index_processing_cdm.py -o "addopts=" -v
```
All tests should be green at this point — they pin the current behaviour. The refactor must keep them green.

- [ ] **3.2 Refactor the CDM dispatch block in `process_index()`.** In `backend/app/services/index_processing_service.py`, replace the `elif config.source_representation == "full_text":` and `elif config.source_representation == "full_markdown":` branches (~lines 195-230 on the slice-2 head; the actual range will shift after merge — locate by content) with a single seam-driven block. The `raw_text` branch is left untouched.

Before:

```python
elif config.source_representation == "full_text":
    parsed_doc_repo = ParsedDocumentRepository(self.session)
    parsed_doc = await parsed_doc_repo.get_by_run(index_doc.parse_run_id)
    if not parsed_doc or not parsed_doc.full_text:
        raise ValueError(
            f"Parse run {index_doc.parse_run_id} did not produce full_text. "
            "Re-parse with a configuration that outputs full text."
        )
    source_type = "full_text"
    doc_parse_run_id = index_doc.parse_run_id
    chunks = self.chunking_service.chunk_text(
        text=parsed_doc.full_text,
        config=config,
        source_document_id=str(doc_id),
        source_filename=document.source_metadata.get("filename"),
        page_boundaries=document.processing_metadata.get("page_boundaries")
            if document.processing_metadata else None,
    )
elif config.source_representation == "full_markdown":
    parsed_doc_repo = ParsedDocumentRepository(self.session)
    parsed_doc = await parsed_doc_repo.get_by_run(index_doc.parse_run_id)
    if not parsed_doc or not parsed_doc.full_markdown:
        raise ValueError(
            "Parse run did not produce full_markdown. "
            "Re-parse the document with a configuration that outputs markdown."
        )
    source_type = "full_markdown"
    doc_parse_run_id = index_doc.parse_run_id
    chunks = self.markdown_chunking_service.chunk_markdown(
        markdown=parsed_doc.full_markdown,
        config=config,
        source_document_id=str(doc_id),
        source_filename=document.source_metadata.get("filename"),
    )
```

After:

```python
elif config.source_representation in ("full_text", "full_markdown", "block"):
    # CDM seam: shared with chunk preview.
    source = await self.source_resolver.resolve(
        parsed_document_id=index_doc.parse_run_id,
        source_representation=config.source_representation,
    )
    # Pass filename from Document.source_metadata so chunk metadata is
    # byte-identical with the pre-refactor save behaviour.
    chunks = self.chunking_dispatcher.dispatch(
        source=source,
        config=config,
        source_document_id=str(doc_id),
        source_filename=document.source_metadata.get("filename"),
    )
    source_type = config.source_representation
    doc_parse_run_id = index_doc.parse_run_id
```

Update the constructor / `__init__` to instantiate the seam pieces:

```python
from app.services.chunking_dispatcher import ChunkingDispatcher
from app.services.source_resolution_service import SourceResolutionService

class IndexProcessingService:
    def __init__(
        self,
        session: AsyncSession,
        index_repo: IndexRepository,
        chunk_repo: ChunkRepository,
        provider_key_repo: ProviderKeyRepository,
    ):
        self.session = session
        self.index_repo = index_repo
        self.chunk_repo = chunk_repo
        self.provider_key_service = ProviderKeyService(provider_key_repo)
        # Seam dependencies:
        self.source_resolver = SourceResolutionService(session)
        self.chunking_dispatcher = ChunkingDispatcher()
        # Legacy raw_text branch still uses these directly:
        self.chunking_service = get_chunking_service()
```

Drop the `markdown_chunking_service` instance attribute and the `parsed_doc_repo = ParsedDocumentRepository(self.session)` lines inside the loop — both are subsumed by the seam. Keep the unused-import removal tidy.

- [ ] **3.3 Run CDM tests — verify still green.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/services/test_index_processing_cdm.py -o "addopts=" -v
```
Expected: same set of tests passing. If a test fails because it patches `markdown_chunking_service` directly, update the patch to target `ChunkingDispatcher.dispatch` (or the dispatcher instance on the service).

- [ ] **3.4 Add a seam-pinning test.** Append to `tests/services/test_index_processing_cdm.py`:

```python
@pytest.mark.asyncio
async def test_process_index_full_markdown_calls_seam(monkeypatch, ...):
    """Save path resolves source via SourceResolutionService and dispatches via ChunkingDispatcher."""
    from app.services.source_resolution_service import (
        SourceResolutionService,
        TextSource,
    )
    from app.services.chunking_dispatcher import ChunkingDispatcher

    resolved: list = []
    dispatched: list = []

    original_resolve = SourceResolutionService.resolve
    async def spy_resolve(self, **kwargs):
        result = await original_resolve(self, **kwargs)
        resolved.append((kwargs, result))
        return result
    monkeypatch.setattr(SourceResolutionService, "resolve", spy_resolve)

    original_dispatch = ChunkingDispatcher.dispatch
    def spy_dispatch(self, **kwargs):
        dispatched.append(kwargs)
        return original_dispatch(self, **kwargs)
    monkeypatch.setattr(ChunkingDispatcher, "dispatch", spy_dispatch)

    # ... seed an index with full_markdown source_representation, run process_index ...

    assert len(resolved) == 1
    assert resolved[0][0]["source_representation"] == "full_markdown"
    assert isinstance(resolved[0][1], TextSource)
    assert dispatched
```

(Use the existing seeded-fixture pattern in the file; keep the test focused on the seam call, not on full chunking output.)

- [ ] **3.5 Run the new test.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/services/test_index_processing_cdm.py::test_process_index_full_markdown_calls_seam -o "addopts=" -v
```

- [ ] **3.6 Commit.**

```bash
git -C /home/asa/rag-admin add backend/app/services/index_processing_service.py backend/tests/services/test_index_processing_cdm.py
git -C /home/asa/rag-admin commit -m "refactor(index): route CDM save path through SourceResolutionService + ChunkingDispatcher"
```

---

### Task 4 — Bridge helper: `ParsedDocumentRepository.get_latest_for_document`

This method exists *only* to support the slice-2 wizard's preview button until the parsed-doc picker lands in Unit 4. Unit 3 deletes the call sites that need it; the method can then be removed.

**Files:**
- Modify: `backend/app/repositories/parsed_document_repository.py`
- Create: `backend/tests/repositories/test_parsed_document_repository_get_latest.py`

- [ ] **4.1 Write failing tests (red).**

```python
"""Tests for ParsedDocumentRepository.get_latest_for_document — bridge helper."""
import pytest
from uuid import uuid4

from app.repositories.parsed_document_repository import ParsedDocumentRepository


@pytest.mark.asyncio
async def test_get_latest_for_document_returns_newest_succeeded_run(
    seeded_document_with_two_succeeded_parse_runs, db_session
):
    repo = ParsedDocumentRepository(db_session)
    result = await repo.get_latest_for_document(
        seeded_document_with_two_succeeded_parse_runs.id
    )
    assert result is not None
    # Fixture should make the second run the newer one
    assert result.parse_run_id == (
        seeded_document_with_two_succeeded_parse_runs.latest_parse_run_id
    )


@pytest.mark.asyncio
async def test_get_latest_for_document_skips_failed_runs(
    seeded_document_with_failed_then_succeeded_run, db_session
):
    repo = ParsedDocumentRepository(db_session)
    result = await repo.get_latest_for_document(
        seeded_document_with_failed_then_succeeded_run.id
    )
    assert result is not None
    assert result.parse_run_id == (
        seeded_document_with_failed_then_succeeded_run.succeeded_parse_run_id
    )


@pytest.mark.asyncio
async def test_get_latest_for_document_returns_none_when_no_runs(seeded_document_no_parse_runs, db_session):
    repo = ParsedDocumentRepository(db_session)
    assert await repo.get_latest_for_document(seeded_document_no_parse_runs.id) is None


@pytest.mark.asyncio
async def test_get_latest_for_document_returns_none_for_unknown_document(db_session):
    repo = ParsedDocumentRepository(db_session)
    assert await repo.get_latest_for_document(uuid4()) is None
```

(If the named fixtures don't exist, lift the seeding pattern from `tests/repositories/test_parsed_document_repository_listing.py` from Unit 1.)

- [ ] **4.2 Run tests — verify red.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/repositories/test_parsed_document_repository_get_latest.py -o "addopts=" -v
```

- [ ] **4.3 Implement.** Add to `backend/app/repositories/parsed_document_repository.py`:

```python
async def get_latest_for_document(
    self, document_id: UUID
) -> ParsedDocument | None:
    """Return the newest succeeded parsed-document for a Document.

    BRIDGE — used only by the chunk-preview endpoint while the slice-2
    wizard lacks a parsed-doc picker. Removed in Unit 3 once the wizard
    sends `parsedDocumentId` directly.

    Join path: Document.source_document_id == ParseRun.source_document_id
    (Document points at SourceDocument; SourceDocument has no back-link.)
    """
    stmt = (
        select(ParsedDocument)
        .join(ParseRun, ParseRun.id == ParsedDocument.parse_run_id)
        .join(DocumentORM, DocumentORM.source_document_id == ParseRun.source_document_id)
        .where(
            DocumentORM.id == document_id,
            ParseRun.status == "succeeded",
        )
        .order_by(ParseRun.finished_at.desc())
        .limit(1)
    )
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none()
```

`DocumentORM` and `ParseRun` are already imported at the top of the file from Unit 1. No new imports needed.

- [ ] **4.4 Run tests — verify green.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/repositories/test_parsed_document_repository_get_latest.py -o "addopts=" -v
```

- [ ] **4.5 Commit.**

```bash
git -C /home/asa/rag-admin add backend/app/repositories/parsed_document_repository.py backend/tests/repositories/test_parsed_document_repository_get_latest.py
git -C /home/asa/rag-admin commit -m "feat(repos): get_latest_for_document bridge helper for chunk preview"
```

---

### Task 5 — Update `ChunkPreviewRequest` schema and the preview endpoint

**Files:**
- Modify: `backend/app/schemas/index.py:247-253`
- Modify: `backend/app/routers/indexes.py:585-621`
- Create: `backend/tests/routers/test_preview_chunks_router.py` (or extend existing index router tests)

- [ ] **5.1 Update `ChunkPreviewRequest` schema (no test yet — covered by router tests).** In `backend/app/schemas/index.py`:

```python
class ChunkPreviewRequest(BaseModel):
    """Schema for previewing chunks before processing.

    Exactly one of `document_id` (legacy raw_text path / slice-2 wizard bridge)
    or `parsed_document_id` (CDM path, matches the eventual spec shape) must be
    supplied. `document_id` is removed in Unit 3.
    """
    document_id: UUID | None = Field(default=None, alias="documentId")
    parsed_document_id: UUID | None = Field(default=None, alias="parsedDocumentId")
    config: IndexConfig
    max_chunks: int = Field(default=5, ge=1, le=20, alias="maxChunks")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def exactly_one_handle(self) -> "ChunkPreviewRequest":
        provided = [self.document_id is not None, self.parsed_document_id is not None]
        if sum(provided) != 1:
            raise ValueError(
                "Exactly one of documentId or parsedDocumentId must be provided"
            )
        return self
```

Add `model_validator` to the existing `from pydantic import ...` line if not already imported.

- [ ] **5.2 Write router tests (red).** Add to `backend/tests/routers/test_preview_chunks_router.py` (create file if needed, mirroring patterns from existing router tests):

```python
"""Tests for POST /projects/{project_id}/indexes/preview-chunks."""
import pytest
from uuid import uuid4


@pytest.mark.asyncio
async def test_preview_chunks_validates_exactly_one_handle(client, auth_headers, project):
    body = {
        "config": {
            "sourceRepresentation": "full_text",
            "chunkingStrategy": "recursive_character",
            "chunkSize": 500,
            "chunkOverlap": 50,
            "chunkUnit": "characters",
            "embeddingProvider": "openai",
            "embeddingModel": "text-embedding-3-small",
        },
    }
    resp = await client.post(
        f"/api/v1/projects/{project.id}/indexes/preview-chunks",
        json=body, headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_preview_chunks_with_parsed_document_id_full_markdown(
    client, auth_headers, project, seeded_parsed_document_with_markdown
):
    body = {
        "parsedDocumentId": str(seeded_parsed_document_with_markdown.parse_run_id),
        "config": {
            "sourceRepresentation": "full_markdown",
            "chunkingStrategy": "markdown_heading",
            "splitHeadingLevel": 2,
            "maxSectionChars": 4000,
            "chunkSize": 500,
            "chunkOverlap": 50,
            "chunkUnit": "characters",
            "embeddingProvider": "openai",
            "embeddingModel": "text-embedding-3-small",
        },
    }
    resp = await client.post(
        f"/api/v1/projects/{project.id}/indexes/preview-chunks",
        json=body, headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["totalChunksEstimate"] >= 1
    assert data["previewChunks"]
    # ChunkPreview surfaces only index/content/charCount/tokenCount/overlaps —
    # not raw metadata. Heading-path correctness is pinned by
    # `MarkdownChunkingService` tests; this test pins that the preview *runs*
    # for full_markdown (band-aid `2a0cfa1` is gone).


@pytest.mark.asyncio
async def test_preview_chunks_bridge_document_id_full_markdown(
    client, auth_headers, project, seeded_document_with_markdown_parse_run
):
    """Bridge: when only documentId is supplied for a CDM mode, resolve to latest parsed-doc."""
    body = {
        "documentId": str(seeded_document_with_markdown_parse_run.id),
        "config": {
            "sourceRepresentation": "full_markdown",
            "chunkingStrategy": "markdown_heading",
            "splitHeadingLevel": 2,
            "maxSectionChars": 4000,
            "chunkSize": 500,
            "chunkOverlap": 50,
            "chunkUnit": "characters",
            "embeddingProvider": "openai",
            "embeddingModel": "text-embedding-3-small",
        },
    }
    resp = await client.post(
        f"/api/v1/projects/{project.id}/indexes/preview-chunks",
        json=body, headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["totalChunksEstimate"] >= 1


@pytest.mark.asyncio
async def test_preview_chunks_bridge_document_id_no_parse_run_returns_400(
    client, auth_headers, project, seeded_document_no_parse_runs
):
    body = {
        "documentId": str(seeded_document_no_parse_runs.id),
        "config": {
            "sourceRepresentation": "full_text",
            "chunkingStrategy": "recursive_character",
            "chunkSize": 500,
            "chunkOverlap": 50,
            "chunkUnit": "characters",
            "embeddingProvider": "openai",
            "embeddingModel": "text-embedding-3-small",
        },
    }
    resp = await client.post(
        f"/api/v1/projects/{project.id}/indexes/preview-chunks",
        json=body, headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "parse" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_preview_chunks_legacy_raw_text_path_unchanged(
    client, auth_headers, project, seeded_document_with_extracted_text
):
    """raw_text + documentId continues to read document.extracted_text."""
    body = {
        "documentId": str(seeded_document_with_extracted_text.id),
        "config": {
            "sourceRepresentation": "raw_text",
            "chunkingStrategy": "recursive_character",
            "chunkSize": 500,
            "chunkOverlap": 50,
            "chunkUnit": "characters",
            "embeddingProvider": "openai",
            "embeddingModel": "text-embedding-3-small",
        },
    }
    resp = await client.post(
        f"/api/v1/projects/{project.id}/indexes/preview-chunks",
        json=body, headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["totalChunksEstimate"] >= 1


@pytest.mark.asyncio
async def test_preview_chunks_parsed_document_outside_project_returns_404(
    client, auth_headers, project, parsed_document_in_other_project
):
    body = {
        "parsedDocumentId": str(parsed_document_in_other_project.parse_run_id),
        "config": {
            "sourceRepresentation": "full_text",
            "chunkingStrategy": "recursive_character",
            "chunkSize": 500,
            "chunkOverlap": 50,
            "chunkUnit": "characters",
            "embeddingProvider": "openai",
            "embeddingModel": "text-embedding-3-small",
        },
    }
    resp = await client.post(
        f"/api/v1/projects/{project.id}/indexes/preview-chunks",
        json=body, headers=auth_headers,
    )
    assert resp.status_code == 404
```

Reuse fixture names that already exist; otherwise extend `backend/tests/conftest.py` with the seeding factories shown.

- [ ] **5.3 Run router tests — verify red.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/routers/test_preview_chunks_router.py -o "addopts=" -v
```

- [ ] **5.4 Refactor the preview endpoint (green).** In `backend/app/routers/indexes.py`, replace the `preview_chunks` handler:

```python
@router.post(
    "/preview-chunks",
    response_model=ChunkPreviewResponse,
    summary="Preview chunks",
    description="Preview how a parsed-document would be chunked without processing.",
)
async def preview_chunks(
    project_id: UUID,
    data: ChunkPreviewRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    project_repo: ProjectRepository = Depends(get_project_repo),
    document_repo: DocumentRepository = Depends(get_document_repo),
):
    await verify_project_access(project_id, current_user, project_repo)

    config = data.config

    # Path 1: parsed_document_id provided — go straight through the seam.
    if data.parsed_document_id is not None:
        parsed_doc_repo = ParsedDocumentRepository(db)
        parsed_doc = await parsed_doc_repo.get_by_run(data.parsed_document_id)
        if parsed_doc is None:
            raise HTTPException(404, f"Parsed document {data.parsed_document_id} not found")
        # Project scoping: a Document in this project must reference the same
        # SourceDocument the parsed-doc points at.
        scope_stmt = (
            select(Document.id)
            .where(
                Document.source_document_id == parsed_doc.source_document_id,
                Document.project_id == project_id,
            )
            .limit(1)
        )
        scope_result = await db.execute(scope_stmt)
        if scope_result.scalar_one_or_none() is None:
            raise HTTPException(
                404, f"Parsed document {data.parsed_document_id} not in project"
            )

        # Preview metadata (source_document_id, source_filename) doesn't appear
        # in the ChunkPreview response, so passing None is safe.
        return await _preview_via_seam(
            db=db,
            parsed_document_id=data.parsed_document_id,
            config=config,
            source_document_id=None,
            source_filename=None,
            max_chunks=data.max_chunks,
        )

    # Path 2: document_id (bridge / legacy raw_text).
    document = await document_repo.get_by_id(data.document_id, current_user.id)
    if document is None or document.project_id != project_id:
        raise HTTPException(404, f"Document {data.document_id} not found")

    if config.source_representation == "raw_text":
        # Legacy untouched path — Unit 3 deletes this branch.
        if not document.extracted_text:
            raise HTTPException(400, "Document has no extracted text")
        return get_chunking_service().preview_chunks(
            text=document.extracted_text,
            config=config,
            max_chunks=data.max_chunks,
        )

    # CDM mode + bridge: resolve to latest parsed-doc for the document.
    parsed_doc_repo = ParsedDocumentRepository(db)
    parsed_doc = await parsed_doc_repo.get_latest_for_document(data.document_id)
    if parsed_doc is None:
        raise HTTPException(
            400,
            f"Document {data.document_id} has no succeeded parse runs. "
            "Parse the document before previewing CDM chunks.",
        )
    return await _preview_via_seam(
        db=db,
        parsed_document_id=parsed_doc.parse_run_id,
        config=config,
        source_document_id=None,
        source_filename=None,
        max_chunks=data.max_chunks,
    )


async def _preview_via_seam(
    *,
    db: AsyncSession,
    parsed_document_id: UUID,
    config: IndexConfig,
    source_document_id: str | None,
    source_filename: str | None,
    max_chunks: int,
) -> ChunkPreviewResponse:
    """Shared seam: resolve_source -> dispatch -> stats/preview projection."""
    try:
        source = await SourceResolutionService(db).resolve(
            parsed_document_id=parsed_document_id,
            source_representation=config.source_representation,
        )
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except ValidationError as e:
        raise HTTPException(400, str(e))

    try:
        all_chunks = ChunkingDispatcher().dispatch(
            source=source,
            config=config,
            source_document_id=source_document_id,
            source_filename=source_filename,
        )
    except NotImplementedError as e:
        raise HTTPException(501, str(e))

    return _project_to_preview_response(all_chunks, config, max_chunks)


def _project_to_preview_response(
    all_chunks: list[ChunkResult],
    config: IndexConfig,
    max_chunks: int,
) -> ChunkPreviewResponse:
    if not all_chunks:
        return ChunkPreviewResponse(
            total_chunks_estimate=0,
            avg_chunk_size_chars=0,
            avg_chunk_size_tokens=0,
            min_chunk_size_chars=0,
            max_chunk_size_chars=0,
            preview_chunks=[],
        )
    char_counts = [c.char_count for c in all_chunks]
    token_counts = [c.token_count for c in all_chunks]
    preview_chunks = []
    for i, chunk in enumerate(all_chunks[:max_chunks]):
        overlap_start = (
            min(config.chunk_overlap, chunk.char_count // 2)
            if i > 0 and config.chunk_overlap > 0 else 0
        )
        overlap_end = (
            min(config.chunk_overlap, chunk.char_count // 2)
            if i < len(all_chunks) - 1 and config.chunk_overlap > 0 else 0
        )
        preview_chunks.append(ChunkPreview(
            index=chunk.chunk_index,
            content=chunk.content,
            char_count=chunk.char_count,
            token_count=chunk.token_count,
            overlap_start_chars=overlap_start,
            overlap_end_chars=overlap_end,
        ))
    return ChunkPreviewResponse(
        total_chunks_estimate=len(all_chunks),
        avg_chunk_size_chars=round(sum(char_counts) / len(char_counts), 1),
        avg_chunk_size_tokens=round(sum(token_counts) / len(token_counts), 1),
        min_chunk_size_chars=min(char_counts),
        max_chunk_size_chars=max(char_counts),
        preview_chunks=preview_chunks,
    )
```

(`_project_to_preview_response` is essentially the body of the existing `ChunkingService.preview_chunks` method, lifted to the router so both the legacy raw_text path and the seam path produce identical response shapes. If the existing `ChunkingService.preview_chunks` is the only caller, you may instead leave it intact and call it from the raw_text branch only — the router-level helper just makes the seam path symmetric.)

Add the imports at the top of `routers/indexes.py` (a few may already be present from existing routes):

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db  # adjust to whatever this codebase uses
from app.models.document import Document
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.services.chunking_dispatcher import ChunkingDispatcher
from app.services.chunking_service import ChunkResult, get_chunking_service
from app.services.exceptions import NotFoundError, ValidationError
from app.services.source_resolution_service import SourceResolutionService
```

- [ ] **5.5 Run router tests — verify green.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/routers/test_preview_chunks_router.py -o "addopts=" -v
```

- [ ] **5.6 Run the full backend suite to catch regressions.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest -o "addopts="
```

- [ ] **5.7 Commit.**

```bash
git -C /home/asa/rag-admin add \
  backend/app/schemas/index.py \
  backend/app/routers/indexes.py \
  backend/tests/routers/test_preview_chunks_router.py
git -C /home/asa/rag-admin commit -m "feat(routers): chunk preview through SourceResolutionService; accept parsedDocumentId"
```

---

### Task 6 — Frontend: lift the band-aid

**Files:**
- Modify: `frontend/src/types/index.ts:146-150`
- Modify: `frontend/src/api/indexes.ts:151-170`
- Modify: `frontend/src/components/indexes/IndexCreateDialog.tsx` (the `<ChunkPreviewPanel>` call site)
- Modify: `frontend/src/pages/CreateIndexPage.tsx` (parity)
- Modify: `frontend/src/components/indexes/IndexCreateDialog.test.tsx` (and any matching `CreateIndexPage` test)

- [ ] **6.1 Widen the `ChunkPreviewRequest` type.** In `frontend/src/types/index.ts`:

```ts
export interface ChunkPreviewRequest {
  documentId?: string
  parsedDocumentId?: string
  config: Partial<IndexConfig>
  maxChunks?: number
}
```

- [ ] **6.2 Send the full config and the right handle.** In `frontend/src/api/indexes.ts`:

```ts
export async function previewChunks(
  projectId: string,
  data: ChunkPreviewRequest
): Promise<ChunkPreviewResponse> {
  const config = data.config as IndexConfig
  const body: Record<string, unknown> = {
    config: {
      // Forward the full config — sourceRepresentation, parser, parseConfigHash,
      // and the markdown chunking knobs all matter for accurate preview.
      source_representation: config.sourceRepresentation,
      parser: config.parser,
      parse_config_hash: config.parseConfigHash,
      chunking_strategy: config.chunkingStrategy,
      chunk_size: config.chunkSize,
      chunk_overlap: config.chunkOverlap,
      chunk_unit: config.chunkUnit,
      split_heading_level: config.splitHeadingLevel,
      max_section_chars: config.maxSectionChars,
      embedding_provider: config.embeddingProvider,
      embedding_model: config.embeddingModel,
    },
    maxChunks: data.maxChunks ?? 5,
  }
  if (data.parsedDocumentId) body.parsedDocumentId = data.parsedDocumentId
  else if (data.documentId) body.documentId = data.documentId

  const response = await apiClient.post<ChunkPreviewResponse>(
    `/projects/${projectId}/indexes/preview-chunks`,
    body,
  )
  return response.data
}
```

(Drop any explicit `null` fields so the backend validator's "exactly one of" check fires correctly. Snake-case key conversion may already be auto-applied by `apiClient`; if so, keep camelCase here and let the client convert.)

- [ ] **6.3 Update `useIndexes.previewChunks` types** if the hook's parameter type narrows `ChunkPreviewRequest` (`frontend/src/hooks/useIndexes.ts:32`, `265-268`). The signature already takes the full `ChunkPreviewRequest`, so no change unless the call sites need new fields.

- [ ] **6.4 Lift the band-aid in `IndexCreateDialog.tsx`.** Find the `<ChunkPreviewPanel>` call (~line 456 on the slice-2 head). Change:

```tsx
<ChunkPreviewPanel
  preview={preview}
  isLoading={isPreviewLoading}
  onPreview={handlePreview}
  disabled={selectedDocumentIds.length === 0 || config.sourceRepresentation === 'full_markdown'}
/>
```

to:

```tsx
<ChunkPreviewPanel
  preview={preview}
  isLoading={isPreviewLoading}
  onPreview={handlePreview}
  disabled={selectedDocumentIds.length === 0}
/>
```

The `handlePreview` callback already passes `documentId: previewDocumentId`. The backend's bridge resolves this for CDM modes. No change to the preview-handler call needed yet.

- [ ] **6.5 Same band-aid lift in `CreateIndexPage.tsx`.** Locate the equivalent `disabled=` clause (`b7ab522` introduced parity) and remove the `config.sourceRepresentation === 'full_markdown'` term.

- [ ] **6.6 Update tests.** Search for the old assertion:

```bash
grep -rn "sourceRepresentation === 'full_markdown'\|'full_markdown'.*disabled\|disabled.*full_markdown" /home/asa/rag-admin/frontend/src
```

For tests asserting `Preview Chunks` is disabled when `full_markdown` is selected, invert the assertion (now enabled) and add a happy-path test that clicking it triggers `previewChunks`. Use the existing test utilities; mock `previewChunks` to resolve with the standard preview shape.

- [ ] **6.7 Run frontend lint, build, and tests.**

```bash
npm --prefix /home/asa/rag-admin/frontend run lint
npm --prefix /home/asa/rag-admin/frontend run build
npx --prefix /home/asa/rag-admin/frontend vitest run
```

- [ ] **6.8 Commit.**

```bash
git -C /home/asa/rag-admin add \
  frontend/src/types/index.ts \
  frontend/src/api/indexes.ts \
  frontend/src/components/indexes/IndexCreateDialog.tsx \
  frontend/src/pages/CreateIndexPage.tsx \
  frontend/src/components/indexes/IndexCreateDialog.test.tsx
# add any other test files modified
git -C /home/asa/rag-admin commit -m "fix(frontend): re-enable chunk preview for full_markdown after seam refactor"
```

---

### Task 7 — Verification

- [ ] **7.1 Full backend suite.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest -o "addopts="
```
Expected: all tests pass. New count = previous + (≥6 resolver + ≥5 dispatcher + ≥1 seam-pinning + ≥6 router + ≥4 repo) = **≥22 new tests**.

- [ ] **7.2 Frontend lint, build, vitest.**

```bash
npm --prefix /home/asa/rag-admin/frontend run lint
npm --prefix /home/asa/rag-admin/frontend run build
npx --prefix /home/asa/rag-admin/frontend vitest run
```

- [ ] **7.3 Manual smoke against local stack.**

```bash
docker compose -f /home/asa/rag-admin/docker-compose.local.yml up -d --build backend
```

For an existing project that has at least one `full_markdown` parsed-doc:

1. Open Create Index → pick a document → set `source_representation = full_markdown` → click `Preview Chunks`. Verify chunks render with heading paths.
2. Repeat with `source_representation = full_text`. Verify chunks render.
3. Repeat with `source_representation = raw_text` (legacy). Verify the legacy path still works for a document with `extracted_text`.
4. Pick a parsed-doc-less document with `source_representation = full_markdown`. Expect a 400 error toast: "no succeeded parse runs" (not the old greyed-out button).
5. Network tab: confirm the `/preview-chunks` POST body has `documentId` (bridge — Unit 4 will switch this to `parsedDocumentId` once the picker exists).

- [ ] **7.4 Confirm save-path behaviour didn't shift.** Create + auto-process a `full_markdown` index against a known document. Diff the resulting chunks (by content + heading_path metadata) against a chunked output produced before this branch was checked out (e.g. the pre-Unit-2 index of the same document). They should be byte-identical — the seam is a refactor, not a behaviour change.

---

## Manual verification checklist (to attach to the PR)

- [ ] `Preview Chunks` button is enabled for all `source_representation` values in Create Index.
- [ ] `full_markdown` preview returns chunks whose `metadata.heading_path` matches the document's heading structure.
- [ ] `full_text` preview returns plain-text chunks identical to those the save path produces.
- [ ] `raw_text` preview still uses `document.extracted_text` (untouched legacy path).
- [ ] Bridge: requesting `parsedDocumentId` directly (e.g. via API client) works end-to-end without going through `documentId`.
- [ ] Sending both `documentId` and `parsedDocumentId` returns 422.
- [ ] Sending neither returns 422.
- [ ] Sending a `parsedDocumentId` from another project returns 404.
- [ ] `IndexProcessingService.process_index()` produces byte-identical chunks for `full_text` and `full_markdown` indexes vs. pre-Unit-2 output (regression-pinned via existing tests).
- [ ] No new Alembic migration was generated.

---

## Out of scope (next units)

- **Unit 3:** `IndexCreate.parsed_document_ids` shape, `IndexConfig` validators (require `parser` + `parse_config_hash`), drop `raw_text` from the Literal, route renames (`POST /indexes/{id}/documents` → `/parsed-documents`), drop the `documentId` bridge from `ChunkPreviewRequest`, delete `ParsedDocumentRepository.get_latest_for_document`.
- **Unit 4:** Wizard rebuild — parse-config family selector + parsed-doc picker; switches the preview call to `parsedDocumentId` based on the picker selection.
- **Unit 5:** Index detail "Documents" tab → "Parsed Documents" with the new column shape.
- **Unit 6 (cleanup):** Cascade-delete legacy NULL-bearing index_documents rows and any indexes left empty; `ALTER COLUMN parsed_document_id SET NOT NULL`; consider implementing `block` chunking and removing the dispatcher's `NotImplementedError`.
