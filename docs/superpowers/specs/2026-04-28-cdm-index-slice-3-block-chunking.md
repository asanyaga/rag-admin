# CDM Index — Slice 3: Block Chunking + Citation

**Date:** 2026-04-28
**Master spec:** [CDM-Based Index Configuration](./2026-04-28-cdm-index-master-design.md)
**Depends on:** [Slice 1 — Foundation](./2026-04-28-cdm-index-slice-1-foundation.md)

---

## Scope

- `BlockChunkingService` — group CDM blocks into chunks by semantic role
- `source_representation = "block"` + `chunking_strategy = "block"` fully supported
- Block provenance in `chunk_metadata`: `block_ids`, `page_indices`, `block_roles`, `bboxes`
- `ChunkCitation` response schema — uniform citation for all source types
- Citation resolution at query time: `block_ids → ParsedDocument.blocks`
- UI: block config panel (grouping toggle, max blocks, role filter)

---

## What this slice does NOT include

- `classified_block` strategy (deferred — requires classification pipeline)
- Staleness indicators (Slice 4)
- Parser + config selector UX (Slice 5)

---

## Backend

### `BlockChunkingService`

New service in `app/services/block_chunking_service.py`.

**Input:** `list[Block]` from `ParsedDocument.blocks`, `IndexConfig`.

**Grouping algorithm:**

1. Sort blocks by `(page_index, bbox.y0)` — document reading order.
2. Apply `block_role_filter`: skip blocks whose `role` is not in the filter (if filter is set).
3. Iterate blocks:
   - A `TITLE` or `HEADING` block opens a new group. If a group is currently open, close it first.
   - `PARAGRAPH`, `LIST`, `CAPTION`, `CODE`, `FORMULA` blocks append to the current group.
   - `TABLE` and `FIGURE` blocks: if `group_by_heading = True` and a group is open, append. Otherwise start and immediately close their own single-block group. **Never split a TABLE or FIGURE across groups regardless of `max_blocks_per_chunk`.**
   - `HEADER`, `FOOTER`, `MARGINALIA` blocks are skipped entirely — they are layout artifacts, not content.
4. If appending would exceed `max_blocks_per_chunk`, close the current group and open a new one. The new group inherits a synthetic context block: the last seen `TITLE`/`HEADING` text is prepended as `[context: <heading text>]` so retrieval has heading context even for continuation chunks.
5. After all blocks are processed, close any open group.
6. If no `TITLE`/`HEADING` is ever encountered, all blocks form one group (subject to `max_blocks_per_chunk` splitting).

**Output:** `list[ChunkResult]`. Content = concatenated block texts with `\n\n` separator. Provenance in `metadata`:

```json
{
  "block_ids": ["uuid1", "uuid2", "uuid3"],
  "page_indices": [3, 4],
  "block_roles": ["HEADING", "PARAGRAPH", "PARAGRAPH"],
  "bboxes": [
    {"x0": 0.1, "y0": 0.05, "x1": 0.9, "y1": 0.12},
    {"x0": 0.1, "y0": 0.14, "x1": 0.9, "y1": 0.45},
    {"x0": 0.1, "y0": 0.47, "x1": 0.9, "y1": 0.71}
  ],
  "context_heading": "Q3 Financial Results"   // set on continuation chunks only
}
```

`bboxes` is null per-block when `block.bbox` is null.

### `IndexConfig` — block config fields (already in Slice 1 schema, activated here)

```python
group_by_heading: bool = Field(default=True, alias="groupByHeading")
max_blocks_per_chunk: int = Field(default=10, ge=1, le=50, alias="maxBlocksPerChunk")
block_role_filter: list[str] | None = Field(default=None, alias="blockRoleFilter")
```

### Processing service dispatch

```python
elif config.source_representation == "block":
    parsed_doc = await parse_run_repo.get_parsed_document(index_doc.parse_run_id)
    if not parsed_doc:
        raise ValueError("Parse run has no parsed document")
    cdm = ParsedDocument.model_validate(parsed_doc.content)
    if not cdm.blocks:
        raise ValueError("Parse run produced no blocks")
    chunks = self.block_chunking_service.chunk_blocks(
        blocks=cdm.blocks,
        config=config,
        source_document_id=str(doc_id),
        source_filename=document.source_metadata.get("filename"),
    )
```

`source_type` on stored chunks: `"block"`.

### `ChunkCitation` schema

New schema in `app/schemas/index.py`. Returned as part of search results.

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
    start_char: int | None = None
    end_char: int | None = None
    page_numbers: list[int] = Field(default_factory=list)
    heading_path: list[str] | None = None

    # Block-based
    block_ids: list[str] | None = None
    page_indices: list[int] | None = None
    block_roles: list[str] | None = None
    bboxes: list[dict] | None = None
    confidence: float | None = None

    model_config = ConfigDict(populate_by_name=True)
```

### Citation resolution

At query time, when assembling search results:

```python
async def resolve_citation(chunk: Chunk, session: AsyncSession) -> ChunkCitation:
    meta = chunk.chunk_metadata

    base = ChunkCitation(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        document_title=...,
        index_id=chunk.index_id,
        index_version=chunk.index_version,
        parse_run_id=chunk.parse_run_id,
        source_type=chunk.source_type,
        start_char=meta.get("start_char"),
        end_char=meta.get("end_char"),
        page_numbers=meta.get("page_numbers", []),
        heading_path=meta.get("heading_path"),
    )

    if chunk.source_type == "block" and meta.get("block_ids") and chunk.parse_run_id:
        parsed_doc_row = await parse_run_repo.get_parsed_document(chunk.parse_run_id)
        if parsed_doc_row:
            cdm = ParsedDocument.model_validate(parsed_doc_row.content)
            block_map = {b.id: b for b in cdm.blocks}
            blocks = [block_map[bid] for bid in meta["block_ids"] if bid in block_map]
            base.block_ids = meta["block_ids"]
            base.page_indices = list({b.page_index for b in blocks})
            base.block_roles = [b.role.value for b in blocks]
            base.bboxes = [
                {"x0": b.bbox.x0, "y0": b.bbox.y0, "x1": b.bbox.x1, "y1": b.bbox.y1}
                if b.bbox else None
                for b in blocks
            ]
            confidences = [b.quality.confidence for b in blocks if b.quality and b.quality.confidence]
            base.confidence = min(confidences) if confidences else None

    return base
```

Degrades gracefully: if `parsed_doc_row` is None (parse run deleted), block fields stay null.

---

## Frontend

### Adaptive form — block config panel

When `source_representation = "block"` is selected, show:

- **Group by heading** — toggle (default on). Label: *"Attach paragraphs and tables to their preceding heading."*
- **Max blocks per chunk** — number input (1–50, default 10). Label: *"Maximum blocks per chunk. Large sections are split and the heading is repeated for context."*
- **Block role filter** — multi-select combobox. Options: all `BlockRole` values. Placeholder: *"All block types (default)"*. Selecting roles limits indexing to those types only.

Chunk size / overlap / unit fields hidden.

### Search results — citation display

Each result card gains a citation footer:

- **Block-based**: `Page {n} · {role}` (e.g. *"Page 4 · Table"*). If `bboxes` present, show a small PDF location indicator. If `confidence` present and < 0.7, show a *"Low confidence"* amber tag.
- **Markdown-based**: heading breadcrumb from `heading_path` (e.g. *"Financials > Q3 Results"*).
- **Text-based**: *"Page {n}"* from `page_numbers`, or character range if no page info.
- All types: small *"Index v{n}"* label (will become stale indicator in Slice 4).

---

## Tests

### Backend — `BlockChunkingService`

- `test_block_chunking_groups_by_heading`: HEADING + following PARAGRAPHs form one chunk
- `test_block_chunking_table_not_split`: TABLE block always forms its own group when `max_blocks_per_chunk` would split it
- `test_block_chunking_max_blocks_cap`: group split at `max_blocks_per_chunk`; continuation chunk has `context_heading`
- `test_block_chunking_role_filter`: blocks with roles not in `block_role_filter` are skipped
- `test_block_chunking_skip_layout_blocks`: HEADER/FOOTER/MARGINALIA blocks not present in any chunk
- `test_block_chunking_no_headings`: all content blocks grouped together (subject to max cap)
- `test_block_chunking_provenance`: `block_ids`, `page_indices`, `block_roles`, `bboxes` populated correctly

### Backend — citation

- `test_citation_resolution_block`: `block_ids` resolve to correct pages, roles, bboxes from ParsedDocument
- `test_citation_resolution_missing_parse_run`: block fields null when parse run deleted, no exception
- `test_citation_resolution_text`: `start_char`/`end_char`/`page_numbers` populated for text-based chunks
- `test_citation_confidence_min_score`: `confidence` is minimum across all blocks in chunk

### Frontend

- Block config panel renders when `block` strategy selected
- Citation footer shows page + role for block chunks
- Low confidence tag shown when `confidence < 0.7`

---

## E2E Validation Checklist

1. Parse a structured document (confirm `ParsedDocument.blocks` is populated with varied roles)
2. Create an index with `source_representation = "block"`, `chunking_strategy = "block"`, `group_by_heading = true`
3. Process → verify chunks group heading + following content correctly
4. Verify TABLE block in document produces its own chunk and is not split
5. Query the index → verify citation includes `block_ids`, `page_indices`, `bboxes`
6. Open the source document and confirm cited block locations visually match query results
7. Delete the parse run → re-query → verify citation degrades gracefully (block fields null, no error)
8. Create a second index with `block_role_filter = ["TABLE"]` → verify only table blocks are indexed
