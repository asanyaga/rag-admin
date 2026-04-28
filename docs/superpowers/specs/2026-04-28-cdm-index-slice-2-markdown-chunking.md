# CDM Index — Slice 2: Markdown Chunking

**Date:** 2026-04-28
**Master spec:** [CDM-Based Index Configuration](./2026-04-28-cdm-index-master-design.md)
**Depends on:** [Slice 1 — Foundation](./2026-04-28-cdm-index-slice-1-foundation.md)

---

## Scope

- `MarkdownChunkingService` — split `full_markdown` on heading boundaries
- `source_representation = "full_markdown"` + `chunking_strategy = "markdown_heading"` fully supported
- `heading_path` provenance in `chunk_metadata`
- UI: heading split level selector in adaptive form

---

## What this slice does NOT include

- Block-based chunking (Slice 3)
- Full citation with bboxes (Slice 3)
- Staleness indicators (Slice 4)

---

## Backend

### `MarkdownChunkingService`

New service in `app/services/markdown_chunking_service.py`.

**Algorithm:**

1. Parse markdown into sections by heading. A heading line (`#`, `##`, `###`, etc.) at or above `split_heading_level` closes the current section and starts a new one.
2. Each section = the heading line + all content until the next qualifying heading.
3. If a section exceeds `max_section_chars` (default: 4000 chars), fall back to `RecursiveCharacterTextSplitter` on that section's content. The resulting sub-chunks inherit the section's heading path.
4. Heading path is tracked as a stack: entering `## Financials > ### Q3` yields `["Financials", "Q3"]`.

**Config knobs:**

```python
split_heading_level: int = 2   # 1=h1 only, 2=h1+h2, 3=h1+h2+h3
max_section_chars: int = 4000  # fallback threshold
```

These are added to `IndexConfig` under the block-based config section:

```python
split_heading_level: int = Field(default=2, ge=1, le=3, alias="splitHeadingLevel")
max_section_chars: int = Field(default=4000, ge=500, le=16000, alias="maxSectionChars")
```

Only relevant when `chunking_strategy = "markdown_heading"`.

**Output:** `list[ChunkResult]` — same shape as `ChunkingService`. Provenance in `metadata`:

```json
{
  "start_char": 1200,
  "end_char": 1850,
  "heading_path": ["Financials", "Q3 Results"],
  "split_level": 2
}
```

### Processing service dispatch

```python
elif config.source_representation == "full_markdown":
    parsed_doc = await parse_run_repo.get_parsed_document(index_doc.parse_run_id)
    if not parsed_doc or not parsed_doc.full_markdown:
        raise ValueError("Parse run did not produce full_markdown")
    chunks = self.markdown_chunking_service.chunk_markdown(
        markdown=parsed_doc.full_markdown,
        config=config,
        source_document_id=str(doc_id),
        source_filename=document.source_metadata.get("filename"),
    )
```

`source_type` on stored chunks: `"full_markdown"`.

### Per-document validation

```python
if config.source_representation == "full_markdown":
    if not parsed_doc.full_markdown:
        raise ValueError(
            "Parse run did not produce full_markdown. "
            "Re-parse the document with a configuration that outputs markdown."
        )
```

---

## Frontend

### Adaptive form — markdown config panel

When `source_representation = "full_markdown"` is selected, replace the chunk size / overlap fields with:

- **Heading split level** — segmented control: `H1 only` / `H1 + H2` (default) / `H1 + H2 + H3`
- **Max section size** — slider (500–16,000 chars, default 4,000). Label: *"Sections larger than this are split further."*

Chunk size / overlap / unit fields are hidden.

---

## Tests

### Backend

- `test_markdown_chunking_splits_on_headings`: sections split at `##` boundaries, content stays with its heading
- `test_markdown_chunking_heading_path`: nested headings produce correct path stack
- `test_markdown_chunking_large_section_fallback`: section exceeding `max_section_chars` is recursively split; sub-chunks inherit heading path
- `test_markdown_chunking_no_headings`: document with no headings treated as single section (then fallback split if needed)
- `test_process_index_full_markdown`: chunks sourced from `full_markdown`, `source_type = "full_markdown"`, `heading_path` in metadata
- `test_full_markdown_missing_raises`: `ValueError` when parse run has no `full_markdown`

### Frontend

- Heading level selector renders when `full_markdown` selected
- Chunk size / overlap hidden when `full_markdown` selected

---

## E2E Validation Checklist

1. Parse a multi-section document (confirm `full_markdown` has headings)
2. Create an index with `source_representation = "full_markdown"`, `chunking_strategy = "markdown_heading"`
3. Process → verify chunks align with document sections
4. Verify `heading_path` in `chunk_metadata` matches document headings
5. Verify a section longer than `max_section_chars` produces multiple chunks, each with the same `heading_path`
6. Search the index — verify heading breadcrumb appears in results
