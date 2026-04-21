# Canonical Document Model (CDM) — Architecture Design

> **Status**: Design document. Guides implementation. Not production code.
> **Generated**: 2026-04-20

---

## 0. Design Goals and Parser Context

This section records the problem statement and source-of-truth parser outputs that drove every design decision below. Keep this section when using this document as a spec or planning input — it is the "why" behind the model.

### 0.1 Goals

Design a canonical `ParsedDocument` model that:

1. **Abstracts over 4 different parser backends** — each with a radically different output shape, coordinate system, and semantic vocabulary.
2. **Serves three downstream workloads** without requiring workload code to know which parser produced the document:
   - `split(doc, strategy) → List[ParsedDocument]` — divide into labelled sub-documents (by page, section, or semantic region)
   - `extract(doc, schema) → BaseModel` — pull structured data out (e.g. balance sheet rows, key-value pairs)
   - `classify(doc) → Label` — assign a document or region a type label (e.g. "annual_report", "balance_sheet")
3. **Preserves enough fidelity** that adapters can be written without meaningful data loss — parser-specific fields are carried through, not discarded.

### 0.2 Downstream Workload Signatures

```python
# SPLIT — divide a parsed document into labelled sub-documents
splits: List[ParsedDocument] = split(
    doc,
    strategy="page" | "section" | "semantic"
)
# e.g. [{page: 1, label: "balance_sheet"}, {page: 2, label: "profit_and_loss"}]

# EXTRACT — pull structured data from a document or split result
result: YourSchema = extract(
    doc_or_split,
    output_schema=BalanceSheet   # Pydantic model or JSON field+type dict
)
# e.g. BalanceSheet(assets=[...], liabilities=[...])

# CLASSIFY — assign a label to a document or region
label: Label = classify(doc_or_split)
# e.g. Label(name="annual_report", confidence=0.95, scope="document")
```

### 0.3 Source Parser Output Reference

The four sections below are ground truth for what each parser adapter must map **from**. All design decisions in this document — type taxonomy, coordinate system, table model, hierarchy representation — were made with reference to this data.

---

#### Parser 1: LiteParse (local, Node.js CLI wrapped in Python)

**Output model:**
- `ParseResult` dataclass: `pages: List[Page]`, `text: str`, `num_pages: int`, `json: dict`
- Each `Page`: `textItems: List[TextItem]`, `boundingBoxes: List[BoundingBox]`
- `TextItem`: `text: str`, `x: float`, `y: float`, `width: float`, `height: float`, `fontName: str`, `fontSize: float`, `pageNumber: int`
- `BoundingBox`: parallel array to textItems, same spatial fields
- **No semantic element types** — only one type: `TextItem`
- **Bounding boxes**: PDF points, origin top-left, `(x, y, width, height)` → derive `x2=x+w, y2=y+h`
- **No confidence scores**
- **No table detection**
- **Batch**: `BatchResult` — output to disk only, no in-memory result

---

#### Parser 2: Unstructured OSS (local Python library)

**Output model:**
- `List[Element]` — flat list, no nesting
- 21 element types including: `Title`, `NarrativeText`, `ListItem`, `Table`, `Image`, `Header`, `Footer`, `PageBreak`, `UncategorizedText`, `Text`, `Formula`, `Address`, `EmailAddress`, `FigureCaption`, `CodeSnippet`
- Each element: `.text: str`, `.id: str` (MD5 hash), `.metadata: ElementMetadata`
- `ElementMetadata` key fields:
  - `page_number: int` — **1-indexed**
  - `coordinates: CoordinatesMetadata` → `.points: List[Tuple[float,float]]` (4 corners), `.system: PixelSpace(width, height)` — absolute pixel coords, NOT normalised
  - `parent_id: Optional[str]` — MD5 of parent element (implicit hierarchy via IDs)
  - `category_depth: Optional[int]` — 0=top-level heading, 1=sub-heading etc.
  - `text_as_html: Optional[str]` — present on `Table` elements only
  - `filename: str`, `filetype: str`
  - `languages: List[str]` — detected languages
  - `is_continuation: bool` — element continues from previous page
  - `emphasized_texts: List[...]` — bold/italic spans
- **Hierarchy**: implicit via `parent_id` chains, not nested objects
- **Coordinates**: 4-corner polygon in pixel space (absolute, not normalised); only available with `hi_res` strategy, not `fast`
- **Silent failure**: `fast` strategy returns 0 elements on graphics-heavy PDFs without error — must check provenance
- **Tables**: `text_as_html` on Table elements; per-element coordinates only with `hi_res`
- **Confidence**: none — no per-element confidence scores
- **Strategies**: `fast` (text layer only), `hi_res` (vision model), `ocr_only` (Tesseract)

---

#### Parser 3: LlamaParse (cloud, Gemini 3.0 Flash per page)

**Output model:**
- `ParsingGetResponse` (Pydantic) — must call `.model_dump()` to get plain dicts
- Top-level fields controlled by `expand` param: `text`, `markdown`, `items`, `metadata`, `job_metadata`
- **Items** is the richest output: `{"pages": [{"page_number": int, "items": [...]}]}` — **nested tree**, not flat
- Item types: `heading` (with `level`), `text`, `list` (container), `image`, `table`, `header` (container), `footer` (container), `code`, `link`
- Each item: `type`, `md` (markdown string), `value` (plain text), `bbox: List[BBoxEntry]`
- Container types (`header`, `footer`, `list`) have `items: [...]` child array
- `BBoxEntry`: `{x, y, w, h, confidence, label, start_index, end_index}` — PDF points, origin top-left, `(x, y, w, h)` form
- **`label`** (layout classifier): separate from `type` — values like `"text"`, `"paragraph_title"`, `"image"`, `"table"`
- **`page_number`**: **1-indexed**
- **Markdown output**: rich semantic markdown per page; images as `![caption](url)`
- **Text output**: clean plain text per page
- **Metadata per page**: `confidence: float`, `cost_optimized: bool`, `original_orientation_angle: int`, `triggered_auto_mode: bool`
- **Job metadata**: `model_invocations` per page with `model`, `task`, `input_tokens`, `output_tokens`; timing keys `pdf-llmTime`, `pdf-inputTokens`, `pdf-outputTokens`
- **Deferred retrieval**: `client.parsing.get(job_id, expand=[...])` — re-fetch results with different expand sets without re-parsing

---

#### Parser 4: Landing AI ADE (cloud, dpt-2 model)

**Output model:**
- `ParseResponse` (Pydantic): `chunks`, `markdown`, `metadata`, `splits`, `grounding`
- **Chunks**: flat `List[Chunk]`; each chunk: `id: str` (UUID4), `type: str`, `markdown: str`, `grounding: ChunkGrounding`
- `ChunkGrounding`: `page: int` (**0-indexed**), `box: ParseGroundingBox`
- `ParseGroundingBox`: `left, top, right, bottom` — **normalised 0.0–1.0 fractions** of page dimensions
- **Chunk types**: `text`, `table`, `figure`, `logo`, `attestation`, `scan_code`, `marginalia`
- **Markdown format**: each chunk prefixed with `<a id='UUID'></a>` anchor; non-text uses custom delimiters: `<::logo: Name\nDesc::>`, `<::attestation: Type\nContent::>`, `<::scan_code: Type\nContent::>`
- **Tables**: HTML `<table id="page-N">` with `<td id="page-col">` per cell
- **`r.markdown`**: full document as a single string with `<!-- PAGE BREAK -->` separators and `<a id='...'>` anchors per chunk
- **`r.splits`**: `[{class_: "full"|"page", identifier: str, pages: List[int], chunks: List[str], markdown: str}]`
- **`r.grounding`**: `Dict[str, Grounding]` — keyed by chunk UUID **or** cell ID:
  - Chunk entries: `type="chunkText"|"chunkTable"|"chunkFigure"|"chunkLogo"...`, `confidence: Optional[float]`, `low_confidence_spans: Optional[List[...]]`
  - Table cell entries: `type="tableCell"`, `position: {chunk_id, row, col, rowspan, colspan}`, `confidence: float`
- **`metadata`**: `filename`, `page_count`, `duration_ms`, `credit_usage`, `job_id`, `version`, `failed_pages`
- **Sync limit**: 100 pages max; use async `parse_jobs` API for larger documents

---

#### Parser Comparison Summary

| Property | LiteParse | Unstructured | LlamaParse | Landing AI |
|---|---|---|---|---|
| Output shape | Flat TextItem list | Flat Element list | Nested items tree | Flat Chunk list |
| Semantic types | None (1 type) | 21 types | 9 types | 7 types |
| Page indexing | 1-indexed | 1-indexed | 1-indexed | **0-indexed** |
| Bbox form | PDF points `(x,y,w,h)` | Pixel polygon (4 corners) | PDF points `(x,y,w,h)` | Normalised `(l,t,r,b)` |
| Bbox availability | All elements | `hi_res` only | All items | All chunks |
| Cell-level bbox | ❌ | ❌ | ❌ | ✅ |
| Confidence | ❌ | ❌ | ✅ per-item + per-page | ✅ per-chunk |
| Table detection | ❌ | ✅ (`hi_res`) | ✅ | ✅ |
| Table format | — | HTML string | Markdown | HTML with cell IDs |
| Hierarchy | None | `parent_id` references | Nested `items` tree | Flat + UUID anchors |
| Cloud / local | Local | Local | Cloud | Cloud |

---

## 1. Naming Rationale

**Proposed name: `ParsedDocument`** (module: `canonical_doc` or `cdm`), with the namespace shorthand **CDM** (Canonical Document Model) for the whole package.

Rationale:
- "Parsed" signals the model is *post-parse* — it is not a generic document abstraction (no authoring, no editing semantics), it is the settled output of a parser adapter.
- "Canonical" is reserved for the package/module name rather than the class name itself, because callers will type `ParsedDocument` constantly; one word beats three.
- Avoids overloaded terms: not `Document` (collides with every ORM/NLP library), not `Parse` (verb), not `Report` (domain-specific), not `Element` or `Chunk` (those names are claimed by specific parsers and would confuse adapter authors).
- Element-level class is **`Block`** — a span of semantic content. Narrower than "Element" (Unstructured), broader than "Chunk" (Landing AI), and doesn't imply the physical-vs-logical distinction that "segment" carries.
- Sub-block text runs (only LiteParse produces these natively) are **`Span`**.

Subsidiary types: `Page`, `Block`, `Span`, `Table`, `Cell`, `BBox`, `Provenance`, `BlockRole`, `ParserKind`.

---

## 2. Object Model

```python
# Enums — closed taxonomies the core model commits to.

class ParserKind(str, Enum):
    LITEPARSE      = "liteparse"
    UNSTRUCTURED   = "unstructured"
    LLAMAPARSE     = "llamaparse"
    LANDING_AI     = "landing_ai"

class BlockRole(str, Enum):
    # Deliberately coarse — ~14 values. Adapter-native types are preserved
    # verbatim on Block.native_type; BlockRole is the lowest common denominator
    # that split/classify/extract can branch on.
    TITLE       = "title"        # heading of any level
    HEADING     = "heading"      # subheading / section heading
    PARAGRAPH   = "paragraph"   # narrative text / generic text
    LIST        = "list"         # list container or list item
    TABLE       = "table"
    FIGURE      = "figure"       # image, figure, logo, scan_code
    CAPTION     = "caption"
    HEADER      = "header"       # page header / running head
    FOOTER      = "footer"       # page footer
    MARGINALIA  = "marginalia"
    CODE        = "code"
    FORMULA     = "formula"
    LINK        = "link"
    OTHER       = "other"        # fall-through; check native_type

class CoordSpace(str, Enum):
    NORMALIZED = "normalized"    # 0..1 fractions of page size — canonical


# ── Geometry ─────────────────────────────────────────────────────────────────

class BBox(BaseModel):
    # Canonical: normalized fractions, origin top-left, (x0, y0, x1, y1).
    x0: float
    y0: float
    x1: float
    y1: float
    space: CoordSpace = CoordSpace.NORMALIZED
    # Optional originals for lossless round-tripping.
    source_space:  Optional[str]                        = None  # "pdf_points" | "pixels" | "fraction"
    source_coords: Optional[Tuple[float, float, float, float]] = None


# ── Quality / confidence ──────────────────────────────────────────────────────

class Quality(BaseModel):
    confidence:           Optional[float]          = None   # 0..1 where defined
    low_confidence_spans: List[Tuple[int, int]]    = []     # char-offset ranges
    notes:                Optional[str]            = None   # e.g. "fast strategy, 0 elements"


# ── Font / style (LiteParse populates richly; others partially) ───────────────

class Style(BaseModel):
    font_name:  Optional[str]   = None
    font_size:  Optional[float] = None
    bold:       Optional[bool]  = None
    italic:     Optional[bool]  = None


# ── Sub-block text run (present for LiteParse; optional elsewhere) ────────────

class Span(BaseModel):
    text:  str
    bbox:  Optional[BBox]  = None
    style: Optional[Style] = None


# ── Table model (see Section 4) ───────────────────────────────────────────────

class Cell(BaseModel):
    row:       int
    col:       int
    rowspan:   int             = 1
    colspan:   int             = 1
    text:      str
    bbox:      Optional[BBox]    = None
    quality:   Optional[Quality] = None
    is_header: bool            = False

class Table(BaseModel):
    rows:     int
    cols:     int
    cells:    List[Cell]
    html:     Optional[str] = None      # source HTML if parser provided
    markdown: Optional[str] = None
    caption:  Optional[str] = None


# ── Block — the unit of semantic content ─────────────────────────────────────

class Block(BaseModel):
    id:            str                   # stable within a ParsedDocument
    role:          BlockRole             # canonical role
    native_type:   str                   # raw type string from source parser
    native_label:  Optional[str] = None  # secondary classifier (e.g. LlamaParse layout label)
    text:          str             = ""  # plain-text view
    markdown:      Optional[str]  = None
    html:          Optional[str]  = None  # e.g. table HTML
    page_index:    int                   # 0-indexed — canonical
    bbox:          Optional[BBox]  = None
    reading_order: Optional[int]  = None  # position within page
    depth:         Optional[int]  = None  # heading depth / nesting depth
    parent_id:     Optional[str]  = None  # hierarchy via reference
    children_ids:  List[str]      = []
    spans:         List[Span]     = []    # sub-block runs (LiteParse)
    table:         Optional[Table] = None # populated iff role == TABLE
    image_ref:     Optional[str]  = None  # asset key for figures
    style:         Optional[Style] = None
    quality:       Optional[Quality] = None
    language:      Optional[str]  = None
    is_continuation: bool         = False  # block continues from previous page
    parser_extras: Dict[str, Any] = {}    # adapter-native fields, opaque to core


# ── Page ──────────────────────────────────────────────────────────────────────

class Page(BaseModel):
    index:         int                    # 0-indexed
    width:         Optional[float] = None  # native units
    height:        Optional[float] = None
    unit:          Optional[str]  = None  # "points" | "pixels"
    rotation:      int            = 0     # degrees: 0 / 90 / 180 / 270
    block_ids:     List[str]      = []    # blocks on this page, reading order
    quality:       Optional[Quality] = None  # per-page score (LlamaParse)
    parser_extras: Dict[str, Any] = {}


# ── Provenance ────────────────────────────────────────────────────────────────

class ModelInvocation(BaseModel):
    model:         str
    task:          str
    input_tokens:  Optional[int] = None
    output_tokens: Optional[int] = None
    page_index:    Optional[int] = None

class Provenance(BaseModel):
    parser:         ParserKind
    parser_version: Optional[str]      = None
    job_id:         Optional[str]      = None
    source_uri:     Optional[str]      = None
    source_hash:    Optional[str]      = None   # sha256 of input bytes
    parsed_at:      datetime
    duration_ms:    Optional[int]      = None
    cost:           Optional[Dict[str, Any]] = None
    invocations:    List[ModelInvocation]    = []
    failed_pages:   List[int]          = []
    warnings:       List[str]          = []
    # For split() children:
    derived_from:   Optional[str]      = None   # parent ParsedDocument.id
    derivation:     Optional[str]      = None   # e.g. "split:page", "split:semantic"


# ── Label (classify() output) ─────────────────────────────────────────────────

class Label(BaseModel):
    name:       str
    confidence: Optional[float] = None
    scope:      Literal["document", "page", "block"] = "document"
    scope_ref:  Optional[Union[int, str]] = None  # page_index or block_id
    source:     Literal["parser", "classifier", "human"] = "classifier"


# ── Root ──────────────────────────────────────────────────────────────────────

class ParsedDocument(BaseModel):
    id:              str                  # UUIDv4
    source_filename: Optional[str] = None
    page_count:      int
    pages:           List[Page]
    blocks:          List[Block]          # authoritative flat list
    full_text:       Optional[str] = None  # cached concatenation
    full_markdown:   Optional[str] = None
    labels:          List[Label]  = []    # classify() outputs live here
    provenance:      Provenance
    schema_version:  str          = "1.0"
```

### 2.1 Hierarchy Representation

Adopt **flat-with-edges**: `blocks` is the authoritative flat list (matches Unstructured and Landing AI natively, and is cheap for downstream iteration). Hierarchy is expressed by `parent_id` + `children_ids` on each block. LlamaParse's nested trees are flattened at adapter time; the edges are preserved. LiteParse produces no hierarchy, so those fields stay empty. This gives O(1) "give me all blocks" for extract/classify, plus recoverable tree structure when needed.

### 2.2 Semantic Type

Two fields: canonical `role: BlockRole` (closed, coarse) and `native_type: str` (open, parser-vocabulary). This is the escape hatch for "Landing AI says `attestation` — we don't want that in the core enum but we don't want to drop it." `native_label` holds a secondary classifier output (LlamaParse's layout `label`, distinct from its `type`).

### 2.3 Parser-Specific Metadata

`parser_extras: Dict[str, Any]` on `Block` and `Page`. Opaque to the core model, available to adapters and to callers who know their parser. Pydantic's `model_config` should allow these to serialize through without validation.

---

## 3. Coordinate System Resolution

**Canonical: normalised fractions `(x0, y0, x1, y1)`, origin top-left, `CoordSpace.NORMALIZED`.**

| Parser | Native form | Conversion |
|---|---|---|
| LiteParse | PDF points, top-left, `(x, y, w, h)` | divide by page width/height from the Page record |
| Unstructured | absolute pixels, 4-corner polygon | take polygon bounding rect, divide by page pixel size |
| LlamaParse | PDF points, top-left, `(x, y, w, h)` | divide by page width/height |
| Landing AI | normalised, top-left, `(left, top, right, bottom)` | identity |

**Why normalised:**
- Three of four parsers provide enough information to normalise; Landing AI is already normalised, making it the cheapest common target.
- Normalised bboxes survive page rasterisation at arbitrary DPI — relevant for visual extraction and UI overlay rendering.
- Comparable across parsers without carrying unit metadata through every consumer.
- `(x0, y0, x1, y1)` form chosen over `(x, y, w, h)` because it composes trivially (union, intersection, containment) and matches the PIL/COCO convention.

**Originals** are preserved on `BBox.source_space` / `source_coords` so adapters are non-lossy and round-trips are possible. `Page.width`/`height`/`unit` preserves native page dimensions for reconstruction.

**Page indexing** is normalised to **0-indexed** at the adapter boundary. Unstructured/LlamaParse/LiteParse all get `-1` applied. Matches Python list semantics: `doc.pages[block.page_index]` always works.

---

## 4. Table Model Deep-Dive

Tables are the most divergent case across parsers. The canonical `Table` is **cell-list + optional HTML + optional markdown** — not HTML-first and not grid-first.

**Design:**
- **`cells: List[Cell]`** is authoritative. Each cell carries `(row, col, rowspan, colspan, text, bbox, quality, is_header)`. This is the only representation that can carry Landing AI's per-cell bbox and confidence, and it correctly models merged cells (rowspan/colspan) without requiring a dense 2D grid.
- **`html`** is preserved verbatim when the parser provides it (Unstructured's `text_as_html`, Landing AI's `<table>` block). Most useful for LLM-based extraction — HTML is a dense, well-understood table representation for models.
- **`markdown`** preserved when present (LlamaParse, Landing AI).
- **No dense grid field stored.** A `grid: List[List[Cell]]` view is a trivial derivation, offered as a helper method on `Table` — not a stored field, to avoid two sources of truth.

**Population by parser:**

| Parser | Cell source | Cell bbox | HTML | Markdown |
|---|---|---|---|---|
| Landing AI | Parsed from `<table>` HTML; row/col/span from `<td id>` attributes | ✅ From `tableCell` grounding entries | ✅ verbatim | ✅ from block |
| Unstructured | Parsed from `text_as_html` | ❌ | ✅ verbatim | ❌ |
| LlamaParse | Parsed from item `md` (markdown table) or HTML rendering | ❌ per-cell (table-level only) | ❌ | ✅ from item |
| LiteParse | **No table detection** | ❌ | ❌ | ❌ |

**LiteParse handling:** Default in v1 — emit no `TABLE` blocks; LiteParse output produces `PARAGRAPH` blocks with position data. A pluggable `TableReconstructor` hook on the adapter (consuming `TextItem` coordinates) is deferred to a future version.

**Queryability for extract():** Cell list is directly iterable; a grid helper gives `table.row(i)` / `table.column(j)`; `html` is the preferred input for LLM-based extraction; `markdown` is the fallback.

---

## 5. Adapter Protocol

```python
class ParserAdapter(Protocol):
    parser: ClassVar[ParserKind]

    def adapt(self, raw: Any, source_meta: SourceMeta) -> ParsedDocument: ...
```

One method, one direction. Adapters are stateless. `raw` is the parser's native output object; `source_meta` carries filename, content hash, and job_id.

### Per-Parser Mapping Notes

**LiteParse**
- ✅ Clean: text content, bboxes (PDF points → normalised), font/size metadata, spans (`TextItem` → `Span`).
- ⚠️ Lossy: no semantic roles — everything collapses to `PARAGRAPH` with `native_type="textItem"`. Heading detection by font-size heuristic is out of scope for v1 (deferred to a post-adapter enrichment pass).
- ❌ Absent: hierarchy, confidence, tables, images.

**Unstructured**
- ✅ Clean: 21 element types map into `BlockRole` via a fixed lookup table (`Title/Header → HEADING`, `NarrativeText → PARAGRAPH`, `ListItem → LIST`, `Table → TABLE`, `Image → FIGURE`, `Formula → FORMULA`, etc.). `parent_id` maps directly. `category_depth → depth`. `text_as_html → Table.html`.
- ⚠️ Lossy: coordinate polygon approximated by axis-aligned bounding rect.
- ❌ Absent: confidence scores. Silent 0-element failure (graphics-heavy PDFs on `fast` strategy) becomes a `provenance.warnings` entry.

**LlamaParse**
- ✅ Clean: nested tree flattened; parent/child edges preserved. `type → role`, `label → native_label`. `md → Block.markdown`. Per-bbox `confidence` → `Block.quality`. Per-page `confidence` → `Page.quality`. `model_invocations → Provenance.invocations`.
- ⚠️ Lossy: items with multiple `BBoxEntry` entries collapsed to one (union bbox) for `Block.bbox`; originals kept in `parser_extras["bboxes"]`. `start_index`/`end_index` saved to `parser_extras`.
- ❌ / ➡️ Extras: `cost_optimized`, `original_orientation_angle` → `Page.rotation` and `parser_extras`.

**Landing AI**
- ✅ Clean: UUID → `Block.id`. `box → BBox` (already normalised, identity conversion). Per-chunk `confidence`, `low_confidence_spans` → `Quality`. Per-cell grounding → `Cell.bbox` + `Cell.quality`. `credit_usage → provenance.cost`.
- ✅ Bonus: `splits` is the one parser that natively supplies split-like groupings — cache in `parser_extras["landing_ai_splits"]` so `split(strategy="parser_native")` can use them directly.
- ⚠️ Mapping: `attestation`, `logo`, `scan_code` chunk types collapse to `FIGURE` / `OTHER` in v1, with `native_type` preserving the distinction. Promotion to first-class `BlockRole` values is an open question (§9).
- ✅ Page indexes already 0-indexed — no conversion.

---

## 6. Extract Schema Convention

**Recommendation: Accept both `Type[BaseModel]` and a JSON field+type dict at the API surface; unify internally via `pydantic.create_model`.**

### Evaluation

| Format | Pros | Cons |
|---|---|---|
| Pydantic class | Type safety, validation, IDE autocomplete, nested models free, `.model_json_schema()` for prompt construction | Defined at import time; runtime-dynamic schemas need `create_model` |
| JSON field+type dict | Universal, serialisable, composable at runtime, easy to ship over HTTP or read from config | No type safety, no validation, ad-hoc nested structure |

### Resolution

Both are accepted at the surface and normalised internally:

```python
SchemaLike = Union[Type[BaseModel], Dict[str, Any]]

def extract(doc: ParsedDocument, schema: SchemaLike) -> BaseModel:
    model_cls = _coerce_to_pydantic(schema)   # pydantic.create_model for dict input
    ...
```

The JSON dict form is a minimal JSON-Schema subset:
```json
{
  "field_name": "str",
  "another_field": {
    "type": "list",
    "items": { "type": "str" }
  },
  "nested": {
    "type": "object",
    "properties": { "sub_field": "float" },
    "description": "optional description for LLM prompt"
  }
}
```

Both input paths converge on the same representation internally. Pydantic models expose `.model_json_schema()` for LLM prompt construction, so static callers (typed) and dynamic callers (dict) are indistinguishable to the extractor implementation.

---

## 7. Downstream Workload Contracts

### `split(doc, strategy) -> List[ParsedDocument]`

**Depends on:** `Block.page_index`, `Block.role`, `Block.depth`, `Block.reading_order`, `Page.block_ids`. Optionally `parser_extras["landing_ai_splits"]` for `strategy="parser_native"`.

**Invariants:**
- Every block in a child `ParsedDocument` also exists in the parent; block IDs are **not re-generated** so that extract/classify results on a child can be joined back to the parent.
- Each child's `Provenance.derived_from = parent.id` and `derivation = f"split:{strategy}"`.
- Page indexes inside a child are **re-indexed from 0**; originals preserved in `Page.parser_extras["source_page_index"]`.

**Driven design decisions:** `Provenance.derived_from`/`derivation`. Flat `blocks` list (O(n) filter by `page_index`). Stable block IDs across the adapter boundary. `Label.scope`/`scope_ref` so a split child can carry `{name: "balance_sheet", scope: "document"}` cleanly.

---

### `extract(doc_or_split, output_schema) -> BaseModel`

**Depends on:** `Block.text`, `Block.markdown`, `Block.html`, `Block.role`, `Block.table` (cell list + html + markdown), `ParsedDocument.full_markdown`.

**Invariants:**
- The model must be serialisable to a prompt context without requiring the caller to understand parser-specific fields — `parser_extras` is not walked by default prompt builders.
- `full_markdown` is cached on the root (concatenation must not happen inside every extract call).

**Driven design decisions:** `Table.html` and `Table.markdown` stored alongside cell list (LLMs extract better from rendered tables). `full_markdown` as a cached root field. Stable block IDs to allow extracted values to carry back-pointers (`_source_block_id`) for auditability — citation tracking is an open question (§9).

---

### `classify(doc_or_split) -> Label` (written into `doc.labels`)

**Depends on:** `Block.role`, `Block.text`, `ParsedDocument.full_text`, `Page.index`, optionally `Provenance.parser`.

**Invariants:**
- `classify()` writes results into `doc.labels` (on a `model_copy`, since the model is immutable) rather than returning a bare string. This gives uniform downstream access whether the label came from a classifier, a parser, or a human reviewer.

**Driven design decisions:** `Label` as a first-class model with `scope`/`scope_ref`/`source` — not a bare string. `BlockRole` being coarse (~14 values): a classifier trying to distinguish `UncategorizedText` from `NarrativeText` is noise at this level of abstraction.

---

## 8. Architecture Decisions and Trade-offs

| Decision | Choice | Rationale |
|---|---|---|
| Model base | Pydantic v2 `BaseModel` | Three of four parsers already return Pydantic. Free JSON (de)serialisation, `.model_json_schema()` for LLM prompts, validators at adapter boundary, `model_copy(update=...)` for immutability pattern. |
| Mutability | Frozen (`model_config(frozen=True)`) | Parsed documents are cache keys, shared across threads/processes, passed between workloads concurrently. Mutations return new instances via `model_copy`. |
| Serialisation | JSON via `model_dump_json()` / `model_validate_json()` | Sufficient for v1. Columnar (Parquet/Arrow over the `blocks` list) deferred for corpus-scale analytics. `schema_version` field present from day one for migration. |
| Hierarchy | Flat list + edge references (`parent_id` / `children_ids`) | Matches Unstructured and Landing AI natively. LlamaParse trees are flattened at adapter time, edges preserved. O(1) full-list iteration; O(n) tree traversal when needed. No circular references; survives serialisation. |
| IDs | `ParsedDocument.id`: UUIDv4, adapter-minted. `Block.id`: stable within document; adapters reuse source parser ID (Unstructured MD5, Landing AI UUID) or mint one. | Cross-document ID stability not promised in v1. |
| Provenance for splits | `derived_from: parent.id` (reference, not embedded parent) | Prevents O(n²) size blowup when splitting a 500-page document into page-level children. |
| `parser_extras` type | `Dict[str, Any]` | Deliberately unstructured pressure valve. If a field in `parser_extras` is consistently used, it gets promoted to a first-class field in the next schema version. |
| Validation boundary | Strict at adapter boundary (`model_config(extra="forbid")` on core types); trusted downstream | Re-validating on every workload call would be expensive and wrong — adapters are the trust boundary. |
| Streaming | Not in v1 | Each parser is called eagerly; full `ParsedDocument` materialised in memory. Deferred for very large documents. |

---

## 9. Open Questions / Deferred Decisions

1. **Heading detection for LiteParse.** A post-adapter enrichment pass that clusters `TextItem` font sizes to promote some `PARAGRAPH` blocks to `HEADING`. Required for `split(strategy="section")` to work on LiteParse output. Not in v1.

2. **Table reconstruction for LiteParse.** A pluggable `TableReconstructor` hook on the LiteParse adapter, consuming `TextItem` coordinates and emitting `Block(role=TABLE)`. Not in v1.

3. **Citation tracking in extract().** When extract() produces `BalanceSheet(total_assets=1_234_000)`, should the result carry `_source_block_ids` automatically? Requires a `Traceable` base mixin on extract outputs and a convention in extractor implementations.

4. **Streaming / chunked parse results.** For very large documents (Landing AI async jobs, 100+ pages). The current model assumes full materialisation.

5. **Columnar storage.** Parquet/Arrow over the `blocks` list for corpus-scale analytics. Likely a sibling serialiser, not a change to the core model.

6. **Landing AI special chunk types.** `attestation`, `logo`, `scan_code` collapse to `FIGURE`/`OTHER` in v1. Promote to first-class `BlockRole` values if downstream workloads branch on them consistently.

7. **Multi-parser consensus.** If the pipeline runs the same PDF through two parsers, can we merge results into one `ParsedDocument` with per-block provenance? Useful for quality; deferred.

8. **Redaction / PII annotations.** First-class `Block` field vs. separate annotation layer. Deferred pending security requirements.

9. **Cross-document `Block.id` stability.** Content-hash based IDs to enable diffing the same document reparsed. Not needed for v1; revisit if reparse/compare tooling is added.

10. **`Page.width`/`height` units.** Currently carried as a `unit` string alongside the value. Could normalise to PDF points universally. Left as-is because raster parsers produce pixels and normalising loses information that may be needed for precise reconstruction.
