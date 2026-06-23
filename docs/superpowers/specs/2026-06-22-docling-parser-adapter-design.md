# Docling Parser Adapter — Design

> **Status**: Approved. Implementation plan to follow.
> **Date**: 2026-06-22
> **References**: [`docs/planning/cdm_architecture.md`](../../planning/cdm_architecture.md), [`docs/superpowers/specs/2026-04-27-landing-ai-cdm-adapter-design.md`](2026-04-27-landing-ai-cdm-adapter-design.md)

---

## 1. Goals

1. Implement a `DoclingAdapter` that maps `DoclingDocument` output to `ParsedDocument` (CDM).
2. Implement `run_docling` runner with a global semaphore (cap: 1 concurrent job) and `asyncio.to_thread` offload.
3. Split large PDFs into page batches before passing to docling, then reconstruct a single CDM document.
4. Register docling in the `_RUNNERS` dispatch table so `ParsingService` can route to it via `config["parser"] = "docling"`.
5. MVP scope: PDF only. Non-PDF conversion to PDF is a follow-up.

---

## 2. Files Changed / Created

| File | Action |
|---|---|
| `backend/app/cdm/adapters/docling.py` | **create** — `DoclingAdapter` |
| `backend/app/services/parsing/docling_runner.py` | **create** — `run_docling`, `_split_pdf`, `_merge_fragments`, `_DOCLING_SEMAPHORE` |
| `backend/tests/cdm/test_docling_adapter.py` | **create** — structural invariant tests |
| `backend/tests/services/parsing/test_docling_runner.py` | **create** — split + merge unit tests |
| `backend/app/cdm/models.py` | **modify** — add `ParserKind.DOCLING = "docling"` |
| `backend/app/services/parsing/errors.py` | **modify** — add `DoclingRunError` |
| `backend/app/services/parsing/parsing_service.py` | **modify** — register `ParserKind.DOCLING: run_docling` in `_RUNNERS` |
| `backend/pyproject.toml` | **modify** — add `docling` dependency |

---

## 3. Adapter Design (`docling.py`)

Stateless class, follows the `ParserAdapter` protocol. Input is a `DoclingDocument` object (passed directly — not a dict, since docling is an in-process library). Also receives a `page_offset: int` from the runner to adjust page indexes when processing a page batch.

### 3.1 DocItemLabel → BlockRole

| Docling label | CDM `BlockRole` | Notes |
|---|---|---|
| `TITLE` | `TITLE` | |
| `SECTION_HEADER` | `HEADING` | `depth` from `iterate_items` level |
| `TEXT`, `PARAGRAPH` | `PARAGRAPH` | |
| `LIST_ITEM` | `LIST` | |
| `TABLE` | `TABLE` | builds `Table` with `Cell` list |
| `PICTURE` | `FIGURE` | |
| `CAPTION` | `CAPTION` | |
| `CODE` | `CODE` | |
| `FORMULA` | `FORMULA` | |
| `PAGE_HEADER` | `HEADER` | |
| `PAGE_FOOTER` | `FOOTER` | |
| `FOOTNOTE`, `CHECKBOX_SELECTED`, `CHECKBOX_UNSELECTED`, `FORM`, `KEY_VALUE_REGION`, `DOCUMENT_INDEX` | `OTHER` | `native_type` preserves original label |

### 3.2 BBox Conversion

Docling PDFs use bottom-left origin (PDF standard). Convert to CDM normalized top-left:

```
x0 = l / page_width
x1 = r / page_width
y0 = 1 - t / page_height    # t is distance from bottom to top edge
y1 = 1 - b / page_height    # b is distance from bottom to bottom edge
```

Page dimensions come from `doc.pages[page_no].size.width` / `.height` (in PDF points).
`BBox.source_space = "pdf_points"`, `source_coords = (l, t, r, b)` preserved for lossless round-trips.

If docling reports `CoordOrigin.TOPLEFT` for a given provenance item, use `y0 = t / page_height`, `y1 = b / page_height` instead (no flip required).

### 3.3 Page Indexing

Docling is 1-indexed (`prov.page_no`). Convert to 0-indexed CDM and apply batch offset:

```python
page_index = (prov.page_no - 1) + page_offset
```

### 3.4 Block IDs

Minted deterministically as `{source_document_id}:p{page_index}:b{reading_order}` — same scheme as LlamaParse and LandingAI adapters. `reading_order` is the item's position in `iterate_items()` output for this batch.

### 3.5 Heading Depth

`DoclingDocument.iterate_items()` yields `(item, level)` where `level` is the nesting depth in the document tree. Stored on `Block.depth` for `SECTION_HEADER` items.

### 3.6 Table Mapping

`TableItem.data.grid` is a 2D `List[List[TableCell]]`. Deduplicate by `(start_row_offset, start_col_offset)` to handle merged cells, then emit a flat `List[Cell]`:

```python
Cell(
    row=cell.start_row_offset,
    col=cell.start_col_offset,
    rowspan=cell.row_span,
    colspan=cell.col_span,
    text=cell.text,
    is_header=cell.column_header,
)
```

`Table.html = item.export_to_html()`, `Table.markdown = item.export_to_markdown()`.

### 3.7 Document-Level Fields

- `full_markdown`: `doc.export_to_markdown()` — docling produces this natively.
- `full_text`: joined from all `block.text` values in reading order, separated by `\n\n`.

### 3.8 Adapter Signature

```python
class DoclingAdapter:
    parser: ClassVar[ParserKind] = ParserKind.DOCLING

    def adapt(
        self,
        raw: DoclingDocument,
        source_meta: SourceMeta,
        *,
        page_offset: int = 0,
    ) -> ParsedDocument: ...
```

---

## 4. Runner Design (`docling_runner.py`)

### 4.1 Concurrency

```python
_DOCLING_SEMAPHORE = asyncio.Semaphore(1)
```

Module-level semaphore, created once on import. Caps concurrent docling jobs to 1 globally. A second parse request waits at `async with _DOCLING_SEMAPHORE:` — it does not fail. The event loop remains responsive during the wait because `asyncio.to_thread` runs docling on a background thread.

Batches within a single parse are processed sequentially through the semaphore — no interleaving between concurrent requests mid-batch.

### 4.2 PDF Splitting (`_split_pdf`)

```python
def _split_pdf(file_path: str, batch_size: int) -> list[Path]:
    """Split a PDF into page batches. Returns paths to temp files."""
```

Uses `pypdf` to write each page range to a `tempfile.NamedTemporaryFile`. Returns a list of temp file paths. The caller is responsible for cleanup. `batch_size` defaults to `config.get("page_batch_size", 20)`.

Single-page and sub-batch-size PDFs produce one batch (no split).

### 4.3 Fragment Merge (`_merge_fragments`)

```python
def _merge_fragments(fragments: list[ParsedDocument]) -> ParsedDocument:
    """Merge CDM fragments from page batches into one ParsedDocument."""
```

Merges by:
- Concatenating `pages` lists (page indexes already correct via `page_offset`)
- Concatenating `blocks` lists (block IDs already globally unique via page_index)
- Joining `full_text` fragments with `\n\n`
- Joining `full_markdown` fragments with `\n\n`
- `page_count = sum(f.page_count for f in fragments)`

### 4.4 Runner Flow

```python
async def run_docling(
    *,
    source: SourceDocument,
    file_path: str,
    representation_kind: str,
    config: Dict[str, Any],
    client: Any,           # unused — docling is in-process; None at call site
    parse_run_id: Optional[str] = None,
) -> Tuple[ParseRun, ParsedDocument]:
```

1. Split `file_path` into batch temp files via `_split_pdf`.
2. For each batch: acquire `_DOCLING_SEMAPHORE`, run `await asyncio.to_thread(_convert, batch_path, config)`, release semaphore. Clean up temp file in `finally`.
3. Adapt each `ConversionResult.document` via `DoclingAdapter().adapt(doc, source_meta, page_offset=i * batch_size)`.
4. Merge fragments via `_merge_fragments`.
5. Return `(ParseRun(status=SUCCEEDED, duration_ms=total_ms, ...), merged_doc)`.

On any exception: build `ParseRun(status=FAILED)`, raise `DoclingRunError(run=failed_run)`. Temp files cleaned up before raising.

### 4.5 `_convert` (sync, runs in thread)

```python
def _convert(file_path: Path, config: dict) -> ConversionResult:
    converter = DocumentConverter()
    return converter.convert(str(file_path))
```

Kept minimal and synchronous — this is the function handed to `asyncio.to_thread`. `DocumentConverter` is instantiated per call (stateless, no shared state across threads).

---

## 5. Error Hierarchy Addition

```python
# errors.py
class DoclingRunError(ParseRunError):
    """Raised by docling_runner when conversion fails on any batch."""
```

`ParsingService` already catches `ParseRunError` (base class) — no change needed there.

---

## 6. Registration

```python
# parsing_service.py
from app.services.parsing.docling_runner import run_docling

_RUNNERS: Dict[ParserKind, Callable] = {
    ParserKind.LLAMAPARSE: run_llamaparse,
    ParserKind.LANDING_AI: run_landingai,
    ParserKind.SIMPLE:     run_simple,
    ParserKind.DOCLING:    run_docling,          # new
}
```

`self._clients[ParserKind.DOCLING]` will be `None` — docling needs no external client. `ParsingService.__init__` already handles missing client keys gracefully (passes `None` to runner).

---

## 7. `supported_file_types`

MVP: PDF only.

```python
def supported_file_types(self) -> list[str]:
    return ["application/pdf"]
```

Future: non-PDF formats (DOCX, PPTX, XLSX, HTML, images) via a pre-conversion step that produces a PDF, then hands off to the same pipeline.

---

## 8. Testing

### 8.1 Adapter Tests (`tests/cdm/test_docling_adapter.py`)

Run offline against a fixture `DoclingDocument` serialized from a small real PDF. Assert structural invariants:

- `page_count == len(pages)`
- Every `block.page_index` in `[0, page_count)`
- Every `bbox` satisfies `0 ≤ x0 ≤ x1 ≤ 1` and `0 ≤ y0 ≤ y1 ≤ 1`
- Every `TABLE` block has a non-None `block.table`
- Every `Page.block_ids` references existing block IDs
- `full_markdown` is non-empty
- Round-trip: `ParsedDocument.model_validate_json(doc.model_dump_json()) == doc`
- `page_offset` shifts all `block.page_index` values correctly

### 8.2 Runner Tests (`tests/services/parsing/test_docling_runner.py`)

Unit tests, no real docling calls (conversion mocked):

- `_split_pdf`: correct batch count for various page counts and batch sizes; temp files deleted after processing
- `_merge_fragments`: correct total `page_count`, block count, `full_text` concatenation, page index continuity across fragments
- `run_docling`: `DoclingRunError` raised and `ParseRun(status=FAILED)` returned on conversion error

---

## 9. Open Questions / Deferred

1. **Non-PDF support.** Convert DOCX/PPTX/images → PDF before splitting. Candidates: `pypdf`, `libreoffice` headless, `python-docx2pdf`. Out of scope for MVP.
2. **Optimal batch size.** Default of 20 pages is a starting point. Profile on real hardware and tune `page_batch_size` config default.
3. **Semaphore count.** Currently 1. If hardware has sufficient memory, raise to 2. Make it an env-var-configurable setting rather than a hardcoded constant.
4. **Docling model configuration.** `DocumentConverter` accepts pipeline options (OCR backend, layout model). Expose via `config["docling_pipeline_options"]` in a follow-up.
5. **Figure extraction.** `PictureItem` carries image data in some docling configurations. Asset storage and `Block.image_ref` population deferred.
