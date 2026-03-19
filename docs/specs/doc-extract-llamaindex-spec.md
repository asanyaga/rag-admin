# Document Extraction with LlamaExtract — Feature Spec

**Status:** Ready for Implementation
**Date:** 2026-03-19
**Scope:** Structured data extraction from documents using LlamaCloud LlamaExtract

---

## 1. Overview

Add a standalone document extraction feature that lets users define a JSON schema and extract structured data from uploaded documents via LlamaCloud LlamaExtract. Extraction is independent of the parsing pipeline — LlamaExtract handles its own internal document processing.

Future iterations will add Claude Vision and LandingAI as alternative extraction providers using the same adapter pattern established here.

## 2. LlamaExtract API

Uses the `llama-cloud` SDK (`AsyncLlamaCloud`), same package and API key (`LLAMA_CLOUD_KEY`) as LlamaParse.

```python
client = AsyncLlamaCloud()  # uses LLAMA_CLOUD_API_KEY env var

# Upload file for extraction
file_obj = await client.files.create(file=open("doc.pdf", "rb"), purpose="extract")

# Run extraction (blocking call, handles polling internally)
result = await client.extraction.extract(
    file_id=file_obj.id,
    data_schema=json_schema,       # JSON Schema dict
    config={
        "extraction_mode": "MULTIMODAL",     # FAST | BALANCED | MULTIMODAL | PREMIUM
        "extraction_target": "PER_DOC",      # PER_DOC | PER_PAGE | PER_TABLE_ROW
        "cite_sources": True,                # trace data to source pages/text
        "use_reasoning": True,               # explain extraction decisions
        "confidence_scores": False,          # per-field confidence (beta)
        "page_range": "1-5",                 # specific pages (optional)
    },
)

result.data                # extracted structured data (dict)
result.extraction_metadata # citations, reasoning, confidence per field
```

### Extraction Modes

| Mode | Description | Best for |
|------|-------------|----------|
| FAST | Simple OCR, no AI parsing | Clean text-based docs |
| BALANCED | Mid-tier speed/accuracy | Typical documents |
| MULTIMODAL (default) | Vision + text + tables | Mixed content, images |
| PREMIUM | Maximum fidelity | Complex tables, dense layouts |

### Extraction Targets

| Target | Description |
|--------|-------------|
| PER_DOC (default) | One JSON object per document |
| PER_PAGE | Array of objects, one per page |
| PER_TABLE_ROW | One object per detected entity (table row, list item) |

### Extensions

- **Citations** (`cite_sources`): Page numbers, verbatim source text, bounding boxes per field. MULTIMODAL/PREMIUM only.
- **Reasoning** (`use_reasoning`): Explanation of extraction decisions per field. BALANCED/MULTIMODAL/PREMIUM.
- **Confidence scores** (`confidence_scores`): Per-field parsing + extraction confidence. Beta, uncalibrated. MULTIMODAL/PREMIUM only.

### Schema Format

LlamaExtract accepts **JSON Schema** (subset). Constraints:
- Root must be `type: "object"`
- Max nesting depth: 7 levels (3-4 recommended)
- Max 5,000 properties total
- Field `description` is critical — guides the LLM on what to extract
- Supports: string, number, boolean, object, array, enums, nullable fields

---

## 3. Database Schema

### Table: `extraction_schemas` (user-defined, project-scoped)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| project_id | UUID FK → projects.id | CASCADE |
| name | String(255) | e.g. "Invoice Fields" |
| description | Text nullable | |
| schema_definition | JSON NOT NULL | JSON Schema entered by user |
| extraction_target | String(30) default "PER_DOC" | PER_DOC, PER_PAGE, PER_TABLE_ROW |
| created_by | UUID FK → users.id | |
| created_at / updated_at | DateTime(tz) | |

Unique constraint: `(project_id, name)`

### Table: `extraction_results`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| document_id | UUID FK → documents.id | CASCADE |
| extraction_schema_id | UUID FK → extraction_schemas.id | CASCADE |
| schema_definition_snapshot | JSON NOT NULL | Frozen copy of schema at extraction time |
| extraction_method | String(30) NOT NULL | "llamaextract" (future: "claude_vision", "landingai") |
| config | JSON nullable | Provider-specific config snapshot |
| structured_data | JSON nullable | Extracted fields (populated on completion) |
| extraction_metadata | JSON nullable | Citations, reasoning, confidence |
| status | Enum(pending/completed/failed) | |
| status_message | Text nullable | Error details if failed |
| started_at | DateTime(tz) nullable | For stale job detection |
| created_by | UUID FK → users.id | |
| created_at / updated_at | DateTime(tz) | |

Index: `(document_id, extraction_schema_id)`

### Config column design

Provider-specific config is stored as an opaque JSON blob. Each provider defines its own shape:

- **LlamaExtract:** `{ "extraction_mode": "MULTIMODAL", "cite_sources": true, "use_reasoning": false, "page_range": "1-5" }`
- **Claude Vision (future):** `{ "model": "claude-sonnet-4-5-20250514", "max_tokens": 4096 }`
- **LandingAI (future):** `{ "model": "layout-v2" }`

The `extraction_target` lives on the schema record (not in config) since it describes how the schema maps to the document structure.

The frontend renders provider-specific config UI dynamically from `config_schema` returned by `GET /extractors`.

---

## 4. Backend Architecture

Follow existing patterns from the parsing layer (`parse_result` model/service/router/repository).

### Port (Abstract Interface)

```python
# backend/app/ports/data_extraction.py

@dataclass
class ExtractionOutput:
    structured_data: dict[str, Any]
    extraction_metadata: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)  # latency, etc.

class DataExtractor(ABC):
    @abstractmethod
    async def extract(self, file_path: str, schema: dict, config: dict | None = None) -> ExtractionOutput: ...

    @property
    @abstractmethod
    def extractor_type(self) -> str: ...
```

The `extract()` method takes `file_path` (original document file). The adapter uploads the file to LlamaCloud and handles the extraction lifecycle.

### LlamaExtract Adapter

```python
# backend/app/adapters/extraction/llamaextract.py

class LlamaExtractAdapter(DataExtractor):
    def __init__(self, api_key=None):
        self.client = AsyncLlamaCloud(api_key=api_key) if api_key else AsyncLlamaCloud()

    async def extract(self, file_path, schema, config=None):
        config = config or {}
        # 1. Upload file: client.files.create(file=..., purpose="extract")
        # 2. Build extraction config from config dict
        # 3. Call client.extraction.extract(file_id=..., data_schema=schema, config=...)
        # 4. Map result → ExtractionOutput
```

### Extractor Registry

```python
# backend/app/adapters/extraction/registry.py
def get_extractor(extraction_method: str) -> DataExtractor | None
def get_available_extractors() -> list[dict]  # includes config_schema per provider
```

Only returns LlamaExtract if `LLAMA_CLOUD_KEY` is configured.

### Service + Background Task

```python
# backend/app/services/extraction_service.py

class ExtractionService:
    # Schema CRUD: create_schema, get_schema, list_schemas, update_schema, delete_schema
    # Extraction: run_extraction (creates pending result, validates inputs)
    # Results: get_extraction_result (with stale detection), list_extraction_results

async def process_extraction(extraction_result_id, ...):
    # Background task: set_started → get file path → extractor.extract() → update_result
```

---

## 5. API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/projects/{pid}/extraction-schemas` | POST | Create extraction schema |
| `/projects/{pid}/extraction-schemas` | GET | List schemas for project |
| `/extraction-schemas/{id}` | GET | Get schema details |
| `/extraction-schemas/{id}` | PUT | Update schema |
| `/extraction-schemas/{id}` | DELETE | Delete schema |
| `/extractions/run` | POST | Run extraction (returns 202) |
| `/documents/{id}/extraction-results` | GET | List extraction results for document |
| `/extraction-results/{id}` | GET | Get extraction result details |
| `/extractors` | GET | List available extraction methods |

### Run Extraction Request Body

```json
{
  "documentId": "uuid",
  "extractionSchemaId": "uuid",
  "extractionMethod": "llamaextract",
  "config": {
    "extraction_mode": "MULTIMODAL",
    "cite_sources": true
  }
}
```

### Background Processing

- Extraction runs as a `BackgroundTasks` task (same pattern as document parsing)
- Frontend polls `GET /extraction-results/{id}` every 3s while status is `pending`
- Stale job detection: pending jobs older than 10 minutes are auto-marked as `failed`
- Frontend polling timeout: 5 minutes

---

## 6. Frontend

### Extraction Page (`/extraction`)

Main page with two sections:

1. **Schema Management** — List, create, edit, delete extraction schemas. Schema editor accepts JSON Schema input with name, description, and extraction target selector.

2. **Extraction Results** — Run extraction on documents, view structured results with citations/reasoning.

### Components

- **ExtractionSchemaEditor** — JSON editor for schema definition, name/description fields, extraction target selector (PER_DOC / PER_PAGE / PER_TABLE_ROW)
- **RunExtractionDialog** — Select schema, extraction method, configure provider options (mode, citations, reasoning), select document
- **ExtractionResultViewer** — Display structured data as key-value pairs and tables, show citations/reasoning metadata
- **StructuredDataDisplay** — Render extracted data: simple fields as key-value rows, arrays (e.g. line_items) as tables, nested objects expanded

### Document Page Integration

Add "Extract" action on documents in `DocumentsPage.tsx` to link into the extraction flow.

### Navigation

Add "Extraction" item to sidebar navigation.

---

## 7. Files

### New files (20)

| # | File | Purpose |
|---|------|---------|
| 1 | `backend/alembic/versions/..._add_extraction_tables.py` | DB migration |
| 2 | `backend/app/models/extraction_schema.py` | Schema model |
| 3 | `backend/app/models/extraction_result.py` | Result model |
| 4 | `backend/app/repositories/extraction_schema_repository.py` | Schema data access |
| 5 | `backend/app/repositories/extraction_result_repository.py` | Result data access |
| 6 | `backend/app/ports/data_extraction.py` | ABC + ExtractionOutput |
| 7 | `backend/app/adapters/extraction/__init__.py` | Package init |
| 8 | `backend/app/adapters/extraction/llamaextract.py` | LlamaExtract adapter |
| 9 | `backend/app/adapters/extraction/registry.py` | Extractor registry |
| 10 | `backend/app/services/extraction_service.py` | Service + background task |
| 11 | `backend/app/schemas/extraction_result.py` | Pydantic response schemas |
| 12 | `backend/app/routers/extraction.py` | API endpoints |
| 13 | `frontend/src/types/extraction.ts` | TypeScript types |
| 14 | `frontend/src/api/extraction.ts` | API client |
| 15 | `frontend/src/hooks/useExtractionSchemas.ts` | Schema hook |
| 16 | `frontend/src/hooks/useExtractionResults.ts` | Results hook with polling |
| 17 | `frontend/src/components/extraction/ExtractionSchemaEditor.tsx` | JSON schema editor |
| 18 | `frontend/src/components/extraction/RunExtractionDialog.tsx` | Run extraction dialog |
| 19 | `frontend/src/components/extraction/ExtractionResultViewer.tsx` | Result viewer |
| 20 | `frontend/src/pages/ExtractionPage.tsx` | Extraction page |

### Modified files (3)

| File | Change |
|------|--------|
| `backend/app/models/__init__.py` | Add extraction model imports |
| `backend/app/main.py` | Register extraction router |
| `frontend/src/pages/DocumentsPage.tsx` | Add "Extract" action on documents |

---

## 8. Future Iterations (not this PR)

- **Claude Vision extraction** — new adapter implementing `DataExtractor` ABC
- **LandingAI extraction** — new adapter implementing `DataExtractor` ABC
- **Extraction ground truth + evaluation** — for measuring extraction accuracy
- **Batch extraction** — run extraction across multiple documents at once
- **Extraction agents** — LlamaCloud stateful agents (reusable extractors with cached config)
- **Schema generation** — auto-generate schemas from sample documents or natural language descriptions

---

## 9. References

- [LlamaExtract Concepts](https://developers.llamaindex.ai/python/cloud/llamaextract/features/concepts/)
- [Schema Design](https://developers.llamaindex.ai/python/cloud/llamaextract/features/schema_design/)
- [Options & Config](https://developers.llamaindex.ai/python/cloud/llamaextract/features/options/)
- [Extensions (Citations, Reasoning, Confidence)](https://developers.llamaindex.ai/python/cloud/llamaextract/features/extensions/)
- [Performance Tips](https://developers.llamaindex.ai/python/cloud/llamaextract/features/performance_tips/)
- [Extract with Citations Example](https://developers.llamaindex.ai/python/cloud/llamaextract/examples/extract_data_with_citations)
