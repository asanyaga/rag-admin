# Docling Parser Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a docling-based PDF parser that maps `DoclingDocument` output to the CDM `ParsedDocument`, with page-batch splitting and a global semaphore to cap concurrency at 1.

**Architecture:** An in-process `DoclingAdapter` maps docling's document model to CDM blocks, pages, and tables. A `run_docling` async runner splits large PDFs into batches (default 20 pages), processes each batch sequentially through a module-level `asyncio.Semaphore(1)` + `asyncio.to_thread`, then merges results into one `ParsedDocument`. The runner is registered in `ParsingService._RUNNERS` like the existing LlamaParse and LandingAI runners.

**Tech Stack:** `docling>=2.0.0`, `pypdf>=4.0.0`, `asyncio.Semaphore`, `asyncio.to_thread`, Pydantic v2, pytest-asyncio.

## Global Constraints

- Python 3.12+; all async functions use `async/await`
- All CDM types are frozen Pydantic v2 models — use `model_copy(update=...)` for mutations, never mutate in place
- Block IDs follow the scheme `{source_document_id}:p{page_index}:b{reading_order}` — same as LlamaParse and LandingAI adapters
- Page indexes are 0-indexed in CDM; docling is 1-indexed — always convert with `page_index = (page_no - 1) + page_offset`
- BBox canonical form: normalized fractions `(x0, y0, x1, y1)`, origin top-left, values in `[0.0, 1.0]`
- `DoclingRunError` must carry the failed `ParseRun` on `.run` (inherits from `ParseRunError`)
- MVP scope: PDF only — `supported_file_types()` returns `["application/pdf"]`
- Run tests with: `uv run --directory backend python -m pytest -o "addopts=" -v <test_path>`
- Add packages with: `uv add --directory backend <package>`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/pyproject.toml` | modify | Add `docling`, `pypdf` dependencies |
| `backend/app/cdm/models.py` | modify | Add `ParserKind.DOCLING = "docling"` |
| `backend/app/services/parsing/errors.py` | modify | Add `DoclingRunError` |
| `backend/app/cdm/adapters/docling.py` | create | `DoclingAdapter`, helpers (`_to_cdm_bbox`, `_map_role`, `_map_table`, `_mint_block_id`) |
| `backend/app/services/parsing/docling_runner.py` | create | `run_docling`, `_split_pdf`, `_merge_fragments`, `_convert`, `_DOCLING_SEMAPHORE` |
| `backend/app/services/parsing/parsing_service.py` | modify | Register `ParserKind.DOCLING: run_docling` in `_RUNNERS` |
| `backend/tests/cdm/adapters/test_docling_adapter.py` | create | Structural invariant tests for `DoclingAdapter` |
| `backend/tests/services/parsing/test_docling_runner.py` | create | Unit tests for `_split_pdf`, `_merge_fragments`, `run_docling` |

---

### Task 1: Bootstrap — dependencies, ParserKind, and DoclingRunError

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/cdm/models.py:14-19`
- Modify: `backend/app/services/parsing/errors.py`

**Interfaces:**
- Produces: `ParserKind.DOCLING` enum value consumable by all later tasks; `DoclingRunError` class

- [ ] **Step 1: Add dependencies**

```toml
# backend/pyproject.toml — inside the dependencies list, after "landingai-ade>=0.3.3,"
"docling>=2.0.0",
"pypdf>=4.0.0",
```

Run:
```
uv add --directory backend docling pypdf
```
Expected: packages installed, `pyproject.toml` updated with pinned versions.

- [ ] **Step 2: Add `ParserKind.DOCLING`**

In `backend/app/cdm/models.py`, edit the `ParserKind` enum (lines 14–19):

```python
class ParserKind(str, Enum):
    SIMPLE       = "simple"
    LITEPARSE    = "liteparse"
    UNSTRUCTURED = "unstructured"
    LLAMAPARSE   = "llamaparse"
    LANDING_AI   = "landing_ai"
    DOCLING      = "docling"
```

- [ ] **Step 3: Write the failing tests**

Create `backend/tests/cdm/adapters/test_docling_adapter.py`:

```python
"""Tests for DoclingAdapter — run before adapter exists to verify TDD baseline."""
import pytest
from app.cdm.models import ParserKind
from app.services.parsing.errors import DoclingRunError, ParseRunError


def test_parser_kind_docling_value():
    assert ParserKind("docling") == ParserKind.DOCLING
    assert ParserKind.DOCLING.value == "docling"


def test_docling_run_error_is_parse_run_error():
    assert issubclass(DoclingRunError, ParseRunError)


def test_docling_run_error_carries_run():
    from datetime import datetime, timezone
    from app.cdm.source import ParseRun, ParseRunStatus

    run = ParseRun(
        id="r1",
        source_document_id="s1",
        parser=ParserKind.DOCLING,
        representation_kind="extract_rich",
        status=ParseRunStatus.FAILED,
        started_at=datetime.now(timezone.utc),
    )
    err = DoclingRunError("failed", run=run)
    assert err.run is run
```

- [ ] **Step 4: Run tests to verify they fail**

```
uv run --directory backend python -m pytest -o "addopts=" -v tests/cdm/adapters/test_docling_adapter.py::test_parser_kind_docling_value tests/cdm/adapters/test_docling_adapter.py::test_docling_run_error_is_parse_run_error tests/cdm/adapters/test_docling_adapter.py::test_docling_run_error_carries_run
```
Expected: FAIL — `ParserKind` has no `DOCLING`, `DoclingRunError` not found.

- [ ] **Step 5: Add `DoclingRunError`**

In `backend/app/services/parsing/errors.py`, append after `SimpleRunError`:

```python
class DoclingRunError(ParseRunError):
    """Raised by docling_runner when conversion fails on any batch."""
```

- [ ] **Step 6: Run tests — expect pass**

```
uv run --directory backend python -m pytest -o "addopts=" -v tests/cdm/adapters/test_docling_adapter.py::test_parser_kind_docling_value tests/cdm/adapters/test_docling_adapter.py::test_docling_run_error_is_parse_run_error tests/cdm/adapters/test_docling_adapter.py::test_docling_run_error_carries_run
```
Expected: 3 PASSED.

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/app/cdm/models.py backend/app/services/parsing/errors.py backend/tests/cdm/adapters/test_docling_adapter.py
git commit -m "feat(docling): add ParserKind.DOCLING, DoclingRunError, and deps"
```

---

### Task 2: BBox conversion and role-mapping helpers

**Files:**
- Create: `backend/app/cdm/adapters/docling.py`
- Test: `backend/tests/cdm/adapters/test_docling_adapter.py` (extend)

**Interfaces:**
- Produces:
  - `_to_cdm_bbox(raw, page_width, page_height) -> BBox`
  - `_map_role(label: DocItemLabel) -> BlockRole`
  - `_mint_block_id(source_document_id, page_index, reading_order) -> str`

- [ ] **Step 1: Write failing tests for helpers**

Add to `backend/tests/cdm/adapters/test_docling_adapter.py`:

```python
from types import SimpleNamespace


def _fake_bbox(l, t, r, b, origin="BOTTOMLEFT"):
    """Build a fake docling BoundingBox-like object."""
    return SimpleNamespace(l=l, t=t, r=r, b=b, coord_origin=origin)


def test_to_cdm_bbox_bottomleft_identity():
    from app.cdm.adapters.docling import _to_cdm_bbox
    # A bbox that covers the full page in bottom-left coords:
    # l=0, t=842 (page top from bottom), r=595, b=0 (page bottom from bottom)
    # → normalized CDM: x0=0, y0=0, x1=1, y1=1
    bbox = _fake_bbox(l=0.0, t=842.0, r=595.0, b=0.0, origin="BOTTOMLEFT")
    result = _to_cdm_bbox(bbox, page_width=595.0, page_height=842.0)
    assert result.x0 == pytest.approx(0.0)
    assert result.y0 == pytest.approx(0.0)
    assert result.x1 == pytest.approx(1.0)
    assert result.y1 == pytest.approx(1.0)


def test_to_cdm_bbox_bottomleft_quarter():
    from app.cdm.adapters.docling import _to_cdm_bbox
    # Bottom-left quarter: l=0, t=421, r=297.5, b=0
    # CDM: x0=0, y0=0.5 (1 - 421/842), x1=0.5, y1=1.0 (1 - 0/842)
    bbox = _fake_bbox(l=0.0, t=421.0, r=297.5, b=0.0, origin="BOTTOMLEFT")
    result = _to_cdm_bbox(bbox, page_width=595.0, page_height=842.0)
    assert result.x0 == pytest.approx(0.0)
    assert result.y0 == pytest.approx(0.5, abs=0.01)
    assert result.x1 == pytest.approx(0.5)
    assert result.y1 == pytest.approx(1.0)


def test_to_cdm_bbox_topleft():
    from app.cdm.adapters.docling import _to_cdm_bbox
    # Top-left quarter: l=0, t=0, r=297.5, b=421
    # CDM: x0=0, y0=0, x1=0.5, y1=0.5
    bbox = _fake_bbox(l=0.0, t=0.0, r=297.5, b=421.0, origin="TOPLEFT")
    result = _to_cdm_bbox(bbox, page_width=595.0, page_height=842.0)
    assert result.x0 == pytest.approx(0.0)
    assert result.y0 == pytest.approx(0.0)
    assert result.x1 == pytest.approx(0.5)
    assert result.y1 == pytest.approx(0.5)


def test_to_cdm_bbox_clamped():
    from app.cdm.adapters.docling import _to_cdm_bbox
    bbox = _fake_bbox(l=-10.0, t=900.0, r=700.0, b=-5.0, origin="BOTTOMLEFT")
    result = _to_cdm_bbox(bbox, page_width=595.0, page_height=842.0)
    assert 0.0 <= result.x0 <= result.x1 <= 1.0
    assert 0.0 <= result.y0 <= result.y1 <= 1.0


def test_map_role_known_labels():
    from app.cdm.adapters.docling import _map_role
    from app.cdm.models import BlockRole

    cases = [
        ("title", BlockRole.TITLE),
        ("section_header", BlockRole.HEADING),
        ("text", BlockRole.PARAGRAPH),
        ("paragraph", BlockRole.PARAGRAPH),
        ("list_item", BlockRole.LIST),
        ("table", BlockRole.TABLE),
        ("picture", BlockRole.FIGURE),
        ("caption", BlockRole.CAPTION),
        ("code", BlockRole.CODE),
        ("formula", BlockRole.FORMULA),
        ("page_header", BlockRole.HEADER),
        ("page_footer", BlockRole.FOOTER),
        ("footnote", BlockRole.OTHER),
    ]
    for label_value, expected_role in cases:
        label = SimpleNamespace(value=label_value)
        assert _map_role(label) == expected_role, f"failed for {label_value}"


def test_map_role_unknown_falls_back_to_other():
    from app.cdm.adapters.docling import _map_role
    from app.cdm.models import BlockRole
    label = SimpleNamespace(value="some_future_label")
    assert _map_role(label) == BlockRole.OTHER


def test_mint_block_id_format():
    from app.cdm.adapters.docling import _mint_block_id
    result = _mint_block_id("doc-abc", page_index=2, reading_order=7)
    assert result == "doc-abc:p2:b7"
```

- [ ] **Step 2: Run tests — expect fail**

```
uv run --directory backend python -m pytest -o "addopts=" -v tests/cdm/adapters/test_docling_adapter.py -k "bbox or role or mint"
```
Expected: FAIL — `app.cdm.adapters.docling` not found.

- [ ] **Step 3: Create the adapter file with helpers**

Create `backend/app/cdm/adapters/docling.py`:

```python
"""Docling adapter — maps DoclingDocument to CDM ParsedDocument."""
from __future__ import annotations

import uuid
from typing import Any, ClassVar, Dict, List, Optional

from app.cdm.adapters.base import ParserAdapter, SourceMeta
from app.cdm.models import (
    BBox,
    Block,
    BlockRole,
    Cell,
    Page,
    ParsedDocument,
    ParserKind,
    Table,
)

_ROLE_MAP: Dict[str, BlockRole] = {
    "title":               BlockRole.TITLE,
    "section_header":      BlockRole.HEADING,
    "text":                BlockRole.PARAGRAPH,
    "paragraph":           BlockRole.PARAGRAPH,
    "list_item":           BlockRole.LIST,
    "table":               BlockRole.TABLE,
    "picture":             BlockRole.FIGURE,
    "figure":              BlockRole.FIGURE,
    "caption":             BlockRole.CAPTION,
    "code":                BlockRole.CODE,
    "formula":             BlockRole.FORMULA,
    "inline_math":         BlockRole.FORMULA,
    "page_header":         BlockRole.HEADER,
    "page_footer":         BlockRole.FOOTER,
    "footnote":            BlockRole.OTHER,
    "checkbox_selected":   BlockRole.OTHER,
    "checkbox_unselected": BlockRole.OTHER,
    "form":                BlockRole.OTHER,
    "key_value_region":    BlockRole.OTHER,
    "document_index":      BlockRole.OTHER,
    "grounding":           BlockRole.OTHER,
}


def _map_role(label: Any) -> BlockRole:
    return _ROLE_MAP.get(label.value, BlockRole.OTHER)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _to_cdm_bbox(raw: Any, page_width: float, page_height: float) -> BBox:
    """Convert a docling BoundingBox to a normalized CDM BBox."""
    l, t, r, b = raw.l, raw.t, raw.r, raw.b
    origin = getattr(raw, "coord_origin", "BOTTOMLEFT")
    is_bottom_left = str(origin) in ("BOTTOMLEFT", "CoordOrigin.BOTTOMLEFT")

    if is_bottom_left:
        x0 = _clamp(l / page_width)
        x1 = _clamp(r / page_width)
        y0 = _clamp(1.0 - t / page_height)
        y1 = _clamp(1.0 - b / page_height)
    else:  # TOPLEFT
        x0 = _clamp(l / page_width)
        y0 = _clamp(t / page_height)
        x1 = _clamp(r / page_width)
        y1 = _clamp(b / page_height)

    return BBox(
        x0=x0, y0=y0, x1=x1, y1=y1,
        source_space="pdf_points",
        source_coords=(l, t, r, b),
    )


def _mint_block_id(source_document_id: str, page_index: int, reading_order: int) -> str:
    return f"{source_document_id}:p{page_index}:b{reading_order}"


def _map_table(item: Any) -> Table:
    """Map a docling TableItem to a CDM Table."""
    seen: set[tuple[int, int]] = set()
    cells: List[Cell] = []

    for row in item.data.grid:
        for cell in row:
            key = (cell.start_row_offset, cell.start_col_offset)
            if key in seen:
                continue
            seen.add(key)
            cells.append(Cell(
                row=cell.start_row_offset,
                col=cell.start_col_offset,
                rowspan=cell.row_span,
                colspan=cell.col_span,
                text=cell.text,
                is_header=getattr(cell, "column_header", False),
            ))

    rows = max((c.row + c.rowspan for c in cells), default=0)
    cols = max((c.col + c.colspan for c in cells), default=0)

    html: Optional[str] = None
    try:
        html = item.export_to_html()
    except Exception:
        pass

    md: Optional[str] = None
    try:
        md = item.export_to_markdown()
    except Exception:
        pass

    return Table(rows=rows, cols=cols, cells=cells, html=html, markdown=md)


class DoclingAdapter:
    parser: ClassVar[ParserKind] = ParserKind.DOCLING

    def adapt(
        self,
        raw: Any,  # DoclingDocument
        source_meta: SourceMeta,
        *,
        page_offset: int = 0,
    ) -> ParsedDocument:
        raise NotImplementedError  # implemented in Task 3

    def supported_file_types(self) -> list[str]:
        return ["application/pdf"]
```

- [ ] **Step 4: Run tests — expect pass**

```
uv run --directory backend python -m pytest -o "addopts=" -v tests/cdm/adapters/test_docling_adapter.py -k "bbox or role or mint"
```
Expected: 7 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/docling.py backend/tests/cdm/adapters/test_docling_adapter.py
git commit -m "feat(docling): add bbox conversion, role mapping, and table helpers"
```

---

### Task 3: DoclingAdapter.adapt()

**Files:**
- Modify: `backend/app/cdm/adapters/docling.py` (implement `adapt()`)
- Test: `backend/tests/cdm/adapters/test_docling_adapter.py` (extend)

**Interfaces:**
- Consumes: `_to_cdm_bbox`, `_map_role`, `_mint_block_id`, `_map_table` from Task 2
- Produces: `DoclingAdapter().adapt(raw, source_meta, page_offset=0) -> ParsedDocument`

- [ ] **Step 1: Write failing structural invariant tests**

Add to `backend/tests/cdm/adapters/test_docling_adapter.py`:

```python
import pytest
from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.docling import DoclingAdapter
from app.cdm.models import BlockRole, ParsedDocument


_META = SourceMeta(
    source_document_id="test-src-id",
    parse_run_id="test-run-id",
    filename="sample.pdf",
    sha256="a" * 64,
)


def _fake_page(width=595.0, height=842.0):
    return SimpleNamespace(size=SimpleNamespace(width=width, height=height))


def _fake_text_item(text, label_value="text", page_no=1, l=50.0, t=750.0, r=545.0, b=730.0):
    bbox = _fake_bbox(l=l, t=t, r=r, b=b, origin="BOTTOMLEFT")
    prov = SimpleNamespace(page_no=page_no, bbox=bbox)
    label = SimpleNamespace(value=label_value)
    return SimpleNamespace(
        label=label,
        text=text,
        prov=[prov],
        export_to_markdown=lambda: f"**{text}**" if label_value == "title" else text,
    )


def _fake_table_item(page_no=1):
    cell = SimpleNamespace(
        start_row_offset=0, start_col_offset=0,
        end_row_offset=1, end_col_offset=1,
        row_span=1, col_span=1,
        text="Header", column_header=True,
    )
    bbox = _fake_bbox(l=50.0, t=600.0, r=545.0, b=500.0, origin="BOTTOMLEFT")
    prov = SimpleNamespace(page_no=page_no, bbox=bbox)
    label = SimpleNamespace(value="table")
    item = SimpleNamespace(
        label=label,
        text="",
        prov=[prov],
        data=SimpleNamespace(grid=[[cell]]),
        export_to_markdown=lambda: "| Header |\n|---|",
        export_to_html=lambda: "<table><tr><th>Header</th></tr></table>",
    )
    return item


def _make_fake_doc(items, page_no=1, width=595.0, height=842.0):
    pages = {page_no: _fake_page(width, height)}
    items_with_level = [(item, 0) for item in items]
    full_md = "\n\n".join(getattr(i, "text", "") for i in items if getattr(i, "text", ""))
    return SimpleNamespace(
        pages=pages,
        iterate_items=lambda: iter(items_with_level),
        export_to_markdown=lambda: full_md,
    )


@pytest.fixture
def simple_doc():
    items = [
        _fake_text_item("Annual Report", label_value="title"),
        _fake_text_item("Introduction", label_value="section_header"),
        _fake_text_item("This is body text.", label_value="text"),
        _fake_table_item(),
    ]
    return _make_fake_doc(items)


@pytest.fixture
def adapted(simple_doc):
    return DoclingAdapter().adapt(simple_doc, _META)


def test_page_count_matches_pages(adapted):
    assert adapted.page_count == len(adapted.pages)


def test_block_page_indexes_valid(adapted):
    for block in adapted.blocks:
        assert 0 <= block.page_index < adapted.page_count, (
            f"Block {block.id} has out-of-range page_index={block.page_index}"
        )


def test_all_bboxes_normalized(adapted):
    for block in adapted.blocks:
        if block.bbox:
            assert 0.0 <= block.bbox.x0 <= block.bbox.x1 <= 1.0
            assert 0.0 <= block.bbox.y0 <= block.bbox.y1 <= 1.0


def test_table_block_has_table(adapted):
    table_blocks = [b for b in adapted.blocks if b.role == BlockRole.TABLE]
    assert len(table_blocks) == 1
    assert table_blocks[0].table is not None
    assert table_blocks[0].table.cells[0].text == "Header"
    assert table_blocks[0].table.cells[0].is_header is True


def test_page_block_ids_reference_existing_blocks(adapted):
    all_ids = {b.id for b in adapted.blocks}
    for page in adapted.pages:
        for bid in page.block_ids:
            assert bid in all_ids


def test_block_ids_use_minted_scheme(adapted):
    for block in adapted.blocks:
        assert block.id.startswith(_META.source_document_id)


def test_full_markdown_non_empty(adapted):
    assert adapted.full_markdown and len(adapted.full_markdown) > 0


def test_source_ids_wired(adapted):
    assert adapted.source_document_id == _META.source_document_id
    assert adapted.parse_run_id == _META.parse_run_id


def test_round_trip_serialization(adapted):
    serialised = adapted.model_dump_json()
    restored = ParsedDocument.model_validate_json(serialised)
    assert restored == adapted


def test_page_offset_shifts_page_indexes(simple_doc):
    doc = DoclingAdapter().adapt(simple_doc, _META, page_offset=5)
    for block in doc.blocks:
        assert block.page_index >= 5
    for page in doc.pages:
        assert page.index >= 5


def test_items_without_prov_are_skipped():
    no_prov_item = SimpleNamespace(
        label=SimpleNamespace(value="text"),
        text="orphan",
        prov=[],
        export_to_markdown=lambda: "orphan",
    )
    doc_with_orphan = _make_fake_doc([no_prov_item])
    result = DoclingAdapter().adapt(doc_with_orphan, _META)
    assert len(result.blocks) == 0
```

- [ ] **Step 2: Run tests — expect fail**

```
uv run --directory backend python -m pytest -o "addopts=" -v tests/cdm/adapters/test_docling_adapter.py -k "page_count or block_page or bboxes or table_block or block_ids or full_markdown or source_ids or round_trip or page_offset or prov"
```
Expected: FAIL — `adapt()` raises `NotImplementedError`.

- [ ] **Step 3: Implement `DoclingAdapter.adapt()`**

Replace the `adapt()` method stub in `backend/app/cdm/adapters/docling.py`:

```python
    def adapt(
        self,
        raw: Any,  # DoclingDocument
        source_meta: SourceMeta,
        *,
        page_offset: int = 0,
    ) -> ParsedDocument:
        # Build page dimension index (docling pages are 1-indexed)
        page_sizes: Dict[int, tuple[float, float]] = {}
        for page_no, page_item in raw.pages.items():
            size = getattr(page_item, "size", None)
            w = size.width if size else 595.0
            h = size.height if size else 842.0
            page_sizes[int(page_no)] = (w, h)

        all_blocks: List[Block] = []
        page_block_ids: Dict[int, List[str]] = {}

        for reading_order, (item, depth) in enumerate(raw.iterate_items()):
            prov_list = getattr(item, "prov", None) or []
            if not prov_list:
                continue

            prov = prov_list[0]
            page_no = int(prov.page_no)
            page_index = (page_no - 1) + page_offset
            page_width, page_height = page_sizes.get(page_no, (595.0, 842.0))

            bbox: Optional[BBox] = None
            raw_bbox = getattr(prov, "bbox", None)
            if raw_bbox is not None:
                try:
                    bbox = _to_cdm_bbox(raw_bbox, page_width, page_height)
                except Exception:
                    pass

            label = item.label
            native_type = label.value
            role = _map_role(label)
            block_id = _mint_block_id(source_meta.source_document_id, page_index, reading_order)

            table: Optional[Table] = None
            if role == BlockRole.TABLE:
                try:
                    table = _map_table(item)
                except Exception:
                    pass

            md: Optional[str] = None
            try:
                md = item.export_to_markdown() or None
            except Exception:
                pass

            text = getattr(item, "text", "") or ""
            if not text and md:
                text = md

            heading_depth: Optional[int] = depth if role == BlockRole.HEADING else None

            block = Block(
                id=block_id,
                role=role,
                native_type=native_type,
                text=text,
                markdown=md,
                page_index=page_index,
                bbox=bbox,
                reading_order=reading_order,
                depth=heading_depth,
                table=table,
            )
            all_blocks.append(block)
            page_block_ids.setdefault(page_index, []).append(block_id)

        pages: List[Page] = []
        for page_no, (w, h) in sorted(page_sizes.items()):
            page_index = (page_no - 1) + page_offset
            pages.append(Page(
                index=page_index,
                width=w,
                height=h,
                unit="points",
                block_ids=page_block_ids.get(page_index, []),
            ))

        full_markdown: Optional[str] = None
        try:
            full_markdown = raw.export_to_markdown() or None
        except Exception:
            pass

        full_text = "\n\n".join(b.text for b in all_blocks if b.text) or None

        return ParsedDocument(
            id=str(uuid.uuid4()),
            source_document_id=source_meta.source_document_id,
            parse_run_id=source_meta.parse_run_id,
            source_filename=source_meta.filename,
            page_count=len(pages),
            pages=pages,
            blocks=all_blocks,
            full_text=full_text,
            full_markdown=full_markdown,
        )
```

- [ ] **Step 4: Run tests — expect pass**

```
uv run --directory backend python -m pytest -o "addopts=" -v tests/cdm/adapters/test_docling_adapter.py
```
Expected: all tests PASSED (including Task 1 bootstrap tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/docling.py backend/tests/cdm/adapters/test_docling_adapter.py
git commit -m "feat(docling): implement DoclingAdapter.adapt() with structural tests"
```

---

### Task 4: PDF splitting and fragment merge utilities

**Files:**
- Create: `backend/app/services/parsing/docling_runner.py` (split/merge only)
- Create: `backend/tests/services/parsing/test_docling_runner.py`

**Interfaces:**
- Produces:
  - `_split_pdf(file_path: str, batch_size: int) -> tuple[list[Path], bool]` — returns `(paths, created_temp_files)`
  - `_merge_fragments(fragments: list[ParsedDocument]) -> ParsedDocument`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/parsing/test_docling_runner.py`:

```python
"""Tests for docling_runner utilities: _split_pdf, _merge_fragments, run_docling."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.docling import DoclingAdapter
from app.cdm.models import ParserKind
from app.cdm.source import ParseRunStatus, SourceDocument


def _make_minimal_pdf(path: Path, num_pages: int) -> None:
    """Write a minimal valid multi-page PDF to path using pypdf."""
    from pypdf import PdfWriter
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=595, height=842)
    with open(path, "wb") as f:
        writer.write(f)


def _source() -> SourceDocument:
    return SourceDocument(
        id=str(uuid.uuid4()),
        sha256="c" * 64,
        filename="test.pdf",
        storage_uri="local://test.pdf",
        created_at=datetime.now(timezone.utc),
    )


# ── _split_pdf tests ──────────────────────────────────────────────────────────

def test_split_pdf_no_split_when_under_batch_size(tmp_path):
    from app.services.parsing.docling_runner import _split_pdf
    pdf = tmp_path / "small.pdf"
    _make_minimal_pdf(pdf, num_pages=5)
    paths, is_temp = _split_pdf(str(pdf), batch_size=20)
    assert len(paths) == 1
    assert str(paths[0]) == str(pdf)
    assert is_temp is False


def test_split_pdf_exact_batch_size_no_split(tmp_path):
    from app.services.parsing.docling_runner import _split_pdf
    pdf = tmp_path / "exact.pdf"
    _make_minimal_pdf(pdf, num_pages=20)
    paths, is_temp = _split_pdf(str(pdf), batch_size=20)
    assert len(paths) == 1
    assert is_temp is False


def test_split_pdf_creates_correct_batch_count(tmp_path):
    from app.services.parsing.docling_runner import _split_pdf
    pdf = tmp_path / "large.pdf"
    _make_minimal_pdf(pdf, num_pages=45)
    paths, is_temp = _split_pdf(str(pdf), batch_size=20)
    assert len(paths) == 3  # 20 + 20 + 5
    assert is_temp is True
    assert all(p.exists() for p in paths)


def test_split_pdf_batch_page_counts(tmp_path):
    from pypdf import PdfReader
    from app.services.parsing.docling_runner import _split_pdf
    pdf = tmp_path / "counted.pdf"
    _make_minimal_pdf(pdf, num_pages=45)
    paths, _ = _split_pdf(str(pdf), batch_size=20)
    page_counts = [len(PdfReader(str(p)).pages) for p in paths]
    assert page_counts == [20, 20, 5]
    for p in paths:
        p.unlink(missing_ok=True)


def test_split_pdf_temp_files_are_real_pdfs(tmp_path):
    from pypdf import PdfReader
    from app.services.parsing.docling_runner import _split_pdf
    pdf = tmp_path / "multi.pdf"
    _make_minimal_pdf(pdf, num_pages=25)
    paths, is_temp = _split_pdf(str(pdf), batch_size=20)
    assert is_temp is True
    for p in paths:
        reader = PdfReader(str(p))
        assert len(reader.pages) > 0
        p.unlink(missing_ok=True)


# ── _merge_fragments tests ────────────────────────────────────────────────────

def _make_fragment(page_offset: int, page_count: int) -> "ParsedDocument":
    """Build a minimal ParsedDocument fragment via the adapter."""
    from types import SimpleNamespace

    def _fake_page_item(w=595.0, h=842.0):
        return SimpleNamespace(size=SimpleNamespace(width=w, height=h))

    def _fake_text(text, page_no):
        bbox = SimpleNamespace(l=0.0, t=800.0, r=595.0, b=750.0, coord_origin="BOTTOMLEFT")
        prov = SimpleNamespace(page_no=page_no, bbox=bbox)
        return SimpleNamespace(
            label=SimpleNamespace(value="text"),
            text=text,
            prov=[prov],
            export_to_markdown=lambda: text,
        )

    pages = {(page_offset + i + 1): _fake_page_item() for i in range(page_count)}
    items = [_fake_text(f"Page {page_offset + i}", page_offset + i + 1) for i in range(page_count)]
    items_with_level = [(item, 0) for item in items]
    full_md = "\n\n".join(f"Page {page_offset + i}" for i in range(page_count))

    raw = SimpleNamespace(
        pages=pages,
        iterate_items=lambda: iter(items_with_level),
        export_to_markdown=lambda: full_md,
    )
    meta = SourceMeta(
        source_document_id="merge-test-src",
        parse_run_id="merge-test-run",
        filename="test.pdf",
        sha256="0" * 64,
    )
    return DoclingAdapter().adapt(raw, meta, page_offset=page_offset)


def test_merge_single_fragment_returns_it():
    from app.services.parsing.docling_runner import _merge_fragments
    frag = _make_fragment(page_offset=0, page_count=3)
    merged = _merge_fragments([frag])
    assert merged is frag


def test_merge_two_fragments_total_page_count():
    from app.services.parsing.docling_runner import _merge_fragments
    f1 = _make_fragment(page_offset=0, page_count=20)
    f2 = _make_fragment(page_offset=20, page_count=5)
    merged = _merge_fragments([f1, f2])
    assert merged.page_count == 25


def test_merge_page_indexes_are_continuous():
    from app.services.parsing.docling_runner import _merge_fragments
    f1 = _make_fragment(page_offset=0, page_count=3)
    f2 = _make_fragment(page_offset=3, page_count=3)
    merged = _merge_fragments([f1, f2])
    page_indexes = [p.index for p in merged.pages]
    assert page_indexes == list(range(6))


def test_merge_block_count_is_sum():
    from app.services.parsing.docling_runner import _merge_fragments
    f1 = _make_fragment(page_offset=0, page_count=2)
    f2 = _make_fragment(page_offset=2, page_count=2)
    merged = _merge_fragments([f1, f2])
    assert len(merged.blocks) == len(f1.blocks) + len(f2.blocks)


def test_merge_full_text_concatenated():
    from app.services.parsing.docling_runner import _merge_fragments
    f1 = _make_fragment(page_offset=0, page_count=1)
    f2 = _make_fragment(page_offset=1, page_count=1)
    merged = _merge_fragments([f1, f2])
    assert f1.full_text in merged.full_text
    assert f2.full_text in merged.full_text
```

- [ ] **Step 2: Run tests — expect fail**

```
uv run --directory backend python -m pytest -o "addopts=" -v tests/services/parsing/test_docling_runner.py -k "split or merge"
```
Expected: FAIL — `docling_runner` module not found.

- [ ] **Step 3: Implement `_split_pdf` and `_merge_fragments`**

Create `backend/app/services/parsing/docling_runner.py`:

```python
"""Docling runner — local PDF parsing with semaphore-bounded concurrency."""
from __future__ import annotations

import asyncio
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.docling import DoclingAdapter
from app.cdm.models import ParsedDocument, ParserKind
from app.cdm.source import ParseRun, ParseRunStatus, SourceDocument
from app.services.parsing.errors import DoclingRunError

_DOCLING_SEMAPHORE = asyncio.Semaphore(1)


def _split_pdf(file_path: str, batch_size: int) -> Tuple[List[Path], bool]:
    """Split a PDF into page-range batches.

    Returns (paths, created_temp_files). If the PDF fits in one batch,
    returns ([Path(file_path)], False) — no temp files created.
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(file_path)
    total_pages = len(reader.pages)

    if total_pages <= batch_size:
        return [Path(file_path)], False

    batch_paths: List[Path] = []
    for start in range(0, total_pages, batch_size):
        end = min(start + batch_size, total_pages)
        writer = PdfWriter()
        for page_num in range(start, end):
            writer.add_page(reader.pages[page_num])

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        with open(tmp.name, "wb") as f:
            writer.write(f)
        batch_paths.append(Path(tmp.name))

    return batch_paths, True


def _merge_fragments(fragments: List[ParsedDocument]) -> ParsedDocument:
    """Merge CDM fragments from page batches into one ParsedDocument."""
    if len(fragments) == 1:
        return fragments[0]

    pages = [p for f in fragments for p in f.pages]
    blocks = [b for f in fragments for b in f.blocks]
    text_parts = [f.full_text for f in fragments if f.full_text]
    md_parts = [f.full_markdown for f in fragments if f.full_markdown]

    first = fragments[0]
    return ParsedDocument(
        id=first.id,
        source_document_id=first.source_document_id,
        parse_run_id=first.parse_run_id,
        source_filename=first.source_filename,
        page_count=len(pages),
        pages=pages,
        blocks=blocks,
        full_text="\n\n".join(text_parts) or None,
        full_markdown="\n\n".join(md_parts) or None,
    )


def _convert(file_path: Path, config: Dict[str, Any]) -> Any:
    """Synchronous docling conversion — runs in a thread via asyncio.to_thread."""
    from docling.document_converter import DocumentConverter
    converter = DocumentConverter()
    return converter.convert(str(file_path))


async def run_docling(
    *,
    source: SourceDocument,
    file_path: str,
    representation_kind: str,
    config: Dict[str, Any],
    client: Any,  # unused — docling is in-process
    parse_run_id: Optional[str] = None,
) -> Tuple[ParseRun, ParsedDocument]:
    raise NotImplementedError  # implemented in Task 5
```

- [ ] **Step 4: Run tests — expect pass**

```
uv run --directory backend python -m pytest -o "addopts=" -v tests/services/parsing/test_docling_runner.py -k "split or merge"
```
Expected: all split and merge tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parsing/docling_runner.py backend/tests/services/parsing/test_docling_runner.py
git commit -m "feat(docling): add _split_pdf and _merge_fragments utilities"
```

---

### Task 5: run_docling runner

**Files:**
- Modify: `backend/app/services/parsing/docling_runner.py` (implement `run_docling`)
- Test: `backend/tests/services/parsing/test_docling_runner.py` (extend)

**Interfaces:**
- Consumes: `_split_pdf`, `_merge_fragments`, `_convert`, `_DOCLING_SEMAPHORE`, `DoclingAdapter` (all from Task 4/2)
- Produces: `async run_docling(*, source, file_path, representation_kind, config, client, parse_run_id=None) -> Tuple[ParseRun, ParsedDocument]`

- [ ] **Step 1: Write failing runner tests**

Add to `backend/tests/services/parsing/test_docling_runner.py`:

```python
import asyncio
from unittest.mock import MagicMock, patch
from types import SimpleNamespace


def _fake_conversion_result(page_count: int = 1):
    """Build a minimal fake docling ConversionResult."""
    def _fake_page_item(w=595.0, h=842.0):
        return SimpleNamespace(size=SimpleNamespace(width=w, height=h))

    def _fake_text(text, page_no):
        bbox = SimpleNamespace(l=0.0, t=800.0, r=595.0, b=750.0, coord_origin="BOTTOMLEFT")
        prov = SimpleNamespace(page_no=page_no, bbox=bbox)
        return SimpleNamespace(
            label=SimpleNamespace(value="text"),
            text=text,
            prov=[prov],
            export_to_markdown=lambda: text,
        )

    pages = {i + 1: _fake_page_item() for i in range(page_count)}
    items = [_fake_text(f"Content page {i + 1}", i + 1) for i in range(page_count)]
    items_with_level = [(item, 0) for item in items]
    full_md = "\n\n".join(f"Content page {i + 1}" for i in range(page_count))

    doc = SimpleNamespace(
        pages=pages,
        iterate_items=lambda: iter(items_with_level),
        export_to_markdown=lambda: full_md,
    )
    return SimpleNamespace(document=doc)


@pytest.mark.asyncio
async def test_run_docling_success(tmp_path):
    from app.services.parsing.docling_runner import run_docling

    pdf = tmp_path / "test.pdf"
    _make_minimal_pdf(pdf, num_pages=3)
    src = _source()

    with patch(
        "app.services.parsing.docling_runner._convert",
        return_value=_fake_conversion_result(page_count=3),
    ):
        run, doc = await run_docling(
            source=src,
            file_path=str(pdf),
            representation_kind="extract_rich",
            config={"parser": "docling"},
            client=None,
        )

    assert run.status == ParseRunStatus.SUCCEEDED
    assert run.parser == ParserKind.DOCLING
    assert run.duration_ms is not None and run.duration_ms >= 0
    assert doc is not None
    assert doc.source_document_id == src.id
    assert doc.page_count == 3


@pytest.mark.asyncio
async def test_run_docling_failure_raises_docling_run_error(tmp_path):
    from app.services.parsing.errors import DoclingRunError
    from app.services.parsing.docling_runner import run_docling

    pdf = tmp_path / "test.pdf"
    _make_minimal_pdf(pdf, num_pages=1)
    src = _source()

    with patch(
        "app.services.parsing.docling_runner._convert",
        side_effect=RuntimeError("docling crashed"),
    ):
        with pytest.raises(DoclingRunError) as exc_info:
            await run_docling(
                source=src,
                file_path=str(pdf),
                representation_kind="extract_rich",
                config={"parser": "docling"},
                client=None,
            )

    err = exc_info.value
    assert err.run.status == ParseRunStatus.FAILED
    assert err.run.parser == ParserKind.DOCLING
    assert "docling crashed" in err.run.error


@pytest.mark.asyncio
async def test_run_docling_temp_files_cleaned_up_on_error(tmp_path):
    from app.services.parsing.errors import DoclingRunError
    from app.services.parsing.docling_runner import run_docling

    pdf = tmp_path / "large.pdf"
    _make_minimal_pdf(pdf, num_pages=25)
    src = _source()

    created_temp_paths: list[Path] = []

    original_split = __import__(
        "app.services.parsing.docling_runner", fromlist=["_split_pdf"]
    )._split_pdf

    def capturing_split(file_path, batch_size):
        paths, is_temp = original_split(file_path, batch_size)
        if is_temp:
            created_temp_paths.extend(paths)
        return paths, is_temp

    with patch("app.services.parsing.docling_runner._split_pdf", side_effect=capturing_split):
        with patch(
            "app.services.parsing.docling_runner._convert",
            side_effect=RuntimeError("crash"),
        ):
            with pytest.raises(DoclingRunError):
                await run_docling(
                    source=src,
                    file_path=str(pdf),
                    representation_kind="extract_rich",
                    config={"parser": "docling", "page_batch_size": 20},
                    client=None,
                )

    # All temp files must be gone after the error
    for p in created_temp_paths:
        assert not p.exists(), f"Temp file not cleaned up: {p}"


def test_docling_semaphore_initialized_with_one_slot():
    """_DOCLING_SEMAPHORE must be initialized with value 1 (not locked at import)."""
    from app.services.parsing.docling_runner import _DOCLING_SEMAPHORE
    assert not _DOCLING_SEMAPHORE.locked()
```

- [ ] **Step 2: Run tests — expect fail**

```
uv run --directory backend python -m pytest -o "addopts=" -v tests/services/parsing/test_docling_runner.py -k "run_docling"
```
Expected: FAIL — `run_docling` raises `NotImplementedError`.

- [ ] **Step 3: Implement `run_docling`**

Replace the `run_docling` stub in `backend/app/services/parsing/docling_runner.py`:

```python
async def run_docling(
    *,
    source: SourceDocument,
    file_path: str,
    representation_kind: str,
    config: Dict[str, Any],
    client: Any,  # unused — docling is in-process
    parse_run_id: Optional[str] = None,
) -> Tuple[ParseRun, ParsedDocument]:
    run_id = parse_run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    batch_size = config.get("page_batch_size", 20)

    try:
        batch_paths, is_temp = _split_pdf(file_path, batch_size)
    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        failed = ParseRun(
            id=run_id,
            source_document_id=source.id,
            parser=ParserKind.DOCLING,
            representation_kind=representation_kind,
            config=config,
            status=ParseRunStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error=f"PDF split failed: {exc}",
        )
        raise DoclingRunError(f"PDF split failed: {exc}", run=failed) from exc

    adapter = DoclingAdapter()
    fragments: List[ParsedDocument] = []

    try:
        for i, batch_path in enumerate(batch_paths):
            page_offset = i * batch_size
            source_meta = SourceMeta(
                source_document_id=source.id,
                parse_run_id=run_id,
                filename=source.filename,
                sha256=source.sha256,
            )
            async with _DOCLING_SEMAPHORE:
                result = await asyncio.to_thread(_convert, batch_path, config)
            fragment = adapter.adapt(result.document, source_meta, page_offset=page_offset)
            fragments.append(fragment)
    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        failed = ParseRun(
            id=run_id,
            source_document_id=source.id,
            parser=ParserKind.DOCLING,
            representation_kind=representation_kind,
            config=config,
            status=ParseRunStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise DoclingRunError(str(exc), run=failed) from exc
    finally:
        if is_temp:
            for tmp_path in batch_paths:
                tmp_path.unlink(missing_ok=True)

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((time.perf_counter() - t0) * 1000)
    merged = _merge_fragments(fragments)

    run = ParseRun(
        id=run_id,
        source_document_id=source.id,
        parser=ParserKind.DOCLING,
        representation_kind=representation_kind,
        config=config,
        status=ParseRunStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
    )
    return run, merged
```

- [ ] **Step 4: Run all runner tests — expect pass**

```
uv run --directory backend python -m pytest -o "addopts=" -v tests/services/parsing/test_docling_runner.py
```
Expected: all tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parsing/docling_runner.py backend/tests/services/parsing/test_docling_runner.py
git commit -m "feat(docling): implement run_docling runner with semaphore and batch splitting"
```

---

### Task 6: Register docling in ParsingService

**Files:**
- Modify: `backend/app/services/parsing/parsing_service.py:24-35`

**Interfaces:**
- Consumes: `ParserKind.DOCLING` (Task 1), `run_docling` (Task 5)

- [ ] **Step 1: Write a failing registration test**

Add to `backend/tests/services/parsing/test_docling_runner.py`:

```python
def test_docling_registered_in_runners():
    """ParsingService._RUNNERS must include DOCLING so parse_and_persist can dispatch it."""
    from app.services.parsing import parsing_service
    from app.cdm.models import ParserKind
    assert ParserKind.DOCLING in parsing_service._RUNNERS
```

- [ ] **Step 2: Run test — expect fail**

```
uv run --directory backend python -m pytest -o "addopts=" -v tests/services/parsing/test_docling_runner.py::test_docling_registered_in_runners
```
Expected: FAIL — `ParserKind.DOCLING` not in `_RUNNERS`.

- [ ] **Step 3: Register the runner**

In `backend/app/services/parsing/parsing_service.py`, add the import and registration:

```python
# Add after the existing runner imports (around line 24-26):
from app.services.parsing.docling_runner import run_docling

# Add to _RUNNERS dict (around line 31-35):
_RUNNERS: Dict[ParserKind, Callable] = {
    ParserKind.LLAMAPARSE: run_llamaparse,
    ParserKind.LANDING_AI: run_landingai,
    ParserKind.SIMPLE:     run_simple,
    ParserKind.DOCLING:    run_docling,
}
```

- [ ] **Step 4: Run test — expect pass**

```
uv run --directory backend python -m pytest -o "addopts=" -v tests/services/parsing/test_docling_runner.py::test_docling_registered_in_runners
```
Expected: PASSED.

- [ ] **Step 5: Run full test suite to check for regressions**

```
uv run --directory backend python -m pytest -o "addopts=" -v tests/cdm/adapters/ tests/services/parsing/
```
Expected: all tests PASSED, no regressions in existing parsing tests.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/parsing/parsing_service.py backend/tests/services/parsing/test_docling_runner.py
git commit -m "feat(docling): register run_docling in ParsingService dispatch table"
```
