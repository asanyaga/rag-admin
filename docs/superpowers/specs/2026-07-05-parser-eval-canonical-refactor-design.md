# Parser Eval — Canonical Entity Model Refactor (Design)

**Date:** 2026-07-05
**Status:** Draft for review
**Author:** brainstorming session (asanyaga)
**Depends on:** `docs/architecture/eval-entity-model.md` (r3 — the canonical model this refactor realizes)
**Supersedes shape of:** `docs/superpowers/specs/2026-07-03-parser-evaluation-harness-design.md` (first-slice backend)

## Problem

The shipped parser-eval backend (PR #142, unshipped/undeployed — migration `8da704a351d2` never
applied to Postgres) uses a data model that diverges from the now-agreed canonical eval model. We are
refactoring it to the canonical shape **before** the frontend is built and before extraction/retrieval
are retrofitted, so parser eval becomes the reference implementation.

Nothing is deployed, so this is a **rename/reshape refactor with a rewritten migration**, not a
data-preserving migration.

## Scope

**Backend only.** No frontend exists for parser eval yet (Plan 2 was never written), so there is
nothing to refactor there — the eventual UI is built against the new model.

In scope:
- Reshape the four tables to the canonical model + add the Dataset container.
- Elevate Metric to a first-class `metrics{name→value}` map on Result.
- Make Variant identity `(adapter, config)` with a deterministic `variant_key`.
- Add provenance (`source_method`) and review (`review_status`) fields (structural only).
- Rewrite the single Alembic migration in place.
- Rewrite repository, engine, scorer registry, schemas, router, and tests accordingly.

Out of scope (deferred — unchanged from the harness design's seams):
- Judgment/Selection layers (Target/Threshold, Profile) — seam #5.
- Golden-tier mechanics (derived vs explicit) — deferred per entity-model Q4; **no `tier` field**.
- Synthetic-generation pipeline — only the provenance/review *slot* is added, no generator.
- Verification workflow (endpoints to promote draft→verified) — fields only, no promotion API.
- **Variance sampling / trials** — sampling a probabilistic variant multiple times *within* one run
  (`trial_index` + widened uniqueness `(run, case, variant_key, trial_index)`, aggregated at report
  time). Named seam; deferred until a probabilistic variant is benched. Until then, variance is
  observed across runs.
- Additional dimension scorers (table/reading_order/roles) — registry seam unchanged.
- Retrofit of extraction/retrieval eval — later, targeted refactors.

## The model (concrete parser-eval instantiation)

Full rationale in `docs/architecture/eval-entity-model.md`. Concrete tables/classes:

| Role | Class | Table |
|---|---|---|
| Document | *(reuse)* `SourceDocument` | `source_documents` |
| Eval Case | `ParserEvalCase` | `parser_eval_cases` |
| Dataset | `ParserEvalDataset` | `parser_eval_datasets` (+ `parser_eval_dataset_cases` M:N join) |
| Eval Run | `ParserEvalRun` | `parser_eval_runs` |
| Result | `ParserEvalResult` | `parser_eval_results` |
| Scorer | *(code)* `ScorerSpec` registry | `app/services/parser_eval/scorers/` |

**Name-reuse footgun (call out in the migration):** `ParserEvalCase` keeps its *name* but changes
*meaning* — the old document-stand-in dissolves into `source_documents`, and the old `ParserEvalTarget`
becomes the new `ParserEvalCase`. `parser_eval_targets` is dropped.

### Schema

**Enums**
- `parser_eval_dimension`: `text` *(unchanged)*
- `parser_eval_run_status`: `pending|running|completed|failed` *(unchanged)*
- `parser_eval_source_method`: `human|generated|bootstrapped` *(new)*
- `parser_eval_review_status`: `draft|verified` *(new)*

**`parser_eval_cases`** — the Eval Case (input + ground truth)
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `project_id` | UUID FK→projects CASCADE | query scope |
| `source_document_id` | UUID FK→source_documents RESTRICT | the Document |
| `dimension` | enum `parser_eval_dimension` | selects the Scorer |
| `expected` | JSON | the Ground Truth (`{pages:[str]}` for `text`) |
| `source_method` | enum `parser_eval_source_method` default `human` | provenance |
| `review_status` | enum `parser_eval_review_status` default `draft` | trust gate |
| `created_by` | UUID FK→users | |
| `created_at` | timestamptz | |
- Unique `(source_document_id, dimension)` — one canonical ground truth per doc-dimension
  (`uq_parser_eval_cases_source_dim`). Index on `project_id`.

**`parser_eval_datasets`** — the container
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `project_id` | UUID FK→projects CASCADE | |
| `name` | String(255) | |
| `description` | Text nullable | |
| `created_by` | UUID FK→users | |
| `created_at` | timestamptz | |
- Index on `project_id`.

**`parser_eval_dataset_cases`** — M:N membership
| Column | Type | Notes |
|---|---|---|
| `dataset_id` | UUID FK→parser_eval_datasets CASCADE | |
| `eval_case_id` | UUID FK→parser_eval_cases CASCADE | |
- PK `(dataset_id, eval_case_id)`.

**`parser_eval_runs`** — the execution
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `project_id` | UUID FK→projects CASCADE | |
| `name` | String(255) | |
| `variants` | JSON default `[]` | list of `{adapter, config}` |
| `eval_case_ids` | JSON default `[]` | **resolved snapshot** (UUID strings) |
| `dataset_id` | UUID FK→parser_eval_datasets SET NULL, nullable | **provenance only** |
| `status` | enum `parser_eval_run_status` default `pending` | |
| `error_message` | Text nullable | |
| `created_by` | UUID FK→users | |
| `created_at`, `updated_at` | timestamptz | |
- Index on `project_id`.

**`parser_eval_results`** — the produced cell
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `run_id` | UUID FK→parser_eval_runs CASCADE | |
| `eval_case_id` | UUID FK→parser_eval_cases CASCADE | |
| `adapter` | String(64) | variant part 1 |
| `config` | JSON | variant part 2 |
| `variant_key` | String(128) | deterministic hash of `(adapter, config)` |
| `metrics` | JSON | `{name→value}` scalar map |
| `primary_metric` | String(64) nullable | which metric is headline |
| `details` | JSON nullable | non-scalar attribution (e.g. per-page) |
| `cost` | JSON nullable | from `ParseRun` |
| `latency_ms` | Integer nullable | from `ParseRun` |
| `created_at` | timestamptz | |
- Unique `(run_id, eval_case_id, variant_key)` (`uq_parser_eval_results_run_case_variant`).
  Index on `run_id`. **`dimension` is NOT on Result** — it is a property of the Eval Case.

**Results are immutable / append-only.** A run is single-shot (each `(case, variant)` executes once),
so results are **inserted, never upserted-over**. `variant_key` is a deterministic *grouping* identity
(for comparison/aggregation), not a mutation key. The unique constraint is a safety net; **retry = a
new run**. This preserves genuine data points for **probabilistic variants** (LLM parsers, sampling,
some OCR), whose output legitimately varies per execution.

### Variant identity

`variant_key(adapter: str, config: dict) -> str` in `app/services/parser_eval/variants.py`:
deterministic — `f"{adapter}@{sha256(json.dumps(config, sort_keys=True, separators=(',',':')))[:12]}"`.
Empty/`None` config normalizes to `{}`. This backs the uniqueness constraint (a JSON blob cannot).

### Scorer signature (Metric elevation)

Registry entry becomes a `ScorerSpec` declaring the metric signature:

```python
@dataclass(frozen=True)
class ScorerSpec:
    fn: Callable[[ParsedDocument, dict], tuple[dict[str, float], dict]]  # (metrics, details)
    emits: tuple[str, ...]      # metric names this scorer produces
    primary: str                # the headline metric

SCORERS: dict[str, ScorerSpec] = {
    "text": ScorerSpec(fn=score_text, emits=("similarity", "omission", "hallucination"),
                       primary="similarity"),
}
```

`score_text` returns `(metrics, details)` where `metrics = {"similarity","omission","hallucination"}`
(scalars) and `details = {"per_page":[…], "page_count_expected", "page_count_parsed"}`.

### Engine

Loop `for case in cases: for variant in run.variants:` — capture with `(adapter, config)`, run the
case's single dimension scorer (no inner target loop; the case *is* one dimension), and **insert** an
immutable Result keyed by `variant_key` (append-only — no overwrite). On capture failure, write
`metrics={primary: 0.0}`, `details={"capture_failed": True}`.

### Service / Router / API

- **Cases:** `create_case` now takes `{source_document_id, dimension, expected, source_method?,
  review_status?}` (one dimension per case — no `targets[]` list). `POST/GET
  /projects/{pid}/parser-eval/cases`.
- **Datasets (new):** `POST/GET /projects/{pid}/parser-eval/datasets`; add/remove members
  `POST/DELETE /projects/{pid}/parser-eval/datasets/{did}/cases/{cid}`; `GET .../datasets/{did}/cases`.
- **Runs:** `create_run` takes `{name?, variants:[{adapter,config}], eval_case_ids? , dataset_id?}`.
  If `dataset_id` given and `eval_case_ids` absent, resolve members → snapshot into `eval_case_ids`.
  Validate each variant's `adapter` against `ParserKind` (reuse existing 422 behaviour).
- **Results:** `GET .../runs/{rid}/results` returns rows with `eval_case_id, adapter, config,
  variant_key, metrics, primary_metric, details, cost, latency_ms`.

## Acceptance criteria

1. `parser_eval_targets` is gone; `parser_eval_cases` holds `(source_document_id, dimension, expected,
   source_method, review_status)`; `parser_eval_datasets` + join exist.
2. A Result stores a `metrics` map + `primary_metric`; no `score` float column remains.
3. Variants are `(adapter, config)`; two configs of the same adapter produce two distinct Results under
   one run (unique on `variant_key`).
3a. Results are **append-only** — the engine inserts (never upserts-over); re-running is a new run.
4. A run created with `dataset_id` snapshots the dataset's member case-ids into `eval_case_ids`, and
   later dataset edits do not change that run's covered set.
5. Creating a run with an unknown adapter returns 422 (unchanged behaviour).
6. Full parser-eval test suite passes on SQLite (`uv run python -m pytest -o "addopts=" tests -k parser_eval`).
7. The rewritten migration `upgrade()`/`downgrade()` round-trips on Postgres (verified by executor).

## Test plan

Rewrite the existing parser-eval tests to the new shape and add:
- repository: case unique `(doc, dimension)`; dataset membership add/remove; run snapshot; result upsert
  keyed by `variant_key`.
- variants: `variant_key` determinism + config-order independence + adapter+config distinctness.
- scorer: `score_text` returns `(metrics, details)` with the three named metrics.
- engine: two variants of one adapter yield two results; capture-failure path writes `{primary:0.0}`.
- router: dataset CRUD + membership; run from `dataset_id` snapshots; unknown adapter → 422.

## Deferred / open

- Golden-tier field (Q4) — not added.
- Verification/promotion API for `review_status` — fields only.
- `config` normalization edge cases (nested key ordering, float canonicalization) — the `sort_keys`
  JSON dump is the agreed baseline; revisit if adapters pass nested config.
