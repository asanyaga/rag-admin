# CDM Index — Slice 1: Foundation (Data Model + `full_text` Sourcing)

**Date:** 2026-04-28
**Master spec:** [CDM-Based Index Configuration](./2026-04-28-cdm-index-master-design.md)
**Priority:** Validates CDM → index pipeline is wired before any new chunking logic lands

---

## Scope

- All data model changes: new columns on `indexes`, `index_documents`, `chunks`; new `index_events` table
- `IndexConfig` schema changes: add `parser`, `parse_config_hash`, `source_representation`; remove `parsing_strategy`
- Processing service: support `source_representation = "full_text"` (same chunker, text sourced from `parsed_document.full_text`)
- `AddDocumentsRequest`: add `parse_run_ids` map
- Version increment + `index_events` write on reprocess
- Basic UI: parse run selector on index form, parse run column on document list

---

## What this slice does NOT include

- `MarkdownChunkingService`, `BlockChunkingService` (Slices 2 + 3)
- Full citation schema (Slice 3)
- `config_dirty` / `PATCH /config` / staleness indicators (Slice 4)
- Parser + config selector dropdown, mismatch error handling (Slice 5)

---

## Backend

### Migration

```sql
-- indexes
ALTER TABLE indexes ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE indexes ADD COLUMN parser VARCHAR;
ALTER TABLE indexes ADD COLUMN parse_config_hash VARCHAR;
ALTER TABLE indexes ADD COLUMN config_dirty BOOLEAN NOT NULL DEFAULT false;

-- index_documents
ALTER TABLE index_documents ADD COLUMN parse_run_id UUID REFERENCES parse_runs(id) ON DELETE SET NULL;

-- chunks
ALTER TABLE chunks ADD COLUMN index_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE chunks ADD COLUMN parse_run_id UUID;
ALTER TABLE chunks ADD COLUMN source_type VARCHAR NOT NULL DEFAULT 'raw_text';

-- index_events (new table)
CREATE TABLE index_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    index_id UUID NOT NULL REFERENCES indexes(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    config_snapshot JSONB NOT NULL,
    document_bindings JSONB NOT NULL,
    triggered_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_index_events_index_id ON index_events(index_id);
CREATE INDEX ix_index_events_version ON index_events(index_id, version);
```

### ORM changes

**`Index` model** — add `version`, `parser`, `parse_config_hash`, `config_dirty`, and `index_events` relationship.

**`IndexDocument` model** — add `parse_run_id` column and `parse_run` relationship.

**`Chunk` model** — add `index_version`, `parse_run_id`, `source_type` columns.

**New `IndexEvent` model**:

```python
class IndexEvent(Base):
    __tablename__ = "index_events"
    id: Mapped[UUID]
    index_id: Mapped[UUID]       # FK → indexes
    version: Mapped[int]
    config_snapshot: Mapped[dict]
    document_bindings: Mapped[dict]  # {str(document_id): str(parse_run_id) | null}
    triggered_by: Mapped[UUID]
    created_at: Mapped[datetime]
```

### `IndexConfig` schema changes

Remove `parsing_strategy`. Add:

```python
parser: str | None = Field(default=None, alias="parser")
parse_config_hash: str | None = Field(default=None, alias="parseConfigHash")
source_representation: Literal["raw_text", "full_text", "full_markdown", "block"] = Field(
    default="raw_text", alias="sourceRepresentation"
)
chunking_strategy: Literal[
    "fixed_size", "recursive_character", "markdown_heading", "block", "classified_block"
] = Field(default="recursive_character", alias="chunkingStrategy")
```

Add validator: if `source_representation != "raw_text"`, `parser` must be set. If `chunking_strategy` in `["markdown_heading", "block", "classified_block"]` and `source_representation` is incompatible, raise `ValueError`.

### `AddDocumentsRequest` changes

```python
class AddDocumentsRequest(BaseModel):
    document_ids: list[UUID]
    parse_run_ids: dict[UUID, UUID] | None = Field(
        default=None, alias="parseRunIds"
    )
    # key: document_id, value: parse_run_id
    # Required for each document when index.config.source_representation != "raw_text"
```

### Processing service changes

**`start_processing()` — additional validation:**

```python
if config.source_representation != "raw_text":
    for index_doc in index.index_documents:
        if index_doc.processing_status == IndexDocumentStatus.pending:
            if not index_doc.parse_run_id:
                raise ValidationError(
                    f"Document {index_doc.document_id} has no parse run set. "
                    "All documents require a parse run when source_representation is not 'raw_text'."
                )
```

**`process_index()` — text sourcing dispatch:**

```python
# For each pending document:
if config.source_representation == "raw_text":
    text = document.extracted_text
elif config.source_representation == "full_text":
    parsed_doc = await parse_run_repo.get_parsed_document(index_doc.parse_run_id)
    if not parsed_doc or not parsed_doc.full_text:
        raise ValueError("Parse run did not produce full_text")
    text = parsed_doc.full_text
else:
    raise NotImplementedError(f"source_representation '{config.source_representation}' not yet supported")

chunks = self.chunking_service.chunk_text(text=text, config=config, ...)
```

**On successful reprocess — version increment and event write:**

```python
# In the same transaction as updating status to ready:
await self.index_repo.increment_version(index_id)
await self.index_repo.write_index_event(
    index_id=index_id,
    version=index.version + 1,
    config_snapshot=config.model_dump(mode="json"),
    document_bindings={
        str(doc.document_id): str(doc.parse_run_id) if doc.parse_run_id else None
        for doc in index.index_documents
    },
    triggered_by=user_id
)
```

**Chunk storage — add new fields:**

```python
chunk_data.append({
    ...existing fields...,
    "index_version": index.version + 1,   # the version being created
    "parse_run_id": str(index_doc.parse_run_id) if index_doc.parse_run_id else None,
    "source_type": config.source_representation,
})
```

### `IndexResponse` changes

Add `version: int` and `config_dirty: bool` to `IndexResponse`.

---

## API changes

### `GET /projects/{id}/parse-runs` — new endpoint (or reuse existing)

Returns parse runs available for documents in a project, grouped by `(parser, parse_config_hash)`. Used by the index form to populate the parser + config selector.

If this endpoint already exists on the document level (`GET /documents/{id}/parse-runs`), no new endpoint needed for Slice 1 — the UI can query per-document when adding documents to an index.

---

## Frontend

### Index form — parse run selector

When `source_representation != "raw_text"` is selected, show a **"Parse run"** field per document in the document picker. For Slice 1, this is a simple dropdown showing available parse runs for each document (parse run ID + parser name + created date). Auto-selects the latest run matching `config.parser` if set.

### Document list in index — parse run column

Add a **"Parse run"** column to the index document list showing:
- Parser name + config hash (truncated) + created date if bound
- "Raw text" if no parse run
- "Not set" if CDM mode and no parse run bound (amber)

### `IndexResponse` — surface version

Show `version` on the index detail page header (e.g. *"v1"* next to the index name). Small, informational.

---

## Tests

### Backend

- `test_index_config_validation`: `source_representation = "full_text"` requires `parser` set; incompatible `chunking_strategy` + `source_representation` combinations rejected
- `test_add_documents_with_parse_run`: `parse_run_ids` map persisted on `index_documents`
- `test_start_processing_validates_parse_runs`: `ValidationError` when CDM mode and document has no `parse_run_id`
- `test_process_index_full_text`: chunks sourced from `parsed_document.full_text`, not `document.extracted_text`
- `test_reprocess_increments_version`: `index.version` incremented, `index_events` row written with correct snapshot
- `test_chunk_has_provenance_fields`: `source_type`, `parse_run_id`, `index_version` populated on chunks

### Frontend

- Index form: parse run selector renders when CDM mode selected
- Document list: parse run column renders with correct values
- `IndexResponse` version field displayed

---

## E2E Validation Checklist

1. Create a document → run a LlamaParse parse → confirm `ParsedDocument.full_text` is populated
2. Create an index with `source_representation = "full_text"`, `parser = "llamaparse"`, add document with parse run
3. Trigger processing → verify chunks reference `source_type = "full_text"` and `parse_run_id` matches
4. Verify chunk text differs from `document.extracted_text` when `full_text` is richer/cleaner
5. Reprocess → verify `index.version` incremented to 2 → verify `index_events` has two rows
6. Verify `index_events` row for v2 has correct `config_snapshot` and `document_bindings`
