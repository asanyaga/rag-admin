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

**Frontend note:** the feature *is* surfaced in the app UI; whether the UI lands in the first slice
or the second is the lead Open Question below. The "printed table + `results.json`" form is the
minimal developer-facing output of the scoring core, which the UI later reads — not the end state.

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

## v0 design — the minimal loop

### Corpus layout

A tiny anchor set of ~5 hand-picked stress documents (e.g. one prose, one table-heavy, one
multi-column, one scanned, one form). Grow by adding real failures, not synthetic breadth.

```
backend/app/services/parser_eval/benchmark/
  <case_name>/
    source.<ext>          # the document
    case.yaml             # manifest: targets + which parsers apply
    truth/                # dimension-typed ground-truth artifacts
      text.txt            #   clean reference text  (text dimension)
      p2.html             #   gold table            (table dimension)
```

`case.yaml` — a doc may attach multiple targets; each names its own dimension + `expected`, and a
dimension is asserted **only** if it appears here:

```yaml
name: acme_invoice
doc_type: invoice
parsers: [docling, llamaparse, custom_pipeline]   # omit/[] = all registered parsers
targets:
  - dimension: text
    expected: truth/text.txt
  - dimension: table
    expected: truth/p2.html         # table is asserted; reading_order/roles are NOT for this doc
```

### Ground truth model (why it's per-dimension, not one shared object)

A document containing multiple targets is the intended shape, but each target owns its ground truth:

- **Per-dimension `expected`.** The `text` target reads `truth/text.txt`; the `table` target reads
  `truth/p2.html`. No scorer reads a shared "expected document."
- **Asserted-or-not is explicit.** A scorer runs for a doc **only if that dimension is a target**. A
  missing dimension means "not evaluated here" — never a silent score of 0. This prevents
  false-zeros and keeps authoring incremental (add a target when you're ready to label it).
- **Prefer content-oriented truth.** Clean text, gold-table HTML — truth that does *not* assume a
  block structure. Structural `expected_blocks`/`expected_page` is reserved for dimensions that are
  inherently positional (reading order, role labels), and even then scorers align by **content, not
  block id** — because parsers legitimately segment blocks differently, and a fixed `expected_blocks`
  would unfairly penalize a parser whose segmentation differs but is correct.

### The run

```
for case in load_cases(benchmark_dir):
    for parser in applicable_parsers(case):
        run = capture(parser, case.doc)          # -> { cdm, cost, latency }
        for target in case.targets:
            expected = load_truth(target)         # dimension-typed loader
            score, details = SCORERS[target.dimension](run.cdm, expected)
            results.append(Result(case, parser, target, score, run.cost, run.latency, details))
report(results)                                   # printed table + results.json
```

Printed output shape:

```
acme_invoice · text
  docling          0.97   (cpu,   890ms,  $0)
  custom_pipeline  0.95   (cpu,   140ms,  $0)
  llamaparse       0.99   (cloud, 3.2s,   $0.010)
```

### First scorer: **text faithfulness** (chosen for v0)

Rationale for picking text over table first: clean reference text is the **cheapest ground truth
to author**, so it proves the entire loop (corpus → capture → scorer → report) end-to-end with the
least up-front labeling, before we take on the harder table metric. Table structure is scorer #2,
added purely through the scorer-registry seam — no harness change.

- **Ground truth:** `truth/text.txt` — the known-correct readable text of the document.
- **Input from CDM:** `cdm.full_text` (fall back to concatenated block text if absent).
- **Metric:** normalize both sides (whitespace, casing per config), then report three numbers,
  combined into the `[0,1]` score:
  - **similarity** — normalized edit-distance similarity (or token-level F1) of parsed vs. reference.
  - **omission rate** — fraction of reference content missing from the parse.
  - **hallucination rate** — fraction of parsed content absent from the reference.
  Omission and hallucination are called out separately because they are the two failure modes that
  actually hurt downstream RAG; a single blended similarity can hide them. v0 score =
  `similarity`; omission/hallucination travel in `details` and are printed as sub-columns.

### Components (v0)

| Component | v0 form | File (proposed) |
|---|---|---|
| Case loader | parse `case.yaml`, resolve truth paths | `app/services/parser_eval/cases.py` |
| Capture | call `adapter.adapt(...)`, time it, read cost from `parser_extras`/job metadata | `app/services/parser_eval/capture.py` |
| Scorer registry | hardcoded `dict[str, Scorer]` | `app/services/parser_eval/scorers/__init__.py` |
| Text scorer | the faithfulness metric above | `app/services/parser_eval/scorers/text.py` |
| Reporter | printed table + `results.json` | `app/services/parser_eval/report.py` |
| Entry point | `python -m app.services.parser_eval.run [--benchmark DIR]` | `app/services/parser_eval/run.py` |

(Directory names are proposals; final layout settled in the implementation plan. The point is that
capture, scoring, and reporting are separate modules from day one, even while wired inline.)

## Extension seams (scaffolding — deliberately NOT built in v0)

Each seam is written so v0 leaves a clean joint. None are implemented until a second concrete case
forces them.

1. **Scorer registry.** v0 is a literal `dict[dimension → scorer]`. Seam: a `register("table", fn)`
   interface so new dimensions are additive files, never edits to the run loop.
2. **Dimension-typed truth loader.** `expected` for `text` is a string, for `table` is HTML, for
   `reading_order` a list. Seam: a per-dimension `load_truth` keyed by dimension, so no single "gold
   format" is ever forced across dimensions.
3. **Parser = adapter + config.** E.g. the `custom_pipeline` adapter run under different tool configs
   (pdfplumber-based or otherwise). Seam: an evaluator identity of `(adapter, config)` so the *same*
   adapter under different configs is a distinct comparable row. v0 uses default config and
   identifies parsers by `ParserKind`.
4. **Capture/score split.** v0 runs `adapt()` inline. Seam: a `CachedRun {cdm, cost, latency}`
   boundary persisted to disk, so scoring decouples from expensive parsing once cloud cost/latency
   make re-parsing-per-metric-tweak wasteful. Aligns with existing raw-payload persistence.
5. **Profiles & selection.** v0 prints raw per-dimension scores. Seam: a `Profile { weights, floors,
   tie_tolerance }` applied *at report time* (so one scoring pass serves many projects) that
   produces a weighted total, marks who clears the floor, and applies the cheapest/fastest-wins
   tie-break — directly implementing the pdfplumber-vs-docling decision. Kicks in at >1 dimension.
   Profiles may later map to real app Projects; not now.
6. **Baseline / regression.** Seam: freeze a scorecard as committed baseline (mirroring the existing
   `UPDATE_SNAPSHOTS` pattern) and fail when a parser drops >Δ below its own baseline. No CI in v0.
7. **Truth bootstrapping.** Authoring `expected` from scratch is the main cost. Seam: generate a
   draft `expected` from a trusted parser run, then hand-correct — record-then-correct, like
   snapshots.
8. **LLM-as-judge scorer.** For dimensions with no cheap objective ground truth (e.g. figure
   captions). Seam: it is just another scorer behind the registry, but must be validated against a
   small hand-labeled anchor set so its error rate is known before it is trusted. Never the backbone.
9. **Extrinsic layer.** Intrinsic scores are primary. Seam: a future evaluator that feeds a parse
   through chunk → retrieve → answer and scores end-task quality, reusing existing answer-evals work.
10. **DB-backed + frontend surface (the destination, not optional).** Unlike the other seams, this
    is a committed goal, sequenced as a later slice: `parser_eval` models/repository/router, ground
    truth persisted (golden-set style), results stored per run, and a `frontend/.../evaluation` view
    to trigger and browse runs. The v0 core (scoring loop + data model) is shaped so these layers
    wrap it additively. The only open question is *which slice* introduces the UI (see Open
    Questions), not *whether*.

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
frontend-surfaced feature. We still build it in thin slices, starting with the smallest correct
core (the scoring loop + data model) and adding the router/UI in a following slice, rather than
front-loading a large surface. Exactly where the frontend enters is settled in the implementation
plan (see Open Questions). The v0 module boundaries above are chosen so the DB/router/UI layers wrap
the core additively.

## Success criteria for v0

- Running the entry point over the anchor corpus prints a per-case, per-parser table of text
  faithfulness scores with cost + latency, and writes `results.json`.
- Adding the table scorer later requires only: a new scorer file + registry line + a `truth/*.html`
  artifact and a `case.yaml` target — no change to the run loop, reporter, or case loader.

## Open questions (resolve in planning)

- **Which slice introduces the frontend.** Options: (a) backend scoring core + data model first,
  UI in the immediately-following slice; or (b) a thin end-to-end vertical slice (one scorer wired
  through DB + a minimal UI view) from the start. Determines whether early ground truth is authored
  as files or through the UI.
- Exact edit-distance vs. token-F1 choice and normalization rules for the text scorer.
- Where cost/latency come from per adapter (job metadata exists for LlamaParse; local parsers need a
  timer and `$0`).

_Out of scope for this feature (noted to prevent scope creep): implementing a `pdfplumber` adapter.
pdfplumber is a tool inside the existing `custom_pipeline` and was only ever an illustrative example;
the corpus compares whatever adapters already exist._
