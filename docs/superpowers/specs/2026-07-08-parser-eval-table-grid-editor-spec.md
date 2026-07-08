# Parser Eval — Slice 2: Table Grid Editor

**Date:** 2026-07-08
**Status:** Draft for review
**Author:** brainstorming session (asanyaga)
**Feature branch:** `feat/parser-eval-table-grid-editor` (suggested)
**Parent design:** [Parser Eval — Table Dimension Design](2026-07-07-parser-eval-table-dimension-design.md) (Slice 2)
**Builds on:** Slice 1 (merged, PR #151) — bootstrap-default table authoring, `teds`/`table_recall` scoring,
case-as-a-page (`/evaluation/parser/cases/:id`), `CaseDetailView` read-only draft review.

---

## Purpose

Slice 1 lets a user *bootstrap* draft table ground truth from a trusted parser and accept or reject it
wholesale. It gives no way to **correct** what the parser got wrong. Since the ground truth is the
reference every parser is TEDS-scored against, an uncorrected bootstrap means scoring against a
possibly-wrong table — the metric is only as trustworthy as the reference.

Slice 2 delivers a **table grid editor**: open a draft table case, fix cell text, add/remove rows and
columns, merge/split cells, mark header cells, and correct the *set* of tables (add a missed table,
delete a hallucinated one). Save persists the corrected ground truth; a human then verifies it. The
result is ground truth the user actually trusts.

---

## Scope

Slice 2 is delivered end-to-end (backend + frontend) as a single, self-contained unit: **the table
grid editor and its save/verify round-trip.**

### Decisions locked in brainstorming (2026-07-08)

1. **Full merge/split editor.** The grid editor supports editing cell text, adding/removing rows and
   columns, **merging and splitting cells** (`colspan`/`rowspan`), and toggling header cells. Merge
   fidelity is a *metric-validity* requirement, not a nicety: TEDS is structure-aware, so a ground
   truth that cannot represent a merged header would penalise parsers that correctly emit the merge —
   on exactly the hard tables (grouped/spanning headers) that justify the table dimension. The
   dominant implementation cost is the spanned-grid data model, which any fidelity-preserving option
   pays anyway; merge/split is a small additive layer on top of it.
2. **Bootstrap-correct-first; from-scratch *case* creation deferred.** A table case is still *created*
   by bootstrapping a trusted parser (Slice 1). Slice 2 corrects that draft. Authoring a brand-new
   table case with no bootstrap is deferred (low value — nobody hand-builds a merged table from a
   blank grid; they fix a parse). Note this differs from *adding a blank table within an existing
   case*, which **is** in scope (see below).
3. **Frontend owns `html ↔ grid` conversion.** Canonical storage stays HTML
   (`expected.tables[].html`) so the scorer, engine, and text dimension are untouched. The browser
   parses HTML tables natively and robustly (`DOMParser` + `HTMLTableCellElement.rowSpan/colSpan`), so
   both directions live in the frontend, next to the editor, with no new backend HTML-parsing
   dependency and no dual parsers. This narrows the parent design's "Backend: HTML ↔ grid round-trip"
   line — the backend does **not** round-trip; it guards (see #4).
4. **Backend guards, doesn't convert.** A new `PUT .../cases/{id}` replaces `expected`. On save the
   backend **sanitises** each table's HTML against a tight allowlist and does a **shallow** structural
   check (parses, contains a table, non-empty, within size bounds). It does not reconstruct the grid.
   Sanitisation also retires the standing `// Follow-up: sanitize (Slice 2)` TODO in `CaseDetailView`:
   stored HTML becomes trusted-by-construction before it is ever `dangerouslySetInnerHTML`'d.
5. **`PUT` always resets `review_status` to `draft`; verify stays an explicit `PATCH`.** Invariant,
   enforced server-side: *"verified" means a human approved exactly the current content.* Editing a
   verified case drops it back to draft. This deliberately supersedes the parent design's "verify on
   save" phrasing; the one-click convenience is preserved in the UI as **Save & Accept** (a `PUT`
   followed by the existing verify `PATCH`), but the backend primitive stays clean.
6. **Table-set management on the case page.** Cell editing cannot fix a wrong *set* of tables (a missed
   or hallucinated table corrupts `table_recall` and order-based matching). The page provides add
   table / delete table / per-table page number / move up-down, around the per-table grid editors.
7. **Inline edit mode, no new route.** Editing happens inline on the existing case page
   (`/evaluation/parser/cases/:id`), preserving the draft's deep-linkable home. Entering Edit swaps
   the Slice 1 read-only render for the editor.

### Narrowing of the parent design (surfaced explicitly)

The parent design's Slice 2 also listed **"bootstrapping generalises beyond `table`"** (e.g. text) and
**"optional/manual authoring for every dimension."** Both are **deferred out of Slice 2**:

- **Bootstrap-to-text is deferred.** It is independent of the grid editor, its value is lower (it only
  pre-fills the per-page textareas that already exist and work), and deferring has no lock-in cost —
  generalising `POST .../cases/bootstrap-table` to a dimension-parameterised endpoint is a trivial
  isolated refactor whenever wanted. It moves to a later slice.
- **From-scratch table-case authoring is deferred** (decision #2).

### Non-goals

- Bootstrap for non-table dimensions; from-scratch table-case creation (both deferred above).
- Diagnostic metrics (`teds_struct`, `cell_content_f1`) and position/overlap-based multi-table
  matching — still Slice 3. Order remains scoring-significant in Slice 2 (hence move up/down).
- Judgment/Selection (thresholds, pass/fail, profiles) — seam #5, deferred for all dimensions.
- Rich text inside cells, cell-level styling, nested tables, captions editing.

---

## Data model — no changes

Storage shape is unchanged from Slice 1:

```json
{ "tables": [ { "page": 3, "html": "<table>…</table>" } ] }
```

No new columns, no new `cells` field on the wire or in the DB. The scorer keeps reading
`expected.tables[].html`; the text dimension is untouched. The grid is a *transient* frontend
representation, never persisted.

---

## Frontend

### Grid model (transient, editor-only)

A **spanned-grid** matrix. Each logical position `grid[r][c]` is either an **anchor** cell or a
**covered** marker referencing its anchor (the second column of a `colspan=2` cell is covered):

```ts
interface EditorCell {
  text: string
  isHeader: boolean
  rowspan: number   // ≥ 1
  colspan: number   // ≥ 1
}
// grid[r][c] = { kind: 'anchor', cell: EditorCell } | { kind: 'covered', anchor: [number, number] }
```

Header cells → `<th>`, others → `<td>`. This mirrors the CDM `Cell` shape
(`row/col/rowspan/colspan/text/is_header`) so it reads naturally to anyone who knows the parser output.

### Conversion (`frontend/src/components/parser-eval/tableGrid.ts`)

- **`htmlToGrid(html: string): Grid`** — parse via `DOMParser`, walk `<tr>` rows placing each `<td>/<th>`
  into the next free position while honouring `rowSpan`/`colSpan` and skipping occupied positions
  (the standard HTML table grid algorithm). Ragged/overlapping input is normalised to a rectangular
  matrix; unknown tags/attributes are ignored (defence-in-depth alongside backend sanitisation).
- **`gridToHtml(grid: Grid): string`** — emit **flat** `<table>` with `<tr>` rows; per anchor emit
  `<th>`/`<td>` with `colspan`/`rowspan` attributes **only when > 1**; skip covered positions; escape
  text. **Output must byte-for-byte match the backend `table_to_html` convention** (flat rows, no
  `thead`/`tbody`, attribute-only-when-≠1) so ground-truth HTML and parsed HTML are directly
  TEDS-comparable and canonical.

Both are pure functions, unit-tested independently of React.

### Grid operations (pure, in `tableGrid.ts`)

Each returns a new grid; each preserves rectangularity and span consistency:

- **Edit text / toggle header** — mutate the anchor at a position.
- **Add / remove row** — insert or delete a logical row; spans that *cross* the boundary are
  incremented (insert) or clipped/decremented (remove); an anchor whose span collapses to 0 is deleted.
- **Add / remove column** — symmetric to rows.
- **Merge** — given a rectangular selection `(r1..r2, c1..c2)`: **validate** the selection is a clean
  rectangle whose members are all 1×1 anchors (reject partial overlap with an existing span). Collapse
  to a single anchor with `rowspan=r2-r1+1`, `colspan=c2-c1+1`; concatenate member texts (space-joined,
  order by row then col); mark the rest covered.
- **Split** — an anchor with `rowspan>1 or colspan>1` → restore the covered positions to 1×1 anchors
  (empty text); origin keeps its text.

Validation failures surface as inline messages; they never produce an inconsistent grid.

### Editor component (`TableGridEditor.tsx`)

Renders the grid as an HTML `<table>` of focusable cells (text `<input>`/`contentEditable` per anchor),
a toolbar (Add row, Add column, Merge, Split, Toggle header, Delete row, Delete column), and cell/range
selection (click, shift-click to extend a rectangle for merge). shadcn/Tailwind, hand-rolled — no table
library, consistent with the codebase.

### Case page changes (`CaseDetailView.tsx`)

`CaseDetailView` gains **view** and **edit** modes for `dimension === 'table'`:

- **View (unchanged from Slice 1)** — read-only render of each table (now sanitised at source), page
  labels, `EvalStatusBadge`. Draft cases add an **Edit** button beside Accept / Reject.
- **Edit** — a `TableCaseEditor` sub-view: a list of tables, each with a page-number field, **move
  up/down**, **delete**, and an embedded `TableGridEditor`. An **Add table** button appends a blank
  1×1 grid on a new page. Footer actions:
  - **Save** — `PUT` the tables; case returns to (or stays) `draft`.
  - **Save & Accept** — `PUT`, then the existing verify `PATCH` → `verified`.
  - **Cancel** — discard local edits, return to view.

The `text` dimension render path is unchanged.

### API + hook

- `frontend/src/api/parserEval.ts`: add `replaceCaseTables(projectId, caseId, tables)` → `PUT`.
- `useParserEvalCase` (`useParserEval.ts`): add a `saveTables(tables, { verify }: {...})` action that
  calls `replaceCaseTables` and, when `verify`, chains the existing `verify()`; refresh `caseDetail`
  from the response.
- Types (`types/parserEval.ts`): reuse `TableGroundTruth` for the `PUT` body.

### Sanitisation of rendered HTML

The view-mode `dangerouslySetInnerHTML` is now safe because HTML is sanitised on write (below). No
client-side sanitiser is added; the `// Follow-up: sanitize (Slice 2)` comment is removed.

---

## Backend

### Endpoint — replace expected

`PUT /projects/{project_id}/parser-eval/cases/{case_id}` (`routers/parser_eval.py`), body
`CaseExpectedUpdate` = `{ tables: [ { page: int, html: str } ] }` (camelCase, reuses the Slice 1 table
shape). Router → service; catches `NotFoundError` (404) and `ValidationError` (400). Returns
`CaseDetailResponse`. Only valid for `dimension == 'table'` in Slice 2 (text replacement stays via the
existing create path / is out of scope) — a text case → `ValidationError`.

### Schema (`schemas/parser_eval.py`)

```python
class CaseExpectedUpdate(BaseModel):
    tables: list[TableGT]              # non-empty; each TableGT = { page: int, html: str }
    model_config = _CAMEL
```

Reuse/lift the per-table validation already in `CaseCreate._validate_expected` (each table needs an
`html: str`). Cap counts as a paste/DoS guard: `≤ 50` tables per case, `≤ 2000` cells per table
(enforced post-sanitisation).

### Sanitisation — `services/parser_eval/table_html.py`

Add `sanitize_table_html(html: str) -> str`. **Allowlist only:**

- Tags: `table, thead, tbody, tr, td, th`.
- Attributes: `colspan`, `rowspan` (on `td`/`th`), `scope` (on `th`).
- Everything else (scripts, styles, event handlers, other tags/attrs) stripped; text content kept.

**Dependency:** add **`nh3`** (`uv add nh3` — maintained Rust/ammonia bindings; `bleach` is
deprecated). If a new dependency is unwelcome, the fallback is a stdlib `html.parser`-based allowlist
filter, but a vetted sanitiser is strongly preferred for security-sensitive HTML. Contained to this one
helper.

### Service (`services/parser_eval/service.py`)

`replace_case_tables(case_id, data: CaseExpectedUpdate) -> CaseDetailResponse`:

1. Load case; `NotFoundError` if missing.
2. `ValidationError` if `dimension != table`.
3. For each table: `html = sanitize_table_html(t.html)`; **shallow-validate** the sanitised HTML —
   parses, contains a `<table>` with ≥ 1 cell, non-empty, within size caps; else `ValidationError`.
4. Persist `expected = { "tables": [ { "page", "html" } ] }` **and set `review_status = draft`** via a
   new repo method.

### Repository (`repositories/parser_eval_repository.py`)

`replace_case_expected(case_id, expected: dict) -> ParserEvalCase | None` — set `case.expected`,
`case.review_status = ParserEvalReviewStatus.draft`, commit, refresh (mirrors
`update_case_review_status`).

The verify transition reuses the existing `PATCH` / `set_case_review` / `update_case_review_status` —
no change.

---

## Testing

### Frontend (unit — the conversion/ops are pure and high-value)

- **`htmlToGrid` / `gridToHtml` round-trip:** flat table; header row; a `colspan` header over sub-columns;
  a `rowspan` cell; ragged input normalised. `gridToHtml(htmlToGrid(x))` is canonical and stable.
- **Format match:** `gridToHtml` output equals the `table_to_html` convention (attribute-only-when-≠1,
  flat rows, `<th>` for headers) for representative grids.
- **Grid ops:** add/remove row & column adjust crossing spans correctly; merge validates rectangular
  1×1-only selection and rejects partial-span overlap; split restores 1×1 anchors; header toggle.
- **Component (light, per FE test pragmatism):** edit → Save calls `PUT` with expected tables; Save &
  Accept chains verify; Add/Delete/Move table mutate the list.

### Backend

- **`sanitize_table_html`:** strips `<script>`/`onclick`/`style`; keeps `table/tr/td/th` +
  `colspan/rowspan/scope`; preserves text.
- **Service `replace_case_tables`:** persists sanitised tables and forces `review_status=draft` (even
  when the case was `verified`); non-table dimension → 400; empty/no-table/oversized html → 400;
  missing case → 404.
- **Router:** `PUT` happy path returns `CaseDetailResponse` with `draft`; auth/project-access enforced
  like sibling routes.

---

## Acceptance criteria

- From a draft table case, a user can open an inline grid editor and: edit cell text, add/remove rows
  and columns, merge a rectangular selection, split a merged cell, and toggle header cells.
- The user can correct the table *set*: add a table, delete a table, change a table's page, and reorder
  tables (move up/down).
- **Save** persists the corrected ground truth and leaves the case `draft`; **Save & Accept** persists
  and marks it `verified`; editing a `verified` case and saving returns it to `draft`.
- Saved HTML is sanitised server-side (no scripts/handlers survive) and round-trips through
  `htmlToGrid`/`gridToHtml` without structural loss, staying canonical and TEDS-comparable.
- A run over a case verified through the editor produces `teds`/`table_recall` reflecting the corrected
  ground truth (i.e. edits change scores), with tests proving the conversion and ops.

---

## Risks / open considerations

- **`gridToHtml` ↔ `table_to_html` format drift.** The two serialisers must agree, or ground-truth and
  parsed HTML diverge cosmetically and depress TEDS. Mitigation: a format-match test pinned to
  `table_to_html`'s convention; treat that convention as the contract.
- **Merge/split UX complexity.** Range selection over a spanned grid is the fiddliest UI. Mitigation:
  strict validation (merge only clean rectangular 1×1 selections), pure well-tested grid ops, and
  clear inline errors rather than silent corruption.
- **Order still matters (Slice 1 matching).** Move up/down exists solely because scoring matches the
  *i-th* expected to the *i-th* parsed table. Slice 3's position/overlap matching removes the
  sensitivity and this control's necessity.
- **New `nh3` dependency.** One small, well-maintained sanitiser, contained to `sanitize_table_html`.
  Stdlib-allowlist fallback exists but is discouraged for security-sensitive HTML.
- **Shallow backend validation.** Deep structural validity (no ragged rows, spans in bounds) is
  guaranteed by the FE editor, not re-verified server-side. Acceptable — ground truth is authored by a
  trusted human through the editor, not adversarial input. A backend `html→grid` validator can be added
  later for defence-in-depth if needed.

---

## What is explicitly NOT in this doc

- Exact React component tree, toolbar layout, and selection-interaction details — implementation plan.
- Migrations/DDL (none needed — no schema change).
- Bootstrap-to-text and from-scratch table-case authoring (deferred; later slice).
- Slice 3 (diagnostics + multi-table robustness) — its own spec.
