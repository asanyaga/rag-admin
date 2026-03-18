# Intelligent Document Parsing & Extraction — Feature Spec v4

## RAG Admin Feature: Document IDP (Intelligent Document Processing)

**Status:** Draft for Review (v4.1 — reviewed, tightened scope)
**Author:** Asa
**Date:** 2026-03-17
**Scope:** Week 1 deliverables (of 7-week plan)
**Codebase reference:** github.com/asanyaga/rag-admin (commit d9f08ca)

---

## 1. Problem Statement

RAG Admin currently extracts text from PDFs using LlamaIndex's SimpleDirectoryReader — a naive text dump that works on clean, text-based PDFs but fails badly on CID-encoded PDFs (DigitalOcean 2024 AR → `(cid:0)(cid:2)(cid:3)...` garbage), scanned documents and images (no text layer), and complex layouts (financial tables, multi-column reports → text ordering garbled).

There is no way to detect these failures, understand WHY they happen, compare parsing approaches, or evaluate extraction quality against expected output.

### Why This Matters Beyond RAG

For document formats, **what you see is not what you get**. The DigitalOcean 2024 AR looks identical to the 2023 AR when viewed in a PDF reader — same fonts, same layout, same visual rendering. But the 2024 version uses CID-mapped fonts that don't encode to Unicode, while the 2023 version uses standard font encoding. A naive text extractor produces perfect text from one and garbage from the other.

Understanding this gap — between visual appearance and machine-readable representation — is the foundation of document processing. A consultant needs to explain why a client's "perfectly good PDF" produces nonsense, why you need OCR for some PDFs but not others, and why extracting a table requires understanding layout, not just reading text top-to-bottom.

**The parse result is the diagnostic artifact that makes this visible.** It's not just a pipeline intermediate — it's proof of what the document actually contains at the machine level.

---

## 2. Conceptual Model: Parse vs Extract

### The Core Distinction

**Parsing** is describing the document — telling you what's physically there at some level of structural fidelity. It answers: "what does this document contain and how is it laid out?"

**Extraction** is interpreting the document against a purpose — mapping the parsed description to a schema. It answers: "given what's in this document, what are the specific values I need?"

These are fundamentally different operations. One is faithful representation, the other is purposeful interpretation. A parser never says "vendor_name is Naivas." It says "there's text at the top that reads 'Naivas Supermarket'" or "there's a region of type 'header' containing 'Naivas Supermarket'." Mapping that to `vendor_name` is extraction's job.

### Parse Fidelity Levels

Parse results describe the document at different levels of structural fidelity:

```
TEXT fidelity                MARKDOWN fidelity             LAYOUT JSON fidelity
─────────────                ────────────────              ────────────────────
"I found these               "I found these characters     "I found these regions,
characters in                 AND this bit is a heading,    their spatial positions,
this order.                   this bit is a table,          reading order, that this
No structure,                 this bit is bold."            table has 3 columns and
no meaning,                                                7 rows, that this is a
just a dump."                                              chart with these values."

PyMuPDF, basic OCR           LlamaParse, Docling           LandingAI, PaddleOCR
                                                           PP-StructureV3
```

All three are PARSING — they describe what's in the document. None of them say `vendor_name: "Naivas"`. The fidelity level determines how much structural information is preserved, which affects how well downstream extraction can work:

- **Harder** from raw text (must infer all structure from character patterns)
- **Easier** from markdown (headings, tables already identified)
- **Easiest** from layout JSON (regions typed, spatial relationships explicit)

### Where Vendors Sit

| Vendor | Parsing? | Extraction? | Output Fidelity |
|--------|----------|------------|----------------|
| **LlamaIndex SimpleDirectoryReader** ("Simple") | Text only | No | Text — characters in reading order |
| **LlamaParse fast tier** | Text only (spatial) | No | Text — preserves spatial layout |
| **LlamaParse agentic/agentic_plus** | Text + Markdown + Items | No | Markdown — headings, tables, formatting preserved |
| **LlamaParse items expand** | Structured JSON | No | Layout JSON — typed items with bounding boxes |
| LlamaCloud `extraction.jobs.extract()` | Internal (opaque) | Yes (schema-mapped) | Bundled parse+extract (Week 3+) |
| Claude Vision | Varies by prompt | Varies by prompt | Depends on what you ask (Week 3+) |

**Week 1 scope:** Simple (existing) + LlamaParse (new). Other vendors are future work.

**Key insight**: LlamaParse output fidelity depends on the **tier** and **expand options** chosen:
- `fast` tier → text only (1 credit/page)
- `agentic` + `expand=["markdown"]` → rich markdown with tables (10 credits/page)
- `agentic` + `expand=["items"]` → structured items with bounding boxes (10 credits/page)
- You can request multiple expand options in one call.

### The Pipeline

```
Document Upload (user selects parse method)
    │
    ├── "Simple" → LlamaIndexExtractor → documents.extracted_text (existing flow)
    │
    └── Intelligent parser (LlamaParse in v1, future: LandingAI, Reducto, etc.)
        │   → DocumentParser.parse() → ParseResult
        │
        ├── parse_results table
        │   parser_type: which parser was used
        │   fidelity: "text" | "markdown" | "layout_json" (depends on parser + config)
        │   raw_text: plain text (ALWAYS populated, regardless of parser)
        │   markdown: richer representation (if parser supports it)
        │   pages: per-page content (if parser provides it)
        │   document_structure: structured layout data (if parser provides it)
        │
        ├── documents.extracted_text (raw_text written here for chunking compatibility)
        │
        └── EXTRACT (downstream, parser-agnostic — uses ParseContentResolver)
            └── extraction_results table
                source_parse_result_id: which parse this extraction was based on
                schema_id: which schema was applied
                structured_data: { "vendor_name": "Naivas", "total": 175.00 }
                extraction_method: "llm" | "rule_based" | "vendor_bundled"
```

---

## 3. Parse-at-Upload Flow

### Current State

```
PDF Upload → user enters title/description
    → BackgroundTasks → LlamaIndexExtractor.extract() (SimpleDirectoryReader)
    → documents.extracted_text populated
    → Chunking reads document.extracted_text
```

The user has no control over how the document is parsed. SimpleDirectoryReader is the only option.

### New State: User Chooses Parse Method at Upload Time

The upload dialog gains a **parse method selector**. The user chooses before clicking "Upload":

```
Document Upload (PDF or image)
    │
    User selects parse method:
    │
    ├── "Simple (local)" — current behavior
    │   └── LlamaIndexExtractor → documents.extracted_text
    │   └── No parse_results record (unchanged pipeline)
    │
    └── "LlamaParse" — new intelligent pipeline
        │   User also selects: tier (fast/agentic/agentic_plus) + output format (markdown/text/both)
        │
        └── BackgroundTasks:
            1. Upload file to LlamaCloud (client.files.create)
            2. Start parse job (client.parsing.parse)
            3. SDK handles polling internally, returns result
            4. Store in parse_results table
            5. Also populate documents.extracted_text with raw_text (for downstream chunking compatibility)
```

**Key design decision:** Parse method is chosen at upload time, not as a separate post-upload action. This is simpler UX — the user doesn't upload then go find a "Parse with..." button. They see the option right there in the upload form.

**Re-parsing:** A user can also trigger a re-parse of an existing document from the document detail page (e.g., to try a different tier or output format). This creates a new `parse_results` row. The document detail page shows all parse results for comparison.

### Why NOT Refactor `extracted_text` in Week 1

18 direct references across the codebase. When using LlamaParse, we write the best-effort text to `documents.extracted_text` too, so chunking and existing features keep working. The migration path is clear (see Section 13) but it's a Week 3+ task.

---

## 4. New Interfaces

### 4.1 DocumentParser ABC (Parsing Layer)

```python
# backend/app/ports/document_parsing.py  (NEW FILE)

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class ParserType(str, Enum):
    """The tool/vendor — not the output shape.

    Only SIMPLE and LLAMAPARSE are implemented in v1.
    The enum is extensible — new parsers are added here as they're integrated.
    The string value is stored in the DB, so values must be stable.
    """
    SIMPLE = "simple"              # Current LlamaIndexExtractor (SimpleDirectoryReader)
    LLAMAPARSE = "llamaparse"      # LlamaParse v2 API (via llama-cloud SDK)
    # Future (not in v1):
    # LANDINGAI = "landingai"      # Layout-aware structured extraction
    # REDUCTO = "reducto"          # High-fidelity document parsing
    # UNSTRUCTURED = "unstructured"# Open-source document parsing
    # CLAUDE_VISION = "claude_vision"  # LLM-based visual parsing
    # CUSTOM = "custom"            # User-defined IDP pipeline


class ParseFidelity(str, Enum):
    """Level of structural description in the parse output."""
    TEXT = "text"                   # Characters in order, no structure
    MARKDOWN = "markdown"          # Characters + structural markers (headings, tables)
    LAYOUT_JSON = "layout_json"    # Regions, spatial positions, typed elements


@dataclass
class ParseResult:
    """A parser's description of a document — parser-agnostic output contract.

    Every parser MUST populate raw_text. Everything else is optional and depends
    on the parser's capabilities and the user's config. Downstream consumers
    (extraction, chunking) use the fidelity field + helper methods to decide
    what to read.

    This contract must work for LlamaParse, LandingAI, Reducto, Unstructured,
    Claude Vision, and any future parser without changes to the dataclass.
    """

    # ── Universal fields (every parser must populate these) ──────────────
    raw_text: str                           # Best-effort plain text (ALWAYS populated)
    fidelity: str = "text"                  # What level of structure is available:
                                            #   "text" → only raw_text is meaningful
                                            #   "markdown" → markdown field is populated
                                            #   "layout_json" → document_structure is populated
    parser_type: str = ""                   # Which parser produced this (matches ParserType enum)

    # ── Optional enrichments (populated depending on parser + config) ────
    markdown: str | None = None             # Markdown representation of the full document
                                            # Populated by: LlamaParse (agentic+), Reducto, Unstructured, etc.
                                            # NOT populated by: Simple, LlamaParse fast tier

    pages: list[dict[str, Any]] | None = None
    # Per-page content. Shape is parser-agnostic — every parser that populates
    # this uses the same minimal contract:
    #   { "page_number": int,              # 1-based
    #     "text": str,                     # plain text for this page
    #     "markdown": str | None,          # markdown for this page (if available)
    #     "metadata": dict | None }        # parser-specific per-page metadata
    # The metadata dict is intentionally unstructured — LlamaParse puts
    # { "confidence": 0.95 }, LandingAI might put { "regions_detected": 12 }, etc.

    document_structure: dict[str, Any] | None = None
    # Structured layout data. Shape varies by parser — this is the parser's
    # native structured output, stored as-is. Examples:
    #
    # LlamaParse items: { "items": [{ "type": "heading", "value": "...", "bbox": {...} }] }
    # LandingAI:        { "regions": [{ "type": "table", "bbox": [...], "cells": [...] }] }
    # Unstructured:     { "elements": [{ "type": "Title", "text": "...", "metadata": {...} }] }
    #
    # Downstream consumers that need structure check parser_type to interpret this.
    # The frontend renders a generic "Structure" tab that shows this as formatted JSON,
    # with parser-specific renderers added as needed.

    # ── Config and metadata ──────────────────────────────────────────────
    parser_config: dict[str, Any] = field(default_factory=dict)
    # Parser-specific config that was used. Stored for reproducibility.
    # LlamaParse: { "tier": "agentic", "expand": ["markdown", "text"], "version": "latest" }
    # LandingAI:  { "model": "layout-v2", "ocr": true }
    # Reducto:    { "quality": "high" }

    metadata: dict[str, Any] = field(default_factory=dict)
    # Parser-specific execution metadata.
    # Common keys (all parsers should try to populate):
    #   "latency_ms": int, "page_count": int, "token_count": int
    # Parser-specific keys:
    #   LlamaParse: "credits_used", "llamaparse_job_id"
    #   LandingAI:  "model_version", "regions_detected"

    # ── Diagnostics (auto-computed from raw_text, parser-agnostic) ───────
    diagnostics: dict[str, Any] = field(default_factory=dict)
    # Always computed by diagnostics.py from raw_text — same for every parser:
    #   "non_empty", "char_count", "printable_ratio", "suspected_cid",
    #   "token_count", "has_table_markers", "has_heading_markers", "empty_pages"
    # Plus parser-specific signals (e.g., LlamaParse per_page_confidence)


class DocumentParser(ABC):
    """Port: Parse documents into structural descriptions.

    Distinct from DocumentExtractor (existing naive text extraction).
    Distinct from ExtractionService (schema-mapped field extraction).
    """

    @abstractmethod
    async def parse(
        self,
        file_path: str,
        config: dict[str, Any] | None = None,
    ) -> ParseResult:
        """Parse a document from a local file path.

        The adapter is responsible for uploading the file to the vendor
        if the vendor API requires it (e.g., LlamaCloud file upload).
        Callers always pass a local path; the adapter handles transfer.
        """
        ...

    @abstractmethod
    def supported_file_types(self) -> list[str]:
        """MIME types this parser can handle."""
        ...

    @property
    @abstractmethod
    def parser_type(self) -> ParserType:
        ...

    @property
    @abstractmethod
    def default_fidelity(self) -> ParseFidelity:
        """The fidelity level this parser naturally produces."""
        ...
```

### 4.2 Downstream Consumer Contract

Parse results feed into two downstream consumers: **structured extraction** and **chunking**. Both must work with output from any parser, not just LlamaParse.

**The resolution rule is simple: use the richest available representation, fall back to raw_text.**

```python
# backend/app/services/parse_content_resolver.py  (NEW FILE)

class ParseContentResolver:
    """Resolves the best content to use from a parse result for a given purpose.

    Downstream consumers call this instead of reaching into ParseResult fields directly.
    This isolates parser-specific knowledge to one place.
    """

    @staticmethod
    def get_text_for_extraction(parse_result: ParseResult) -> str:
        """Get the best text representation for structured extraction (LLM or rule-based).

        Extraction works best with markdown (tables are preserved), falls back to raw_text.
        """
        if parse_result.markdown:
            return parse_result.markdown
        return parse_result.raw_text

    @staticmethod
    def get_text_for_chunking(parse_result: ParseResult) -> str:
        """Get the best text representation for chunking.

        Chunking needs plain text with page markers for now (matches existing
        documents.extracted_text format). Markdown chunking is a future enhancement.
        """
        return parse_result.raw_text

    @staticmethod
    def get_pages(parse_result: ParseResult) -> list[dict] | None:
        """Get per-page content if available (any parser that provides it)."""
        return parse_result.pages

    @staticmethod
    def get_structure(parse_result: ParseResult) -> dict | None:
        """Get structured layout data. Caller must check parser_type to interpret."""
        return parse_result.document_structure
```

**Why this matters for future parsers:**
- **LandingAI** produces layout regions with bounding boxes but no markdown → extraction gets `raw_text`, structure is available for specialized table extractors
- **Reducto** produces high-fidelity markdown → extraction gets markdown, chunking gets text
- **Unstructured** produces elements with metadata → extraction gets markdown (if available) or text, structure has element types
- **Claude Vision** produces whatever the prompt asks for → adapter normalizes to `raw_text` + optionally `markdown`

The resolver is the **only place** that needs to change when a new parser's output is better suited to a specific consumer. The consumers themselves never check `parser_type`.

### 4.3 ExtractionService (Extraction Layer — parser-agnostic)

```python
# backend/app/services/extraction_service.py  (NEW FILE)

from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class ExtractionMethod(str, Enum):
    LLM = "llm"                     # Send parse result + schema to LLM
    RULE_BASED = "rule_based"       # Pattern matching on structured parse output
    VENDOR_BUNDLED = "vendor_bundled"  # Vendor did parse+extract in one shot


@dataclass
class ExtractionResult:
    """Schema-mapped data extracted from a parsed document.

    This is the purposeful interpretation layer — mapping the parser's
    description of the document to specific fields the user cares about.
    """
    structured_data: dict[str, Any]         # { "vendor_name": "Naivas", ... }
    source_parse_result_id: str             # Which parse result this came from (always set — vendor-bundled creates an opaque ParseResult)
    schema_id: str | None                   # Which schema was applied
    extraction_method: str                  # "llm" | "rule_based" | "vendor_bundled"
    confidence: dict[str, float] | None = None  # Per-field confidence (populated when vendor provides it, None otherwise — aspirational for LLM method)
    metadata: dict[str, Any] = field(default_factory=dict)       # Latency, cost, tokens


class ExtractionService:
    """Takes a parse result + a schema → structured data.

    Uses ParseContentResolver to get the best text from the parse result,
    regardless of which parser produced it. The extraction service never
    checks parser_type — it works with whatever text the resolver provides.

    For LLM extraction: sends resolved text + schema to an LLM.
    For rule-based: pattern matches on resolved text.
    For vendor-bundled: the adapter produced both ParseResult and ExtractionResult.
    """

    async def extract(
        self,
        parse_result: ParseResult,
        schema: dict[str, Any],
        method: ExtractionMethod = ExtractionMethod.LLM,
        config: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        # text = ParseContentResolver.get_text_for_extraction(parse_result)
        # → returns markdown if available, falls back to raw_text
        ...
```

### 4.4 LlamaParseAdapter — Actual SDK Integration (v1 parser)

```python
# backend/app/adapters/parsing/llamaparse.py

from llama_cloud import AsyncLlamaCloud
from app.ports.document_parsing import DocumentParser, ParseResult, ParserType, ParseFidelity

# LlamaParse v2 tiers and what they cost
LLAMAPARSE_TIERS = {
    "fast":             {"credits_per_page": 1,  "supports_markdown": False, "supports_items": False},
    "cost_effective":   {"credits_per_page": 3,  "supports_markdown": True,  "supports_items": True},
    "agentic":          {"credits_per_page": 10, "supports_markdown": True,  "supports_items": True},
    "agentic_plus":     {"credits_per_page": 45, "supports_markdown": True,  "supports_items": True},
}

# What the user can request as output
LLAMAPARSE_EXPAND_OPTIONS = ["text", "markdown", "items", "metadata"]
# "text"     → spatial text per page (always available, all tiers)
# "markdown" → markdown per page (NOT available on "fast" tier)
# "items"    → structured items: headings, tables, images with bboxes (NOT available on "fast" tier)
# "metadata" → per-page confidence scores, orientation, etc.


class LlamaParseAdapter(DocumentParser):
    """LlamaParse v2 adapter using the llama-cloud SDK.

    Lifecycle: upload file → create parse job → SDK polls internally → return results.
    The SDK's client.parsing.parse() handles the full lifecycle including polling.
    """

    def __init__(self, api_key: str | None = None):
        # Reads LLAMA_CLOUD_API_KEY from env if not provided
        self.client = AsyncLlamaCloud(api_key=api_key) if api_key else AsyncLlamaCloud()

    @property
    def parser_type(self) -> ParserType:
        return ParserType.LLAMAPARSE

    @property
    def default_fidelity(self) -> ParseFidelity:
        return ParseFidelity.MARKDOWN

    def supported_file_types(self) -> list[str]:
        return [
            "application/pdf",
            "image/jpeg", "image/png", "image/gif", "image/bmp", "image/tiff", "image/webp",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # pptx
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
        ]

    async def parse(self, file_path: str, config: dict | None = None) -> ParseResult:
        """Parse a document using LlamaParse v2 API.

        Config options (all optional, sensible defaults):
            tier: "fast" | "cost_effective" | "agentic" | "agentic_plus" (default: "agentic")
            expand: list of output types to request (default: ["markdown", "text"])
            version: API version pin (default: "latest")
            page_ranges: "1,3,5-10" (optional, parse specific pages only)
            output_options: dict passed to LlamaParse output_options (optional)
            processing_options: dict passed to LlamaParse processing_options (optional)
        """
        config = config or {}
        tier = config.get("tier", "agentic")
        version = config.get("version", "latest")

        # Determine expand based on tier capabilities
        requested_expand = config.get("expand", ["markdown", "text"])
        if tier == "fast":
            # Fast tier only supports "text" — silently drop unsupported options
            expand = ["text"]
        else:
            expand = [e for e in requested_expand if e in LLAMAPARSE_EXPAND_OPTIONS]

        # Step 1: Upload file to LlamaCloud
        with open(file_path, "rb") as f:
            file_obj = await self.client.files.create(file=f, purpose="parse")

        # Step 2: Create parse job — SDK handles polling internally and returns result
        parse_kwargs = {
            "file_id": file_obj.id,
            "tier": tier,
            "version": version,
            "expand": expand,
        }

        # Optional: page ranges
        if "page_ranges" in config:
            parse_kwargs["page_ranges"] = {"target_pages": config["page_ranges"]}

        # Optional: output_options (table formatting, image saving, etc.)
        if "output_options" in config:
            parse_kwargs["output_options"] = config["output_options"]

        # Optional: processing_options (OCR languages, chart parsing, etc.)
        if "processing_options" in config:
            parse_kwargs["processing_options"] = config["processing_options"]

        result = await self.client.parsing.parse(**parse_kwargs)

        # Step 3: Map LlamaParse response → our ParseResult

        # Build per-page content
        pages = []
        raw_text_parts = []
        markdown_parts = []

        if hasattr(result, "text") and result.text:
            for page in result.text.pages:
                page_data = {"page_number": page.page_number, "text": page.text}
                raw_text_parts.append(f"[Page {page.page_number}]\n{page.text}")
                pages.append(page_data)

        if hasattr(result, "markdown") and result.markdown:
            for page in result.markdown.pages:
                if page.success:
                    # Find matching page entry or create one
                    for p in pages:
                        if p["page_number"] == page.page_number:
                            p["markdown"] = page.markdown
                            break
                    markdown_parts.append(page.markdown)

        # Build document_structure from items (if requested and available)
        document_structure = None
        if hasattr(result, "items") and result.items:
            items = []
            for page in result.items.pages:
                if page.success:
                    for item in page.items:
                        items.append({
                            "type": item.type,          # "text", "heading", "table", "image", etc.
                            "value": getattr(item, "value", ""),
                            "md": getattr(item, "md", ""),
                            "page": page.page_number,
                            "bbox": item.bbox[0].__dict__ if getattr(item, "bbox", None) else None,
                            # Table-specific fields
                            "rows": getattr(item, "rows", None),
                            "csv": getattr(item, "csv", None),
                            "html": getattr(item, "html", None),
                        })
            document_structure = {"items": items}

        # Per-page metadata (confidence scores)
        if hasattr(result, "metadata") and result.metadata:
            for page_meta in result.metadata.pages:
                for p in pages:
                    if p["page_number"] == page_meta.page_number:
                        p["metadata"] = {
                            "confidence": page_meta.confidence,
                            "cost_optimized": page_meta.cost_optimized,
                        }

        # Determine fidelity
        if document_structure:
            fidelity = "layout_json"
        elif markdown_parts:
            fidelity = "markdown"
        else:
            fidelity = "text"

        raw_text = "\n\n".join(raw_text_parts) if raw_text_parts else ""
        full_markdown = "\n\n".join(markdown_parts) if markdown_parts else None

        return ParseResult(
            raw_text=raw_text,
            markdown=full_markdown,
            pages=pages if pages else None,
            document_structure=document_structure,
            fidelity=fidelity,
            parser_type="llamaparse",
            parser_config={"tier": tier, "expand": expand, "version": version},
            metadata={
                "llamaparse_job_id": result.job.id if hasattr(result, "job") else None,
                "page_count": len(pages),
                "credits_used": len(pages) * LLAMAPARSE_TIERS.get(tier, {}).get("credits_per_page", 0),
            },
        )
```

**Key SDK behaviors:**
- `client.parsing.parse()` is a **blocking call** — it uploads, creates the job, polls until complete, and returns the full result. No manual polling needed on our side.
- The `expand` parameter controls what data comes back. Only request what you need to save credits and latency.
- `fast` tier returns text only (spatial text). Requesting `markdown` or `items` on fast tier will error — the adapter silently filters these out.
- Per-page failures are returned inline (`success: false` with error string) rather than failing the whole job.
- File upload (`client.files.create`) and parsing are separate API calls but both happen inside `parse()`.

### 4.5 Interface Relationships

```
┌───────────────────────────────────────────────────────────────────┐
│ Existing (unchanged) — "Simple" parse option                      │
│                                                                   │
│   DocumentExtractor Protocol  →  LlamaIndexExtractor              │
│   (ports/document_processing.py)  (adapters/llamaindex/)          │
│   Returns: ExtractionResult (text + page_boundaries)              │
│   Writes to: documents.extracted_text                             │
│   Triggered when: user selects "Simple (local)" at upload         │
│                                                                   │
├───────────────────────────────────────────────────────────────────┤
│ New — Parsing Layer (parser-agnostic ABC)                         │
│                                                                   │
│   DocumentParser ABC  →  LlamaParseAdapter (v1)                   │
│   (ports/document_parsing.py)  future: LandingAI, Reducto, etc.  │
│   Returns: ParseResult (raw_text + optional markdown/structure)   │
│   Writes to: parse_results table                                  │
│   Also writes: documents.extracted_text (for chunking compat)     │
│   Triggered when: user selects a parser at upload or re-parse     │
│                                                                   │
├───────────────────────────────────────────────────────────────────┤
│ New — Content Resolver (isolates parser-specific knowledge)       │
│                                                                   │
│   ParseContentResolver                                            │
│   (services/parse_content_resolver.py)                            │
│   Picks best representation from ParseResult for each consumer:   │
│     get_text_for_extraction() → markdown || raw_text              │
│     get_text_for_chunking()   → raw_text (for now)                │
│   Downstream consumers never check parser_type directly.          │
│                                                                   │
├───────────────────────────────────────────────────────────────────┤
│ New — Extraction Layer (parser-agnostic)                          │
│                                                                   │
│   ExtractionService                                               │
│   (services/extraction_service.py)                                │
│   Input: ParseResult + schema → uses resolver to get best text    │
│   Returns: ExtractionResult (structured_data)                     │
│   Writes to: extraction_results table                             │
│   Works identically regardless of which parser produced the input │
└───────────────────────────────────────────────────────────────────┘
```

---

## 5. Database Changes (All Additive)

### `parse_results` table

A parser's description of a document.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| document_id | UUID FK → documents.id | CASCADE delete |
| parser_type | String(50) | "simple", "llamaparse", future: "landingai", "reducto", "unstructured", etc. |
| fidelity | String(20) | "text", "markdown", "layout_json" — describes richest available output |
| parser_config | JSON | Parser-specific config used (stored for reproducibility). Shape varies by parser. |
| raw_text | Text | Best-effort plain text (ALWAYS populated, every parser) |
| markdown | Text | Markdown representation (nullable — populated by parsers that support it) |
| pages | JSON | Per-page content (nullable). Common shape: `[{ "page_number": 1, "text": "...", "markdown": "..." }]` |
| document_structure | JSON | Structured layout data (nullable). Shape varies by parser — see ParseResult docs. |
| diagnostics | JSON | Auto-computed quality signals from raw_text (parser-agnostic) |
| metadata | JSON | Parser-specific execution metadata. Common: `latency_ms`, `page_count`, `token_count`. |
| status | Enum | pending / completed / failed |
| status_message | Text | Error details if failed |
| started_at | DateTime(tz) | Set when background task begins (used for stale job detection) |
| created_by | UUID FK → users.id | |
| created_at | DateTime(tz) | |
| updated_at | DateTime(tz) | Updated on status transitions |

Index: `(document_id, parser_type)`

### `extraction_results` table

Schema-mapped data extracted from a parse result.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| parse_result_id | UUID FK → parse_results.id | CASCADE delete, NOT NULL (vendor-bundled creates an opaque ParseResult) |
| document_id | UUID FK → documents.id | CASCADE delete |
| schema_name | String(100) | "receipt_v1", "reit_financials_v1" |
| schema_definition | JSON | The schema that was applied |
| extraction_method | String(30) | "llm", "rule_based", "vendor_bundled" |
| structured_data | JSON | { "vendor_name": "Naivas", ... } |
| confidence | JSON | Per-field confidence (nullable — populated when vendor provides it) |
| metadata | JSON | latency_ms, cost, tokens, model used |
| status | Enum | pending / completed / failed |
| status_message | Text | |
| started_at | DateTime(tz) | Set when background task begins |
| created_by | UUID FK → users.id | |
| created_at | DateTime(tz) | |
| updated_at | DateTime(tz) | Updated on status transitions |

Index: `(document_id, schema_name)`

### `extraction_ground_truth_sets` table

Collections of expected structured output for extraction evaluation.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| project_id | UUID FK → projects.id | CASCADE delete |
| name | String(255) | "Kenyan Receipts v1" |
| document_type | String(50) | "receipt", "financial_report" |
| schema_name | String(100) | Must match extraction_results.schema_name |
| schema_definition | JSON | Expected fields schema |
| description | Text | Optional |
| created_by | UUID FK → users.id | |
| created_at / updated_at | DateTime(tz) | |

### `extraction_ground_truth_items` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| ground_truth_set_id | UUID FK → extraction_ground_truth_sets.id | CASCADE delete |
| document_id | UUID FK → documents.id | CASCADE delete |
| expected_data | JSON | Expected structured output |
| annotations | JSON | quality, difficulty, language, notes |
| created_by | UUID FK → users.id | |
| created_at / updated_at | DateTime(tz) | |

Unique constraint: `(ground_truth_set_id, document_id)`

### `extraction_eval_results` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| eval_batch_id | UUID | Groups results from a single evaluation run |
| extraction_result_id | UUID FK → extraction_results.id | CASCADE delete |
| ground_truth_item_id | UUID FK → extraction_ground_truth_items.id | CASCADE delete |
| overall_score | Float | Weighted composite 0-1 |
| field_scores | JSON | Per-field breakdown |
| line_items_score | JSON | Precision, recall, F1 |
| evaluation_metadata | JSON | Metric versions, weights |
| created_at | DateTime(tz) | |

Unique constraint: `(extraction_result_id, ground_truth_item_id)`

### Schema Management (Week 1: Code-Defined Constants)

Extraction schemas (e.g., `receipt_v1`) are defined as Python dicts in `backend/app/schemas/extraction_schemas.py` — a single registry module. No `schemas` table in Week 1.

```python
# backend/app/schemas/extraction_schemas.py
EXTRACTION_SCHEMAS: dict[str, dict] = {
    "receipt_v1": {
        "version": "1",
        "fields": {
            "vendor_name": {"type": "string", "required": True},
            "date": {"type": "date", "required": True},
            "total": {"type": "number", "required": True},
            # ...
        }
    },
}
```

**Rules:**
- Schemas are versioned by name suffix (`_v1`, `_v2`). A new version is a new key — old versions are never mutated.
- `extraction_results.schema_definition` snapshots the schema dict at extraction time, so results remain interpretable even if the code-defined schema is later removed.
- `extraction_ground_truth_sets.schema_name` must reference a key in `EXTRACTION_SCHEMAS` — validated at creation time (not a DB FK, but checked in the service layer).
- `GET /extraction-schemas` reads from this registry, not a DB table.

**Week 3+ migration path:** If schema management becomes a user-facing need (custom schemas per project), promote to a DB table then.

### Background Job Status & Stale Job Policy

Parse and extraction operations run as `BackgroundTasks`. The frontend needs to know when they finish.

**Polling contract (Week 1 — simple):**
- Frontend polls `GET /parse-results/{id}` or `GET /extraction-results/{id}` every 3 seconds while `status == "pending"`.
- Stop polling after `status` changes to `completed` or `failed`, or after 5 minutes (treat as timeout, show error).
- The `status` field and `updated_at` timestamp are sufficient — no SSE or WebSocket in Week 1.

**Stale job reaper:**
- On each `GET /parse-results/{id}` or `GET /extraction-results/{id}` request, if `status == "pending"` and `started_at` is older than 10 minutes, the API automatically marks it `failed` with `status_message = "Timed out — background task did not complete within 10 minutes"`.
- This handles the case where a `BackgroundTasks` worker crashes silently.

**Week 3+ migration path:** Replace polling with SSE if latency matters.

### Vendor Error Handling (LlamaParse-specific)

**Timeouts:**
- The LlamaParse SDK's `client.parsing.parse()` is a blocking call that handles polling internally.
- LlamaParse has a server-side max job runtime of **30 minutes** (returns TIMEOUT status).
- We set a client-side timeout of **5 minutes** in the adapter (via `httpx` timeout on the SDK client). If exceeded, mark the parse_result as `failed`.
- The `agentic` tier averages ~45s per document; larger docs or `agentic_plus` can take 2-3 minutes.

**Error handling:**
- LlamaParse returns per-page errors inline (`success: false` with error string) rather than failing the whole job. The adapter stores these in the `pages` JSON — the frontend shows which pages failed.
- Full job failure (status `FAILED`) → mark parse_result as `failed`, store `result.job.error_message` in `status_message`.
- Network errors / SDK exceptions → 1 retry with 5s delay. If retry also fails → mark `failed`.
- 4xx from LlamaCloud (invalid tier, bad file, etc.) → no retry, mark `failed` immediately.

**Cost tracking:** Log `credits_used` in `metadata.credits_used` (calculated as `page_count * tier_credits_per_page`). No budget cap in Week 1. LlamaParse pricing: $1.25 per 1,000 credits (fast=1/page, cost_effective=3, agentic=10, agentic_plus=45).

**LlamaParse file cache:** LlamaParse caches parsed results for 48 hours. Re-parsing the same file with the same config will return cached results (no charge). To force re-parse, pass `disable_cache: true` in config.

---

## 6. Evaluation Strategy

### What We Evaluate at Each Layer

| Layer | What's evaluated | Ground truth needed | Week | Metrics |
|-------|-----------------|--------------------|----|---------|
| **Parse diagnostics** | "Did the parser produce something sane?" | **None** — heuristic checks | 1 | Non-empty, printable ratio, CID detection, page count, token plausibility |
| **Extraction accuracy** | "Did we get the right field values?" | Schema-mapped expected output (receipt labels) | 1 | Field exact/fuzzy match, numeric match, line items F1 |
| **Parse quality** (optional) | "How faithfully was text reproduced?" | Character-level text GT (small subset) | 3+ | CER, WER, ANLS |
| **Downstream retrieval** | "Does this parse→chunk→retrieve well?" | Existing retrieval golden sets | Already built | Precision@k, Recall@k |
| **Downstream answers** | "Does the full pipeline produce good answers?" | Existing answer eval | Already built | Faithfulness, relevance (LLM-as-judge) |

### Week 1: Extraction Evaluation (Primary)

The evaluation engine scores `extraction_results.structured_data` against `extraction_ground_truth_items.expected_data`:

| Metric | What It Measures | Implementation |
|--------|-----------------|----------------|
| **Field exact match** | Core fields correct? | Binary on vendor_name, date, total, payment_method |
| **Field fuzzy match** | Close but not exact? | `rapidfuzz.fuzz.ratio()` threshold ≥ 85 |
| **Numeric match** | Money amounts correct? | Exact with tolerance ±0.01 |
| **Line items F1** | Items captured? | Hungarian algorithm on (description, total) pairs (see cost function below) |
| **Overall doc score** | Single number | Weighted: 30% exact + 20% fuzzy + 25% numeric + 25% line_items |

**Line items matching — cost function:**
- For each (predicted, expected) line item pair, compute: `cost = 0.6 * (1 - fuzz.ratio(pred.description, exp.description) / 100) + 0.4 * (0 if abs(pred.total - exp.total) <= 0.01 else 1)`
- Pairs with `cost > 0.5` are treated as unmatched (threshold).
- `scipy.optimize.linear_sum_assignment` on the cost matrix gives optimal assignment.
- F1 computed from matched/unmatched counts: `precision = matched / predicted_count`, `recall = matched / expected_count`.

### Week 1: Parse Diagnostics (Free, No Ground Truth)

Auto-computed on every parse result. Stored in `parse_results.diagnostics`:

```json
{
  "non_empty": true,
  "char_count": 4523,
  "printable_ratio": 0.97,
  "suspected_cid": false,
  "page_count": 3,
  "token_count": 1200,
  "has_table_markers": true,
  "has_heading_markers": true,
  "empty_pages": []
}
```

These diagnostics catch the DigitalOcean AR case instantly: `printable_ratio: 0.02`, `suspected_cid: true`. No labeling required.

---

## 7. API Endpoints

### 7.1 Parsing

```
POST   /api/v1/documents/{document_id}/parse
       Body: {
         "parser_type": "llamaparse",
         "config": {
           "tier": "agentic",                        # fast | cost_effective | agentic | agentic_plus
           "expand": ["markdown", "text"],            # what output to request
           "version": "latest",                       # optional, default "latest"
           "page_ranges": "1-5",                      # optional, parse specific pages
           "output_options": { ... },                 # optional, LlamaParse output_options passthrough
           "processing_options": { ... }              # optional, LlamaParse processing_options passthrough
         }
       }
       Returns: 202 Accepted, { "parse_result_id": "uuid" }
       Note: This endpoint is used for re-parsing an existing document.
             Initial parse at upload time goes through the upload endpoint.

GET    /api/v1/documents/{document_id}/parse-results
       Query: ?parser_type=llamaparse (optional filter)
       Returns: List of parse results for this document (most recent first)

GET    /api/v1/parse-results/{result_id}
       Returns: Full parse result (raw_text, markdown, pages, document_structure, diagnostics)

GET    /api/v1/parsers
       Returns: Available parsers with their configuration schemas and supported file types.
       Each parser self-describes its options — the frontend renders config UI dynamically.
       Example response:
       [
         {
           "type": "simple",
           "label": "Simple (local)",
           "description": "Fast local text extraction. No AI, no cost.",
           "default_fidelity": "text",
           "config_schema": null,            # No config options
           "supported_types": ["application/pdf"]
         },
         {
           "type": "llamaparse",
           "label": "LlamaParse",
           "description": "AI-powered parsing with OCR, table detection, and layout analysis.",
           "default_fidelity": "markdown",
           "config_schema": {                # Drives dynamic config UI in frontend
             "tier": {
               "type": "select",
               "label": "Tier",
               "default": "agentic",
               "options": [
                 { "value": "fast", "label": "Fast", "description": "1 credit/page, text only" },
                 { "value": "cost_effective", "label": "Cost Effective", "description": "3 credits/page" },
                 { "value": "agentic", "label": "Agentic", "description": "10 credits/page" },
                 { "value": "agentic_plus", "label": "Agentic Plus", "description": "45 credits/page" }
               ]
             },
             "expand": {
               "type": "multiselect",
               "label": "Output",
               "default": ["text", "markdown"],
               "options": [
                 { "value": "text", "label": "Text", "always": true },
                 { "value": "markdown", "label": "Markdown", "requires_tier": ["cost_effective", "agentic", "agentic_plus"] },
                 { "value": "items", "label": "Structured Items", "requires_tier": ["cost_effective", "agentic", "agentic_plus"] },
                 { "value": "metadata", "label": "Page Metadata" }
               ]
             }
           },
           "supported_types": ["application/pdf", "image/jpeg", "image/png", ...]
         }
       ]

       When future parsers are added (e.g., LandingAI), they register with
       their own config_schema and the frontend renders their options automatically.
       No frontend changes needed to support a new parser's config UI.
```

### 7.1.1 Upload with Parse Options (Modified Existing Endpoint)

```
POST   /api/v1/documents
       FormData:
         project_id: UUID
         title: string
         description: string (optional)
         file: UploadFile
         parser_type: "simple" | "llamaparse"  (NEW, default: "simple")
         parse_config: JSON string             (NEW, optional)
           e.g.: '{"tier": "agentic", "expand": ["markdown", "text"]}'
       Returns: 202 Accepted, DocumentResponse
         (includes parse_result_id when parser_type != "simple")

       When parser_type = "simple": existing flow unchanged (LlamaIndexExtractor)
       When parser_type = "llamaparse": BackgroundTasks runs LlamaParseAdapter.parse()
         → creates parse_results record
         → also writes raw_text to documents.extracted_text for compatibility
```

### 7.2 Extraction

```
POST   /api/v1/extractions/run
       Body: {
         "parse_result_id": "uuid",          # OR document_id + parser for bundled
         "schema_name": "receipt_v1",
         "extraction_method": "llm",         # or "vendor_bundled"
         "config": { ... }
       }
       Returns: 202 Accepted, { "extraction_result_id": "uuid" }

POST   /api/v1/documents/{document_id}/parse-and-extract
       Body: {
         "parser_type": "llamaparse",
         "schema_name": "receipt_v1",
         "config": { ... }
       }
       Returns: 202, { "parse_result_id": "uuid", "extraction_result_id": "uuid" }

GET    /api/v1/documents/{document_id}/extraction-results
       Query: ?schema_name=receipt_v1

GET    /api/v1/extraction-results/{result_id}
```

### 7.3 Extraction Ground Truth

```
POST   /api/v1/projects/{project_id}/extraction-ground-truth-sets
GET    /api/v1/projects/{project_id}/extraction-ground-truth-sets
GET    /api/v1/extraction-ground-truth-sets/{set_id}
DELETE /api/v1/extraction-ground-truth-sets/{set_id}

POST   /api/v1/extraction-ground-truth-sets/{set_id}/items
POST   /api/v1/extraction-ground-truth-sets/{set_id}/items/bulk
GET    /api/v1/extraction-ground-truth-sets/{set_id}/items
PUT    /api/v1/extraction-ground-truth-items/{item_id}
DELETE /api/v1/extraction-ground-truth-items/{item_id}
```

### 7.4 Extraction Evaluation

```
POST   /api/v1/extraction-evaluations/run
       Body: {
         "ground_truth_set_id": "uuid",
         "parser_type": "llamaparse",
         "extraction_method": "vendor_bundled",
         "config": { ... }
       }
       Returns: 202 Accepted, { "eval_batch_id": "uuid" }
       (eval_batch_id groups all extraction_eval_results created by this run)

GET    /api/v1/extraction-evaluations/results
       Query: ?eval_batch_id=uuid (primary) OR ?ground_truth_set_id=uuid&parser_type=llamaparse

GET    /api/v1/extraction-eval-results/{result_id}
```

### 7.5 Schemas

```
GET    /api/v1/extraction-schemas
       Returns: Available schemas (receipt_v1, reit_financials_v1, etc.)

GET    /api/v1/extraction-schemas/{schema_name}
       Returns: Schema definition with field descriptions
```

---

## 8. Frontend

### 8.1 User Flow

1. **Upload with parse choice** → user selects file, chooses "Simple" or "LlamaParse" with tier/output options
2. **Wait for processing** → document shows "processing" status, frontend polls
3. **View parse results** → document detail page shows parsed content (text, markdown, structured items)
4. **See diagnostics** → quality signals (printable ratio, CID detection, per-page confidence)
5. **Re-parse** (optional) → from document detail, try different tier or output format
6. **Extract** → select a parse result + schema → run extraction → see structured fields
7. **Label ground truth** → extraction ground truth page (Week 2)
8. **Evaluate** → extraction evaluation dashboard (Week 2)

### 8.2 Upload Dialog: Parse Method Selector

The existing `DocumentUploadZone` gains a parse method section between the file drop zone and the Upload button:

```
┌──────────────────────────────────────────────────┐
│  📄 receipt-naivas.pdf  (1.2 MB)     [Remove]    │
├──────────────────────────────────────────────────┤
│  Title: [Naivas Supermarket Receipt      ]       │
│  Description: [                          ]       │
├──────────────────────────────────────────────────┤
│  Parse Method                                     │
│                                                   │
│  ○ Simple (local)          ● LlamaParse           │
│    Fast, free, text only     AI-powered, richer   │
│                                                   │
│  ┌─ LlamaParse Options ──────────────────────┐   │
│  │  Tier:   [ Agentic          ▼]            │   │
│  │          10 credits/page                   │   │
│  │                                            │   │
│  │  Output: ☑ Markdown  ☑ Text  ☐ Items      │   │
│  │          ☐ Page Metadata                   │   │
│  └────────────────────────────────────────────┘   │
│                                                   │
│  [ Upload Document ]                              │
└──────────────────────────────────────────────────┘
```

**Implementation notes:**
- Parse method defaults to "Simple" (no behavior change for existing users)
- Parser-specific options collapse/expand when a parser is selected
- **Config UI is driven by `config_schema` from `GET /parsers`** — the frontend renders `select`, `multiselect`, etc. based on the schema. When future parsers are added, their config appears automatically.
- Tier selector is a `<Select>` dropdown with credit cost shown (from schema options)
- Output options are checkboxes; "text" is always included (non-removable, `always: true`)
- Conditional disabling (e.g., fast tier → markdown grayed out) is driven by `requires_tier`
- Frontend sends `parser_type` and `parse_config` as additional form fields
- For image files (JPEG/PNG), "Simple" option is disabled (SimpleDirectoryReader can't handle images)

### 8.3 Document Detail: Parse Results Tab

The document detail page (currently `DocumentTextViewer` showing monospace extracted text) is extended with a tabbed view when parse results exist:

**When only simple parse exists** (no parse_results rows): current behavior unchanged — shows extracted text in monospace.

**When parse_results exist**: shows a `ParseResultViewer` component with **fidelity-driven tabs** — the tabs that appear depend on what the parse result contains, not which parser produced it:

- **Text tab** (always): raw text with `[Page N]` markers (same monospace view as current `DocumentTextViewer`)
- **Markdown tab** (if `parse_result.markdown` is non-null): rendered markdown using a markdown renderer — tables render as actual tables, headings render as headings. This is the hero feature. Works for any parser that produces markdown (LlamaParse, Reducto, Unstructured, etc.)
- **Structure tab** (if `parse_result.document_structure` is non-null): formatted JSON view of structured data. For LlamaParse items, could render typed items. For unknown parsers, shows raw JSON tree.
- **Diagnostics tab** (always): quality signals computed from raw_text (parser-agnostic) plus any parser-specific metadata (e.g., per-page confidence)
- **Config tab** (always): parser used, config options, execution metadata (latency, cost, etc.)

**Re-parse button**: "Parse again..." button on the detail page opens a small dialog to select different tier/options, creating a new parse_results row.

**Multiple parse results**: If a document has been parsed multiple times, show a dropdown to switch between results (e.g., "Agentic — Mar 17" vs "Fast — Mar 17").

### 8.4 Document Detail: Extraction Results Section

Below parse results, extraction results for this document:

- Schema used, extraction method, source parse result
- Structured data rendered as key-value pairs / table
- If ground truth exists, inline comparison (expected vs actual per field)

### 8.5 Extraction Ground Truth Page

**Route:** `/extraction-ground-truth`

- Ground truth sets list → create set (name, document_type, schema)
- Set detail → documents table with labeling status
- Editor → document preview (PDF/image) on left, JSON/form editor on right

### 8.6 Extraction Evaluation Dashboard

**Route:** `/extraction-evaluation`

- Config: select ground truth set + parser + extraction method
- Aggregate cards: Overall Score, Field Match %, Line Items F1, Docs Evaluated
- Per-document table (sortable, color-coded)
- Row expansion: per-field expected vs actual breakdown

### 8.7 Navigation Updates

```typescript
// Add to frontend/src/config/navigation.ts:
{ label: 'Extraction GT', href: '/extraction-ground-truth', icon: Target },
{ label: 'Extraction Eval', href: '/extraction-evaluation', icon: FlaskConical },
```

---

## 9. Ground Truth Schema (Receipts)

```json
{
  "expected_data": {
    "vendor_name": "Naivas Supermarket",
    "vendor_branch": "Westlands",
    "date": "2025-11-15",
    "time": "14:23",
    "currency": "KES",
    "line_items": [
      { "description": "Bread White 400g", "quantity": 1, "unit_price": 65.00, "total": 65.00 }
    ],
    "subtotal": 175.00,
    "tax": null,
    "total": 175.00,
    "payment_method": "M-Pesa",
    "payment_reference": "SHK7842931"
  },
  "annotations": {
    "quality": "clean",
    "difficulty": "easy",
    "language": "en",
    "is_scanned": true,
    "has_tables": false,
    "receipt_category": "supermarket",
    "notes": "Thermal paper, slightly faded at bottom"
  }
}
```

---

## 10. Task Breakdown (Week 1)

### Task 1: Upload Flow with Parse Method Selection (Day 1, ~2.5 hours)

**Objective:** Extend upload to accept images, add parse method selection at upload time.

**Backend files to modify:**
```
backend/app/config.py                           # ALLOWED_MIME_TYPES += image types, add LLAMA_CLOUD_API_KEY
backend/app/routers/documents.py                # Add parser_type and parse_config form fields
backend/app/services/document_service.py         # Route to simple vs llamaparse background task
```

**Frontend files to modify:**
```
frontend/src/components/documents/DocumentUploadZone.tsx   # Add parse method selector UI
frontend/src/api/documents.ts                               # Send parser_type + parse_config in FormData
frontend/src/types/parsing.ts                               # ParseMethod, LlamaParseConfig types (NEW)
```

**Changes to upload endpoint (`POST /documents`):**
- Add optional `parser_type` form field (default: `"simple"`)
- Add optional `parse_config` form field (JSON string)
- When `parser_type == "simple"`: existing flow, calls `process_document_extraction()` as today
- When `parser_type == "llamaparse"`: schedule `process_llamaparse()` background task instead
- Accept `ALLOWED_MIME_TYPES: ["application/pdf", "image/jpeg", "image/png"]`
- Images skip simple extraction (no SimpleDirectoryReader for images); must use LlamaParse

**Verification:**
- [ ] PDF upload with "Simple" works exactly as before
- [ ] PDF upload with "LlamaParse" creates parse_results record
- [ ] JPEG/PNG upload works (must select LlamaParse — simple is disabled for images)
- [ ] parse_config correctly passes tier/expand options through
- [ ] Frontend shows parse method selector in upload dialog

---

### Task 2: Database Schema (Day 1, ~2.5 hours)

**Objective:** Create the five new tables. Purely additive.

**Files to create:**
```
backend/app/models/parse_result.py
backend/app/models/extraction_result.py
backend/app/models/extraction_ground_truth.py
backend/app/models/extraction_eval_result.py
backend/app/models/__init__.py                   # Register new models
backend/app/schemas/parse_result.py
backend/app/schemas/extraction_result.py
backend/app/schemas/extraction_ground_truth.py
backend/app/schemas/extraction_eval_result.py
backend/app/repositories/parse_result_repository.py
backend/app/repositories/extraction_result_repository.py
backend/app/repositories/extraction_ground_truth_repository.py
backend/app/repositories/extraction_eval_repository.py
backend/alembic/versions/XXXXX_add_idp_tables.py
```

**Follow existing patterns from:** `models/golden_set.py`, `models/eval_run.py`, `repositories/golden_set_repository.py`

**Verification:**
- [ ] `uv run alembic upgrade head` succeeds
- [ ] `uv run alembic downgrade -1` succeeds
- [ ] All FK relationships and cascades correct
- [ ] No impact on existing tables

---

### Task 3: DocumentParser Interface + LlamaParse Adapter (Day 2, ~3 hours)

**Objective:** Create `DocumentParser` ABC, `ParseResult` dataclass, `LlamaParseAdapter` using the `llama-cloud` SDK.

**Files to create:**
```
backend/app/ports/document_parsing.py            # DocumentParser ABC, ParseResult, ParseFidelity, ParserType
backend/app/adapters/parsing/__init__.py
backend/app/adapters/parsing/llamaparse.py       # LlamaParseAdapter (see Section 4.3 for full implementation)
backend/app/adapters/parsing/registry.py         # get_parser(parser_type) → DocumentParser
backend/app/adapters/parsing/diagnostics.py      # Auto-computed parse quality signals
backend/app/dependencies/parsing.py              # FastAPI dependency injection for parsers
```

**Dependencies:** `uv add llama-cloud` (provides `AsyncLlamaCloud` client for file upload + parsing)

**LlamaParse SDK integration (see Section 4.3 for full code):**
1. `client.files.create(file=open(path, "rb"), purpose="parse")` → get `file_id`
2. `client.parsing.parse(file_id=file_id, tier=tier, version=version, expand=expand)` → returns result
3. The SDK call is blocking (handles polling internally) — can take 10-120s depending on doc size and tier
4. Map `result.text.pages`, `result.markdown.pages`, `result.items.pages` → our `ParseResult`

**`diagnostics.py`:** Compute from raw_text locally (no API calls):
- `non_empty`, `char_count`, `printable_ratio`, `suspected_cid`, `token_count`
- `has_table_markers` (from markdown), `has_heading_markers`
- `per_page_confidence` (from LlamaParse metadata, if requested)
- `empty_pages` (pages with empty text)

**Verification:**
- [ ] `LlamaParseAdapter.parse()` with `tier="agentic", expand=["markdown","text"]` returns markdown + text
- [ ] `LlamaParseAdapter.parse()` with `tier="fast", expand=["text"]` returns text only
- [ ] Requesting markdown on fast tier is silently filtered (no error)
- [ ] Items expand returns structured heading/table/image data with bboxes
- [ ] Diagnostics auto-populated on every parse result
- [ ] Missing `LLAMA_CLOUD_API_KEY` → clear error message, no crash
- [ ] Large document (>10 pages) completes within timeout

---

### Task 4: ExtractionService + Parsing/Extraction API Endpoints (Day 2-3, ~3 hours)

**Objective:** Service layer for extraction and REST APIs for both parsing and extraction.

**Files to create:**
```
backend/app/services/parsing_service.py          # Orchestrates parse runs
backend/app/services/extraction_service.py       # Orchestrates extraction (LLM or vendor-bundled)
backend/app/routers/parsing.py                   # Parse endpoints
backend/app/routers/extraction.py                # Extraction endpoints
backend/app/dependencies/parsing.py
backend/app/main.py                              # Register routers
```

**Background processing:** `BackgroundTasks` (same pattern as document upload)

**Verification:**
- [ ] `POST /documents/{id}/parse` returns 202
- [ ] `POST /documents/{id}/parse-and-extract` returns 202 with both IDs
- [ ] `GET /parse-results/{id}` returns full data with diagnostics
- [ ] `GET /extraction-results/{id}` returns structured data
- [ ] `GET /parsers` returns available parsers with fidelity info
- [ ] Auth + project scoping enforced

---

### Task 5: Extraction Ground Truth Service + API (Day 3, ~2 hours)

**Objective:** CRUD for extraction ground truth.

**Files to create:**
```
backend/app/services/extraction_ground_truth_service.py
backend/app/routers/extraction_ground_truth.py
```

**Follow patterns from:** `services/golden_set_service.py`, `routers/golden_sets.py`

**Verification:**
- [ ] Full CRUD works
- [ ] Bulk import accepts JSON array
- [ ] Unique constraint enforced
- [ ] Project scoping enforced

---

### Task 6: Extraction Evaluation Engine + Service (Day 3-4, ~3 hours)

**Objective:** Scoring engine for extraction results against ground truth.

**Files to create:**
```
backend/app/services/extraction_evaluation/__init__.py
backend/app/services/extraction_evaluation/engine.py         # Pure computation
backend/app/services/extraction_evaluation/field_matchers.py
backend/app/services/extraction_evaluation/line_item_matcher.py
backend/app/services/extraction_evaluation/service.py
backend/app/routers/extraction_evaluation.py
```

**Dependencies:** `uv add rapidfuzz scipy`

**The engine takes:** `extraction_result.structured_data` (dict) + `ground_truth_item.expected_data` (dict) → scores. No DB calls.

**Verification:**
- [ ] Field matching (exact, fuzzy, numeric) works
- [ ] Line items F1 via Hungarian algorithm works
- [ ] Overall weighted score correct
- [ ] API returns aggregate + per-document scores

---

### Task 7: Frontend — Parse Results Viewer + Re-parse (Day 4, ~3 hours)

**Objective:** Parse result viewer with tabs (text, markdown, items, diagnostics) on document detail page. Re-parse button.

**Files to create/modify:**
```
frontend/src/types/parsing.ts                               # ParseResult, ParseMethod, LlamaParseConfig types
frontend/src/types/extraction.ts
frontend/src/api/parsing.ts                                 # getParseResults, getParseResult, triggerParse, getParsers
frontend/src/api/extraction.ts
frontend/src/hooks/useParsing.ts                            # Manage parse results state, polling for pending results
frontend/src/components/parsing/ParseResultViewer.tsx        # Tabs: text, markdown, items, diagnostics, config
frontend/src/components/parsing/ReParseDialog.tsx            # Dialog to select tier/options and trigger re-parse
frontend/src/components/parsing/MarkdownRenderer.tsx         # Render markdown with table support
frontend/src/components/documents/DocumentTextViewer.tsx     # MODIFY: integrate ParseResultViewer when parse results exist
frontend/src/components/extraction/ExtractionResultView.tsx
frontend/src/pages/ProjectDocumentsPage.tsx                  # Integrate new sections
```

**Dependencies:** `npm install react-markdown remark-gfm` (for rendering markdown with GFM tables)

**Verification:**
- [ ] Document with simple parse shows current text viewer (unchanged)
- [ ] Document with LlamaParse result shows tabbed ParseResultViewer
- [ ] Markdown tab renders formatted markdown with proper tables
- [ ] Items tab shows structured headings/tables (if items expand was used)
- [ ] Diagnostics tab shows quality signals and per-page confidence
- [ ] "Parse again..." button opens dialog with tier/option selection
- [ ] Re-parse creates new result; dropdown switches between results
- [ ] Pending parse results poll and update when complete

---

### Task 8: Frontend — Extraction Ground Truth Page (MOVED TO WEEK 2)

Deferred to Week 2. Backend APIs (Task 5) ship in Week 1; ground truth can be created via API/curl for initial testing. The labeling UI is important but not on the critical path for proving the parse→extract→evaluate loop works.

---

### Task 9: Frontend — Extraction Evaluation Dashboard (MOVED TO WEEK 2)

Deferred to Week 2. Backend eval engine (Task 6) ships in Week 1; evaluation can be triggered and inspected via API. The dashboard is a display concern that doesn't block validating the scoring logic.

---

### Week 2 Tasks (deferred from Week 1)

**Task 8 (Week 2): Frontend — Extraction Ground Truth Page (~2 hours)**

**Files to create:**
```
frontend/src/types/extractionGroundTruth.ts
frontend/src/api/extractionGroundTruth.ts
frontend/src/hooks/useExtractionGroundTruth.ts
frontend/src/pages/ExtractionGroundTruthPage.tsx
frontend/src/components/extraction-ground-truth/GroundTruthSetList.tsx
frontend/src/components/extraction-ground-truth/GroundTruthEditor.tsx
frontend/src/config/navigation.ts
```

**Task 9 (Week 2): Frontend — Extraction Evaluation Dashboard (~3 hours)**

**Files to create:**
```
frontend/src/types/extractionEvaluation.ts
frontend/src/api/extractionEvaluation.ts
frontend/src/hooks/useExtractionEvaluation.ts
frontend/src/pages/ExtractionEvaluationPage.tsx
frontend/src/components/extraction-evaluation/EvalConfigPanel.tsx
frontend/src/components/extraction-evaluation/AggregateMetrics.tsx
frontend/src/components/extraction-evaluation/DocumentResultsTable.tsx
frontend/src/components/extraction-evaluation/FieldBreakdownView.tsx
frontend/src/config/navigation.ts
```

---

## 11. What This Spec Does NOT Change

| Existing Component | Status |
|--------------------|--------|
| `documents.extracted_text` column | **Unchanged** (LlamaParse also writes here for compat) |
| `documents.processing_metadata` column | **Unchanged** |
| `DocumentExtractor` Protocol | **Unchanged** |
| `LlamaIndexExtractor` adapter | **Unchanged** (used when parser_type="simple") |
| `process_document_extraction()` background task | **Unchanged** (called when parser_type="simple") |
| Chunking pipeline | **Unchanged** (reads `documents.extracted_text` regardless of parse method) |
| Existing `golden_sets` / `eval_runs` tables | **Unchanged** |
| Existing Evaluation page (retrieval eval) | **Unchanged** |

**Modified existing components:**
| Component | Change |
|-----------|--------|
| `POST /documents` upload endpoint | Adds optional `parser_type` and `parse_config` form fields |
| `DocumentUploadZone.tsx` | Adds parse method selector UI |
| `config.py` | Adds `LLAMA_CLOUD_API_KEY` setting, extends `ALLOWED_MIME_TYPES` |
| `DocumentTextViewer.tsx` | Conditionally shows `ParseResultViewer` when parse results exist |

---

## 12. Naming Clarity

To avoid confusion with existing evaluation infrastructure:

| Existing (retrieval evaluation) | New (extraction evaluation) |
|---|---|
| `golden_sets` table | `extraction_ground_truth_sets` table |
| `golden_set_queries` table | `extraction_ground_truth_items` table |
| `eval_runs` / `eval_run_results` tables | `extraction_eval_results` table |
| Query → relevant documents/pages | Document → expected structured output |
| Evaluates retrieval quality | Evaluates extraction accuracy |
| "Evaluation" nav item | "Extraction Eval" nav item |

---

## 13. Future Migration Path

### Week 3+: Unify `extracted_text` into `parse_results`

1. Create `PyMuPDFParser` adapter wrapping current `LlamaIndexExtractor`
2. For each existing document, create `parse_result` with `parser_type="pymupdf"`, `fidelity="text"`, `raw_text = document.extracted_text`
3. Add `is_default` flag to `parse_results`
4. Update chunking pipeline to read from default parse result
5. Add compatibility property on Document model
6. Eventually drop `extracted_text` column

### Week 2+: Parse-Level Comparison View

- Side-by-side view of multiple parse results for the same document
- Fidelity-aware rendering (text vs markdown vs layout JSON)
- Diagnostic comparison ("LlamaParse detected 3 tables, PyMuPDF detected 0")

### Week 3+: Parse Quality Evaluation (CER/WER)

- Add character-level ground truth for a small subset (8-10 receipts)
- CER/WER metrics for comparing OCR engines
- TEDS for table structure accuracy

### Adding a New Parser (the checklist)

When adding a parser (e.g., LandingAI, Reducto, Unstructured, Claude Vision):

1. **Create adapter** in `backend/app/adapters/parsing/{name}.py` implementing `DocumentParser` ABC
2. **Add enum value** to `ParserType` (string value is stored in DB — must be stable)
3. **Register in registry** (`adapters/parsing/registry.py`) with `config_schema` for `GET /parsers`
4. **Map output to ParseResult**: populate `raw_text` (required), plus `markdown`, `pages`, `document_structure` as available
5. **Update ParseContentResolver** if the new parser's output is better suited to extraction or chunking than the current fallback logic
6. **No frontend changes needed** for config UI (driven by `config_schema`). Tabs in `ParseResultViewer` appear automatically based on which ParseResult fields are non-null.
7. **Add config setting** for API key in `config.py` (e.g., `LANDINGAI_API_KEY`)

What you do NOT need to change: ExtractionService, chunking pipeline, parse_results table schema, evaluation engine, ground truth structure.

### Week 5+: Agentic Pipeline (LangGraph)

- Agent decides which parser based on document type and diagnostics
- Agent decides which extraction method based on parse fidelity
- The pipeline: classify → parse → verify_parse → extract → verify_extract

---

## 14. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `llama-cloud` package conflicts with existing `llama-index` | Medium | Medium | Test in dev first; same org, but different packages. Pin versions. |
| LlamaParse SDK blocking call takes too long (agentic: ~45s avg, agentic_plus: 2-3min) | High | Medium | 5-min client timeout; frontend shows "parsing..." status with elapsed time; user can cancel |
| LlamaParse returns per-page errors on complex docs | Medium | Low | Store per-page success/failure in `pages` JSON; frontend shows which pages succeeded vs failed |
| Fast tier doesn't support markdown — user confused by text-only output | Medium | Low | Frontend disables markdown/items checkboxes when fast tier selected; show tier capabilities in UI |
| Upload dialog complexity — parse options confuse users | Medium | Medium | Default to "Simple"; LlamaParse options collapsed until selected; good defaults (agentic + markdown) |
| Ground truth labeling slower than 15 min/receipt | Medium | Medium | Start with 15 receipts |
| Image upload with "Simple" parse fails (SimpleDirectoryReader doesn't support images) | Medium | Medium | Disable "Simple" option for image files in frontend; require LlamaParse for images |
| BackgroundTasks worker crashes leave jobs stuck in `pending` | Medium | Low | Stale job reaper marks pending jobs older than 10 min as failed on next GET |
| File storage not accessible across containers/restarts | Medium | High | Week 1 uses local disk with Docker volume mount (same as current PDF uploads); S3 is a Week 3+ concern |
| LlamaParse presigned URLs for images expire | Low | Low | Download and store images locally during parse if `images_to_save` is configured; Week 2+ concern |

---

## 15. LlamaParse SDK Quick Reference

Included here for implementation — this is the actual SDK surface we use.

### Installation & Auth
```python
# pip install llama-cloud (or uv add llama-cloud)
from llama_cloud import AsyncLlamaCloud
client = AsyncLlamaCloud()  # reads LLAMA_CLOUD_API_KEY from env
```

### Full Parse Lifecycle (one blocking call)
```python
# Step 1: Upload file
file_obj = await client.files.create(file=open("doc.pdf", "rb"), purpose="parse")

# Step 2: Parse (SDK handles polling, returns when complete)
result = await client.parsing.parse(
    file_id=file_obj.id,
    tier="agentic",                    # required: fast | cost_effective | agentic | agentic_plus
    version="latest",                   # required: "latest" or pinned date e.g. "2026-03-12"
    expand=["markdown", "text", "items", "metadata"],  # what to return
    # Optional:
    # page_ranges={"target_pages": "1,3,5-10"},
    # output_options={...},
    # processing_options={"ocr_parameters": {"languages": ["en"]}},
    # agentic_options={"custom_prompt": "..."},
    # disable_cache=False,
)
```

### Accessing Results
```python
# Text (always available, all tiers)
result.text.pages[0].text                    # per-page spatial text
result.text.pages[0].page_number             # 1-based

# Markdown (agentic/agentic_plus only, must be in expand)
result.markdown.pages[0].markdown            # per-page markdown
result.markdown.pages[0].success             # bool — some pages may fail

# Items (agentic/agentic_plus only, must be in expand)
result.items.pages[0].items                  # list of structured items
# Item types: text, heading, table, image, list, code, link, header, footer
# Tables have: rows (list[list[str]]), csv, html, md
# All items have: bbox (list of {h, w, x, y, confidence})

# Metadata (must be in expand)
result.metadata.pages[0].confidence          # 0-1 float
result.metadata.pages[0].cost_optimized      # bool

# Job info
result.job.id                                # job UUID
result.job.status                            # PENDING | RUNNING | COMPLETED | FAILED | CANCELLED
```

### Tiers

| Tier | Credits/page | Markdown | Items | Best for |
|------|-------------|----------|-------|----------|
| `fast` | 1 | No | No | Spatial text only, no AI |
| `cost_effective` | 3 | Yes | Yes | Text-heavy, minimal structure |
| `agentic` | 10 | Yes | Yes | Complex docs, images, diagrams |
| `agentic_plus` | 45 | Yes | Yes | Maximum fidelity, dense layouts |

Pricing: **$1.25 per 1,000 credits**. Cached results (48h) are free.

### Supported File Types
PDF, DOCX, PPTX, XLSX, JPG, PNG, GIF, BMP, TIFF, WEBP, HTML, RTF, EPUB, CSV, and many more.
Max file size: 300 MB. Max job runtime: 30 minutes.

### Key Constraints
- `fast` tier does NOT support markdown, items, or metadata expands
- Page numbering is 1-based (changed from v1's 0-based)
- Per-page text limit: 64 KB
- Per-page image limit: 35 images
- Presigned image URLs expire — download promptly if saving

---

## 16. Definition of Done

### Week 1 (core pipeline — must ship)

- [ ] Upload dialog shows parse method selector (Simple vs LlamaParse)
- [ ] LlamaParse tier selector (fast/cost_effective/agentic/agentic_plus) with credit cost
- [ ] LlamaParse output checkboxes (text/markdown/items/metadata)
- [ ] Image upload (JPEG/PNG) working — requires LlamaParse (Simple disabled for images)
- [ ] LlamaParse integration working end-to-end: upload → file.create → parsing.parse → store results
- [ ] Parse results viewable on document detail page with tabs (text, markdown, items, diagnostics)
- [ ] Markdown tab renders formatted markdown with proper tables
- [ ] Re-parse button on document detail page (try different tier/options)
- [ ] Parse diagnostics auto-computed (CID detection, printable ratio, per-page confidence)
- [ ] `documents.extracted_text` populated from LlamaParse raw_text (chunking compat)
- [ ] Extraction ground truth backend CRUD API working (no frontend UI yet)
- [ ] Extraction evaluation engine computing field-level and line-item metrics (API only)
- [ ] Polling-based status updates working in frontend (3s interval)
- [ ] Existing "Simple" upload flow unbroken
- [ ] 15 annotated Kenyan receipts with ground truth loaded via API

### Week 2 (frontend for eval — follows immediately)

- [ ] Extraction ground truth labeling UI (document preview + editor)
- [ ] Extraction evaluation dashboard with aggregate and per-document scores
- [ ] Remaining 10 annotated receipts (total: 25)
- [ ] Side-by-side parse result comparison (e.g., fast vs agentic for same document)
