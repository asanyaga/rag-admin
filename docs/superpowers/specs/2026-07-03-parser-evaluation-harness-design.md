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

## Non-Goals (for v0)

- No CI integration, no regression gating. (Named as a seam; deferred.)
- No extrinsic / end-task evaluation (retrieval or answer quality). **Intrinsic first** — score the
  CDM directly against ground truth. Extrinsic is a future layer.
- No profile/weighting engine, no automatic "winner" selection. v0 prints raw per-dimension scores.
- No caching layer / capture-score split. v0 runs parsing and scoring inline.
- No UI. Output is a printed table + a JSON/JSONL artifact.

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
- **Ground truth is per-dimension**, not per-document. A case carries `expected` only for the
  dimensions it tests. A table-stress doc ships a gold table; a prose doc ships clean text. Ground
  truth cost scales with *what you test*, not with document complexity — this is what makes the
  corpus sustainable.

## v0 design — the minimal loop

### Corpus layout

A tiny anchor set of ~5 hand-picked stress documents (e.g. one prose, one table-heavy, one
multi-column, one scanned, one form). Grow by adding real failures, not synthetic breadth.

```
backend/app/cdm/eval/benchmark/
  <case_name>/
    source.<ext>          # the document
    case.yaml             # manifest: targets + which parsers apply
    truth/                # dimension-typed ground-truth artifacts
      text.txt            #   clean reference text  (text dimension)
      p2.html             #   gold table            (table dimension)
```

`case.yaml`:

```yaml
name: acme_invoice
doc_type: invoice
parsers: [pdfplumber, docling, llamaparse]   # omit/[] = all registered parsers
targets:
  - dimension: text
    expected: truth/text.txt
```

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
  pdfplumber   0.98   (cpu,   120ms,  $0)
  docling      0.97   (cpu,   890ms,  $0)
  llamaparse   0.99   (cloud, 3.2s,   $0.010)
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
| Case loader | parse `case.yaml`, resolve truth paths | `app/cdm/eval/harness/cases.py` |
| Capture | call `adapter.adapt(...)`, time it, read cost from `parser_extras`/job metadata | `app/cdm/eval/harness/capture.py` |
| Scorer registry | hardcoded `dict[str, Scorer]` | `app/cdm/eval/harness/scorers/__init__.py` |
| Text scorer | the faithfulness metric above | `app/cdm/eval/harness/scorers/text.py` |
| Reporter | printed table + `results.json` | `app/cdm/eval/harness/report.py` |
| Entry point | `python -m app.cdm.eval.harness.run [--benchmark DIR]` | `app/cdm/eval/harness/run.py` |

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
3. **Parser = adapter + config.** The `pdfplumber_config` idea. Seam: an evaluator identity of
   `(adapter, config)` so the *same* adapter under different configs is a distinct comparable row.
   v0 uses default config and identifies parsers by `ParserKind`.
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

## Relationship to existing eval code

- Keeps `tests/cdm/eval/` invariant + snapshot + cost tests as-is (structural + change + cost
  layers). This harness adds the missing **quality-vs-ground-truth** and **cross-parser comparison**
  layers.
- Lives under `app/cdm/eval/` (library, reusable) rather than test-only, because capture is a
  deliberate script that may spend money, and the scorers are reusable logic.

## Success criteria for v0

- Running the entry point over the anchor corpus prints a per-case, per-parser table of text
  faithfulness scores with cost + latency, and writes `results.json`.
- Adding the table scorer later requires only: a new scorer file + registry line + a `truth/*.html`
  artifact and a `case.yaml` target — no change to the run loop, reporter, or case loader.

## Open questions (resolve in planning)

- Exact edit-distance vs. token-F1 choice and normalization rules for the text scorer.
- Where cost/latency come from per adapter (job metadata exists for LlamaParse; local parsers need a
  timer and `$0`).
- Whether `pdfplumber` is added as a new `ParserKind` + adapter now, or the corpus starts with
  existing adapters and pdfplumber lands with the table scorer.
