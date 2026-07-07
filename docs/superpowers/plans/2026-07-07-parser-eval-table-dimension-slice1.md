# Parser Eval — Table Dimension (Slice 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `table` dimension to parser-eval so parsers are compared on table-extraction quality via TEDS, with ground truth bootstrapped from a trusted parser and reviewed (accept/reject) on a dedicated case page.

**Architecture:** No new DB tables — the `table` dimension reuses the existing `ParserEvalCase.expected` (JSON), `metrics` (JSON) and `details` (JSON) columns. Ground truth is `{ "tables": [ { "page": int, "html": str } ] }`. A new `score_table` scorer (registered in the existing `SCORERS` registry) emits `teds` (primary) + `table_recall`, backed by a small self-contained TEDS module using the `apted` package. Bootstrap reuses the existing `capture()` helper. On the frontend, case authoring is promoted from a modal to a dedicated page (`/evaluation/parser/cases/new` + `/evaluation/parser/cases/:caseId`) whose dimension selector forks between text authoring and the table bootstrap flow; the run comparison table becomes dimension-aware.

**Tech Stack:** Backend — Python 3.12, FastAPI (async), SQLAlchemy 2.0, Pydantic v2, Alembic, `apted` (new), stdlib `html.parser` + `difflib`. Frontend — React 18, TypeScript, Vite, shadcn/ui, react-router-dom, Vitest + React Testing Library.

## Global Constraints

- Backend data flow is **router → service → repository → database**; services raise exceptions, routers catch and map to HTTP. All DB ops are async with type hints.
- API JSON is **camelCase** (Pydantic aliases, `populate_by_name=True`); DB/Python stays snake_case. Frontend sends and receives camelCase.
- API route prefix is `/projects/{project_id}/parser-eval/...`; the frontend **route** prefix is `/evaluation/parser/...` (these differ — do not conflate).
- Backend tests run on **SQLite in-memory** (`pytest -o "addopts="`); migrations are NOT exercised by tests — the Postgres enum migration is verified only by a container restart (`alembic upgrade head`).
- Run the backend suite with: `cd backend && uv run python -m pytest -o "addopts="`.
- Frontend: `cd frontend && npm run lint && npm run build && npx vitest run`.
- One eval case per `(source_document_id, dimension)` — enforced by the existing unique constraint `uq_parser_eval_cases_source_dim`.
- Slice 1 table matching is **order-based** (i-th expected vs i-th parsed) — deliberately naive; robust matching is Slice 3. Do not add matching logic here.
- Frequent commits: one per task, after its tests pass.
- Spec: `docs/superpowers/specs/2026-07-07-parser-eval-table-dimension-design.md`. Issue: #150.

---

## File Structure

**Backend — create**
- `backend/app/services/parser_eval/table_html.py` — CDM `Table` → HTML string + CDM-table extraction helper. Used by both the scorer and bootstrap.
- `backend/app/services/parser_eval/scorers/teds.py` — `teds(html_a, html_b) -> float` + `cell_count(html) -> int`, self-contained (HTML parse → tree → APTED).
- `backend/app/services/parser_eval/scorers/table.py` — `score_table(cdm, expected) -> (metrics, details)`.
- `backend/alembic/versions/a1b2c3d4e5f6_add_table_parser_eval_dimension.py` — `ALTER TYPE ... ADD VALUE 'table'`.
- Tests: `backend/tests/services/parser_eval/test_table_html.py`, `test_teds.py`, `test_table_scorer.py`.

**Backend — modify**
- `backend/app/models/parser_eval.py` — add `table` to `ParserEvalDimension`.
- `backend/app/services/parser_eval/scorers/__init__.py` — register the `table` scorer.
- `backend/app/schemas/parser_eval.py` — `table` validation in `CaseCreate`; add `CaseDetailResponse`, `BootstrapTableRequest`, `CaseReviewUpdate`.
- `backend/app/repositories/parser_eval_repository.py` — `get_case_by_doc_dimension`, `update_case_review_status`, `delete_case`.
- `backend/app/services/parser_eval/service.py` — `get_case`, `bootstrap_table_case`, `set_case_review`, `delete_case`.
- `backend/app/routers/parser_eval.py` — bootstrap / get-detail / patch-review / delete endpoints.
- `backend/pyproject.toml` — add `apted` dependency (via `uv add apted`).

**Frontend — create**
- `frontend/src/pages/ParserEvalCasePage.tsx` — dual-mode case page: **new** (dimension fork: text authoring or table bootstrap) and **detail** (draft review + accept/reject).
- Test: `frontend/src/pages/ParserEvalCasePage.test.tsx`.

**Frontend — modify**
- `frontend/src/types/parserEval.ts` — `ParserEvalCaseDetail`, `BootstrapTableRequest`, `TableGroundTruth`.
- `frontend/src/api/parserEval.ts` — `bootstrapTableCase`, `getCase`, `updateCaseReview`, `deleteCase`.
- `frontend/src/hooks/useParserEval.ts` — `bootstrapTableCase` + `deleteCase` on `useParserEvalCases`; new `useParserEvalCase` detail hook.
- `frontend/src/components/parser-eval/ParserEvalCasesTab.tsx` — "New case" navigates to the page; rows link to detail; retire `CaseEditorDialog`.
- `frontend/src/components/parser-eval/ParserComparisonTable.tsx` — dimension-aware metric columns.
- `frontend/src/pages/ParserEvalRunDetailPage.tsx` — pass `caseDimensions` to the comparison table.
- `frontend/src/App.tsx` — routes for `evaluation/parser/cases/new` and `evaluation/parser/cases/:caseId`.
- Delete `frontend/src/components/parser-eval/CaseEditorDialog.tsx` and update `ParserEvalCasesTab.test.tsx`.

---

## Task 1: `table` dimension — enum, migration, schema validation

**Files:**
- Modify: `backend/app/models/parser_eval.py:19-20`
- Create: `backend/alembic/versions/a1b2c3d4e5f6_add_table_parser_eval_dimension.py`
- Modify: `backend/app/schemas/parser_eval.py:24-30`
- Test: `backend/tests/schemas/test_parser_eval_schema.py`, `backend/tests/models/test_parser_eval_models.py`

**Interfaces:**
- Produces: `ParserEvalDimension.table` (value `"table"`); `CaseCreate` accepts `dimension="table"` with `expected={"tables":[{"page":int,"html":str}]}` and rejects malformed table expected.

- [ ] **Step 1: Write the failing schema test**

Add to `backend/tests/schemas/test_parser_eval_schema.py`:

```python
import pytest
from pydantic import ValidationError as PydanticValidationError
from app.schemas.parser_eval import CaseCreate


def test_table_case_accepts_tables_html():
    c = CaseCreate.model_validate(
        {"sourceDocumentId": "11111111-1111-1111-1111-111111111111",
         "dimension": "table",
         "expected": {"tables": [{"page": 1, "html": "<table><tr><td>a</td></tr></table>"}]}})
    assert c.dimension == "table"
    assert c.expected["tables"][0]["html"].startswith("<table")


def test_table_case_rejects_missing_html():
    with pytest.raises(PydanticValidationError):
        CaseCreate.model_validate(
            {"sourceDocumentId": "11111111-1111-1111-1111-111111111111",
             "dimension": "table",
             "expected": {"tables": [{"page": 1}]}})


def test_table_case_rejects_non_list_tables():
    with pytest.raises(PydanticValidationError):
        CaseCreate.model_validate(
            {"sourceDocumentId": "11111111-1111-1111-1111-111111111111",
             "dimension": "table",
             "expected": {"tables": "nope"}})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/schemas/test_parser_eval_schema.py -k table -v`
Expected: FAIL — `table` currently not a valid enum value / no table validation (cases accepted or wrong error).

- [ ] **Step 3: Add the enum value**

In `backend/app/models/parser_eval.py`, change:

```python
class ParserEvalDimension(str, enum.Enum):
    text = "text"          # seam #1: table/reading_order/roles added later
```

to:

```python
class ParserEvalDimension(str, enum.Enum):
    text = "text"
    table = "table"        # seam #1: reading_order/roles added later
```

- [ ] **Step 4: Add table validation to `CaseCreate`**

In `backend/app/schemas/parser_eval.py`, extend `_validate_expected` (currently only handles `text`):

```python
    @model_validator(mode="after")
    def _validate_expected(self):
        if self.dimension == "text":
            pages = self.expected.get("pages")
            if not isinstance(pages, list) or not all(isinstance(p, str) for p in pages):
                raise ValueError("text case requires expected.pages: list[str]")
        elif self.dimension == "table":
            tables = self.expected.get("tables")
            if not isinstance(tables, list):
                raise ValueError("table case requires expected.tables: list")
            for t in tables:
                if not isinstance(t, dict) or not isinstance(t.get("html"), str):
                    raise ValueError("each expected table requires an 'html' string")
        return self
```

- [ ] **Step 5: Create the migration**

Create `backend/alembic/versions/a1b2c3d4e5f6_add_table_parser_eval_dimension.py`:

```python
"""add table parser_eval_dimension value

Revision ID: a1b2c3d4e5f6
Revises: 9f3b7c2e1a04
Create Date: 2026-07-07 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9f3b7c2e1a04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE parser_eval_dimension ADD VALUE IF NOT EXISTS 'table'")


def downgrade() -> None:
    # PostgreSQL cannot drop an enum value without recreating the type; no-op.
    pass
```

- [ ] **Step 6: Add a model test for the new value**

Add to `backend/tests/models/test_parser_eval_models.py`:

```python
def test_dimension_enum_includes_table():
    from app.models.parser_eval import ParserEvalDimension
    assert ParserEvalDimension.table.value == "table"
    assert {d.value for d in ParserEvalDimension} >= {"text", "table"}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/schemas/test_parser_eval_schema.py tests/models/test_parser_eval_models.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/parser_eval.py backend/app/schemas/parser_eval.py \
  backend/alembic/versions/a1b2c3d4e5f6_add_table_parser_eval_dimension.py \
  backend/tests/schemas/test_parser_eval_schema.py backend/tests/models/test_parser_eval_models.py
git commit -m "feat(parser-eval): add table dimension enum + expected validation + migration"
```

---

## Task 2: CDM table → HTML + extraction helper

**Files:**
- Create: `backend/app/services/parser_eval/table_html.py`
- Test: `backend/tests/services/parser_eval/test_table_html.py`

**Interfaces:**
- Consumes: `app.cdm.models.Table`, `Cell`, `Block`, `BlockRole`, `ParsedDocument`.
- Produces:
  - `table_to_html(table: Table) -> str` — returns `table.html` if present, else synthesizes `<table>` from `table.cells` honoring `is_header`/`colspan`/`rowspan`.
  - `extract_cdm_tables(cdm: ParsedDocument) -> list[tuple[int, str]]` — `(page_index, html)` for each TABLE block, sorted by `(page_index, reading_order)`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/services/parser_eval/test_table_html.py`:

```python
from app.cdm.models import Block, BlockRole, Cell, Page, ParsedDocument, Table
from app.services.parser_eval.table_html import extract_cdm_tables, table_to_html


def test_table_to_html_prefers_existing_html():
    t = Table(rows=1, cols=1, cells=[], html="<table><tr><td>x</td></tr></table>")
    assert table_to_html(t) == "<table><tr><td>x</td></tr></table>"


def test_table_to_html_synthesizes_from_cells():
    cells = [
        Cell(row=0, col=0, text="Item", is_header=True),
        Cell(row=0, col=1, text="Qty", is_header=True),
        Cell(row=1, col=0, text="Widget"),
        Cell(row=1, col=1, text="3"),
    ]
    html = table_to_html(Table(rows=2, cols=2, cells=cells))
    assert html.count("<tr>") == 2
    assert "<th>Item</th>" in html
    assert "<td>Widget</td>" in html


def test_table_to_html_encodes_colspan_and_escapes():
    cells = [Cell(row=0, col=0, colspan=2, text="A & B")]
    html = table_to_html(Table(rows=1, cols=2, cells=cells))
    assert 'colspan="2"' in html
    assert "A &amp; B" in html


def test_extract_cdm_tables_orders_by_page_then_reading_order():
    blocks = [
        Block(id="b2", role=BlockRole.TABLE, native_type="table", page_index=1,
              reading_order=0, table=Table(rows=1, cols=1, cells=[], html="<table>p1</table>")),
        Block(id="b1", role=BlockRole.TABLE, native_type="table", page_index=0,
              reading_order=5, table=Table(rows=1, cols=1, cells=[], html="<table>p0</table>")),
        Block(id="b0", role=BlockRole.TEXT, native_type="p", page_index=0, text="ignore me"),
    ]
    cdm = ParsedDocument(id="d", source_document_id="s", parse_run_id="r",
                         page_count=2, pages=[Page(index=0), Page(index=1)], blocks=blocks)
    result = extract_cdm_tables(cdm)
    assert result == [(0, "<table>p0</table>"), (1, "<table>p1</table>")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_table_html.py -v`
Expected: FAIL with "No module named app.services.parser_eval.table_html"

- [ ] **Step 3: Implement `table_html.py`**

Create `backend/app/services/parser_eval/table_html.py`:

```python
"""CDM Table → HTML, and extraction of TABLE blocks from a ParsedDocument.

Shared by the table scorer (needs HTML per parsed table) and bootstrap (needs
page + HTML per parsed table). HTML is the canonical ground-truth/comparison form.
"""
from __future__ import annotations

from html import escape

from app.cdm.models import BlockRole, ParsedDocument, Table


def table_to_html(table: Table) -> str:
    """Prefer the parser's own HTML; otherwise synthesize from structured cells."""
    if table.html:
        return table.html
    if not table.cells:
        return "<table></table>"

    rows: dict[int, list] = {}
    for cell in table.cells:
        rows.setdefault(cell.row, []).append(cell)

    parts = ["<table>"]
    for r in sorted(rows):
        parts.append("<tr>")
        for cell in sorted(rows[r], key=lambda c: c.col):
            tag = "th" if cell.is_header else "td"
            attrs = ""
            if cell.colspan and cell.colspan != 1:
                attrs += f' colspan="{cell.colspan}"'
            if cell.rowspan and cell.rowspan != 1:
                attrs += f' rowspan="{cell.rowspan}"'
            parts.append(f"<{tag}{attrs}>{escape(cell.text or '')}</{tag}>")
        parts.append("</tr>")
    parts.append("</table>")
    return "".join(parts)


def extract_cdm_tables(cdm: ParsedDocument) -> list[tuple[int, str]]:
    """Return (page_index, html) for each TABLE block, in reading order."""
    blocks = [b for b in cdm.blocks if b.role == BlockRole.TABLE and b.table is not None]
    blocks.sort(key=lambda b: (b.page_index, b.reading_order if b.reading_order is not None else 0))
    return [(b.page_index, table_to_html(b.table)) for b in blocks]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_table_html.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parser_eval/table_html.py backend/tests/services/parser_eval/test_table_html.py
git commit -m "feat(parser-eval): CDM table->html + extraction helper"
```

---

## Task 3: TEDS module (`apted`)

**Files:**
- Modify: `backend/pyproject.toml` (via `uv add apted`)
- Create: `backend/app/services/parser_eval/scorers/teds.py`
- Test: `backend/tests/services/parser_eval/test_teds.py`

**Interfaces:**
- Produces:
  - `teds(html_a: str, html_b: str) -> float` — 1.0 for identical tables, degrading toward 0.0; handles `colspan`/`rowspan`; content differences scored by normalized cell-text similarity.
  - `cell_count(html: str) -> int` — number of `<td>`/`<th>` cells (used for size-weighting).

- [ ] **Step 1: Add the dependency**

Run: `cd backend && uv add apted`
Expected: `apted` added to `pyproject.toml` dependencies and installed.

- [ ] **Step 2: Write the failing test**

Create `backend/tests/services/parser_eval/test_teds.py`:

```python
from app.services.parser_eval.scorers.teds import cell_count, teds

_T = "<table><tr><td>Item</td><td>Qty</td></tr><tr><td>Widget</td><td>3</td></tr></table>"


def test_identical_tables_score_one():
    assert teds(_T, _T) == 1.0


def test_single_cell_text_change_is_high_but_below_one():
    changed = _T.replace("<td>3</td>", "<td>8</td>")
    score = teds(_T, changed)
    assert 0.7 < score < 1.0


def test_structural_difference_scores_lower_than_content_difference():
    dropped_col = "<table><tr><td>Item</td></tr><tr><td>Widget</td></tr></table>"
    changed = _T.replace("<td>3</td>", "<td>8</td>")
    assert teds(_T, dropped_col) < teds(_T, changed)


def test_empty_vs_nonempty_scores_low():
    assert teds(_T, "<table></table>") < 0.3


def test_colspan_mismatch_penalized():
    a = "<table><tr><td colspan='2'>H</td></tr></table>"
    b = "<table><tr><td>H</td></tr></table>"
    assert teds(a, b) < 1.0


def test_cell_count():
    assert cell_count(_T) == 4
    assert cell_count("<table></table>") == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_teds.py -v`
Expected: FAIL with "No module named app.services.parser_eval.scorers.teds"

- [ ] **Step 4: Implement `teds.py`**

Create `backend/app/services/parser_eval/scorers/teds.py`:

```python
"""Tree-Edit-Distance-based Similarity (TEDS) for HTML tables.

A table is parsed into a tree (table -> tr -> td/th, each cell carrying normalized
text + colspan/rowspan). APTED computes the minimum edit distance; TEDS normalizes
it to 1 - distance / max(nodes_a, nodes_b), so 1.0 = identical, 0.0 = fully different.
Cell-text differences contribute a fractional rename cost via normalized string
similarity, so a single misread cell barely dents the score.
"""
from __future__ import annotations

import difflib
import re
from html.parser import HTMLParser

from apted import APTED, Config

_WS = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS.sub(" ", (text or "").strip()).lower()


def _to_int(value: str | None, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


class _Node:
    def __init__(self, tag: str, colspan: int = 1, rowspan: int = 1, text: str = ""):
        self.name = tag            # apted may read .name; keep it in sync with tag
        self.tag = tag
        self.colspan = colspan
        self.rowspan = rowspan
        self.text = text
        self.children: list["_Node"] = []


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.root = _Node("table")
        self._row: _Node | None = None
        self._cell: _Node | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = _Node("tr")
            self.root.children.append(self._row)
        elif tag in ("td", "th"):
            if self._row is None:
                self._row = _Node("tr")
                self.root.children.append(self._row)
            a = dict(attrs)
            self._cell = _Node(tag, _to_int(a.get("colspan"), 1), _to_int(a.get("rowspan"), 1))
            self._row.children.append(self._cell)

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._cell = None
        elif tag == "tr":
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.text += data


def _parse(html: str) -> _Node:
    parser = _TableParser()
    parser.feed(html or "")
    for row in parser.root.children:
        for cell in row.children:
            cell.text = _normalize(cell.text)
    return parser.root


def _count(node: _Node) -> int:
    return 1 + sum(_count(child) for child in node.children)


class _TedsConfig(Config):
    def children(self, node):
        return node.children

    def insert(self, node):
        return 1.0

    def delete(self, node):
        return 1.0

    def rename(self, node1, node2):
        if (node1.tag != node2.tag or node1.colspan != node2.colspan
                or node1.rowspan != node2.rowspan):
            return 1.0
        if node1.tag in ("td", "th") and node1.text != node2.text:
            return 1.0 - difflib.SequenceMatcher(None, node1.text, node2.text).ratio()
        return 0.0


def teds(html_a: str, html_b: str) -> float:
    tree_a, tree_b = _parse(html_a), _parse(html_b)
    denom = max(_count(tree_a), _count(tree_b))
    if denom == 0:
        return 1.0
    distance = APTED(tree_a, tree_b, _TedsConfig()).compute_edit_distance()
    return max(0.0, 1.0 - distance / denom)


def cell_count(html: str) -> int:
    root = _parse(html)
    return sum(len(row.children) for row in root.children)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_teds.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/services/parser_eval/scorers/teds.py \
  backend/tests/services/parser_eval/test_teds.py
git commit -m "feat(parser-eval): TEDS scorer core via apted"
```

---

## Task 4: `score_table` scorer + registration

**Files:**
- Create: `backend/app/services/parser_eval/scorers/table.py`
- Modify: `backend/app/services/parser_eval/scorers/__init__.py`
- Test: `backend/tests/services/parser_eval/test_table_scorer.py`

**Interfaces:**
- Consumes: `table_to_html`/`extract_cdm_tables` (Task 2), `teds`/`cell_count` (Task 3), `ScorerSpec` (registry).
- Produces: `score_table(cdm, expected) -> tuple[dict[str, float], dict]` emitting `teds` (primary) + `table_recall`; registered as `SCORERS["table"]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/services/parser_eval/test_table_scorer.py`:

```python
from app.cdm.models import Block, BlockRole, Cell, Page, ParsedDocument, Table
from app.services.parser_eval.scorers import get_scorer
from app.services.parser_eval.scorers.table import score_table

_HTML = "<table><tr><td>Item</td><td>Qty</td></tr><tr><td>Widget</td><td>3</td></tr></table>"


def _doc(*tables: Table) -> ParsedDocument:
    blocks = [Block(id=f"b{i}", role=BlockRole.TABLE, native_type="table",
                    page_index=0, reading_order=i, table=t) for i, t in enumerate(tables)]
    return ParsedDocument(id="d", source_document_id="s", parse_run_id="r",
                          page_count=1, pages=[Page(index=0)], blocks=blocks)


def test_exact_match_scores_one():
    doc = _doc(Table(rows=2, cols=2, cells=[], html=_HTML))
    metrics, details = score_table(doc, {"tables": [{"page": 1, "html": _HTML}]})
    assert metrics["teds"] == 1.0
    assert metrics["table_recall"] == 1.0
    assert details["expected_count"] == 1
    assert details["parsed_count"] == 1


def test_dropped_column_lowers_teds():
    dropped = "<table><tr><td>Item</td></tr><tr><td>Widget</td></tr></table>"
    doc = _doc(Table(rows=2, cols=1, cells=[], html=dropped))
    metrics, _ = score_table(doc, {"tables": [{"page": 1, "html": _HTML}]})
    assert metrics["teds"] < 1.0


def test_missing_table_reduces_recall():
    doc = _doc()  # parser found no tables
    metrics, details = score_table(doc, {"tables": [{"page": 1, "html": _HTML}]})
    assert metrics["table_recall"] == 0.0
    assert metrics["teds"] == 0.0
    assert details["parsed_count"] == 0


def test_cells_fallback_when_parser_gives_no_html():
    cells = [Cell(row=0, col=0, text="Item", is_header=True),
             Cell(row=0, col=1, text="Qty", is_header=True),
             Cell(row=1, col=0, text="Widget"), Cell(row=1, col=1, text="3")]
    doc = _doc(Table(rows=2, cols=2, cells=cells))  # html=None -> synthesized
    expected_html = "<table><tr><th>Item</th><th>Qty</th></tr><tr><td>Widget</td><td>3</td></tr></table>"
    metrics, _ = score_table(doc, {"tables": [{"page": 1, "html": expected_html}]})
    assert metrics["teds"] == 1.0


def test_no_tables_expected_or_parsed_is_perfect():
    metrics, _ = score_table(_doc(), {"tables": []})
    assert metrics["teds"] == 1.0
    assert metrics["table_recall"] == 1.0


def test_registered_in_scorers():
    spec = get_scorer("table")
    assert spec.primary == "teds"
    assert set(spec.emits) == {"teds", "table_recall"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_table_scorer.py -v`
Expected: FAIL — module missing / `get_scorer("table")` KeyError.

- [ ] **Step 3: Implement `table.py`**

Create `backend/app/services/parser_eval/scorers/table.py`:

```python
"""Table-structure+content scorer — compares parsed tables to expected tables via TEDS.

Slice 1 matches tables by order (i-th expected vs i-th parsed); an unmatched table on
either side scores TEDS 0. Aggregate TEDS is size-weighted by the larger table's cell
count so big tables dominate. Robust position-based matching is Slice 3.
"""
from __future__ import annotations

from typing import Any

from app.cdm.models import ParsedDocument
from app.services.parser_eval.scorers.teds import cell_count, teds
from app.services.parser_eval.table_html import extract_cdm_tables


def score_table(cdm: ParsedDocument, expected: dict[str, Any]) -> tuple[dict[str, float], dict]:
    expected_html = [t.get("html", "") for t in expected.get("tables", [])]
    parsed_html = [html for _page, html in extract_cdm_tables(cdm)]

    n = max(len(expected_html), len(parsed_html))
    per_table: list[dict[str, Any]] = []
    weighted_sum = 0.0
    total_weight = 0.0
    for i in range(n):
        exp = expected_html[i] if i < len(expected_html) else None
        par = parsed_html[i] if i < len(parsed_html) else None
        score = teds(exp, par) if (exp is not None and par is not None) else 0.0
        weight = max(cell_count(exp) if exp else 0, cell_count(par) if par else 0, 1)
        weighted_sum += score * weight
        total_weight += weight
        per_table.append({"index": i, "teds": score,
                          "expected_present": exp is not None, "parsed_present": par is not None})

    teds_metric = weighted_sum / total_weight if total_weight else 1.0

    expected_count = len(expected_html)
    if expected_count == 0:
        recall = 1.0 if len(parsed_html) == 0 else 0.0
    else:
        recall = min(len(parsed_html), expected_count) / expected_count

    metrics = {"teds": teds_metric, "table_recall": recall}
    details = {"per_table": per_table,
               "expected_count": expected_count, "parsed_count": len(parsed_html)}
    return metrics, details
```

- [ ] **Step 4: Register the scorer**

In `backend/app/services/parser_eval/scorers/__init__.py`, add the import and registry entry:

```python
from app.services.parser_eval.scorers.table import score_table
from app.services.parser_eval.scorers.text import score_text
```

```python
SCORERS: dict[str, ScorerSpec] = {
    "text": ScorerSpec(fn=score_text, emits=("similarity", "omission", "hallucination"),
                       primary="similarity"),
    "table": ScorerSpec(fn=score_table, emits=("teds", "table_recall"), primary="teds"),
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_table_scorer.py tests/services/parser_eval/test_registry.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/parser_eval/scorers/table.py backend/app/services/parser_eval/scorers/__init__.py \
  backend/tests/services/parser_eval/test_table_scorer.py
git commit -m "feat(parser-eval): score_table scorer (teds + table_recall)"
```

---

## Task 5: Repository methods — lookup, review-status, delete

**Files:**
- Modify: `backend/app/repositories/parser_eval_repository.py`
- Test: `backend/tests/repositories/test_parser_eval_repository.py`

**Interfaces:**
- Produces:
  - `get_case_by_doc_dimension(source_document_id, dimension) -> ParserEvalCase | None`
  - `update_case_review_status(case_id, review_status) -> ParserEvalCase | None`
  - `delete_case(case_id) -> bool`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/repositories/test_parser_eval_repository.py` (follow the file's existing fixtures for `repo`, `project_id`, `user_id`, `source_document_id`; mirror how existing tests create a case):

```python
import pytest
from app.models.parser_eval import ParserEvalDimension, ParserEvalReviewStatus


@pytest.mark.asyncio
async def test_get_case_by_doc_dimension_and_review_and_delete(repo, project_id, user_id, source_document_id):
    case = await repo.create_case(
        project_id, source_document_id, ParserEvalDimension.table,
        {"tables": []}, user_id)

    found = await repo.get_case_by_doc_dimension(source_document_id, ParserEvalDimension.table)
    assert found is not None and found.id == case.id

    updated = await repo.update_case_review_status(case.id, ParserEvalReviewStatus.verified)
    assert updated.review_status == ParserEvalReviewStatus.verified

    assert await repo.delete_case(case.id) is True
    assert await repo.get_case(case.id) is None
    assert await repo.delete_case(case.id) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/repositories/test_parser_eval_repository.py -k by_doc_dimension -v`
Expected: FAIL with `AttributeError: 'ParserEvalRepository' object has no attribute 'get_case_by_doc_dimension'`

- [ ] **Step 3: Implement the repo methods**

In `backend/app/repositories/parser_eval_repository.py`, add to the `# --- cases ---` section (after `get_cases_by_ids`):

```python
    async def get_case_by_doc_dimension(self, source_document_id: UUID,
                                        dimension: ParserEvalDimension) -> ParserEvalCase | None:
        res = await self.session.execute(
            select(ParserEvalCase).where(
                ParserEvalCase.source_document_id == source_document_id,
                ParserEvalCase.dimension == dimension))
        return res.scalar_one_or_none()

    async def update_case_review_status(self, case_id: UUID,
                                        review_status: ParserEvalReviewStatus
                                        ) -> ParserEvalCase | None:
        case = await self.get_case(case_id)
        if case is None:
            return None
        case.review_status = review_status
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def delete_case(self, case_id: UUID) -> bool:
        case = await self.get_case(case_id)
        if case is None:
            return False
        await self.session.delete(case)
        await self.session.commit()
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/repositories/test_parser_eval_repository.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/parser_eval_repository.py backend/tests/repositories/test_parser_eval_repository.py
git commit -m "feat(parser-eval): repo lookup/review-status/delete for cases"
```

---

## Task 6: Schemas + service — bootstrap, get detail, review, delete

**Files:**
- Modify: `backend/app/schemas/parser_eval.py`
- Modify: `backend/app/services/parser_eval/service.py`
- Test: `backend/tests/services/parser_eval/test_service.py`

**Interfaces:**
- Consumes: `capture` (existing), `extract_cdm_tables` (Task 2), repo methods (Task 5), `ConflictError`/`NotFoundError`/`ValidationError` from `app.services.exceptions`.
- Produces (schemas): `CaseDetailResponse` (adds `expected: dict` to case fields), `BootstrapTableRequest {sourceDocumentId, adapter, config}`, `CaseReviewUpdate {reviewStatus}`.
- Produces (service): `get_case(case_id) -> CaseDetailResponse`; `bootstrap_table_case(project_id, user_id, data) -> CaseDetailResponse`; `set_case_review(case_id, review_status) -> CaseDetailResponse`; `delete_case(case_id) -> None`.

- [ ] **Step 1: Add the schemas**

In `backend/app/schemas/parser_eval.py`, after `CaseResponse`, add:

```python
class CaseDetailResponse(BaseModel):
    id: UUID
    source_document_id: UUID = Field(..., alias="sourceDocumentId")
    dimension: str
    expected: dict
    source_method: str = Field(..., alias="sourceMethod")
    review_status: str = Field(..., alias="reviewStatus")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = _CAMEL_ORM


class BootstrapTableRequest(BaseModel):
    source_document_id: UUID = Field(..., alias="sourceDocumentId")
    adapter: str
    config: dict = {}

    model_config = _CAMEL

    @field_validator("adapter")
    @classmethod
    def _validate_adapter(cls, value: str) -> str:
        valid = {p.value for p in ParserKind}
        if value not in valid:
            raise ValueError(f"Invalid adapter '{value}'. Valid: {sorted(valid)}")
        return value


class CaseReviewUpdate(BaseModel):
    review_status: str = Field(..., alias="reviewStatus")

    model_config = _CAMEL

    @field_validator("review_status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        if value not in ("draft", "verified"):
            raise ValueError("reviewStatus must be 'draft' or 'verified'")
        return value
```

- [ ] **Step 2: Write the failing service test**

Add to `backend/tests/services/parser_eval/test_service.py`. This mirrors the file's existing async service setup; `capture` is patched so no real parser runs.

```python
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.cdm.models import Block, BlockRole, Page, ParsedDocument, Table
from app.schemas.parser_eval import BootstrapTableRequest
from app.services.exceptions import ConflictError, NotFoundError


def _cdm_with_one_table():
    html = "<table><tr><td>a</td></tr></table>"
    return ParsedDocument(
        id="d", source_document_id="s", parse_run_id="r", page_count=1,
        pages=[Page(index=0)],
        blocks=[Block(id="b0", role=BlockRole.TABLE, native_type="table",
                      page_index=0, reading_order=0, table=Table(rows=1, cols=1, cells=[], html=html))])


@pytest.mark.asyncio
async def test_bootstrap_table_case_creates_draft(service, project_id, user_id, source_document_id):
    req = BootstrapTableRequest.model_validate(
        {"sourceDocumentId": str(source_document_id), "adapter": "docling", "config": {}})
    with patch("app.services.parser_eval.service.capture",
               new=AsyncMock(return_value=(_cdm_with_one_table(), {}, 100))):
        detail = await service.bootstrap_table_case(project_id, user_id, req)
    assert detail.dimension == "table"
    assert detail.source_method == "bootstrapped"
    assert detail.review_status == "draft"
    assert detail.expected["tables"][0]["html"] == "<table><tr><td>a</td></tr></table>"
    assert detail.expected["tables"][0]["page"] == 1


@pytest.mark.asyncio
async def test_bootstrap_duplicate_raises_conflict(service, project_id, user_id, source_document_id):
    req = BootstrapTableRequest.model_validate(
        {"sourceDocumentId": str(source_document_id), "adapter": "docling", "config": {}})
    with patch("app.services.parser_eval.service.capture",
               new=AsyncMock(return_value=(_cdm_with_one_table(), {}, 100))):
        await service.bootstrap_table_case(project_id, user_id, req)
        with pytest.raises(ConflictError):
            await service.bootstrap_table_case(project_id, user_id, req)


@pytest.mark.asyncio
async def test_set_case_review_and_delete(service, project_id, user_id, source_document_id):
    req = BootstrapTableRequest.model_validate(
        {"sourceDocumentId": str(source_document_id), "adapter": "docling", "config": {}})
    with patch("app.services.parser_eval.service.capture",
               new=AsyncMock(return_value=(_cdm_with_one_table(), {}, 100))):
        detail = await service.bootstrap_table_case(project_id, user_id, req)
    verified = await service.set_case_review(detail.id, "verified")
    assert verified.review_status == "verified"
    await service.delete_case(detail.id)
    with pytest.raises(NotFoundError):
        await service.get_case(detail.id)
```

> **Note for the implementer:** if `test_service.py` has no `service`/`project_id`/`user_id`/`source_document_id` fixtures, add them following the pattern in `tests/routers/test_parser_eval_router.py` / existing service tests (construct `ParserEvalService` with a `ParserEvalRepository(test_db)`, a real `SourceDocumentRepository`, and stub `parsing_service`/`storage`). Create a real `source_documents` row so the FK resolves.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_service.py -k "bootstrap or review" -v`
Expected: FAIL — `AttributeError: 'ParserEvalService' object has no attribute 'bootstrap_table_case'`

- [ ] **Step 4: Implement the service methods**

In `backend/app/services/parser_eval/service.py`, extend imports:

```python
from app.models.parser_eval import (
    ParserEvalDimension, ParserEvalSourceMethod, ParserEvalReviewStatus,
)
from app.schemas.parser_eval import (
    BootstrapTableRequest, CaseCreate, CaseDetailResponse, CaseResponse,
    DatasetCreate, DatasetResponse, RunCreate, RunResponse, ResultResponse,
)
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
from app.services.parser_eval.capture import capture
from app.services.parser_eval.table_html import extract_cdm_tables
```

Add these methods to the `# --- cases ---` section:

```python
    async def get_case(self, case_id: UUID) -> CaseDetailResponse:
        case = await self.repo.get_case(case_id)
        if case is None:
            raise NotFoundError(f"Parser eval case {case_id} not found")
        return CaseDetailResponse.model_validate(case)

    async def bootstrap_table_case(self, project_id: UUID, user_id: UUID,
                                   data: BootstrapTableRequest) -> CaseDetailResponse:
        source = await self.source_doc_repo.get(data.source_document_id)
        if source is None:
            raise NotFoundError(f"Source document {data.source_document_id} not found")
        existing = await self.repo.get_case_by_doc_dimension(
            data.source_document_id, ParserEvalDimension.table)
        if existing is not None:
            raise ConflictError("A table case already exists for this document")

        cdm, _cost, _latency = await capture(
            self.parsing_service, self.storage,
            source_document_id=str(data.source_document_id), storage_uri=source.storage_uri,
            filename=source.filename, mime_type=source.mime_type, parser=data.adapter,
            project_id=project_id, config=data.config or {})
        if cdm is None:
            raise ValidationError("Bootstrap parse failed — the chosen parser could not parse this document")

        expected = {"tables": [{"page": page_index + 1, "html": html}
                               for page_index, html in extract_cdm_tables(cdm)]}
        case = await self.repo.create_case(
            project_id, data.source_document_id, ParserEvalDimension.table, expected, user_id,
            source_method=ParserEvalSourceMethod.bootstrapped,
            review_status=ParserEvalReviewStatus.draft)
        return CaseDetailResponse.model_validate(case)

    async def set_case_review(self, case_id: UUID, review_status: str) -> CaseDetailResponse:
        case = await self.repo.update_case_review_status(
            case_id, ParserEvalReviewStatus(review_status))
        if case is None:
            raise NotFoundError(f"Parser eval case {case_id} not found")
        return CaseDetailResponse.model_validate(case)

    async def delete_case(self, case_id: UUID) -> None:
        if not await self.repo.delete_case(case_id):
            raise NotFoundError(f"Parser eval case {case_id} not found")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/parser_eval.py backend/app/services/parser_eval/service.py \
  backend/tests/services/parser_eval/test_service.py
git commit -m "feat(parser-eval): bootstrap/get/review/delete case service + schemas"
```

---

## Task 7: Router endpoints

**Files:**
- Modify: `backend/app/routers/parser_eval.py`
- Test: `backend/tests/routers/test_parser_eval_router.py`

**Interfaces:**
- Produces routes (all under `/projects/{project_id}/parser-eval`):
  - `POST /cases/bootstrap-table` → `CaseDetailResponse` (409 on duplicate, 404 on missing doc, 400 on parse failure)
  - `GET /cases/{case_id}` → `CaseDetailResponse` (404)
  - `PATCH /cases/{case_id}` (`CaseReviewUpdate`) → `CaseDetailResponse` (404)
  - `DELETE /cases/{case_id}` → 204 (404)

> **Ordering:** declare `cases/bootstrap-table` BEFORE `cases/{case_id}`, or the `{case_id}` UUID path would capture the literal `bootstrap-table` and 422. Put the static route first.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/routers/test_parser_eval_router.py` (reuse the file's existing `client`, auth override, and project/document setup helpers; mirror how `test_create_case`-style tests post):

```python
from unittest.mock import AsyncMock, patch

from app.cdm.models import Block, BlockRole, Page, ParsedDocument, Table


def _cdm_one_table():
    html = "<table><tr><td>a</td></tr></table>"
    return ParsedDocument(id="d", source_document_id="s", parse_run_id="r", page_count=1,
                          pages=[Page(index=0)],
                          blocks=[Block(id="b0", role=BlockRole.TABLE, native_type="table",
                                        page_index=0, reading_order=0,
                                        table=Table(rows=1, cols=1, cells=[], html=html))])


@pytest.mark.asyncio
async def test_bootstrap_get_review_delete_flow(client, project, source_document):
    with patch("app.services.parser_eval.service.capture",
               new=AsyncMock(return_value=(_cdm_one_table(), {}, 100))):
        r = await client.post(
            f"/projects/{project.id}/parser-eval/cases/bootstrap-table",
            json={"sourceDocumentId": str(source_document.id), "adapter": "docling", "config": {}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dimension"] == "table"
    assert body["reviewStatus"] == "draft"
    assert body["expected"]["tables"][0]["html"].startswith("<table")
    case_id = body["id"]

    g = await client.get(f"/projects/{project.id}/parser-eval/cases/{case_id}")
    assert g.status_code == 200
    assert g.json()["expected"]["tables"][0]["page"] == 1

    p = await client.patch(f"/projects/{project.id}/parser-eval/cases/{case_id}",
                           json={"reviewStatus": "verified"})
    assert p.status_code == 200
    assert p.json()["reviewStatus"] == "verified"

    d = await client.delete(f"/projects/{project.id}/parser-eval/cases/{case_id}")
    assert d.status_code == 204
    assert (await client.get(f"/projects/{project.id}/parser-eval/cases/{case_id}")).status_code == 404


@pytest.mark.asyncio
async def test_bootstrap_duplicate_returns_409(client, project, source_document):
    with patch("app.services.parser_eval.service.capture",
               new=AsyncMock(return_value=(_cdm_one_table(), {}, 100))):
        first = await client.post(
            f"/projects/{project.id}/parser-eval/cases/bootstrap-table",
            json={"sourceDocumentId": str(source_document.id), "adapter": "docling", "config": {}})
        assert first.status_code == 200
        dup = await client.post(
            f"/projects/{project.id}/parser-eval/cases/bootstrap-table",
            json={"sourceDocumentId": str(source_document.id), "adapter": "docling", "config": {}})
    assert dup.status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/routers/test_parser_eval_router.py -k "bootstrap" -v`
Expected: FAIL (404 — routes not defined)

- [ ] **Step 3: Implement the routes**

In `backend/app/routers/parser_eval.py`, extend imports:

```python
from app.schemas.parser_eval import (
    BootstrapTableRequest, CaseCreate, CaseDetailResponse, CaseResponse, CaseReviewUpdate,
    DatasetCreate, DatasetResponse, RunCreate, RunResponse, ResultResponse,
)
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
```

Add these routes immediately after the existing `list_cases` route (static `bootstrap-table` first, then the `{case_id}` routes):

```python
@router.post("/projects/{project_id}/parser-eval/cases/bootstrap-table",
             response_model=CaseDetailResponse)
async def bootstrap_table_case(
    project_id: UUID,
    data: BootstrapTableRequest,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.bootstrap_table_case(project_id, current_user.id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/projects/{project_id}/parser-eval/cases/{case_id}",
            response_model=CaseDetailResponse)
async def get_case(
    project_id: UUID,
    case_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.get_case(case_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/projects/{project_id}/parser-eval/cases/{case_id}",
              response_model=CaseDetailResponse)
async def update_case_review(
    project_id: UUID,
    case_id: UUID,
    data: CaseReviewUpdate,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.set_case_review(case_id, data.review_status)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/projects/{project_id}/parser-eval/cases/{case_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    project_id: UUID,
    case_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        await service.delete_case(case_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/routers/test_parser_eval_router.py -v`
Expected: PASS

- [ ] **Step 5: Run the full parser-eval backend suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/ -k parser_eval -v`
Expected: PASS (all parser-eval tests green)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/parser_eval.py backend/tests/routers/test_parser_eval_router.py
git commit -m "feat(parser-eval): bootstrap/get/review/delete case routes"
```

---

## Task 8: Frontend types + API client

**Files:**
- Modify: `frontend/src/types/parserEval.ts`
- Modify: `frontend/src/api/parserEval.ts`

**Interfaces:**
- Produces (types): `ParserEvalCaseDetail`, `BootstrapTableRequest`, `TableGroundTruth`.
- Produces (api): `bootstrapTableCase`, `getCase`, `updateCaseReview`, `deleteCase`.

- [ ] **Step 1: Add the types**

In `frontend/src/types/parserEval.ts`, add:

```typescript
export interface ParserEvalCaseDetail extends ParserEvalCase {
  expected: Record<string, unknown>
}

export interface TableGroundTruth {
  tables: { page: number; html: string }[]
}

export interface BootstrapTableRequest {
  sourceDocumentId: string
  adapter: string
  config: Record<string, unknown>
}
```

- [ ] **Step 2: Add the API functions**

In `frontend/src/api/parserEval.ts`, extend the import and add functions:

```typescript
import type {
  ParserEvalCase, ParserEvalCaseDetail, ParserEvalRun, ParserEvalResult,
  CreateCaseRequest, CreateRunRequest, BootstrapTableRequest,
} from '@/types/parserEval'
```

```typescript
export async function bootstrapTableCase(
  projectId: string, data: BootstrapTableRequest,
): Promise<ParserEvalCaseDetail> {
  const r = await apiClient.post<ParserEvalCaseDetail>(
    `/projects/${projectId}/parser-eval/cases/bootstrap-table`, data)
  return r.data
}

export async function getCase(projectId: string, caseId: string): Promise<ParserEvalCaseDetail> {
  const r = await apiClient.get<ParserEvalCaseDetail>(
    `/projects/${projectId}/parser-eval/cases/${caseId}`)
  return r.data
}

export async function updateCaseReview(
  projectId: string, caseId: string, reviewStatus: 'draft' | 'verified',
): Promise<ParserEvalCaseDetail> {
  const r = await apiClient.patch<ParserEvalCaseDetail>(
    `/projects/${projectId}/parser-eval/cases/${caseId}`, { reviewStatus })
  return r.data
}

export async function deleteCase(projectId: string, caseId: string): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/parser-eval/cases/${caseId}`)
}
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (no type errors)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/parserEval.ts frontend/src/api/parserEval.ts
git commit -m "feat(parser-eval-fe): case-detail types + bootstrap/review/delete api"
```

---

## Task 9: Frontend hooks

**Files:**
- Modify: `frontend/src/hooks/useParserEval.ts`

**Interfaces:**
- Consumes: api functions from Task 8.
- Produces:
  - `useParserEvalCases` also returns `bootstrapTableCase(data)` and `deleteCase(caseId)`.
  - New `useParserEvalCase(projectId, caseId)` → `{ caseDetail, isLoading, error, verify, reject }`.

- [ ] **Step 1: Extend `useParserEvalCases` and add `useParserEvalCase`**

In `frontend/src/hooks/useParserEval.ts`, extend imports:

```typescript
import type {
  ParserEvalCase, ParserEvalCaseDetail, ParserEvalRun, ParserEvalResult,
  CreateCaseRequest, CreateRunRequest, BootstrapTableRequest,
} from '@/types/parserEval'
```

Inside `useParserEvalCases`, add (before the `return`):

```typescript
  const bootstrapTableCase = useCallback(
    async (data: BootstrapTableRequest): Promise<ParserEvalCaseDetail> => {
      if (!projectId) throw new Error('No project selected')
      const created = await api.bootstrapTableCase(projectId, data)
      setCases((prev) => [created, ...prev])
      return created
    }, [projectId])

  const deleteCase = useCallback(async (caseId: string): Promise<void> => {
    if (!projectId) throw new Error('No project selected')
    await api.deleteCase(projectId, caseId)
    setCases((prev) => prev.filter((c) => c.id !== caseId))
  }, [projectId])
```

and update the return to include them: `return { cases, isLoading, error, fetchCases, createCase, bootstrapTableCase, deleteCase }`.

Add the detail hook at the end of the file:

```typescript
export function useParserEvalCase(projectId: string | null, caseId: string | null) {
  const [caseDetail, setCaseDetail] = useState<ParserEvalCaseDetail | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!projectId || !caseId) { setCaseDetail(null); return }
    setIsLoading(true); setError(null)
    try {
      setCaseDetail(await api.getCase(projectId, caseId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load case')
    } finally {
      setIsLoading(false)
    }
  }, [projectId, caseId])

  useEffect(() => { load() }, [load])

  const verify = useCallback(async () => {
    if (!projectId || !caseId) return
    setCaseDetail(await api.updateCaseReview(projectId, caseId, 'verified'))
  }, [projectId, caseId])

  const reject = useCallback(async () => {
    if (!projectId || !caseId) return
    await api.deleteCase(projectId, caseId)
  }, [projectId, caseId])

  return { caseDetail, isLoading, error, verify, reject }
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useParserEval.ts
git commit -m "feat(parser-eval-fe): bootstrap/delete + useParserEvalCase hook"
```

---

## Task 10: Case page — authoring (new mode) + routing + retire dialog

**Files:**
- Create: `frontend/src/pages/ParserEvalCasePage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/parser-eval/ParserEvalCasesTab.tsx`
- Delete: `frontend/src/components/parser-eval/CaseEditorDialog.tsx`
- Test: `frontend/src/pages/ParserEvalCasePage.test.tsx`, update `frontend/src/components/parser-eval/ParserEvalCasesTab.test.tsx`

**Interfaces:**
- Consumes: `useParserEvalCases` (`createCase`, `bootstrapTableCase`), `useParserEvalCase` (Task 9), `ParseMethodSelector` + `PARSER_REGISTRY`, `useSourceDocuments`, `useProject`.
- Produces: route component `ParserEvalCasePage` handling `/evaluation/parser/cases/new` (authoring) and `/evaluation/parser/cases/:caseId` (detail — filled in Task 11).

- [ ] **Step 1: Write the failing page test**

Create `frontend/src/pages/ParserEvalCasePage.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import ParserEvalCasePage from './ParserEvalCasePage'

vi.mock('@/contexts/ProjectContext', () => ({
  useProject: () => ({ currentProject: { id: 'p1' } }),
}))
vi.mock('@/hooks/useSourceDocuments', () => ({
  useSourceDocuments: () => ({ sourceDocuments: [{ id: 'doc1', filename: 'a.pdf' }] }),
}))
vi.mock('@/hooks/useParserEval', () => ({
  useParserEvalCases: () => ({ createCase: vi.fn(), bootstrapTableCase: vi.fn() }),
  useParserEvalCase: () => ({ caseDetail: null, isLoading: false, verify: vi.fn(), reject: vi.fn() }),
}))

describe('ParserEvalCasePage (new mode)', () => {
  it('shows the dimension selector when authoring a new case', () => {
    render(
      <MemoryRouter initialEntries={['/evaluation/parser/cases/new']}>
        <Routes><Route path="/evaluation/parser/cases/new" element={<ParserEvalCasePage />} /></Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText(/New case/i)).toBeInTheDocument()
    expect(screen.getByText(/Dimension/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/ParserEvalCasePage.test.tsx`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `ParserEvalCasePage` (new-mode authoring)**

Create `frontend/src/pages/ParserEvalCasePage.tsx`. (Detail/review mode is stubbed here and completed in Task 11.)

```tsx
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useParserEvalCases } from '@/hooks/useParserEval'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import { ParseMethodSelector, PARSER_REGISTRY } from '@/components/documents/ParseMethodSelector'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import type { ParseConfig } from '@/types/parsing'
import { CaseDetailView } from '@/components/parser-eval/CaseDetailView'

const DEFAULT_ADAPTER = 'docling'

export default function ParserEvalCasePage(): JSX.Element {
  const { caseId } = useParams<{ caseId: string }>()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null
  const navigate = useNavigate()

  if (caseId) return <CaseDetailView projectId={projectId} caseId={caseId} />

  return <NewCaseForm projectId={projectId} onDone={(id) => navigate(`/evaluation/parser/cases/${id}`)} />
}

function NewCaseForm({ projectId, onDone }: { projectId: string | null; onDone: (id: string) => void }) {
  const { sourceDocuments } = useSourceDocuments()
  const { createCase, bootstrapTableCase } = useParserEvalCases(projectId)
  const [dimension, setDimension] = useState<'text' | 'table'>('text')
  const [sourceDocumentId, setSourceDocumentId] = useState('')
  const [pages, setPages] = useState<string[]>([''])
  const [adapter, setAdapter] = useState(DEFAULT_ADAPTER)
  const [config, setConfig] = useState<ParseConfig>(PARSER_REGISTRY[DEFAULT_ADAPTER]?.defaultConfig ?? {})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canSubmit = dimension === 'text'
    ? sourceDocumentId !== '' && pages.some((p) => p.trim() !== '')
    : sourceDocumentId !== ''

  const handleSubmit = async () => {
    setSubmitting(true); setError(null)
    try {
      if (dimension === 'text') {
        const created = await createCase({ sourceDocumentId, dimension: 'text', expected: { pages } })
        onDone(created.id)
      } else {
        const created = await bootstrapTableCase({ sourceDocumentId, adapter, config })
        onDone(created.id)
      }
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      setError(status === 409 ? `A ${dimension} case already exists for this document.`
        : status === 400 ? 'The chosen parser could not parse this document.'
        : 'Failed to save case.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <button onClick={() => history.back()}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Back
      </button>
      <h1 className="text-2xl font-bold">New case</h1>

      <div>
        <Label>Source document</Label>
        <Select value={sourceDocumentId} onValueChange={setSourceDocumentId}>
          <SelectTrigger><SelectValue placeholder="Select a document" /></SelectTrigger>
          <SelectContent>
            {sourceDocuments.map((d) => (
              <SelectItem key={d.id} value={d.id}>{d.filename ?? d.id}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <Label>Dimension</Label>
        <Select value={dimension} onValueChange={(v) => setDimension(v as 'text' | 'table')}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="text">Text faithfulness</SelectItem>
            <SelectItem value="table">Table extraction</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {dimension === 'text' ? (
        <div className="space-y-2">
          <Label>Ground truth (per page)</Label>
          {pages.map((page, i) => (
            <div key={i} className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Page {i + 1}</span>
                {pages.length > 1 && (
                  <Button variant="ghost" size="sm"
                    onClick={() => setPages((p) => p.filter((_, idx) => idx !== i))}>Remove</Button>
                )}
              </div>
              <Textarea value={page} rows={4}
                onChange={(e) => setPages((p) => p.map((v, idx) => (idx === i ? e.target.value : v)))}
                placeholder={`Correct readable text for page ${i + 1}`} />
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={() => setPages((p) => [...p, ''])}>Add page</Button>
        </div>
      ) : (
        <div className="space-y-2">
          <Label>Bootstrap ground truth from a trusted parser</Label>
          <p className="text-xs text-muted-foreground">
            Run a parser you trust; its extracted tables become a draft you review next.
          </p>
          <div className="rounded-md border p-3">
            <ParseMethodSelector
              compact
              parserType={adapter}
              config={config}
              onParserTypeChange={setAdapter}
              onConfigChange={setConfig}
            />
          </div>
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button disabled={!canSubmit || submitting} onClick={handleSubmit}>
        {submitting ? 'Saving…' : dimension === 'table' ? 'Bootstrap draft' : 'Create case'}
      </Button>
    </div>
  )
}
```

- [ ] **Step 4: Add a placeholder `CaseDetailView` (completed in Task 11)**

Create `frontend/src/components/parser-eval/CaseDetailView.tsx` with a minimal stub so the page compiles now:

```tsx
export function CaseDetailView({ projectId, caseId }: { projectId: string | null; caseId: string }) {
  return <div data-testid="case-detail" data-project={projectId ?? ''} data-case={caseId} />
}
```

- [ ] **Step 5: Wire the routes**

In `frontend/src/App.tsx`, import the page (near the other parser-eval imports at lines 20-21):

```tsx
import ParserEvalCasePage from './pages/ParserEvalCasePage'
```

Add two route objects next to the existing `evaluation/parser` routes (after the `evaluation/parser/runs/:runId` object, ~line 201):

```tsx
          {
            path: 'evaluation/parser/cases/new',
            element: <ParserEvalCasePage />,
            handle: { breadcrumb: 'New Case' },
          },
          {
            path: 'evaluation/parser/cases/:caseId',
            element: <ParserEvalCasePage />,
            handle: { breadcrumb: 'Case Detail' },
          },
```

- [ ] **Step 6: Point the Cases tab at the page and retire the dialog**

Replace `frontend/src/components/parser-eval/ParserEvalCasesTab.tsx` with:

```tsx
import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EvalStatusBadge } from '@/components/evaluation/EvalStatusBadge'
import { useParserEvalCases } from '@/hooks/useParserEval'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'

export function ParserEvalCasesTab({ projectId }: { projectId: string }) {
  const { cases, isLoading } = useParserEvalCases(projectId)
  const { sourceDocuments } = useSourceDocuments()
  const navigate = useNavigate()

  const filenameById = useMemo(() => {
    const map = new Map<string, string>()
    sourceDocuments.forEach((d) => map.set(d.id, d.filename ?? d.id))
    return map
  }, [sourceDocuments])

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => navigate('/evaluation/parser/cases/new')}>New case</Button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : cases.length === 0 ? (
        <p className="text-center py-8 text-muted-foreground">No cases yet — author one.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Document</TableHead>
              <TableHead>Dimension</TableHead>
              <TableHead>Review</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cases.map((c) => (
              <TableRow key={c.id} className="cursor-pointer"
                onClick={() => navigate(`/evaluation/parser/cases/${c.id}`)}>
                <TableCell>{filenameById.get(c.sourceDocumentId) ?? c.sourceDocumentId}</TableCell>
                <TableCell>{c.dimension}</TableCell>
                <TableCell><EvalStatusBadge status={c.reviewStatus} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
```

Then delete the dialog: `git rm frontend/src/components/parser-eval/CaseEditorDialog.tsx`.

- [ ] **Step 7: Update the Cases tab test**

Open `frontend/src/components/parser-eval/ParserEvalCasesTab.test.tsx`. Remove any assertion that opening "New case" renders the dialog; instead assert the button navigates. Wrap the render in `<MemoryRouter>` and mock `useNavigate`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import { ParserEvalCasesTab } from './ParserEvalCasesTab'

const navigate = vi.fn()
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}))
vi.mock('@/hooks/useParserEval', () => ({
  useParserEvalCases: () => ({ cases: [], isLoading: false }),
}))
vi.mock('@/hooks/useSourceDocuments', () => ({
  useSourceDocuments: () => ({ sourceDocuments: [] }),
}))

describe('ParserEvalCasesTab', () => {
  it('navigates to the new-case page', () => {
    render(<MemoryRouter><ParserEvalCasesTab projectId="p1" /></MemoryRouter>)
    fireEvent.click(screen.getByText('New case'))
    expect(navigate).toHaveBeenCalledWith('/evaluation/parser/cases/new')
  })
})
```

- [ ] **Step 8: Run the frontend tests**

Run: `cd frontend && npx vitest run src/pages/ParserEvalCasePage.test.tsx src/components/parser-eval/ParserEvalCasesTab.test.tsx`
Expected: PASS

- [ ] **Step 9: Typecheck + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add frontend/src/pages/ParserEvalCasePage.tsx frontend/src/components/parser-eval/CaseDetailView.tsx \
  frontend/src/App.tsx frontend/src/components/parser-eval/ParserEvalCasesTab.tsx \
  frontend/src/pages/ParserEvalCasePage.test.tsx frontend/src/components/parser-eval/ParserEvalCasesTab.test.tsx
git rm frontend/src/components/parser-eval/CaseEditorDialog.tsx
git commit -m "feat(parser-eval-fe): case page with dimension fork + table bootstrap; retire dialog"
```

---

## Task 11: Case page — detail/review mode (accept/reject)

**Files:**
- Modify (replace stub): `frontend/src/components/parser-eval/CaseDetailView.tsx`
- Test: `frontend/src/components/parser-eval/CaseDetailView.test.tsx`

**Interfaces:**
- Consumes: `useParserEvalCase` (Task 9).
- Produces: rendered draft review — table HTML per page + a draft/verified badge + Accept (verify) / Reject (delete → navigate back).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/parser-eval/CaseDetailView.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import { CaseDetailView } from './CaseDetailView'

vi.mock('@/hooks/useParserEval', () => ({
  useParserEvalCase: () => ({
    caseDetail: {
      id: 'c1', dimension: 'table', reviewStatus: 'draft',
      sourceDocumentId: 'd1', sourceMethod: 'bootstrapped', createdAt: '',
      expected: { tables: [{ page: 1, html: '<table><tr><td>Cell A</td></tr></table>' }] },
    },
    isLoading: false, verify: vi.fn(), reject: vi.fn(),
  }),
}))

describe('CaseDetailView', () => {
  it('renders draft tables with accept/reject actions', () => {
    render(<MemoryRouter><CaseDetailView projectId="p1" caseId="c1" /></MemoryRouter>)
    expect(screen.getByText('Cell A')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /accept/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/parser-eval/CaseDetailView.test.tsx`
Expected: FAIL (stub renders nothing)

- [ ] **Step 3: Implement `CaseDetailView`**

Replace `frontend/src/components/parser-eval/CaseDetailView.tsx`:

```tsx
import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useParserEvalCase } from '@/hooks/useParserEval'
import { EvalStatusBadge } from '@/components/evaluation/EvalStatusBadge'
import { Button } from '@/components/ui/button'
import type { TableGroundTruth } from '@/types/parserEval'

export function CaseDetailView({ projectId, caseId }: { projectId: string | null; caseId: string }) {
  const { caseDetail, isLoading, verify, reject } = useParserEvalCase(projectId, caseId)
  const navigate = useNavigate()

  const back = (
    <button onClick={() => navigate('/evaluation/parser')}
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft className="h-4 w-4" /> Back to cases
    </button>
  )

  if (isLoading && !caseDetail) return <p className="text-muted-foreground">Loading…</p>
  if (!caseDetail) return <div className="space-y-4">{back}<p className="text-muted-foreground">Case not found.</p></div>

  const tables = caseDetail.dimension === 'table'
    ? ((caseDetail.expected as unknown as TableGroundTruth).tables ?? [])
    : []

  const handleReject = async () => { await reject(); navigate('/evaluation/parser') }

  return (
    <div className="space-y-6">
      {back}
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">Ground truth · {caseDetail.dimension}</h1>
        <EvalStatusBadge status={caseDetail.reviewStatus} />
      </div>

      {caseDetail.dimension === 'table' ? (
        tables.length === 0 ? (
          <p className="text-muted-foreground">The parser found no tables in this document.</p>
        ) : (
          <div className="space-y-4">
            {tables.map((t, i) => (
              <div key={i} className="space-y-1">
                <span className="text-xs text-muted-foreground">Page {t.page}</span>
                {/* Parser-generated HTML rendered read-only for review. Follow-up: sanitize (Slice 2). */}
                <div className="rounded-md border p-3 overflow-x-auto [&_table]:border-collapse [&_td]:border [&_th]:border [&_td]:px-2 [&_th]:px-2"
                  dangerouslySetInnerHTML={{ __html: t.html }} />
              </div>
            ))}
          </div>
        )
      ) : (
        <p className="text-muted-foreground">Text ground truth review is unchanged.</p>
      )}

      {caseDetail.reviewStatus === 'draft' && (
        <div className="flex gap-2">
          <Button onClick={() => verify()}>Accept</Button>
          <Button variant="outline" onClick={handleReject}>Reject</Button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/parser-eval/CaseDetailView.test.tsx`
Expected: PASS

- [ ] **Step 5: Typecheck + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/parser-eval/CaseDetailView.tsx frontend/src/components/parser-eval/CaseDetailView.test.tsx
git commit -m "feat(parser-eval-fe): draft table review with accept/reject"
```

---

## Task 12: Dimension-aware comparison table

**Files:**
- Modify: `frontend/src/components/parser-eval/ParserComparisonTable.tsx`
- Modify: `frontend/src/pages/ParserEvalRunDetailPage.tsx`
- Test: `frontend/src/components/parser-eval/ParserComparisonTable.test.tsx`

**Interfaces:**
- Consumes: `ParserEvalResult[]`, `caseLabels: Record<caseId,filename>`, and NEW `caseDimensions: Record<caseId,dimension>`.
- Produces: per-case metric columns chosen by dimension — `text` → Similarity(pill)/Omission/Hallucination; `table` → TEDS(pill)/Table recall. Sorted by the dimension's primary metric.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/parser-eval/ParserComparisonTable.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ParserComparisonTable } from './ParserComparisonTable'
import type { ParserEvalResult } from '@/types/parserEval'

const result = (over: Partial<ParserEvalResult>): ParserEvalResult => ({
  evalCaseId: 'c1', adapter: 'docling', config: {}, variantKey: 'docling@x',
  metrics: {}, primaryMetric: null, details: null, cost: null, latencyMs: 100, ...over,
})

describe('ParserComparisonTable', () => {
  it('renders TEDS columns for a table case', () => {
    render(<ParserComparisonTable
      results={[result({ metrics: { teds: 0.9, table_recall: 1 }, primaryMetric: 'teds' })]}
      caseLabels={{ c1: 'a.pdf' }} caseDimensions={{ c1: 'table' }} />)
    expect(screen.getByText('TEDS')).toBeInTheDocument()
    expect(screen.getByText('Table recall')).toBeInTheDocument()
  })

  it('renders text columns for a text case', () => {
    render(<ParserComparisonTable
      results={[result({ metrics: { similarity: 0.8, omission: 0.1, hallucination: 0 }, primaryMetric: 'similarity' })]}
      caseLabels={{ c1: 'a.pdf' }} caseDimensions={{ c1: 'text' }} />)
    expect(screen.getByText('Similarity')).toBeInTheDocument()
    expect(screen.getByText('Hallucination')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/parser-eval/ParserComparisonTable.test.tsx`
Expected: FAIL — `caseDimensions` prop unknown / TEDS column not rendered.

- [ ] **Step 3: Rewrite `ParserComparisonTable` to be dimension-aware**

Replace `frontend/src/components/parser-eval/ParserComparisonTable.tsx`:

```tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ScorePill } from '@/components/evaluation/ScorePill'
import { PARSER_REGISTRY } from '@/components/documents/ParseMethodSelector'
import type { ParserEvalResult } from '@/types/parserEval'

interface MetricColumns {
  primary: { key: string; label: string }
  rest: { key: string; label: string }[]
}

const METRIC_COLUMNS: Record<string, MetricColumns> = {
  text: {
    primary: { key: 'similarity', label: 'Similarity' },
    rest: [{ key: 'omission', label: 'Omission' }, { key: 'hallucination', label: 'Hallucination' }],
  },
  table: {
    primary: { key: 'teds', label: 'TEDS' },
    rest: [{ key: 'table_recall', label: 'Table recall' }],
  },
}

function adapterLabel(adapter: string): string {
  return PARSER_REGISTRY[adapter]?.label ?? adapter
}
function fmtCost(cost: Record<string, number> | null): string {
  const usd = cost?.usd ?? 0
  return usd === 0 ? '$0' : `$${usd.toFixed(3)}`
}
function fmtLatency(ms: number | null): string {
  if (ms == null) return '—'
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}
function pct(v: number | undefined): string {
  return v == null ? '—' : `${(v * 100).toFixed(0)}%`
}

interface Props {
  results: ParserEvalResult[]
  caseLabels: Record<string, string>       // evalCaseId -> filename
  caseDimensions: Record<string, string>   // evalCaseId -> dimension
}

export function ParserComparisonTable({ results, caseLabels, caseDimensions }: Props) {
  const byCase = new Map<string, ParserEvalResult[]>()
  results.forEach((r) => {
    const arr = byCase.get(r.evalCaseId) ?? []
    arr.push(r)
    byCase.set(r.evalCaseId, arr)
  })

  return (
    <div className="space-y-6">
      {[...byCase.entries()].map(([caseId, rows]) => {
        const dimension = caseDimensions[caseId] ?? 'text'
        const cols = METRIC_COLUMNS[dimension] ?? METRIC_COLUMNS.text
        const sorted = [...rows].sort(
          (a, b) => (b.metrics[cols.primary.key] ?? 0) - (a.metrics[cols.primary.key] ?? 0),
        )
        return (
          <div key={caseId} className="space-y-2">
            <h3 className="text-sm font-semibold">{caseLabels[caseId] ?? caseId} · {dimension}</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Adapter</TableHead>
                  <TableHead>{cols.primary.label}</TableHead>
                  {cols.rest.map((c) => <TableHead key={c.key}>{c.label}</TableHead>)}
                  <TableHead>Cost</TableHead>
                  <TableHead>Latency</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((r) => (
                  <TableRow key={r.variantKey} data-testid="cmp-row">
                    <TableCell>{adapterLabel(r.adapter)}</TableCell>
                    <TableCell><ScorePill score={r.metrics[cols.primary.key] ?? null} /></TableCell>
                    {cols.rest.map((c) => <TableCell key={c.key}>{pct(r.metrics[c.key])}</TableCell>)}
                    <TableCell>{fmtCost(r.cost)}</TableCell>
                    <TableCell>{fmtLatency(r.latencyMs)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 4: Pass `caseDimensions` from the run detail page**

In `frontend/src/pages/ParserEvalRunDetailPage.tsx`, extend the `useMemo` to also build a dimensions map, and pass it to the table. Replace the `caseLabels` memo and the `<ParserComparisonTable .../>` usage:

```tsx
  const { caseLabels, caseDimensions } = useMemo(() => {
    const fname = new Map(sourceDocuments.map((d) => [d.id, d.filename ?? d.id]))
    const labels: Record<string, string> = {}
    const dims: Record<string, string> = {}
    cases.forEach((c) => {
      labels[c.id] = fname.get(c.sourceDocumentId) ?? c.sourceDocumentId
      dims[c.id] = c.dimension
    })
    return { caseLabels: labels, caseDimensions: dims }
  }, [cases, sourceDocuments])
```

```tsx
      {run.status === 'completed' && (
        <ParserComparisonTable results={results} caseLabels={caseLabels} caseDimensions={caseDimensions} />
      )}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/parser-eval/ParserComparisonTable.test.tsx`
Expected: PASS

- [ ] **Step 6: Typecheck + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/parser-eval/ParserComparisonTable.tsx \
  frontend/src/pages/ParserEvalRunDetailPage.tsx \
  frontend/src/components/parser-eval/ParserComparisonTable.test.tsx
git commit -m "feat(parser-eval-fe): dimension-aware comparison table (teds/recall)"
```

---

## Task 13: Full verification + manual round-trip

**Files:** none (verification only)

- [ ] **Step 1: Full backend suite**

Run: `cd backend && uv run python -m pytest -o "addopts="`
Expected: PASS (no regressions; new parser-eval tests green). Record the pass count.

- [ ] **Step 2: Frontend lint + build + tests**

Run: `cd frontend && npm run lint && npm run build && npx vitest run`
Expected: lint clean, build succeeds, tests pass (note: two pre-existing unrelated failures — `SchemaBuilder`, `ParseMethodSelector` — may still be red per project history; confirm no NEW failures).

- [ ] **Step 3: Postgres migration round-trip (container)**

The enum migration is not covered by SQLite tests. Verify against a real database per the CLAUDE.md local-testing flow:

```bash
cd frontend && npm run build
docker compose -f docker-compose.local.yml -p rag-admin up --build -d
docker compose -p rag-admin logs backend | grep -i alembic
```

Expected: backend starts; `alembic upgrade head` applies `a1b2c3d4e5f6` without error; `parser_eval_dimension` now includes `table`.

- [ ] **Step 4: Manual end-to-end smoke**

At http://localhost:
1. Evaluation → Parser → Cases → **New case** → routes to `/evaluation/parser/cases/new`.
2. Select a document with a table, choose **Table extraction**, pick a trusted parser (e.g. docling), configure, **Bootstrap draft** → lands on the case page showing the extracted table(s).
3. **Accept** → badge flips to verified. (Or Reject → returns to cases, case gone.)
4. Runs → **New Run** → select the table case + 2 parser variants → Run.
5. On the run detail page, confirm the comparison table shows **TEDS** + **Table recall** columns and sorts by TEDS.

- [ ] **Step 5: Request code review**

Use superpowers:requesting-code-review against the branch diff.

- [ ] **Step 6: Push and open the PR**

```bash
git push -u origin feat/parser-eval-table-dimension
gh pr create --title "Parser eval: table dimension — Slice 1 (TEDS + bootstrap)" \
  --body "Closes #150. Adds the table dimension end-to-end: TEDS scorer (teds + table_recall), bootstrap-from-trusted-parser ground truth on a promoted case page, dimension-aware comparison table. See docs/superpowers/specs/2026-07-07-parser-eval-table-dimension-design.md."
```

---

## Self-Review Notes (traceability to the spec & issue #150)

- **`table` dimension enum + migration** → Task 1. **Expected shape `{tables:[{page,html}]}`** → Task 1 (validation) + Task 6 (bootstrap builds it).
- **TEDS via `apted`** → Task 3. **`cells_to_html` fallback** → Task 2 (`table_to_html`) used by scorer (Task 4) and bootstrap (Task 6).
- **`score_table` emits `teds`(primary)+`table_recall`, order-matching, per-table details** → Task 4.
- **Bootstrap service + `POST cases/bootstrap-table`, provenance bootstrapped/draft, duplicate 409** → Tasks 6–7.
- **Accept (verify) / Reject (delete) endpoints** → Tasks 5–7 (backend), Task 11 (UI).
- **Case authoring moved to a page; dimension fork; reuse `ParseMethodSelector`+config** → Task 10.
- **Draft review renders tables read-only, badge** → Task 11.
- **Run results show `teds`+`table_recall`** → Task 12 (the existing table was NOT generic; this makes it dimension-aware).
- **Engine unchanged** → confirmed; no task modifies `engine.py` (it already dispatches by `case.dimension.value`).
- **Tests: scorer/teds/bootstrap/light FE** → Tasks 3,4,6,7,10,11,12. **Migration round-trip on container** → Task 13.
- **Out of scope (grid editor, optional/manual authoring, teds_struct/cell_content_f1, robust matching)** → not present; deferred to Slices 2–3 per spec.

**Type consistency check:** `bootstrapTableCase`/`getCase`/`updateCaseReview`/`deleteCase` names match across api (Task 8), hooks (Task 9), and callers (Tasks 10–11). `CaseDetailResponse.expected` (backend) ↔ `ParserEvalCaseDetail.expected` (frontend). `caseDimensions` prop consistent between `ParserComparisonTable` (Task 12) and `ParserEvalRunDetailPage` (Task 12). Scorer `emits`/`primary` (`teds`,`table_recall`) match the FE `METRIC_COLUMNS.table` keys.
```
