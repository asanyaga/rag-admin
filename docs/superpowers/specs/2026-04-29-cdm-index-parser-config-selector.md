# CDM Index — Parsed-Document Selector

**Date:** 2026-04-29 (revised 2026-04-30)
**Master spec:** [CDM-Based Index Configuration](./2026-04-28-cdm-index-master-design.md)
**Extracted from:** [Slice 5 UI Polish](./2026-04-28-cdm-index-slice-5-ui-polish.md)
**Depends on:** Slices 1–2 (foundation + markdown chunking)

---

## Implementation roadmap

The work is split into six units. Each unit is its own branch, PR, and plan
document under `docs/superpowers/plans/`. Status of each as of 2026-04-30:

| Unit | Scope | Status | PR | Plan |
|---|---|---|---|---|
| **1** | Parsed-doc read APIs + ORM tighten (`index_documents.parse_run_id` FK CASCADE, `IndexDocument.parsed_document` relationship, `GET /parse-runs/configs`, `GET /parsed-documents`) | ✅ Shipped | [#47](https://github.com/asanyaga/rag-admin/pull/47) | [Unit 1 plan](../plans/2026-04-30-cdm-index-parsed-doc-unit-1-foundation.md) |
| **2** | Source-resolution seam (`SourceResolutionService` + `ChunkingDispatcher`) + chunk preview fix (un-bandaid `2a0cfa1`) | ✅ Shipped | [#49](https://github.com/asanyaga/rag-admin/pull/49) | [Unit 2 plan](../plans/2026-04-30-cdm-index-parsed-doc-unit-2-source-resolution-seam.md) |
| **3** | `IndexCreate.parsed_document_ids` shape, `IndexConfig` validators, drop `raw_text`, route renames, cascade-delete legacy raw_text indexes | ✅ Shipped | merged locally `08dca24` (issue [#50](https://github.com/asanyaga/rag-admin/issues/50)) | [Unit 3 plan](../plans/2026-04-30-cdm-index-parsed-doc-unit-3-shape-tightening.md) |
| **4** | Wizard rebuild — parse-config family selector (Step 2) + parsed-doc picker (Step 4); replaces the wide-net resolver bridge from Unit 3 | ⏳ Pending | — | — |
| **5** | Index detail "Documents" tab → "Parsed Documents" with the new column shape (Source filename / Parse run / Parsed at / Status / Chunks); restores the `Add Documents` flow on the index detail page | ⏳ Pending | — | — |
| **6** | Cleanup — `ALTER COLUMN index_documents.parse_run_id SET NOT NULL`; consider dropping denormalized `index_documents.document_id`; optionally implement block chunking and remove the `ChunkingDispatcher.NotImplementedError` | ⏳ Pending | — | — |

### Standing bridges (removed in later units)

- **Wide-net wizard resolver** (`frontend/src/lib/parsed-documents.ts::resolveLatestParsedDocsForDocuments`) — Unit 3 ships this client-side helper to keep the slice-2 document picker working with the new `parsed_document_ids` API. Removed by Unit 4 once the explicit parsed-doc picker lands.
- **`IndexDetailPage` "Add Documents" toast stub** — Unit 3 reduces the legacy bulk-add UI to a toast pointing at Unit 4/5. Replaced by Unit 5's parsed-doc picker for that page.
- **`block` chunking `NotImplementedError`** — `ChunkingDispatcher` accepts `BlocksSource` but raises until a future unit implements block chunking. Tracked as Unit 6 cleanup work.

---

## Problem

Indexes today are built around `Document` + `extracted_text`. The CDM model introduces `ParsedDocument` as the actual unit of indexable content — every parse run produces one, and every `ParsedDocument` carries `full_text` (always), `full_markdown` (sometimes), and `blocks` (≥1) along with its own `parse_run_id`, `parser`, and `parse_config_hash`. The Index feature has not yet been re-centered on this unit.

The two specific gaps:

1. **No way to choose which `ParsedDocument` an index reads.** Multiple parse runs can target the same source document with the same `(parser, parse_config_hash)` family — and because parse runs are **not deterministic** (LLM-driven layout, OCR variation), they can produce different `ParsedDocument` outputs. This app exists as a visual prototyping/debugging tool; the user must be able to pin a specific parse output and see how it propagates through chunking, embedding, and retrieval. "Latest run" is a useful default, not a model rule.

2. **No selector for the parse-config family.** The wizard cannot express "build this index off LlamaParse/premium output" before listing parsed-documents.

This spec re-centers the Index feature on `ParsedDocument`:

- A parse-config family selector for the project (`parser` + `parse_config_hash`).
- A parsed-document picker scoped to that family, defaulting to "latest per source document," with the override toggle that surfaces older runs in the same family.
- A request shape that submits `parsed_document_ids` directly. No more parallel `document_ids` + `parse_run_ids`; no per-row binding object.
- Server-side validation that every chosen parsed-doc belongs to the declared family and has the segment named by `IndexConfig.source_representation` populated.
- A chunk-preview path that resolves source from a `parsed_document_id` instead of reading `document.extracted_text`.

This is an **evolution from the document-centric implementation**, not a layered feature. Existing `IndexCreate` / `AddDocumentsRequest` shapes change; legacy `index_documents` rows that pre-date CDM are migrated where possible and cascade-deleted otherwise.

---

## Background: data model

```
Project
  └─ ParseRuns               (filterable by parser + parse_config_hash)
       └─ ParsedDocuments    ← unit of selection
            └─ {full_text (always), full_markdown (optional), blocks (≥1)}
```

Invariants going forward:
- Every successful `ParseRun` produces exactly one `ParsedDocument`.
- `ParsedDocument.full_text` is always non-null.
- `len(ParsedDocument.blocks) ≥ 1`.
- `ParsedDocument.full_markdown` is optional — populated when the parse config produced markdown output.

A **parse-config family** is `(parser, parse_config_hash)`. Within a family, multiple runs can target the same source document and may diverge.

---

## Backend

### 1. `GET /projects/{projectId}/parse-runs/configs`

Returns distinct `(parser, parse_config_hash)` combinations that have at least one successful parse run for any document in the project. Locating this under `/parse-runs/configs` makes it explicit that this is a derived projection of parse-runs scoped to the project, not a first-class "parse-config" resource.

**Response:** `list[ParseConfigOption]`

```python
class ParseConfigOption(BaseModel):
    parser: str                         # "llamaparse", "landingai"
    parse_config_hash: str              # hex SHA-256 of the config dict
    config: dict[str, Any]              # actual config dict (for label derivation)
    parsed_document_count: int          # parsed-docs in this family across the project
    has_full_markdown: bool             # ≥1 parsed-doc in this family has full_markdown
    latest_parsed_at: datetime          # newest parse_run finished_at in this family
```

Notes:
- `has_full_text` is omitted — it's tautologically true under the invariants above.
- `representation_kind` is omitted — what matters for the index UI is which segments are populated on the `ParsedDocument`s, not the parser's intent.

The query joins `parsed_documents → parse_runs → source_documents → documents` filtered by `project_id` and `parse_runs.status = 'succeeded'`. Groups by `(parser, parse_config_hash)`.

### 2. `GET /projects/{projectId}/parsed-documents`

Lists parsed-documents in the project. The index-create wizard uses this with the family + representation filters as the picker data source. Replaces the previously-proposed `/parse-runs/candidates` endpoint.

**Query parameters:**

| param | required | description |
|---|---|---|
| `parser` | when `parse_config_hash` is set | restrict to one family |
| `parse_config_hash` | when `parser` is set | restrict to one family |
| `representation` | no | `full_text` \| `full_markdown` \| `block` — filters to parsed-docs where the segment is populated |
| `latest_per_source` | no, default `true` | when true, return only the newest parsed-doc per `source_document_id` within the result set |

**Response:** `list[ParsedDocumentListItem]`

```python
class ParsedDocumentListItem(BaseModel):
    id: UUID = Field(..., alias="id")
    parse_run_id: UUID = Field(..., alias="parseRunId")
    parser: str
    parse_config_hash: str = Field(..., alias="parseConfigHash")
    source_document_id: UUID = Field(..., alias="sourceDocumentId")
    source_filename: str | None = Field(None, alias="sourceFilename")
    has_full_markdown: bool = Field(..., alias="hasFullMarkdown")
    block_count: int = Field(..., alias="blockCount")
    parsed_at: datetime = Field(..., alias="parsedAt")  # parse_run finished_at

    model_config = ConfigDict(populate_by_name=True)
```

Sorted newest-first by `parsed_at`. When `latest_per_source=false`, callers see all parse runs in the family per source document — that's the non-determinism debugging affordance.

### 3. `IndexConfig` — family constraint, drop `raw_text`

```python
class IndexConfig(BaseModel):
    # Parse-config family (declarative; constrains parsed-doc selection)
    parser: str | None = Field(default=None)
    parse_config_hash: str | None = Field(default=None, alias="parseConfigHash")

    # Which segment of each ParsedDocument this index reads
    source_representation: Literal["full_text", "full_markdown", "block"] = Field(
        default="full_text", alias="sourceRepresentation"
    )

    # Chunking strategy + the rest of the config — unchanged
    ...
```

Changes:
- `raw_text` removed from the Literal. The default is now `full_text`. Every `ParsedDocument` has `full_text`, so the legacy "no CDM" path collapses into the CDM path.
- `parser` and `parse_config_hash` are **required** when this config is used to create an index (model validator below).

Validator:

```python
@model_validator(mode="after")
def require_family_for_indexing(self) -> "IndexConfig":
    if self.parser is None or self.parse_config_hash is None:
        raise ValueError(
            "IndexConfig requires parser and parse_config_hash"
        )
    return self
```

The existing strategy-vs-representation validator updates to drop the `raw_text` row.

### 4. `IndexCreate` and `AddParsedDocumentsRequest` — new shape

The unit of selection is the parsed-document. The request collapses to a flat list of parsed-document IDs. No per-row binding schema.

```python
class IndexCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    parsed_document_ids: list[UUID] = Field(
        default_factory=list, alias="parsedDocumentIds"
    )
    config: IndexConfig
    auto_process: bool = Field(default=False, alias="autoProcess")

    model_config = ConfigDict(populate_by_name=True)


class AddParsedDocumentsRequest(BaseModel):
    parsed_document_ids: list[UUID] = Field(
        ..., alias="parsedDocumentIds", min_length=1
    )

    model_config = ConfigDict(populate_by_name=True)
```

Renamed: `AddDocumentsRequest` → `AddParsedDocumentsRequest`. The route `POST /indexes/{id}/documents` becomes `POST /indexes/{id}/parsed-documents`.

**Validation in `IndexService.create_index()` and `add_parsed_documents()`:**

For each `parsed_document_id`:
1. The parsed-doc must exist and belong to the project. Otherwise → 404 listing the offending IDs.
2. Its `parse_run.parser` and `parse_run.config_hash` must match `IndexConfig.(parser, parse_config_hash)`. Otherwise → `ValidationError` listing the mismatched IDs.
3. The segment named by `IndexConfig.source_representation` must be populated:
   - `full_text` → `full_text is not null` (always true under invariants; included for symmetry).
   - `full_markdown` → `full_markdown is not null`.
   - `block` → `len(blocks) >= 1` (always true under invariants).
   Mismatches → `ValidationError` listing offending IDs.
4. Parse run status must be `succeeded`.

### 5. Chunk preview — refactor for source resolution

Today's preview reads `document.extracted_text`, which works only for `raw_text` and lies for CDM modes. Once `raw_text` is gone, the preview must read the same `ParsedDocument.{segment}` the save path will read, for the *specific* parsed-doc the user selected.

**Refactor:** factor source resolution out of the chunking pipeline so preview and save share it.

```
resolve_source(parsed_document_id, source_representation) → ChunkSource
chunk(source, config)                                      → list[Chunk]
persist(index_id, parsed_document_id, chunks)              → IndexDocument rows
```

- Preview = `resolve_source → chunk → slice/stats` (no DB writes).
- Save = `resolve_source → chunk → persist → embed`.

`ChunkSource` is `text` (for `full_text` / `full_markdown`) or `blocks` (for `block`).

`ChunkPreviewRequest`:

```python
class ChunkPreviewRequest(BaseModel):
    parsed_document_id: UUID = Field(..., alias="parsedDocumentId")
    config: IndexConfig
    max_chunks: int = Field(default=5, ge=1, le=20, alias="maxChunks")

    model_config = ConfigDict(populate_by_name=True)
```

`document_id` is removed — the parsed-doc is the unit. The "disable preview for full_markdown" guard added in commit `2a0cfa1` is removed once this is wired up.

### 6. ORM persistence

Existing `index_documents` table keeps its name. Schema changes:

| column | change |
|---|---|
| `parsed_document_id` | **new**, FK → `parsed_documents.id`, `ON DELETE CASCADE`, `NOT NULL` after backfill |
| `document_id` | **kept**, denormalized lookup. May be dropped in a future cleanup. |
| `parse_run_id` | **kept**, denormalized lookup. May be dropped in a future cleanup. |

`parsed_document_id` becomes the canonical FK. `document_id` and `parse_run_id` continue to exist for query convenience (existing reports, debug views) but are derivable via FK and are no longer load-bearing.

---

## Frontend

### Wizard step ordering

1. **Name & description**
2. **Parse-config family** — pick from `GET /parse-runs/configs`. Sets `IndexConfig.parser` and `IndexConfig.parseConfigHash`.
3. **Source representation** — `full_text` / `full_markdown` / `block`. `full_markdown` greyed out unless the chosen family has `has_full_markdown = true`.
4. **Parsed-documents** — pick from `GET /parsed-documents?parser=…&parse_config_hash=…&representation=…&latest_per_source=true`. Defaults to latest-per-source; toggle reveals older runs in the same family.
5. **Chunking strategy** — unchanged.
6. **Submit** — `IndexCreate` with `parsed_document_ids` and `config`.

### Parse-config family selector — Step 2

Each option displays:
- Parser name: "LlamaParse" / "LandingAI"
- Config summary derived from key config fields (`result_type`, `num_workers`, etc.)
- Markdown availability badge (`[markdown]` or greyed)
- Coverage: *"N parsed documents"*

**Empty state:** *"No parse runs found for this project. Parse some documents first."* with a link to the Documents page. Block proceeding.

### Parsed-document picker — Step 4

Header controls:
- **"Latest per source document"** toggle, default on. When off, the list expands to show every parse run in the family per source document.
- Search by filename.

Row layout:
```
☐  acme-msa.pdf         run b3fa4… · Apr 30 09:11    [markdown ✓]  [12 blocks]
☐  acme-msa.pdf         run 7d3f2… · Apr 29 14:32    [markdown ✓]  [12 blocks]
☐  vendor-form.pdf      run 1ab9b… · Apr 30 11:48    [markdown ✓]  [ 8 blocks]
```

(Two `acme-msa.pdf` rows appear only when "Latest per source document" is off — same source, two parse runs.)

The picker is the source of truth for `parsed_document_ids`. The existing "Documents" step in the wizard is replaced by this picker.

### Index detail — "Documents" tab → "Parsed Documents"

The index detail page's Documents tab is renamed **Parsed Documents** in the same slice. Columns:

| Source filename | Parse run | Parsed at | Status | Chunks |
|---|---|---|---|---|

Source filename links to the document detail; Parse run links to the parse-run viewer. Status and chunks come from the existing `index_documents` row.

### Create-index submit flow

Body of `IndexCreate` becomes:

```json
{
  "name": "...",
  "description": "...",
  "parsedDocumentIds": ["<uuid>", "<uuid>"],
  "config": {
    "parser": "llamaparse",
    "parseConfigHash": "...",
    "sourceRepresentation": "full_markdown",
    "chunkingStrategy": "markdown_heading",
    "splitHeadingLevel": 2,
    "maxSectionChars": 4000,
    "embeddingProvider": "openai",
    "embeddingModel": "text-embedding-3-small"
  },
  "autoProcess": true
}
```

Same shape semantics for `AddParsedDocumentsRequest`.

---

## Tests

### Backend

- `test_parse_runs_configs_returns_distinct_families`
- `test_parse_runs_configs_scoped_to_project`
- `test_parse_runs_configs_empty_when_no_runs`
- `test_parse_runs_configs_has_full_markdown_reflects_population`
- `test_parsed_documents_filter_by_family`
- `test_parsed_documents_filter_by_representation`
- `test_parsed_documents_latest_per_source_default_true`
- `test_parsed_documents_latest_per_source_false_returns_all_runs`
- `test_parsed_documents_scoped_to_project` — rejects parsed-docs in other projects
- `test_create_index_persists_parsed_document_id_per_row`
- `test_create_index_rejects_parsed_doc_outside_declared_family`
- `test_create_index_rejects_parsed_doc_missing_segment` — e.g. `full_markdown` requested but parsed-doc has it null
- `test_create_index_rejects_parsed_doc_from_failed_run`
- `test_create_index_rejects_parsed_doc_from_other_project`
- `test_index_config_requires_parser_and_hash`
- `test_index_config_rejects_legacy_raw_text`
- `test_chunk_preview_resolves_source_from_parsed_document_id`
- `test_chunk_preview_full_markdown_works_after_refactor` — guard removed in `2a0cfa1` no longer triggers
- `test_resolve_source_returns_text_for_full_text_and_full_markdown`
- `test_resolve_source_returns_blocks_for_block_representation`

### Frontend

- Family selector populates from API
- `full_markdown` representation greyed out when family lacks markdown
- Empty state renders when no families exist
- Parsed-document picker defaults to latest-per-source
- Toggling "Latest per source document" off shows multiple runs per source
- Picker selection round-trips into `parsedDocumentIds` payload
- Create button disabled when no parsed-docs selected
- Submit payload uses the new shape
- Index detail "Parsed Documents" tab renders the new columns

---

## E2E Validation Checklist

1. Parse two source documents *twice* each with LlamaParse/premium (full_markdown) → 4 parse runs, 4 parsed-documents, all in one family.
2. Open Create Index → enter name → Step 2 shows LlamaParse/premium.
3. Step 3: pick `full_markdown`. Verify `full_text` and `block` are also enabled.
4. Step 4: with "Latest per source document" on, the picker shows 2 rows (one per source). Toggle off → 4 rows. Select the *older* run for one source.
5. Step 5: pick `markdown_heading` chunking. Submit with auto-process.
6. Verify `index_documents.parsed_document_id` matches the picker selections (including the manually-chosen older run).
7. Build a sibling index against the *latest* run for the same source and compare retrieval — surfaces non-determinism through the pipeline.
8. Index detail → Parsed Documents tab shows source filename, parse-run id, parsed-at, status, chunks.

---

## Migration

### Schema

```sql
ALTER TABLE index_documents
    ADD COLUMN parsed_document_id UUID NULL
        REFERENCES parsed_documents(id) ON DELETE CASCADE;
```

### Backfill

For each `index_documents` row:
- If `parse_run_id IS NOT NULL`, look up the corresponding `parsed_documents.id` and set `parsed_document_id`.
- If `parse_run_id IS NULL` (legacy raw_text rows): the row is unmigrable.

### Cascade-delete legacy

After backfill, any `indexes` that contain at least one `index_documents` row with `parsed_document_id IS NULL` are **deleted in their entirety** (the index, all its rows, all its chunks). This removes legacy raw_text indexes. Acceptable because:
- The system is pre-prod; legacy raw_text indexes carry no committed value.
- `raw_text` is removed from `IndexConfig.source_representation` in this slice; legacy indexes would fail to validate anyway.

```sql
DELETE FROM indexes WHERE id IN (
    SELECT DISTINCT index_id FROM index_documents
    WHERE parsed_document_id IS NULL
);
-- index_documents and chunks cascade via existing FKs
```

### Finalize

```sql
ALTER TABLE index_documents
    ALTER COLUMN parsed_document_id SET NOT NULL;
```

### Future cleanup (out of scope)

Once nothing reads `index_documents.document_id` or `index_documents.parse_run_id` directly, drop those columns. Tracked as a follow-up — not part of this slice.

---

## Breaking changes summary

- `IndexCreate.document_ids: list[UUID]` → `IndexCreate.parsed_document_ids: list[UUID]`.
- `AddDocumentsRequest{document_ids, parse_run_ids}` → `AddParsedDocumentsRequest.parsed_document_ids`.
- Route `POST /indexes/{id}/documents` → `POST /indexes/{id}/parsed-documents`.
- `IndexConfig.source_representation` Literal drops `raw_text`; default changes to `full_text`.
- `IndexConfig.(parser, parse_config_hash)` become required.
- `ChunkPreviewRequest.document_id` → `parsed_document_id`.
- `GET /projects/{id}/parse-configs` (proposed; not yet shipped) → `GET /projects/{id}/parse-runs/configs`.
- `POST /projects/{id}/indexes/resolve-parse-runs` (proposed; not yet shipped) → replaced by `GET /projects/{id}/parsed-documents`.
- Legacy raw_text indexes deleted by migration.
- Index detail "Documents" tab renamed "Parsed Documents."
- Frontend callers (`IndexCreateDialog`, `CreateIndexPage`, `useIndexes`, `api/indexes.ts`, index detail page) updated in this slice.
