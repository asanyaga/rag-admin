# Docling as a First-Class Parser Kind

**Status:** Design — pending review
**Date:** 2026-07-18
**Supersedes (in part):** [Layout analysis capability](2026-07-11-layout-analysis-capability-design.md) §2 D1, §4 "Retire standalone docling", §6
**Related:** [Custom pipeline overview](2026-06-30-custom-pipeline-design.md) ·
[Docling parser adapter](2026-06-22-docling-parser-adapter-design.md) ·
[Backend parse architecture review](../../architecture/2026-07-11-parse-architecture-review-backend.md)

---

## 1. Why this reverses D1

The 2026-07-11 design retired `ParserKind.DOCLING` (decision D1) and made docling reachable
only as a `layout_analysis` tool inside the custom pipeline. Two premises supported that, and
both are wrong.

**Premise 1 — "a shared config surface is what makes runs comparable."** It isn't.
Comparability lives in the CDM contract: `ParseRun` + `config_hash` + a uniform
`ParsedDocument`. The eval engine already forwards `variant["adapter"]` opaquely
(`engine.py:36`), and LlamaParse and Landing AI are already separate parser kinds that compare
against each other without sharing a config shape. Docling as its own kind is exactly
consistent with how the cloud tier is treated.

**Premise 2 — "`text_extraction` and `layout_analysis` are the same capability at different
tiers"** (that doc's §1). They are the same capability *in docling*, because
`StandardPdfPipeline` emits regions and their text from one conversion pass. Collapsing them
encoded docling's internal coupling into the capability enum before `DoclingTool` was even
written. Region detection and text acquisition fail independently — a layout model can find a
perfect table region while OCR returns garbage inside it — and a capability model that cannot
express that is describing docling, not IDP.

**The consequence in code.** `DoclingTool` declares `provides = {LAYOUT_ANALYSIS}`
(`tools/docling_tool.py:68`) but calls bare `DocumentConverter()` (`:63`), which runs with
`do_ocr=True` and `do_table_structure=True`. It occupies three slots while claiming one, and
`build_pipeline_config` will happily compose it with camelot and tesseract — running two table
engines and two OCR engines whose outputs then fight in the bbox merger. The tool also exposes
exactly one knob, `page_batch_size`, which is not a docling option at all but our own memory
workaround. Docling-as-a-tool can therefore answer no question finer than "docling defaults vs
fitz."

**The split this design makes.**

| | Owns |
|---|---|
| `ParserKind.DOCLING` | Docling on its own terms — every pipeline, backend, and option it exposes. The opinionated baseline rung, and the only path for non-PDF formats. |
| `ParserKind.CUSTOM_PIPELINE` | Vendor-neutral composition over *models and engines*, PDF/image only. Where IDP invariants are exposed and mixed. |

Docling's **models** remain fair game for the custom pipeline —
`docling-ibm-models` (3.13.3, already in the lockfile) ships the Egret/Heron layout predictors
and TableFormer as directly importable predictors. The thing being removed from the custom
pipeline is `DocumentConverter`, not docling's models.

## 2. What docling actually exposes (verified against the install)

Installed: `docling` 2.105.0, `docling-core` 2.83.1, `docling-ibm-models` 3.13.3,
`docling-parse` 6.2.0.

**Pipelines** (`docling/pipeline/`): `standard_pdf_pipeline`, `threaded_standard_pdf_pipeline`,
`vlm_pipeline`, `simple_pipeline`, `asr_pipeline`.

**Backends** (`docling/backend/`) split into two worlds:

- **Paginated** — `docling_parse_v4`, `docling_parse_v2`, `pypdfium2`, `managed_pdfium`,
  `image_backend`. These feed the ML pipelines.
- **Declarative** — `msword`, `msexcel`, `mspowerpoint`, `html`, `md`, `csv`, `epub`, `latex`,
  `asciidoc`, `email`, `webvtt`, `xml/*`, `json/*`, `mets_gbs`. These feed `simple_pipeline`
  and construct `DoclingDocument` directly from the format's own structure, **with no models
  at all**.

**`PdfPipelineOptions` fields:** `do_ocr`, `do_table_structure`, `do_code_enrichment`,
`do_formula_enrichment`, `force_backend_text`, `ocr_options`, `table_structure_options`,
`layout_options`, `code_formula_options`, `images_scale`, `generate_page_images`,
`generate_picture_images`, `generate_parsed_pages`, plus `ocr_batch_size` /
`layout_batch_size` / `table_batch_size`.

**OCR engines** (`kind` discriminator): `easyocr`, `tesseract` (CLI), `tesserocr`, `rapidocr`,
`ocrmac`, `nemotron-ocr`, `kserve_v2_ocr`, `auto`. All share `lang`, `force_full_page_ocr`,
`bitmap_area_threshold`.

**Table structure:** `TableStructureOptions` (TableFormer — `mode` ∈ {FAST, ACCURATE},
`do_cell_matching`), plus `TableStructureV2Options` and `GraniteVisionTableStructureOptions`.

**Layout models** (`layout_model_specs.py`): `docling_layout_v2`, `docling_layout_heron`,
`docling_layout_heron_101`, `docling_layout_egret_medium`, `..._large`, `..._xlarge`.

**Provenance is format-dependent — this is the load-bearing finding:**

| Backend | Provenance emitted |
|---|---|
| `msword_backend.py` | **None.** Zero `ProvenanceItem`, zero `BoundingBox`. DOCX blocks carry no geometry and docling doesn't pretend otherwise. |
| `mspowerpoint_backend.py` | Real bboxes from shape EMU coordinates, `CoordOrigin.BOTTOMLEFT`. |
| `msexcel_backend.py` | `ProvenanceItem(page_no=<sheet>, bbox=(origin_col, origin_row, origin_col+num_cols, origin_row+num_rows))` — **the bbox field holds cell indices, not points.** |

`msexcel_backend` also does genuine region discovery: `_find_data_tables` runs a BFS flood-fill
over connected non-empty cells with gap tolerance, explicitly handling L-shapes and staggered
columns, so one sheet yields multiple logical tables.

**The XLSX bbox is a type pun and must not be copied into the CDM.** Our
`_to_cdm_bbox(raw_bbox, w, h)` (`adapters/docling.py`) normalizes against page dimensions;
applied to cell indices it produces meaningless fractions that then silently corrupt anything
assuming renderable space — overlap thresholds, IoU-based eval alignment, viewer highlighting.
This is why multi-format is sliced separately (§5).

## 3. Decisions

- **D1 is reversed.** `ParserKind.DOCLING` returns, with a runner and a real adapter.
- **`DoclingTool` is deleted** from the custom-pipeline tool registry, along with
  `DoclingConfig` and the docling branch of `CustomPipelineConfig.tsx`.
- **The docling config model mirrors docling's own shape**, not our capability slots — a
  discriminated union over pipeline choice, with nested `ocr_options` / `table_structure_options`
  / `layout_options`. We do not invent an abstraction over docling; the point of this parser
  kind is to see docling as docling.
- **Slice 1 is PDF + image only.** It needs no CDM change and unblocks exploration immediately.
- **Slice 2 adds non-PDF formats**, and owns the CDM anchor generalization that XLSX and DOCX
  force (§5). It is sequenced after, not merged in.
- **The custom pipeline is PDF/image-only by design.** Docling's declarative backends already
  cover the format long tail; reimplementing them buys no experimental value, because formats
  with native structure have exactly one sensible occupant per slot.
- **VLM pipeline is in scope for slice 1** as a pipeline choice (`vlm_pipeline` over rendered
  pages works on PDF/image), but with a stub-level config — model spec selection only.
- **ASR pipeline is out of scope** entirely.

## 4. Slice 1 — docling parser kind, PDF + image

### 4.1 Config model (`app/services/parsing/docling_config.py`)

A Pydantic model, validated at the API boundary (this also closes review §1.4 for docling):

```
DoclingConfig
  pipeline: "standard" | "vlm"          # discriminator
  backend:  "docling_parse_v4" | "docling_parse_v2" | "pypdfium2"

  # pipeline == "standard"
  do_ocr, do_table_structure, do_code_enrichment, do_formula_enrichment: bool
  force_backend_text: bool
  images_scale: float
  generate_page_images, generate_picture_images: bool
  layout_options:          { model: <one of the six layout specs> }
  ocr_options:             discriminated on `kind`
                           easyocr | tesseract | tesserocr | rapidocr | auto
                           + shared lang / force_full_page_ocr / bitmap_area_threshold
                           + engine-specific fields
  table_structure_options: { mode: FAST|ACCURATE, do_cell_matching: bool }

  # pipeline == "vlm"
  vlm_model: <model spec name>

  # ours, not docling's
  page_batch_size: int = 20
```

Engines requiring platform support we don't have (`ocrmac`, `kserve_v2_ocr`, `nemotron-ocr`)
are excluded from the union rather than exposed and failing at runtime.

`ocr_options` and `table_structure_options` are only meaningful when the corresponding `do_*`
flag is true; the model validates that rather than silently ignoring them.

### 4.2 Runner (`app/services/parsing/docling_runner.py`)

Matches the existing runner signature exactly (`source, file_path, representation_kind,
config, client, parse_run_id`) and registers in `_RUNNERS` (`parsing_service.py:33`).

- Build `DocumentConverter` from `DoclingConfig`, **cached per options-hash** at module level
  (review §2.5 — the old runner rebuilt it per batch and `DoclingTool` still does).
- Preserve page-range batching (`page_batch_size`) with `page_offset`, and the memory
  serialization lock — carried over from `DoclingTool`, still fixed, still revisited with the
  job queue.
- **Offload conversion via `asyncio.to_thread`** so a parse never runs on the event loop
  (review §2.1).
- Per-page failure degrades to `warnings` + `failed_pages`; the run completes. A missing or
  broken docling install surfaces as a clear error, not a mid-parse crash.
- Failed runs build a `ParseRun(status=FAILED)` and raise `DoclingRunError` — same shape as
  the other four runners.

### 4.3 Adapter (`app/cdm/adapters/docling.py`)

The file already holds `_map_role`, `_map_table`, `_to_cdm_bbox` as shared helpers. It regains
a real `DoclingAdapter(ParserAdapter)` with `parser = ParserKind.DOCLING`, doing the
`DoclingDocument → ParsedDocument` assembly that `DoclingTool` had stripped out: final id
minting, `reading_order` from `iterate_items()` order, `full_text` / `full_markdown`, and
page metadata.

### 4.4 Removals

- `tools/docling_tool.py`, its registry entry (`custom_pipeline/config.py:77`), and
  `test_docling_tool.py`.
- `DOCLING_DEFAULTS` and the docling `SelectItem` + batch-size panel in
  `CustomPipelineConfig.tsx` (`:46`, `:543`, `:554`, `:584`).

### 4.5 Frontend

- `ParseMethodSelector.tsx` — docling returns as a top-level parse method with a config panel
  built from §4.1. Progressive disclosure: pipeline + backend + the `do_*` toggles up front;
  OCR engine, layout model, and TableFormer options behind a collapsible "advanced" section
  that only renders the sub-panel for the enabled stage.
- `ParserEvalCasePage.tsx:17` — `DEFAULT_ADAPTER = 'docling'` becomes correct again; no change
  needed, but its test should assert the variant round-trips.
- `ParserComparisonTable.tsx:38-40` — `RETIRED_ADAPTER_LABELS` is no longer a retirement shim;
  fold `docling` back into the live label map.
- `ParseConfigFamilySelector.tsx:19` — already maps `docling → 'Docling'`; unchanged.

### 4.6 Accepted consequence

Removing `DoclingTool` leaves the custom pipeline's `layout_analysis` slot with only `fitz`
until the region-rooted rework lands. That is a real temporary regression in what the custom
pipeline can express, and it is accepted deliberately: the composed configs it removes
(docling + camelot, docling + tesseract) were the incoherent ones — two table engines or two
OCR engines reconciled by bbox eviction. Nothing that produced trustworthy output is lost.

## 5. Slice 2 — non-PDF formats (scoped here, specified separately)

Enabling docling's declarative backends is not a config change; it forces a CDM change,
because `Block.bbox` stops being the universal anchor.

**The generalization:** replace `bbox` with a tagged `anchor` union —

| Anchor | Formats |
|---|---|
| `PageBox(page, x0, y0, x1, y1)` | PDF, images, PPTX |
| `CellRange(sheet, r0, c0, r1, c1)` | XLSX, CSV |
| `ElementPath(path)` | DOCX, HTML, MD, EPUB |
| `CharSpan(offset, length)` | plain text; secondary anchor everywhere |

Overlap, containment, and eval alignment become operations defined per anchor type — IoU for
`PageBox`, range intersection for `CellRange`, prefix containment for `ElementPath`. The
concept survives; the implementation varies by type. This is what prevents the XLSX type pun
(§2) from propagating into our data.

Also required: `ALLOWED_MIME_TYPES` (`config.py:45`) currently permits only
`application/pdf`, `image/jpeg`, `image/png`, so uploads of DOCX/XLSX/PPTX are rejected before
parsing is ever reached.

Slice 2 gets its own design doc once slice 1 is merged and the anchor shape has been pressure-
tested against real docling output for each format.

## 6. Testing

**Slice 1**

- **Config model:** valid configs round-trip; unknown OCR `kind` rejected; `ocr_options` with
  `do_ocr=False` rejected; the API boundary returns 422 rather than failing inside the
  background task.
- **Adapter (no docling binary):** captured `DoclingDocument` fixture → `ParsedDocument` with
  correct roles, normalized bboxes, `reading_order`, page metadata. Retarget the existing
  `test_docling_adapter.py`.
- **Converter caching:** two runs with identical options reuse one `DocumentConverter`;
  differing options build two.
- **Threading:** conversion is offloaded (not on the event loop); concurrent runs serialize.
- **Integration (`skipif` no docling):** a two-column fixture parses in correct cross-column
  reading order; `TableFormerMode.FAST` vs `ACCURATE` produce different `config_hash` and both
  succeed; `force_full_page_ocr=True` on a CID-corrupt fixture recovers text; one-page failure
  → `warnings` + `failed_pages`, run completes.
- **Custom pipeline equivalence:** with `DoclingTool` removed, every remaining custom-pipeline
  config produces byte-identical `ParsedDocument`s to before.
- **Frontend:** docling config panel round-trips through `ParseMethodSelector`; the docling
  option is gone from `CustomPipelineConfig`.

## 7. Known limitations

| # | Item |
|---|------|
| 1 | Non-PDF formats deferred to slice 2 (blocked on the anchor union). |
| 2 | VLM pipeline exposed at model-spec granularity only; prompt/generation options deferred. |
| 3 | ASR pipeline out of scope. |
| 4 | Custom pipeline loses its tier-1 layout option until the region-rooted rework (§4.6). |
| 5 | `page_batch_size` serialization stays fixed rather than adaptive; revisited with the job queue (review §4.1). |
| 6 | Docling's own `threaded_standard_pdf_pipeline` is not used — our batching + lock predates it and interacts with the same memory constraint. Worth revisiting once the job queue owns concurrency. |

## 8. Sequencing

1. **Slice 1** — this doc. One GitHub issue + PR.
2. **Slice 2** — non-PDF formats + CDM anchor union. Own design doc, own issue.
3. **Custom pipeline region-rooted rework** — independent of both; supersedes the remainder of
   the 2026-07-11 capability model.

Per the pre-implementation gate, a GitHub issue with acceptance criteria derived from §4 is
created and confirmed before implementation begins.
