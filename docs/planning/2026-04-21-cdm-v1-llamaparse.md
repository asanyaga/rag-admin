# CDM v1 + LlamaParse Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the canonical document model (CDM) types, a LlamaParse adapter that maps LlamaParse output to CDM, a thin orchestration runner, and a lightweight pytest-based eval harness.

**Architecture:** Greenfield package at `backend/app/cdm/` with three-level identity (`SourceDocument → ParseRun → ParsedDocument`). Frozen Pydantic v2 models. One adapter (`LlamaParseAdapter`) implementing a `ParserAdapter` protocol. Runner lives outside the CDM package in `app/services/parsing/`. Eval uses recorded LlamaParse JSON fixtures so tests run offline.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, `llama-cloud` SDK (already a project dep).

**Spec:** [`docs/specs/cdm_v1.md`](../specs/cdm_v1.md) — authoritative for scope and acceptance criteria.

---

## File Structure

Created:

```
backend/app/cdm/
  __init__.py
  models.py                # enums, BBox, Quality, Style, Span, Cell, Table, Block, Page, Label, ParsedDocument
  source.py                # SourceDocument, ParseRun, ParseRunStatus
  citation.py              # CitationRef
  adapters/
    __init__.py
    base.py                # ParserAdapter protocol, SourceMeta
    llamaparse.py          # LlamaParseAdapter
backend/app/services/parsing/
  __init__.py
  llamaparse_runner.py     # orchestration: SourceDocument + config -> (ParseRun, ParsedDocument)
backend/tests/cdm/
  __init__.py
  test_models.py
  test_source.py
  test_citation.py
  adapters/
    __init__.py
    test_llamaparse_adapter.py
  eval/
    __init__.py
    conftest.py
    recorder.py            # metrics jsonl writer
    test_llamaparse_eval.py
    fixtures/
      one_page_text.json           # recorded LlamaParse response
      one_page_text.expected.json  # snapshot (generated on first run)
      table_and_headings.json
      table_and_headings.expected.json
      multi_column.json
      multi_column.expected.json
```

Not modified: `app/adapters/parsing/llamaparse.py` (the existing adapter stays untouched).

---

## Task 1: CDM Enums and Geometry

**Files:**
- Create: `backend/app/cdm/__init__.py`
- Create: `backend/app/cdm/models.py`
- Create: `backend/tests/cdm/__init__.py`
- Create: `backend/tests/cdm/test_models.py`

- [ ] **Step 1: Write failing tests for enums and BBox**

Create `backend/tests/cdm/test_models.py`:

```python
import pytest
from pydantic import ValidationError

from app.cdm.models import BBox, BlockRole, CoordSpace, ParserKind


def test_parser_kind_values():
    assert ParserKind.LLAMAPARSE.value == "llamaparse"
    assert ParserKind.LITEPARSE.value == "liteparse"
    assert ParserKind.UNSTRUCTURED.value == "unstructured"
    assert ParserKind.LANDING_AI.value == "landing_ai"


def test_block_role_has_coarse_taxonomy():
    # Closed taxonomy — ~14 values.
    assert BlockRole.TITLE.value == "title"
    assert BlockRole.PARAGRAPH.value == "paragraph"
    assert BlockRole.TABLE.value == "table"
    assert BlockRole.OTHER.value == "other"


def test_bbox_defaults_to_normalized_space():
    b = BBox(x0=0.1, y0=0.2, x1=0.5, y1=0.6)
    assert b.space == CoordSpace.NORMALIZED
    assert b.source_space is None
    assert b.source_coords is None


def test_bbox_preserves_source_coords():
    b = BBox(
        x0=0.1, y0=0.2, x1=0.5, y1=0.6,
        source_space="pdf_points",
        source_coords=(72.0, 144.0, 360.0, 432.0),
    )
    assert b.source_space == "pdf_points"
    assert b.source_coords == (72.0, 144.0, 360.0, 432.0)


def test_bbox_is_frozen():
    b = BBox(x0=0.0, y0=0.0, x1=1.0, y1=1.0)
    with pytest.raises(ValidationError):
        b.x0 = 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/cdm/test_models.py -v -o "addopts="`
Expected: ImportError / ModuleNotFoundError for `app.cdm.models`.

- [ ] **Step 3: Create the package init**

Create `backend/app/cdm/__init__.py` with contents:

```python
"""Canonical Document Model (CDM) — parser-agnostic document representation."""
```

Create `backend/tests/cdm/__init__.py` as an empty file:

```python
```

- [ ] **Step 4: Implement enums and BBox**

Create `backend/app/cdm/models.py`:

```python
"""Canonical Document Model types — core content representation.

All models are frozen Pydantic v2 BaseModels. Mutations return new instances
via `model_copy(update=...)`.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict


class ParserKind(str, Enum):
    LITEPARSE    = "liteparse"
    UNSTRUCTURED = "unstructured"
    LLAMAPARSE   = "llamaparse"
    LANDING_AI   = "landing_ai"


class BlockRole(str, Enum):
    TITLE      = "title"
    HEADING    = "heading"
    PARAGRAPH  = "paragraph"
    LIST       = "list"
    TABLE      = "table"
    FIGURE     = "figure"
    CAPTION    = "caption"
    HEADER     = "header"
    FOOTER     = "footer"
    MARGINALIA = "marginalia"
    CODE       = "code"
    FORMULA    = "formula"
    LINK       = "link"
    OTHER      = "other"


class CoordSpace(str, Enum):
    NORMALIZED = "normalized"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BBox(_Frozen):
    """Normalized bounding box — origin top-left, fractions of page size."""
    x0: float
    y0: float
    x1: float
    y1: float
    space: CoordSpace = CoordSpace.NORMALIZED
    source_space: Optional[str] = None                              # "pdf_points" | "pixels" | "fraction"
    source_coords: Optional[Tuple[float, float, float, float]] = None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/cdm/test_models.py -v -o "addopts="`
Expected: 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/cdm/__init__.py backend/app/cdm/models.py backend/tests/cdm/__init__.py backend/tests/cdm/test_models.py
git commit -m "feat(cdm): enums and BBox geometry type"
```

---

## Task 2: Quality, Style, Span, Cell, Table

**Files:**
- Modify: `backend/app/cdm/models.py` (append)
- Modify: `backend/tests/cdm/test_models.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/cdm/test_models.py`:

```python
from app.cdm.models import Cell, Quality, Span, Style, Table


def test_quality_defaults():
    q = Quality()
    assert q.confidence is None
    assert q.low_confidence_spans == []
    assert q.notes is None


def test_style_fields_optional():
    s = Style(font_name="Helvetica", font_size=12.0, bold=True, italic=False)
    assert s.bold is True


def test_span_carries_text_and_optional_bbox():
    sp = Span(text="hello")
    assert sp.text == "hello"
    assert sp.bbox is None
    assert sp.style is None


def test_cell_minimum_fields():
    c = Cell(row=0, col=0, text="A")
    assert c.rowspan == 1
    assert c.colspan == 1
    assert c.is_header is False


def test_table_requires_dimensions_and_cells():
    t = Table(rows=2, cols=2, cells=[
        Cell(row=0, col=0, text="A", is_header=True),
        Cell(row=0, col=1, text="B", is_header=True),
        Cell(row=1, col=0, text="1"),
        Cell(row=1, col=1, text="2"),
    ])
    assert t.rows == 2
    assert len(t.cells) == 4
    assert t.html is None
    assert t.markdown is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/cdm/test_models.py -v -o "addopts="`
Expected: ImportErrors for the new names.

- [ ] **Step 3: Append types to models.py**

Append to `backend/app/cdm/models.py`:

```python
from typing import List


class Quality(_Frozen):
    confidence: Optional[float] = None
    low_confidence_spans: List[Tuple[int, int]] = []
    notes: Optional[str] = None


class Style(_Frozen):
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None


class Span(_Frozen):
    text: str
    bbox: Optional[BBox] = None
    style: Optional[Style] = None


class Cell(_Frozen):
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    text: str
    bbox: Optional[BBox] = None
    quality: Optional[Quality] = None
    is_header: bool = False


class Table(_Frozen):
    rows: int
    cols: int
    cells: List[Cell]
    html: Optional[str] = None
    markdown: Optional[str] = None
    caption: Optional[str] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/cdm/test_models.py -v -o "addopts="`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/models.py backend/tests/cdm/test_models.py
git commit -m "feat(cdm): Quality, Style, Span, Cell, Table types"
```

---

## Task 3: Block, Page, Label

**Files:**
- Modify: `backend/app/cdm/models.py` (append)
- Modify: `backend/tests/cdm/test_models.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/cdm/test_models.py`:

```python
from app.cdm.models import Block, Label, Page


def test_block_minimum_fields():
    b = Block(
        id="b1",
        role=BlockRole.PARAGRAPH,
        native_type="text",
        page_index=0,
    )
    assert b.text == ""
    assert b.children_ids == []
    assert b.parser_extras == {}
    assert b.is_continuation is False


def test_block_parser_extras_accept_arbitrary_values():
    b = Block(
        id="b1",
        role=BlockRole.OTHER,
        native_type="weird",
        page_index=0,
        parser_extras={"foo": [1, 2, 3], "bar": {"nested": True}},
    )
    assert b.parser_extras["foo"] == [1, 2, 3]


def test_page_defaults():
    p = Page(index=0)
    assert p.rotation == 0
    assert p.block_ids == []
    assert p.width is None


def test_label_scope_defaults_to_document():
    lbl = Label(name="annual_report")
    assert lbl.scope == "document"
    assert lbl.source == "classifier"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/cdm/test_models.py -v -o "addopts="`
Expected: ImportErrors.

- [ ] **Step 3: Append Block, Page, Label to models.py**

Append to `backend/app/cdm/models.py`:

```python
from typing import Any, Dict, Literal, Union


class Block(_Frozen):
    id: str
    role: BlockRole
    native_type: str
    native_label: Optional[str] = None
    text: str = ""
    markdown: Optional[str] = None
    html: Optional[str] = None
    page_index: int
    bbox: Optional[BBox] = None
    reading_order: Optional[int] = None
    depth: Optional[int] = None
    parent_id: Optional[str] = None
    children_ids: List[str] = []
    spans: List[Span] = []
    table: Optional[Table] = None
    image_ref: Optional[str] = None
    style: Optional[Style] = None
    quality: Optional[Quality] = None
    language: Optional[str] = None
    is_continuation: bool = False
    parser_extras: Dict[str, Any] = {}


class Page(_Frozen):
    index: int
    width: Optional[float] = None
    height: Optional[float] = None
    unit: Optional[str] = None
    rotation: int = 0
    block_ids: List[str] = []
    quality: Optional[Quality] = None
    parser_extras: Dict[str, Any] = {}


class Label(_Frozen):
    name: str
    confidence: Optional[float] = None
    scope: Literal["document", "page", "block"] = "document"
    scope_ref: Optional[Union[int, str]] = None
    source: Literal["parser", "classifier", "human"] = "classifier"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/cdm/test_models.py -v -o "addopts="`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/models.py backend/tests/cdm/test_models.py
git commit -m "feat(cdm): Block, Page, Label types"
```

---

## Task 4: ParsedDocument Root

**Files:**
- Modify: `backend/app/cdm/models.py` (append)
- Modify: `backend/tests/cdm/test_models.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/cdm/test_models.py`:

```python
from app.cdm.models import ParsedDocument


def test_parsed_document_minimum_shape():
    doc = ParsedDocument(
        id="doc-1",
        source_document_id="src-1",
        parse_run_id="run-1",
        page_count=1,
        pages=[Page(index=0)],
        blocks=[],
    )
    assert doc.schema_version == "1.0"
    assert doc.labels == []
    assert doc.derived_from is None


def test_parsed_document_json_round_trip():
    doc = ParsedDocument(
        id="doc-1",
        source_document_id="src-1",
        parse_run_id="run-1",
        page_count=1,
        pages=[Page(index=0, block_ids=["b1"])],
        blocks=[Block(
            id="b1",
            role=BlockRole.PARAGRAPH,
            native_type="text",
            text="hello",
            page_index=0,
        )],
    )
    restored = ParsedDocument.model_validate_json(doc.model_dump_json())
    assert restored == doc
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/cdm/test_models.py -v -o "addopts="`
Expected: ImportError for `ParsedDocument`.

- [ ] **Step 3: Append ParsedDocument to models.py**

Append to `backend/app/cdm/models.py`:

```python
class ParsedDocument(_Frozen):
    id: str
    source_document_id: str
    parse_run_id: str
    source_filename: Optional[str] = None
    page_count: int
    pages: List[Page]
    blocks: List[Block]
    full_text: Optional[str] = None
    full_markdown: Optional[str] = None
    labels: List[Label] = []
    # Lineage for future split() outputs — set when this is a derived document.
    derived_from: Optional[str] = None
    derivation: Optional[str] = None
    schema_version: str = "1.0"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/cdm/test_models.py -v -o "addopts="`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/models.py backend/tests/cdm/test_models.py
git commit -m "feat(cdm): ParsedDocument root type"
```

---

## Task 5: SourceDocument and ParseRun

**Files:**
- Create: `backend/app/cdm/source.py`
- Create: `backend/tests/cdm/test_source.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/cdm/test_source.py`:

```python
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.cdm.models import ParserKind
from app.cdm.source import ParseRun, ParseRunStatus, SourceDocument


def test_source_document_minimum_shape():
    s = SourceDocument(
        id="src-1",
        sha256="a" * 64,
        created_at=datetime.now(timezone.utc),
    )
    assert s.filename is None
    assert s.storage_uri is None


def test_parse_run_defaults():
    r = ParseRun(
        id="run-1",
        source_document_id="src-1",
        parser=ParserKind.LLAMAPARSE,
        representation_kind="extract_rich",
        status=ParseRunStatus.SUCCEEDED,
        started_at=datetime.now(timezone.utc),
    )
    assert r.config == {}
    assert r.cost == {}
    assert r.provider_refs == {}
    assert r.failed_pages == []
    assert r.warnings == []


def test_parse_run_is_frozen():
    r = ParseRun(
        id="run-1",
        source_document_id="src-1",
        parser=ParserKind.LLAMAPARSE,
        representation_kind="extract_rich",
        status=ParseRunStatus.PENDING,
        started_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValidationError):
        r.status = ParseRunStatus.SUCCEEDED


def test_parse_run_statuses():
    assert ParseRunStatus.PENDING.value == "pending"
    assert ParseRunStatus.RUNNING.value == "running"
    assert ParseRunStatus.SUCCEEDED.value == "succeeded"
    assert ParseRunStatus.FAILED.value == "failed"
    assert ParseRunStatus.PARTIAL.value == "partial"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/cdm/test_source.py -v -o "addopts="`
Expected: ImportError for `app.cdm.source`.

- [ ] **Step 3: Implement source.py**

Create `backend/app/cdm/source.py`:

```python
"""SourceDocument and ParseRun — identity and execution records.

A SourceDocument is the content-addressable representation of input bytes.
A ParseRun is one execution of a parser against a SourceDocument, identified
separately so that a single source can have multiple parsed representations
(e.g. vector_light vs. extract_rich) each with their own metrics.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from app.cdm.models import ParserKind


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ParseRunStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    SUCCEEDED = "succeeded"
    FAILED    = "failed"
    PARTIAL   = "partial"


class SourceDocument(_Frozen):
    id: str
    sha256: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    byte_size: Optional[int] = None
    storage_uri: Optional[str] = None
    created_at: datetime


class ParseRun(_Frozen):
    id: str
    source_document_id: str
    parser: ParserKind
    parser_version: Optional[str] = None
    representation_kind: str  # open string: "vector_light" | "extract_rich" | ...
    config: Dict[str, Any] = {}
    status: ParseRunStatus
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    cost: Dict[str, Any] = {}
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    warnings: List[str] = []
    failed_pages: List[int] = []
    provider_refs: Dict[str, Any] = {}
    error: Optional[str] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/cdm/test_source.py -v -o "addopts="`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/source.py backend/tests/cdm/test_source.py
git commit -m "feat(cdm): SourceDocument and ParseRun"
```

---

## Task 6: CitationRef

**Files:**
- Create: `backend/app/cdm/citation.py`
- Create: `backend/tests/cdm/test_citation.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/cdm/test_citation.py`:

```python
from app.cdm.citation import CitationRef
from app.cdm.models import BBox


def test_citation_ref_block_level():
    ref = CitationRef(
        source_document_id="src-1",
        parse_run_id="run-1",
        block_id="b42",
        page_index=3,
    )
    assert ref.char_start is None
    assert ref.cell_id is None
    assert ref.bbox is None


def test_citation_ref_char_offset():
    ref = CitationRef(
        source_document_id="src-1",
        parse_run_id="run-1",
        block_id="b42",
        page_index=3,
        char_start=17,
        char_end=42,
    )
    assert ref.char_end - ref.char_start == 25


def test_citation_ref_cell_level_with_bbox():
    ref = CitationRef(
        source_document_id="src-1",
        parse_run_id="run-1",
        block_id="b42",
        page_index=3,
        cell_id="r2c1",
        bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.2),
    )
    assert ref.cell_id == "r2c1"
    assert ref.bbox.x0 == 0.1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/cdm/test_citation.py -v -o "addopts="`
Expected: ImportError.

- [ ] **Step 3: Implement citation.py**

Create `backend/app/cdm/citation.py`:

```python
"""CitationRef — references from downstream outputs back to CDM blocks.

Block IDs are only unique within a ParseRun, so parse_run_id is required.
bbox is denormalized for UI overlay rendering without a lookup.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.cdm.models import BBox


class CitationRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_document_id: str
    parse_run_id: str
    block_id: str
    page_index: int
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    cell_id: Optional[str] = None
    bbox: Optional[BBox] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/cdm/test_citation.py -v -o "addopts="`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/citation.py backend/tests/cdm/test_citation.py
git commit -m "feat(cdm): CitationRef type"
```

---

## Task 7: Adapter Protocol

**Files:**
- Create: `backend/app/cdm/adapters/__init__.py`
- Create: `backend/app/cdm/adapters/base.py`
- Create: `backend/tests/cdm/adapters/__init__.py`

- [ ] **Step 1: Create package inits**

Create `backend/app/cdm/adapters/__init__.py`:

```python
"""Parser adapters — map parser-native output to ParsedDocument."""
```

Create `backend/tests/cdm/adapters/__init__.py` empty.

- [ ] **Step 2: Implement adapter protocol**

Create `backend/app/cdm/adapters/base.py`:

```python
"""Adapter protocol — each parser implementation adapts raw output to CDM."""
from __future__ import annotations

from typing import Any, ClassVar, Optional, Protocol

from pydantic import BaseModel

from app.cdm.models import ParsedDocument, ParserKind


class SourceMeta(BaseModel):
    """Identity passed into an adapter so it can wire up foreign references."""
    source_document_id: str
    parse_run_id: str
    filename: Optional[str] = None
    sha256: Optional[str] = None


class ParserAdapter(Protocol):
    parser: ClassVar[ParserKind]

    def adapt(self, raw: Any, source_meta: SourceMeta) -> ParsedDocument: ...
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/cdm/adapters/__init__.py backend/app/cdm/adapters/base.py backend/tests/cdm/adapters/__init__.py
git commit -m "feat(cdm): ParserAdapter protocol and SourceMeta"
```

---

## Task 8: LlamaParse Adapter — Conversion Helpers

Scope: pure helper functions (no SDK calls). TDD them first, then wire into the full adapter in Task 9.

**Files:**
- Create: `backend/app/cdm/adapters/llamaparse.py`
- Create: `backend/tests/cdm/adapters/test_llamaparse_adapter.py`

- [ ] **Step 1: Write failing tests for helpers**

Create `backend/tests/cdm/adapters/test_llamaparse_adapter.py`:

```python
import pytest

from app.cdm.adapters.llamaparse import (
    _map_role,
    _pdf_points_to_normalized,
    _union_bbox,
)
from app.cdm.models import BBox, BlockRole


def test_pdf_points_to_normalized_basic():
    # page_width=100, page_height=200 in pdf points.
    bbox = _pdf_points_to_normalized(x=10, y=20, w=30, h=40,
                                      page_width=100, page_height=200)
    assert bbox.x0 == pytest.approx(0.10)
    assert bbox.y0 == pytest.approx(0.10)
    assert bbox.x1 == pytest.approx(0.40)
    assert bbox.y1 == pytest.approx(0.30)
    assert bbox.source_space == "pdf_points"
    assert bbox.source_coords == (10.0, 20.0, 30.0, 40.0)


def test_pdf_points_clamps_to_unit_square():
    # Values slightly outside [0,1] due to rounding should clamp.
    bbox = _pdf_points_to_normalized(x=0, y=0, w=101, h=201,
                                      page_width=100, page_height=200)
    assert bbox.x0 == 0.0
    assert bbox.y0 == 0.0
    assert bbox.x1 == 1.0
    assert bbox.y1 == 1.0


def test_union_bbox_single():
    b = BBox(x0=0.1, y0=0.2, x1=0.5, y1=0.6)
    assert _union_bbox([b]) == b


def test_union_bbox_multiple():
    b1 = BBox(x0=0.1, y0=0.2, x1=0.4, y1=0.5)
    b2 = BBox(x0=0.2, y0=0.1, x1=0.6, y1=0.4)
    u = _union_bbox([b1, b2])
    assert u.x0 == pytest.approx(0.1)
    assert u.y0 == pytest.approx(0.1)
    assert u.x1 == pytest.approx(0.6)
    assert u.y1 == pytest.approx(0.5)


def test_union_bbox_empty_returns_none():
    assert _union_bbox([]) is None


@pytest.mark.parametrize("llama_type,expected_role", [
    ("heading", BlockRole.HEADING),
    ("text", BlockRole.PARAGRAPH),
    ("list", BlockRole.LIST),
    ("table", BlockRole.TABLE),
    ("image", BlockRole.FIGURE),
    ("header", BlockRole.HEADER),
    ("footer", BlockRole.FOOTER),
    ("code", BlockRole.CODE),
    ("link", BlockRole.LINK),
    ("mystery", BlockRole.OTHER),
])
def test_map_role(llama_type, expected_role):
    assert _map_role(llama_type) == expected_role
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/cdm/adapters/test_llamaparse_adapter.py -v -o "addopts="`
Expected: ImportError.

- [ ] **Step 3: Implement helpers**

Create `backend/app/cdm/adapters/llamaparse.py`:

```python
"""LlamaParse adapter — maps llama-cloud parsing output to CDM.

Input is the result of ``client.parsing.parse(...)`` after ``.model_dump()``,
i.e. a plain dict with top-level keys controlled by the ``expand`` parameter
(``text``, ``markdown``, ``items``, ``metadata``, ``job_metadata``).
"""
from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional, Tuple

from app.cdm.adapters.base import ParserAdapter, SourceMeta
from app.cdm.models import (
    BBox,
    Block,
    BlockRole,
    Page,
    ParsedDocument,
    ParserKind,
    Quality,
)


_ROLE_MAP: Dict[str, BlockRole] = {
    "heading": BlockRole.HEADING,
    "text":    BlockRole.PARAGRAPH,
    "list":    BlockRole.LIST,
    "table":   BlockRole.TABLE,
    "image":   BlockRole.FIGURE,
    "header":  BlockRole.HEADER,
    "footer":  BlockRole.FOOTER,
    "code":    BlockRole.CODE,
    "link":    BlockRole.LINK,
}


def _map_role(native_type: str) -> BlockRole:
    return _ROLE_MAP.get(native_type, BlockRole.OTHER)


def _clamp(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _pdf_points_to_normalized(
    *, x: float, y: float, w: float, h: float,
    page_width: float, page_height: float,
) -> BBox:
    x0 = _clamp(x / page_width)
    y0 = _clamp(y / page_height)
    x1 = _clamp((x + w) / page_width)
    y1 = _clamp((y + h) / page_height)
    return BBox(
        x0=x0, y0=y0, x1=x1, y1=y1,
        source_space="pdf_points",
        source_coords=(float(x), float(y), float(w), float(h)),
    )


def _union_bbox(bboxes: List[BBox]) -> Optional[BBox]:
    if not bboxes:
        return None
    if len(bboxes) == 1:
        return bboxes[0]
    x0 = min(b.x0 for b in bboxes)
    y0 = min(b.y0 for b in bboxes)
    x1 = max(b.x1 for b in bboxes)
    y1 = max(b.y1 for b in bboxes)
    return BBox(x0=x0, y0=y0, x1=x1, y1=y1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/cdm/adapters/test_llamaparse_adapter.py -v -o "addopts="`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/llamaparse.py backend/tests/cdm/adapters/test_llamaparse_adapter.py
git commit -m "feat(cdm): LlamaParse conversion helpers"
```

---

## Task 9: LlamaParse Adapter — Full `adapt()` Method

Scope: build `ParsedDocument` from a raw LlamaParse response dict. Tested against a hand-crafted minimal fixture that mirrors the real SDK shape.

**Files:**
- Modify: `backend/app/cdm/adapters/llamaparse.py` (append `LlamaParseAdapter` class)
- Modify: `backend/tests/cdm/adapters/test_llamaparse_adapter.py` (append end-to-end tests)

- [ ] **Step 1: Write the failing end-to-end test with a minimal fixture**

Append to `backend/tests/cdm/adapters/test_llamaparse_adapter.py`:

```python
from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.llamaparse import LlamaParseAdapter
from app.cdm.models import ParserKind


MINIMAL_RAW = {
    "text": "Title\n\nBody paragraph.",
    "markdown": "# Title\n\nBody paragraph.",
    "items": {
        "pages": [
            {
                "page_number": 1,
                "width": 100.0,
                "height": 200.0,
                "items": [
                    {
                        "type": "heading",
                        "level": 1,
                        "value": "Title",
                        "md": "# Title",
                        "bbox": [
                            {"x": 10, "y": 10, "w": 30, "h": 10,
                             "confidence": 0.98, "label": "paragraph_title"},
                        ],
                    },
                    {
                        "type": "text",
                        "value": "Body paragraph.",
                        "md": "Body paragraph.",
                        "bbox": [
                            {"x": 10, "y": 30, "w": 80, "h": 20,
                             "confidence": 0.95, "label": "text"},
                        ],
                    },
                ],
            }
        ]
    },
    "metadata": {"pages": [{"page_number": 1, "confidence": 0.97,
                            "original_orientation_angle": 0}]},
    "job_metadata": {
        "job_id": "job-abc",
        "pdf-inputTokens": 100,
        "pdf-outputTokens": 50,
        "pdf-llmTime": 1500,
    },
}


def test_adapter_parser_kind():
    assert LlamaParseAdapter.parser == ParserKind.LLAMAPARSE


def test_adapter_produces_page_count_and_indexing():
    doc = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    assert doc.page_count == 1
    assert len(doc.pages) == 1
    assert doc.pages[0].index == 0
    assert doc.pages[0].parser_extras["source_page_number"] == 1


def test_adapter_produces_blocks_with_normalized_bboxes():
    doc = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    assert len(doc.blocks) == 2
    heading, body = doc.blocks
    assert heading.role.value == "heading"
    assert heading.native_type == "heading"
    assert heading.native_label == "paragraph_title"
    assert heading.page_index == 0
    assert 0.0 <= heading.bbox.x0 <= heading.bbox.x1 <= 1.0
    assert heading.markdown == "# Title"
    assert heading.text == "Title"
    assert body.role.value == "paragraph"


def test_adapter_populates_quality_from_confidence():
    doc = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    assert doc.blocks[0].quality.confidence == 0.98
    assert doc.pages[0].quality.confidence == 0.97


def test_adapter_builds_full_text_and_markdown():
    doc = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    assert "Title" in doc.full_text
    assert "# Title" in doc.full_markdown


def test_adapter_block_ids_are_deterministic():
    doc1 = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    doc2 = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-2"),
    )
    # Same source + content -> same block IDs (ids are scoped to source, not run).
    assert [b.id for b in doc1.blocks] == [b.id for b in doc2.blocks]


def test_adapter_wires_source_and_run_ids():
    doc = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-7"),
    )
    assert doc.source_document_id == "src-1"
    assert doc.parse_run_id == "run-7"


def test_adapter_page_block_ids_in_reading_order():
    doc = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    assert doc.pages[0].block_ids == [b.id for b in doc.blocks]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/cdm/adapters/test_llamaparse_adapter.py -v -o "addopts="`
Expected: AttributeError — `LlamaParseAdapter` not defined.

- [ ] **Step 3: Implement LlamaParseAdapter**

Append to `backend/app/cdm/adapters/llamaparse.py`:

```python
import uuid

from app.cdm.models import ParsedDocument


def _mint_block_id(source_document_id: str, page_index: int, reading_order: int) -> str:
    return f"{source_document_id}:p{page_index}:b{reading_order}"


class LlamaParseAdapter:
    parser: ClassVar[ParserKind] = ParserKind.LLAMAPARSE

    def adapt(self, raw: Dict[str, Any], source_meta: SourceMeta) -> ParsedDocument:
        pages_raw: List[Dict[str, Any]] = (raw.get("items") or {}).get("pages") or []
        page_metadata_list: List[Dict[str, Any]] = (raw.get("metadata") or {}).get("pages") or []
        page_metadata_by_number = {pm.get("page_number"): pm for pm in page_metadata_list}

        all_blocks: List[Block] = []
        pages: List[Page] = []

        for page_raw in pages_raw:
            source_page_number: int = page_raw.get("page_number", 1)
            page_index = source_page_number - 1
            page_width = float(page_raw.get("width") or 1.0)
            page_height = float(page_raw.get("height") or 1.0)
            page_items = page_raw.get("items") or []

            page_blocks: List[Block] = []
            reading_order = 0

            # Recursive flatten preserving parent/child edges.
            def _walk(items: List[Dict[str, Any]], parent_id: Optional[str],
                      depth: int) -> List[str]:
                nonlocal reading_order
                child_ids_out: List[str] = []
                for item in items:
                    block_id = _mint_block_id(source_meta.source_document_id,
                                              page_index, reading_order)
                    reading_order += 1
                    native_type = str(item.get("type", "other"))
                    role = _map_role(native_type)

                    # bbox union
                    bboxes = []
                    for bb in item.get("bbox") or []:
                        bboxes.append(_pdf_points_to_normalized(
                            x=float(bb.get("x", 0.0)),
                            y=float(bb.get("y", 0.0)),
                            w=float(bb.get("w", 0.0)),
                            h=float(bb.get("h", 0.0)),
                            page_width=page_width,
                            page_height=page_height,
                        ))
                    block_bbox = _union_bbox(bboxes)

                    # confidence from first bbox entry (LlamaParse per-bbox)
                    confidence: Optional[float] = None
                    native_label: Optional[str] = None
                    for bb in item.get("bbox") or []:
                        if confidence is None and "confidence" in bb:
                            confidence = bb.get("confidence")
                        if native_label is None and bb.get("label"):
                            native_label = bb.get("label")

                    quality = Quality(confidence=confidence) if confidence is not None else None

                    parser_extras: Dict[str, Any] = {}
                    if len(bboxes) > 1:
                        parser_extras["bboxes"] = [b.model_dump() for b in bboxes]
                    # preserve start_index / end_index at item level if present
                    for bb in item.get("bbox") or []:
                        if "start_index" in bb or "end_index" in bb:
                            parser_extras.setdefault("char_range", []).append({
                                "start": bb.get("start_index"),
                                "end":   bb.get("end_index"),
                            })

                    # recurse into children first so we can collect their ids
                    child_items = item.get("items") or []
                    children_ids = _walk(child_items, parent_id=block_id, depth=depth + 1) \
                        if child_items else []

                    block = Block(
                        id=block_id,
                        role=role,
                        native_type=native_type,
                        native_label=native_label,
                        text=str(item.get("value") or ""),
                        markdown=item.get("md"),
                        page_index=page_index,
                        bbox=block_bbox,
                        reading_order=reading_order - 1,
                        depth=item.get("level") if native_type == "heading" else depth,
                        parent_id=parent_id,
                        children_ids=children_ids,
                        quality=quality,
                        parser_extras=parser_extras,
                    )
                    page_blocks.append(block)
                    child_ids_out.append(block_id)
                return child_ids_out

            _walk(page_items, parent_id=None, depth=0)
            all_blocks.extend(page_blocks)

            # page-level metadata
            pm = page_metadata_by_number.get(source_page_number, {})
            page_quality = (
                Quality(confidence=pm.get("confidence"))
                if pm.get("confidence") is not None else None
            )
            pages.append(Page(
                index=page_index,
                width=page_width,
                height=page_height,
                unit="points",
                rotation=int(pm.get("original_orientation_angle") or 0),
                block_ids=[b.id for b in page_blocks],
                quality=page_quality,
                parser_extras={"source_page_number": source_page_number},
            ))

        # Root-level text / markdown
        full_text = raw.get("text") or "\n\n".join(
            b.text for b in all_blocks if b.text
        ) or None
        full_markdown = raw.get("markdown") or "\n\n".join(
            b.markdown for b in all_blocks if b.markdown
        ) or None

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/cdm/adapters/test_llamaparse_adapter.py -v -o "addopts="`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/llamaparse.py backend/tests/cdm/adapters/test_llamaparse_adapter.py
git commit -m "feat(cdm): LlamaParseAdapter.adapt() end-to-end"
```

---

## Task 10: LlamaParse Runner (Orchestration)

Goal: a thin function that drives the live LlamaParse SDK, records a `ParseRun`, and returns `(ParseRun, ParsedDocument)`. Tested with a mocked client; no live calls.

**Files:**
- Create: `backend/app/services/parsing/__init__.py`
- Create: `backend/app/services/parsing/llamaparse_runner.py`
- Create: `backend/tests/services/parsing/__init__.py`
- Create: `backend/tests/services/parsing/test_llamaparse_runner.py`

- [ ] **Step 1: Create package inits**

Create `backend/app/services/parsing/__init__.py`:

```python
"""Parsing orchestration — drives parser adapters end-to-end."""
```

Create `backend/tests/services/parsing/__init__.py` empty.

- [ ] **Step 2: Write failing test for the runner**

Create `backend/tests/services/parsing/test_llamaparse_runner.py`:

```python
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.cdm.models import ParserKind
from app.cdm.source import ParseRunStatus, SourceDocument
from app.services.parsing.llamaparse_runner import run_llamaparse


MINIMAL_RAW = {
    "text": "Hello.",
    "markdown": "Hello.",
    "items": {"pages": [{
        "page_number": 1, "width": 100.0, "height": 200.0,
        "items": [{"type": "text", "value": "Hello.", "md": "Hello.",
                   "bbox": [{"x": 0, "y": 0, "w": 100, "h": 10, "confidence": 0.9}]}],
    }]},
    "metadata": {"pages": [{"page_number": 1, "confidence": 0.95}]},
    "job_metadata": {"job_id": "job-xyz",
                     "pdf-inputTokens": 10, "pdf-outputTokens": 5, "pdf-llmTime": 500},
}


class _FakeClient:
    def __init__(self, response: dict):
        self.parsing = SimpleNamespace(
            parse=AsyncMock(return_value=SimpleNamespace(model_dump=lambda: response))
        )


@pytest.mark.asyncio
async def test_runner_returns_run_and_doc_on_success(tmp_path):
    src = SourceDocument(
        id="src-1", sha256="a" * 64,
        filename="hello.pdf",
        created_at=datetime.now(timezone.utc),
    )
    file_path = tmp_path / "hello.pdf"
    file_path.write_bytes(b"%PDF-1.4\n")

    client = _FakeClient(MINIMAL_RAW)

    run, doc = await run_llamaparse(
        source=src,
        file_path=str(file_path),
        representation_kind="extract_rich",
        config={"tier": "agentic"},
        client=client,
    )
    assert run.parser == ParserKind.LLAMAPARSE
    assert run.status == ParseRunStatus.SUCCEEDED
    assert run.provider_refs["llamaparse_job_id"] == "job-xyz"
    assert run.input_tokens == 10
    assert run.output_tokens == 5
    assert run.duration_ms is not None and run.duration_ms >= 0
    assert doc.parse_run_id == run.id
    assert doc.source_document_id == src.id


@pytest.mark.asyncio
async def test_runner_records_failure(tmp_path):
    src = SourceDocument(
        id="src-1", sha256="a" * 64,
        created_at=datetime.now(timezone.utc),
    )
    file_path = tmp_path / "hello.pdf"
    file_path.write_bytes(b"%PDF-1.4\n")

    class _BoomClient:
        def __init__(self):
            self.parsing = SimpleNamespace(parse=AsyncMock(side_effect=RuntimeError("boom")))
    client = _BoomClient()

    with pytest.raises(RuntimeError):
        await run_llamaparse(
            source=src,
            file_path=str(file_path),
            representation_kind="extract_rich",
            config={},
            client=client,
        )
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/services/parsing/test_llamaparse_runner.py -v -o "addopts="`
Expected: ImportError.

- [ ] **Step 4: Implement the runner**

Create `backend/app/services/parsing/llamaparse_runner.py`:

```python
"""Drives LlamaParse end-to-end: SDK call → ParseRun + ParsedDocument."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.llamaparse import LlamaParseAdapter
from app.cdm.models import ParsedDocument, ParserKind
from app.cdm.source import ParseRun, ParseRunStatus, SourceDocument


async def run_llamaparse(
    *,
    source: SourceDocument,
    file_path: str,
    representation_kind: str,
    config: Dict[str, Any],
    client: Any,  # AsyncLlamaCloud or compatible
    parse_run_id: Optional[str] = None,
) -> Tuple[ParseRun, ParsedDocument]:
    """Parse `file_path` via LlamaParse and adapt to CDM.

    Raises on SDK failure. On success returns (ParseRun, ParsedDocument).
    """
    run_id = parse_run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    tier = config.get("tier", "agentic")
    expand = config.get("expand", ["markdown", "text", "items", "metadata"])

    try:
        result = await client.parsing.parse(
            upload_file=file_path,
            tier=tier,
            expand=expand,
        )
    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        # Emit a failed ParseRun via exception chain — callers persist if they want.
        failed = ParseRun(
            id=run_id,
            source_document_id=source.id,
            parser=ParserKind.LLAMAPARSE,
            representation_kind=representation_kind,
            config=config,
            status=ParseRunStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise RuntimeError(f"LlamaParse failed: {exc}") from exc

    raw = result.model_dump()
    finished_at = datetime.now(timezone.utc)
    duration_ms = int((time.perf_counter() - t0) * 1000)

    jm = raw.get("job_metadata") or {}
    run = ParseRun(
        id=run_id,
        source_document_id=source.id,
        parser=ParserKind.LLAMAPARSE,
        representation_kind=representation_kind,
        config=config,
        status=ParseRunStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        input_tokens=jm.get("pdf-inputTokens"),
        output_tokens=jm.get("pdf-outputTokens"),
        provider_refs={"llamaparse_job_id": jm.get("job_id")} if jm.get("job_id") else {},
    )

    adapter = LlamaParseAdapter()
    doc = adapter.adapt(raw, SourceMeta(
        source_document_id=source.id,
        parse_run_id=run.id,
        filename=source.filename,
        sha256=source.sha256,
    ))
    return run, doc
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/services/parsing/test_llamaparse_runner.py -v -o "addopts="`
Expected: both tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/parsing/__init__.py backend/app/services/parsing/llamaparse_runner.py backend/tests/services/parsing/__init__.py backend/tests/services/parsing/test_llamaparse_runner.py
git commit -m "feat(parsing): LlamaParse runner producing ParseRun + ParsedDocument"
```

---

## Task 11: Eval Harness — Structural Invariants

Goal: pytest suite that loads recorded LlamaParse JSON fixtures, runs the adapter, and asserts structural invariants from spec §5.1.

**Files:**
- Create: `backend/tests/cdm/eval/__init__.py`
- Create: `backend/tests/cdm/eval/conftest.py`
- Create: `backend/tests/cdm/eval/fixtures/one_page_text.json`
- Create: `backend/tests/cdm/eval/test_llamaparse_eval.py`

- [ ] **Step 1: Create fixture directory and inits**

Create `backend/tests/cdm/eval/__init__.py` empty.

Create a synthetic fixture at `backend/tests/cdm/eval/fixtures/one_page_text.json`:

```json
{
  "text": "Hello World.",
  "markdown": "# Hello World\n\nThis is a test.",
  "items": {
    "pages": [
      {
        "page_number": 1,
        "width": 612.0,
        "height": 792.0,
        "items": [
          {
            "type": "heading",
            "level": 1,
            "value": "Hello World",
            "md": "# Hello World",
            "bbox": [{"x": 72, "y": 72, "w": 200, "h": 24,
                      "confidence": 0.99, "label": "paragraph_title"}]
          },
          {
            "type": "text",
            "value": "This is a test.",
            "md": "This is a test.",
            "bbox": [{"x": 72, "y": 120, "w": 300, "h": 18,
                      "confidence": 0.97, "label": "text"}]
          }
        ]
      }
    ]
  },
  "metadata": {"pages": [{"page_number": 1, "confidence": 0.98,
                          "original_orientation_angle": 0}]},
  "job_metadata": {"job_id": "fixture-job",
                   "pdf-inputTokens": 42, "pdf-outputTokens": 21, "pdf-llmTime": 333}
}
```

Create `backend/tests/cdm/eval/conftest.py`:

```python
"""Eval harness fixtures — loads recorded LlamaParse JSON responses."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterator, Tuple

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _fixture_cases() -> Iterator[Tuple[str, Path]]:
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        if path.name.endswith(".expected.json"):
            continue
        yield path.stem, path


@pytest.fixture(params=list(_fixture_cases()), ids=lambda c: c[0])
def llamaparse_fixture(request) -> Tuple[str, Dict]:
    name, path = request.param
    with path.open("r", encoding="utf-8") as f:
        return name, json.load(f)
```

- [ ] **Step 2: Write failing invariants test**

Create `backend/tests/cdm/eval/test_llamaparse_eval.py`:

```python
from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.llamaparse import LlamaParseAdapter


def test_invariants(llamaparse_fixture):
    name, raw = llamaparse_fixture
    doc = LlamaParseAdapter().adapt(
        raw, SourceMeta(source_document_id="src-eval", parse_run_id="run-eval"),
    )

    # page_count matches pages list
    assert doc.page_count == len(doc.pages)

    # every block.page_index within range
    for b in doc.blocks:
        assert 0 <= b.page_index < doc.page_count

    # every bbox within the unit square
    for b in doc.blocks:
        if b.bbox is not None:
            assert 0.0 <= b.bbox.x0 <= b.bbox.x1 <= 1.0
            assert 0.0 <= b.bbox.y0 <= b.bbox.y1 <= 1.0

    # every block has non-empty role and native_type
    for b in doc.blocks:
        assert b.role is not None
        assert b.native_type

    # Page.block_ids reference blocks that exist
    block_ids = {b.id for b in doc.blocks}
    for p in doc.pages:
        for bid in p.block_ids:
            assert bid in block_ids

    # parent_id references point to blocks that exist
    for b in doc.blocks:
        if b.parent_id is not None:
            assert b.parent_id in block_ids

    # full text / markdown populated when content present
    if doc.blocks:
        assert doc.full_text or doc.full_markdown

    # identity wiring
    assert doc.source_document_id == "src-eval"
    assert doc.parse_run_id == "run-eval"

    # JSON round-trip
    from app.cdm.models import ParsedDocument
    restored = ParsedDocument.model_validate_json(doc.model_dump_json())
    assert restored == doc
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/cdm/eval/test_llamaparse_eval.py -v -o "addopts="`
Expected: passes against the one fixture.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/cdm/eval/
git commit -m "test(cdm): eval invariants harness with one fixture"
```

---

## Task 12: Eval Harness — Additional Fixtures

Add two more fixtures exercising tables and multi-column. Synthetic — mirror LlamaParse output shape faithfully.

**Files:**
- Create: `backend/tests/cdm/eval/fixtures/table_and_headings.json`
- Create: `backend/tests/cdm/eval/fixtures/multi_column.json`

- [ ] **Step 1: Add table_and_headings fixture**

Create `backend/tests/cdm/eval/fixtures/table_and_headings.json`:

```json
{
  "text": "Results\n\nScores table follows.\n\nName\tScore\nAlice\t95\nBob\t87",
  "markdown": "# Results\n\n## Scores table follows.\n\n| Name | Score |\n|------|-------|\n| Alice | 95 |\n| Bob | 87 |",
  "items": {
    "pages": [
      {
        "page_number": 1,
        "width": 612.0,
        "height": 792.0,
        "items": [
          {"type": "heading", "level": 1, "value": "Results", "md": "# Results",
           "bbox": [{"x": 72, "y": 72, "w": 100, "h": 24, "confidence": 0.99, "label": "paragraph_title"}]},
          {"type": "heading", "level": 2, "value": "Scores table follows.",
           "md": "## Scores table follows.",
           "bbox": [{"x": 72, "y": 110, "w": 300, "h": 18, "confidence": 0.98, "label": "paragraph_title"}]},
          {"type": "table", "value": "Name Score Alice 95 Bob 87",
           "md": "| Name | Score |\n|------|-------|\n| Alice | 95 |\n| Bob | 87 |",
           "bbox": [{"x": 72, "y": 140, "w": 400, "h": 80, "confidence": 0.94, "label": "table"}]}
        ]
      }
    ]
  },
  "metadata": {"pages": [{"page_number": 1, "confidence": 0.96, "original_orientation_angle": 0}]},
  "job_metadata": {"job_id": "fixture-job-2", "pdf-inputTokens": 60, "pdf-outputTokens": 40, "pdf-llmTime": 510}
}
```

- [ ] **Step 2: Add multi_column fixture**

Create `backend/tests/cdm/eval/fixtures/multi_column.json`:

```json
{
  "text": "Left column text.\n\nRight column text.\n\nMore left.\n\nMore right.",
  "markdown": "Left column text.\n\nRight column text.\n\nMore left.\n\nMore right.",
  "items": {
    "pages": [
      {
        "page_number": 1,
        "width": 612.0,
        "height": 792.0,
        "items": [
          {"type": "text", "value": "Left column text.", "md": "Left column text.",
           "bbox": [{"x": 72, "y": 72, "w": 234, "h": 18, "confidence": 0.95, "label": "text"}]},
          {"type": "text", "value": "Right column text.", "md": "Right column text.",
           "bbox": [{"x": 320, "y": 72, "w": 220, "h": 18, "confidence": 0.95, "label": "text"}]},
          {"type": "text", "value": "More left.", "md": "More left.",
           "bbox": [{"x": 72, "y": 100, "w": 234, "h": 18, "confidence": 0.93, "label": "text"}]},
          {"type": "text", "value": "More right.", "md": "More right.",
           "bbox": [{"x": 320, "y": 100, "w": 220, "h": 18, "confidence": 0.93, "label": "text"}]}
        ]
      }
    ]
  },
  "metadata": {"pages": [{"page_number": 1, "confidence": 0.94, "original_orientation_angle": 0}]},
  "job_metadata": {"job_id": "fixture-job-3", "pdf-inputTokens": 70, "pdf-outputTokens": 30, "pdf-llmTime": 480}
}
```

- [ ] **Step 3: Re-run eval**

Run: `cd backend && uv run python -m pytest tests/cdm/eval/test_llamaparse_eval.py -v -o "addopts="`
Expected: 3 parametrized invariant tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/cdm/eval/fixtures/table_and_headings.json backend/tests/cdm/eval/fixtures/multi_column.json
git commit -m "test(cdm): add table and multi-column eval fixtures"
```

---

## Task 13: Eval Harness — Snapshot Assertions

Goal: each fixture has an `<name>.expected.json` snapshot of the adapter output. Test diffs current output against snapshot. Snapshot is generated on first run, committed afterwards; subsequent changes require explicit regeneration.

**Files:**
- Modify: `backend/tests/cdm/eval/test_llamaparse_eval.py`
- Create: `backend/tests/cdm/eval/fixtures/one_page_text.expected.json` (generated)
- Create: `backend/tests/cdm/eval/fixtures/table_and_headings.expected.json` (generated)
- Create: `backend/tests/cdm/eval/fixtures/multi_column.expected.json` (generated)

- [ ] **Step 1: Append the snapshot test**

Append to `backend/tests/cdm/eval/test_llamaparse_eval.py`:

```python
import json
import os
from pathlib import Path

from app.cdm.models import ParsedDocument

SNAPSHOT_DIR = Path(__file__).parent / "fixtures"


def _redact_unstable(doc_dict: dict) -> dict:
    """Remove fields that differ run-to-run (UUIDs)."""
    d = dict(doc_dict)
    d["id"] = "<doc-id>"
    return d


def test_snapshot(llamaparse_fixture):
    name, raw = llamaparse_fixture
    doc = LlamaParseAdapter().adapt(
        raw, SourceMeta(source_document_id="src-eval", parse_run_id="run-eval"),
    )
    actual = _redact_unstable(json.loads(doc.model_dump_json()))

    snapshot_path = SNAPSHOT_DIR / f"{name}.expected.json"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1" or not snapshot_path.exists():
        snapshot_path.write_text(json.dumps(actual, indent=2, sort_keys=True),
                                  encoding="utf-8")
        # First-run write counts as a pass; CI should fail if file not committed.
        return

    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert actual == expected, (
        f"Snapshot mismatch for {name}. Re-run with UPDATE_SNAPSHOTS=1 "
        f"if intentional and commit the updated {snapshot_path.name}."
    )
```

- [ ] **Step 2: Generate snapshots**

Run: `cd backend && UPDATE_SNAPSHOTS=1 uv run python -m pytest tests/cdm/eval/test_llamaparse_eval.py::test_snapshot -v -o "addopts="`
Expected: passes, 3 `.expected.json` files created.

- [ ] **Step 3: Re-run without the env var to verify diffs pass**

Run: `cd backend && uv run python -m pytest tests/cdm/eval/test_llamaparse_eval.py -v -o "addopts="`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/cdm/eval/test_llamaparse_eval.py backend/tests/cdm/eval/fixtures/*.expected.json
git commit -m "test(cdm): snapshot assertions for eval fixtures"
```

---

## Task 14: Eval Harness — Metrics Recorder

Goal: writes a JSONL line per eval run with config + duration + tokens so you can grep drift later.

**Files:**
- Create: `backend/tests/cdm/eval/recorder.py`
- Modify: `backend/tests/cdm/eval/test_llamaparse_eval.py` (append recorder usage)
- Add to `backend/.gitignore` (or root): `tests/cdm/eval/metrics.jsonl`

- [ ] **Step 1: Implement the recorder**

Create `backend/tests/cdm/eval/recorder.py`:

```python
"""Append-only JSONL metrics log for eval runs."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

LOG_PATH = Path(__file__).parent / "metrics.jsonl"


def record(entry: Dict[str, Any]) -> None:
    entry_with_ts = {"ts": datetime.now(timezone.utc).isoformat(), **entry}
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry_with_ts) + "\n")
```

- [ ] **Step 2: Record metrics from the eval test**

Append to `backend/tests/cdm/eval/test_llamaparse_eval.py`:

```python
from tests.cdm.eval.recorder import record as _record_metrics


def test_record_metrics(llamaparse_fixture):
    name, raw = llamaparse_fixture
    jm = raw.get("job_metadata") or {}
    _record_metrics({
        "fixture": name,
        "parser": "llamaparse",
        "input_tokens":  jm.get("pdf-inputTokens"),
        "output_tokens": jm.get("pdf-outputTokens"),
        "duration_ms":   jm.get("pdf-llmTime"),
    })
```

- [ ] **Step 3: Add metrics log to gitignore**

Append to `backend/.gitignore` (create if missing):

```
tests/cdm/eval/metrics.jsonl
```

- [ ] **Step 4: Run all eval tests**

Run: `cd backend && uv run python -m pytest tests/cdm/eval/ -v -o "addopts="`
Expected: all pass; `metrics.jsonl` written but gitignored.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/cdm/eval/recorder.py backend/tests/cdm/eval/test_llamaparse_eval.py backend/.gitignore
git commit -m "test(cdm): metrics recorder for eval runs"
```

---

## Task 15: Full Regression + Final Verification

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && uv run python -m pytest -o "addopts="`
Expected: all existing tests still pass plus the new CDM tests.

- [ ] **Step 2: Verify final file layout matches spec §2**

Check with:

```bash
find backend/app/cdm backend/app/services/parsing backend/tests/cdm backend/tests/services/parsing -type f | sort
```

Confirm every file in the "File Structure" section at the top of this plan exists.

- [ ] **Step 3: No commit needed if regression is clean**

If regressions exist, fix them per individual failure. Do not mark the plan complete until step 1 is clean.

---

## Post-Implementation Checklist (aligned with spec §7 acceptance criteria)

1. ✅ `app/cdm/models.py`, `app/cdm/source.py`, `app/cdm/citation.py` defined with frozen Pydantic v2 types.
2. ✅ `app/cdm/adapters/base.py` defines `ParserAdapter` protocol and `SourceMeta`.
3. ✅ `app/cdm/adapters/llamaparse.py` implements the adapter per spec §4.2.
4. ✅ `app/services/parsing/llamaparse_runner.py` returns `(ParseRun, ParsedDocument)`.
5. ✅ `tests/cdm/eval/test_llamaparse_eval.py` passes 3 fixtures with structural invariants.
6. ✅ Snapshot files committed under `tests/cdm/eval/fixtures/`.
7. ✅ Existing backend tests continue to pass.
8. ✅ No persistence layer changes (deferred).
