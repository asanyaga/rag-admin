# CDM Extraction — General Spec

**Date:** 2026-05-06
**Status:** Draft

## Overview

Refactor the extraction subsystem so that the primary input to every extractor is a CDM
`ParsedDocument` rather than a raw file path. Each adapter derives its own required inputs
from the CDM internally; nothing about file storage, markdown format, or provider protocol
leaks into the top-level abstraction.

This spec covers the shared foundation: port interface, output contract, provenance model,
LLM context building utilities, registry design, service layer changes, and ORM migrations.
Adapter-specific implementation details live in separate specs:

- `2026-05-06-llamaextract-adapter-refactor-design.md`
- `2026-05-06-ollama-extractor-design.md`

---

## Goals

- Single clean port: `extract(parsed_document, schema, config) → ExtractionOutput`
- All provenance anchored to a `parse_run_id` at minimum; block/page level where possible
- Registry keys are extractor identities, not protocol names
- Config includes prompt slots from day one — ready for the prompt management workstream
- User autonomy preference is expressed in registry ordering
- Provider adapters preserve full raw response for future provenance mining

## Non-Goals

- Prompt management UI or template versioning (separate workstream)
- LandingAI adapter implementation (follow-on spec)
- Frontend changes to support new provenance fields (follow-on)

---

## Port Interface

**File:** `backend/app/ports/data_extraction.py`

```python
from abc import ABC, abstractmethod
from app.cdm.models import ParsedDocument

class DataExtractor(ABC):

    @property
    @abstractmethod
    def extractor_type(self) -> str:
        """Registry key, e.g. 'ollama', 'llamaextract'."""
        ...

    @property
    def display_name(self) -> str:
        return self.extractor_type

    @abstractmethod
    async def extract(
        self,
        parsed_document: ParsedDocument,
        schema: dict,
        config: dict | None = None,
    ) -> ExtractionOutput:
        ...
```

`ParsedDocument` is the frozen Pydantic CDM type from `app.cdm.models`, not the ORM model.
The adapter is fully responsible for deriving what it needs from it.

---

## Output Contract

**File:** `backend/app/ports/data_extraction.py` (same file as port)

```python
from dataclasses import dataclass, field
from uuid import UUID
from typing import Any

@dataclass(frozen=True)
class FieldCitation:
    field_path: str               # dot/bracket path: "total", "line_items[0].sku"
    page_index: int | None        # always attempted; None only when truly unavailable
    block_ids: list[str] | None   # CDM block UUIDs; None in phase 1 (no block injection)
    text_spans: list[str] | None  # verbatim text the model drew from; optional

@dataclass(frozen=True)
class ExtractionOutput:
    structured_data: dict[str, Any]           # always — clean extracted values
    source_parse_run_id: UUID                  # always — minimum provenance anchor
    citations: list[FieldCitation] | None      # LLM path only
    provider_response_raw: dict | None         # provider path only — full response
    extraction_metadata: dict[str, Any] | None # timing, tokens, cost, warnings
```

Rules:
- `source_parse_run_id` is non-negotiable — every adapter must populate it
- LLM adapters populate `citations`, leave `provider_response_raw` null
- Provider adapters populate `provider_response_raw`, leave `citations` null
- Both may populate `extraction_metadata` with timing/cost data

---

## Provenance: Shadow Schema + Page-Annotated Markdown

### Phase 1 — Page-level provenance (ships first)

LLM adapters build extraction context from the CDM's `full_markdown` with page boundary
markers injected at each page transition:

```
<!-- page: 1 -->
# Section Heading

Paragraph text...

<!-- page: 2 -->
...
```

Page indices come from `parsed_document.pages[i].index`. If `full_markdown` is absent
the adapter falls back to `full_text` with page markers.

The user's extraction schema is augmented with a `__source` sibling for every leaf field:

```jsonc
// user schema field
"rent_income": { "type": "string" }

// augmented (sent to model, not stored or shown to user)
"rent_income": { "type": "string" },
"rent_income__source": {
  "type": "object",
  "properties": {
    "page_index": { "type": "integer" },
    "block_id":   { "type": "string"  }
  },
  "required": ["page_index"]
}
```

The model returns both; the adapter's post-processor strips all `__source` entries into
`FieldCitation` objects, leaving clean values in `structured_data`.

Nested objects and arrays are handled recursively — each leaf field gets its own
`__source` sibling at the same nesting level.

### Phase 2 — Block-level provenance (additive, no interface change)

When `inject_block_ids: true` in config, adapters additionally prepend
`<!-- block: {block.id} -->` before each block's markdown in the context string.
The model can then return `block_id` in the `__source` objects. The post-processor
is unchanged — it already handles `block_id` as optional.

### Utility module

**File:** `backend/app/adapters/extraction/llm_context.py`

Shared functions used by all LLM adapters:

| Function | Purpose |
|---|---|
| `build_extraction_context(parsed_doc, inject_block_ids) → str` | page/block-annotated markdown |
| `augment_schema_with_sources(schema) → dict` | adds `__source` siblings recursively |
| `strip_source_fields(raw_data, schema) → tuple[dict, list[FieldCitation]]` | post-processes model output |

---

## Registry

**File:** `backend/app/adapters/extraction/registry.py`

The registry is a pure catalogue. It knows what adapters exist and how to construct them.
It has no opinion on ordering, availability, or user preferences — those are user/project
concerns and do not belong in the backend constant layer.

### Catalogue

`get_known_extractors() → list[dict]` returns every known adapter unconditionally. No
credential checks, no settings reads, no filtering. The list is static. Adapter entries
are returned in registration order — no hierarchy implied.

The UI receives the full catalogue and decides how to present it (ordering, "Configure"
badges for unconfigured entries, etc.) without the backend encoding a product preference.

### Adapter construction

`get_extractor(method: str, credentials: dict) → DataExtractor` takes credentials
explicitly. The caller is responsible for resolving credentials from wherever they live.

```python
# Today — call site resolves from settings
credentials = _resolve_credentials_from_settings(method)
extractor = get_extractor(method, credentials)

# BYOK — call site resolves from project_extractor_credentials table
credentials = await credential_repo.get_for_project(project_id, method)
extractor = get_extractor(method, credentials)
```

The registry never reads `settings` directly. Only the call-site resolver changes for BYOK.

### BYOK seam

Credentials are stored at the **project level** (`project_extractor_credentials` table,
not per-user). All project members share one configured credential set. Per-user overrides
are deferred — if needed, that is a well-scoped additive change, not a registry refactor.

Today, `_resolve_credentials_from_settings(method)` in the router reads from `settings`.
For BYOK, replace that single function with a `project_extractor_credentials` DB lookup.
Nothing else in the system changes.

### `configured` flag

`GET /extractors` returns the full catalogue with a `configured: bool` per entry. The
service overlays this flag by checking the current credential source for each method:

```json
[
  { "extractionMethod": "llamaextract", "name": "LlamaExtract", "configured": true,  ... },
  { "extractionMethod": "ollama",        "name": "Ollama",        "configured": false, ... }
]
```

`configured: false` means "adapter exists, credentials not yet provided." The UI shows a
"Configure" link rather than hiding the entry.

---

## Config Shape

### Shared base fields (honoured by all adapters)

Every adapter config dict may contain these keys. Adapters use their own defaults when
the key is absent or null.

```
system_prompt: str | None        # null → adapter built-in default
user_prompt_template: str | None # null → adapter built-in default
```

These are the hook points for the future prompt management workstream. Provider adapters
that support prompt injection (e.g. LlamaExtract's `prompt_override`) map their field onto
`system_prompt` internally — the external config key is uniform.

### Adapter-specific fields

Each adapter's `config_schema` (returned by `get_known_extractors()`) documents its
own fields. See the individual adapter specs for details.

---

## Service Layer Changes

**File:** `backend/app/services/extraction_service.py`

### `run_extraction` signature change

```python
async def run_extraction(
    self,
    parse_run_id: UUID,          # replaces document_id as the document input
    extraction_schema_id: UUID,
    extraction_method: str,
    user_id: UUID,
    config: dict | None = None,
) -> ExtractionResultResponse
```

The service resolves `parse_run_id → ParsedDocument` (CDM Pydantic object) via
`parsed_document_repository.get_by_run(parse_run_id)`. The `document_id` for the ORM
`ExtractionResult` row is derived from `parsed_document.source_document_id`.

`document_id` is retained on the ORM row for backwards-compatible queries from the
existing results list endpoints.

### `process_extraction` background task changes

```python
async def process_extraction(
    extraction_result_id: UUID,
    result_repo: ExtractionResultRepository,
    parsed_document_repo: ParsedDocumentRepository,   # new
    storage_service: StorageService,
    extractor: DataExtractor,
) -> None
```

Flow:
1. `result_repo.set_started(extraction_result_id)`
2. Fetch `ExtractionResult` row — read `source_parse_run_id`
3. `parsed_document_repo.get_by_run(source_parse_run_id)` → CDM ORM row
4. Deserialise `orm_row.content` → `cdm.models.ParsedDocument` Pydantic object
5. Call `extractor.extract(parsed_document, schema_snapshot, config)`
6. `result_repo.update_result(...)` with `structured_data`, `citations`, `provider_response_raw`, `extraction_metadata`

`document_repo` dependency is removed from this task; the CDM row carries `source_document_id`
for any downstream lookups.

---

## ORM / Database Changes

**File:** `backend/app/models/extraction_result.py`

Three new columns on `extraction_results`:

| Column | SQLAlchemy type | Nullable | Notes |
|---|---|---|---|
| `source_parse_run_id` | `PGUUID` FK → `parse_runs.id` | True | nullable for migration; required for new rows |
| `citations` | `JSONB` | True | serialised `list[FieldCitation]`; null for provider path |
| `provider_response_raw` | `JSONB` | True | full provider response; null for LLM path |

`document_id` is retained; `source_parse_run_id` is added alongside it.
New index: `ix_extraction_results_parse_run` on `source_parse_run_id`.

Alembic migration adds the three columns and the index. The existing
`extraction_result_status` enum type is unchanged.

---

## Backwards Compatibility

- Existing `ExtractionResult` rows have no `source_parse_run_id`; the column is nullable
  to allow the migration without a data backfill
- The existing `list_extraction_results(document_id)` endpoint continues to work
- The `run_extraction` API endpoint changes its request body: `document_id` →
  `parse_run_id`. This is a breaking change on the request side — the frontend must be
  updated in the same PR

---

## Testing Strategy

- `TestDataExtractor` stub that implements the port for service-layer unit tests
- `llm_context.py` functions are pure and tested in isolation with fixture CDM documents
- `shadow_schema` round-trip: given schema → augmented → model output → stripped; assert
  `structured_data` is clean and `citations` are populated
- Service layer tests use the stub extractor and an in-memory `ParsedDocument`
- Integration tests for each concrete adapter live in their respective specs
