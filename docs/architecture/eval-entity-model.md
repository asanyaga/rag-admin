# Canonical Eval Entity Model

**Date:** 2026-07-05
**Status:** Draft for review — **no code to be written against this yet**
**Author:** brainstorming session (asanyaga)
**Applies to:** all evaluation features — parser eval, retrieval/answer eval, extraction eval, classification eval (future)
**Revision:** r3 — all open questions resolved (Q1–Q7): concrete per-feature tables + uniform `ParserEval*` naming, Dataset container modeled now, `page` stays inside `expected`, Variant = `(adapter, config)` from day one, Experiment folds into Eval Run + Variant. (r2 added Datasets, generation/provenance, run-snapshots-cases.)

---

## Purpose

Establish **one canonical vocabulary and entity model** for every eval feature, so that
"case", "ground truth", "scorer", "metric", "dataset", and "run" mean the same thing everywhere and
map to the same table/column shapes. Parser eval is the reference implementation; retrieval and
extraction are retrofitted to match.

This is a **naming + modelling contract**, not an implementation plan. It defines *what the entities
are and what they are called*. It does **not** specify migrations, APIs, or UI.

### Why now

- Nothing is shipped yet. Renames are free; there is no migration cost to hedge against.
- Three eval features currently use **three different vocabularies** for the same concepts
  (`GoldenSetQuery` vs `ExtractionGroundTruthItem` vs `ParserEvalTarget` all mean "eval case").
  Fixing this after they calcify is expensive; fixing it now is a rename.

### Non-goals

- No migrations, schema DDL, API contracts, or UI in this doc.
- The **Judgment/Selection layer** (thresholds, pass/fail, profiles) is *named* here so it has a home,
  but is **not specified** — it remains parser-eval seam #5, deliberately deferred.
- Not proposing a single shared `eval_case` table across features. Eval Case is **polymorphic** (a
  query in retrieval, a document+dimension in parser eval); this doc defines a shared *pattern* each
  feature instantiates, not one shared table.

---

## The core idea: an eval is a function, and it has four run-time layers

```
run(variant, eval_case) → metric values → (optional) verdict → (optional) selection
```

Every eval concept lives on exactly one of four conceptual layers. Confusion in this feature came
from fusing them (the "unit-test frame": test-case + assertion + threshold → pass/fail as one thing).
Evals keep them separate on purpose.

| Layer | Question it answers | Concept | Output | Built today? |
|---|---|---|---|---|
| **1. Fact** | What is correct? | **Ground Truth** | data | ✅ |
| **2. Measurement** | How close was the output? | **Scorer → Metric** | a number | ✅ |
| **3. Judgment** | Is that number good enough? | **Target / Threshold** | pass/fail | ❌ (seam #5) |
| **4. Selection** | Which variant wins? | **Profile** (weights, floors, tie-break) | a ranking | ❌ (seam #5) |

Layers 3–4 are **policy applied at report time to aggregate metrics** — never baked onto the case or
the ground truth, so the same case can be judged against different bars (e.g. 90% for indexing, 99%
for transcription) without re-authoring or re-running anything.

**Upstream of all four is authoring (layer 0).** Datasets and synthetic generation are not run-time
layers — they **manufacture and organize the fixture** (Eval Cases + ground truth) before any run.
They touch neither measurement nor judgment. See "Specification plane" below.

---

## Two planes of entities

| Plane | Authored/produced | Entities |
|---|---|---|
| **Specification** (static, authored once, held fixed) | authored | Document, **Eval Case** (carries Ground Truth + provenance), **Dataset** (container), Scorer, *generation/bootstrapping (a process)* |
| **Execution** (produced by every run) | produced | **Eval Run**, **Result** (carries Metric values), Variant |

The specification plane is the fixture; the execution plane is the output. The current parser-eval
confusion was modelling the fixture *twice* (a `Case` table **and** a `Target` table) and the
execution plane's variant axis as an un-named string column.

---

## Canonical entities

```
Specification plane (authored)
──────────────────────────────
   synthetic generation / bootstrapping ─┐   (populates cases as review_status=draft)
                                          ▼
 Document ──1:N──►  Eval Case { dimension, expected(GroundTruth), source_method, review_status }
   (source doc)        ▲   │
                       │   └── M:N ──►  Dataset { curated container/view; "golden" tier when all members verified }
                       │
                 dimension ── selects ──►  Scorer (code)
                                           Scorer.signature: { dimension, emits:[metric names] }

Execution plane (produced)
──────────────────────────
 Eval Run { variants[], resolved eval_case_ids[] (snapshot), dataset_id? (provenance), status }
                       │ 1:N
                 Result { eval_case, variant, metrics{name→value}, cost, latency }
                          └─ unique (run, eval_case, variant)
```

### Document
The shared input an Eval Case projects from. **Not an eval-owned table** — it is the existing
project-scoped source document (`source_documents`), and per the parser-eval vision it converges on
the first-class `Document` / `ParsedDocument` primitive. Eval Cases reference it directly; there is
**no parallel `*_eval_case`-as-document table** (this removes today's `ParserEvalCase` stand-in).

### Eval Case — the unit you measure
**Input + Ground Truth.** The atomic gradeable thing. For parser eval:
`{ id, project_id, source_document_id, dimension, expected, source_method, review_status, created_by, created_at }`.

- **Ground Truth is the `expected` field** — an *attribute of the case*, not a separate entity. There
  is no `ground_truth` table that the case links to; that split was redundant (Case + Target were one
  concept in two tables).
- `dimension` (text / table / reading_order …) is part of case identity because ground truth is
  inherently dimension-typed. `dimension` selects the Scorer.
- One Document → many Eval Cases (one per asserted dimension). A dimension is asserted **iff a case
  for it exists** — a missing dimension means "not evaluated," never a silent score of 0.
- **Provenance** — `source_method` (`human` | `generated` | `bootstrapped`) records where the case /
  ground truth came from. **Review status** — `review_status` (`draft` | `verified`) records whether a
  human has trusted it. These two fields are how synthetic/bootstrapped truth is tracked (below).
- Cases live in a **project-scoped pool**; Dataset membership is optional and many-to-many.

### Dataset — the container/collection
A **named, curated collection of Eval Cases** — the industry "dataset". It is a **container/view over
the case pool, not the owner of a case**: membership is **many-to-many** (`dataset_eval_case` join),
so the *same* verified case can belong to many datasets (e.g. a fast "smoke" subset and the full
regression set) **without duplicating its ground truth**. A case may also belong to no dataset.

- **"Golden Set" is a tier, not a separate entity.** A Dataset whose members are all `verified` is
  "golden" (curated, trusted, stable). Golden is an *adjective/status about trust*, not a divergent
  structure. This preserves retrieval's `GoldenSet` product noun as a **label** over a uniform shape.
- **A Dataset does not force runs to be dataset-bound** — see Eval Run. It is a reusable *selector*.

`{ id, project_id, name, description?, created_at }` + M:N membership to Eval Case.

### Synthetic generation / bootstrapping — a case-authoring *process*
Generation is not a core entity; it is a **pipeline on the specification plane that populates a
Dataset with generated Eval Cases and draft ground truth.** Same slot as manual authoring, and the
general case of parser-eval **seam #7 (truth bootstrapping)**.

- Output cases are written with `source_method=generated` (or `bootstrapped`) and
  `review_status=draft`. **Generated ≠ golden:** a generated `expected` is *candidate* truth until a
  human verifies it (`review_status=verified`). That draft→verified gate **is** the line between a raw
  Dataset (may contain unverified cases) and the golden tier.
- Track it with the provenance/review fields; add an optional `GenerationJob` entity only if you want
  to record generation-run state (retrieval already models this as `GenerationStatus`).
- **Per-feature mechanism differs, slot is identical.** Retrieval/answer eval *synthesizes* Q&A pairs
  from the corpus (question + reference answer + contexts). Parser eval **cannot** synthesize "the
  correct text of page 5" from nothing — its truth is the document itself — so its mechanism is
  **bootstrapping**: run a trusted parser → its output becomes *draft* `expected` → human corrects.

### Scorer — the measurement mechanism
**Code, keyed by dimension**, in a registry (`SCORERS[dimension] = fn`). Selected by the case's
`dimension` at run time — **not** a foreign key stored on the case.

- A scorer grades one case and **emits one or more named Metrics**:
  `score(cdm, expected) → { metric_name → value, … }`.
- Its **signature** — `{ dimension, emits: [metric names] }` — is reference data the UI can read to
  render columns. This is the *definition* of its metrics (see Metric).
- A scorer produces **numbers, not verdicts.** Even a boolean per-item scorer (exact-match = 1/0)
  yields a *rate* at the eval level; pass/fail is the Judgment layer, not the scorer's job.
- **LLM-as-judge is a Scorer** (a model-based one), *not* the layer-3 Judge. It emits a number; keep
  the word "judge" off layer 3 to avoid the collision.

### Metric — a named measurement
A named number a Scorer emits (`similarity`, `omission`, `hallucination`, `exact_match`, `table_f1`…).
Two senses, two homes:

- **Definition** ("the text scorer emits similarity/omission/hallucination") → on the **Scorer**.
- **Value** ("docling scored similarity=0.97 on this case in this run") → in **Result.metrics**.

One scorer emits several metrics. One is designated `primary_metric` (the headline number used for
default sorting); the rest travel alongside it.

### Eval Run — one execution
`{ id, project_id, name, variants[], eval_case_ids[] (resolved snapshot), dataset_id? (provenance), status, timestamps }`.

- **A Run binds to a resolved *set of Eval Cases*, not to a Dataset.** Targeting a Dataset is optional
  sugar meaning "the cases that are members of it right now"; ad-hoc runs over a handful of cases are
  equally first-class. (Parser eval's existing `case_ids[]` already is this model.)
- **Snapshot the resolved case set onto the Run.** Datasets are **mutable**; a Run is an **immutable
  historical fact**. Storing only `dataset_id` would let later dataset edits retroactively change what
  "that run covered" and destroy run-to-run comparability. So resolve membership at launch, store the
  concrete `eval_case_ids[]`, and keep `dataset_id` as *provenance* only. (This is how LangSmith /
  Braintrust pin a dataset *version* to an experiment.)
- Runs a set of **Variants** over the resolved cases and produces Results. Carries lifecycle status
  (`pending/running/completed/failed`).

### Variant — the thing under test (the compared axis)
The parser here; the retriever/index config in retrieval; the model+prompt in extraction. **This is
the axis you compare** and the reason the feature exists ("which parser should I pick"). It lives as a
first-class **column** on Run (`variants[]`) and Result (`variant`) — never buried in a JSON blob.

**Variant identity = `(adapter, config)` from day one** *(Q5 resolved; formerly seam #3).* A variant is
**not** just a `ParserKind` string — it is the adapter plus its config, so the *same* adapter under two
configs (e.g. `custom_pipeline` with pdfplumber vs. fitz tables) is a **distinct comparable row**.
Implication for storage: a Result needs a **deterministic variant identity** for its uniqueness key —
store `adapter` (string) + `config` (JSON) and derive a canonical `variant_key` (stable hash of
adapter + normalized config), since a raw JSON blob can't back a unique constraint. Uniqueness becomes
`(run, eval_case, variant_key)`.

### Result — the produced cell
`{ id, run_id, eval_case_id, adapter, config, variant_key, metrics{name→value}, primary_metric?, cost, latency_ms }`,
unique on `(run, eval_case, variant_key)` where `variant_key` is the deterministic hash of
`(adapter, config)`. This is the output of applying one Scorer to one Eval Case under one Variant. It
stores **metric values**, cost, and latency. It carries **no verdict** — judgment is a later, separate
layer.

---

## Glossary (the contract)

| Canonical term | Definition | Layer | Home |
|---|---|---|---|
| **Ground Truth** | the known-correct answer for a case | Fact | `Eval Case.expected` (a field) |
| **Eval Case** | one input + its ground truth; the unit you measure | Spec | `<feature>_eval_case` row |
| **Provenance** | how a case/GT was created | Spec | `Eval Case.source_method` |
| **Review status** | draft → verified trust gate | Spec | `Eval Case.review_status` |
| **Dataset** | a curated container/collection of Eval Cases (M:N) | Spec | `<feature>_dataset` + join |
| **Golden Set** | a Dataset tier: all members `verified` | Spec | (status/label over Dataset) |
| **Generation** | a process that populates a Dataset with draft cases | Spec (process) | pipeline (+ optional job) |
| **Scorer** | code that grades a case and emits metrics | Measurement | registry (code) + signature |
| **Metric** | a named number; *definition* on scorer, *value* on result | Measurement | Scorer.signature / Result.metrics |
| **Variant** | the thing under test; the compared axis | Execution | column on Run + Result |
| **Eval Run** | one execution over cases × variants | Execution | `<feature>_eval_run` row |
| **Result** | the `(run, case, variant)` cell holding metric values | Execution | `<feature>_eval_result` row |
| **Target / Threshold** | the bar a metric must clear | Judgment | *deferred* (report-time policy) |
| **Profile** | weights + floors + tie-break for selection | Selection | *deferred* (report-time policy) |

**Reconciled from r1:**
- **Dataset** is now a first-class entity (the container), not "dropped." It is the industry term the
  frameworks use, and the home for synthetic data.
- **Golden Set** is a **tier of a Dataset** (verified), not a separate entity.
- **Experiment** remains folded into **Eval Run + Variant** — comparing variant A vs B *is* the
  experiment; it needs no own entity. (Retrieval's `EvalRun` already carries "experiment fields" —
  reconcile during retrofit; see open questions.)

---

## Naming convention (the pattern each feature instantiates)

Eval Case is polymorphic, so each feature owns its own tables, but all follow one pattern:

| Role | Table / field pattern |
|---|---|
| Eval Case | `<feature>_eval_case` (with `source_method`, `review_status`) |
| Ground Truth | `expected` (payload field on the case; shape discriminated by `dimension` where applicable) |
| Dataset | `<feature>_dataset` + `<feature>_dataset_eval_case` (M:N join) |
| Eval Run | `<feature>_eval_run` (with snapshot `eval_case_ids[]`, optional `dataset_id`) |
| Result | `<feature>_eval_result` |
| Variant | column `variant` on run/result (feature may name for its domain, but always a first-class column) |

`*_eval_run` and `*_eval_result` **already** match this across all three features — leave them. The
churn is confined to the case/ground-truth naming, elevating Metric, and adding the Dataset container.

### Concrete first, abstractions later (Q1 + Q7 resolved)

**Decision:** implement **concrete per-feature tables with no abstract base class and no shared
discriminated table** (Q1 = per-feature). Build **parser eval first**, then targeted-refactor
extraction and retrieval onto the same concrete pattern (Q7 = parser-first). **Only after the model is
validated across all eval types** do we lift the shared columns into an abstraction and subclass — to
prevent long-term data-model drift, without premature abstraction now.

- **Interim anti-drift mechanism is this doc.** Until the code abstraction exists, the shared shape is
  enforced only by this naming/shape contract at review. The doc stays authoritative until then.
- **Future lift target:** a SQLAlchemy **mixin** (`EvalCaseMixin` etc.) carrying the common columns
  (`id`, `source_method`, `review_status`, timestamps, dataset membership) that each concrete table
  still instantiates as its **own** table — de-duplication without single-table downsides. Joined-table
  inheritance is the heavier alternative only if cross-feature queries are later required.

**Concrete parser-eval instantiation** (uniform `ParserEval*` / `parser_eval_*`, matching existing
tables and sibling `ExtractionEval*`):

| Role | Class | Table |
|---|---|---|
| Dataset | `ParserEvalDataset` | `parser_eval_datasets` + `parser_eval_dataset_cases` (M:N join) |
| Eval Case | `ParserEvalCase` | `parser_eval_cases` |
| Eval Run | `ParserEvalRun` | `parser_eval_runs` |
| Result | `ParserEvalResult` | `parser_eval_results` |
| Document | *(reuse)* | `source_documents` |

> **Name-reuse footgun:** `ParserEvalCase` **already exists** meaning the *document stand-in*. Under
> this model the name moves to a **different concept** (doc + dimension + `expected` + provenance): the
> old document-`ParserEvalCase` **dissolves into `source_documents`**, and the old `ParserEvalTarget`
> **becomes** the new `ParserEvalCase`. This is a **semantic reshuffle of an existing table**, not an
> additive rename — the migration moves meaning between tables and must say so explicitly.

---

## Mapping: current parser eval → canonical

| Current | Canonical | Change |
|---|---|---|
| `ParserEvalCase` (doc + labels) | **Document** (existing `source_documents`) | **Dissolve** — cases reference `source_document_id` directly. Drop the stand-in table. `source_filename` is a redundant denormalization; derive by join. |
| `ParserEvalTarget` `{case_id, dimension, expected}` | **Eval Case** `{source_document_id, dimension, expected, source_method, review_status}` | **Rename + reparent** — this *is* the eval case. `expected` is the Ground Truth. Add provenance + review fields. |
| — (none) | **Dataset** + M:N join | **New (in scope)** — a curated container over cases; runs may target it. Modeled from the start (Q3 resolved). "Golden" tier deferred (Q4). |
| `SCORERS[dimension]`, `Scorer` type | **Scorer** | ✅ keep. Add explicit `signature {dimension, emits:[...]}`. |
| `ParserEvalRun` `{parsers[], case_ids[], status}` | **Eval Run** | ✅ keep. `parsers[]` → `variants[]` (each a `(adapter, config)`); `case_ids[]` becomes the **resolved snapshot**; add optional `dataset_id` provenance. |
| `ParserEvalResult` `{run,case,parser,dimension, score, details, cost, latency}` | **Result** | Replace `score`(float)+`details`(JSON) with `metrics{name→value}` + `primary_metric`. `parser` → `adapter` + `config` + `variant_key`. Uniqueness `(run, eval_case, variant_key)` — `dimension` is now a property of the eval case, not a separate key component. |
| — (implicit: `score` + `details` numbers) | **Metric** | **Elevate.** `similarity/omission/hallucination` become named metrics in `Result.metrics`; `similarity` is `primary_metric`. |
| — (none) | **Target/Threshold/Profile** | Still absent; **seam #5**, out of scope here. |

Net: 4 parser-eval tables (`Case, Target, Run, Result`) → `Eval Case, Eval Run, Result` (+ reuse of
existing Document) **plus an optional Dataset container**. Metric becomes explicit; Variant becomes
named; provenance/review added for generated truth.

---

## Cross-feature mapping

| Canonical | Parser eval | Retrieval / answer eval | Extraction eval |
|---|---|---|---|
| Document | `source_documents` | (n/a — input is a query) | source document |
| Eval Case | `ParserEvalTarget` → new case | `GoldenSetQuery` | `ExtractionGroundTruthItem` |
| Ground Truth | `expected` | `GoldenSetSource` (expected sources) | item expected fields |
| Dataset | — (none) | `GoldenSet` ✅ | `ExtractionGroundTruthSet` |
| Provenance / Review | — (add) | `SourceMethod` / `ReviewStatus` ✅ | (add) |
| Generation | — (seam #7 bootstrap) | `GenerationStatus` + auto-gen spec ✅ | (n/a yet) |
| Scorer | `scorers/` registry ✅ | in `eval_service` | `field_matchers` / `line_item_matcher` |
| Metric | `score`+`details` | fields on result | `metrics` JSON ✅-ish |
| Eval Run | `ParserEvalRun` ✅ | `EvalRun` ✅ | `ExtractionEvalRun` ✅ |
| Variant | `parser` | index/retriever config | model+prompt |
| Result | `ParserEvalResult` ✅ | `EvalRunResult` | `ExtractionEvalResult` |

Observations:
- **Retrieval eval already ships the entire authoring layer** — `GoldenSet` (Dataset), `SourceMethod`
  (provenance), `ReviewStatus` (draft→verified gate), `GenerationStatus` (synthetic generation), plus
  the golden-set auto-gen/import specs. It is the **reference implementation for Dataset + generation**;
  parser and extraction adopt the same field pattern when they need it.
- **Ground Truth already exists in extraction** (`ground_truth_set/item`) — aligning parser eval to it
  moves *toward* a peer, confirming the direction.

---

## Decisions captured (for confirmation)

1. **Ground Truth is a field, not a table.** Eval Case carries `expected`; no separate GT table.
2. **Eval Case = the per-dimension unit** (was `ParserEvalTarget`); the old `ParserEvalCase` is the
   **Document** and dissolves into `source_documents`.
3. **Scorer is code selected by dimension**, not a stored FK on the case.
4. **Metric is first-class**: a `metrics{name→value}` map on Result + a `primary_metric`, replacing
   `score`+`details`. Highest-value change; shared by all features.
5. **Variant is a named first-class column** on Run + Result, never JSON-buried. **Variant identity =
   `(adapter, config)` from day one** *(Q5)* — stored as `adapter` + `config` + a deterministic
   `variant_key`; uniqueness `(run, eval_case, variant_key)`.
6. **Judgment & Selection (Target/Profile) are named but deferred** (seam #5) — report-time policy over
   aggregate metrics, never on the case.
7. **Dataset is the container entity, modeled from the start.** *(Revised from r1; Q3 resolved.)*
   Dataset is a **M:N container/view** over a project-scoped case pool — not the owner of a case — so
   verified cases are reused across datasets without duplicating ground truth. The **"golden" tier
   mechanics are deferred** (Q4): treat golden as an informal label for now; no `tier` field committed.
8. **A Run binds to a resolved set of cases, not to a Dataset.** Targeting a Dataset is optional sugar;
   ad-hoc runs stay first-class.
9. **Runs snapshot their resolved case set** (`eval_case_ids[]`) for immutability/comparability;
   `dataset_id` is provenance only.
10. **Synthetic data is tracked by provenance + review, not new core machinery.** Generated/bootstrapped
    cases are `source_method=generated|bootstrapped, review_status=draft`; verification promotes them,
    and an all-verified Dataset is "golden."
11. **Concrete per-feature tables now; abstractions lifted later** *(Q1 + Q7).* No abstract base / no
    shared discriminated table. Parser eval first (concrete `ParserEval*` / `parser_eval_*`), then
    targeted refactors of extraction and retrieval, then lift a shared mixin once the model is
    validated across types. This doc is the anti-drift contract until that mixin exists.
12. **Uniform `ParserEval*` prefix confirmed** — `ParserEvalDataset`, `ParserEvalCase`, `ParserEvalRun`,
    `ParserEvalResult` on `parser_eval_*` tables.
13. **`page` stays inside `expected`** *(Q2)* — `{pages:[str]}`, one case per document-dimension,
    doc-level metric. No per-page case axis.
14. **Experiment folds into Eval Run + Variant** *(Q6, confirmed)* — no separate Experiment entity;
    retrieval's existing "experiment fields" are reinterpreted during its refactor.

---

## Open questions for review

1. **~~Per-feature tables vs one shared eval schema?~~ RESOLVED — per-feature concrete tables, no
   abstract base / no shared discriminated table.** Abstractions (a mixin) are lifted only after the
   model is validated across all eval types. See "Concrete first, abstractions later" above.
2. **~~`page` granularity?~~ RESOLVED — pages stay inside `expected`** (`{pages:[str]}`, one case per
   document-dimension, doc-level metric). No per-page case axis.
3. **~~Does parser eval need a Dataset now?~~ RESOLVED — model the Dataset container now.** The M:N
   Dataset container is in scope from the start (not deferred to seam #10). Cases still live in a
   project-scoped pool; the Dataset is the curated view over them.
4. **~~Golden tier: derived or explicit?~~ DEFERRED — revisit later.** Whether "golden" is computed
   (all members `verified`) or an explicit user-set status is not decided now. Until then, treat
   "golden" as an informal label over a Dataset; no `tier`/status field is committed.
5. **~~Variant identity?~~ RESOLVED — `(adapter, config)` from day one.** Stored as `adapter` +
   `config` + deterministic `variant_key`; uniqueness `(run, eval_case, variant_key)`.
6. **~~Experiment reconciliation?~~ RESOLVED — Experiment collapses into Eval Run + Variant.** No
   separate entity; retrieval's "experiment fields" are reinterpreted during its refactor.
7. **~~Retrofit sequencing?~~ RESOLVED — parser eval first, then targeted refactors.** Parser eval is
   the reference build; extraction and retrieval are then refactored onto the same concrete pattern;
   shared abstractions are lifted last, once validated. Not a single big-bang pass.

---

## What is explicitly NOT in this doc

- Migrations / DDL / API / UI.
- The Judgment and Selection layers' design (thresholds, profiles, floors, tie-breaks) — deferred to
  parser-eval seam #5.
- The synthetic-generation *pipeline* design (prompts, models, corpus sampling) — only its **slot**
  (provenance + review + Dataset population) is fixed here.
- LLM-as-judge scorers (seam #8), caching/capture-score split (seam #4), baselines/regression (seam #6)
  — all remain additive behind the registry and unaffected by this naming model.
```
