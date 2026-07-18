# Layout Analysis — the Structure Capability Slot (WS3, slice 1)

**Status:** ⚠️ **Partially superseded** — implemented, but §2 D1, §4 "Retire standalone docling",
and §6 are reversed by
[Docling as a first-class parser kind](2026-07-18-docling-parser-kind-design.md) (2026-07-18).
**Date:** 2026-07-11
**Related:** [OCR + capability-slot pipeline](2026-07-10-ocr-capability-pipeline-design.md) ·
[Custom pipeline overview](2026-06-30-custom-pipeline-design.md) ·
[Docling parser adapter](2026-06-22-docling-parser-adapter-design.md) ·
[Backend parse architecture review](../../architecture/2026-07-11-parse-architecture-review-backend.md)

---

## 1. Context & product framing

The custom pipeline is a set of **capability slots**, each filled by at most one named
tool instance (established in the OCR slice). `layout_analysis` was reserved in the
`Capability` enum as a *staging* capability with no tools. This slice fills it — and in
doing so corrects a structural inversion in the model.

**The product.** This is an internal tool for **quick prototyping and evaluation** of
parsing approaches. Its job is to let a user compose a config and compare it against
another, to answer a specific question for a specific document population: *"is local,
fast, cheap layout analysis (fitz/pdfplumber) good enough for these documents, or do we
need an ML layout model (docling), or a cloud VLM?"* We are **not** chasing the best
layout analysis, OCR, or table detection. We are making capabilities **independently
swappable and comparable** so the local→AI ladder can be walked empirically, with
justification. The config *is* the ladder.

**The inversion this slice fixes.** A mature IDP pipeline is a **DAG with layout at the
root**: layout analysis finds regions + reading order, and text/OCR/table are recognition
backends that *fill* those regions. The current pipeline instead models capabilities as
**peers reconciled by spatial eviction** — `fitz(text)`, `camelot(tables)`,
`tesseract(ocr)` deduplicated by bbox overlap. That was a reasonable bootstrap, but it is
upside-down: `fitz.get_text("blocks")` + a `(y0,x0)` sort **is already a crude layout
analysis** — it was simply never named one. The OCR slice's own limitations L1 (peers, not
a DAG) and L2 (`(y0,x0)` breaks on multi-column pages) are symptoms of having no layout
root.

> **⚠️ Reversed 2026-07-18.** The collapse argued for below holds *inside docling* — where
> `StandardPdfPipeline` emits regions and their text in one pass — but not in IDP generally.
> Region detection and text acquisition fail independently (a layout model can find a perfect
> table region while OCR returns garbage inside it), so a capability model that cannot express
> both is describing docling rather than the domain. Retained here as the reasoning that
> motivated the current code; the successor model separates them again. See
> [2026-07-18-docling-parser-kind-design.md](2026-07-18-docling-parser-kind-design.md) §1.

**Consequence — `text_extraction` is not a real capability.** It was presented as mandatory
and load-bearing, but text extraction is a **non-differentiator** (every tool pulls clean
text off a digital PDF) and, in industry terms, is *recognition within regions*, subordinate
to layout. `text_extraction` and `layout_analysis` are therefore **the same capability at
different tiers**, not two capabilities:

| Tier | Tool | Character |
|------|------|-----------|
| 0 | `fitz` (today), `pdfplumber` (later) | geometric, no ML, fast, CPU, text-only |
| 1 | `docling` (this slice) | ML layout + reading-order + table structure, local, slower |
| 2 | LlamaParse / vision-LLM (exists as other adapters) | cloud, priciest |

They all fill **one required slot** — "turn a page into ordered, labelled regions with
text." This slice collapses `text_extraction` into `layout_analysis` and adds docling as
the first tier-1 tool.

## 2. Decisions (locked in brainstorming)

- **Slice scope = regions + reading order → CDM.** Routing (region-level OCR selection) is
  **out of scope**.
- **Model A — the layout tool is authoritative.** When a `layout_analysis` tool is chosen it
  produces the CDM (regions + reading order + text). It is *not* a pure ordering overlay on
  separate text/OCR tools (that was "model B", rejected for this slice — its main added value
  beyond reordering is routing, which is out of scope). `layout_analysis` is reclassified from
  *staging* to *block-producing*; "staging" was a brainstorming artifact, not a product
  decision.
- **Unify now, not later.** Greenfield, undeployed, sole user, no data migration concerns.
  The only cost of the collapse is engineering effort, and deferring it would mean building
  the merger + config UI twice. So `text_extraction` is retired *now*, not in a follow-up.
- **fitz stays a text-producing `layout_analysis` tool** — a deliberately naive tier-0
  placeholder (text blocks only, order via the merger's `(y0,x0)` sort). Iterating fitz/
  pdfplumber into a *real* geometric layout analyzer happens after docling shows what's worth
  reaching for.
- **Delivery = two PRs**, seam chosen so PR A is a pure refactor (no behaviour change),
  verified by equivalence, and PR B adds docling on top of the proven contract. Same seam the
  OCR slice used.
- **Composition deferred.** docling-alone is the tested path this slice; wiring docling
  alongside external camelot/tesseract is the composition/routing problem, deferred.
- **~~Standalone `ParserKind.DOCLING` is retired (D1).~~** — **REVERSED 2026-07-18.** Both
  premises were wrong: comparability lives in the CDM contract, not a shared config surface
  (LlamaParse and Landing AI are already separate kinds that compare fine); and `DoclingTool`
  declares one capability slot while occupying three. Docling returns as its own parser kind —
  see [2026-07-18-docling-parser-kind-design.md](2026-07-18-docling-parser-kind-design.md).
  The original decision text follows for history:

  Docling is reachable only via
  `custom_pipeline` with `layout_analysis: docling`. The parser-eval engine is
  adapter-agnostic (forwards the adapter string), so eval *logic* is unaffected; the
  follow-throughs are UI-level (§6) plus the accepted consequence that stored `docling` eval
  variants can no longer be *re-run* (their captured results still display).

## 3. PR A — unify the capability model (pure refactor)

**One line:** delete `TEXT_EXTRACTION`; make `LAYOUT_ANALYSIS` the single required,
block-producing structure slot; fitz becomes its tier-0 tool. No new ML, no behaviour change.

### Backend

- **`capabilities.py`**
  - Remove `Capability.TEXT_EXTRACTION`.
  - Move `LAYOUT_ANALYSIS` out of `STAGING` into `BLOCK_PRODUCING`. `STAGING` becomes an empty
    frozenset (kept, with a comment: routing will refill it — see §8).
  - `resolve_precedence` uses `LAYOUT_ANALYSIS` everywhere it used `TEXT_EXTRACTION`.
    Ranks are **identical** (structure at the bottom, below tables; OCR flips above/below it
    via `cid_corrupt` / `ocr_prefer` exactly as before).
- **`config.py`**
  - Required-slot check: `LAYOUT_ANALYSIS` instead of `TEXT_EXTRACTION` (was `config.py:120`).
  - The guard rejecting a non-block-producing capability (was `config.py:116`) now permits
    `LAYOUT_ANALYSIS` automatically, since it moved into `BLOCK_PRODUCING`.
- **`fitz_tool.py`** — `provides = {LAYOUT_ANALYSIS}`. Behaviour untouched; it remains the
  naive tier-0 analyzer.
- **`custom_pipeline_runner.py`** — `structure_instance =
  pipeline.for_capability(LAYOUT_ANALYSIS)`; it still runs first and supplies `page_meta` to
  every other tool and to the adapter (this is the second, load-bearing role the structure
  slot inherits: authoritative page geometry).
- **`base.py`** — `PageMeta` docstring: "sourced from the structure (layout_analysis) tool."
- **The merger is NOT touched in PR A.** fitz sets no intrinsic `reading_order`, so the
  existing `(y0,x0)` sort still runs — this is what makes equivalence hold.

### Frontend

- `CustomPipelineConfig.tsx` — the "Text extraction" slot becomes the "Layout analysis" slot.
  `CAPABILITY_BY_TOOL` maps `fitz`/`pdfplumber` → `layout_analysis`; the required-slot
  guarantee in `normalizeCustomPipelineConfig` targets `layout_analysis`. fitz stays the only
  option in PR A (docling arrives in PR B). Help text introduces the tier framing.
- `CustomPipelineConfig.test.tsx` — slot relabel.
- **No compat shim / no DB migration** (sole user, prototyping): stale dev runs with
  `capabilities.text_extraction` are wiped/ignored, not coerced.

### Acceptance property

For every fixture document and every pipeline expressible under the old config, the new
pipeline produces a **byte-identical `ParsedDocument`** (same block ids, roles,
`reading_order`, `raw_output`). PR A is proven by equivalence, not just unit tests.

## 4. PR B — docling as the tier-1 authoritative tool

### The one merger change

docling's `iterate_items()` **is** reading order — it crosses columns correctly. If the
merger re-sorts docling's blocks by `(y0,x0)` it destroys that order and reintroduces L2. So:

> **Within-page ordering honors a block's intrinsic `reading_order` when present, falling
> back to `(y0,x0)` when absent.**

That is the whole change. It preserves PR A's equivalence *even in PR B*: fitz blocks carry
no `reading_order`, so they still get `(y0,x0)`; only a tool that supplies its own order
(docling) opts into being honored. `Block.reading_order` already exists (`models.py:109`) —
nothing new in the CDM.

### DoclingTool (`tools/docling_tool.py`, implements `PipelineTool`)

- `provides = {LAYOUT_ANALYSIS}` for this slice. docling still emits table content as
  `BlockRole.TABLE` blocks (they flow through as ordinary blocks); claiming
  `TABLE_DETECTION`/`TEXT_OCR` for eviction/composition is a later refinement.
- `run(pdf_path, *, pages, page_meta, emit) -> ToolResult` with
  `blocks_by_capability={LAYOUT_ANALYSIS: blocks}`, `page_meta` (docling knows page sizes),
  `raw`, `native_by_block`, `warnings`, `duration_ms`.
- **Reuses `docling.py`'s adapter logic**: "iterate items → Blocks with roles + normalized
  bboxes + `reading_order` from `enumerate`" and "page sizes → `page_meta`" move into the
  tool. **Dropped**: the `ParsedDocument` assembly and final-id minting — the merger mints
  final ids and `CustomPipelineAdapter` assembles the doc. Blocks come out with provisional
  ids + intrinsic `reading_order`.
- **Batching / semaphore / offload** move in from `docling_runner.py`: page-range batching
  (`page_batch_size`, default 20) with `page_offset`; a module-level `asyncio.Semaphore(1)`
  (docling is memory-hungry — carried over verbatim, **fixed** for this slice, revisited with
  the job-queue work); the runner **offloads each `tool.run` via `asyncio.to_thread`** so a
  parse never runs on the event loop (fixes review §2.1 for docling; incidentally helps
  tesseract/camelot too — not an expansion of scope).
- Errors: a per-page docling failure degrades to `warnings` + `failed_pages`; the run
  completes. A missing/failed docling install is surfaced clearly, not as a mid-parse crash.

### Retire standalone docling (D1)

- Delete `ParserKind.DOCLING`, `_RUNNERS[DOCLING]` (`parsing_service.py:37`),
  `docling_runner.py`, `DoclingRunError` (`errors.py`). Repurpose `docling.py`'s logic into
  `DoclingTool`.
- Tests: delete `test_docling_runner.py`; retarget `test_docling_adapter.py` at the tool.

### Composition stance

docling-alone is the recommended and tested config. The machinery permits adding external
camelot/tesseract alongside docling, but interleaving external blocks into docling's intrinsic
sequence is **out of slice-1 scope** and recorded as a limitation (§8).

### Acceptance

- A two-column fixture parses with docling into **correct cross-column reading order** (L2
  fix, demonstrated).
- fitz on the same fixture still produces its `(y0,x0)` order unchanged (equivalence holds).
- A one-page docling failure → `warnings` + `failed_pages`, run completes.

## 5. Config UI (`CustomPipelineConfig.tsx`)

| Slot | Control |
|------|---------|
| **Layout analysis** *(required)* | Select: `fitz` (PR A) → `+ docling` (PR B). Help text: *"fitz — fast, local, text-only (no real layout yet). docling — local ML layout + reading order + tables; slower."* |
| Table detection | Unchanged — `none / fitz_tables / camelot`. |
| Text OCR | Unchanged — `none / tesseract` + precedence. |
| Eviction thresholds | Unchanged. |

- `CAPABILITY_BY_TOOL`: `fitz`/`pdfplumber`/`docling` → `layout_analysis`.
- The current "Text extraction" `Select` is inert (`onValueChange={() => {}}`) because fitz
  was the only option; PR B makes it a real selector (fitz ↔ docling) via the existing
  `setSlot` helper (handles slot swap + config defaults). docling arriving is a genuine slot
  swap, not a redesign.
- When docling is selected, fitz-specific checkboxes (`include_images`, `span_detail`) hide
  and a minimal docling panel shows — slice-1 config is just `page_batch_size` (default 20).
  Add knobs when we learn what matters.

## 6. Parser-eval follow-throughs (D1)

The eval engine is adapter-agnostic (`engine.py:36` forwards `variant["adapter"]` →
`parsing_service.parse_and_persist(parser=adapter)`), so eval logic is unaffected. UI-level
changes only:

1. **`NewRunDialog.tsx:16`** — `DEFAULT_ADAPTER = 'docling'` → `custom_pipeline` seeded with a
   `layout_analysis: docling` config (the real functional break, since a bare `docling`
   adapter would no longer resolve).
2. **`ParseMethodSelector.tsx:36`** — remove the top-level `docling` parse method.
3. **`ParserComparisonTable`** — keep the cosmetic `'Docling'` label so historical eval rows
   with `adapter: "docling"` still render a friendly name.

**Accepted consequence:** stored `docling` eval variants can no longer be *re-run*
(re-running would call `ParserKind("docling")` → error); their captured results still display.
Re-expressing docling as `custom_pipeline` + `layout_analysis: docling` is the intended path.

## 7. Testing

**PR A**
- **Equivalence harness (load-bearing):** fixture PDFs (clean digital, multi-column, tables,
  image+OCR) → assert `ParsedDocument` byte-identical to a golden captured on `main`.
- Unit: `build_pipeline_config` requires `layout_analysis`; rejects a config missing it;
  `resolve_precedence` truth table unchanged under the renamed capability.
- Frontend: slot relabel; `normalizeCustomPipelineConfig` guarantees `layout_analysis`.

**PR B**
- **Pure functions, no docling binary:** blocks *with* intrinsic `reading_order` → merger
  honors it; *without* → `(y0,x0)` fallback. The merger change is tested without invoking
  docling.
- **Tool logic (retargeted `test_docling_adapter.py`):** captured `DoclingDocument` fixture →
  `DoclingTool.run` yields blocks with roles, normalized bboxes, populated `reading_order`,
  and `page_meta`.
- **Integration (`skipif` no docling):** two-column fixture → correct cross-column order (L2);
  fitz unchanged (equivalence); one-page failure → `warnings` + `failed_pages`, run completes.
- **Threading:** `tool.run` is offloaded (not on the event loop); the docling `Semaphore(1)`
  serializes concurrent runs.
- Frontend: docling appears as a `layout_analysis` option; `NewRunDialog` default variant is
  `custom_pipeline`+docling and round-trips.

## 8. Known limitations & deferred (accepted deliberately)

| # | Item |
|---|------|
| 1 | **Composition unwired.** docling-alone is the tested path; interleaving external camelot/tesseract into docling's intrinsic order is deferred (the composition/routing problem). |
| 2 | **`STAGING` is now empty.** Pure bbox+label layout detectors (needing a separate recognition pass — e.g. LayoutParser/PubLayNet, a bare Surya detector) are deferred to the **router slice**. The `PipelineTool` contract must **not** assume "layout always carries text," so such a detector can slot in later. |
| 3 | **fitz stays naive.** tier-0 remains text-only with `(y0,x0)` order; making fitz/pdfplumber a real geometric layout analyzer (column detection / XY-cut) is the post-docling iteration. |
| 4 | **Routing out of scope.** Region-level OCR selection (mitigating OCR-slice L3) is not addressed here; it is the motivating workload for the router slice and for the parked execution-location axis. |
| 5 | **docling multi-capability deferred.** docling emits only `layout_analysis` this slice; having it also claim `table_detection`/`text_ocr` (one run, multiple slots via `emit` masking) is a later refinement. |

## 9. Sequencing

1. **PR A** — capability-model unification (equivalence-gated, no ML). Merges first.
2. **PR B** — docling tool + the merger reading-order change + D1 retirement, on top of the
   proven contract.

Each PR is a single GitHub issue + PR per the project workflow. Per the pre-implementation
gate, an issue with acceptance criteria is created and confirmed before implementation begins.
