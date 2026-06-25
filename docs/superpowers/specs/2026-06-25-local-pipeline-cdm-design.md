# Local-First PDF Parse Pipeline — Design Spec

> **Status:** Draft for review
> **Date:** 2026-06-25
> **Scope:** DocumentProbe (iteration 1) + local parse pipeline architecture (iterations 1–3)
> **References:** [`docs/specs/cdm_v1.md`](../../specs/cdm_v1.md), [`docs/planning/cdm_architecture.md`](../../planning/cdm_architecture.md)

---

## 1. Goals

Design a local-first PDF parsing pipeline that:

1. Produces a clean `ParsedDocument` (CDM) from local tools — no cloud API required.
2. Is a **prototyping and eval tool** for building intuition about which tool configurations work with which document types.
3. Uses a `DocumentProbe` (classifier) that runs independently, producing a per-page document profile to guide tool selection.
4. Supports composable, config-driven tool selection — the user picks the right tools for the job based on the probe output.
5. Retains full traceability from raw tool output to each CDM block, stored in `ParseRun.raw_output`.
6. Builds progressively — iteration 1 is fitz + camelot; later iterations add PaddleOCR, docling, and others.

Non-goals: automatic merge conflict resolution, multi-user workflows, production-grade eval framework, cloud parser replacement.

---

## 2. Design Principles

**Probe is decoupled.** The `DocumentProbe` is an independent invocation. It produces a `DocumentProfile` — a diagnostic artifact. The user reads it and decides how to configure the pipeline. The runner never requires a profile to operate.

**ParsedDocument stays clean.** The CDM is the content artifact. Run concerns (which tool produced which block, what was evicted, raw native output) live entirely in `ParseRun.raw_output`. The `ParsedDocument` carries no tool attribution or conflict annotations.

**Full audit trail in ParseRun.** `ParseRun.raw_output` links every CDM block back to the exact native record that produced it, and records every evicted block with the reason. Nothing is silently discarded.

**Tool order = priority.** When two tools produce blocks for the same spatial region, the later-declared tool wins. Evicted blocks are logged, not deleted.

**Delete and retry over clever conflict resolution.** For iteration 1, if a parse result is unsatisfactory, the user deletes the `ParseRun` and reconfigures. HITL conflict resolution via UI is a later iteration.

---

## 3. Document Fidelity Tiers and Tool Progression

```
Tier 1 — Text + Tables (iteration 1)
  Tools:   fitz + camelot
  Output:  PARAGRAPH blocks with bboxes, TABLE blocks with cell-level bboxes
  Handles: text-native PDFs with ruled or borderless tables

Tier 2 — OCR (iteration 2)
  Tools:   fitz (rasterize) + PaddleOCR PP-OCRv4 [+ PP-StructureV3 for tables]
  Output:  PARAGRAPH blocks with bboxes + confidence scores, TABLE blocks from images
  Handles: CID-corrupt PDFs, scanned PDFs

Tier 3 — Semantic Structure (iteration 3)
  Tools:   + docling
  Output:  + heading detection, semantic hierarchy, richer markdown
  Handles: documents where section/heading structure matters for downstream extraction
```

The `DocumentProbe` maps document characteristics to the appropriate tier:

| Probe signal | Recommended tier |
|---|---|
| `has_text_layer: true`, `has_cid_corruption: false` | Tier 1 |
| `has_cid_corruption: true` OR `has_scanned_pages: true` | Tier 2 |
| Semantic structure needed for downstream extraction | Tier 3 |

---

## 4. DocumentProbe

### 4.1 Purpose

A standalone diagnostic tool. Inspects a PDF using fitz and produces a `DocumentProfile` with per-page signals. Stored as a document-level artifact (one per `SourceDocument`, reused across parse runs). Does not feed into the runner automatically — the user reads the profile and configures the pipeline.

### 4.2 Output types

```python
class PageProfile(BaseModel):
    index: int                    # 0-based
    char_count: int               # characters extracted by fitz
    has_text_layer: bool          # fitz found any text on this page
    image_count: int              # embedded raster images on this page
    font_health: Literal["clean", "cid_corrupt", "mixed", "unknown"]
    table_signal: bool            # heuristic: line density via page.get_drawings()
    page_type: Literal["text", "scanned", "mixed", "empty"]

class DocumentProfile(BaseModel):
    source_document_id: str
    filename: Optional[str]
    page_count: int
    pages: List[PageProfile]
    # document-level summaries (derived from pages)
    has_text_layer: bool          # any page has text
    has_scanned_pages: bool       # any page_type == "scanned"
    has_cid_corruption: bool      # any font_health == "cid_corrupt"
    table_signal: bool            # any page has table_signal
    recommended_tools: List[str]  # non-binding: e.g. ["fitz", "camelot"]
    duration_ms: int
    probed_at: datetime
```

### 4.3 Detection logic

**`font_health`:** fitz extracts text; if the ratio of Unicode private-use area codepoints (U+E000–U+F8FF) or CID surrogates exceeds a threshold (~20% of chars), the page is flagged `cid_corrupt`. Pages with mixed clean and corrupt sections are `mixed`.

**`table_signal`:** `page.get_drawings()` returns vector drawing commands. High line density with horizontal/vertical alignment patterns indicates a ruled table. This is a heuristic — camelot confirms or disproves at parse time.

**`page_type`:** derived from `has_text_layer` and `image_count`:
- `text` → has text layer, no dominant images
- `scanned` → no text layer, has images
- `mixed` → has both text layer and significant image content
- `empty` → neither text nor images

### 4.4 Storage

`DocumentProfile` is a document-level artifact — one per `SourceDocument`, not per `ParseRun`. Persistence implementation is deferred (see open question 1). For iteration 1, the probe returns the profile in-memory; the caller decides whether to store it. It is NOT written into `ParseRun` — the parse runner and the probe are independent invocations.

---

## 5. LocalTool Protocol

### 5.1 Contracts

```python
class PageMeta(BaseModel):
    index: int
    width: float       # PDF points
    height: float      # PDF points
    unit: str = "points"
    rotation: int = 0  # degrees

class ToolResult(BaseModel):
    tool_id: str
    blocks: List[Block]
    page_meta: Dict[int, PageMeta]   # keyed by 0-based page index
    raw: Any                          # native output (fitz dict, camelot TableList)
    warnings: List[str] = []
    duration_ms: int

class LocalTool(Protocol):
    tool_id: str
    def run(self, pdf_path: Path, pages: Optional[List[int]] = None) -> ToolResult: ...
```

Tools speak CDM at their boundary — each tool's `run()` method returns CDM `Block`s, not native objects. The native output is preserved in `ToolResult.raw` for the audit trail.

### 5.2 FitzTool

```python
class FitzConfig(BaseModel):
    min_chars_threshold: int = 10    # pages below → emit warning
    include_images: bool = True       # emit FIGURE blocks for image blocks
    span_detail: bool = False         # store full span list in parser_extras
```

**What it extracts:**
- `page.get_text("dict")` → blocks → lines → spans
- Text blocks → `Block(role=PARAGRAPH, text=..., bbox=BBox(normalized))`
- Image blocks → `Block(role=FIGURE, bbox=BBox(normalized))` when `include_images`
- `parser_extras["fitz_block_type"]` = 0 (text) or 1 (image)
- `parser_extras["spans"]` = span list if `span_detail` (includes font, size, flags)
- Page dimensions → `PageMeta` (authoritative source for normalization)

**Coordinate normalization:** fitz uses top-left origin, PDF points.
`x_norm = x / page.width`, `y_norm = y / page.height`. No axis flip needed.

**Warns** on pages below `min_chars_threshold` — signal for CID corruption or scanned content.

### 5.3 CamelotTool

```python
class CamelotConfig(BaseModel):
    flavor: Literal["lattice", "stream"] = "lattice"
    edge_tol: int = 50
    row_tol: int = 2
    copy_text: List[str] = []
```

**What it extracts:**
- `camelot.read_pdf(str(path), flavor=..., pages="1-end")`
- Each `Table` → `Block(role=TABLE, bbox=BBox(normalized), table=Table(cells=[...]))`
- Cell bboxes: camelot uses bottom-left origin → flip: `y_top = page_height_pts - y_camelot`
- `Table.html` = `camelot_table.df.to_html()`
- `parser_extras["camelot_accuracy"]` = `table.parsing_report["accuracy"]`
- `parser_extras["camelot_order"]` = `table.parsing_report["order"]`
- `parser_extras["camelot_flavor"]` = config.flavor

**Page height for y-flip:** taken from `page_meta` passed by the runner after FitzTool completes. CamelotTool accepts `page_meta` as a constructor argument from the runner.

**Fidelity by mode:**
- `lattice` — very high (uses actual PDF line vectors); use for ruled tables
- `stream` — moderate (whitespace heuristics); use for borderless tables

---

## 6. LocalParseRunner

### 6.1 Config

```python
class LocalPipelineConfig(BaseModel):
    tools: List[LocalTool]                              # ordered; later = higher priority
    eviction_overlap_threshold: float = 0.5             # fraction of fitz block area
```

### 6.2 Execution sequence

```
1. Run FitzTool  → fitz_result  (provides page_meta for all subsequent tools)
2. Run CamelotTool(page_meta=fitz_result.page_meta) → camelot_result

3. Eviction pass:
   For each camelot TABLE block B_table:
     For each fitz PARAGRAPH block B_fitz on the same page:
       overlap = intersection_area(B_table.bbox, B_fitz.bbox) / area(B_fitz.bbox)
       if overlap > eviction_overlap_threshold:
         mark B_fitz as evicted (reason="spatial_overlap", won_by=B_table.id)

4. Assign final block_ids:
   "{source_document_id}:{page_index}:{reading_order}"
   reading_order = position in the merged, non-evicted block list for that page

5. Build raw_output:
   {
     "tools": {
       "fitz":    { "raw": fitz_result.raw,    "block_map": {block_id → fitz record} },
       "camelot": { "raw": camelot_result.raw, "block_map": {block_id → camelot record} }
     },
     "evicted": [
       {
         "block_id": str,
         "tool": "fitz",
         "reason": "spatial_overlap",
         "won_by": str,              # camelot block_id
         "overlap_fraction": float,
         "raw_block": dict           # full native fitz block
       }
     ]
   }

6. Build ParsedDocument:
   pages  = assemble_pages(fitz_result.page_meta, final_blocks)
   blocks = final_blocks (non-evicted fitz + camelot, sorted by page then reading_order)
   full_text = "\n\n".join(b.text for b in blocks if b.text)

7. Build ParseRun(
     parser=ParserKind.LOCAL_PIPELINE,
     config=config.model_dump(),
     raw_output=raw_output,
     status=SUCCEEDED
   )

8. Return (ParseRun, ParsedDocument)
```

### 6.3 Relation to existing patterns

`LocalParseRunner` mirrors `llamaparse_runner.py`:
- Same `SourceMeta` input
- Same `(ParseRun, ParsedDocument)` return contract
- Same `ParserKind` enum extended with `LOCAL_PIPELINE = "local_pipeline"`

It does **not** implement the `ParserAdapter` protocol (which is for adapting pre-existing raw output). The runner orchestrates its own tool invocations. A thin `LocalPipelineAdapter(ParserAdapter)` wrapper can be added later for uniform treatment if needed.

---

## 7. CDM Changes

Minimal. The existing `ParsedDocument`, `Block`, `Page`, `Table`, `Cell`, `BBox`, `Quality` types are sufficient for iteration 1 without modification.

The only change:

```python
class ParserKind(str, Enum):
    LITEPARSE    = "liteparse"
    UNSTRUCTURED = "unstructured"
    LLAMAPARSE   = "llamaparse"
    LANDING_AI   = "landing_ai"
    LOCAL_PIPELINE = "local_pipeline"   # new
```

---

## 8. Package Layout

```
backend/app/cdm/
  adapters/
    local_pipeline/
      __init__.py
      config.py          # LocalPipelineConfig, FitzConfig, CamelotConfig
      probe.py           # DocumentProbe, DocumentProfile, PageProfile
      runner.py          # LocalParseRunner
      merger.py          # eviction logic, bbox overlap math, raw_output assembly
      tools/
        __init__.py
        base.py          # LocalTool protocol, ToolResult, PageMeta
        fitz_tool.py     # FitzTool
        camelot_tool.py  # CamelotTool
```

Future tools drop in as new files under `tools/` — `paddleocr_tool.py`, `docling_tool.py`, etc.

---

## 9. UI Placement

### DocumentProbe UI

**Primary surface: document detail page (iteration 1)**
A "Probe document" action on the document detail page. Shows the `DocumentProfile` as a read-only view: per-page breakdown (page type, text coverage, font health, table signal), document-level summary flags, recommended tools.

**Secondary surface: local pipeline config UI (iteration 2)**
When creating a local pipeline parse run, the existing `DocumentProfile` (if any) is surfaced inline alongside tool selection — `has_cid_corruption: true` → PaddleOCR recommended, `table_signal: true` → camelot recommended. If no profile exists, a "Run probe first" button is offered.

### Local pipeline config UI (iteration 2)
A parse run creation surface specific to `ParserKind.LOCAL_PIPELINE`. Allows tool selection and per-tool config (flavor, thresholds). Probe profile shown as context. Separate from the existing LlamaParse/Landing AI parse run UI.

---

## 10. Iteration Roadmap

| Iteration | Deliverables |
|---|---|
| **1 (this spec)** | `DocumentProbe` + `DocumentProfile` types + probe runner + probe UI on document detail page |
| **2** | `FitzTool` + `CamelotTool` + `LocalParseRunner` + `LocalPipelineConfig` + local pipeline parse run creation UI |
| **3** | `PaddleOCRTool` for CID/scanned pages + PP-StructureV3 for image-based tables |
| **4** | `DoclingTool` for semantic structure (heading detection, hierarchy) |
| **5** | HITL conflict review UI: inspect blocks by tool, evict conflicting blocks via UI |

Each iteration builds on the previous. The `ParseRun.raw_output` schema established in iteration 2 is append-only — new tools add new keys under `tools`, no breaking changes.

---

## 11. Open Questions

1. **DocumentProfile persistence** — where is it stored? Alongside the `Document` ORM row (new column)? As a separate `document_profiles` table? Recommendation: new JSONB column on `documents` table — one profile per document, updated on re-probe.

2. **Re-probe policy** — if a document is re-probed (e.g. after detecting the first probe was wrong), does the new profile replace the old one? Recommendation: yes, replace — there is no meaningful history value in prior probe results.

3. **CamelotTool page mapping** — camelot uses 1-indexed page numbers in its API (`pages="1-3"`). The runner must translate 0-indexed CDM page indices to camelot's 1-indexed strings.

4. **stream flavor and overlap** — in stream mode, camelot TABLE block bboxes may be less precise. The eviction threshold may need tuning per flavor. Consider a `flavor_eviction_threshold` override in `CamelotConfig`.

5. **MarkitdownTool** — can be added in iteration 2 as an optional final step: takes assembled `full_text` or block text and derives `block.markdown` / `full_markdown`. Depends on whether markitdown can operate on already-extracted text (rather than the raw PDF).

6. **Tabula as CamelotTool alternative** — tabula-py covers similar ground to camelot with a different implementation (Java-based). Worth evaluating as an alternative for stream-mode tables. Could be a config option: `CamelotConfig(backend="camelot"|"tabula")`.
