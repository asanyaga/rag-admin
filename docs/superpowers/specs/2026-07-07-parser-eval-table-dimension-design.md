# Parser Eval — Table Dimension Design

**Date:** 2026-07-07
**Status:** Draft for review
**Author:** brainstorming session (asanyaga)
**Feature branch:** `feat/parser-eval-table-dimension`
**Builds on:** parser-eval feature (backend PR #142, canonical refactor PR #144, frontend PR #146+),
canonical eval entity model (`docs/architecture/eval-entity-model.md`)

---

## Purpose

Add a **`table` dimension** to the parser-eval feature so that parsers can be compared on **how well
they extract tables**, not just prose text. Today only the `text` dimension exists. This is the
first exercise of the model's anticipated **seam #1** ("add a dimension = add one `ScorerSpec`").

The unit of comparison stays the same: score each parser's CDM (`ParsedDocument`) output against
per-`(document, dimension)` ground truth, and surface named metrics per parser so the user can decide
which parser to pick.

### Why tables, why this way

Tables are the hardest thing to parse and the most valuable to get right, and parsers differ wildly
on them. But table *evaluation* is also hard: a table is a 2-D grid with structure (rows, columns,
merged cells, headers), so comparing two tables is not string comparison. The industry-standard answer
is **TEDS** (Tree-Edit-Distance-based Similarity), which turns each table into a tree and scores how
few edits transform one into the other, blending structure and content into a single 0–1 number.

We author ground truth **once** (the correct table as HTML) and derive **several** metrics from it —
matching the entity model's "one Scorer emits many Metrics, one primary" shape. This keeps authoring
cost bounded while leaving room to add diagnostic metrics later without re-authoring.

---

## Scope

This design covers the whole table-eval feature, delivered in **three end-to-end slices** (each ships
backend + frontend and is independently usable). **Slice 1 is specified in implementation detail;
Slices 2 and 3 are sketched and will get their own detailed specs when we reach them.**

### Decisions locked in brainstorming

1. **Measure structure + content together via TEDS** as the headline metric, with room for
   structure-only and content-only diagnostics later. One authored ground truth backs all of them.
2. **Ground truth = the document's tables as HTML**, stored in the existing `expected` JSON column.
   HTML because it is TEDS-native, can express merged cells (markdown cannot), and matches the CDM's
   existing `Table.html`.
3. **One eval case per document** (its `expected` holds *all* the document's tables), consistent with
   how the `text` dimension already models one case per document. The cost is table-to-table matching,
   deferred to Slice 3.
4. **Slice 1 authoring is bootstrap-only** (accept/reject); the full grid editor is Slice 2.
5. **Each slice lands end-to-end** (backend + frontend). The grid editor (Slice 2) is a committed
   slice, not an "if needed" afterthought.

### Non-goals

- The Judgment/Selection layers (thresholds, pass/fail, weighted profiles) — parser-eval seam #5,
  still deferred for all dimensions.
- Datasets UI, generation, LLM-as-judge — unchanged and out of scope.
- Robust multi-table matching and diagnostic metrics — deferred to Slice 3 (see below).

---

## Slice 1 — Core scoring loop, bootstrap-only authoring

**Goal:** pick a document, bootstrap draft table ground truth from a trusted parser, run several
parsers, and see a TEDS + recall comparison. Fully demoable end to end. No hand-editing of ground
truth yet (accept/reject only).

### Data model — no new tables

- Add `table = "table"` to `ParserEvalDimension`
  (`backend/app/models/parser_eval.py`). On Postgres this needs an `ALTER TYPE parser_eval_dimension
  ADD VALUE 'table'` migration; SQLite tests are unaffected (enum stored as string).
- Ground-truth shape in the existing `expected` JSON column:

  ```json
  {
    "tables": [
      { "page": 3, "html": "<table><tr><td>Item</td>…</tr>…</table>" },
      { "page": 3, "html": "<table>…</table>" }
    ]
  }
  ```

  `page` is a locator (1-based, informational in Slice 1); `html` is the canonical table content.
  Order in the array is the authored order (used by Slice 1's order-based matching).

No changes to `ParserEvalCase`, `ParserEvalRun`, or `ParserEvalResult` structure — `expected`,
`metrics`, and `details` are already free-form JSON.

### Scorer — `backend/app/services/parser_eval/scorers/table.py`

Signature matches the existing `ScorerFn`:
`score_table(cdm: ParsedDocument, expected: dict) -> tuple[dict[str, float], dict]`.

1. **Extract parsed tables** from `cdm.blocks` where `role == BlockRole.TABLE`, in reading order.
   For each, obtain HTML: prefer `block.table.html`; when absent, synthesize it from
   `block.table.cells` (a `cells_to_html` helper honoring `row`/`col`/`rowspan`/`colspan`/`is_header`).
   This fallback matters because parsers vary in whether they populate `html` vs only `cells`/
   `markdown` — synthesizing keeps scoring fair across parsers.
2. **Match by order (Slice 1 simplification):** the i-th expected table is compared to the i-th
   parsed table. Aggregate over `max(len(expected), len(parsed))`; an unmatched table on either side
   scores TEDS 0. This mirrors how `score_text` already handles page-count mismatches, and is
   deliberately naive — Slice 3 replaces it with position/overlap matching.
3. **Metrics emitted:**
   - `teds` *(primary)* — size-weighted mean of per-table TEDS (weight = cell count of the larger of
     the matched pair, so bigger tables carry more weight; same weighting philosophy as the text
     scorer's length weighting).
   - `table_recall` — `min(parsed_count, expected_count) / expected_count`
     (`expected_count == 0` → `1.0` when no tables parsed, else `0.0`).
4. **`details`** — `{ per_table: [{index, teds, ...}], expected_count, parsed_count }` for the UI.

Register in `scorers/__init__.py`:

```python
SCORERS = {
    "text":  ScorerSpec(fn=score_text,  emits=("similarity", "omission", "hallucination"), primary="similarity"),
    "table": ScorerSpec(fn=score_table, emits=("teds", "table_recall"),                    primary="teds"),
}
```

The engine (`engine.py`) needs **no change** — it already selects the scorer by
`case.dimension.value` and persists whatever metrics map the scorer returns.

### TEDS implementation

`backend/app/services/parser_eval/scorers/teds.py` — a small module: `teds(html_a, html_b) -> float`.
Parse each HTML table into a labeled tree (node per `<td>`/`<th>` carrying normalized cell text plus
`colspan`/`rowspan`), compute tree-edit distance, normalize to
`1 − distance / max(nodes_a, nodes_b)`.

**Recommendation:** add the well-known pure-Python **`apted`** package (`uv add apted`) for the
tree-edit-distance core and vendor the ~60-line HTML→tree + normalization wrapper adapted from the
standard PubTabNet TEDS implementation. **Alternative:** hand-roll tree-edit distance (~100 lines, no
dependency). We choose `apted` because tree-edit distance is subtle to implement correctly and `apted`
is the reference everyone uses. HTML parsing uses `lxml`/`html` from the existing stack (confirm
`lxml` is available; the wrapper can fall back to stdlib `html.parser` if not).

### Bootstrap — backend service + route

- **Service** (`parser_eval/service.py` or a `bootstrap.py` helper): given `source_document_id` and a
  trusted `adapter` (+ optional `config`), reuse `capture()` to parse the document, extract its
  `TABLE` blocks into the `{ "tables": [...] }` shape, and create a `ParserEvalCase` with
  `dimension=table`, `source_method=bootstrapped`, `review_status=draft`. The unique constraint
  `(source_document_id, dimension)` means one table case per document — re-bootstrapping is a
  conflict the service surfaces (409), not a silent overwrite.
- **Route** (`routers/parser_eval.py`): `POST .../evaluation/parser/cases/bootstrap-table` accepting
  `{ sourceDocumentId, adapter, config? }` (camelCase DTOs per app convention), returning the created
  draft case. Follows router → service → repository flow; router catches service exceptions.
- **Accept/reject:** accept reuses/introduces a `PATCH .../cases/{id}` that sets
  `review_status=verified`; reject reuses case deletion.

### Frontend — end to end

- **Cases tab:** a **"Bootstrap table ground truth"** dialog — pick a source document + a trusted
  parser (reusing `ParseMethodSelector`/`PARSER_REGISTRY`) → creates a draft table case. Reuses
  `useSourceDocuments`.
- **Draft review:** render the stored table HTML read-only (the `expected.tables[].html`), grouped by
  page, with **Accept** (→ `verified`) and **Reject** (delete) actions and a draft/verified badge
  (reuse existing status badge patterns).
- **Runs & results:** runs already operate over any case regardless of dimension, and the results
  table already renders a generic metrics map — so `teds` and `table_recall` appear as columns with
  minimal wiring. Confirm metric formatting (0–1, higher-is-better) matches the existing ScorePill
  treatment.

### Testing (Slice 1)

- **Scorer unit tests:** identical table → `teds ≈ 1.0`; a dropped column / mangled grid → lower
  `teds`; a missing table → `table_recall < 1`; the `cells_to_html` fallback path; empty-expected and
  empty-parsed edge cases.
- **TEDS unit tests:** identical → 1.0; one cell text change → high-but-<1; structurally different →
  low; merged-cell (`colspan`) handling.
- **Bootstrap service test:** parses via a stubbed `capture`, writes a draft case with correct
  provenance; duplicate bootstrap → conflict.
- **Frontend:** light coverage of the bootstrap dialog and accept/reject actions (respecting the
  project's existing FE test pragmatism).

### Slice 1 acceptance criteria

- A user can bootstrap draft table ground truth for a document from a chosen parser.
- The draft tables render for review and can be accepted (verified) or rejected (deleted).
- A run including a verified table case produces, per parser variant, a `teds` and `table_recall`
  value visible in the results comparison.
- `score_table` returns 1.0 TEDS for an exact-match table and degrades sensibly for structural and
  content errors, with tests proving it.

---

## Slice 2 — Grid editor (first-class authoring)

**Goal:** produce ground truth the user actually trusts, rather than whatever the bootstrap parser
guessed. Committed slice, not optional.

- **Frontend:** a table **grid editor** — edit cell text, add/remove rows and columns, merge/split
  cells, mark header cells — reachable from a draft (to correct a bootstrap) or from scratch. Verify
  on save (draft → verified).
- **Backend:** HTML ↔ grid round-trip and validation on save; `review_status` transitions;
  `PUT .../cases/{id}` to replace `expected`.
- Detailed spec written when we reach this slice.

---

## Slice 3 — Diagnostics + multi-table robustness

**Goal:** make a low TEDS diagnosable and stop naive matching from unfairly punishing parsers.

- **Backend:** add `teds_struct` (structure-only — TEDS with cell text blanked) and `cell_content_f1`
  (content-only — bag overlap of cell texts) to `score_table.emits`; replace order-based matching with
  position/overlap-based matching (using `bbox`/`page` when available), so table *k* in one parser is
  compared to the corresponding table in another regardless of extraction order.
- **Frontend:** per-table breakdown and a structure-vs-content diagnostic view on run detail.
- Detailed spec written when we reach this slice.

---

## Risks / open considerations

- **Parser HTML completeness.** Parsers differ in whether they populate `Table.html` vs only
  `cells`/`markdown`. The `cells_to_html` fallback is load-bearing for fair scoring; if a parser
  provides *neither* structured cells nor html for a table it detected, that table is effectively
  unscorable — treat as a parsed table with empty content (low TEDS), and note the limitation.
- **Naive order-matching (Slice 1).** A parser that finds tables in a different order than authored is
  unfairly penalized. Acceptable for a first slice on simple documents; fixed in Slice 3. Choose
  bootstrap/authoring documents accordingly for early use.
- **`apted` dependency.** Adds one small pure-Python dependency. If the team prefers zero new deps, the
  hand-rolled alternative is viable at ~100 lines but carries correctness risk.
- **Postgres enum migration.** `ALTER TYPE ... ADD VALUE` is not transactional on older Postgres and
  cannot run inside a transaction block in some Alembic setups — follow the existing enum-migration
  pattern in the repo and verify the round-trip on a real container (SQLite tests won't exercise it).

---

## What is explicitly NOT in this doc

- Migrations/DDL beyond naming the enum change; API request/response schemas beyond field names; exact
  React component structure — these belong in the implementation plan.
- Slice 2 and Slice 3 implementation detail (their own specs later).
- Judgment/Selection (thresholds, profiles) — seam #5, deferred for all dimensions.
