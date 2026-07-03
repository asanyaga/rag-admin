# Design: Classification-based input filtering for extraction (`category_filter`)

**Date:** 2026-07-02
**Status:** Design — awaiting review
**Related code:** `backend/app/adapters/extraction/preprocess/`, `backend/app/services/classification/`, `backend/app/routers/extraction.py`

## Problem

LLM extraction is slow and expensive. When only part of a document is relevant to
an extraction schema, feeding the whole document wastes tokens and dilutes accuracy.
We want to optionally scope an extraction run to the page-regions of a **completed
classification run**, so only relevant content reaches the extractor.

This completes a pre-existing seam: `category_filter` is already registered in the
preprocess registry (`preprocess/base.py`) with config schema
`{classificationRunId, categories}` and stubbed as `NotImplementedError` in
`preprocess/block_filter.py`.

## Goals

- Optional classification-based filter for extraction. When not configured, extraction
  behaves exactly as today.
- Configurable granularity (`page` default, `block`) so we can experiment with fidelity.
- Correct-by-construction: block IDs only ever come from the *same parse* the extraction
  uses.
- Fail fast on misconfiguration — never spend LLM tokens on an empty or unintended scope.

## Non-goals

- No backend workflow/orchestration engine. The UI sequences classification → extraction;
  a real workflow engine is a later sprint.
- No inline "trigger classification and wait" from the Extract panel (see Assumptions).
- No retrofit of the existing `block_filter` stage (it leaves stale `pages[].block_ids`;
  out of scope here — noted only).

## Key decisions (from brainstorming)

1. **Frame:** classification is a *filter* that narrows extraction inputs. Optional.
2. **Abstraction:** complete the existing `category_filter` preprocess stage using a
   **resolve-then-filter** split (below). Preprocess stages stay pure functions.
3. **Granularity:** `granularity: "page" | "block"`, default `"page"`.
   - `page` → keep whole pages touched by matching regions.
   - `block` → keep the regions' `block_ids`; for any matching region with an **empty**
     `block_ids` list, fall back to keeping that region's page range.
4. **Parse-run coupling:** **strict.** Only classification runs whose `parse_run_id`
   equals the extraction's `parse_run_id` and whose `status == "completed"` are eligible.
5. **Empty match:** **fail fast** at request time with HTTP 400, before any LLM call.
6. **Reconstruction:** `category_filter` returns a **whole, self-consistent
   `ParsedDocument`** (regenerated `full_text`/`full_markdown`, pruned `pages`), not a
   naive block subset.
7. **Page numbering:** **preserve original page indices** (Option A). Pages are sparse
   (e.g. indices 2, 5, 7); `page_count` = number of retained pages. No renumbering.
8. **Orchestration:** UI-driven, same pattern as parse config assembly.

## Architecture: resolve-then-filter

Preprocess stages remain **pure functions** `(doc, config) -> doc` with no DB access.
The classification run's regions live in the DB, so a **resolver** turns the user's
selection into a concrete keep-set *before* the pipeline is built.

```
RunExtractionRequest.preprocess = [
  { "stage": "category_filter",
    "config": { "classificationRunId": "...", "categories": ["financials"],
                "granularity": "page" } },
  ...
]
        │
        ▼  (router, before _maybe_wrap_pipeline)
resolve_category_filter_stages(preprocess, parse_run_id, classification_repo)
   - for each category_filter stage:
       • load run; validate status == "completed"                  → else NotFound/400
       • validate run.parse_run_id == parse_run_id (strict)         → else 400
       • select regions whose label ∈ categories
       • compute keep-set:
           page  → keepPages = ∪ [page_start..page_end]; keepBlockIds = ∅
           block → keepBlockIds = ∪ region.block_ids;
                   keepPages   = ∪ page ranges of matching regions with empty block_ids
       • validate keep-set non-empty                                → else 400 (fail fast)
       • rewrite stage.config to add resolved keepPages / keepBlockIds
         (original selection retained for provenance)
        │
        ▼
_maybe_wrap_pipeline(extractor, resolved_preprocess, chunking)  → PipelineExtractor
        │
        ▼  (background task → PipelineExtractor.extract → apply_preprocess)
category_filter(doc, config)   # PURE: reads keepPages / keepBlockIds only
```

### Resolver

`resolve_category_filter_stages(preprocess, parse_run_id, repo)` — new helper in the
`app.services.classification` package (owns region knowledge). Returns a new preprocess
list with each `category_filter` stage's config augmented by the resolved keep-set.
Raises `NotFoundError` / `ValueError` which the extraction router already maps to
404 / 400.

Resolution needs only the run row + its regions (`ClassificationRunRepository.get`,
`.get_regions`); it does **not** need the `ParsedDocument`. The router constructs the
repo (it already has `db`) and calls the resolver before `_maybe_wrap_pipeline`.

### `category_filter` (pure) — reconstruction contract

Given resolved `keepPages` and `keepBlockIds`, build a new `ParsedDocument` where every
field is internally consistent with the retained content:

- **`blocks`** — retained blocks in original reading order. A block is retained if
  `page_index ∈ keepPages` **or** `str(block.id) ∈ keepBlockIds`. Original `page_index`
  preserved.
- **`pages`** — only pages with ≥1 retained block; each `Page.block_ids` pruned to the
  retained set; `Page.index` kept as the **original** page number (sparse indices).
- **`page_count`** — number of retained pages.
- **`full_text` / `full_markdown`** — **regenerated** by concatenating retained blocks'
  `text` / `markdown` in reading order (this is what makes the doc "whole" — flattened
  text matches the blocks the extractor sees).
- **`derived_from`** = source `parse_run_id`; **`derivation`** = `"preprocess:category_filter"`.
- **`labels`** — applied categories added as document-scoped `Label`s
  (`source="classifier"`) so the filter is visible in the doc itself.
- Identity fields (`id`, `source_document_id`, `parse_run_id`, `source_filename`,
  `schema_version`) preserved.

**Page numbering (Option A) tradeoff:** `page_count` no longer equals `max(index)+1`.
Any consumer iterating `range(page_count)` would be wrong; consumers must iterate
`doc.pages`. The extraction pipeline estimates tokens from `full_markdown` and does not
assume contiguous page indices, so it is unaffected.

## Provenance / persistence

Today `preprocess` is **not** persisted on the extraction result (the router builds the
pipeline from the request field; `process_extraction` only passes `result.config`).
To make the applied filter visible after the fact, `run_extraction` will fold a compact
summary into the stored `config`:

```json
"applied_filter": {
  "classificationRunId": "...",
  "categories": ["financials"],
  "granularity": "page",
  "keptPages": 3,
  "keptBlocks": 0
}
```

The derived doc additionally records `derivation` and document-scoped `Label`s, so
provenance survives in both the result config and the doc itself.

## API changes

- **`RunExtractionRequest.preprocess`** — no schema change; `category_filter` stages are
  already valid entries. Behavior: the router now resolves them.
- **Errors** (all via existing `ValueError`→400 / `NotFoundError`→404 mapping in the
  router):
  - classification run not found → 404
  - run not `completed` → 400
  - run `parse_run_id` ≠ extraction `parse_run_id` → 400
  - selected categories match no content → 400 `"Selected categories matched no content in classification run {id}"`
- The `category_filter` entry in `get_preprocess_stages()` is updated: drop "(coming
  soon)", add `granularity` to its `config_schema`.

## Frontend

Optional **"Filter by classification"** section in the Extract config panel:

- On open, fetch classification runs for the document
  (`GET /documents/{id}/classification-runs`), filter client-side to
  `status == "completed"` **and** `parse_run_id == current parse_run_id`, auto-select the
  latest.
- Render that run's categories (distinct region labels) as multi-select checkboxes, plus
  a granularity toggle defaulting to **Page**.
- If no eligible run exists → blank state with a hint that classification must be run and
  completed on this parse first.
- Selecting categories composes one `category_filter` stage into the request `preprocess`
  array. Skipping the section adds no stage → unchanged extraction.

## Testing

- **`category_filter` (pure) unit tests:** page mode; block mode; block mode with
  page-fallback region; non-matching selection; reconstruction invariants
  (`full_markdown` regenerated, `pages` pruned, original `page_index` preserved,
  `page_count` = retained page count).
- **Resolver unit tests:** happy path (page + block); parse-run mismatch → error;
  not-completed → error; empty match → error; missing `classificationRunId` → error.
- **Router/service test:** `run_extraction` with a `category_filter` stage resolves,
  persists `applied_filter`, and dispatches; a mismatched/empty selection returns 400
  before dispatch.
- **Frontend:** hook fetches and filters runs to eligible set; selection composes the
  correct stage config; blank state renders when none eligible.

## Assumptions (confirm during review)

- Categories offered = the selected run's `labelsRequested` (the document
  classification-runs *list* endpoint does not populate `regions`).

---

## Revision 2026-07-03: reworked extraction page + inline classification

Supersedes the original "Frontend" section and the select-only assumption. Backend is
unchanged — the resolver, `category_filter`, and the classification create/poll endpoints
already support everything below.

### Page layout

- **Extraction config → a Card** (primary, always visible): schema, method,
  method-specific settings, prompt/output mode, chunking.
- **Parse config → a Collapsible.** Collapsed when a viable parse run exists; auto-expanded
  and required when none does.
- **Classification filter → a Collapsible.** Always optional, collapsed by default.

### Classification filter is standalone and method-agnostic

The filter leaves the LLM method block. On submit the composed `category_filter`
preprocess stage is attached regardless of extraction method. (Guaranteed to affect the
CDM-based LLM path; `llamaextract` behaviour verified separately.)

### Classification collapsible — dual mode

- **Select mode** — a completed classification run exists for the resolved parse: show its
  `labelsRequested` as category checkboxes + granularity toggle.
- **Configure mode** — no run exists for the parse: reuse `ClassificationConfig` (labels +
  classifier type) + `PromptConfigEditor` + batch size/overlap, **plus** a "filter by"
  multi-select over the labels being classified (a run may have many labels; the user
  filters extraction to a subset) + granularity. Defaults to all entered labels.

### Auto-chain orchestration

`useExtractionSubmit` gains a `classifying` phase between parse and extract. A single "Run
extraction" click performs:

```
ensure parse (create + wait if needed)
  → configure mode: createClassificationRun(parseRunId, labels, classifierConfig)
                     → poll getClassificationRun until completed (or failed → abort)
  → build category_filter { classificationRunId, categories (subset), granularity }
  → run extraction with that stage (method-agnostic)
```

Phases: `parsing → classifying → extracting`. If neither an existing run is selected nor a
configure-mode classification is set up, the classify phase is skipped and nothing filters.

### Reuse

Extract the classifier-config assembly (the `classifierConfig` object built inline in
`NewClassificationRunPage.handleSubmit`) into a shared helper so both pages build it
identically.

### Testing (delta)

- Filter hook: select mode composes stage from existing run; configure mode carries labels,
  classifier config, filter-subset, granularity; `none` when unconfigured.
- Orchestration: parse → classify (poll to completed) → extract with the just-created
  run id; classification failure aborts before extraction.
- Component: renders select mode vs configure mode by eligibility; filter-subset selection.
