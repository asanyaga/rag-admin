# Parser Evaluation Harness — Design

**Date:** 2026-07-03
**Status:** Draft for review
**Author:** brainstorming session (asanyaga)

## Problem

We have multiple CDM parser adapters — `simple`, `docling`, `llamaparse`, `landing_ai`,
`custom_pipeline` (and want to add e.g. `pdfplumber`). Each turns a source document into a
`ParsedDocument` (CDM). Today we can tell whether an adapter's output is *structurally legal*
(`test_invariants`), whether it *changed* (`test_snapshot`), and what it *cost* (`metrics.jsonl`).

We cannot answer the question that actually drives tool choice:

> "How **good** is this parser on this document, and which parser should I pick?"

We want to establish **"good enough" baselines** and **compare tools across dimensions**
(accuracy, speed, cost). Motivating example: if `pdfplumber` and `docling` both score ~0.95 on
table structure for a document, pick `pdfplumber` — it is CPU-only, fast, and free.

## Goals

- Score a parser's CDM output against ground truth on a named **quality dimension**, producing a
  number in `[0, 1]`.
- Compare multiple parsers on the **same** document + dimension, alongside cost and latency.
- Support **different priorities per use case** — one project cares about precise tables, another
  about content faithfulness — without re-running parsers.
- Start **as simple as possible**; grow abstractions only when a second concrete case demands them.
- Leave clean seams so extension is additive, not a rewrite.

## Non-Goals (for the first slice)

The feature's destination is DB-backed and frontend-surfaced (see "Relationship to existing code").
These are deferred out of the *first* slice, not out of the feature:

- No CI integration, no regression gating. (Named as a seam; deferred.)
- No extrinsic / end-task evaluation (retrieval or answer quality). **Intrinsic first** — score the
  CDM directly against ground truth. Extrinsic is a future layer.
- No profile/weighting engine, no automatic "winner" selection. First slice reports raw
  per-dimension scores.
- No caching layer / capture-score split. First slice runs parsing and scoring inline.
- Implementing a `pdfplumber` adapter — pdfplumber belongs to the existing `custom_pipeline`.

**Frontend note:** the UI *is* in the first slice — a minimal view to author a case + one truth
dimension, run, and read the comparison table. It is intentionally thin (one scorer, no profiles, no
history browsing); richness follows through seam #10.

## Mental model

Two tuples describe the entire system:

```
Case (ground truth):   { doc, target: dimension, expected }
Evaluator:             { parser (+ config), scorer }
Result:                score in [0,1] for (case, parser, target), plus cost + latency
```

- A **dimension** is one independently-failing aspect of parse quality: text faithfulness, table
  structure, reading order, role/structure accuracy, spatial (bbox). Different documents stress
  different dimensions; a parser is never one number.
- A **scorer** is a small, independently testable unit: `score(cdm, expected) -> (float, details)`.
- **One document, many scorers — but ground truth stays per-dimension.** A document is a *container*:
  it may attach several dimension scorers (that is the intended UX). But each dimension carries its
  **own** `expected` artifact and is **explicitly asserted or not** for that document. There is no
  single shared ground-truth object that all scorers read — that path causes all-or-nothing
  authoring, silent false-zeros when a dimension's truth is absent, schema-migration ripple, and
  segmentation bias. See "Ground truth model" below.
- **Ground truth cost scales with what you test**, not with document complexity. A table-stress doc
  ships a gold table; a prose doc ships clean text; neither is forced to label the other's dimension.
- **The result key is `(doc, parser, dimension)`** — a flat row, from day one. Many scorers per doc
  produces a vector of these rows, which is also how baselines and regression are keyed.

## First slice — thin vertical slice (end-to-end)

The first slice is **one scorer wired all the way through**: DB-backed data model → scoring service
→ router → a minimal frontend view. It proves the full stack early. The user flow it delivers:

> Create a case (upload a source document) → attach **one** dimension's ground truth (the `text`
> reference) in the UI → pick parsers → run → see a persisted per-parser score table.

Deliberately one scorer (`text`), one dimension of ground truth authored via UI, no profiles, no
caching. Everything else grows through the seams.

### Data model (lean, mirrors `eval_run` / `extraction_eval`)

Ground truth and results live in the **database**, not files. Sketch (finalized in the plan):

| Entity | Purpose | Key fields |
|---|---|---|
| `ParserEvalCase` | a benchmark document | `id`, `name`, `doc_type`, source document ref, `created_at` |
| `ParserEvalTarget` | one asserted dimension + its truth for a case | `case_id`, `dimension`, `expected` (dimension-typed JSON payload; for `text` = `{ pages: [str] }`) |
| `ParserEvalRun` | one execution over case(s) × parsers | `id`, `status`, selected parsers, `created_at` |
| `ParserEvalResult` | one score cell | `run_id`, `case_id`, `parser`, `dimension`, `score`, `details` (json), `cost`, `latency_ms` — **unique on `(run_id, case_id, parser, dimension)`** |

A **target existing is what "asserts" a dimension** — the result key `(run, case, parser, dimension)`
is the flat row the mental model calls for. Aim for a tiny anchor set (~5 stress docs: prose,
table-heavy, multi-column, scanned, form); grow by adding real failures, not synthetic breadth.

### Ground truth model (why it's per-dimension, not one shared object)

A case with multiple targets is the intended shape, but each target owns its ground truth:

- **Per-dimension `expected`.** The `text` target stores page-segmented reference text; a future
  `table` target stores gold-table HTML. No scorer reads a shared "expected document."
- **Asserted-or-not is explicit.** A scorer runs for a case **only if a target for that dimension
  exists**. A missing dimension means "not evaluated here" — never a silent score of 0. This prevents
  false-zeros and keeps authoring incremental (add a target when you're ready to label it).
- **Prefer content-oriented truth.** Clean text, gold-table HTML — truth that does *not* assume a
  block structure. Structural `expected_blocks`/`expected_page` is reserved for dimensions that are
  inherently positional (reading order, role labels), and even then scorers align by **content, not
  block id** — because parsers legitimately segment blocks differently, and a fixed `expected_blocks`
  would unfairly penalize a parser whose segmentation differs but is correct.

### Ground truth formats per dimension

**The user never authors a `ParsedDocument`.** No block ids, `parent_id`, `reading_order` integers,
`bbox`, or page `block_ids` — those are per-parser artifacts and authoring them would bake in one
parser's segmentation. Instead `expected` is the **minimal parser-agnostic projection** of a single
dimension, and every scorer locates what to compare by **matching text content, not index/id**
(content-anchored alignment) — this is what lets one `expected` fairly score parsers that segment
differently.

CDM vocabulary is reused *selectively*:
- **Value vocabulary reused** where it is intrinsic and parser-agnostic: `BlockRole` names, the
  `Table`/`Cell` shape, and `page` (a PDF's page N is physically page N for every parser).
- **Structural/identity vocabulary never authored**: block ids, `parent_id`, `reading_order`, `bbox`.

`ParserEvalTarget.expected` is a **JSON payload whose shape is discriminated by `dimension`** (this
is seam #2). Each dimension also gets its own authoring widget:

| Dimension | User enters | `expected` payload | CDM vocab | Scorer compares vs | Authoring widget |
|---|---|---|---|---|---|
| **text** | correct readable text, per page | `{ pages: [str] }` | `page` only | per-page slices of `cdm.full_text` (via `Page.start_char/end_char`) | per-page textareas, pre-fillable from a trusted parser |
| **table** | correct table as HTML `<table>` | `{ locator: {page}, html: str }` | `Table`/`Cell` | matching `Block.table`, aligned by page+content | HTML paste + rendered preview |
| **reading_order** | ordered short anchor snippets | `{ anchors: [str] }` | none | positions of anchors located in the parser's block sequence | drag-to-order snippet list |
| **roles** | `snippet → role` assertions | `{ assertions: [{snippet, role, depth?}] }` | `BlockRole` | role of the block whose text matches each snippet | snippet + role dropdown |
| **spatial** (deferred) | gold boxes per region | `{ regions: [{bbox, label}] }` | `BBox` | region boxes, IoU after content match | box-drawing tool |

**OCR is a *condition*, not a dimension.** A scanned document is evaluated on the same dimensions
(chiefly `text`, sometimes `table`); the `expected` format is unchanged. The case is **tagged**
`scanned`/`ocr` so results can be *sliced* ("text faithfulness on scanned docs") — that is where OCR
surfaces, as a filter over the same scores, not a new truth format.

First slice implements the **`text` payload + per-page textarea authoring only**; every other row is
additive via the scorer registry (seam #1) and dimension-typed loader (seam #2).

### The scoring service (backend core)

```
run = create_run(case_ids, parsers)              # persisted, status=running
for case in cases(run):
    for parser in applicable_parsers(case, run):
        # capture reuses ParsingService.parse_and_persist — NOT adapter.adapt directly.
        # The runners do file→raw→adapt, and the returned ParseRun already carries
        # duration_ms + cost + tokens (our cost/latency signal) and same-config reuse.
        parse_run, cdm = capture(parser, case.source, project_id)
        cost, latency = parse_run.cost, parse_run.duration_ms
        for target in case.targets:                            # only asserted dimensions
            score, details = SCORERS[target.dimension](cdm, target.expected)
            save_result(run, case, parser, target.dimension, score, details, cost, latency)
finish_run(run)                                   # status=complete
```

> **Capture reuses existing infrastructure.** `capture(parser, source, project_id)` calls
> `ParsingService.ensure_source_document(...)` then `parse_and_persist(config={"parser": kind}, …)`,
> which returns `(ParseRunCDM, ParsedDocumentCDM)`. Cost/latency come from the `ParseRun`
> (`duration_ms`, `cost`, `input_tokens`, `output_tokens`) — no bespoke timing/metrics needed. Local
> parsers (docling, custom_pipeline, simple) need no cloud client; cloud parsers reuse the existing
> per-parser clients from `get_parsing_service`.

What the UI shows (a comparison table keyed by parser, one row group per case × dimension):

```
acme_invoice · text
  docling          0.97   (cpu,   890ms,  $0)
  custom_pipeline  0.95   (cpu,   140ms,  $0)
  llamaparse       0.99   (cloud, 3.2s,   $0.010)
```

Reuse existing evaluation UI primitives where they fit (`ComparisonTable`, `ScorePill`,
`MetricCard`) rather than building new ones.

### The one scorer: **text faithfulness** (chosen for the first slice)

Rationale for text over table first: a clean reference string is the **cheapest ground truth to
author** (paste/type it in the UI), so it proves the full vertical (upload → author truth → run →
persisted score) with the least labeling before we take on the harder table metric. Table structure
is scorer #2, added purely through the scorer-registry seam — no service change.

- **Ground truth:** `{ pages: [str] }` — the known-correct readable text **per page**, authored in
  the UI (one textarea per page), pre-fillable from a trusted parser's per-page text then corrected.
- **Input from CDM:** per-page text via `Page.start_char/end_char` slices of `cdm.full_text` (fall
  back to concatenated per-page block text if offsets absent).
- **Metric:** compare **page-aligned** — score each page's parsed text vs. its reference, then
  aggregate to a document score (mean, or content-length-weighted). Per page, normalize both sides
  (whitespace, casing per config) and compute three numbers:
  - **similarity** — normalized edit-distance similarity (or token-level F1) of parsed vs. reference.
  - **omission rate** — fraction of reference content missing from the parse.
  - **hallucination rate** — fraction of parsed content absent from the reference.
  Omission and hallucination are called out separately because they are the two failure modes that
  actually hurt downstream RAG; a single blended similarity can hide them. Slice-1 score =
  `similarity`; per-page scores + omission/hallucination travel in `details` (enabling per-page
  attribution) and surface as sub-columns.
- **Page-count mismatch:** if a parser yields a different page count than the reference, unmatched
  reference pages count as fully omitted and unmatched parser pages as fully hallucinated — the
  mismatch is penalized, not silently ignored.

### Components (first slice) — full-stack, mirroring `extraction_eval`

| Layer | Responsibility | File (proposed) |
|---|---|---|
| Models | `ParserEvalCase/Target/Run/Result` | `app/models/parser_eval.py` |
| Repository | persistence + result upsert keyed `(run, case, parser, dimension)` | `app/repositories/parser_eval_repository.py` |
| Scorer registry | `dict[dimension → scorer]`, one entry (`text`) | `app/services/parser_eval/scorers/__init__.py` |
| Text scorer | the faithfulness metric above | `app/services/parser_eval/scorers/text.py` |
| Capture | wraps `ParsingService.parse_and_persist` per parser; cost/latency from `ParseRun` | `app/services/parser_eval/capture.py` |
| Engine/service | orchestrate run → capture → score → persist | `app/services/parser_eval/engine.py`, `service.py` |
| Router | create case/target, trigger run, fetch results | `app/routers/parser_eval.py` |
| Schemas | request/response DTOs | `app/schemas/parser_eval.py` |
| Frontend | author case+truth, run, view comparison | `frontend/src/components/evaluation/parser/…` |

(Names are proposals; final layout settled in the plan. The point: capture, scoring, and persistence
are separate modules from day one, so seams wrap them additively.)

## Extension seams (scaffolding — deliberately NOT built in the first slice)

Each seam is written so the first slice leaves a clean joint. None are implemented until a concrete
case forces them. (The DB + a minimal frontend view are *in* the first slice — see Components — so
seam #10 is only about the *richer* surface that follows.)

1. **Scorer registry.** First slice is a literal `dict[dimension → scorer]` with one entry. Seam: a
   `register("table", fn)` interface so new dimensions are additive files, never edits to the engine.
2. **Dimension-typed truth loader.** `expected` for `text` is a string, for `table` is HTML, for
   `reading_order` a list. Seam: a per-dimension `load_truth` keyed by dimension, so no single "gold
   format" is ever forced across dimensions.
3. **Parser = adapter + config.** E.g. the `custom_pipeline` adapter run under different tool configs
   (pdfplumber-based or otherwise). Seam: an evaluator identity of `(adapter, config)` so the *same*
   adapter under different configs is a distinct comparable row. First slice uses default config and
   identifies parsers by `ParserKind`.
4. **Capture/score split.** First slice runs `adapt()` inline. Seam: a `CachedRun {cdm, cost, latency}`
   boundary persisted, so scoring decouples from expensive parsing once cloud cost/latency
   make re-parsing-per-metric-tweak wasteful. Aligns with existing raw-payload persistence.
5. **Profiles & selection.** First slice reports raw per-dimension scores. Seam: a `Profile { weights, floors,
   tie_tolerance }` applied *at report time* (so one scoring pass serves many projects) that
   produces a weighted total, marks who clears the floor, and applies the cheapest/fastest-wins
   tie-break — directly implementing the pdfplumber-vs-docling decision. Kicks in at >1 dimension.
   Profiles may later map to real app Projects; not now.
6. **Baseline / regression.** Seam: freeze a scorecard as committed baseline (mirroring the existing
   `UPDATE_SNAPSHOTS` pattern) and fail when a parser drops >Δ below its own baseline. No CI initially.
7. **Truth bootstrapping.** Authoring `expected` from scratch is the main cost. Seam: generate a
   draft `expected` from a trusted parser run, then hand-correct — record-then-correct, like
   snapshots.
8. **LLM-as-judge scorer.** For dimensions with no cheap objective ground truth (e.g. figure
   captions). Seam: it is just another scorer behind the registry, but must be validated against a
   small hand-labeled anchor set so its error rate is known before it is trusted. Never the backbone.
9. **Extrinsic layer.** Intrinsic scores are primary. Seam: a future evaluator that feeds a parse
   through chunk → retrieve → answer and scores end-task quality, reusing existing answer-evals work.
10. **Richer frontend + operational surface.** The *minimal* DB + UI (author a case, one truth
    dimension, run, view a comparison table) is in the first slice. This seam is the surface that
    follows: run history browsing, multi-case corpus management, a golden-set-style truth library,
    profile/floor configuration UI, and a regression/baseline dashboard. Built as those needs land.

## Relationship to existing code

**This is a new, first-class, frontend-surfaced feature — not an extension of anything that exists.**

- The `tests/cdm/eval/` invariant/snapshot/cost artifacts are **early test scaffolding from the
  parse feature's first iterations**. They are *not* the foundation for this work and are not being
  extended, refactored, or depended on. Parser eval is greenfield.
- Its **peers** are the other two evals, and it is modeled after them as a sibling feature under
  `app/services/`:
  - **Answer / retrieval eval** — `app/services/eval_service.py` + `eval_run`
    models/repository/router + golden sets + `frontend/src/components/evaluation/`.
  - **Extraction eval** — `app/services/extraction_eval/` package + models/repository/router + UI.
- **Parser eval lives at `app/services/parser_eval/`**, mirroring `app/services/extraction_eval/`,
  and — like both peers — is **DB-backed and surfaced in the app frontend**. The end state is a
  feature a user runs and browses in the UI, not a developer-only script.

**Phasing "start simple" against "it's a real feature":** the destination is the full DB-backed,
frontend-surfaced feature. The **first slice is a thin end-to-end vertical** — one scorer (`text`)
wired through models → repository → engine → router → a minimal UI view — proving the whole stack
before breadth. Additional dimensions, profiles, caching, and the richer surface follow through the
seams. Truth is authored **in the UI** from the first slice (no file corpus).

## Success criteria for the first slice

- In the app UI: create a case (upload a document), author the `text` ground truth, select ≥2
  parsers, run, and see a persisted per-parser score table with cost + latency.
- Scores, cost, and latency persist as `ParserEvalResult` rows keyed `(run, case, parser, dimension)`
  and reload after refresh.
- A case with no `text` target simply isn't scored on `text` — no false-zero. (Asserted-or-not works.)
- Adding the table scorer later requires only: a new scorer file + one registry line + a `table`
  target type — no change to the engine, router, or result model.

## Vision alignment & known deviations (revisit before hardening)

The product's larger purpose is to **evaluate the options available at each stage of a RAG pipeline** —
hand-rolled/custom pipelines vs. providers (LlamaParse) vs. OSS (docling) — using the CDM
(`ParsedDocument`) as the common *projection* of each tool's output that makes them comparable. Parser
eval is the first stage. The first slice takes deliberate shortcuts that are **not** the target shape:

1. **`ParserEvalCase` is a stand-in, not the target entity.** It re-wraps `project_id +
   source_document_id` (plus `name`/`doc_type`/`source_filename`) in a parallel table. In the product
   vision, `Document` and `ParsedDocument` are the first-class, load-bearing primitives — and
   "Document" means *the source_document that belongs to this project*. Eval + ground truth should
   ultimately bind to that first-class project-scoped `Document`/`ParsedDocument` primitive rather than
   a parallel case table. (The `documents` table's chunk/index/folder weight is **vestigial** — an
   artifact of Index being the first pipeline component built; Index has since been refactored onto
   `ParsedDocument` and those references are slated for cleanup. Do not treat that baggage as the
   definition of `Document`.) **Plan:** collapse `ParserEvalCase` onto `Document`/`ParsedDocument` once
   that primitive settles from the Index refactor.
2. **Raw-text ground truth is a convenience, not canonical.** For `text`, ground truth is authored and
   scored as raw text (`{"pages": [str]}`) rather than against `ParsedDocument.Page.Block.text`, to
   feel out the parser flow first. The canonical form follows the primitives later.
3. **`source_filename` on `ParserEvalCase` is redundant** — a denormalization of
   `SourceDocument.filename`; derive via join when the entity is reworked (or drop it).

These are intentional stepping stones for the first slice; revisit before the feature is hardened.

## Open questions (resolve in planning)

- Exact edit-distance vs. token-F1 choice and normalization rules for the text scorer.
- Where cost/latency come from per adapter (job metadata exists for LlamaParse; local parsers need a
  timer and `$0`).

_Out of scope for this feature (noted to prevent scope creep): implementing a `pdfplumber` adapter.
pdfplumber is a tool inside the existing `custom_pipeline` and was only ever an illustrative example;
the corpus compares whatever adapters already exist._
