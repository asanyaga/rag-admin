# CDM Index Slice 3: Block Chunking + Citation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `BlockChunkingService` to group CDM `Block` objects into chunks by semantic role with full block provenance, expose a uniform `ChunkCitation` returned with every search result, and surface block config + citation footers in the UI.

**Architecture:** A new pure `BlockChunkingService` consumes `list[dict]` blocks from `BlocksSource` (already produced by `SourceResolutionService`) and returns `ChunkResult` objects whose `metadata` carries `block_ids`, `page_indices`, `block_roles`, `bboxes`, and (for continuation chunks) `context_heading`. `ChunkingDispatcher` gains a `BlocksSource` branch that calls this service. Citation is layered on top of search results: `QueryService._to_result` builds a `ChunkCitation` from `chunk_metadata` for all source types; for `source_type == "block"` it lazily fetches the `ParsedDocument` to resolve `block_ids → bboxes/pages/roles/confidence`. Frontend `CreateIndexPage` gains a third source-representation toggle (`block`) and an adaptive block config panel; `ResultCard` shows a citation footer that adapts to the source type.

**Tech Stack:** Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 (async) · pytest · React 18 · TypeScript · shadcn/ui (ToggleGroup, Slider, MultiSelect/Combobox) · Vitest + @testing-library/react

---

## File Map

| Action | Path | What changes |
|--------|------|-------------|
| Modify | `backend/app/schemas/index.py` | Add `group_by_heading`, `max_blocks_per_chunk`, `block_role_filter` to `IndexConfig` |
| Modify | `backend/tests/schemas/test_index_config_schema.py` | Tests for new fields & validators |
| **Create** | `backend/app/services/block_chunking_service.py` | New `BlockChunkingService` |
| **Create** | `backend/tests/services/test_block_chunking_service.py` | Block grouping algorithm tests |
| Modify | `backend/app/services/chunking_dispatcher.py` | Replace `NotImplementedError` with real `BlocksSource` branch |
| Modify | `backend/tests/services/test_chunking_dispatcher.py` | Update `BlocksSource` test from `NotImplementedError` to real dispatch |
| **Create** | `backend/app/schemas/citation.py` | `ChunkCitation` schema |
| Modify | `backend/app/schemas/query.py` | Add `citation: ChunkCitation \| None` to `RetrievalResult` |
| Modify | `backend/app/services/query_service.py` | Async citation resolver; build citation in `_to_result` (now async) |
| **Create** | `backend/tests/services/test_query_citation.py` | Citation-resolution tests |
| Modify | `frontend/src/types/index.ts` | Add `groupByHeading`, `maxBlocksPerChunk`, `blockRoleFilter`; add `ChunkCitation` type; add `citation` to `RetrievalResult` |
| Modify | `frontend/src/pages/CreateIndexPage.tsx` | `block` toggle in Step 3; block config panel in Step 5 |
| **Create** | `frontend/src/components/indexes/BlockConfigPanel.tsx` | Block-config form panel (extracted to keep CreateIndexPage tidy) |
| **Create** | `frontend/src/components/indexes/BlockConfigPanel.test.tsx` | Component test |
| Modify | `frontend/src/components/indexes/ResultCard.tsx` | Render `CitationFooter` |
| **Create** | `frontend/src/components/indexes/CitationFooter.tsx` | Adaptive citation footer |
| **Create** | `frontend/src/components/indexes/CitationFooter.test.tsx` | Component test |

---

## Conventions

- **`BlockRole` enum values are lowercase strings** (`"title"`, `"heading"`, `"paragraph"`, `"table"`, etc.) — see `backend/app/cdm/models.py:22`. Use lowercase consistently for `block_role_filter` config values, the `block_roles` provenance list, and frontend filter options. The spec uses uppercase names informally; the wire format is lowercase.
- **`Block` is a frozen Pydantic model**; tests construct blocks with `Block(id=..., role=BlockRole.HEADING, native_type="h1", page_index=0, text="...")`.
- **Layout-only blocks (`HEADER`, `FOOTER`, `MARGINALIA`) are always dropped** by the algorithm, even if explicitly listed in `block_role_filter`.
- **`max_blocks_per_chunk` never splits a single `TABLE` or `FIGURE` block**; if the existing group is already at capacity, those blocks form their own one-block group.
- **`source_representation == "block"` is already wired** through `SourceResolutionService` (returns `BlocksSource(blocks=[...])`) and `IndexProcessingService.process_index` (calls dispatcher with `source_type = "block"`). The only backend integration gap is the `NotImplementedError` in `ChunkingDispatcher` for `BlocksSource`.

---

## Task 1: Extend `IndexConfig` with block fields

**Files:**
- Modify: `backend/app/schemas/index.py:43-50` (insert after the markdown-config block, before embedding config)
- Modify: `backend/tests/schemas/test_index_config_schema.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/schemas/test_index_config_schema.py`:

```python
import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.index import IndexConfig


def _block_config(**overrides):
    base = dict(
        parser="llamaparse",
        parse_config_hash="h" * 64,
        source_representation="block",
        chunking_strategy="block",
    )
    base.update(overrides)
    return base


def test_block_config_defaults():
    cfg = IndexConfig(**_block_config())
    assert cfg.group_by_heading is True
    assert cfg.max_blocks_per_chunk == 10
    assert cfg.block_role_filter is None


def test_block_config_accepts_role_filter():
    cfg = IndexConfig(**_block_config(block_role_filter=["table", "figure"]))
    assert cfg.block_role_filter == ["table", "figure"]


def test_max_blocks_per_chunk_below_min_rejected():
    with pytest.raises(PydanticValidationError):
        IndexConfig(**_block_config(max_blocks_per_chunk=0))


def test_max_blocks_per_chunk_above_max_rejected():
    with pytest.raises(PydanticValidationError):
        IndexConfig(**_block_config(max_blocks_per_chunk=51))


def test_block_role_filter_accepts_camel_case_alias():
    cfg = IndexConfig.model_validate({
        "parser": "llamaparse",
        "parseConfigHash": "h" * 64,
        "sourceRepresentation": "block",
        "chunkingStrategy": "block",
        "groupByHeading": False,
        "maxBlocksPerChunk": 5,
        "blockRoleFilter": ["paragraph"],
    })
    assert cfg.group_by_heading is False
    assert cfg.max_blocks_per_chunk == 5
    assert cfg.block_role_filter == ["paragraph"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/schemas/test_index_config_schema.py -v`
Expected: 5 new tests FAIL with `AttributeError` / unknown-field validation errors.

- [ ] **Step 3: Add fields to `IndexConfig`**

In `backend/app/schemas/index.py`, after line 50 (after `max_section_chars`), insert:

```python
    # Block-based config (block, classified_block)
    group_by_heading: bool = Field(default=True, alias="groupByHeading")
    max_blocks_per_chunk: int = Field(
        default=10, ge=1, le=50, alias="maxBlocksPerChunk"
    )
    block_role_filter: list[str] | None = Field(
        default=None, alias="blockRoleFilter"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/schemas/test_index_config_schema.py -v`
Expected: all schema tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/index.py backend/tests/schemas/test_index_config_schema.py
git commit -m "feat(indexes): add block-config fields to IndexConfig"
```

---

## Task 2: Create `BlockChunkingService` skeleton + happy-path test

**Files:**
- Create: `backend/app/services/block_chunking_service.py`
- Create: `backend/tests/services/test_block_chunking_service.py`

The service receives `list[dict]` (raw block dicts from `ParsedDocument.content["blocks"]`) and validates each into a CDM `Block` for type-safe access. It returns `list[ChunkResult]`. Internally we run an iterative state machine described in the spec.

- [ ] **Step 1: Write the failing happy-path test**

Create `backend/tests/services/test_block_chunking_service.py`:

```python
"""Tests for BlockChunkingService."""
from app.cdm.models import BBox, Block, BlockRole, CoordSpace, Quality
from app.schemas.index import IndexConfig
from app.services.block_chunking_service import BlockChunkingService


def _config(**overrides) -> IndexConfig:
    base = dict(
        parser="llamaparse",
        parse_config_hash="h" * 64,
        source_representation="block",
        chunking_strategy="block",
    )
    base.update(overrides)
    return IndexConfig(**base)


def _bbox(y0: float = 0.0) -> BBox:
    return BBox(x0=0.1, y0=y0, x1=0.9, y1=y0 + 0.05, space=CoordSpace.NORMALIZED)


def _block(
    bid: str,
    role: BlockRole,
    text: str,
    page: int = 0,
    y0: float = 0.0,
    confidence: float | None = None,
) -> Block:
    quality = Quality(confidence=confidence) if confidence is not None else None
    return Block(
        id=bid,
        role=role,
        native_type=role.value,
        page_index=page,
        bbox=_bbox(y0),
        text=text,
        quality=quality,
    )


def test_block_chunking_groups_by_heading():
    """A HEADING + following PARAGRAPHs form a single chunk."""
    svc = BlockChunkingService()
    blocks = [
        _block("b1", BlockRole.HEADING, "Q3 Financial Results", y0=0.0).model_dump(),
        _block("b2", BlockRole.PARAGRAPH, "Revenue grew 12%.", y0=0.1).model_dump(),
        _block("b3", BlockRole.PARAGRAPH, "Margins held steady.", y0=0.2).model_dump(),
    ]
    chunks = svc.chunk_blocks(blocks=blocks, config=_config())

    assert len(chunks) == 1
    assert "Q3 Financial Results" in chunks[0].content
    assert "Revenue grew 12%." in chunks[0].content
    assert "Margins held steady." in chunks[0].content
    assert chunks[0].metadata["block_ids"] == ["b1", "b2", "b3"]
    assert chunks[0].metadata["block_roles"] == ["heading", "paragraph", "paragraph"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/test_block_chunking_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.block_chunking_service'`.

- [ ] **Step 3: Create the service module**

Create `backend/app/services/block_chunking_service.py`:

```python
"""Service for chunking a CDM ParsedDocument's blocks by semantic role.

Grouping algorithm (per spec slice 3):

1. Sort blocks by (page_index, bbox.y0). Blocks without a bbox sort to the
   top of their page (y0 treated as -infinity for ordering only).
2. Apply block_role_filter (whitelist) if set.
3. Iterate:
   - HEADER/FOOTER/MARGINALIA: skip entirely (layout, never content).
   - TITLE/HEADING: closes any open group, opens a new one with this block.
   - TABLE/FIGURE: never split. If group_by_heading and a group is open,
     append; else close the current group and emit a single-block group.
   - Other content roles (PARAGRAPH/LIST/CAPTION/CODE/FORMULA): append to
     the open group; if no group is open, start one without a heading.
4. If appending would push current group over max_blocks_per_chunk and the
   incoming block is NOT a TABLE/FIGURE, close the group and start a new one.
   The new group is a "continuation": its metadata records `context_heading`
   from the most recently seen TITLE/HEADING and the chunk content is
   prefixed with `[context: <heading>]`.
5. Close any open group at end.
"""
from __future__ import annotations

import tiktoken

from app.cdm.models import Block, BlockRole
from app.schemas.index import IndexConfig
from app.services.chunking_service import ChunkResult


_HEADING_OPENERS = {BlockRole.TITLE, BlockRole.HEADING}
_NEVER_SPLIT = {BlockRole.TABLE, BlockRole.FIGURE}
_LAYOUT_SKIP = {BlockRole.HEADER, BlockRole.FOOTER, BlockRole.MARGINALIA}


class BlockChunkingService:
    """Groups CDM blocks into chunks per the block-chunking spec."""

    def __init__(self) -> None:
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        return len(self._tokenizer.encode(text))

    def chunk_blocks(
        self,
        *,
        blocks: list[dict],
        config: IndexConfig,
        source_document_id: str | None = None,
        source_filename: str | None = None,
    ) -> list[ChunkResult]:
        if not blocks:
            return []

        # 1. Validate dicts → Block. Skip rows that fail validation defensively.
        validated: list[Block] = []
        for raw in blocks:
            try:
                validated.append(Block.model_validate(raw))
            except Exception:
                continue
        if not validated:
            return []

        # 2. Sort by (page_index, bbox.y0). y0 missing → -inf within its page.
        validated.sort(
            key=lambda b: (b.page_index, b.bbox.y0 if b.bbox else float("-inf"))
        )

        # 3. Apply role filter (whitelist).
        role_filter = (
            {r for r in (config.block_role_filter or [])} or None
        )
        if role_filter is not None:
            validated = [b for b in validated if b.role.value in role_filter]
        if not validated:
            return []

        # 4. Iterate.
        chunks: list[ChunkResult] = []
        current: list[Block] = []
        current_is_continuation = False
        last_heading_text: str | None = None
        chunk_index_counter = 0

        def emit_current() -> None:
            nonlocal chunk_index_counter, current, current_is_continuation
            if not current:
                return
            chunks.append(
                self._build_chunk(
                    blocks=current,
                    chunk_index=chunk_index_counter,
                    context_heading=last_heading_text if current_is_continuation else None,
                    source_document_id=source_document_id,
                    source_filename=source_filename,
                )
            )
            chunk_index_counter += 1
            current = []
            current_is_continuation = False

        for block in validated:
            if block.role in _LAYOUT_SKIP:
                continue

            # Heading opens a new group.
            if block.role in _HEADING_OPENERS:
                emit_current()
                last_heading_text = block.text or last_heading_text
                current.append(block)
                continue

            # Table / Figure: never split.
            if block.role in _NEVER_SPLIT:
                if config.group_by_heading and current:
                    current.append(block)
                else:
                    emit_current()
                    current.append(block)
                    emit_current()
                continue

            # Generic content block.
            if current and len(current) >= config.max_blocks_per_chunk:
                emit_current()
                current_is_continuation = True
            current.append(block)

        emit_current()
        return chunks

    def _build_chunk(
        self,
        *,
        blocks: list[Block],
        chunk_index: int,
        context_heading: str | None,
        source_document_id: str | None,
        source_filename: str | None,
    ) -> ChunkResult:
        body = "\n\n".join(b.text for b in blocks if b.text)
        if context_heading:
            content = f"[context: {context_heading}]\n\n{body}"
        else:
            content = body

        page_indices = sorted({b.page_index for b in blocks})
        bboxes = [
            (
                {"x0": b.bbox.x0, "y0": b.bbox.y0, "x1": b.bbox.x1, "y1": b.bbox.y1}
                if b.bbox
                else None
            )
            for b in blocks
        ]

        metadata: dict = {
            "chunk_index": chunk_index,
            "block_ids": [b.id for b in blocks],
            "page_indices": page_indices,
            "block_roles": [b.role.value for b in blocks],
            "bboxes": bboxes,
        }
        if context_heading:
            metadata["context_heading"] = context_heading
        if source_document_id:
            metadata["source_document_id"] = source_document_id
        if source_filename:
            metadata["source_filename"] = source_filename

        return ChunkResult(
            content=content,
            chunk_index=chunk_index,
            token_count=self.count_tokens(content),
            char_count=len(content),
            start_char=0,
            end_char=len(content),
            metadata=metadata,
        )


_block_chunking_service: BlockChunkingService | None = None


def get_block_chunking_service() -> BlockChunkingService:
    global _block_chunking_service
    if _block_chunking_service is None:
        _block_chunking_service = BlockChunkingService()
    return _block_chunking_service
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/test_block_chunking_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/block_chunking_service.py backend/tests/services/test_block_chunking_service.py
git commit -m "feat(indexes): add BlockChunkingService skeleton with heading-grouping happy path"
```

---

## Task 3: TABLE / FIGURE never-split test

**Files:**
- Modify: `backend/tests/services/test_block_chunking_service.py`

- [ ] **Step 1: Write the failing test**

Append to the test file:

```python
def test_block_chunking_table_not_split_when_cap_would_force_it():
    """A TABLE block always forms (or extends) a group; max_blocks_per_chunk
    never splits a single table off mid-table."""
    svc = BlockChunkingService()
    blocks = [
        _block("h1", BlockRole.HEADING, "Section", y0=0.0).model_dump(),
        _block("p1", BlockRole.PARAGRAPH, "Para 1", y0=0.1).model_dump(),
        _block("p2", BlockRole.PARAGRAPH, "Para 2", y0=0.2).model_dump(),
        _block("t1", BlockRole.TABLE, "table-text", y0=0.3).model_dump(),
    ]
    chunks = svc.chunk_blocks(blocks=blocks, config=_config(max_blocks_per_chunk=3))

    # Heading + 2 paragraphs hit cap, table joins via group_by_heading default.
    # Spec: TABLE never splits. Either it appends to current open group
    # (group_by_heading=True) or it closes and forms its own one-block group.
    table_chunks = [c for c in chunks if "t1" in c.metadata["block_ids"]]
    assert len(table_chunks) == 1
    assert table_chunks[0].metadata["block_ids"].count("t1") == 1


def test_block_chunking_table_standalone_when_no_open_group():
    """When group_by_heading=False, TABLE blocks emit their own one-block chunk."""
    svc = BlockChunkingService()
    blocks = [
        _block("t1", BlockRole.TABLE, "table-text", y0=0.0).model_dump(),
        _block("t2", BlockRole.TABLE, "another-table", y0=0.1).model_dump(),
    ]
    chunks = svc.chunk_blocks(blocks=blocks, config=_config(group_by_heading=False))

    assert len(chunks) == 2
    assert chunks[0].metadata["block_ids"] == ["t1"]
    assert chunks[1].metadata["block_ids"] == ["t2"]
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/test_block_chunking_service.py -v`
Expected: both PASS (the algorithm in Task 2 already handles this).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/services/test_block_chunking_service.py
git commit -m "test(indexes): cover TABLE/FIGURE never-split in BlockChunkingService"
```

---

## Task 4: max_blocks_per_chunk cap + context_heading on continuation

**Files:**
- Modify: `backend/tests/services/test_block_chunking_service.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_block_chunking_max_blocks_cap_emits_continuation_with_context():
    """When a group exceeds max_blocks_per_chunk, the next chunk is a
    continuation tagged with the most recent heading."""
    svc = BlockChunkingService()
    blocks = [
        _block("h1", BlockRole.HEADING, "Big Section", y0=0.0).model_dump(),
        *[
            _block(f"p{i}", BlockRole.PARAGRAPH, f"para {i}", y0=0.1 + i * 0.01).model_dump()
            for i in range(6)
        ],
    ]
    # Cap at 3 → first chunk = heading + 2 paras, second = 3 paras (continuation),
    # third = 1 para (continuation). Continuation chunks carry context_heading.
    chunks = svc.chunk_blocks(blocks=blocks, config=_config(max_blocks_per_chunk=3))

    assert len(chunks) == 3
    assert "context_heading" not in chunks[0].metadata
    assert chunks[0].content.startswith("Big Section")
    for cont in chunks[1:]:
        assert cont.metadata.get("context_heading") == "Big Section"
        assert cont.content.startswith("[context: Big Section]")
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/test_block_chunking_service.py::test_block_chunking_max_blocks_cap_emits_continuation_with_context -v`
Expected: PASS (Task 2 algorithm already tracks `last_heading_text` and `current_is_continuation`).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/services/test_block_chunking_service.py
git commit -m "test(indexes): cover max-blocks cap with context-heading continuation"
```

---

## Task 5: role filter, layout skip, no-headings, provenance

**Files:**
- Modify: `backend/tests/services/test_block_chunking_service.py`

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_block_chunking_role_filter_applies_whitelist():
    svc = BlockChunkingService()
    blocks = [
        _block("h1", BlockRole.HEADING, "H", y0=0.0).model_dump(),
        _block("p1", BlockRole.PARAGRAPH, "para", y0=0.1).model_dump(),
        _block("t1", BlockRole.TABLE, "tab", y0=0.2).model_dump(),
    ]
    chunks = svc.chunk_blocks(
        blocks=blocks, config=_config(block_role_filter=["table"])
    )

    assert len(chunks) == 1
    assert chunks[0].metadata["block_ids"] == ["t1"]
    assert chunks[0].metadata["block_roles"] == ["table"]


def test_block_chunking_skips_layout_blocks():
    svc = BlockChunkingService()
    blocks = [
        _block("hd", BlockRole.HEADER, "running header", y0=0.0).model_dump(),
        _block("h1", BlockRole.HEADING, "Real heading", y0=0.05).model_dump(),
        _block("p1", BlockRole.PARAGRAPH, "real para", y0=0.1).model_dump(),
        _block("ft", BlockRole.FOOTER, "page 1 of 5", y0=0.95).model_dump(),
        _block("mg", BlockRole.MARGINALIA, "[note]", y0=0.5).model_dump(),
    ]
    chunks = svc.chunk_blocks(blocks=blocks, config=_config())

    all_ids = {bid for c in chunks for bid in c.metadata["block_ids"]}
    assert "hd" not in all_ids
    assert "ft" not in all_ids
    assert "mg" not in all_ids
    assert all_ids == {"h1", "p1"}


def test_block_chunking_layout_skipped_even_when_in_filter():
    """Layout blocks are dropped even if explicitly listed in block_role_filter."""
    svc = BlockChunkingService()
    blocks = [
        _block("hd", BlockRole.HEADER, "noise", y0=0.0).model_dump(),
        _block("p1", BlockRole.PARAGRAPH, "real", y0=0.1).model_dump(),
    ]
    chunks = svc.chunk_blocks(
        blocks=blocks, config=_config(block_role_filter=["header", "paragraph"])
    )
    all_ids = {bid for c in chunks for bid in c.metadata["block_ids"]}
    assert "hd" not in all_ids
    assert "p1" in all_ids


def test_block_chunking_no_headings_groups_all_content():
    svc = BlockChunkingService()
    blocks = [
        _block(f"p{i}", BlockRole.PARAGRAPH, f"para {i}", y0=0.1 * i).model_dump()
        for i in range(4)
    ]
    chunks = svc.chunk_blocks(blocks=blocks, config=_config(max_blocks_per_chunk=10))

    assert len(chunks) == 1
    assert chunks[0].metadata["block_ids"] == ["p0", "p1", "p2", "p3"]
    assert "context_heading" not in chunks[0].metadata


def test_block_chunking_provenance_fields_populated():
    svc = BlockChunkingService()
    blocks = [
        _block("h1", BlockRole.HEADING, "Heading", page=2, y0=0.0).model_dump(),
        _block("p1", BlockRole.PARAGRAPH, "paragraph A", page=2, y0=0.1).model_dump(),
        _block("p2", BlockRole.PARAGRAPH, "paragraph B", page=3, y0=0.0).model_dump(),
    ]
    chunks = svc.chunk_blocks(
        blocks=blocks,
        config=_config(),
        source_document_id="doc-1",
        source_filename="report.pdf",
    )

    meta = chunks[0].metadata
    assert meta["block_ids"] == ["h1", "p1", "p2"]
    assert meta["page_indices"] == [2, 3]
    assert meta["block_roles"] == ["heading", "paragraph", "paragraph"]
    assert len(meta["bboxes"]) == 3
    for bb in meta["bboxes"]:
        assert set(bb.keys()) == {"x0", "y0", "x1", "y1"}
    assert meta["source_document_id"] == "doc-1"
    assert meta["source_filename"] == "report.pdf"


def test_block_chunking_bbox_null_when_block_has_no_bbox():
    svc = BlockChunkingService()
    block_dict = Block(
        id="b1",
        role=BlockRole.PARAGRAPH,
        native_type="p",
        page_index=0,
        text="no bbox",
    ).model_dump()
    chunks = svc.chunk_blocks(blocks=[block_dict], config=_config())

    assert chunks[0].metadata["bboxes"] == [None]


def test_block_chunking_empty_input_returns_empty():
    svc = BlockChunkingService()
    assert svc.chunk_blocks(blocks=[], config=_config()) == []
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/test_block_chunking_service.py -v`
Expected: ALL PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/services/test_block_chunking_service.py
git commit -m "test(indexes): cover role filter, layout skip, no-headings, provenance"
```

---

## Task 6: Wire `BlockChunkingService` into `ChunkingDispatcher`

**Files:**
- Modify: `backend/app/services/chunking_dispatcher.py`
- Modify: `backend/tests/services/test_chunking_dispatcher.py:65-73`

- [ ] **Step 1: Update the failing dispatcher test**

Replace the `test_dispatch_blocks_source_raises_not_implemented` test in `backend/tests/services/test_chunking_dispatcher.py` with:

```python
def test_dispatch_blocks_source_routes_to_block_service():
    from app.cdm.models import BBox, Block, BlockRole, CoordSpace

    bbox = BBox(x0=0.0, y0=0.0, x1=1.0, y1=0.05, space=CoordSpace.NORMALIZED)
    blocks = [
        Block(
            id="b1",
            role=BlockRole.HEADING,
            native_type="h1",
            page_index=0,
            bbox=bbox,
            text="Heading",
        ).model_dump(),
        Block(
            id="b2",
            role=BlockRole.PARAGRAPH,
            native_type="p",
            page_index=0,
            bbox=bbox.model_copy(update={"y0": 0.1, "y1": 0.2}),
            text="Body paragraph",
        ).model_dump(),
    ]
    src = BlocksSource(blocks=blocks)
    chunks = ChunkingDispatcher().dispatch(
        source=src,
        config=_config("block", "block"),
        source_document_id=str(uuid4()),
        source_filename="acme.pdf",
    )

    assert len(chunks) == 1
    assert chunks[0].metadata["block_ids"] == ["b1", "b2"]
    assert chunks[0].metadata["page_indices"] == [0]
    assert chunks[0].metadata["block_roles"] == ["heading", "paragraph"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/test_chunking_dispatcher.py::test_dispatch_blocks_source_routes_to_block_service -v`
Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Wire `BlockChunkingService` into the dispatcher**

Replace the contents of `backend/app/services/chunking_dispatcher.py` with:

```python
"""Dispatch a resolved ChunkSource + IndexConfig to the right chunker."""
from app.schemas.index import IndexConfig
from app.services.block_chunking_service import (
    BlockChunkingService,
    get_block_chunking_service,
)
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
        block_chunking_service: BlockChunkingService | None = None,
    ) -> None:
        self.chunking_service = chunking_service or get_chunking_service()
        self.markdown_chunking_service = (
            markdown_chunking_service or get_markdown_chunking_service()
        )
        self.block_chunking_service = (
            block_chunking_service or get_block_chunking_service()
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
            # full_text uses the plain-text chunker.
            return self.chunking_service.chunk_text(
                text=source.text,
                config=config,
                source_document_id=source_document_id,
                source_filename=source_filename,
                page_boundaries=None,
            )
        if isinstance(source, BlocksSource):
            if config.chunking_strategy == "classified_block":
                raise NotImplementedError(
                    "classified_block chunking requires a classification run "
                    "and is not yet implemented"
                )
            return self.block_chunking_service.chunk_blocks(
                blocks=source.blocks,
                config=config,
                source_document_id=source_document_id,
                source_filename=source_filename,
            )
        raise TypeError(f"Unsupported ChunkSource type: {type(source).__name__}")
```

- [ ] **Step 4: Run all dispatcher + block tests**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/test_chunking_dispatcher.py tests/services/test_block_chunking_service.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/chunking_dispatcher.py backend/tests/services/test_chunking_dispatcher.py
git commit -m "feat(indexes): route BlocksSource to BlockChunkingService in dispatcher"
```

---

## Task 7: End-to-end processing test (`source_representation = block`)

The processing service already dispatches `block` (see `backend/app/services/index_processing_service.py:175`). With Task 6 in place, the full pipeline now produces real block chunks. Add an integration test that exercises this path.

**Files:**
- Modify: `backend/tests/services/test_index_processing_cdm.py`

- [ ] **Step 1: Inspect the existing CDM processing test for the markdown pattern**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/test_index_processing_cdm.py --collect-only -q`
Expected: lists existing tests; identify the `full_markdown` end-to-end test as the structural template (uses real DB session + mocked embedding provider).

- [ ] **Step 2: Add the failing block end-to-end test**

Append a test mirroring the markdown test pattern but with `source_representation="block"`. Construct a parsed-document fixture whose `content["blocks"]` contains 1 heading + 2 paragraphs (use `Block(...).model_dump()` like in Task 2). Set `index_doc.parse_run_id` to the parsed-document handle. After running `process_index`, assert:

```python
chunks = await chunk_repo.list_for_index(index_id=index.id)
assert len(chunks) == 1
chunk = chunks[0]
assert chunk.source_type == "block"
assert chunk.parse_run_id is not None
assert chunk.chunk_metadata["block_ids"] == ["b1", "b2", "b3"]
assert chunk.chunk_metadata["block_roles"] == ["heading", "paragraph", "paragraph"]
assert chunk.chunk_metadata["page_indices"] == [0]
```

(Reuse the helpers from `tests/services/test_block_chunking_service.py` for block construction; copy them inline if the existing CDM-processing test file does not import them.)

- [ ] **Step 3: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/test_index_processing_cdm.py -v`
Expected: new test PASSES; existing tests remain PASSING.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/services/test_index_processing_cdm.py
git commit -m "test(indexes): end-to-end block-source processing through pipeline"
```

---

## Task 8: Add `ChunkCitation` schema

**Files:**
- Create: `backend/app/schemas/citation.py`

- [ ] **Step 1: Create the schema**

Create `backend/app/schemas/citation.py`:

```python
"""Uniform citation schema returned with every search result.

Fields are populated based on the chunk's `source_type`:
- text-based (`raw_text`, `full_text`): start_char, end_char, page_numbers
- markdown-based (`full_markdown`): start_char, end_char, heading_path
- block-based (`block`): block_ids, page_indices, block_roles, bboxes, confidence

Block fields are resolved at query time by re-fetching the parsed document.
If the parse run has been deleted, block fields stay null — the caller can
detect resolution failure rather than render stale references.
"""
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChunkCitation(BaseModel):
    chunk_id: UUID = Field(..., alias="chunkId")
    document_id: UUID = Field(..., alias="documentId")
    document_title: str = Field(..., alias="documentTitle")
    index_id: UUID = Field(..., alias="indexId")
    index_version: int = Field(..., alias="indexVersion")
    parse_run_id: UUID | None = Field(None, alias="parseRunId")
    source_type: str = Field(..., alias="sourceType")

    # Text-based
    start_char: int | None = Field(None, alias="startChar")
    end_char: int | None = Field(None, alias="endChar")
    page_numbers: list[int] = Field(default_factory=list, alias="pageNumbers")
    heading_path: list[str] | None = Field(None, alias="headingPath")

    # Block-based
    block_ids: list[str] | None = Field(None, alias="blockIds")
    page_indices: list[int] | None = Field(None, alias="pageIndices")
    block_roles: list[str] | None = Field(None, alias="blockRoles")
    bboxes: list[dict | None] | None = None
    confidence: float | None = None

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 2: Add `citation` field to `RetrievalResult`**

Modify `backend/app/schemas/query.py`:

At the top, add:

```python
from app.schemas.citation import ChunkCitation
```

Inside `RetrievalResult`, add a field after `metadata`:

```python
    citation: ChunkCitation | None = None
```

- [ ] **Step 3: Verify import sanity**

Run: `cd backend && uv run python -c "from app.schemas.query import RetrievalResult; from app.schemas.citation import ChunkCitation; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/citation.py backend/app/schemas/query.py
git commit -m "feat(indexes): add ChunkCitation schema and attach to RetrievalResult"
```

---

## Task 9: Implement citation resolution in `QueryService`

`_to_result` becomes async because block citations need a DB fetch. The four call sites (`_semantic_search`, `_keyword_search`, `_hybrid_search` returns) must be updated to `await`. The repository fetch is one row per result with a block-source chunk; an in-memory `dict` cache prevents duplicate fetches when several results share the same parse run.

**Files:**
- Modify: `backend/app/services/query_service.py`
- Create: `backend/tests/services/test_query_citation.py`

- [ ] **Step 1: Write the failing citation test**

Create `backend/tests/services/test_query_citation.py`:

```python
"""Tests for ChunkCitation resolution inside QueryService._to_result."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.cdm.models import BBox, Block, BlockRole, CoordSpace, Quality
from app.services.query_service import QueryService


def _chunk(*, source_type: str, chunk_metadata: dict, parse_run_id=None,
           document_title="Doc"):
    chunk_id = uuid4()
    document_id = uuid4()
    index_id = uuid4()
    return SimpleNamespace(
        id=chunk_id,
        document_id=document_id,
        index_id=index_id,
        index_version=1,
        parse_run_id=parse_run_id,
        source_type=source_type,
        chunk_metadata=chunk_metadata,
        chunk_index=0,
        token_count=10,
        char_count=42,
        content="content",
        document=SimpleNamespace(
            title=document_title,
            source_metadata={"filename": "doc.pdf"},
        ),
    )


@pytest.mark.asyncio
async def test_citation_resolution_text_chunk_populates_text_fields():
    svc = QueryService(
        index_repo=AsyncMock(),
        chunk_repo=AsyncMock(),
        provider_key_repo=AsyncMock(),
    )
    chunk = _chunk(
        source_type="full_text",
        chunk_metadata={"start_char": 100, "end_char": 250, "page_numbers": [3]},
    )
    result = await svc._to_result(chunk, score=0.9, rank=1)

    assert result.citation is not None
    assert result.citation.source_type == "full_text"
    assert result.citation.start_char == 100
    assert result.citation.end_char == 250
    assert result.citation.page_numbers == [3]
    assert result.citation.block_ids is None


@pytest.mark.asyncio
async def test_citation_resolution_markdown_chunk_populates_heading_path():
    svc = QueryService(
        index_repo=AsyncMock(),
        chunk_repo=AsyncMock(),
        provider_key_repo=AsyncMock(),
    )
    chunk = _chunk(
        source_type="full_markdown",
        chunk_metadata={
            "start_char": 0,
            "end_char": 100,
            "heading_path": ["Financials", "Q3 Results"],
        },
    )
    result = await svc._to_result(chunk, score=0.8, rank=1)

    assert result.citation.heading_path == ["Financials", "Q3 Results"]


@pytest.mark.asyncio
async def test_citation_resolution_block_resolves_against_parsed_doc(monkeypatch):
    parse_run_id = uuid4()
    bbox = BBox(x0=0.1, y0=0.0, x1=0.9, y1=0.05, space=CoordSpace.NORMALIZED)
    blocks = [
        Block(
            id="b1", role=BlockRole.HEADING, native_type="h1", page_index=2,
            bbox=bbox, text="Heading", quality=Quality(confidence=0.95),
        ).model_dump(),
        Block(
            id="b2", role=BlockRole.PARAGRAPH, native_type="p", page_index=2,
            bbox=bbox.model_copy(update={"y0": 0.1, "y1": 0.2}),
            text="body", quality=Quality(confidence=0.6),
        ).model_dump(),
    ]
    parsed_doc_row = SimpleNamespace(content={"blocks": blocks})
    repo_get = AsyncMock(return_value=parsed_doc_row)
    monkeypatch.setattr(
        "app.services.query_service.ParsedDocumentRepository",
        lambda session: SimpleNamespace(get_by_run=repo_get),
    )

    svc = QueryService(
        index_repo=AsyncMock(),
        chunk_repo=SimpleNamespace(session=object()),
        provider_key_repo=AsyncMock(),
    )
    chunk = _chunk(
        source_type="block",
        parse_run_id=parse_run_id,
        chunk_metadata={"block_ids": ["b1", "b2"]},
    )
    result = await svc._to_result(chunk, score=0.7, rank=1)

    cit = result.citation
    assert cit.block_ids == ["b1", "b2"]
    assert cit.page_indices == [2]
    assert cit.block_roles == ["heading", "paragraph"]
    assert len(cit.bboxes) == 2
    assert cit.confidence == pytest.approx(0.6)
    repo_get.assert_awaited_once_with(parse_run_id)


@pytest.mark.asyncio
async def test_citation_resolution_block_missing_parse_run_degrades_gracefully(monkeypatch):
    repo_get = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.query_service.ParsedDocumentRepository",
        lambda session: SimpleNamespace(get_by_run=repo_get),
    )

    svc = QueryService(
        index_repo=AsyncMock(),
        chunk_repo=SimpleNamespace(session=object()),
        provider_key_repo=AsyncMock(),
    )
    chunk = _chunk(
        source_type="block",
        parse_run_id=uuid4(),
        chunk_metadata={"block_ids": ["x"]},
    )
    result = await svc._to_result(chunk, score=0.5, rank=1)

    cit = result.citation
    assert cit.block_ids is None
    assert cit.bboxes is None
    assert cit.confidence is None
    assert cit.source_type == "block"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/test_query_citation.py -v`
Expected: FAIL — `_to_result` is currently a sync `@staticmethod` and emits no `citation`.

- [ ] **Step 3: Make `_to_result` async and build citations**

In `backend/app/services/query_service.py`:

(a) Add imports near the top:

```python
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.schemas.citation import ChunkCitation
```

(b) Replace the `_to_result` static method with an instance async method:

```python
    async def _to_result(self, chunk: Chunk, score: float, rank: int) -> RetrievalResult:
        """Convert a Chunk ORM object to a RetrievalResult schema."""
        doc = chunk.document
        if doc:
            stored_filename = doc.source_metadata.get("filename")
            if stored_filename and stored_filename != "upload.pdf":
                doc_name = stored_filename
            else:
                doc_name = doc.title or "Unknown"
        else:
            doc_name = "Unknown"

        page_numbers = (chunk.chunk_metadata or {}).get("page_numbers")
        page = page_numbers[0] if page_numbers else None

        citation = await self._build_citation(chunk, doc_name)

        return RetrievalResult(
            chunk_id=str(chunk.id),
            rank=rank,
            score=round(score, 4),
            content=chunk.content,
            metadata=RetrievalResultMetadata(
                document_id=str(chunk.document_id),
                document_name=doc_name,
                page=page,
                page_numbers=page_numbers,
                chunk_index=chunk.chunk_index,
                token_count=chunk.token_count,
                char_count=chunk.char_count,
                chunk_metadata=chunk.chunk_metadata or {},
            ),
            citation=citation,
        )

    async def _build_citation(self, chunk: Chunk, document_title: str) -> ChunkCitation:
        meta = chunk.chunk_metadata or {}
        citation = ChunkCitation(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_title=document_title,
            index_id=chunk.index_id,
            index_version=getattr(chunk, "index_version", 1),
            parse_run_id=chunk.parse_run_id,
            source_type=chunk.source_type,
            start_char=meta.get("start_char"),
            end_char=meta.get("end_char"),
            page_numbers=meta.get("page_numbers") or [],
            heading_path=meta.get("heading_path"),
        )

        if (
            chunk.source_type == "block"
            and chunk.parse_run_id is not None
            and meta.get("block_ids")
        ):
            await self._resolve_block_citation(citation, chunk, meta["block_ids"])

        return citation

    async def _resolve_block_citation(
        self, citation: ChunkCitation, chunk: Chunk, block_ids: list[str]
    ) -> None:
        repo = ParsedDocumentRepository(self.chunk_repo.session)
        parsed_doc_row = await repo.get_by_run(chunk.parse_run_id)
        if parsed_doc_row is None:
            # Parse run deleted — keep block fields null so the UI can detect failure.
            return
        blocks_raw = (parsed_doc_row.content or {}).get("blocks") or []
        block_map = {b.get("id"): b for b in blocks_raw if b.get("id")}
        ordered = [block_map[bid] for bid in block_ids if bid in block_map]
        if not ordered:
            return

        citation.block_ids = block_ids
        citation.page_indices = sorted({b.get("page_index") for b in ordered if b.get("page_index") is not None})
        citation.block_roles = [b.get("role") for b in ordered if b.get("role") is not None]
        citation.bboxes = [
            (
                {
                    "x0": b["bbox"]["x0"],
                    "y0": b["bbox"]["y0"],
                    "x1": b["bbox"]["x1"],
                    "y1": b["bbox"]["y1"],
                }
                if b.get("bbox")
                else None
            )
            for b in ordered
        ]
        confidences = [
            b["quality"]["confidence"]
            for b in ordered
            if b.get("quality") and b["quality"].get("confidence") is not None
        ]
        citation.confidence = min(confidences) if confidences else None
```

(c) `_semantic_search`, `_keyword_search`, `_hybrid_search` each end with a list comprehension calling `self._to_result(...)`. Replace each with an explicit awaited loop:

In `_semantic_search` (replace the final `return [...]` block at line 183-186):

```python
        results: list[RetrievalResult] = []
        for rank, (chunk, score) in enumerate(scored_chunks, 1):
            results.append(await self._to_result(chunk, score, rank))
        return results
```

In `_keyword_search` (replace the final `return [...]` at line 247-250):

```python
        results: list[RetrievalResult] = []
        for rank, (chunk, score) in enumerate(filtered, 1):
            results.append(await self._to_result(chunk, score, rank))
        return results
```

In `_hybrid_search` (replace the final `return [...]` at line 330-333):

```python
        out: list[RetrievalResult] = []
        for rank, (chunk, score) in enumerate(results, 1):
            out.append(await self._to_result(chunk, score, rank))
        return out
```

(d) Bump `chunk.index_version` access requires the column to be present on the ORM (Slice 1 added it). No code change needed beyond the `getattr(..., "index_version", 1)` fallback already in `_build_citation`.

- [ ] **Step 4: Run citation tests**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/test_query_citation.py -v`
Expected: ALL 4 tests PASS.

- [ ] **Step 5: Run full query service test suite to catch regressions**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/ -v -k query`
Expected: existing query tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/query_service.py backend/tests/services/test_query_citation.py
git commit -m "feat(query): build ChunkCitation per result; resolve block citations from ParsedDocument"
```

---

## Task 10: Frontend types — block fields + citation

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add block fields to `IndexConfig`**

In `frontend/src/types/index.ts`, after `maxSectionChars: number` (line 35), insert:

```typescript
  // Block-specific chunking
  groupByHeading: boolean
  maxBlocksPerChunk: number
  blockRoleFilter: string[] | null
```

- [ ] **Step 2: Add `BlockRole` type and `ChunkCitation` interface**

After the `IndexConfig` interface, add:

```typescript
// CDM block role (mirrors backend BlockRole enum values)
export type BlockRole =
  | 'title'
  | 'heading'
  | 'paragraph'
  | 'list'
  | 'table'
  | 'figure'
  | 'caption'
  | 'header'
  | 'footer'
  | 'marginalia'
  | 'code'
  | 'formula'
  | 'link'
  | 'other'

export const BLOCK_ROLE_OPTIONS: BlockRole[] = [
  'title', 'heading', 'paragraph', 'list', 'table', 'figure',
  'caption', 'code', 'formula', 'link', 'other',
]

export interface BBoxLike {
  x0: number
  y0: number
  x1: number
  y1: number
}

export interface ChunkCitation {
  chunkId: string
  documentId: string
  documentTitle: string
  indexId: string
  indexVersion: number
  parseRunId: string | null
  sourceType: 'raw_text' | 'full_text' | 'full_markdown' | 'block'

  // Text-based
  startChar: number | null
  endChar: number | null
  pageNumbers: number[]
  headingPath: string[] | null

  // Block-based
  blockIds: string[] | null
  pageIndices: number[] | null
  blockRoles: BlockRole[] | null
  bboxes: (BBoxLike | null)[] | null
  confidence: number | null
}
```

- [ ] **Step 3: Add `citation` to `RetrievalResult`**

Update the existing `RetrievalResult` interface so `citation` becomes:

```typescript
export interface RetrievalResult {
  chunkId: string
  rank: number
  score: number
  content: string
  metadata: RetrievalResultMetadata
  citation?: ChunkCitation | null
}
```

- [ ] **Step 4: Verify type-check passes**

Run: `cd frontend && npm run lint`
Expected: no new lint errors. Run `npm run build` for stricter type-check; expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(indexes): add block-config fields, BlockRole, ChunkCitation TS types"
```

---

## Task 11: Frontend `BlockConfigPanel` component

**Files:**
- Create: `frontend/src/components/indexes/BlockConfigPanel.tsx`
- Create: `frontend/src/components/indexes/BlockConfigPanel.test.tsx`

The panel is a controlled form: it receives `config: Partial<IndexConfig>` and `onUpdate(key, value)` (matching the existing `updateConfig` signature in `CreateIndexPage`). It renders three controls: Group-by-heading switch, Max-blocks-per-chunk slider, Block-role-filter chip toggles.

- [ ] **Step 1: Write the failing component test**

Create `frontend/src/components/indexes/BlockConfigPanel.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { BlockConfigPanel } from './BlockConfigPanel'

describe('BlockConfigPanel', () => {
  const baseConfig = {
    groupByHeading: true,
    maxBlocksPerChunk: 10,
    blockRoleFilter: null,
  }

  it('renders group-by-heading toggle, max-blocks slider, and role-filter section', () => {
    render(<BlockConfigPanel config={baseConfig} onUpdate={vi.fn()} />)
    expect(screen.getByLabelText(/group by heading/i)).toBeChecked()
    expect(screen.getByText(/max blocks per chunk/i)).toBeInTheDocument()
    expect(screen.getByText(/block role filter/i)).toBeInTheDocument()
  })

  it('calls onUpdate when group-by-heading is toggled', async () => {
    const onUpdate = vi.fn()
    render(<BlockConfigPanel config={baseConfig} onUpdate={onUpdate} />)
    await userEvent.click(screen.getByLabelText(/group by heading/i))
    expect(onUpdate).toHaveBeenCalledWith('groupByHeading', false)
  })

  it('calls onUpdate with role list when a role chip is selected', async () => {
    const onUpdate = vi.fn()
    render(<BlockConfigPanel config={baseConfig} onUpdate={onUpdate} />)
    await userEvent.click(screen.getByRole('button', { name: /^table$/i }))
    expect(onUpdate).toHaveBeenCalledWith('blockRoleFilter', ['table'])
  })

  it('shows existing role filter as selected', () => {
    render(
      <BlockConfigPanel
        config={{ ...baseConfig, blockRoleFilter: ['table', 'paragraph'] }}
        onUpdate={vi.fn()}
      />
    )
    expect(screen.getByRole('button', { name: /^table$/i })).toHaveAttribute(
      'aria-pressed', 'true'
    )
    expect(screen.getByRole('button', { name: /^paragraph$/i })).toHaveAttribute(
      'aria-pressed', 'true'
    )
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/indexes/BlockConfigPanel.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/indexes/BlockConfigPanel.tsx`:

```tsx
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Toggle } from '@/components/ui/toggle'
import { BLOCK_ROLE_OPTIONS, BlockRole, IndexConfig } from '@/types/index'

interface BlockConfigPanelProps {
  config: Partial<IndexConfig>
  onUpdate: (key: keyof IndexConfig, value: IndexConfig[keyof IndexConfig]) => void
}

export function BlockConfigPanel({ config, onUpdate }: BlockConfigPanelProps) {
  const groupByHeading = config.groupByHeading ?? true
  const maxBlocks = config.maxBlocksPerChunk ?? 10
  const filter: BlockRole[] = (config.blockRoleFilter as BlockRole[] | null | undefined) ?? []

  const toggleRole = (role: BlockRole) => {
    const next = filter.includes(role)
      ? filter.filter((r) => r !== role)
      : [...filter, role]
    onUpdate('blockRoleFilter', next.length === 0 ? null : next)
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="group-by-heading">Group by heading</Label>
          <Switch
            id="group-by-heading"
            checked={groupByHeading}
            onCheckedChange={(v) => onUpdate('groupByHeading', v)}
          />
        </div>
        <p className="text-xs text-muted-foreground">
          Attach paragraphs and tables to their preceding heading.
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Max blocks per chunk</Label>
          <span className="text-sm text-muted-foreground">{maxBlocks}</span>
        </div>
        <Slider
          min={1} max={50} step={1}
          value={[maxBlocks]}
          onValueChange={([v]) => onUpdate('maxBlocksPerChunk', v)}
        />
        <p className="text-xs text-muted-foreground">
          Large sections are split and the heading is repeated for context.
        </p>
      </div>

      <div className="space-y-2">
        <Label>Block role filter</Label>
        <p className="text-xs text-muted-foreground">
          {filter.length === 0
            ? 'All block types (default).'
            : `Indexing only: ${filter.join(', ')}.`}
        </p>
        <div className="flex flex-wrap gap-2">
          {BLOCK_ROLE_OPTIONS.map((role) => {
            const active = filter.includes(role)
            return (
              <Toggle
                key={role}
                pressed={active}
                aria-pressed={active}
                onPressedChange={() => toggleRole(role)}
                size="sm"
              >
                {role}
              </Toggle>
            )
          })}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Verify Switch + Toggle exist in shadcn/ui or install**

Run: `ls frontend/src/components/ui/ | grep -E '^(switch|toggle)\.tsx$'`
Expected: both files exist. If either is missing, add via `cd frontend && npx shadcn@latest add switch toggle`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/indexes/BlockConfigPanel.test.tsx`
Expected: ALL 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/indexes/BlockConfigPanel.tsx frontend/src/components/indexes/BlockConfigPanel.test.tsx
git commit -m "feat(indexes): add BlockConfigPanel for block source-representation"
```

---

## Task 12: Wire `BlockConfigPanel` and `block` toggle into `CreateIndexPage`

**Files:**
- Modify: `frontend/src/pages/CreateIndexPage.tsx`

- [ ] **Step 1: Extend `DEFAULT_CONFIG`**

In `CreateIndexPage.tsx:47-57`, add the new defaults:

```typescript
const DEFAULT_CONFIG: Partial<IndexConfig> = {
  sourceRepresentation: 'full_text',
  chunkingStrategy: 'recursive_character',
  chunkSize: 512,
  chunkOverlap: 50,
  chunkUnit: 'characters',
  splitHeadingLevel: 2,
  maxSectionChars: 4000,
  groupByHeading: true,
  maxBlocksPerChunk: 10,
  blockRoleFilter: null,
  embeddingProvider: 'openai',
  embeddingModel: 'text-embedding-3-small',
}
```

- [ ] **Step 2: Add `block` to source-representation handler**

In `handleSourceRepresentationChange` (lines 120-127), extend the strategy auto-mapping:

```typescript
  const handleSourceRepresentationChange = (value: SourceRepresentation) => {
    updateConfig('sourceRepresentation', value)
    if (value === 'full_markdown') updateConfig('chunkingStrategy', 'markdown_heading')
    else if (value === 'full_text') updateConfig('chunkingStrategy', 'recursive_character')
    else if (value === 'block') updateConfig('chunkingStrategy', 'block')
    setSelectedParsedDocIds([])
    setPreviewDocId(null)
    setPreview(null)
  }
```

- [ ] **Step 3: Add Block toggle to Step 3**

In `CreateIndexPage.tsx:325-336`, after the `full_markdown` `ToggleGroupItem`, insert a third item:

```tsx
                    <ToggleGroupItem value="block" aria-label="Blocks">
                      Blocks
                    </ToggleGroupItem>
```

(The block representation is always available — every parse run produces blocks. No `disabled` guard needed.)

- [ ] **Step 4: Wire the panel into Step 5**

Import the new component near the other indexes-component imports:

```typescript
import { BlockConfigPanel } from '@/components/indexes/BlockConfigPanel'
```

In Step 5 (around line 379), change the conditional from a binary `full_markdown ? markdown : text` into a three-way switch:

```tsx
                  {config.sourceRepresentation === 'full_markdown' ? (
                    <>
                      {/* existing markdown panel — unchanged */}
                    </>
                  ) : config.sourceRepresentation === 'block' ? (
                    <BlockConfigPanel config={config} onUpdate={updateConfig} />
                  ) : (
                    <>
                      {/* existing text panel — unchanged */}
                    </>
                  )}
```

- [ ] **Step 5: Manual verification**

Run: `cd frontend && npm run dev`
Open the Create Index wizard. Choose any parse-config family with parsed documents. In Step 3, confirm three toggles appear (Full text, Full Markdown, Blocks). Select **Blocks**. Advance to Step 5; verify the block panel renders with the switch, slider (default 10), and role chips. Toggle a role chip and confirm the helper text updates.

- [ ] **Step 6: Run lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: both pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/CreateIndexPage.tsx
git commit -m "feat(indexes): expose block source-representation and config panel in wizard"
```

---

## Task 13: `CitationFooter` component

**Files:**
- Create: `frontend/src/components/indexes/CitationFooter.tsx`
- Create: `frontend/src/components/indexes/CitationFooter.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/indexes/CitationFooter.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

import { CitationFooter } from './CitationFooter'
import { ChunkCitation } from '@/types/index'

const baseCitation: ChunkCitation = {
  chunkId: 'c1',
  documentId: 'd1',
  documentTitle: 'Doc',
  indexId: 'i1',
  indexVersion: 3,
  parseRunId: 'p1',
  sourceType: 'block',
  startChar: null,
  endChar: null,
  pageNumbers: [],
  headingPath: null,
  blockIds: ['b1', 'b2'],
  pageIndices: [4],
  blockRoles: ['table'],
  bboxes: [{ x0: 0.1, y0: 0.2, x1: 0.9, y1: 0.4 }],
  confidence: 0.85,
}

describe('CitationFooter', () => {
  it('renders page + role for block citations', () => {
    render(<CitationFooter citation={baseCitation} />)
    expect(screen.getByText(/page 5/i)).toBeInTheDocument() // page_index 4 → page 5
    expect(screen.getByText(/table/i)).toBeInTheDocument()
  })

  it('renders heading breadcrumb for markdown citations', () => {
    render(
      <CitationFooter
        citation={{
          ...baseCitation,
          sourceType: 'full_markdown',
          blockIds: null,
          pageIndices: null,
          blockRoles: null,
          bboxes: null,
          confidence: null,
          headingPath: ['Financials', 'Q3 Results'],
        }}
      />
    )
    expect(screen.getByText('Financials')).toBeInTheDocument()
    expect(screen.getByText('Q3 Results')).toBeInTheDocument()
  })

  it('renders page number for text citations', () => {
    render(
      <CitationFooter
        citation={{
          ...baseCitation,
          sourceType: 'full_text',
          blockIds: null,
          pageIndices: null,
          blockRoles: null,
          bboxes: null,
          confidence: null,
          pageNumbers: [7],
        }}
      />
    )
    expect(screen.getByText(/page 7/i)).toBeInTheDocument()
  })

  it('shows low-confidence tag when confidence < 0.7', () => {
    render(
      <CitationFooter
        citation={{ ...baseCitation, confidence: 0.55 }}
      />
    )
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument()
  })

  it('does not show low-confidence tag at or above 0.7', () => {
    render(
      <CitationFooter
        citation={{ ...baseCitation, confidence: 0.7 }}
      />
    )
    expect(screen.queryByText(/low confidence/i)).not.toBeInTheDocument()
  })

  it('always renders Index version label', () => {
    render(<CitationFooter citation={baseCitation} />)
    expect(screen.getByText(/index v3/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/indexes/CitationFooter.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/indexes/CitationFooter.tsx`:

```tsx
import { ChunkCitation } from '@/types/index'

interface CitationFooterProps {
  citation: ChunkCitation
}

function pageLabel(citation: ChunkCitation): string | null {
  if (citation.sourceType === 'block' && citation.pageIndices && citation.pageIndices.length > 0) {
    // page_index is 0-indexed in CDM; display as 1-indexed page number.
    const pages = citation.pageIndices.map((p) => p + 1)
    return pages.length === 1 ? `Page ${pages[0]}` : `Pages ${pages.join(', ')}`
  }
  if (citation.pageNumbers.length > 0) {
    return citation.pageNumbers.length === 1
      ? `Page ${citation.pageNumbers[0]}`
      : `Pages ${citation.pageNumbers.join(', ')}`
  }
  if (citation.startChar != null && citation.endChar != null) {
    return `Chars ${citation.startChar}–${citation.endChar}`
  }
  return null
}

function roleLabel(citation: ChunkCitation): string | null {
  if (!citation.blockRoles || citation.blockRoles.length === 0) return null
  // Show first non-heading role for compact display; fall back to first.
  const primary = citation.blockRoles.find((r) => r !== 'heading' && r !== 'title')
    ?? citation.blockRoles[0]
  return primary.charAt(0).toUpperCase() + primary.slice(1)
}

export function CitationFooter({ citation }: CitationFooterProps) {
  const page = pageLabel(citation)
  const role = roleLabel(citation)
  const lowConfidence = citation.confidence != null && citation.confidence < 0.7

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500 mt-2">
      {citation.sourceType === 'full_markdown' && citation.headingPath && citation.headingPath.length > 0 && (
        <span className="flex items-center gap-1">
          {citation.headingPath.map((h, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && <span className="text-zinc-300">›</span>}
              <span>{h}</span>
            </span>
          ))}
        </span>
      )}
      {page && <span>{page}</span>}
      {role && <span>· {role}</span>}
      {lowConfidence && (
        <span className="rounded-sm bg-amber-50 text-amber-700 px-1.5 py-0.5">
          Low confidence
        </span>
      )}
      <span className="ml-auto text-zinc-400">Index v{citation.indexVersion}</span>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/indexes/CitationFooter.test.tsx`
Expected: ALL 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/indexes/CitationFooter.tsx frontend/src/components/indexes/CitationFooter.test.tsx
git commit -m "feat(playground): add CitationFooter for adaptive result citation display"
```

---

## Task 14: Render `CitationFooter` inside `ResultCard`

**Files:**
- Modify: `frontend/src/components/indexes/ResultCard.tsx`

- [ ] **Step 1: Import and render the footer**

In `frontend/src/components/indexes/ResultCard.tsx`, add the import:

```typescript
import { CitationFooter } from './CitationFooter'
```

After the existing "Source metadata" block (line 131, just before the conditional `{result.metadata.chunkMetadata && ...}` block), insert:

```tsx
        {/* Citation */}
        {result.citation && <CitationFooter citation={result.citation} />}
```

- [ ] **Step 2: Manual verification**

Run: `cd frontend && npm run dev`. Run a query against a block-source index and confirm:
- Each result card shows page + role and an `Index v{n}` label.
- A result with `confidence < 0.7` shows the amber "Low confidence" tag.
- Results from a markdown index show the heading breadcrumb.
- Results from a `full_text` index show the page number.

If you do not yet have a fully-processed block index to query, defer the manual verification until the E2E checklist (Task 15).

- [ ] **Step 3: Run lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: both pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/indexes/ResultCard.tsx
git commit -m "feat(playground): show citation footer on result cards"
```

---

## Task 15: End-to-End validation

These steps are not committed code — they verify the slice as a whole. Run them only after Tasks 1–14 are merged into the working branch.

**Setup:** `cd backend && uvicorn app.main:app --reload` and `cd frontend && npm run dev`. Have at least one structured PDF parsed via LlamaParse so `ParsedDocument.blocks` contains varied roles (heading, paragraph, table).

- [ ] **Step 1: Verify the parse run has blocks**

In the parsed-doc viewer, confirm the document shows at least one heading + paragraph + one table.

- [ ] **Step 2: Create a block-source index**

Open Create Index. Pick the parse-config family for the parsed doc above. Step 3 → choose **Blocks**. Step 4 → select the parsed doc. Step 5 → keep defaults (`group_by_heading=true`, `max_blocks_per_chunk=10`, no role filter). Step 6 → confirm preview shows chunks; create with auto-process.

- [ ] **Step 3: Inspect chunks**

After processing completes, open the index detail page → Chunks tab. Confirm at least one chunk has `block_ids`, `page_indices`, `block_roles` in metadata; for any TABLE block, confirm a chunk contains exactly that one block id (not split).

- [ ] **Step 4: Query and verify citations**

Open the playground for the index. Run a query that targets table content. In the result cards, confirm:
- Page label, role label, Index v1 label all visible.
- A chunk citation referencing a TABLE shows "Table" as role.

- [ ] **Step 5: Confirm graceful degradation when parse run deleted**

In the DB shell, delete the `parsed_documents` row for the parse run bound to the indexed document:

```sql
DELETE FROM parsed_documents WHERE parse_run_id = '<uuid>';
```

Re-run the same query. Result cards still render, citation footer shows the `Index v1` label and any `pageNumbers`/`headingPath` fallback content; block-specific role label disappears (because `blockRoles` is now null). No 500 errors in the backend logs.

- [ ] **Step 6: Role filter sanity**

Create a second index with the same parse-config family but `block_role_filter=["table"]`. Process. Confirm only chunks whose `block_roles` are exclusively `["table"]` exist.

- [ ] **Step 7: Restore deleted parse-doc (optional)**

If you ran Step 5, restore the dev DB or re-parse so subsequent work isn't blocked.

---

## Self-review notes

- **Spec coverage**: every spec section maps to a task — `BlockChunkingService` (Task 2–5), dispatcher branch (Task 6), end-to-end pipeline (Task 7), `ChunkCitation` schema (Task 8), citation resolution (Task 9), block config UI (Tasks 10–12), citation UI (Tasks 13–14), E2E checklist (Task 15).
- **Layout-block safety**: Task 5 adds an explicit test that HEADER/FOOTER/MARGINALIA blocks are dropped even when listed in `block_role_filter`, codifying the spec's "layout artifacts, not content" rule.
- **TABLE/FIGURE never-split**: Task 3 covers both branches (`group_by_heading=True` appends to current group; `False` emits standalone single-block chunks). The algorithm in Task 2 deliberately appends TABLE/FIGURE to a heading group even if it pushes past `max_blocks_per_chunk`, which is the spec's intent ("never split a TABLE or FIGURE across groups regardless of `max_blocks_per_chunk`").
- **Citation graceful degradation**: Task 9's fourth test asserts that `block_ids`, `bboxes`, `confidence` stay null when the parse run is deleted, matching the spec's degradation contract.
- **`page_index` vs `page_numbers`**: CDM `page_index` is 0-indexed; the citation footer renders `page_index + 1` for the user. Text-source `page_numbers` from the existing chunker are already 1-indexed and are passed through unchanged.
- **`classified_block` deferral**: dispatcher raises `NotImplementedError` for `classified_block` (Task 6), preserving the spec's "schema accepts now, processing later" stance.
- **No placeholders**: every step has either runnable code or an exact CLI command with expected output.
