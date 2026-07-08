# Parser Eval — Table Grid Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user open a draft table eval case and correct its ground truth in a real grid editor (edit cells, add/remove rows & columns, merge/split cells, mark headers, fix the table set), then save and verify it.

**Architecture:** Storage stays HTML (`expected.tables[].html`) — the scorer/engine/text dimension are untouched. The frontend owns `html ↔ grid` conversion (native `DOMParser` in, canonical serializer out) and holds the grid as a transient `TableModel`. The backend adds one `PUT` endpoint that sanitizes HTML against a tight allowlist, shallow-validates it, replaces `expected`, and always resets `review_status` to `draft`. Verifying stays the existing `PATCH`.

**Tech Stack:** Backend — Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2, `nh3` (new). Frontend — React 18, TypeScript, Vite, shadcn/ui, Tailwind, Vitest + Testing Library.

## Global Constraints

- **Storage shape is unchanged:** `expected = {"tables": [{"page": int, "html": str}]}`. No new DB column, no `cells` field on the wire or in the DB.
- **`gridToHtml`/`modelToHtml` output MUST match the backend `table_to_html` convention** (`backend/app/services/parser_eval/table_html.py`): flat `<table>` → `<tr>` rows, no `thead`/`tbody`, `<th>` for header cells else `<td>`, `colspan`/`rowspan` attributes emitted **only when > 1**, text escaped as Python `html.escape(quote=True)` does (`&amp; &lt; &gt; &quot; &#x27;`).
- **`PUT` always sets `review_status = draft`.** Verified means a human approved exactly the current content. Verifying is a separate explicit `PATCH`.
- **Sanitizer allowlist — tags:** `table, thead, tbody, tr, td, th`. **Attributes:** `colspan`, `rowspan` (on `td`/`th`), `scope` (on `th`). Everything else stripped, text kept.
- **Size caps (post-sanitization):** ≤ 50 tables per case, ≤ 2000 cells per table.
- **Scope:** dimension `table` only. From-scratch *case* creation and bootstrap-to-text are out of scope (deferred).
- **Frontend:** shadcn/ui + Tailwind, hand-rolled — no table-editor library.
- **Backend tests run on SQLite** via the `test_db` / `client` / `seed_project_user_source` fixtures. Route prefix is `/api/v1`.
- **Test commands:** backend `cd backend && uv run python -m pytest -o "addopts=" <path> -v`; frontend `cd frontend && npx vitest run <path>`.

---

## File Structure

**Backend**
- Modify `backend/app/services/parser_eval/table_html.py` — add `sanitize_table_html`.
- Modify `backend/app/repositories/parser_eval_repository.py` — add `replace_case_expected`.
- Modify `backend/app/schemas/parser_eval.py` — add `CaseExpectedUpdate`.
- Modify `backend/app/services/parser_eval/service.py` — add `replace_case_tables`.
- Modify `backend/app/routers/parser_eval.py` — add `PUT .../cases/{case_id}`.
- Modify `backend/pyproject.toml` — add `nh3`.
- Tests: `backend/tests/services/test_table_html_sanitize.py` (new), and additions to `test_parser_eval_repository.py`, `test_parser_eval_schema.py`, `test_parser_eval_router.py`.

**Frontend**
- Create `frontend/src/components/parser-eval/tableGrid.ts` — model, conversion, ops (pure).
- Create `frontend/src/components/parser-eval/TableGridEditor.tsx` — single-table editor UI.
- Create `frontend/src/components/parser-eval/TableCaseEditor.tsx` — table-set + save/verify.
- Modify `frontend/src/components/parser-eval/CaseDetailView.tsx` — view/edit mode toggle.
- Modify `frontend/src/api/parserEval.ts` — add `replaceCaseTables`.
- Modify `frontend/src/hooks/useParserEval.ts` — add `saveTables` to `useParserEvalCase`.
- Modify `frontend/src/types/parserEval.ts` — reuse `TableGroundTruth` for the PUT body.
- Tests: `tableGrid.test.ts` (new), `TableGridEditor.test.tsx` (new), additions to `CaseDetailView.test.tsx`.

---

## Task 1: Backend — HTML sanitizer

**Files:**
- Modify: `backend/pyproject.toml` (add `nh3`)
- Modify: `backend/app/services/parser_eval/table_html.py`
- Test: `backend/tests/services/test_table_html_sanitize.py`

**Interfaces:**
- Produces: `sanitize_table_html(html: str) -> str` — returns HTML containing only allowlisted table tags/attributes, text preserved.

- [ ] **Step 1: Add the dependency**

Run: `cd backend && uv add nh3`
Expected: `pyproject.toml` gains an `nh3` entry and the lockfile updates.

- [ ] **Step 2: Write the failing test**

Create `backend/tests/services/test_table_html_sanitize.py`:

```python
from app.services.parser_eval.table_html import sanitize_table_html


def test_strips_script_and_handlers_keeps_text():
    dirty = '<table><tr><td onclick="x()">Hi<script>alert(1)</script></td></tr></table>'
    clean = sanitize_table_html(dirty)
    assert "script" not in clean.lower()
    assert "onclick" not in clean.lower()
    assert "Hi" in clean


def test_keeps_table_tags_and_span_attrs():
    html = '<table><tr><th colspan="2" scope="col">H</th></tr>' \
           '<tr><td rowspan="2">a</td><td>b</td></tr></table>'
    clean = sanitize_table_html(html)
    assert "<th" in clean and 'colspan="2"' in clean and 'scope="col"' in clean
    assert 'rowspan="2"' in clean


def test_drops_non_table_wrapper_tags():
    clean = sanitize_table_html('<div style="x"><table><tr><td>c</td></tr></table></div>')
    assert "<div" not in clean
    assert "style" not in clean
    assert "<td>c</td>" in clean
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/test_table_html_sanitize.py -v`
Expected: FAIL with `ImportError: cannot import name 'sanitize_table_html'`.

- [ ] **Step 4: Implement the sanitizer**

Add to the top-of-file imports of `backend/app/services/parser_eval/table_html.py`:

```python
import nh3
```

Append to the same file:

```python
_ALLOWED_TAGS = {"table", "thead", "tbody", "tr", "td", "th"}
_ALLOWED_ATTRS = {"td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan", "scope"}}


def sanitize_table_html(html: str) -> str:
    """Strip everything outside the table-structure allowlist; keep text content.

    Ground-truth HTML is authored by a trusted human but is rendered via
    dangerouslySetInnerHTML and scored, so it is sanitized at the write boundary.
    """
    return nh3.clean(
        html or "",
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        strip_comments=True,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/test_table_html_sanitize.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/services/parser_eval/table_html.py backend/tests/services/test_table_html_sanitize.py
git commit -m "feat(parser-eval): add table HTML sanitizer (nh3 allowlist)"
```

---

## Task 2: Backend — repository `replace_case_expected`

**Files:**
- Modify: `backend/app/repositories/parser_eval_repository.py`
- Test: `backend/tests/repositories/test_parser_eval_repository.py`

**Interfaces:**
- Consumes: existing `ParserEvalRepository.create_case`, `get_case`.
- Produces: `ParserEvalRepository.replace_case_expected(case_id: UUID, expected: dict) -> ParserEvalCase | None` — sets `expected`, forces `review_status = draft`, commits, refreshes; `None` if the case is missing.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/repositories/test_parser_eval_repository.py`:

```python
@pytest.mark.asyncio
async def test_replace_case_expected_resets_to_draft(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    repo = ParserEvalRepository(test_db)
    case = await repo.create_case(
        project_id, source_id, ParserEvalDimension.table,
        {"tables": [{"page": 1, "html": "<table><tr><td>a</td></tr></table>"}]}, user_id,
        review_status=ParserEvalReviewStatus.verified)

    new_expected = {"tables": [{"page": 2, "html": "<table><tr><td>b</td></tr></table>"}]}
    updated = await repo.replace_case_expected(case.id, new_expected)

    assert updated is not None
    assert updated.expected == new_expected
    assert updated.review_status == ParserEvalReviewStatus.draft
    assert await repo.replace_case_expected(uuid4(), new_expected) is None
```

Add `from uuid import uuid4` to the test file's imports if absent.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/repositories/test_parser_eval_repository.py::test_replace_case_expected_resets_to_draft -v`
Expected: FAIL with `AttributeError: 'ParserEvalRepository' object has no attribute 'replace_case_expected'`.

- [ ] **Step 3: Implement the repository method**

Add to `ParserEvalRepository` in `backend/app/repositories/parser_eval_repository.py`, right after `update_case_review_status`:

```python
    async def replace_case_expected(self, case_id: UUID, expected: dict) -> ParserEvalCase | None:
        case = await self.get_case(case_id)
        if case is None:
            return None
        case.expected = expected
        case.review_status = ParserEvalReviewStatus.draft
        await self.session.commit()
        await self.session.refresh(case)
        return case
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/repositories/test_parser_eval_repository.py::test_replace_case_expected_resets_to_draft -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/parser_eval_repository.py backend/tests/repositories/test_parser_eval_repository.py
git commit -m "feat(parser-eval): repo.replace_case_expected resets case to draft"
```

---

## Task 3: Backend — `CaseExpectedUpdate` schema

**Files:**
- Modify: `backend/app/schemas/parser_eval.py`
- Test: `backend/tests/schemas/test_parser_eval_schema.py`

**Interfaces:**
- Produces: `CaseExpectedUpdate` with field `tables: list[dict]` (camelCase JSON, `populate_by_name`). Validates: non-empty list; each item has an `html: str` and an integer `page`; ≤ 50 tables.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/schemas/test_parser_eval_schema.py`:

```python
import pytest
from pydantic import ValidationError
from app.schemas.parser_eval import CaseExpectedUpdate


def test_case_expected_update_accepts_tables():
    m = CaseExpectedUpdate(tables=[{"page": 1, "html": "<table><tr><td>a</td></tr></table>"}])
    assert m.tables[0]["html"].startswith("<table")


def test_case_expected_update_rejects_empty():
    with pytest.raises(ValidationError):
        CaseExpectedUpdate(tables=[])


def test_case_expected_update_rejects_missing_html():
    with pytest.raises(ValidationError):
        CaseExpectedUpdate(tables=[{"page": 1}])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/schemas/test_parser_eval_schema.py -k case_expected_update -v`
Expected: FAIL with `ImportError: cannot import name 'CaseExpectedUpdate'`.

- [ ] **Step 3: Implement the schema**

Add to `backend/app/schemas/parser_eval.py` (after `CaseReviewUpdate`):

```python
_MAX_TABLES = 50


class CaseExpectedUpdate(BaseModel):
    tables: list[dict]

    model_config = _CAMEL

    @field_validator("tables")
    @classmethod
    def _validate_tables(cls, value: list[dict]) -> list[dict]:
        if not value:
            raise ValueError("at least one table is required")
        if len(value) > _MAX_TABLES:
            raise ValueError(f"at most {_MAX_TABLES} tables allowed")
        for t in value:
            if not isinstance(t.get("html"), str) or not t["html"].strip():
                raise ValueError("each table requires a non-empty 'html' string")
            if not isinstance(t.get("page"), int):
                raise ValueError("each table requires an integer 'page'")
        return value
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/schemas/test_parser_eval_schema.py -k case_expected_update -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/parser_eval.py backend/tests/schemas/test_parser_eval_schema.py
git commit -m "feat(parser-eval): CaseExpectedUpdate schema"
```

---

## Task 4: Backend — service `replace_case_tables` + `PUT` route

**Files:**
- Modify: `backend/app/services/parser_eval/service.py`
- Modify: `backend/app/routers/parser_eval.py`
- Test: `backend/tests/routers/test_parser_eval_router.py`

**Interfaces:**
- Consumes: `sanitize_table_html` (Task 1), `repo.replace_case_expected` (Task 2), `CaseExpectedUpdate` (Task 3).
- Produces:
  - `ParserEvalService.replace_case_tables(case_id: UUID, data: CaseExpectedUpdate) -> CaseDetailResponse` — sanitizes each table's HTML, validates it contains a table with ≥1 cell and ≤ 2000 cells, persists, returns the (now `draft`) case. Raises `NotFoundError`, `ValidationError`.
  - Route `PUT /projects/{project_id}/parser-eval/cases/{case_id}` → `CaseDetailResponse`; 404 / 400 mapping.

- [ ] **Step 1: Write the failing integration test**

Add to `backend/tests/routers/test_parser_eval_router.py`:

```python
@pytest.mark.asyncio
async def test_put_case_replaces_tables_and_resets_draft(client: AsyncClient, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source

    class _FakeUser:
        id = user_id

    app.dependency_overrides[get_current_active_user] = lambda: _FakeUser()
    try:
        r = await client.post(
            f"/api/v1/projects/{project_id}/parser-eval/cases",
            json={"source_document_id": str(source_id), "dimension": "table",
                  "expected": {"tables": [{"page": 1, "html": "<table><tr><td>a</td></tr></table>"}]},
                  "reviewStatus": "verified"})
        assert r.status_code == 200, r.text
        case_id = r.json()["id"]

        r = await client.put(
            f"/api/v1/projects/{project_id}/parser-eval/cases/{case_id}",
            json={"tables": [{"page": 2,
                              "html": '<table><tr><td onclick="x">b</td></tr></table>'}]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["reviewStatus"] == "draft"
        assert body["expected"]["tables"][0]["page"] == 2
        assert "onclick" not in body["expected"]["tables"][0]["html"].lower()

    finally:
        app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_put_case_rejects_text_dimension(client: AsyncClient, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source

    class _FakeUser:
        id = user_id

    app.dependency_overrides[get_current_active_user] = lambda: _FakeUser()
    try:
        r = await client.post(
            f"/api/v1/projects/{project_id}/parser-eval/cases",
            json={"source_document_id": str(source_id), "dimension": "text",
                  "expected": {"pages": ["hi"]}})
        case_id = r.json()["id"]
        r = await client.put(
            f"/api/v1/projects/{project_id}/parser-eval/cases/{case_id}",
            json={"tables": [{"page": 1, "html": "<table><tr><td>a</td></tr></table>"}]})
        assert r.status_code == 400, r.text
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/routers/test_parser_eval_router.py -k put_case -v`
Expected: FAIL (405 Method Not Allowed — no `PUT` route yet).

- [ ] **Step 3: Implement the service method**

In `backend/app/services/parser_eval/service.py`, update the `table_html` import to include the sanitizer:

```python
from app.services.parser_eval.table_html import extract_cdm_tables, sanitize_table_html
```

Add `CaseExpectedUpdate` to the schema import block, then add this method after `set_case_review`:

```python
    _MAX_CELLS_PER_TABLE = 2000

    async def replace_case_tables(self, case_id: UUID,
                                  data: "CaseExpectedUpdate") -> CaseDetailResponse:
        case = await self.repo.get_case(case_id)
        if case is None:
            raise NotFoundError(f"Parser eval case {case_id} not found")
        if case.dimension != ParserEvalDimension.table:
            raise ValidationError("Only table cases support table replacement")

        clean_tables = []
        for t in data.tables:
            html = sanitize_table_html(t["html"])
            cell_count = html.lower().count("<td") + html.lower().count("<th")
            if "<table" not in html.lower() or cell_count == 0:
                raise ValidationError("each table must contain at least one cell")
            if cell_count > self._MAX_CELLS_PER_TABLE:
                raise ValidationError(
                    f"table exceeds {self._MAX_CELLS_PER_TABLE} cells")
            clean_tables.append({"page": t["page"], "html": html})

        updated = await self.repo.replace_case_expected(case_id, {"tables": clean_tables})
        return CaseDetailResponse.model_validate(updated)
```

Add the import for `CaseExpectedUpdate` to the existing `from app.schemas.parser_eval import (...)` block.

- [ ] **Step 4: Implement the route**

In `backend/app/routers/parser_eval.py`, add `CaseExpectedUpdate` to the `from app.schemas.parser_eval import (...)` block, then add after `update_case_review`:

```python
@router.put("/projects/{project_id}/parser-eval/cases/{case_id}",
            response_model=CaseDetailResponse)
async def replace_case_tables(
    project_id: UUID,
    case_id: UUID,
    data: CaseExpectedUpdate,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.replace_case_tables(case_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/routers/test_parser_eval_router.py -k put_case -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Run the full parser-eval backend suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/ -k parser_eval -v`
Expected: PASS (no regressions).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/parser_eval/service.py backend/app/routers/parser_eval.py backend/tests/routers/test_parser_eval_router.py
git commit -m "feat(parser-eval): PUT cases/{id} replaces table ground truth"
```

---

## Task 5: Frontend — grid model + HTML conversion

**Files:**
- Create: `frontend/src/components/parser-eval/tableGrid.ts`
- Test: `frontend/src/components/parser-eval/tableGrid.test.ts`

**Interfaces:**
- Produces:
  - `interface EditorCell { text: string; isHeader: boolean }`
  - `interface AnchorCell extends EditorCell { row: number; col: number; rowspan: number; colspan: number }`
  - `interface TableModel { rows: number; cols: number; cells: AnchorCell[] }`
  - `type Slot = { kind: 'anchor'; cell: AnchorCell } | { kind: 'covered'; cell: AnchorCell }`
  - `htmlToModel(html: string): TableModel`
  - `modelToHtml(model: TableModel): string`
  - `materialize(model: TableModel): Slot[][]`
  - `emptyModel(rows: number, cols: number): TableModel`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/parser-eval/tableGrid.test.ts`:

```ts
// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { htmlToModel, modelToHtml, materialize, emptyModel } from './tableGrid'

describe('tableGrid conversion', () => {
  it('round-trips a flat table', () => {
    const html = '<table><tr><th>H1</th><th>H2</th></tr><tr><td>a</td><td>b</td></tr></table>'
    expect(modelToHtml(htmlToModel(html))).toBe(html)
  })

  it('round-trips colspan and rowspan', () => {
    const html = '<table><tr><th colspan="2">Top</th></tr>'
      + '<tr><td rowspan="2">L</td><td>b</td></tr><tr><td>c</td></tr></table>'
    expect(modelToHtml(htmlToModel(html))).toBe(html)
  })

  it('escapes text like the backend serializer', () => {
    const m = emptyModel(1, 1)
    m.cells[0].text = 'a < b & "c"'
    expect(modelToHtml(m)).toBe('<table><tr><td>a &lt; b &amp; &quot;c&quot;</td></tr></table>')
  })

  it('materialize marks covered slots for a colspan', () => {
    const grid = materialize(htmlToModel('<table><tr><td colspan="2">x</td></tr></table>'))
    expect(grid[0][0].kind).toBe('anchor')
    expect(grid[0][1].kind).toBe('covered')
  })

  it('fills ragged rows with empty cells', () => {
    const m = htmlToModel('<table><tr><td>a</td><td>b</td></tr><tr><td>c</td></tr></table>')
    expect(m.rows).toBe(2)
    expect(m.cols).toBe(2)
    expect(m.cells).toHaveLength(4)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/parser-eval/tableGrid.test.ts`
Expected: FAIL (cannot resolve `./tableGrid`).

- [ ] **Step 3: Implement conversion**

Create `frontend/src/components/parser-eval/tableGrid.ts`:

```ts
export interface EditorCell {
  text: string
  isHeader: boolean
}

export interface AnchorCell extends EditorCell {
  row: number
  col: number
  rowspan: number
  colspan: number
}

export interface TableModel {
  rows: number
  cols: number
  cells: AnchorCell[]
}

export type Slot =
  | { kind: 'anchor'; cell: AnchorCell }
  | { kind: 'covered'; cell: AnchorCell }

function newCell(row: number, col: number): AnchorCell {
  return { row, col, rowspan: 1, colspan: 1, text: '', isHeader: false }
}

export function emptyModel(rows: number, cols: number): TableModel {
  const cells: AnchorCell[] = []
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) cells.push(newCell(r, c))
  return { rows, cols, cells }
}

/** Fill any unoccupied (r,c) inside rows×cols with empty 1×1 anchors. */
function fillHoles(model: TableModel): TableModel {
  const occupied = new Set<string>()
  for (const cell of model.cells) {
    for (let dr = 0; dr < cell.rowspan; dr++) {
      for (let dc = 0; dc < cell.colspan; dc++) occupied.add(`${cell.row + dr},${cell.col + dc}`)
    }
  }
  for (let r = 0; r < model.rows; r++) {
    for (let c = 0; c < model.cols; c++) {
      if (!occupied.has(`${r},${c}`)) model.cells.push(newCell(r, c))
    }
  }
  model.cells.sort((a, b) => (a.row - b.row) || (a.col - b.col))
  return model
}

export function htmlToModel(html: string): TableModel {
  const doc = new DOMParser().parseFromString(html, 'text/html')
  const table = doc.querySelector('table')
  if (!table) return emptyModel(1, 1)

  const occupied = new Set<string>()
  const cells: AnchorCell[] = []
  let maxRow = 0
  let maxCol = 0

  Array.from(table.querySelectorAll('tr')).forEach((tr, r) => {
    let c = 0
    for (const el of Array.from(tr.children)) {
      if (el.tagName !== 'TD' && el.tagName !== 'TH') continue
      while (occupied.has(`${r},${c}`)) c++
      const td = el as HTMLTableCellElement
      const rowspan = Math.max(1, td.rowSpan || 1)
      const colspan = Math.max(1, td.colSpan || 1)
      cells.push({ row: r, col: c, rowspan, colspan,
        text: (el.textContent ?? '').trim(), isHeader: el.tagName === 'TH' })
      for (let dr = 0; dr < rowspan; dr++) {
        for (let dc = 0; dc < colspan; dc++) occupied.add(`${r + dr},${c + dc}`)
      }
      maxRow = Math.max(maxRow, r + rowspan)
      maxCol = Math.max(maxCol, c + colspan)
      c += colspan
    }
  })

  if (cells.length === 0) return emptyModel(1, 1)
  return fillHoles({ rows: maxRow, cols: maxCol, cells })
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
}

export function modelToHtml(model: TableModel): string {
  const byRow = new Map<number, AnchorCell[]>()
  for (const cell of model.cells) {
    if (!byRow.has(cell.row)) byRow.set(cell.row, [])
    byRow.get(cell.row)!.push(cell)
  }
  const parts = ['<table>']
  for (let r = 0; r < model.rows; r++) {
    parts.push('<tr>')
    const row = (byRow.get(r) ?? []).slice().sort((a, b) => a.col - b.col)
    for (const cell of row) {
      const tag = cell.isHeader ? 'th' : 'td'
      let attrs = ''
      if (cell.colspan > 1) attrs += ` colspan="${cell.colspan}"`
      if (cell.rowspan > 1) attrs += ` rowspan="${cell.rowspan}"`
      parts.push(`<${tag}${attrs}>${escapeHtml(cell.text)}</${tag}>`)
    }
    parts.push('</tr>')
  }
  parts.push('</table>')
  return parts.join('')
}

export function materialize(model: TableModel): Slot[][] {
  const grid: Slot[][] = Array.from({ length: model.rows }, () =>
    new Array<Slot>(model.cols))
  for (const cell of model.cells) {
    for (let dr = 0; dr < cell.rowspan; dr++) {
      for (let dc = 0; dc < cell.colspan; dc++) {
        grid[cell.row + dr][cell.col + dc] =
          dr === 0 && dc === 0 ? { kind: 'anchor', cell } : { kind: 'covered', cell }
      }
    }
  }
  return grid
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/parser-eval/tableGrid.test.ts`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/parser-eval/tableGrid.ts frontend/src/components/parser-eval/tableGrid.test.ts
git commit -m "feat(parser-eval): table grid model + HTML conversion"
```

---

## Task 6: Frontend — grid operations

**Files:**
- Modify: `frontend/src/components/parser-eval/tableGrid.ts`
- Test: `frontend/src/components/parser-eval/tableGrid.test.ts`

**Interfaces:**
- Consumes: `TableModel`, `AnchorCell`, `materialize`, `emptyModel` (Task 5).
- Produces (all pure; return a new `TableModel`; throw `Error` on invalid input):
  - `setText(m, row, col, text): TableModel`
  - `toggleHeader(m, row, col): TableModel`
  - `addRow(m, at): TableModel` / `removeRow(m, at): TableModel`
  - `addColumn(m, at): TableModel` / `removeColumn(m, at): TableModel`
  - `mergeCells(m, r1, c1, r2, c2): TableModel`
  - `splitCell(m, row, col): TableModel`

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/components/parser-eval/tableGrid.test.ts`:

```ts
import {
  setText, toggleHeader, addRow, removeRow, addColumn, removeColumn, mergeCells, splitCell,
} from './tableGrid'

const anchorAt = (m: import('./tableGrid').TableModel, r: number, c: number) =>
  m.cells.find((cell) => cell.row === r && cell.col === c)!

describe('tableGrid operations', () => {
  it('setText and toggleHeader mutate the anchor', () => {
    let m = emptyModel(1, 1)
    m = setText(m, 0, 0, 'hi')
    m = toggleHeader(m, 0, 0)
    expect(anchorAt(m, 0, 0).text).toBe('hi')
    expect(anchorAt(m, 0, 0).isHeader).toBe(true)
  })

  it('addRow grows dimensions and shifts lower cells', () => {
    const m = addRow(emptyModel(2, 2), 1)
    expect(m.rows).toBe(3)
    expect(m.cells.filter((c) => c.row === 1)).toHaveLength(2)
  })

  it('addColumn extends a crossing colspan', () => {
    let m = emptyModel(1, 2)
    m = mergeCells(m, 0, 0, 0, 1)
    m = addColumn(m, 1)
    expect(anchorAt(m, 0, 0).colspan).toBe(3)
  })

  it('removeRow deletes a plain row', () => {
    const m = removeRow(emptyModel(2, 2), 0)
    expect(m.rows).toBe(1)
  })

  it('removeRow rejects slicing a rowspan', () => {
    let m = emptyModel(2, 1)
    m = mergeCells(m, 0, 0, 1, 0)
    expect(() => removeRow(m, 0)).toThrow()
  })

  it('mergeCells joins a rectangle and materialize covers it', () => {
    let m = emptyModel(2, 2)
    m = setText(m, 0, 0, 'a')
    m = setText(m, 0, 1, 'b')
    m = mergeCells(m, 0, 0, 0, 1)
    expect(anchorAt(m, 0, 0).colspan).toBe(2)
    expect(anchorAt(m, 0, 0).text).toBe('a b')
    expect(materialize(m)[0][1].kind).toBe('covered')
  })

  it('mergeCells rejects a selection overlapping an existing span', () => {
    let m = emptyModel(2, 2)
    m = mergeCells(m, 0, 0, 1, 0)
    expect(() => mergeCells(m, 0, 0, 0, 1)).toThrow()
  })

  it('splitCell restores 1x1 anchors', () => {
    let m = emptyModel(2, 2)
    m = mergeCells(m, 0, 0, 1, 1)
    m = splitCell(m, 0, 0)
    expect(anchorAt(m, 0, 0).rowspan).toBe(1)
    expect(anchorAt(m, 0, 0).colspan).toBe(1)
    expect(m.cells).toHaveLength(4)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/parser-eval/tableGrid.test.ts`
Expected: FAIL (the operation functions are not exported).

- [ ] **Step 3: Implement the operations**

Append to `frontend/src/components/parser-eval/tableGrid.ts`:

```ts
function clone(model: TableModel): TableModel {
  return { rows: model.rows, cols: model.cols, cells: model.cells.map((c) => ({ ...c })) }
}

function anchorAt(model: TableModel, row: number, col: number): AnchorCell {
  const cell = model.cells.find((c) => c.row === row && c.col === col)
  if (!cell) throw new Error(`No anchor cell at (${row}, ${col}); select a top-left cell`)
  return cell
}

export function setText(model: TableModel, row: number, col: number, text: string): TableModel {
  const next = clone(model)
  anchorAt(next, row, col).text = text
  return next
}

export function toggleHeader(model: TableModel, row: number, col: number): TableModel {
  const next = clone(model)
  const cell = anchorAt(next, row, col)
  cell.isHeader = !cell.isHeader
  return next
}

export function addRow(model: TableModel, at: number): TableModel {
  const next = clone(model)
  for (const cell of next.cells) {
    if (at <= cell.row) cell.row++
    else if (at <= cell.row + cell.rowspan - 1) cell.rowspan++
  }
  next.rows++
  for (let c = 0; c < next.cols; c++) next.cells.push(newCell(at, c))
  return fillHoles(next)
}

export function removeRow(model: TableModel, at: number): TableModel {
  if (model.rows <= 1) throw new Error('A table needs at least one row')
  for (const cell of model.cells) {
    if (cell.rowspan > 1 && cell.row <= at && at <= cell.row + cell.rowspan - 1) {
      throw new Error('Split the merged cell crossing this row before removing it')
    }
  }
  const next = clone(model)
  next.cells = next.cells.filter((cell) => cell.row !== at)
  for (const cell of next.cells) if (cell.row > at) cell.row--
  next.rows--
  return next
}

export function addColumn(model: TableModel, at: number): TableModel {
  const next = clone(model)
  for (const cell of next.cells) {
    if (at <= cell.col) cell.col++
    else if (at <= cell.col + cell.colspan - 1) cell.colspan++
  }
  next.cols++
  for (let r = 0; r < next.rows; r++) next.cells.push(newCell(r, at))
  return fillHoles(next)
}

export function removeColumn(model: TableModel, at: number): TableModel {
  if (model.cols <= 1) throw new Error('A table needs at least one column')
  for (const cell of model.cells) {
    if (cell.colspan > 1 && cell.col <= at && at <= cell.col + cell.colspan - 1) {
      throw new Error('Split the merged cell crossing this column before removing it')
    }
  }
  const next = clone(model)
  next.cells = next.cells.filter((cell) => cell.col !== at)
  for (const cell of next.cells) if (cell.col > at) cell.col--
  next.cols--
  return next
}

export function mergeCells(model: TableModel, r1: number, c1: number,
                           r2: number, c2: number): TableModel {
  const top = Math.min(r1, r2)
  const bottom = Math.max(r1, r2)
  const left = Math.min(c1, c2)
  const right = Math.max(c1, c2)
  const grid = materialize(model)
  const members: AnchorCell[] = []
  for (let r = top; r <= bottom; r++) {
    for (let c = left; c <= right; c++) {
      const slot = grid[r][c]
      if (slot.kind !== 'anchor' || slot.cell.rowspan !== 1 || slot.cell.colspan !== 1) {
        throw new Error('Merge only supports a clean rectangle of single cells')
      }
      members.push(slot.cell)
    }
  }
  const next = clone(model)
  const keep = anchorAt(next, top, left)
  keep.rowspan = bottom - top + 1
  keep.colspan = right - left + 1
  keep.text = members.map((m) => m.text).filter((t) => t).join(' ')
  const removed = new Set(members.filter((m) => !(m.row === top && m.col === left))
    .map((m) => `${m.row},${m.col}`))
  next.cells = next.cells.filter((c) => !removed.has(`${c.row},${c.col}`))
  return next
}

export function splitCell(model: TableModel, row: number, col: number): TableModel {
  const next = clone(model)
  const cell = anchorAt(next, row, col)
  const { rowspan, colspan } = cell
  cell.rowspan = 1
  cell.colspan = 1
  for (let dr = 0; dr < rowspan; dr++) {
    for (let dc = 0; dc < colspan; dc++) {
      if (dr === 0 && dc === 0) continue
      next.cells.push(newCell(row + dr, col + dc))
    }
  }
  next.cells.sort((a, b) => (a.row - b.row) || (a.col - b.col))
  return next
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/parser-eval/tableGrid.test.ts`
Expected: PASS (all conversion + operation tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/parser-eval/tableGrid.ts frontend/src/components/parser-eval/tableGrid.test.ts
git commit -m "feat(parser-eval): grid ops (rows, cols, merge, split, header)"
```

---

## Task 7: Frontend — `TableGridEditor` component

**Files:**
- Create: `frontend/src/components/parser-eval/TableGridEditor.tsx`
- Test: `frontend/src/components/parser-eval/TableGridEditor.test.tsx`

**Interfaces:**
- Consumes: everything from `tableGrid.ts` (Tasks 5–6).
- Produces: `TableGridEditor({ model, onChange }: { model: TableModel; onChange: (m: TableModel) => void })` — renders the materialized grid with per-anchor text inputs and a toolbar (Add row, Add column, Merge, Split, Header, Delete row, Delete column). Selection is a single anchor by default; shift-click extends a rectangle for Merge. Operation errors are shown inline (not thrown to the caller).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/parser-eval/TableGridEditor.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { TableGridEditor } from './TableGridEditor'
import { emptyModel } from './tableGrid'

describe('TableGridEditor', () => {
  it('edits cell text through onChange', () => {
    const onChange = vi.fn()
    render(<TableGridEditor model={emptyModel(1, 1)} onChange={onChange} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'hello' } })
    expect(onChange).toHaveBeenCalled()
    const next = onChange.mock.calls.at(-1)![0]
    expect(next.cells[0].text).toBe('hello')
  })

  it('adds a row via the toolbar', () => {
    const onChange = vi.fn()
    render(<TableGridEditor model={emptyModel(1, 1)} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /add row/i }))
    expect(onChange.mock.calls.at(-1)![0].rows).toBe(2)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/parser-eval/TableGridEditor.test.tsx`
Expected: FAIL (cannot resolve `./TableGridEditor`).

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/parser-eval/TableGridEditor.tsx`:

```tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  materialize, setText, toggleHeader, addRow, removeRow, addColumn, removeColumn,
  mergeCells, splitCell, type TableModel,
} from './tableGrid'

interface Sel { r1: number; c1: number; r2: number; c2: number }

export function TableGridEditor({ model, onChange }:
  { model: TableModel; onChange: (m: TableModel) => void }) {
  const [sel, setSel] = useState<Sel>({ r1: 0, c1: 0, r2: 0, c2: 0 })
  const [error, setError] = useState<string | null>(null)
  const grid = materialize(model)

  const apply = (fn: () => TableModel) => {
    try { setError(null); onChange(fn()) } catch (e) { setError((e as Error).message) }
  }
  const onCellMouseDown = (r: number, c: number, shift: boolean) =>
    setSel((s) => shift ? { ...s, r2: r, c2: c } : { r1: r, c1: c, r2: r, c2: c })

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        <Button size="sm" variant="outline" onClick={() => apply(() => addRow(model, sel.r1 + 1))}>Add row</Button>
        <Button size="sm" variant="outline" onClick={() => apply(() => addColumn(model, sel.c1 + 1))}>Add column</Button>
        <Button size="sm" variant="outline" onClick={() => apply(() => removeRow(model, sel.r1))}>Delete row</Button>
        <Button size="sm" variant="outline" onClick={() => apply(() => removeColumn(model, sel.c1))}>Delete column</Button>
        <Button size="sm" variant="outline"
          onClick={() => apply(() => mergeCells(model, sel.r1, sel.c1, sel.r2, sel.c2))}>Merge</Button>
        <Button size="sm" variant="outline" onClick={() => apply(() => splitCell(model, sel.r1, sel.c1))}>Split</Button>
        <Button size="sm" variant="outline" onClick={() => apply(() => toggleHeader(model, sel.r1, sel.c1))}>Header</Button>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
      <table className="border-collapse">
        <tbody>
          {grid.map((row, r) => (
            <tr key={r}>
              {row.map((slot, c) => {
                if (slot.kind === 'covered') return null
                const { cell } = slot
                const selected = r === sel.r1 && c === sel.c1
                return (
                  <td key={c} rowSpan={cell.rowspan} colSpan={cell.colspan}
                    onMouseDown={(e) => onCellMouseDown(r, c, e.shiftKey)}
                    className={`border p-0 ${selected ? 'ring-2 ring-primary' : ''} ${cell.isHeader ? 'bg-muted font-semibold' : ''}`}>
                    <input
                      aria-label={`cell ${r},${c}`}
                      className="w-full min-w-24 bg-transparent px-2 py-1 text-sm outline-none"
                      value={cell.text}
                      onChange={(e) => apply(() => setText(model, r, c, e.target.value))} />
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/parser-eval/TableGridEditor.test.tsx`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/parser-eval/TableGridEditor.tsx frontend/src/components/parser-eval/TableGridEditor.test.tsx
git commit -m "feat(parser-eval): TableGridEditor component"
```

---

## Task 8: Frontend — case page edit mode, API + hook wiring

**Files:**
- Modify: `frontend/src/api/parserEval.ts`
- Modify: `frontend/src/types/parserEval.ts`
- Modify: `frontend/src/hooks/useParserEval.ts`
- Create: `frontend/src/components/parser-eval/TableCaseEditor.tsx`
- Modify: `frontend/src/components/parser-eval/CaseDetailView.tsx`
- Test: `frontend/src/components/parser-eval/CaseDetailView.test.tsx`

**Interfaces:**
- Consumes: `TableGridEditor` (Task 7), `htmlToModel`/`modelToHtml` (Task 5), `PUT` endpoint (Task 4).
- Produces:
  - `replaceCaseTables(projectId, caseId, tables: { page: number; html: string }[]): Promise<ParserEvalCaseDetail>` in `api/parserEval.ts`.
  - `useParserEvalCase(...)` gains `saveTables(tables, opts?: { verify?: boolean }): Promise<void>`.
  - `TableCaseEditor({ tables, onSave, onCancel })` manages the table list + save actions.
  - `CaseDetailView` gains an inline edit mode for `dimension === 'table'`.

- [ ] **Step 1: Add the API function**

Add to `frontend/src/api/parserEval.ts`:

```ts
export async function replaceCaseTables(
  projectId: string, caseId: string, tables: { page: number; html: string }[],
): Promise<ParserEvalCaseDetail> {
  const r = await apiClient.put<ParserEvalCaseDetail>(
    `/projects/${projectId}/parser-eval/cases/${caseId}`, { tables })
  return r.data
}
```

- [ ] **Step 2: Extend the hook**

In `frontend/src/hooks/useParserEval.ts`, inside `useParserEvalCase`, add after `reject`:

```ts
  const saveTables = useCallback(
    async (tables: { page: number; html: string }[], opts?: { verify?: boolean }) => {
      if (!projectId || !caseId) return
      let updated = await api.replaceCaseTables(projectId, caseId, tables)
      if (opts?.verify) updated = await api.updateCaseReview(projectId, caseId, 'verified')
      setCaseDetail(updated)
    }, [projectId, caseId])
```

Add `saveTables` to the returned object: `return { caseDetail, isLoading, error, verify, reject, saveTables }`.

- [ ] **Step 3: Write the failing test**

Add to `frontend/src/components/parser-eval/CaseDetailView.test.tsx` (follow the file's existing mock/render setup; this test asserts the new edit affordance and save wiring):

```tsx
it('edits a draft table case and saves', async () => {
  // Arrange: a draft table case detail is returned by the mocked hook/api.
  renderCaseDetail({
    dimension: 'table', reviewStatus: 'draft',
    expected: { tables: [{ page: 1, html: '<table><tr><td>a</td></tr></table>' }] },
  })
  fireEvent.click(await screen.findByRole('button', { name: /edit/i }))
  fireEvent.change(screen.getByLabelText('cell 0,0'), { target: { value: 'z' } })
  fireEvent.click(screen.getByRole('button', { name: /^save$/i }))
  await waitFor(() => expect(replaceCaseTablesMock).toHaveBeenCalled())
  const tablesArg = replaceCaseTablesMock.mock.calls.at(-1)![2]
  expect(tablesArg[0].html).toContain('z')
})
```

Wire `replaceCaseTablesMock` into the file's existing `vi.mock('@/api/parserEval', ...)` (or hook mock) alongside the mocks already there, and add a `renderCaseDetail` helper if the file doesn't already expose one (mirror the existing render setup in this test file).

- [ ] **Step 4: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/parser-eval/CaseDetailView.test.tsx`
Expected: FAIL (no Edit button / `saveTables` not wired).

- [ ] **Step 5: Implement `TableCaseEditor`**

Create `frontend/src/components/parser-eval/TableCaseEditor.tsx`:

```tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { TableGridEditor } from './TableGridEditor'
import { htmlToModel, modelToHtml, emptyModel, type TableModel } from './tableGrid'

interface EditableTable { page: number; model: TableModel }

export function TableCaseEditor({ tables, onSave, onCancel }: {
  tables: { page: number; html: string }[]
  onSave: (tables: { page: number; html: string }[], opts: { verify: boolean }) => Promise<void>
  onCancel: () => void
}) {
  const [rows, setRows] = useState<EditableTable[]>(
    () => tables.map((t) => ({ page: t.page, model: htmlToModel(t.html) })))
  const [saving, setSaving] = useState(false)

  const update = (i: number, patch: Partial<EditableTable>) =>
    setRows((r) => r.map((t, idx) => (idx === i ? { ...t, ...patch } : t)))
  const move = (i: number, dir: -1 | 1) => setRows((r) => {
    const j = i + dir
    if (j < 0 || j >= r.length) return r
    const copy = [...r];[copy[i], copy[j]] = [copy[j], copy[i]]; return copy
  })
  const serialize = () => rows.map((t) => ({ page: t.page, html: modelToHtml(t.model) }))
  const save = async (verify: boolean) => {
    setSaving(true)
    try { await onSave(serialize(), { verify }) } finally { setSaving(false) }
  }

  return (
    <div className="space-y-6">
      {rows.map((t, i) => (
        <div key={i} className="space-y-2 rounded-md border p-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Page</span>
            <Input type="number" className="w-20" value={t.page}
              onChange={(e) => update(i, { page: Number(e.target.value) })} />
            <Button size="sm" variant="ghost" onClick={() => move(i, -1)}>↑</Button>
            <Button size="sm" variant="ghost" onClick={() => move(i, 1)}>↓</Button>
            <Button size="sm" variant="ghost"
              onClick={() => setRows((r) => r.filter((_, idx) => idx !== i))}>Delete table</Button>
          </div>
          <TableGridEditor model={t.model} onChange={(m) => update(i, { model: m })} />
        </div>
      ))}
      <Button variant="outline" size="sm"
        onClick={() => setRows((r) => [...r, { page: 1, model: emptyModel(2, 2) }])}>Add table</Button>
      <div className="flex gap-2">
        <Button disabled={saving} onClick={() => save(false)}>Save</Button>
        <Button disabled={saving} variant="secondary" onClick={() => save(true)}>Save &amp; Accept</Button>
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Wire edit mode into `CaseDetailView`**

In `frontend/src/components/parser-eval/CaseDetailView.tsx`: pull `saveTables` from `useParserEvalCase`, add an `editing` state, render an **Edit** button for draft table cases, and render `TableCaseEditor` when editing. Replace the existing table view/action block with:

```tsx
import { useState } from 'react'
import { TableCaseEditor } from './TableCaseEditor'
// ...existing imports...

// inside the component, replace the hook line:
const { caseDetail, isLoading, verify, reject, saveTables } = useParserEvalCase(projectId, caseId)
const [editing, setEditing] = useState(false)

// ...unchanged loading / not-found / header ...

// table branch:
{caseDetail.dimension === 'table' ? (
  editing ? (
    <TableCaseEditor
      tables={tables}
      onSave={async (t, opts) => { await saveTables(t, opts); setEditing(false) }}
      onCancel={() => setEditing(false)} />
  ) : (
    <>
      {tables.length === 0 ? (
        <p className="text-muted-foreground">The parser found no tables in this document.</p>
      ) : (
        <div className="space-y-4">
          {tables.map((t, i) => (
            <div key={i} className="space-y-1">
              <span className="text-xs text-muted-foreground">Page {t.page}</span>
              <div className="rounded-md border p-3 overflow-x-auto [&_table]:border-collapse [&_td]:border [&_th]:border [&_td]:px-2 [&_th]:px-2"
                dangerouslySetInnerHTML={{ __html: t.html }} />
            </div>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <Button variant="outline" onClick={() => setEditing(true)}>Edit</Button>
        {caseDetail.reviewStatus === 'draft' && (
          <>
            <Button onClick={() => verify()}>Accept</Button>
            <Button variant="outline" onClick={handleReject}>Reject</Button>
          </>
        )}
      </div>
    </>
  )
) : (
  <p className="text-muted-foreground">Text ground truth review is unchanged.</p>
)}
```

Remove the now-superseded standalone draft action block and the `// Follow-up: sanitize (Slice 2).` comment (HTML is sanitized server-side on save now).

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/parser-eval/CaseDetailView.test.tsx`
Expected: PASS (existing tests + the new edit test).

- [ ] **Step 8: Lint and build**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/api/parserEval.ts frontend/src/types/parserEval.ts frontend/src/hooks/useParserEval.ts frontend/src/components/parser-eval/TableCaseEditor.tsx frontend/src/components/parser-eval/CaseDetailView.tsx frontend/src/components/parser-eval/CaseDetailView.test.tsx
git commit -m "feat(parser-eval): inline grid-editor edit mode on case page"
```

---

## Task 9: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Backend parser-eval suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/ -k parser_eval -v`
Expected: PASS.

- [ ] **Step 2: Frontend parser-eval suite**

Run: `cd frontend && npx vitest run src/components/parser-eval`
Expected: PASS.

- [ ] **Step 3: Frontend lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors.

- [ ] **Step 4: Manual smoke (documented, run if a stack is up)**

1. Open a draft table case at `/evaluation/parser/cases/:id` → click **Edit**.
2. Change a cell, **Add row**, select two adjacent cells (shift-click) → **Merge**, **Split** it back.
3. **Add table**, set its page, reorder with ↑/↓, delete it.
4. **Save** → case stays `draft`; reopen edit, **Save & Accept** → badge shows `verified`.
5. Start a run including the case → `teds`/`table_recall` reflect the edited ground truth.

---

## Self-Review

**Spec coverage:**
- Full merge/split editor → Tasks 6, 7. ✓
- FE-owned html↔grid, canonical serializer matching `table_to_html` → Task 5 (+ format-match test). ✓
- Backend sanitize + shallow validation + `PUT` replacing `expected`, always draft → Tasks 1–4. ✓
- Save / Save & Accept / verified→draft-on-edit → Tasks 2 (repo reset), 8 (hook + UI). ✓
- Table-set management (add/delete/reorder/page) → Task 8 (`TableCaseEditor`). ✓
- Inline edit, no new route; retire sanitize TODO → Task 8. ✓
- Size caps, allowlist, `nh3` dep → Tasks 1, 3, 4. ✓
- Out of scope (bootstrap-to-text, from-scratch case) → not implemented. ✓

**Placeholder scan:** none — every code step carries full code.

**Type consistency:** `TableModel`/`AnchorCell`/`Slot` defined in Task 5 and used consistently in Tasks 6–8; `replaceCaseTables` signature `(projectId, caseId, tables)` matches its hook consumer and the Task 8 test assertion (`calls.at(-1)![2]` = the tables arg). `saveTables(tables, opts?)` matches `onSave` in `TableCaseEditor`. Backend `replace_case_tables(case_id, data)` matches the route call.
