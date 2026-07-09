# Parser Eval — Table Diagnostics + Robust Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Match ground-truth tables to parsed tables by page + content (order-independent), emit `teds_struct` and `cell_content_f1` diagnostics alongside `teds`, and surface a per-table structure-vs-content breakdown on run detail.

**Architecture:** A new pure `table_match` module buckets tables by page and greedily pairs them by TEDS. `teds.py` gains a `structure_only` flag and a `cell_content_f1` function. `score_table` is rewritten to match, then compute three metrics per matched pair (size-weighted aggregate) plus an enriched `details.per_table`. Frontend adds two metric columns and an expandable per-table diagnostics row. No schema or `expected`-shape change.

**Tech Stack:** Backend — Python 3.12, `apted` (existing), pytest on SQLite. Frontend — React 18, TypeScript, shadcn/ui, Vitest + Testing Library (happy-dom).

## Global Constraints

- **No schema / migration / `expected`-shape change.** `expected.tables[]` stays `{page, html}`; results keep the free-form `metrics` map + `details` JSON.
- **`emits` for `table` becomes** `("teds", "teds_struct", "cell_content_f1", "table_recall")`; **primary stays `teds`**.
- **Aggregation** for `teds`, `teds_struct`, `cell_content_f1`: size-weighted mean, weight = `max(cell_count(gt), cell_count(parsed), 1)`; unmatched tables contribute 0. `table_recall` unchanged: `min(parsed, expected)/expected` (`expected==0` → 1.0 if none parsed else 0.0).
- **Page convention:** GT `page` is 1-based; `extract_cdm_tables` returns 0-based `page_index`. The matcher normalises parsed to 1-based (`page_index + 1`). `Block.page_index` is required; GT `page` is required — bucketing is always defined.
- **Bbox is not used** (GT has no coordinates; scoring is GT-vs-one-parser). Matching is page + content only.
- **Scope:** `table` dimension only. No change to `text` dimension, authoring, bootstrap, or the grid editor. No thresholds/profiles (deferred Judgment layer).
- **Test commands:** backend `cd backend && uv run python -m pytest -o "addopts=" <path> -v`; frontend `cd frontend && npx vitest run <path>` (run from the `frontend` dir).

---

## File Structure

**Backend**
- Modify `backend/app/services/parser_eval/scorers/teds.py` — add `structure_only` flag + `cell_content_f1`.
- Create `backend/app/services/parser_eval/scorers/table_match.py` — page+content matcher.
- Modify `backend/app/services/parser_eval/scorers/table.py` — rewrite `score_table`.
- Modify `backend/app/services/parser_eval/scorers/__init__.py` — update `emits`.
- Tests: additions to `backend/tests/services/parser_eval/test_teds.py`, `test_table_scorer.py`; new `test_table_match.py`.

**Frontend**
- Modify `frontend/src/components/parser-eval/ParserComparisonTable.tsx` — columns + expandable per-table diagnostics.
- Test: additions to `frontend/src/components/parser-eval/ParserComparisonTable.test.tsx`.

---

## Task 1: TEDS structure-only flag + cell_content_f1

**Files:**
- Modify: `backend/app/services/parser_eval/scorers/teds.py`
- Test: `backend/tests/services/parser_eval/test_teds.py`

**Interfaces:**
- Consumes: existing `_parse`, `_normalize`, `_count`, `_Node`, `APTED`, `_TedsConfig`.
- Produces:
  - `teds(html_a: str, html_b: str, *, structure_only: bool = False) -> float`
  - `cell_content_f1(html_a: str, html_b: str) -> float`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/parser_eval/test_teds.py`:

```python
from app.services.parser_eval.scorers.teds import cell_content_f1


def test_structure_only_ignores_text():
    changed = _T.replace("<td>3</td>", "<td>999</td>").replace("<td>Item</td>", "<td>zzz</td>")
    assert teds(_T, changed, structure_only=True) == 1.0
    assert teds(_T, changed) < 1.0


def test_structure_only_penalizes_grid_change():
    dropped_col = "<table><tr><td>Item</td></tr><tr><td>Widget</td></tr></table>"
    assert teds(_T, dropped_col, structure_only=True) < 1.0


def test_cell_content_f1_identical():
    assert cell_content_f1(_T, _T) == 1.0


def test_cell_content_f1_structure_independent():
    flat = ("<table><tr><td>Item</td></tr><tr><td>Qty</td></tr>"
            "<tr><td>Widget</td></tr><tr><td>3</td></tr></table>")
    assert cell_content_f1(_T, flat) == 1.0


def test_cell_content_f1_disjoint_is_zero():
    other = "<table><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></table>"
    assert cell_content_f1(_T, other) == 0.0


def test_cell_content_f1_one_empty_is_zero():
    assert cell_content_f1(_T, "<table></table>") == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_teds.py -k "structure_only or cell_content_f1" -v`
Expected: FAIL — `ImportError: cannot import name 'cell_content_f1'`.

- [ ] **Step 3: Add `structure_only` to `_TedsConfig` and `teds`**

In `backend/app/services/parser_eval/scorers/teds.py`, replace the `_TedsConfig` class and `teds` function with:

```python
class _TedsConfig(Config):
    def __init__(self, structure_only: bool = False):
        self.structure_only = structure_only

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
        if self.structure_only:
            return 0.0
        if node1.tag in ("td", "th") and node1.text != node2.text:
            return 1.0 - difflib.SequenceMatcher(None, node1.text, node2.text).ratio()
        return 0.0


def teds(html_a: str, html_b: str, *, structure_only: bool = False) -> float:
    tree_a, tree_b = _parse(html_a), _parse(html_b)
    denom = max(_count(tree_a), _count(tree_b))
    if denom == 0:
        return 1.0
    distance = APTED(tree_a, tree_b, _TedsConfig(structure_only)).compute_edit_distance()
    return max(0.0, 1.0 - distance / denom)
```

- [ ] **Step 4: Add `cell_content_f1`**

Add `from collections import Counter` to the imports at the top of `teds.py`, then append at the end of the file:

```python
def _cell_texts(html: str) -> Counter:
    root = _parse(html)  # _parse already normalizes each cell's text
    return Counter(cell.text for row in root.children for cell in row.children
                   if cell.tag in ("td", "th"))


def cell_content_f1(html_a: str, html_b: str) -> float:
    a, b = _cell_texts(html_a), _cell_texts(html_b)
    total = sum(a.values()) + sum(b.values())
    if total == 0:
        return 1.0
    if not a or not b:
        return 0.0
    intersection = sum((a & b).values())  # multiset intersection
    return 2 * intersection / total
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_teds.py -v`
Expected: PASS (existing + 6 new).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/parser_eval/scorers/teds.py backend/tests/services/parser_eval/test_teds.py
git commit -m "feat(parser-eval): teds structure_only flag + cell_content_f1"
```

---

## Task 2: Page + content table matcher

**Files:**
- Create: `backend/app/services/parser_eval/scorers/table_match.py`
- Test: `backend/tests/services/parser_eval/test_table_match.py`

**Interfaces:**
- Consumes: `teds` (Task 1).
- Produces: `match_tables(expected: list[dict], parsed: list[tuple[int, str]]) -> list[tuple[int | None, int | None]]` — returns `(expected_index, parsed_index)` pairs: matched pairs and missing GT tables (`(i, None)`) in `expected_index` order, then extra parsed tables (`(None, j)`) in `parsed_index` order.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/services/parser_eval/test_table_match.py`:

```python
from app.services.parser_eval.scorers.table_match import match_tables

A = "<table><tr><td>a</td><td>b</td></tr></table>"
B = "<table><tr><td>c</td><td>d</td></tr></table>"


def test_identity_order():
    expected = [{"page": 1, "html": A}, {"page": 1, "html": B}]
    assert match_tables(expected, [(0, A), (0, B)]) == [(0, 0), (1, 1)]


def test_reversed_parsed_matches_by_content():
    expected = [{"page": 1, "html": A}, {"page": 1, "html": B}]
    assert match_tables(expected, [(0, B), (0, A)]) == [(0, 1), (1, 0)]


def test_missing_gt_table():
    expected = [{"page": 1, "html": A}, {"page": 1, "html": B}]
    assert match_tables(expected, [(0, A)]) == [(0, 0), (1, None)]


def test_extra_parsed_table():
    expected = [{"page": 1, "html": A}]
    assert match_tables(expected, [(0, A), (0, B)]) == [(0, 0), (None, 1)]


def test_pages_do_not_cross_match():
    # GT page 1, parsed page_index 2 -> page 3: different buckets, no match.
    assert match_tables([{"page": 1, "html": A}], [(2, A)]) == [(0, None), (None, 0)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_table_match.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the matcher**

Create `backend/app/services/parser_eval/scorers/table_match.py`:

```python
"""Match ground-truth tables to parsed tables by page bucket + content similarity.

Slice 3: replaces Slice 1's order-based matching. Within each page, greedily pair
the highest-TEDS GT/parsed tables; leftovers are missing (GT) or extra (parsed).
Page is the only locator shared by both sides — GT is authored HTML with no bbox.
"""
from __future__ import annotations

from app.services.parser_eval.scorers.teds import teds


def match_tables(expected: list[dict],
                 parsed: list[tuple[int, str]]) -> list[tuple[int | None, int | None]]:
    exp_by_page: dict[int, list[int]] = {}
    for i, t in enumerate(expected):
        exp_by_page.setdefault(int(t.get("page", 0)), []).append(i)
    par_by_page: dict[int, list[int]] = {}
    for j, (page_index, _html) in enumerate(parsed):
        par_by_page.setdefault(page_index + 1, []).append(j)

    matched: list[tuple[int, int]] = []
    used_exp: set[int] = set()
    used_par: set[int] = set()
    for page in sorted(set(exp_by_page) | set(par_by_page)):
        pairs = [(teds(expected[ei]["html"], parsed[pj][1]), ei, pj)
                 for ei in exp_by_page.get(page, [])
                 for pj in par_by_page.get(page, [])]
        pairs.sort(key=lambda p: (-p[0], p[1], p[2]))  # best first, deterministic ties
        for _score, ei, pj in pairs:
            if ei in used_exp or pj in used_par:
                continue
            used_exp.add(ei)
            used_par.add(pj)
            matched.append((ei, pj))

    result: list[tuple[int | None, int | None]] = [
        (i, next((p for e, p in matched if e == i), None)) for i in range(len(expected))
    ]
    result.extend((None, j) for j in range(len(parsed)) if j not in used_par)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_table_match.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parser_eval/scorers/table_match.py backend/tests/services/parser_eval/test_table_match.py
git commit -m "feat(parser-eval): page+content table matcher (order-independent)"
```

---

## Task 3: Rewrite `score_table` + register new metrics

**Files:**
- Modify: `backend/app/services/parser_eval/scorers/table.py`
- Modify: `backend/app/services/parser_eval/scorers/__init__.py`
- Test: `backend/tests/services/parser_eval/test_table_scorer.py`

**Interfaces:**
- Consumes: `match_tables` (Task 2); `teds`, `cell_content_f1`, `cell_count` (Task 1); `extract_cdm_tables` (existing).
- Produces: `score_table(cdm, expected) -> (metrics, details)` emitting `teds`, `teds_struct`, `cell_content_f1`, `table_recall`; `details.per_table[]` entries `{expected_index, parsed_index, page, status, teds, teds_struct, cell_content_f1}`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/services/parser_eval/test_table_scorer.py` — first update the registry assertion, then add new tests. Replace the body of `test_registered_in_scorers`:

```python
def test_registered_in_scorers():
    spec = get_scorer("table")
    assert spec.primary == "teds"
    assert set(spec.emits) == {"teds", "teds_struct", "cell_content_f1", "table_recall"}
```

Then append:

```python
def _doc_pages(tables):  # tables: list[(page_index, html)]
    blocks = [Block(id=f"b{i}", role=BlockRole.TABLE, native_type="table",
                    page_index=pi, reading_order=i, table=Table(rows=1, cols=2, cells=[], html=h))
              for i, (pi, h) in enumerate(tables)]
    return ParsedDocument(id="d", source_document_id="s", parse_run_id="r",
                          page_count=3, pages=[Page(index=0), Page(index=1), Page(index=2)],
                          blocks=blocks)


def test_extra_spurious_table_does_not_shift_matches():
    t1 = "<table><tr><td>a</td><td>b</td></tr></table>"
    t2 = "<table><tr><td>c</td><td>d</td></tr></table>"
    spurious = "<table><tr><td>zzz</td></tr></table>"
    expected = {"tables": [{"page": 1, "html": t1}, {"page": 1, "html": t2}]}
    doc = _doc(Table(rows=1, cols=2, cells=[], html=t1),
               Table(rows=1, cols=1, cells=[], html=spurious),
               Table(rows=1, cols=2, cells=[], html=t2))
    _metrics, details = score_table(doc, expected)
    matched = [e for e in details["per_table"] if e["status"] == "matched"]
    assert len(matched) == 2
    assert all(e["teds"] == 1.0 for e in matched)


def test_emits_structure_and_content_axes():
    gt = "<table><tr><td>Item</td><td>Qty</td></tr><tr><td>Widget</td><td>3</td></tr></table>"
    text_wrong = "<table><tr><td>xxx</td><td>yyy</td></tr><tr><td>zzz</td><td>9</td></tr></table>"
    doc = _doc(Table(rows=2, cols=2, cells=[], html=text_wrong))
    metrics, _ = score_table(doc, {"tables": [{"page": 1, "html": gt}]})
    assert metrics["teds_struct"] == 1.0
    assert metrics["cell_content_f1"] < 0.5


def test_details_per_table_carries_axes_and_status():
    doc = _doc(Table(rows=2, cols=2, cells=[], html=_HTML))
    _metrics, details = score_table(doc, {"tables": [{"page": 1, "html": _HTML}]})
    entry = details["per_table"][0]
    assert entry["status"] == "matched"
    assert entry["page"] == 1
    assert entry["expected_index"] == 0 and entry["parsed_index"] == 0
    assert entry["teds"] == 1.0 and entry["teds_struct"] == 1.0 and entry["cell_content_f1"] == 1.0


def test_cross_page_matching():
    t1 = "<table><tr><td>a</td></tr></table>"
    t2 = "<table><tr><td>b</td></tr></table>"
    expected = {"tables": [{"page": 1, "html": t1}, {"page": 2, "html": t2}]}
    doc = _doc_pages([(0, t1), (1, t2)])
    metrics, _ = score_table(doc, expected)
    assert metrics["teds"] == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_table_scorer.py -v`
Expected: FAIL — new metrics/details fields absent; registry assertion mismatch.

- [ ] **Step 3: Update the registry**

In `backend/app/services/parser_eval/scorers/__init__.py`, replace the `"table"` entry:

```python
    "table": ScorerSpec(fn=score_table,
                        emits=("teds", "teds_struct", "cell_content_f1", "table_recall"),
                        primary="teds"),
```

- [ ] **Step 4: Rewrite `score_table`**

Replace the entire contents of `backend/app/services/parser_eval/scorers/table.py` with:

```python
"""Table scorer — matches GT tables to parsed tables by page+content, then scores each pair.

Emits `teds` (primary), `teds_struct` (structure-only), `cell_content_f1` (content-only),
and `table_recall`. Aggregates the TEDS-family metrics as a size-weighted mean over matched
pairs; unmatched tables (missing or extra) contribute 0. Matching is order-independent
(Slice 3), replacing Slice 1's positional matching.
"""
from __future__ import annotations

from typing import Any

from app.cdm.models import ParsedDocument
from app.services.parser_eval.scorers.table_match import match_tables
from app.services.parser_eval.scorers.teds import cell_content_f1, cell_count, teds
from app.services.parser_eval.table_html import extract_cdm_tables

_ZERO = {"teds": 0.0, "teds_struct": 0.0, "cell_content_f1": 0.0}


def score_table(cdm: ParsedDocument, expected: dict[str, Any]) -> tuple[dict[str, float], dict]:
    expected_tables = expected.get("tables", [])
    parsed = extract_cdm_tables(cdm)  # list[(page_index, html)]
    pairs = match_tables(expected_tables, parsed)

    per_table: list[dict[str, Any]] = []
    acc = {"teds": 0.0, "teds_struct": 0.0, "cell_content_f1": 0.0}
    total_weight = 0.0
    for ei, pj in pairs:
        gt_html = expected_tables[ei]["html"] if ei is not None else None
        par_html = parsed[pj][1] if pj is not None else None
        if ei is not None and pj is not None:
            scores = {"teds": teds(gt_html, par_html),
                      "teds_struct": teds(gt_html, par_html, structure_only=True),
                      "cell_content_f1": cell_content_f1(gt_html, par_html)}
            status = "matched"
            page = int(expected_tables[ei].get("page", 0))
        elif ei is not None:
            scores, status = dict(_ZERO), "missing"
            page = int(expected_tables[ei].get("page", 0))
        else:
            scores, status = dict(_ZERO), "extra"
            page = parsed[pj][0] + 1

        weight = max(cell_count(gt_html) if gt_html else 0,
                     cell_count(par_html) if par_html else 0, 1)
        for k in acc:
            acc[k] += scores[k] * weight
        total_weight += weight
        per_table.append({"expected_index": ei, "parsed_index": pj, "page": page,
                          "status": status, **scores})

    if total_weight:
        metrics = {k: acc[k] / total_weight for k in acc}
    else:
        metrics = {"teds": 1.0, "teds_struct": 1.0, "cell_content_f1": 1.0}

    expected_count = len(expected_tables)
    parsed_count = len(parsed)
    if expected_count == 0:
        metrics["table_recall"] = 1.0 if parsed_count == 0 else 0.0
    else:
        metrics["table_recall"] = min(parsed_count, expected_count) / expected_count

    details = {"per_table": per_table,
               "expected_count": expected_count, "parsed_count": parsed_count}
    return metrics, details
```

- [ ] **Step 5: Run the full parser-eval scorer + registry tests**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_table_scorer.py -v`
Expected: PASS (existing 7 kept green + 4 new).

- [ ] **Step 6: Run the full parser-eval backend suite (no regressions)**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/ -k parser_eval`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/parser_eval/scorers/table.py backend/app/services/parser_eval/scorers/__init__.py backend/tests/services/parser_eval/test_table_scorer.py
git commit -m "feat(parser-eval): order-independent scoring + teds_struct/cell_content_f1 diagnostics"
```

---

## Task 4: Frontend — diagnostic columns + per-table drill-down

**Files:**
- Modify: `frontend/src/components/parser-eval/ParserComparisonTable.tsx`
- Test: `frontend/src/components/parser-eval/ParserComparisonTable.test.tsx`

**Interfaces:**
- Consumes: `ParserEvalResult.metrics` (`teds_struct`, `cell_content_f1`) and `ParserEvalResult.details.per_table` (Task 3).
- Produces: table-dimension comparison rows with Structure/Content columns and an expandable per-table diagnostics row.

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/components/parser-eval/ParserComparisonTable.test.tsx` (inside the `describe`), and add `fireEvent` to the testing-library import (`import { render, screen, within, fireEvent } from '@testing-library/react'`):

```tsx
it('shows structure/content columns and expands per-table diagnostics for a table case', () => {
  const r = one({
    metrics: { teds: 0.9, teds_struct: 1.0, cell_content_f1: 0.8, table_recall: 1 },
    primaryMetric: 'teds',
    details: {
      per_table: [{ expected_index: 0, parsed_index: 0, page: 3, status: 'matched',
        teds: 0.9, teds_struct: 1.0, cell_content_f1: 0.8 }],
      expected_count: 1, parsed_count: 1,
    },
  })
  render(<ParserComparisonTable results={[r]} caseLabels={{ c1: 'a.pdf' }}
    caseDimensions={{ c1: 'table' }} />)
  expect(screen.getByText('Structure')).toBeInTheDocument()
  expect(screen.getByText('Content')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /diagnostics/i }))
  expect(screen.getByText(/page 3/i)).toBeInTheDocument()
  expect(screen.getByText(/matched/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/parser-eval/ParserComparisonTable.test.tsx`
Expected: FAIL — no Structure/Content columns, no diagnostics button.

- [ ] **Step 3: Add the two columns**

In `frontend/src/components/parser-eval/ParserComparisonTable.tsx`, replace the `table` entry of `METRIC_COLUMNS`:

```ts
  table: {
    primary: { key: 'teds', label: 'TEDS' },
    rest: [
      { key: 'teds_struct', label: 'Structure' },
      { key: 'cell_content_f1', label: 'Content' },
      { key: 'table_recall', label: 'Table recall' },
    ],
  },
```

- [ ] **Step 4: Add the expandable per-table diagnostics**

In the same file: add `Fragment` and `useState` to the React import (`import { Fragment, useState } from 'react'`), and a `PerTable` type + expansion state. Replace the component body so each table-dimension row carries a toggle and an optional detail row.

Add near the top (after the imports):

```tsx
interface PerTable {
  expected_index: number | null
  parsed_index: number | null
  page: number | null
  status: string
  teds: number
  teds_struct: number
  cell_content_f1: number
}
```

Inside `ParserComparisonTable`, add expansion state right after the `byCase` map is built:

```tsx
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const toggle = (key: string) => setExpanded((prev) => {
    const next = new Set(prev)
    next.has(key) ? next.delete(key) : next.add(key)
    return next
  })
```

Replace the `<TableRow key={r.variantKey} ...>` block (the mapped variant row) with a fragment that renders the row plus an optional diagnostics row:

```tsx
                {sorted.map((r) => {
                  const perTable = (r.details?.per_table as PerTable[] | undefined) ?? []
                  const canExpand = dimension === 'table' && perTable.length > 0
                  const isOpen = expanded.has(r.variantKey)
                  const colSpan = 2 + cols.rest.length + 2
                  return (
                    <Fragment key={r.variantKey}>
                      <TableRow data-testid="cmp-row">
                        <TableCell>
                          {canExpand && (
                            <button type="button" aria-label="Toggle diagnostics"
                              className="mr-1 text-muted-foreground hover:text-foreground"
                              onClick={() => toggle(r.variantKey)}>{isOpen ? '▾' : '▸'}</button>
                          )}
                          {adapterLabel(r.adapter)}
                        </TableCell>
                        <TableCell><ScorePill score={r.metrics[cols.primary.key] ?? null} /></TableCell>
                        {cols.rest.map((c) => <TableCell key={c.key}>{pct(r.metrics[c.key])}</TableCell>)}
                        <TableCell>{fmtCost(r.cost)}</TableCell>
                        <TableCell>{fmtLatency(r.latencyMs)}</TableCell>
                      </TableRow>
                      {canExpand && isOpen && (
                        <TableRow>
                          <TableCell colSpan={colSpan} className="bg-muted/30">
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="text-muted-foreground">
                                  <th className="py-1 text-left">Table</th>
                                  <th className="text-left">TEDS</th>
                                  <th className="text-left">Structure</th>
                                  <th className="text-left">Content</th>
                                </tr>
                              </thead>
                              <tbody>
                                {perTable.map((t, i) => (
                                  <tr key={i}>
                                    <td className="py-1">Page {t.page ?? '—'} · {t.status}</td>
                                    <td>{pct(t.teds)}</td>
                                    <td>{pct(t.teds_struct)}</td>
                                    <td>{pct(t.cell_content_f1)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  )
                })}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/parser-eval/ParserComparisonTable.test.tsx`
Expected: PASS (existing 3 + new 1).

- [ ] **Step 6: Lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors. (If lint flags the ternary in `toggle` as an unused-expression, convert it to an `if/else`.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/parser-eval/ParserComparisonTable.tsx frontend/src/components/parser-eval/ParserComparisonTable.test.tsx
git commit -m "feat(parser-eval): structure/content columns + per-table diagnostics drill-down"
```

---

## Task 5: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Backend parser-eval suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/ -k parser_eval`
Expected: PASS.

- [ ] **Step 2: Frontend parser-eval suite**

Run: `cd frontend && npx vitest run src/components/parser-eval`
Expected: PASS.

- [ ] **Step 3: Frontend lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors.

- [ ] **Step 4: Manual smoke (documented; run if a stack is up)**

1. Run a table-dimension case across ≥2 parser variants.
2. On run detail, confirm the table comparison shows TEDS / Structure / Content / Table recall columns.
3. Expand a variant row → per-table breakdown lists each ground-truth table with page, status, and the three scores.
4. Sanity: a parser that emits an extra/misordered table still scores its real tables correctly (no order penalty).

---

## Self-Review

**Spec coverage:**
- Page-bucketed content-similarity matching, bbox dropped → Task 2. ✓
- `teds_struct` (structure_only), `cell_content_f1` (multiset F1) → Task 1. ✓
- `score_table` emits 4 metrics, size-weighted aggregate, enriched `details.per_table` → Task 3. ✓
- Registry `emits` update, primary `teds` → Task 3. ✓
- FE Structure/Content columns + per-table drill-down → Task 4. ✓
- Page convention (1-based GT vs 0-based page_index) → Task 2 matcher + Task 3 `page` derivation. ✓
- `table_recall` unchanged → Task 3. ✓
- Out of scope (text dimension, authoring, thresholds, bbox) → untouched. ✓

**Placeholder scan:** none — every code step carries full code.

**Type consistency:** `match_tables(expected, parsed) -> list[tuple[int|None, int|None]]` defined in Task 2 and consumed in Task 3 with matching destructuring `for ei, pj in pairs`. `teds(..., structure_only=...)` and `cell_content_f1(a, b)` defined in Task 1 and used in Task 3. FE `PerTable` fields (`page`, `status`, `teds`, `teds_struct`, `cell_content_f1`) match the backend `details.per_table` entry keys from Task 3. `cols.rest.length` used for `colSpan` matches the 3-entry `rest` added in Task 4 Step 3.
