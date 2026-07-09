# Parser Eval — Slice 3: Table Diagnostics + Robust Matching

**Date:** 2026-07-09
**Status:** Draft for review
**Author:** brainstorming session (asanyaga)
**Feature branch:** `feat/parser-eval-table-diagnostics` (suggested)
**Parent design:** [Parser Eval — Table Dimension Design](2026-07-07-parser-eval-table-dimension-design.md) (Slice 3)
**Builds on:** Slice 1 (PR #151, TEDS scoring + bootstrap authoring) and Slice 2 (PR #153, grid editor).

---

## Purpose

Slice 1's table scorer answers *"how good is this parser's table extraction?"* with a single `teds`
number, but two problems blunt it:

1. **A low `teds` isn't diagnosable.** Is the parser getting the *grid shape* wrong (merged/split/missed
   cells) or the *text* wrong (OCR errors)? One number can't say.
2. **Order-based matching is unfair.** Slice 1 compares the i-th ground-truth table to the i-th parsed
   table. A parser that emits tables in a different order than authored is penalised for a difference
   that doesn't exist.

Slice 3 fixes both: **robust page-and-content matching** (so a table is compared to its true
counterpart regardless of extraction order) and **two diagnostic metrics** (`teds_struct`,
`cell_content_f1`) that decompose `teds` into a structure axis and a content axis, surfaced per-table on
run detail.

---

## Scope

Delivered end-to-end (backend + frontend) as one slice: robust matching, the two diagnostics, and the
run-detail diagnostic view.

### Decisions locked in brainstorming (2026-07-09)

1. **Matching = page-bucketed content-similarity assignment.** Bucket ground-truth and parsed tables by
   `page`; within each page, compute TEDS for every GT×parsed pair and greedily assign highest-TEDS
   pairs first (each table used once). Unmatched tables on either side score 0. Robust to extraction
   order (cross-page *and* within-page), uses only signals that reliably exist, and page-gating keeps
   it cheap and prevents cross-page mis-pairs.
2. **`teds_struct` (structure-only)** — TEDS with cell text blanked, so edit cost depends only on
   `tag`/`colspan`/`rowspan`. Implemented as a `structure_only` flag on the existing `teds()`.
3. **`cell_content_f1` (content-only)** — multiset F1 over normalised cell texts of a matched pair:
   `2·|GT ∩ parsed| / (|GT| + |parsed|)`, structure-independent. Multiset so duplicate values count
   faithfully. `1.0` if both empty, `0.0` if exactly one empty.
4. **`emits` becomes** `("teds", "teds_struct", "cell_content_f1", "table_recall")`; **primary stays
   `teds`**. Aggregation for all three TEDS-family metrics is unchanged from Slice 1 — size-weighted
   mean (weight = larger cell count of the pair), unmatched tables contribute 0.
5. **Frontend = aggregate columns + per-table drill-down.** Add `teds_struct` and `cell_content_f1`
   columns to the table-dimension comparison table, and an expandable per-(case, variant) breakdown
   listing each ground-truth table with its page, matched/missing status, and three scores.

### Correction to the parent design (surfaced explicitly)

The parent design said matching would use "`bbox`/`page` when available." **Bbox is not usable here and
is dropped from Slice 3.** The scoring unit is always *ground truth vs. one parser* (each variant scored
independently against the same GT), never parser-vs-parser. Ground truth is authored HTML carrying only
`{page, html}` — it has **no bounding boxes**. So the only cross-side signals are `page` (both sides)
and content similarity (TEDS). `Block.bbox` on the parsed side has no GT counterpart to overlap against,
so it plays no role. Matching is therefore page + content, not spatial.

### Non-goals

- Thresholds / pass-fail / weighted profiles on any metric — Judgment/Selection layer (seam #5),
  deferred for all dimensions. `table_recall` stays a coverage proxy (`min(parsed, expected)/expected`).
- Bbox/spatial matching (dropped — see above).
- Diagnostics for the `text` dimension — unchanged.
- Changes to authoring, bootstrap, or the grid editor (Slice 2).

---

## Data model — no changes

No schema, migration, or `expected` shape change. `expected.tables[]` stays `{page, html}`; results
still carry a free-form `metrics` map + `details` JSON. Slice 3 only changes what the scorer *computes*
and what the FE *renders*.

**Page convention (made explicit):** GT `page` is 1-based (bootstrap stored `page_index + 1`);
`extract_cdm_tables` returns 0-based `page_index`. The matcher normalises the parsed side to 1-based
(`page_index + 1`) so buckets line up. `Block.page_index` is a required field, so every parsed table has
a page; GT `page` is required by the schema — page-bucketing is always well-defined.

---

## Backend

### Matching — `backend/app/services/parser_eval/scorers/table_match.py` (new)

Small, pure, independently testable module.

`match_tables(expected: list[dict], parsed: list[tuple[int, str]]) -> list[tuple[int | None, int | None]]`

- `expected` is `expected.tables` (each `{page, html}`); `parsed` is the `(page_index, html)` list from
  `extract_cdm_tables`.
- Bucket both sides by 1-based page (`parsed` normalised via `page_index + 1`).
- For each page present in either bucket: compute `teds(gt_html, parsed_html)` for all pairs in that
  page, sort pairs by descending TEDS (tie-break by `(expected_index, parsed_index)` for determinism),
  and greedily assign — a pair is taken if both members are still free.
- Emit one tuple per matched pair `(expected_index, parsed_index)`, one per unmatched GT table
  `(expected_index, None)`, and one per unmatched parsed table `(None, parsed_index)`.
- Ordering of the returned list: matched/missing in `expected_index` order, then extras in
  `parsed_index` order (stable, for readable details).

The matcher computes TEDS only to *decide* pairing; `score_table` recomputes the three metrics for the
chosen pairs (the extra TEDS pass is negligible for realistic table counts).

### TEDS additions — `backend/app/services/parser_eval/scorers/teds.py`

- **`teds(html_a, html_b, *, structure_only: bool = False) -> float`** — new keyword flag threaded into
  `_TedsConfig(structure_only=...)`. When set, `rename` ignores cell text: returns `1.0` only when
  `tag`/`colspan`/`rowspan` differ, else `0.0` (no fractional text cost). Default `False` preserves
  current behaviour exactly.
- **`cell_content_f1(html_a, html_b) -> float`** — parse each side (reusing `_parse`, which already
  `_normalize`s text), collect a `Counter` of cell texts, compute multiset F1
  `2·Σ min(a[k], b[k]) / (Σa + Σb)`. `1.0` if both bags empty; `0.0` if exactly one is empty.

### Scorer rewrite — `backend/app/services/parser_eval/scorers/table.py`

`score_table(cdm, expected)` becomes:

1. `expected_tables = expected.get("tables", [])`; `parsed = extract_cdm_tables(cdm)`.
2. `pairs = match_tables(expected_tables, parsed)`.
3. For each pair compute per-table `teds`, `teds_struct` (`structure_only=True`), `cell_content_f1`
   (0 for any unmatched side). Weight = `max(cell_count(gt), cell_count(parsed), 1)` where a missing
   side counts as its present side's cells.
4. Aggregate each of `teds`, `teds_struct`, `cell_content_f1` as the size-weighted mean over all pairs.
5. `table_recall = min(len(parsed), len(expected_tables)) / len(expected_tables)` (unchanged;
   `expected == 0` → `1.0` when no tables parsed else `0.0`).
6. `metrics = {"teds", "teds_struct", "cell_content_f1", "table_recall"}`.
7. `details = {"per_table": [...], "expected_count", "parsed_count"}` where each `per_table` entry is:

   ```json
   {
     "expected_index": 0,        // null for an extra parsed table
     "parsed_index": 1,          // null for a missing GT table
     "page": 3,                  // GT page if matched/missing, else parsed page
     "status": "matched",        // "matched" | "missing" | "extra"
     "teds": 0.94,
     "teds_struct": 1.0,
     "cell_content_f1": 0.88
   }
   ```

### Registry — `backend/app/services/parser_eval/scorers/__init__.py`

```python
"table": ScorerSpec(fn=score_table,
                    emits=("teds", "teds_struct", "cell_content_f1", "table_recall"),
                    primary="teds"),
```

The engine needs no change — it persists whatever `metrics`/`details` the scorer returns.

---

## Frontend

### Comparison columns — `frontend/src/components/parser-eval/ParserComparisonTable.tsx`

Extend the `table` entry in `METRIC_COLUMNS`:

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

The generic metrics map renders these with the existing `pct()` treatment — no other change to the
aggregate table.

### Per-table drill-down (new)

Each variant row in the table dimension gains an expander. When expanded, render a compact sub-table
from `result.details.per_table`: one row per entry showing **page**, **status** (matched / missing /
extra badge), and **TEDS / Structure / Content** scores. This localises which ground-truth table is
dragging the aggregate down and shows the structure-vs-content split per table. Text-dimension rows have
no expander (their `details` shape is unchanged and out of scope).

Implementation: a small `TableDiagnosticsRow` (or inline expandable `<tr>`) inside
`ParserComparisonTable`, gated on `dimension === 'table'` and `result.details?.per_table`. Reuse
`ScorePill`/`pct` and the existing status-badge styling.

---

## Testing

### Backend

- **`match_tables`:** identical order → identity pairing; reversed parsed order → still pairs by
  content; a missing GT table → `(idx, None)`; an extra parsed table → `(None, idx)`; two tables on
  different pages don't cross-match; two tables on the same page pair by best TEDS.
- **`teds` structure_only:** identical tables → `1.0`; same grid but all cell text changed →
  `teds_struct == 1.0` while plain `teds < 1.0`; a merged/split cell (colspan change) → `teds_struct < 1`.
- **`cell_content_f1`:** identical cell bags → `1.0`; same texts in a totally different grid → `1.0`
  (structure-independent); disjoint texts → `0.0`; multiset duplicates counted; one-empty → `0.0`.
- **`score_table`:** reordered parsed tables now score the same as in-order (regression vs. Slice 1's
  order penalty); emits all four metrics; `details.per_table` carries indices, page, status, and three
  scores; missing/extra tables reflected in aggregate and in `per_table`.

### Frontend

- **`ParserComparisonTable`:** table-dimension rows show Structure and Content columns; expanding a row
  renders the per-table breakdown from `details.per_table` with page/status/scores; text-dimension rows
  are unchanged and have no expander. (Light coverage, per FE test pragmatism; happy-dom env.)

---

## Acceptance criteria

- A parser that extracts the correct tables in a different order than authored scores the same `teds` as
  one that extracts them in order (order no longer penalised), with a test proving it.
- `score_table` emits `teds`, `teds_struct`, `cell_content_f1`, and `table_recall`; `teds_struct`
  isolates structure (high when the grid is right regardless of text) and `cell_content_f1` isolates
  content (high when text is right regardless of grid), with tests proving each axis.
- `details.per_table` carries, per ground-truth (and extra parsed) table, its page, matched/missing/extra
  status, and the three scores.
- On run detail, the table comparison shows Structure and Content columns, and each variant row expands
  to a per-table breakdown surfacing which table is weak and on which axis.

---

## Risks / open considerations

- **Content-matching self-reference.** The matcher uses TEDS to choose pairings and then reports TEDS for
  those pairings — self-consistent, but two near-identical tables on one page could be paired differently
  than a human would. Low risk given page-gating and that such duplicates are rare; if it ever bites,
  a page+order tiebreaker within equal-TEDS pairs is an easy refinement.
- **Cost.** Matching computes TEDS for all same-page GT×parsed pairs, then `score_table` recomputes three
  metrics for chosen pairs. For realistic per-page table counts (≤ ~3) this is a handful of APTED runs
  per (case, variant); acceptable. If a pathological page ever holds many tables, capping per-page pair
  computation is a future guard.
- **`table_recall` unchanged.** Still a blunt coverage proxy; turning "matched above a threshold" into a
  pass/fail belongs to the deferred Judgment layer, not here.
- **Aggregate comparability with Slice 1.** For in-order, well-matched cases the aggregate `teds` is
  numerically unchanged; only mis-ordered cases move (upward, correctly). Note this when comparing old
  and new run numbers.

---

## What is explicitly NOT in this doc

- Exact per-table breakdown component markup and expander interaction — implementation plan.
- Judgment/Selection (thresholds, profiles) — seam #5, deferred for all dimensions.
- Any change to authoring/bootstrap/grid editor, or to the `text` dimension.
- Bbox/spatial matching (dropped).
