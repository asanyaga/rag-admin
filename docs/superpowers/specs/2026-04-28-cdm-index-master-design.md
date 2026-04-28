# CDM-Based Index Configuration — Master Design

**Date:** 2026-04-28
**Status:** Approved
**Slices:** [Slice 1 — Foundation](./2026-04-28-cdm-index-slice-1-foundation.md) · [Slice 2 — Markdown Chunking](./2026-04-28-cdm-index-slice-2-markdown-chunking.md) · [Slice 3 — Block Chunking + Citation](./2026-04-28-cdm-index-slice-3-block-chunking.md) · [Slice 4 — Staleness + Config UX](./2026-04-28-cdm-index-slice-4-staleness.md) · [Slice 5 — UI Polish](./2026-04-28-cdm-index-slice-5-ui-polish.md)

---

## Problem

The index pipeline currently sources document text from `document.extracted_text` — raw extracted content. This ignores the rich structured output produced by the CDM parse pipeline: semantic block roles, page layout, bounding boxes, markdown structure, and quality scores. The result is text-only chunking with no provenance, no structure-aware splitting, and no citation beyond character offsets.

---

## Goal

Make index configuration aware of CDM parse results so that:

1. Chunks can be sourced from CDM representations (`full_text`, `full_markdown`, `blocks`) rather than raw extracted text
2. Chunking strategy can exploit document structure (headings, semantic block roles, classification labels)
3. Every chunk carries provenance sufficient to reconstruct an exact citation — which block, which page, which bounding box, from which parse run
4. Downstream outputs (evals, retrieval logs, agent runs) are traceable to the exact index version and parse run that produced them, with staleness surfaced when the index changes

---

## Architecture

### Binding model

An index binds to parse runs at the **document level**, not the index level. Each document in an index has its own `parse_run_id` on the `index_documents` join table.

The index-level config constrains **which parse runs are eligible**: `parser` (e.g. `"llamaparse"`) and `parse_config_hash` ensure all documents in an index are processed with the same parser and parser configuration, guaranteeing consistent representation availability and fidelity.

### Versioning model

The index is mutable but versioned. Every successful reprocess increments `index.version` and writes an immutable `index_events` row capturing the config and document→parse_run bindings at that version.

Downstream outputs snapshot `(index_id, index_version, parse_run_id)` at creation time. Staleness is `output.index_version < index.version`, resolved at read time — no background jobs.

This is designed for migration toward full `IndexVersion` entities if A/B version querying is needed in future.

---

## Data Model

### `indexes` table — additions

| Column | Type | Description |
|---|---|---|
| `version` | `int NOT NULL DEFAULT 1` | Increments on every successful reprocess |
| `parser` | `varchar | NULL` | Constrains eligible parse runs (`"llamaparse"`, `"landing_ai"`, etc.) |
| `parse_config_hash` | `varchar | NULL` | Constrains eligible parse runs to a specific parser config |
| `config_dirty` | `bool NOT NULL DEFAULT false` | True when config has been changed since last reprocess |

### `index_documents` join table — additions

| Column | Type | Description |
|---|---|---|
| `parse_run_id` | `UUID | NULL` | FK → `parse_runs`. The specific parse run to use for this document. NULL = raw text mode |

### `chunks` table — additions

| Column | Type | Description |
|---|---|---|
| `index_version` | `int NOT NULL` | Index version that created this chunk |
| `parse_run_id` | `UUID | NULL` | Snapshot of the parse run that fed this chunk |
| `source_type` | `varchar NOT NULL` | `"raw_text"` \| `"full_text"` \| `"full_markdown"` \| `"block"` |

Block/text provenance is stored in the existing `chunk_metadata` JSON. The keys present depend on `source_type` — they do not coexist on the same chunk:

```json
// source_type = "raw_text" or "full_text"
{ "start_char": 1200, "end_char": 1850, "page_numbers": [3] }

// source_type = "full_markdown"
{ "start_char": 1200, "end_char": 1850, "heading_path": ["Financials", "Q3 Results"], "split_level": 2 }

// source_type = "block"
{
  "block_ids": ["uuid1", "uuid2"],
  "page_indices": [3, 4],
  "block_roles": ["HEADING", "PARAGRAPH"],
  "bboxes": [{"x0": 0.1, "y0": 0.2, "x1": 0.9, "y1": 0.35}]
}
```

### `index_events` table — new

Write-once. One row per successful reprocess. Enables reconstruction of "at version N, which parse run was used and what was the config?"

| Column | Type | Description |
|---|---|---|
| `id` | `UUID PK` | |
| `index_id` | `UUID FK` | → `indexes` |
| `version` | `int` | The version this event created |
| `config_snapshot` | `JSON` | `IndexConfig` frozen at this version |
| `document_bindings` | `JSON` | `{document_id: parse_run_id \| null}` map |
| `triggered_by` | `UUID FK` | → `users` |
| `created_at` | `datetime` | |

### Downstream output tables — pattern (not yet built)

Every future table (eval runs, retrieval logs, agent runs) stores these three fields at write time, never updated:

```python
index_id: UUID
index_version: int       # snapshot of index.version at time of run
parse_run_id: UUID | None  # snapshot of index.parse_run_id at time of run
```

---

## `IndexConfig` Schema

Replaces the `parsing_strategy: Literal["static"]` placeholder entirely.

### Parse source binding

```python
parser: str | None = None
# e.g. "llamaparse", "landing_ai". None = raw_text mode.
# Constrains which parse runs are eligible for documents in this index.

parse_config_hash: str | None = None
# Hash of the parser config. Auto-populated from the selected parse run.
# Ensures all documents use the same parser configuration and fidelity.

source_representation: Literal["raw_text", "full_text", "full_markdown", "block"] = "raw_text"
# raw_text     → document.extracted_text (unchanged behaviour)
# full_text    → parsed_document.full_text
# full_markdown → parsed_document.full_markdown
# block        → parsed_document.blocks
```

### Chunking strategy — expanded

```python
chunking_strategy: Literal[
    "fixed_size",           # raw_text, full_text only
    "recursive_character",  # raw_text, full_text only
    "markdown_heading",     # full_markdown only
    "block",                # block only
    "classified_block",     # block + classification labels (future)
]
```

Allowed combinations:

| `source_representation` | Allowed strategies |
|---|---|
| `raw_text` | `fixed_size`, `recursive_character` |
| `full_text` | `fixed_size`, `recursive_character` |
| `full_markdown` | `markdown_heading` |
| `block` | `block`, `classified_block` |

### Existing embedding config (retained unchanged)

```python
embedding_provider: str = "openai"
embedding_model: str = "text-embedding-3-small"
embedding_dimensions: int | None = None
```

These fields are present in the existing `IndexConfig` and are not modified by this feature. Changes to any of them are chunk-invalidating (existing chunks are incompatible with a different embedding model).

### Text-based config (unchanged, conditional)

```python
chunk_size: int = 512           # 100–8000
chunk_overlap: int = 50         # 0–chunk_size/2
chunk_unit: Literal["tokens", "characters"] = "characters"
```

Relevant only when `chunking_strategy` is `fixed_size` or `recursive_character`. Ignored silently otherwise.

### Markdown-based config (new, conditional)

```python
split_heading_level: int = 2    # 1=h1 only, 2=h1+h2, 3=h1+h2+h3
max_section_chars: int = 4000   # sections larger than this are recursively split
```

Relevant only when `chunking_strategy = "markdown_heading"`. Ignored silently otherwise.

### Block-based config (new, conditional)

```python
group_by_heading: bool = True
# TITLE/HEADING blocks anchor chunks; following PARAGRAPH/LIST/TABLE siblings merge in.

max_blocks_per_chunk: int = 10
# Safety cap. TABLE and FIGURE blocks are never split across chunks.

block_role_filter: list[str] | None = None
# None = all roles. e.g. ["TABLE"] indexes only table blocks.
# Values are BlockRole enum strings: TITLE, HEADING, PARAGRAPH, LIST, TABLE, FIGURE, etc.
```

### Classified block config (future-proofed)

```python
classification_labels: list[str] | None = None
# Groups blocks sharing a classification label into one chunk.
# Requires a future classification_run_id (TBD in classification design).
# Accepted by schema validator; processing raises NotImplementedError until built.
```

---

## Processing Service

### Dispatch

```
process_index()
  → load IndexConfig
  → if parse_run_id set on index_doc → load ParsedDocument
  → validate representation available in ParsedDocument
  → route to chunker:
      raw_text / full_text   → ChunkingService (existing)
      full_markdown          → MarkdownChunkingService
      block                  → BlockChunkingService
  → embed (unchanged)
  → store chunks with source_type, parse_run_id, index_version, provenance metadata
  → on full success: increment index.version, write index_events row, clear config_dirty
```

### Pre-process validation

Before processing starts (`start_processing()`), the service validates:
- If `source_representation != "raw_text"`, all pending documents must have `parse_run_id` set
- Raises `ValidationError` with clear message rather than failing per-document mid-run

### Per-document validation

At process time for each document, confirms the ParsedDocument contains the requested representation:
- `full_text` → `parsed_document.full_text` not null
- `full_markdown` → `parsed_document.full_markdown` not null
- `block` → `parsed_document.blocks` non-empty

Failure marks that document `failed` with a descriptive error; processing continues for remaining documents.

---

## Citation

Returned with every search result. Shape is uniform regardless of source type; fields are null when not applicable.

```python
class ChunkCitation(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    index_id: UUID
    index_version: int
    parse_run_id: UUID | None
    source_type: str

    # Text-based
    start_char: int | None
    end_char: int | None
    page_numbers: list[int]
    heading_path: list[str] | None      # markdown only

    # Block-based
    block_ids: list[str] | None
    page_indices: list[int] | None
    block_roles: list[str] | None
    bboxes: list[dict] | None           # [{x0,y0,x1,y1}] normalised 0..1
    confidence: float | None            # min quality score across blocks
```

Block fields resolved at query time: `block_ids → ParsedDocument.blocks` (single row fetch + in-memory filter). Degrades gracefully if parse run deleted — block fields return null.

---

## Staleness Model

### Index versioning

- `index.version` starts at 1, increments atomically with each successful reprocess
- Version increment and `index_events` write happen in the same transaction as the `ready` status update
- Downstream outputs only observe the new version once the full reprocess commits

### Staleness check

`is_stale = output.index_version < index.version` — computed at read time, no background job.

`stale_since_version` derived from `index_events`: first event with `version > output.index_version`.

### Config change flow (separate update and reprocess)

1. `PATCH /indexes/{id}/config` — stores updated config, sets `config_dirty = true`, returns impact summary (chunks count, downstream output count). Index stays `ready` and queryable with old chunks.
2. `POST /indexes/{id}/process` — explicit reprocess. Clears `config_dirty`, rebuilds chunks, increments `version`.

Config changes that invalidate chunks (`source_representation`, `chunking_strategy`, `parser`, `parse_config_hash`, embedding model/dimensions) trigger a `409 Conflict` that must be confirmed before being applied.

### Adding documents — parse run mismatch

If a document has no parse run matching `config.parser + config.parse_config_hash`, the API returns a structured error with `available_parse_runs` so the UI can offer a one-click parse action.

---

## UI Behaviour

### Index form — CDM mode (source_representation != raw_text)

1. Parser + config selector — dropdown of distinct `(parser, config_hash)` combinations with successful parse runs in the project, shown as human-readable labels
2. Source representation selector — shows availability badges per representation; auto-selects richest available
3. Chunking config — adaptive: text controls for text strategies, heading/block controls for structured strategies

### Staleness surfaces

- Index detail: `config_dirty` amber banner with reprocess call-to-action
- Index list: amber dot when `config_dirty = true`
- Downstream output rows: `IndexVersionBadge` — *"Index v3"* (current) or *"Index v1 · stale"* (amber, tooltip with reprocess date)
- Document list in index: parse run column showing parser + config + date; "Needs parsing" for missing runs

### Invariants the UI enforces

- Never auto-selects a parse run from a different parser or config hash than the index requires
- Blocks adding a document with no matching parse run — shows mismatch error inline
- Never triggers reprocess automatically on config change

---

## Future: Classified Block Chunking

When the classification pipeline lands, `classified_block` strategy will:
- Bind to a `classification_run_id` (analogous to `parse_run_id`) — exact binding mechanism TBD in classification design
- Group blocks sharing a classification label into one chunk, regardless of page boundary
- Require `parse_run_id` for citation (block text, bbox resolution)
- Surface `classification_labels` in the block config panel

The `classified_block` strategy value is accepted by the schema validator now so configs can be stored; processing raises `NotImplementedError` until built.

---

## Implementation Slices

| Slice | Scope | Validates |
|---|---|---|
| [1 — Foundation](./2026-04-28-cdm-index-slice-1-foundation.md) | Data model + `full_text` sourcing | CDM → index pipeline is wired |
| [2 — Markdown Chunking](./2026-04-28-cdm-index-slice-2-markdown-chunking.md) | `MarkdownChunkingService` + `markdown_heading` strategy | Dispatch pattern + markdown provenance |
| [3 — Block Chunking + Citation](./2026-04-28-cdm-index-slice-3-block-chunking.md) | `BlockChunkingService` + full citation | Highest-value CDM downstream validation |
| [4 — Staleness + Config UX](./2026-04-28-cdm-index-slice-4-staleness.md) | `config_dirty`, `PATCH /config`, staleness fields | Version tracking for downstream workloads |
| [5 — UI Polish](./2026-04-28-cdm-index-slice-5-ui-polish.md) | Parser+config selector, mismatch handling | Production-grade UX |
