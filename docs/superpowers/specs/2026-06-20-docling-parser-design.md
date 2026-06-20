# Docling Parser Integration — Design Spec

**Date:** 2026-06-20
**Status:** Approved

---

## Problem

The parser supports LlamaParse, LandingAI, and a simple local extractor. All three are either cloud-based or produce low-fidelity output. Docling is a local Python library that produces high-fidelity structured output (typed blocks, native cell grids for tables, bounding boxes, page dimensions) without any API cost or network dependency. Adding it gives users a capable offline alternative.

---

## Approach

Option A: serialize docling output to a dict first (`export_to_dict()`), then pass to a `DoclingAdapter` that maps the dict to `ParsedDocument` (CDM). This is consistent with all existing adapters (`raw: dict → ParsedDocument`). The same dict is stored as `raw_payload`.

---

## Architecture & Data Flow

```
docling_runner.py
  └── asyncio.to_thread(_run_docling_sync)     # blocking — runs in thread pool
        └── DocumentConverter().convert(path)  # created per run
              └── ConversionResult.document    # DoclingDocument
  └── result.document.export_to_dict()         # → raw dict (raw_payload)
  └── inject raw["full_text"], raw["full_markdown"] from docling exporters
  └── DoclingAdapter().adapt(raw, source_meta) # dict → CDM ParsedDocument

parsing_service.py
  └── _RUNNERS[ParserKind.DOCLING] = run_docling
  └── clients.get(DOCLING) → None (no external client)
```

- `DocumentConverter` is created inside `_run_docling_sync` per run — no startup wiring, no shared state.
- `asyncio.to_thread` wraps the blocking call so the FastAPI event loop stays free.
- `raw["full_text"]` and `raw["full_markdown"]` are runner-injected keys (not in `export_to_dict()` natively) so the adapter can access them without calling live docling methods.

---

## DoclingAdapter (`cdm/adapters/docling.py`)

### Role Mapping

| Docling label | CDM BlockRole |
|---|---|
| `title` | TITLE |
| `section_header` | HEADING |
| `paragraph`, `text` | PARAGRAPH |
| `list_item`, `list` | LIST |
| `table` | TABLE |
| `picture` | FIGURE |
| `caption` | CAPTION |
| `footnote` | MARGINALIA |
| `page_header` | HEADER |
| `page_footer` | FOOTER |
| `code` | CODE |
| `formula` | FORMULA |
| `key_value_region`, `form_item` | OTHER |

### Ref Resolution

Docling's body tree uses JSON pointer refs (`{"$ref": "#/texts/5"}`). The adapter builds a lookup dict upfront by flattening all item arrays (`texts`, `tables`, `pictures`, `key_value_items`, `form_items`) keyed by `self_ref`. Resolving a ref is an O(1) dict lookup.

### Body Traversal

Walk `body.children` recursively. A child is either:
- A leaf ref → resolved to an item, converted to a `Block`
- A group node with `children` → recurse, incrementing depth

This yields correct reading order and heading depth. Furniture items (page headers/footers) live in a separate `furniture` tree and are walked the same way, appended after body blocks.

### BBox Conversion

Docling bboxes carry a `coord_origin` flag (`BOTTOMLEFT` or `TOPLEFT`). When `BOTTOMLEFT` (PDF native), flip `y` before normalizing:

```
y0 = (page_height - b) / page_height
y1 = (page_height - t) / page_height
x0 = l / page_width
x1 = r / page_width
```

All values are clamped to `[0.0, 1.0]`. `source_space = "pdf_points"`, `source_coords = (l, t, r, b)`.

### Table Handling

Docling provides a native cell grid (`table_cells`) with `row_span`, `col_span`, `start_row_offset_idx`, `start_col_offset_idx`, `text`, `column_header`. Maps directly to CDM `Cell` — no reconstruction needed. Per-cell bboxes are also populated. `Table.markdown` is left `None`; the document-level `full_markdown` covers table content.

### Page Dimensions

`raw["pages"]` is a dict keyed by string page number (`"1"`, `"2"`, …). Each entry has `size.width` and `size.height` in points. Used for bbox normalization and for `Page.width`, `Page.height`, `Page.unit = "points"`.

---

## Runner (`services/parsing/docling_runner.py`)

### Converter Creation

```python
# ocr=False (default)
converter = DocumentConverter()

# ocr=True — applies EasyOCR to PDF pages; image formats (PNG/JPG/TIFF)
# are routed through docling's image pipeline which always uses OCR.
pipeline_options = PdfPipelineOptions(do_ocr=True, ocr_options=EasyOcrOptions())
converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
)
```

### Config Options

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `ocr` | bool | `false` | Enable EasyOCR for scanned/image pages |

### Run Metadata

Docling is local — no token counts or provider job IDs. `ParseRun` will have `input_tokens=None`, `output_tokens=None`, `provider_refs={}`. `duration_ms` tracked via `perf_counter`.

### Error Handling

Any exception from `_run_docling_sync` is caught, a failed `ParseRun` is built, and `DoclingRunError` (new subclass of `ParseRunError`) is raised — identical pattern to `LlamaParseRunError`.

---

## Cross-cutting Changes

### Files Created

- `backend/app/cdm/adapters/docling.py` — DoclingAdapter
- `backend/app/services/parsing/docling_runner.py` — run_docling + _run_docling_sync

### Files Modified

| File | Change |
|------|--------|
| `backend/app/cdm/models.py` | Add `DOCLING = "docling"` to `ParserKind` |
| `backend/app/services/parsing/errors.py` | Add `class DoclingRunError(ParseRunError): ...` |
| `backend/app/services/parsing/parsing_service.py` | Register `ParserKind.DOCLING: run_docling` in `_RUNNERS` |
| `backend/pyproject.toml` | Add `docling` dependency via `uv add docling` |

### No Migration Required

`parser` is stored as a plain string in `parse_runs`. Adding `"docling"` to the Python enum requires no schema change.

### Out of Scope

Frontend parser config selector update (adding docling as a selectable parser with an `ocr` toggle) is a follow-on task.
