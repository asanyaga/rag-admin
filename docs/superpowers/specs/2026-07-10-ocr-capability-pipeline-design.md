# OCR + Capability-Slot Pipeline (WS2, slice 1)

**Status:** Design — approved in brainstorming, pending spec review
**Date:** 2026-07-10
**Related:** [WS2 constraints parking lot](2026-07-09-ocr-ws2-constraints.md) ·
[WS1 standalone Probe](2026-07-09-probe-standalone-design.md) ·
[Custom pipeline overview](2026-06-30-custom-pipeline-design.md)

---

## 1. Context

WS1 shipped the standalone Probe — an evidence provider that reports, per page and per
image region, what a document *is*. WS2 makes the parser act on that: **add OCR to the
custom pipeline**, so text trapped in images and text on scanned pages is actually
extracted.

Doing that surfaced a structural problem. Despite its name, the custom pipeline is
**composable in name only**:

| Slot | How it is enforced today |
|------|--------------------------|
| Text | Hardcoded string — `custom_pipeline_runner.py` raises `"custom pipeline requires a 'fitz' tool"`. Not swappable. |
| Table | `TABLE_TOOL_IDS` frozenset + a `len(...) > 1` count check over a flat `tools: [...]` list. |
| Merge | Binary positional call — `merge(fitz_result, table_result)`. |

There is no capability abstraction. This slice introduces one, then adds OCR into it.

**Product framing.** This application exists to let a user *evaluate* parsing approaches
and cut through vendor marketing ("awesome_parser beats all other parsers"). Nobody
differentiates on text extraction — every parser pulls clean text off a digital PDF. The
real battleground is **OCR quality on degraded scans, table structure recognition, and
layout/reading order on complex documents**. The pipeline must therefore make those
capabilities *independently swappable and comparable*. Configuration over convention.

## 2. Core model — capability slots

The pipeline is a fixed set of **IDP capabilities**, each filled by at most **one named
tool instance**.

```jsonc
{
  "tools": {
    "fitz":      { "tool": "fitz",      "config": { "include_images": true } },
    "camelot":   { "tool": "camelot",   "config": { "flavor": "lattice" } },
    "tesseract": { "tool": "tesseract", "config": { "pages": "auto", "lang": "eng" } }
  },
  "capabilities": {
    "text_extraction": "fitz",       // required
    "table_detection": "camelot",    // optional
    "text_ocr":        "tesseract"   // optional
  },
  "precedence": { "text_ocr": "fallback" },
  "eviction_overlap_threshold": 0.5,
  "ocr_eviction_threshold": 0.3,

  // Per-page facts consumed by BOTH the OCR tool (`pages: "auto"`) and the
  // merger (the CID precedence flip). Computed once, in the runner.
  "page_flags": {
    "min_chars": 10,                 // below this, the page has no usable text layer
    "cid_ratio": 0.3,                // private-use-area char ratio => cid_corrupt
    "min_uncovered_coverage": 0.10,  // image must cover >=10% of the page to matter
    "covered_overlap": 0.6           // >=60% overlap with native text => "covered"
  }
}
```

### Rules

- **Capabilities are a closed enum.** Slice 1 implements `text_extraction` (required),
  `table_detection`, `text_ocr`. `layout_analysis` exists in the enum but has no tools yet.
- **Two capability kinds.**
  - *Block-producing* (`text_extraction`, `table_detection`, `text_ocr`) emit blocks that
    compete for page area, governed by the precedence matrix.
  - *Staging* (`layout_analysis`) orders and routes; it never competes. Declared now so the
    merger does not assume every capability competes.
- **Tools declare `provides: frozenset[Capability]`.** The executor derives
  `assigned(instance)` from the slot references and passes `emit=assigned`, **masking off**
  everything not assigned. So `text_extraction: docling, table_detection: camelot`
  automatically runs docling with table structure disabled — derived, not hand-specified.
  Assigning a capability to a tool that does not `provide` it is a config error.
- **One instance → one run**, regardless of how many slots reference it. This is what makes
  `text/tables/ocr/layout: docling` mean a single docling execution.
- **`TABLE_TOOL_IDS` and its count guard are deleted, not generalized.** Two table tools
  becomes structurally unrepresentable.
- **`LocalTool` → `PipelineTool`** (constraint C2).
- **No compat shim.** There is no legacy data; clean cut-over.

### Deliberate limitation

One tool per capability **forbids ensembling** (two OCR engines voting, highest-confidence
wins). This is intentional: an evaluation tool compares configurations *across runs*, not
within a run. If ensembling is ever wanted, this model must break — state it, don't
discover it.

## 3. Merger — precedence and reconciliation

### The reconciliation model

OCR runs **wholesale on selected pages**; its output is then **filtered spatially**. We do
*not* feed probe regions into the OCR tool.

Rationale: OCR engines already perform text detection. Give tesseract a page raster and it
returns word/line boxes. Finding text inside an image is the *engine's* job. So the two real
decisions are:

1. **Which pages to OCR** — a cost/routing decision (§4).
2. **Which OCR output to keep** — resolved spatially: discard OCR blocks that overlap
   existing native text, because native text is exact and OCR is lossy.

The mixed-page case then falls out for free: on a page with a native text layer plus a logo
and an embedded table screenshot, OCR returns boxes for all three; reconciliation drops the
body text (already covered) and keeps the logo and table text (nothing underneath).
**What survives is exactly the text that was trapped in images** — with no region hand-off
and no dependency on `app/probe/`.

### Precedence

Block-producing capabilities rank `table_detection` above text — structure beats loose
spans. The only variable is whether OCR sits above or below native text:

```python
ocr_outranks_text(page) = (precedence.text_ocr == "prefer") or page.cid_corrupt
```

| Situation | Order | Why |
|---|---|---|
| Default (`fallback`) | `table` > `text` > `ocr` | Native text is exact; OCR is lossy |
| CID-corrupt page | `table` > `ocr` > `text` | Native text exists but is garbage |
| `prefer` (whole run) | `table` > `ocr` > `text` | Scans already OCR'd badly by another tool |

The CID flip and `prefer` are **the same mechanism**, applied per-page vs per-run.

`prefer` exists because a large share of real-world PDFs are scans already OCR'd by a cheap
tool: a *bad but valid* text layer, real characters, wrong ones. `pua_ratio` cannot detect
it (no private-use chars) and `char_count` cannot (plenty of chars). No heuristic wins here,
so the router decides. Precedence is configuration, not convention.

### Eviction

For each overlapping pair, the lower-precedence block is evicted and logged.
`overlap_fraction(winner, loser) = intersection / area(loser)` is reused verbatim from the
existing merger; only its parameter names change.

Two thresholds, because the pairs differ geometrically:

- `eviction_overlap_threshold: 0.5` — table vs text *(existing behaviour, unchanged)*
- `ocr_eviction_threshold: 0.3` — OCR blocks sit *inside* native paragraphs, so partial
  coverage already implies duplication

### Reading order

**Requirement:** every producer emits blocks at **paragraph/region granularity** with
intra-block text order preserved. **The merger never reorders text within a block.**

Tesseract returns a `block → paragraph → line → word` hierarchy. We aggregate to
**paragraph-level blocks**. We do **not** emit line-level blocks. Once no producer emits
lines, the merger's existing cross-block `(y0, x0)` sort is exactly as good as it is today
for fitz.

Stated honestly: `(y0, x0)` **still breaks on genuinely multi-column pages**. It does today,
for fitz; OCR does not make it worse. That is the defect `layout_analysis` fixes next slice
by supplying reading order as a *staging* capability. This slice does not pretend to solve
it.

### Audit trail

`raw_output` stops being two hardcoded slots and explains itself in capability terms:

```jsonc
{
  "instances": {
    "fitz":      { "tool": "fitz", "capabilities": ["text_extraction"], "raw": …, "block_map": … },
    "tesseract": { "tool": "tesseract", "capabilities": ["text_ocr"], "raw": …, "block_map": … }
  },
  "evicted": [{
    "block_id": "…", "capability": "text_ocr",
    "reason": "covered_by", "winner_capability": "text_extraction",
    "won_by": "<final block id>", "overlap_fraction": 0.82
  }]
}
```

An eviction record now reads *"an OCR block was dropped because native text already covered
82% of it"* — the same explainability ethos as the probe's receipts, and what makes
configuration comparison honest.

## 4. The OCR tool

### Identity

**The engine is the tool.** `tesseract` (later `paddleocr`, `easyocr`) are tool ids filling
the `text_ocr` slot. The capability slot already enforces one-engine-per-run, so no separate
`OcrEngine` protocol is needed: engine pluggability *is* slot pluggability (constraint C3
satisfied structurally).

Slice 1 ships one concrete `TesseractTool` implementing `PipelineTool`. If a second engine
later reveals genuinely shared machinery (rasterization, paragraph assembly), extract a base
class **then**, informed by a real second case.

### Config

```jsonc
"tesseract": { "tool": "tesseract", "config": {
  "pages": "auto",          // "auto" | "all" | [3, 7]
  "lang": "eng",
  "psm": 3,                 // tesseract page-segmentation mode
  "dpi": 300,               // render resolution
  "min_confidence": 0.0     // 0..1
}}
```

`min_confidence` defaults to **0.0 on purpose**: an evaluation tool must not silently
discard low-confidence OCR. Surface it; let the user decide.

There is **no `execution` field**. Execution location is parked (§9) — omitting the field
bakes in nothing, and adding it later is purely additive.

### Page selection — how `auto` works

`auto` needs per-page facts, and so does the merger (the CID flip). They are computed
**once, in the runner**, and fed to both.

```python
# custom_pipeline/page_flags.py — fitz metadata only, no rasterization
PageFlags(char_count, pua_ratio, cid_corrupt, has_uncovered_image)

ocr_page = (char_count < min_chars) or cid_corrupt or has_uncovered_image
```

All four thresholds live in the pipeline-level `page_flags` config block (§2), **not** in the
tesseract tool config — because the merger consumes `cid_corrupt` even when no OCR tool is
configured. `cid_corrupt = pua_ratio > cid_ratio`.

`has_uncovered_image` = an image whose area ≥ `min_uncovered_coverage` (0.10) **and** whose
overlap with native text spans < `covered_overlap` (0.6).

That third term is load-bearing: **it stops a full-bleed marketing image from triggering OCR
on every page it appears on.** Defining `auto` as merely "the page has an image" would
reintroduce exactly the false positive that motivated this whole workstream.

**Accepted trade — duplication over coupling.** `page_flags` re-derives ~40 lines of
probe-shaped heuristics (char count, PUA ratio, image/text overlap) inside the pipeline. The
probe is *advisory evidence* with its own lifecycle; the pipeline needs *deterministic
execution flags*. Importing `app/probe/` into the parse path would bind parsing to a
diagnostic tool. If the two implementations drift in a way that matters, that is the trigger
to extract a shared leaf util — not before.

### Execution order

```
1. compute page_flags                     (fitz metadata, no raster)
2. text_extraction tool                   (required)
3. table_detection tool                   (optional; uses page_meta from step 2)
4. text_ocr tool                          (optional; only the selected pages)
5. merge(results, page_flags, precedence) (capability precedence + eviction)
6. adapter → CDM ParsedDocument
```

The OCR tool renders each selected page at `dpi`, calls tesseract, aggregates the
`block → paragraph → line → word` hierarchy into paragraph-level blocks, normalizes pixel
bboxes to `[0, 1]`, and sets `Block.quality.confidence` from the mean word confidence.

Provenance for evaluation: `Block.parser_extras = {"producer": "tesseract",
"capability": "text_ocr", "engine": "tesseract"}`.

### Errors

A per-page OCR failure degrades to a **warning + `failed_pages`** on the `ParseRun` (both
fields already exist); a single unreadable page must not discard a 200-page parse. A missing
tesseract binary is a **config-time** error naming the tool, not a mid-parse crash.

## 4b. Delivery — two PRs

The slice ships as two sequential PRs. The seam is chosen so the first is a **pure
structural refactor with no behaviour change**, which is far safer to review than a refactor
tangled with a new capability.

### PR A — capability refactor (no OCR)

- `capabilities.py` — Capability enum, block-producing vs staging, precedence resolution
- `config.py` — new contract (`tools` / `capabilities` / `precedence` / `page_flags` /
  thresholds), instance→slot resolution, capability masking; **delete** `TABLE_TOOL_IDS` and
  the `len(...) > 1` guard
- `tools/base.py` — `LocalTool` → `PipelineTool`, `provides`, `emit`,
  `ToolResult.blocks_by_capability`
- `fitz_tool.py`, `camelot_tool.py`, `fitz_tables_tool.py` — ported to the new contract
- `page_flags.py` — `char_count`, `pua_ratio`, `cid_corrupt` only
  (`has_uncovered_image` lands in PR B, where its only consumer lives — no dead code)
- `merger.py` — N-way, capability-aware eviction; capability-tagged audit trail
- `custom_pipeline_runner.py` — slot-driven; the hardcoded `'fitz'` requirement dies
- Frontend — `CustomPipelineConfig.tsx` emits the new config; text presented as a *slot*
  (fitz the only option); table slot unchanged; no OCR controls yet
- `ParseMethodSelector.test.tsx` updated

**Acceptance property:** for any document and any pipeline expressible under the old config,
the new pipeline produces an **identical `ParsedDocument`**. The refactor is verified by
equivalence, not just by unit tests.

### PR B — tesseract OCR

- `tesseract_tool.py` — rasterization, `pages: auto|all|[…]`, paragraph aggregation
- `page_flags.py` — add `has_uncovered_image`
- Precedence wiring — `ocr_outranks_text()`, `ocr_eviction_threshold`
- Frontend — OCR slot, `precedence` control, OCR thresholds
- Tests — paragraph aggregation, `auto` selection, and the mixed-page acceptance test

PR B's plan is written **after PR A merges**, from this same spec — no further brainstorming
required. `precedence.text_ocr: "prefer"` (L6) lands in PR B and remains cheap to cut if it
still feels speculative then.

## 5. Backend structure

```
backend/app/cdm/adapters/custom_pipeline/
  capabilities.py     # Capability enum; block-producing vs staging; precedence resolution
  config.py           # tools/capabilities/precedence contract; instance→slot resolution; masking
  page_flags.py       # PageFlags + compute_page_flags (fitz metadata only)
  merger.py           # N-way, capability-aware eviction; capability-tagged audit trail
  tools/
    base.py           # PipelineTool protocol (renamed from LocalTool), ToolResult, PageMeta
    fitz_tool.py  camelot_tool.py  fitz_tables_tool.py
    tesseract_tool.py # NEW
backend/app/services/parsing/custom_pipeline_runner.py   # slot-driven, no hardcoded 'fitz'
```

Contract changes:

```python
class PipelineTool(Protocol):
    tool_id: str
    provides: frozenset[Capability]
    def run(self, pdf_path, *, pages=None, page_meta=None,
            emit: frozenset[Capability]) -> ToolResult

class ToolResult(BaseModel):
    tool_id: str
    blocks_by_capability: Dict[Capability, List[Block]]   # was: blocks
    page_meta: Dict[int, PageMeta]
    raw: Any
    native_by_block: Dict[str, Any]
    warnings: List[str]
    duration_ms: int
```

Single-capability tools assert `emit == provides`.

## 6. Frontend

`CustomPipelineConfig.tsx` already renders capability slots — *"Fitz — always on"* plus a
*"Table extraction"* select. The backend now agrees, and the *"always on"* copy dies (it was
the symptom of a frozen slot).

| Slot | Control |
|---|---|
| Text extraction | Select — `fitz` (one option today, but a *slot*: `pdfplumber`/`docling` become options, not a redesign) |
| Table detection | Select — `none / fitz_tables / camelot` + existing config panels, unchanged |
| Text OCR | Select — `none / tesseract` + panel: `pages`, `lang`, `psm`, `dpi`, `min_confidence` |
| Precedence *(shown only when OCR is on)* | `Native text wins (fallback)` / `OCR wins (prefer)`, with help text: *"Choose 'OCR wins' for scans that already carry a poor-quality text layer."* |
| Advanced | `eviction_overlap_threshold`, `ocr_eviction_threshold` |

**Instance keying:** the UI keys instances by tool id — a 1:1 simplification of the
named-instance model. A future multi-capability tool referenced from two slots therefore
resolves to a single instance automatically, so docling-in-two-slots needs no UI redesign.
Richer named-instance setups remain available to API and agent callers.

Knock-on: `ParseMethodSelector.test.tsx` asserts the *Table extraction* combobox and will
need a light update.

## 7. Testing

Tesseract 5.5.0 is present on the dev machine **and** in the backend image, so OCR
integration tests run everywhere. They are still guarded with `skipif` for portability.

**1. Pure functions — no PDF, no binary.** This is where the design's risk lives.
- Precedence: truth table — `table > text > ocr`; CID flip; `prefer` mode.
- Merger: N-way eviction; capability-tagged audit records; **text within a block is never
  reordered**.
- Paragraph aggregation: feed a *fixture* `image_to_data` dict (word rows with
  `block_num`/`par_num`/`line_num`/`conf`) → assert paragraph-level blocks, preserved order,
  unioned bbox, mean confidence. The reading-order rule is tested without invoking OCR.

**2. Fixture PDFs (fitz-generated), still no OCR.**
- `page_flags`: scanned → `char_count == 0`; CID-corrupt → high `pua_ratio`;
  **image covered by native text → `has_uncovered_image is False`** (the false-positive
  killer); full-bleed image with no text → `True` (asserting the *documented* wasted-compute
  behaviour, so nobody "fixes" it by accident).
- `pages: "auto" | "all" | [3]` selection is honoured.

**3. Integration (`skipif` no tesseract binary).**
- Render a page with known text as an image → OCR → text recovered, confidence populated,
  bbox normalized to `[0, 1]`.
- **Acceptance test for the slice:** a mixed page with native text *and* an image containing
  text. After merge — native blocks survive, OCR blocks over native text are evicted, OCR
  blocks over the image survive.

**4. Runner / e2e.** All three capabilities → `ParsedDocument`. An OCR failure on one page →
`warnings` + `failed_pages`, run still completes.

**Frontend.** Config emission shape; OCR panel round-trip; precedence control.

## 8. Known limitations (accepted, deliberately)

These emerged from stress-testing the model. They are recorded so they are not rediscovered
as bugs.

| # | Limitation |
|---|---|
| L1 | **Capabilities are modelled as peers; in real IDP they are a DAG with layout upstream.** Spatial reconciliation is a cheap substitute for a layout stage. It works because fitz/camelot/tesseract are all page-global. The staging-capability distinction (§2) keeps layout able to slot in above the merger later without a rewrite. |
| L2 | **Cross-block reading order is `(y0, x0)` and breaks on multi-column pages.** Pre-existing; OCR does not worsen it because no producer emits lines. `layout_analysis` fixes it. |
| L3 | **`auto` is page-level; text-in-image is region-level.** A small logo on a dense page triggers OCR of the whole page, and most of the output is discarded by reconciliation. Correct output, wasted compute — the price of having no layout stage. |
| L4 | **No ensembling.** One tool per capability, by design (§2). |
| L5 | **Parsing produces a flat block list, not a document tree.** As capabilities grow, "merge" will increasingly mean "assemble structure" (sections, captions bound to figures, table cells) rather than "dedupe overlapping boxes". The merger's job will grow. |
| L6 | **Heuristics cannot detect a bad-but-valid text layer.** Mitigated by `precedence.text_ocr: "prefer"`, decided by the router. |

## 9. Parked / future

- **Execution location (GPU, neocloud, local acceleration).** Deliberately parked. Slice 1
  ships tesseract in-process with **no `execution` config field**. The question — remote
  services, GPU boxes, local GPU acceleration — deserves its own brainstorm and will be
  taken up when PaddleOCR and layout analysis are implemented, since those are the workloads
  that motivate it. Note: an earlier `RemoteEngine(engine="paddleocr")` sketch was rejected
  because it made engine identity a class locally and a string remotely — asymmetric, and a
  violation of C1's orthogonality. The right factoring separates *recognizer* from
  *transport*; settle it with real requirements in hand.
- **`layout_analysis` — the immediate next slice.** It is where parser differentiation
  actually lives (reading order, region classification, routing). It brings
  **docling-as-a-pipeline-tool** with it naturally, since docling *is* a layout model — a far
  better reason to do that work than "make multi-capability real". Landing it also fixes L2
  and mitigates L3.
- **Additional engines** (`paddleocr`, `easyocr`) — both are heavy (paddlepaddle: hundreds of
  MB; easyocr: torch, GB+). Their natural home is behind the parked execution axis, not in
  the API image.
- **Table structure comparison** — after layout.
- The probe's `edge_density` could be upgraded from numpy-Sobel to OpenCV Canny at **zero
  dependency cost** (`cv2` is already in the image via docling).
