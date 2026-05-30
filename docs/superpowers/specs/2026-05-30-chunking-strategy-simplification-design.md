# Chunking Strategy Simplification — Design Spec

**Date:** 2026-05-30
**Status:** Approved

---

## Problem

The index pipeline supports three CDM source representations (`full_text`, `full_markdown`, `block`) and five chunking strategies. `full_markdown` + `markdown_heading` is the most problematic path:

- `Page.start_char/end_char` in the CDM are character offsets into `parsed_document.full_text`, not into `parsed_document.full_markdown`. Applying those same page boundary offsets to the markdown string — a different, longer string — produces incorrect page attribution on markdown chunks.
- The markdown heading structure (`BlockRole.HEADING`, `depth`) is already first-class in the CDM block model. `markdown_heading` re-parses heading hierarchy from a flat string, discarding the richer block-level representation.
- LlamaParseand LandingAI emit element-level markdown captured per-block. The `full_markdown` flat string is a derived projection of that block structure, not the canonical representation.

`full_text` + text splitting strategies, by contrast, are architecturally sound and serve a legitimate pedagogical use case: demonstrating naive text chunking alongside semantic block chunking as a teaching contrast.

---

## Decision

Remove `full_markdown` and `markdown_heading`. Retain `full_text` + text splitting as the naive path and `block` as the semantic path.

The markdown-in-IDP concern (widely referenced in LlamaIndex/LangChain tutorials) is addressed by the CDM: markdown value (table structure in `block.markdown`, heading hierarchy in `block.role` and `block.depth`) is already captured at the block level. `full_markdown` chunking was a workaround for tools that output flat markdown without block structure; this project's CDM parsers are upstream of that pattern.

---

## Scope

### Removed

| Component | Detail |
|---|---|
| `MarkdownChunkingService` | `markdown_chunking_service.py` deleted entirely |
| `full_markdown` source representation | Removed from `IndexConfig`, `SourceResolutionService`, `IndexProcessingService` |
| `markdown_heading` chunking strategy | Removed from `IndexConfig` |
| `split_heading_level`, `max_section_chars` | Removed from `IndexConfig` |
| `full_markdown` dispatch branch | Removed from `ChunkingDispatcher` |
| `markdown_chunking_service` dep | Removed from `ChunkingDispatcher.__init__` |
| `full_markdown` heading breadcrumb | Removed from `CitationFooter.tsx` |
| Frontend toggle + config panel | `full_markdown` button and markdown config inputs removed from `CreateIndexPage.tsx` |

### Retained unchanged

| Component | Why |
|---|---|
| `full_text` + `{fixed_size, recursive_character}` | Pedagogically useful naive path; page_boundaries are correctly aligned (char offsets are into the same `full_text` string) |
| `_extract_page_boundaries()` | Still used by the `full_text` resolution path |
| `TextSource.page_boundaries` | Still populated for `full_text` chunks |
| `ChunkingService` | Serves the `full_text` path unchanged |
| `BlockChunkingService`, `BlocksSource` | Unchanged |
| `block` + `{block, classified_block}` | CDM semantic path, unchanged |

---

## Schema Changes

### Backend — `IndexConfig` (`schemas/index.py`)

```python
# source_representation
source_representation: Literal["full_text", "block"] = Field(
    default="full_text", alias="sourceRepresentation"
)

# chunking_strategy
chunking_strategy: Literal[
    "fixed_size",
    "recursive_character",
    "block",
    "classified_block",
] = Field(default="recursive_character", alias="chunkingStrategy")

# Removed fields
# split_heading_level  (was: alias="splitHeadingLevel")
# max_section_chars    (was: alias="maxSectionChars")
```

`validate_representation_and_strategy` model validator simplifies to:

```python
allowed = {
    "full_text": {"fixed_size", "recursive_character"},
    "block":     {"block", "classified_block"},
}
```

### Backend — `SourceResolutionService`

```python
SourceRepresentation = Literal["full_text", "block"]
```

`full_markdown` resolution branch removed. `full_text` and `block` branches unchanged.

### Frontend — `types/index.ts`

```ts
export type SourceRepresentation = 'full_text' | 'block'

export type ChunkingStrategy =
  | 'fixed_size'
  | 'recursive_character'
  | 'block'
  | 'classified_block'

// ChunkCitation.sourceType
sourceType: 'raw_text' | 'full_text' | 'block'
```

### Frontend — `lib/parsed-documents.ts`

```ts
// Before
representation?: 'full_text' | 'full_markdown' | 'block'

// After
representation?: 'full_text' | 'block'
```

This type is used as a query filter when fetching parsed documents for `ParsedDocumentPicker`.

---

## Pipeline Changes

### `ChunkingDispatcher`

```python
# Before
def dispatch(self, *, source, config, ...):
    if isinstance(source, TextSource):
        if config.source_representation == "full_markdown":
            return self.markdown_chunking_service.chunk_markdown(...)
        return self.chunking_service.chunk_text(...)
    ...

# After
def dispatch(self, *, source, config, ...):
    if isinstance(source, TextSource):
        return self.chunking_service.chunk_text(...)  # single path
    ...
```

Constructor no longer accepts or holds `markdown_chunking_service`.

### `IndexProcessingService`

```python
# Before
if config.source_representation in ("full_text", "full_markdown", "block"):

# After
if config.source_representation in ("full_text", "block"):
```

---

## Frontend Changes

### `CreateIndexPage.tsx`

- Remove `full_markdown` `ToggleGroupItem` from the source representation toggle group
- Remove the `full_markdown` conditional block rendering `split_heading_level` and `max_section_chars` inputs. Three-branch conditional (`full_markdown ? ... : block ? ... : text`) becomes two-branch (`block ? ... : text`)
- Remove `full_markdown → markdown_heading` auto-select in `handleSourceRepresentationChange`
- Remove `full_markdown` auto-downgrade in `handleParserFamilyChange`
- Default config remains `sourceRepresentation: 'full_text'`, `chunkingStrategy: 'recursive_character'`

### `CitationFooter.tsx`

Remove the `full_markdown` heading breadcrumb branch:

```tsx
// Remove entirely:
{citation.sourceType === 'full_markdown' && citation.headingPath?.length > 0 && (...)}
```

`heading_path` in chunk metadata was produced exclusively by `MarkdownChunkingService`. Block chunks carry `context_heading` in metadata but this is not surfaced in citation.

---

## Test Changes

### Deleted

- `backend/tests/services/test_markdown_chunking_service.py` — entire file
- `test_chunking_dispatcher.py`: `test_dispatch_text_source_full_markdown_routes_to_markdown_service`

### Updated

| File | Change |
|---|---|
| `test_chunking_dispatcher.py` | Remove `full_markdown` / `markdown_heading` config helper usage; `full_text` tests unchanged |
| `test_preview_chunks_router.py` | Any `full_markdown` / `markdown_heading` fixtures updated to `full_text` / `recursive_character` |
| `frontend/IndexDetailPage.test.tsx` | Fixture using `sourceRepresentation: 'full_markdown'` updated to `'full_text'` |
| `frontend/CitationFooter.test.tsx` | `full_markdown` sourceType test case removed |
| `frontend/ParsedDocumentPicker.test.tsx` | Fixtures using `representation: 'full_markdown'` updated to `'block'` |

---

## Out of Scope

- `raw_text` source representation (pre-CDM fallback, planned for when local parser matures)
- `classified_block` strategy implementation (accepted by schema, raises `NotImplementedError` until classification pipeline lands)
- SimpleTextAdapter improvements (one-block-per-page output is acceptable for its current placeholder role)
