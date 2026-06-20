# Docling Parser Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add docling as a local parser option that converts documents to CDM `ParsedDocument` via a `DoclingAdapter` and `run_docling` runner, consistent with the LlamaParse and LandingAI parser patterns.

**Architecture:** The runner calls `DocumentConverter().convert(file_path)` inside `asyncio.to_thread`, exports to a dict via `export_to_dict()`, injects `full_text`/`full_markdown`, then passes the dict to `DoclingAdapter` which resolves docling's `$ref` pointer graph, walks the `body` tree for reading order, and maps items to CDM `Block`s. No startup client wiring — converter created per run.

**Tech Stack:** Python 3.12, docling, FastAPI async, existing CDM models (`Block`, `Page`, `Table`, `Cell`, `BBox`), pytest-asyncio.

## Global Constraints

- All new code under `backend/app/` and `backend/tests/`
- No docling imports at module level in any file (deferred into `_run_docling_sync` body only)
- Adapter takes `raw: Dict[str, Any]` → `ParsedDocument`; no live docling objects outside the runner
- Runner follows the exact same function signature as `run_llamaparse`, `run_landingai`, `run_simple`
- `uv add` for dependencies, never `pip install`
- Run tests with: `uv run --directory backend python -m pytest tests/<path> -v` (no `cd`)

---

## File Map

| Status | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/cdm/models.py` | Add `DOCLING = "docling"` to `ParserKind` |
| Modify | `backend/app/services/parsing/errors.py` | Add `DoclingRunError` |
| **Create** | `backend/app/cdm/adapters/docling.py` | `DoclingAdapter` — dict → CDM |
| **Create** | `backend/tests/cdm/adapters/test_docling_adapter.py` | Adapter unit tests (no docling dep) |
| **Create** | `backend/app/services/parsing/docling_runner.py` | `run_docling` + `_run_docling_sync` |
| **Create** | `backend/tests/services/parsing/test_docling_runner.py` | Runner tests (mock `_run_docling_sync`) |
| Modify | `backend/app/services/parsing/parsing_service.py` | Register `ParserKind.DOCLING` in `_RUNNERS` |
| Modify | `backend/pyproject.toml` | Add `docling` dependency |

---

## Task 1: Foundation — ParserKind enum + DoclingRunError

**Files:**
- Modify: `backend/app/cdm/models.py`
- Modify: `backend/app/services/parsing/errors.py`

**Interfaces:**
- Produces: `ParserKind.DOCLING` (value `"docling"`) used by Tasks 2, 3, 4
- Produces: `DoclingRunError(ParseRunError)` used by Task 3

- [ ] **Step 1: Add DOCLING to ParserKind enum**

In `backend/app/cdm/models.py`, find the `ParserKind` class (currently ends at `LANDING_AI = "landing_ai"`) and add one line:

```python
class ParserKind(str, Enum):
    SIMPLE       = "simple"
    LITEPARSE    = "liteparse"
    UNSTRUCTURED = "unstructured"
    LLAMAPARSE   = "llamaparse"
    LANDING_AI   = "landing_ai"
    DOCLING      = "docling"
```

- [ ] **Step 2: Add DoclingRunError**

In `backend/app/services/parsing/errors.py`, add after `class SimpleRunError`:

```python
class DoclingRunError(ParseRunError):
    """Raised by docling_runner when local conversion fails."""
```

- [ ] **Step 3: Verify the enum round-trips**

Run: `uv run --directory backend python -c "from app.cdm.models import ParserKind; assert ParserKind('docling') == ParserKind.DOCLING; print('OK')"`

Expected output: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/cdm/models.py backend/app/services/parsing/errors.py
git commit -m "feat(parser): add DOCLING to ParserKind enum and DoclingRunError"
```

---

## Task 2: DoclingAdapter

**Files:**
- Create: `backend/app/cdm/adapters/docling.py`
- Create: `backend/tests/cdm/adapters/test_docling_adapter.py`

**Interfaces:**
- Consumes: `ParserKind.DOCLING` from Task 1
- Consumes: `BBox`, `Block`, `BlockRole`, `Cell`, `Page`, `ParsedDocument`, `Table` from `app.cdm.models`
- Consumes: `SourceMeta` from `app.cdm.adapters.base`
- Produces: `DoclingAdapter().adapt(raw: Dict[str, Any], source_meta: SourceMeta) -> ParsedDocument`
  - `raw` must have: `body`, `furniture`, `texts`, `tables`, `pictures`, `groups`, `key_value_items`, `form_items`, `pages`, and runner-injected `full_text`, `full_markdown`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/cdm/adapters/test_docling_adapter.py`:

```python
"""Unit tests for DoclingAdapter — no docling dependency required."""
from __future__ import annotations

import pytest

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.docling import DoclingAdapter
from app.cdm.models import BlockRole

_META = SourceMeta(
    source_document_id="doc-1",
    parse_run_id="run-1",
    filename="test.pdf",
)

_PAGE = {"size": {"width": 612.0, "height": 792.0}}


def _raw(**overrides) -> dict:
    """Minimal valid docling export_to_dict() with runner-injected keys."""
    base = {
        "body": {
            "self_ref": "#/body",
            "children": [{"$ref": "#/texts/0"}],
            "name": "_root_",
            "label": "unspecified",
        },
        "furniture": {
            "self_ref": "#/furniture",
            "children": [],
            "name": "_root_",
            "label": "unspecified",
        },
        "texts": [{
            "self_ref": "#/texts/0",
            "parent": {"$ref": "#/body"},
            "children": [],
            "label": "paragraph",
            "prov": [{"page_no": 1, "bbox": {"l": 72.0, "t": 700.0, "r": 540.0, "b": 720.0, "coord_origin": "BOTTOMLEFT"}, "charspan": [0, 5]}],
            "orig": "Hello",
            "text": "Hello",
        }],
        "tables": [],
        "pictures": [],
        "key_value_items": [],
        "form_items": [],
        "groups": [],
        "pages": {"1": _PAGE},
        "full_text": "Hello",
        "full_markdown": "Hello",
    }
    base.update(overrides)
    return base


def test_paragraph_block_created():
    doc = DoclingAdapter().adapt(_raw(), _META)
    assert len(doc.blocks) == 1
    assert doc.blocks[0].role == BlockRole.PARAGRAPH
    assert doc.blocks[0].text == "Hello"


def test_role_title():
    r = _raw()
    r["texts"][0]["label"] = "title"
    doc = DoclingAdapter().adapt(r, _META)
    assert doc.blocks[0].role == BlockRole.TITLE


def test_role_section_header():
    r = _raw()
    r["texts"][0]["label"] = "section_header"
    doc = DoclingAdapter().adapt(r, _META)
    assert doc.blocks[0].role == BlockRole.HEADING


def test_bbox_bottomleft_normalized():
    # Full page bbox in BOTTOMLEFT coords → normalized [0,1] in all axes.
    r = _raw()
    r["texts"][0]["prov"][0]["bbox"] = {
        "l": 0.0, "t": 792.0, "r": 612.0, "b": 0.0, "coord_origin": "BOTTOMLEFT",
    }
    doc = DoclingAdapter().adapt(r, _META)
    bb = doc.blocks[0].bbox
    assert bb is not None
    assert round(bb.x0, 4) == 0.0
    assert round(bb.x1, 4) == 1.0
    assert round(bb.y0, 4) == 0.0
    assert round(bb.y1, 4) == 1.0


def test_bbox_topleft_normalized():
    r = _raw()
    r["texts"][0]["prov"][0]["bbox"] = {
        "l": 0.0, "t": 0.0, "r": 612.0, "b": 792.0, "coord_origin": "TOPLEFT",
    }
    doc = DoclingAdapter().adapt(r, _META)
    bb = doc.blocks[0].bbox
    assert bb is not None
    assert round(bb.y0, 4) == 0.0
    assert round(bb.y1, 4) == 1.0


def test_page_dimensions_populated():
    doc = DoclingAdapter().adapt(_raw(), _META)
    assert doc.pages[0].width == 612.0
    assert doc.pages[0].height == 792.0
    assert doc.pages[0].unit == "points"


def test_block_id_in_page_block_ids():
    doc = DoclingAdapter().adapt(_raw(), _META)
    assert doc.blocks[0].id in doc.pages[0].block_ids


def test_full_text_and_markdown_passed_through():
    r = _raw()
    r["full_text"] = "custom text"
    r["full_markdown"] = "# custom"
    doc = DoclingAdapter().adapt(r, _META)
    assert doc.full_text == "custom text"
    assert doc.full_markdown == "# custom"


def test_page_count_matches_pages():
    doc = DoclingAdapter().adapt(_raw(), _META)
    assert doc.page_count == len(doc.pages)


def test_source_meta_propagated():
    doc = DoclingAdapter().adapt(_raw(), _META)
    assert doc.source_document_id == "doc-1"
    assert doc.parse_run_id == "run-1"
    assert doc.source_filename == "test.pdf"


def test_furniture_page_header_included():
    r = _raw()
    r["texts"].append({
        "self_ref": "#/texts/1",
        "parent": {"$ref": "#/furniture"},
        "children": [],
        "label": "page_header",
        "prov": [{"page_no": 1, "bbox": {"l": 72.0, "t": 780.0, "r": 540.0, "b": 790.0, "coord_origin": "BOTTOMLEFT"}, "charspan": [0, 6]}],
        "orig": "Header",
        "text": "Header",
    })
    r["furniture"]["children"] = [{"$ref": "#/texts/1"}]
    doc = DoclingAdapter().adapt(r, _META)
    headers = [b for b in doc.blocks if b.role == BlockRole.HEADER]
    assert len(headers) == 1
    assert headers[0].text == "Header"


def test_group_node_children_traversed_in_order():
    r = _raw()
    r["texts"].append({
        "self_ref": "#/texts/1",
        "parent": {"$ref": "#/groups/0"},
        "children": [],
        "label": "paragraph",
        "prov": [{"page_no": 1, "bbox": {"l": 72.0, "t": 600.0, "r": 540.0, "b": 620.0, "coord_origin": "BOTTOMLEFT"}, "charspan": [5, 10]}],
        "orig": "World",
        "text": "World",
    })
    r["groups"] = [{
        "self_ref": "#/groups/0",
        "parent": {"$ref": "#/body"},
        "children": [{"$ref": "#/texts/1"}],
        "name": "section-1",
        "label": "section",
    }]
    r["body"]["children"] = [{"$ref": "#/texts/0"}, {"$ref": "#/groups/0"}]
    doc = DoclingAdapter().adapt(r, _META)
    assert len(doc.blocks) == 2
    assert doc.blocks[0].text == "Hello"
    assert doc.blocks[1].text == "World"


def test_table_cells_and_role():
    r = _raw()
    r["tables"] = [{
        "self_ref": "#/tables/0",
        "parent": {"$ref": "#/body"},
        "children": [],
        "label": "table",
        "prov": [{"page_no": 1, "bbox": {"l": 72.0, "t": 500.0, "r": 540.0, "b": 600.0, "coord_origin": "BOTTOMLEFT"}, "charspan": [0, 0]}],
        "data": {
            "num_rows": 2,
            "num_cols": 2,
            "table_cells": [
                {"row_span": 1, "col_span": 1, "start_row_offset_idx": 0, "end_row_offset_idx": 1,
                 "start_col_offset_idx": 0, "end_col_offset_idx": 1, "text": "A",
                 "column_header": True, "row_header": False},
                {"row_span": 1, "col_span": 1, "start_row_offset_idx": 0, "end_row_offset_idx": 1,
                 "start_col_offset_idx": 1, "end_col_offset_idx": 2, "text": "B",
                 "column_header": True, "row_header": False},
                {"row_span": 1, "col_span": 1, "start_row_offset_idx": 1, "end_row_offset_idx": 2,
                 "start_col_offset_idx": 0, "end_col_offset_idx": 1, "text": "1",
                 "column_header": False, "row_header": False},
                {"row_span": 1, "col_span": 1, "start_row_offset_idx": 1, "end_row_offset_idx": 2,
                 "start_col_offset_idx": 1, "end_col_offset_idx": 2, "text": "2",
                 "column_header": False, "row_header": False},
            ],
        },
    }]
    r["body"]["children"].append({"$ref": "#/tables/0"})
    doc = DoclingAdapter().adapt(r, _META)
    table_blocks = [b for b in doc.blocks if b.role == BlockRole.TABLE]
    assert len(table_blocks) == 1
    tbl = table_blocks[0].table
    assert tbl is not None
    assert tbl.rows == 2
    assert tbl.cols == 2
    assert len(tbl.cells) == 4
    assert tbl.cells[0].is_header is True
    assert tbl.cells[0].text == "A"
    assert "A" in table_blocks[0].text
```

- [ ] **Step 2: Run tests to confirm they all fail**

Run: `uv run --directory backend python -m pytest tests/cdm/adapters/test_docling_adapter.py -v`

Expected: all tests fail with `ModuleNotFoundError: No module named 'app.cdm.adapters.docling'`

- [ ] **Step 3: Implement DoclingAdapter**

Create `backend/app/cdm/adapters/docling.py`:

```python
"""Docling adapter — maps docling export_to_dict() output to CDM.

Input is DoclingDocument.export_to_dict() with two runner-injected keys:
  ``full_text``     — from result.document.export_to_text()
  ``full_markdown`` — from result.document.export_to_markdown()
"""
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
    "title":            BlockRole.TITLE,
    "section_header":   BlockRole.HEADING,
    "paragraph":        BlockRole.PARAGRAPH,
    "text":             BlockRole.PARAGRAPH,
    "list_item":        BlockRole.LIST,
    "list":             BlockRole.LIST,
    "table":            BlockRole.TABLE,
    "picture":          BlockRole.FIGURE,
    "caption":          BlockRole.CAPTION,
    "footnote":         BlockRole.MARGINALIA,
    "page_header":      BlockRole.HEADER,
    "page_footer":      BlockRole.FOOTER,
    "code":             BlockRole.CODE,
    "formula":          BlockRole.FORMULA,
    "key_value_region": BlockRole.OTHER,
    "form_item":        BlockRole.OTHER,
}


def _map_role(label: str) -> BlockRole:
    return _ROLE_MAP.get(label, BlockRole.OTHER)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _make_bbox(
    bbox_dict: Dict[str, Any],
    page_width: float,
    page_height: float,
) -> Optional[BBox]:
    if not bbox_dict or not page_width or not page_height:
        return None
    l = float(bbox_dict.get("l", 0.0))
    t = float(bbox_dict.get("t", 0.0))
    r = float(bbox_dict.get("r", 0.0))
    b = float(bbox_dict.get("b", 0.0))
    coord_origin = bbox_dict.get("coord_origin", "BOTTOMLEFT")
    if coord_origin == "BOTTOMLEFT":
        y0 = _clamp((page_height - b) / page_height)
        y1 = _clamp((page_height - t) / page_height)
    else:
        y0 = _clamp(t / page_height)
        y1 = _clamp(b / page_height)
    x0 = _clamp(l / page_width)
    x1 = _clamp(r / page_width)
    return BBox(
        x0=x0, y0=y0, x1=x1, y1=y1,
        source_space="pdf_points",
        source_coords=(l, t, r, b),
    )


def _build_page_dims(raw: Dict[str, Any]) -> Dict[int, tuple[float, float]]:
    dims: Dict[int, tuple[float, float]] = {}
    for page_no_str, page_data in (raw.get("pages") or {}).items():
        page_index = int(page_no_str) - 1
        size = page_data.get("size") or {}
        dims[page_index] = (
            float(size.get("width") or 0.0),
            float(size.get("height") or 0.0),
        )
    return dims


def _build_ref_lookup(raw: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for collection in ("texts", "tables", "pictures", "key_value_items", "form_items", "groups"):
        for item in raw.get(collection) or []:
            ref = item.get("self_ref")
            if ref:
                lookup[ref] = item
    return lookup


def _build_table(
    table_item: Dict[str, Any],
    page_dims: Dict[int, tuple[float, float]],
) -> Optional[Table]:
    data = table_item.get("data") or {}
    cells_raw = data.get("table_cells") or []
    num_rows = int(data.get("num_rows") or 0)
    num_cols = int(data.get("num_cols") or 0)
    if not cells_raw or num_rows == 0 or num_cols == 0:
        return None

    prov_list = table_item.get("prov") or []
    page_index = (int(prov_list[0].get("page_no", 1)) - 1) if prov_list else 0
    pw, ph = page_dims.get(page_index, (0.0, 0.0))

    cells: List[Cell] = []
    for cell_raw in cells_raw:
        cell_bbox: Optional[BBox] = None
        if cell_raw.get("bbox") and pw and ph:
            cell_bbox = _make_bbox(cell_raw["bbox"], pw, ph)
        cells.append(Cell(
            row=int(cell_raw.get("start_row_offset_idx", 0)),
            col=int(cell_raw.get("start_col_offset_idx", 0)),
            rowspan=int(cell_raw.get("row_span", 1)),
            colspan=int(cell_raw.get("col_span", 1)),
            text=str(cell_raw.get("text") or ""),
            bbox=cell_bbox,
            is_header=bool(cell_raw.get("column_header") or cell_raw.get("row_header")),
        ))
    return Table(rows=num_rows, cols=num_cols, cells=cells)


def _mint_block_id(source_document_id: str, page_index: int, reading_order: int) -> str:
    return f"{source_document_id}:p{page_index}:b{reading_order}"


class DoclingAdapter:
    parser: ClassVar[ParserKind] = ParserKind.DOCLING

    def adapt(self, raw: Dict[str, Any], source_meta: SourceMeta) -> ParsedDocument:
        page_dims = _build_page_dims(raw)
        ref_lookup = _build_ref_lookup(raw)
        all_blocks: List[Block] = []
        ro_by_page: Dict[int, int] = {}

        def _walk(children: List[Dict[str, Any]], depth: int) -> None:
            for child in children:
                ref = child.get("$ref")
                if not ref:
                    continue
                item = ref_lookup.get(ref)
                if item is None:
                    continue
                if ref.startswith("#/groups/"):
                    _walk(item.get("children") or [], depth + 1)
                    continue

                prov_list = item.get("prov") or []
                if not prov_list:
                    continue
                prov = prov_list[0]
                page_index = int(prov.get("page_no", 1)) - 1
                pw, ph = page_dims.get(page_index, (0.0, 0.0))

                ro = ro_by_page.get(page_index, 0)
                ro_by_page[page_index] = ro + 1
                block_id = _mint_block_id(source_meta.source_document_id, page_index, ro)

                label = str(item.get("label") or "")
                role = _map_role(label)
                bbox = _make_bbox(prov.get("bbox") or {}, pw, ph)

                table: Optional[Table] = None
                text = str(item.get("text") or item.get("orig") or "")
                if role == BlockRole.TABLE:
                    table = _build_table(item, page_dims)
                    if table:
                        text = " | ".join(c.text for c in table.cells if c.text)

                all_blocks.append(Block(
                    id=block_id,
                    role=role,
                    native_type=label,
                    text=text,
                    page_index=page_index,
                    bbox=bbox,
                    reading_order=ro,
                    depth=depth,
                    table=table,
                ))

        _walk((raw.get("body") or {}).get("children") or [], depth=0)
        _walk((raw.get("furniture") or {}).get("children") or [], depth=0)

        pages_map: Dict[int, List[str]] = {}
        for block in all_blocks:
            pages_map.setdefault(block.page_index, []).append(block.id)

        page_count = (max(pages_map.keys()) + 1) if pages_map else 0
        pages: List[Page] = []
        for pi in range(page_count):
            pw, ph = page_dims.get(pi, (0.0, 0.0))
            pages.append(Page(
                index=pi,
                width=pw if pw else None,
                height=ph if ph else None,
                unit="points" if pw else None,
                block_ids=pages_map.get(pi, []),
            ))

        return ParsedDocument(
            id=str(uuid.uuid4()),
            source_document_id=source_meta.source_document_id,
            parse_run_id=source_meta.parse_run_id,
            source_filename=source_meta.filename,
            page_count=page_count,
            pages=pages,
            blocks=all_blocks,
            full_text=raw.get("full_text") or None,
            full_markdown=raw.get("full_markdown") or None,
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `uv run --directory backend python -m pytest tests/cdm/adapters/test_docling_adapter.py -v`

Expected: all 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/docling.py backend/tests/cdm/adapters/test_docling_adapter.py
git commit -m "feat(parser): add DoclingAdapter — dict to CDM mapping"
```

---

## Task 3: DoclingRunner

**Files:**
- Create: `backend/app/services/parsing/docling_runner.py`
- Create: `backend/tests/services/parsing/test_docling_runner.py`

**Interfaces:**
- Consumes: `DoclingAdapter` from Task 2
- Consumes: `DoclingRunError` from Task 1
- Consumes: `ParserKind.DOCLING` from Task 1
- Produces: `run_docling(*, source, file_path, representation_kind, config, client, parse_run_id) -> Tuple[ParseRun, ParsedDocument]`
  - `config["ocr"]` (bool, default `False`) enables EasyOCR
  - `client` is ignored (docling is local)
  - Raises `DoclingRunError` (carrying a failed `ParseRun`) on conversion failure

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/services/parsing/test_docling_runner.py`:

```python
"""Tests for run_docling — mocks _run_docling_sync to avoid docling install."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.cdm.models import ParserKind
from app.cdm.source import ParseRunStatus, SourceDocument
from app.services.parsing.errors import DoclingRunError
from app.services.parsing.docling_runner import run_docling


_MINIMAL_EXPORT = {
    "body": {
        "self_ref": "#/body",
        "children": [{"$ref": "#/texts/0"}],
        "name": "_root_",
        "label": "unspecified",
    },
    "furniture": {
        "self_ref": "#/furniture",
        "children": [],
        "name": "_root_",
        "label": "unspecified",
    },
    "texts": [{
        "self_ref": "#/texts/0",
        "parent": {"$ref": "#/body"},
        "children": [],
        "label": "paragraph",
        "prov": [{"page_no": 1, "bbox": {"l": 0, "t": 100, "r": 612, "b": 0, "coord_origin": "BOTTOMLEFT"}, "charspan": [0, 5]}],
        "orig": "Hello",
        "text": "Hello",
    }],
    "tables": [], "pictures": [], "key_value_items": [], "form_items": [], "groups": [],
    "pages": {"1": {"size": {"width": 612.0, "height": 792.0}}},
}


def _source() -> SourceDocument:
    return SourceDocument(
        id=str(uuid4()),
        sha256="a" * 64,
        filename="test.pdf",
        created_at=datetime.now(timezone.utc),
    )


def _fake_result() -> MagicMock:
    result = MagicMock()
    result.document.export_to_dict.return_value = dict(_MINIMAL_EXPORT)
    result.document.export_to_text.return_value = "Hello"
    result.document.export_to_markdown.return_value = "Hello"
    return result


@pytest.mark.asyncio
async def test_success_returns_run_and_doc(tmp_path):
    fp = str(tmp_path / "test.pdf")
    open(fp, "wb").close()

    with patch("app.services.parsing.docling_runner._run_docling_sync", return_value=_fake_result()):
        run, doc = await run_docling(
            source=_source(), file_path=fp,
            representation_kind="extract_rich",
            config={"parser": "docling"}, client=None,
        )

    assert run.parser == ParserKind.DOCLING
    assert run.status == ParseRunStatus.SUCCEEDED
    assert run.duration_ms >= 0
    assert doc.source_document_id == run.source_document_id


@pytest.mark.asyncio
async def test_full_text_and_markdown_injected_into_raw_payload(tmp_path):
    fp = str(tmp_path / "test.pdf")
    open(fp, "wb").close()

    with patch("app.services.parsing.docling_runner._run_docling_sync", return_value=_fake_result()):
        run, doc = await run_docling(
            source=_source(), file_path=fp,
            representation_kind="extract_rich",
            config={}, client=None,
        )

    assert run.raw_payload["full_text"] == "Hello"
    assert run.raw_payload["full_markdown"] == "Hello"
    assert doc.full_text == "Hello"


@pytest.mark.asyncio
async def test_failure_raises_docling_run_error(tmp_path):
    fp = str(tmp_path / "test.pdf")
    open(fp, "wb").close()

    with patch(
        "app.services.parsing.docling_runner._run_docling_sync",
        side_effect=RuntimeError("conversion failed"),
    ):
        with pytest.raises(DoclingRunError) as exc_info:
            await run_docling(
                source=_source(), file_path=fp,
                representation_kind="extract_rich",
                config={}, client=None,
            )

    err = exc_info.value
    assert err.run.status == ParseRunStatus.FAILED
    assert "conversion failed" in err.run.error
    assert err.run.finished_at is not None
    assert err.run.duration_ms >= 0
    assert err.run.raw_payload is None


@pytest.mark.asyncio
async def test_ocr_false_by_default(tmp_path):
    fp = str(tmp_path / "test.pdf")
    open(fp, "wb").close()

    with patch(
        "app.services.parsing.docling_runner._run_docling_sync",
        return_value=_fake_result(),
    ) as mock_sync:
        await run_docling(
            source=_source(), file_path=fp,
            representation_kind="extract_rich",
            config={}, client=None,
        )

    mock_sync.assert_called_once_with(fp, False)


@pytest.mark.asyncio
async def test_ocr_true_passed_to_sync(tmp_path):
    fp = str(tmp_path / "test.pdf")
    open(fp, "wb").close()

    with patch(
        "app.services.parsing.docling_runner._run_docling_sync",
        return_value=_fake_result(),
    ) as mock_sync:
        await run_docling(
            source=_source(), file_path=fp,
            representation_kind="extract_rich",
            config={"ocr": True}, client=None,
        )

    mock_sync.assert_called_once_with(fp, True)


@pytest.mark.asyncio
async def test_parse_run_id_propagated(tmp_path):
    fp = str(tmp_path / "test.pdf")
    open(fp, "wb").close()

    with patch("app.services.parsing.docling_runner._run_docling_sync", return_value=_fake_result()):
        run, _ = await run_docling(
            source=_source(), file_path=fp,
            representation_kind="extract_rich",
            config={}, client=None,
            parse_run_id="fixed-id",
        )

    assert run.id == "fixed-id"
```

- [ ] **Step 2: Run tests to confirm they all fail**

Run: `uv run --directory backend python -m pytest tests/services/parsing/test_docling_runner.py -v`

Expected: all 6 tests fail with `ModuleNotFoundError: No module named 'app.services.parsing.docling_runner'`

- [ ] **Step 3: Implement the runner**

Create `backend/app/services/parsing/docling_runner.py`:

```python
"""Drives docling end-to-end: local convert → ParseRun + ParsedDocument."""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.docling import DoclingAdapter
from app.cdm.models import ParsedDocument, ParserKind
from app.cdm.source import ParseRun, ParseRunStatus, SourceDocument
from app.services.parsing.errors import DoclingRunError


def _run_docling_sync(file_path: str, ocr_enabled: bool) -> Any:
    """Blocking docling conversion. Must be called via asyncio.to_thread."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import EasyOcrOptions, PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    if ocr_enabled:
        pipeline_options = PdfPipelineOptions(do_ocr=True, ocr_options=EasyOcrOptions())
        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )
    else:
        converter = DocumentConverter()

    return converter.convert(file_path)


async def run_docling(
    *,
    source: SourceDocument,
    file_path: str,
    representation_kind: str,
    config: Dict[str, Any],
    client: Any,  # unused — docling is local, no external client
    parse_run_id: Optional[str] = None,
) -> Tuple[ParseRun, ParsedDocument]:
    """Parse file_path via docling and adapt to CDM."""
    run_id = parse_run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    ocr_enabled = bool(config.get("ocr", False))

    try:
        result = await asyncio.to_thread(_run_docling_sync, file_path, ocr_enabled)
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
        raise DoclingRunError(f"Docling failed: {exc}", run=failed) from exc

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((time.perf_counter() - t0) * 1000)

    raw = result.document.export_to_dict()
    raw["full_text"] = result.document.export_to_text()
    raw["full_markdown"] = result.document.export_to_markdown()

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
        raw_payload=raw,
    )

    doc = DoclingAdapter().adapt(raw, SourceMeta(
        source_document_id=source.id,
        parse_run_id=run.id,
        filename=source.filename,
        sha256=source.sha256,
    ))
    return run, doc
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `uv run --directory backend python -m pytest tests/services/parsing/test_docling_runner.py -v`

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parsing/docling_runner.py backend/tests/services/parsing/test_docling_runner.py
git commit -m "feat(parser): add docling_runner with asyncio.to_thread and OCR toggle"
```

---

## Task 4: Wire up — parsing_service + install dependency

**Files:**
- Modify: `backend/app/services/parsing/parsing_service.py`
- Modify: `backend/pyproject.toml` (via `uv add`)

**Interfaces:**
- Consumes: `run_docling` from Task 3
- Consumes: `ParserKind.DOCLING` from Task 1

- [ ] **Step 1: Register the runner in parsing_service**

In `backend/app/services/parsing/parsing_service.py`, add the import alongside the other runner imports:

```python
from app.services.parsing.docling_runner import run_docling
```

Then add `ParserKind.DOCLING` to the `_RUNNERS` dict:

```python
_RUNNERS: Dict[ParserKind, Callable] = {
    ParserKind.LLAMAPARSE: run_llamaparse,
    ParserKind.LANDING_AI: run_landingai,
    ParserKind.SIMPLE: run_simple,
    ParserKind.DOCLING: run_docling,
}
```

- [ ] **Step 2: Verify existing parsing_service tests still pass**

Run: `uv run --directory backend python -m pytest tests/services/parsing/test_parsing_service.py -v`

Expected: all tests PASS (no new tests needed — the service's runner dispatch is already covered by existing tests for the other parsers)

- [ ] **Step 3: Install docling**

Run: `uv add --directory backend docling`

Wait for it to complete (docling has heavy dependencies including torch). Expected: `pyproject.toml` and `uv.lock` updated.

- [ ] **Step 4: Verify all new tests still pass after install**

Run: `uv run --directory backend python -m pytest tests/cdm/adapters/test_docling_adapter.py tests/services/parsing/test_docling_runner.py -v`

Expected: all 19 tests PASS

- [ ] **Step 5: Smoke-test the import chain**

Run: `uv run --directory backend python -c "from app.services.parsing.parsing_service import _RUNNERS; from app.cdm.models import ParserKind; assert ParserKind.DOCLING in _RUNNERS; print('DOCLING registered:', _RUNNERS[ParserKind.DOCLING])"`

Expected output: `DOCLING registered: <function run_docling at 0x...>`

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/parsing/parsing_service.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(parser): wire docling into parsing_service and install dependency"
```
