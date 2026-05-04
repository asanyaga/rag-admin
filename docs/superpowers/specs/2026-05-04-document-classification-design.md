# Document Classification — Design Spec

**Date:** 2026-05-04  
**Status:** Approved for implementation  
**Author:** Asa Nyaga

---

## 1. Problem & Use Case

Extraction workloads (balance sheet, income statement, receipt line items) should not receive an entire document. Classification identifies which pages and blocks within a `ParsedDocument` correspond to a requested label — "balance_sheet", "income_statement", "legal_clause", or any arbitrary user-defined label — so extraction receives only the relevant region.

Primary flow:
1. Parse document → `ParsedDocument`
2. Classify → identify labeled regions (page ranges + block IDs)
3. Slice → produce a sub-`ParsedDocument` from the region
4. Extract from the sub-document

Classification is also a standalone workload: results are stored, re-runnable, and queryable (e.g. for building eval datasets).

---

## 2. Approach

**LLM-based, page-batched classification.** The `ParsedDocument` is serialized to a compact block-level text representation and sent to an LLM in page batches. The LLM returns a per-page, per-label status (`start | continue | none`). Batch results are assembled into `ClassifiedRegion` objects.

Rules-based approaches were explicitly rejected: they require ongoing maintenance, have unpredictable edge-case failures, and cannot be iterated on as easily as prompts. The CDM already provides rich signals (block roles, text, page structure) that an LLM can reason over directly.

**Why batching instead of sending the full document:**  
Small local models (Qwen2.5 7B, Phi-4) have context windows of 16K–32K tokens. A 200-page annual report serialized as `(page, role, text)` per block is ~50K–100K tokens. Batching of 10 pages with 3-page overlap keeps each call well within any model's context window and enables local-first execution.

---

## 3. Architecture

Classification is a new first-class workload alongside parsing. It follows the existing `router → service → repository → database` pattern.

```
routers/classification.py
  ↓
services/classification/service.py      — orchestrates batching, LLM calls, assembly
services/classification/serializer.py   — ParsedDocument → compact block text
services/classification/assembler.py    — batch results → ClassifiedRegion list
  ↓
repositories/classification_run_repository.py
  ↓
classification_runs + classification_regions tables
```

**LLM layer:** The service uses the existing `LLMPort` protocol and `LLMRegistry` — no classification-specific LLM abstraction. Two new adapters are added to the existing `services/llm/` package: `OllamaAdapter` and `GroqAdapter`. Both use the OpenAI-compatible API and are thin wrappers over `OpenAIAdapter` with different base URLs. These are available to all LLM-consuming features, not just classification.

**CDM extension:** A new file `cdm/classification.py` adds the `ClassifiedRegion` value object. No changes to `cdm/models.py`.

**`slice_doc` utility:** `cdm/workloads.py` (new file) provides a pure function `slice_doc(doc, region) → ParsedDocument` that produces a derived sub-document for downstream extraction. Sets `derived_from` and `derivation` on the result.

---

## 4. Data Model

### CDM value objects (`cdm/classification.py`)

```python
class ClassifiedRegion(_Frozen):
    label: str
    page_start: int                    # 0-indexed, inclusive
    page_end: int                      # 0-indexed, inclusive
    block_ids: List[str]               # blocks in region, reading order
    confidence: Optional[float] = None  # LLM-provided if model returns it; otherwise null
    reasoning: Optional[str] = None     # LLM chain-of-thought if model returns it; otherwise null
    source: Literal["llm", "human"] = "llm"

class ClassificationRunStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
```

### DB tables

**`classification_runs`**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `parse_run_id` | UUID FK → `parse_runs.id` CASCADE | specific parsed representation |
| `document_id` | UUID FK → `documents.id` CASCADE | for UI lookup without joins |
| `labels_requested` | JSONB | `["balance_sheet", "income_statement"]` |
| `llm_provider` | TEXT | `"ollama"`, `"groq"`, `"anthropic"` |
| `llm_model` | TEXT | `"qwen2.5:7b"`, `"llama-3.3-70b"`, `"claude-haiku-4-5"` |
| `status` | TEXT | pending / running / completed / failed |
| `error` | TEXT | |
| `batch_size` | INT | default 10 |
| `batch_overlap` | INT | default 3 |
| `input_tokens` | INT | total across all batches |
| `output_tokens` | INT | |
| `duration_ms` | INT | |
| `started_at` | TIMESTAMPTZ | |
| `finished_at` | TIMESTAMPTZ | |
| `created_at` | TIMESTAMPTZ | |

**`classification_regions`**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `run_id` | UUID FK → `classification_runs.id` CASCADE | |
| `label` | TEXT | |
| `page_start` | INT | 0-indexed, inclusive |
| `page_end` | INT | 0-indexed, inclusive |
| `block_ids` | JSONB | ordered list of block UUIDs |
| `confidence` | FLOAT | |
| `reasoning` | TEXT | |
| `source` | TEXT | `"llm"` or `"human"` |

Indexes: `(run_id)` and `(label)` on regions; `(parse_run_id)`, `(document_id)`, `(status)` on runs.

Regions are a separate table (not JSONB on the run) to support label-based queries across runs — needed for eval dataset building.

---

## 5. Service & LLM Batching

### Serialization (`serializer.py`)

Each block becomes one line:
```
[page {N}, {role}] {text_or_markdown}
```
Tables use `block.markdown` if available, falling back to `block.text`. `bbox`, `spans`, and `parser_extras` are stripped. A 200-page doc at ~20 blocks/page serializes to roughly 4K–8K tokens total.

### Batching

Pages are batched with configurable size and overlap:
```
batch_size=10, overlap=3, 25 pages:
  batch 0: pages 0–9
  batch 1: pages 7–16
  batch 2: pages 14–23
  batch 3: pages 21–24
```

The overlap ensures sections that straddle a batch boundary are seen in full context in at least one batch.

### LLM call

Each batch call passes the serialized blocks for those pages plus the full label list. The LLM returns structured JSON with per-page, per-label status:

```json
{
  "pages": [
    {"page": 0, "labels": {"balance_sheet": "none", "income_statement": "none"}},
    {"page": 7, "labels": {"balance_sheet": "start", "income_statement": "none"}},
    {"page": 8, "labels": {"balance_sheet": "continue", "income_statement": "none"}}
  ]
}
```

All providers use JSON mode / structured output for reliable parsing.

### Overlap resolution

For pages that appear in multiple batch results, the result from the batch where the page falls in the **middle 50% of the window** takes precedence — the model has more context there than at edges.

### Assembly (`assembler.py`)

Single pass per label over sorted pages:
- `"start"` → open a new region
- `"continue"` → extend current region's `page_end`
- `"none"` → close current region

After regions are built, `block_ids` are populated from `doc.blocks` filtered by `page_index ∈ [page_start, page_end]`, preserving `reading_order`.

### LLM provider configuration

The service accepts an `LLMPort` (from the registry) and an `LLMConfig`. Provider and model are specified per-run. Defaults come from env vars:

```
CLASSIFIER_LLM_PROVIDER=ollama
CLASSIFIER_LLM_MODEL=qwen2.5:7b
```

**Provider tier recommendation:**
1. `ollama/qwen2.5:7b` — local default, runs on CPU or consumer GPU
2. `ollama/phi4` — better edge-case handling, needs 8 GB VRAM
3. `groq/llama-3.3-70b` — fast hosted open source, free tier available
4. `anthropic/claude-haiku-4-5` — AI lab fallback, reliable JSON output

### Background execution

Classification runs as a background task (same pattern as parse runs). `POST` returns immediately with `status=pending`; the client polls for completion.

---

## 6. API

```
POST   /api/documents/{doc_id}/classification-runs   — start a new run (background task)
GET    /api/documents/{doc_id}/classification-runs   — list runs for a document
GET    /api/classification-runs                      — list all runs for the project (powers /classify list page)
GET    /api/classification-runs/{run_id}             — run detail with regions inline
DELETE /api/classification-runs/{run_id}             — hard delete, cascades to regions
```

**POST request body:**
```json
{
  "parse_run_id": "uuid",
  "labels": ["balance_sheet", "income_statement"],
  "llm_provider": "ollama",
  "llm_model": "qwen2.5:7b",
  "batch_size": 10,
  "batch_overlap": 3
}
```
`llm_provider`, `llm_model`, `batch_size`, `batch_overlap` are optional — defaults from env.

**GET single run response:**
```json
{
  "id": "uuid",
  "status": "completed",
  "labels_requested": ["balance_sheet"],
  "llm_provider": "ollama",
  "llm_model": "qwen2.5:7b",
  "duration_ms": 4200,
  "input_tokens": 8100,
  "output_tokens": 620,
  "regions": [
    {
      "label": "balance_sheet",
      "page_start": 44,
      "page_end": 47,
      "block_ids": ["b-001", "b-002"],
      "confidence": 0.92,
      "reasoning": "Section headed 'Consolidated Balance Sheet' on page 45...",
      "source": "llm"
    }
  ],
  "error": null
}
```

Regions are always returned inline with the run — no separate regions endpoint in v1.

---

## 7. Frontend

Classification is a top-level nav item. Entry point is independent of the document detail page.

### Routes

```
/classify              → ClassificationPage       (run list + new run button)
/classify/new          → NewClassificationRunPage (wizard)
/classify/{run_id}     → ClassificationRunDetailPage
```

### New run wizard (`/classify/new`)

Three steps:
1. **Select document** — searchable list from the project's documents
2. **Select parse run** — for the chosen document, pick which parse run to classify (shows parser, representation kind, date)
3. **Configure** — label tag input (free text, multiple), LLM provider + model selects, batch size in collapsible advanced section

One classification run = one document + one parse run. Batch mode (multiple documents) is out of scope for v1.

### Run list (`/classify`)

Table: document name, parse run (parser + date), labels, status badge, provider/model, duration, created at. Filterable by status and document.

### Run detail (`/classify/{run_id}`)

- Run metadata header (document, parse run, provider, tokens, duration)
- Regions as cards: label name, page range, confidence badge, reasoning (collapsible)
- Block count shown as a number ("142 blocks") — not listed individually
- "Re-run" button pre-fills the new run wizard with the same config

### Reusable components

Built prop-driven with no dependency on page routing, for use in agent pipeline configs:

| Component | Purpose |
|---|---|
| `ClassificationRunForm` | Label input + provider/model/batch config |
| `ClassificationRegionList` | List of region cards for a run |
| `ClassificationRegionCard` | Single region: label, page range, confidence, reasoning |
| `ClassificationRunStatusBadge` | Status pill |

---

## 8. File Map

| Layer | New files |
|---|---|
| CDM | `backend/app/cdm/classification.py` |
| CDM utility | `backend/app/cdm/workloads.py` (`slice_doc`) |
| LLM adapters | `backend/app/services/llm/ollama_adapter.py`, `groq_adapter.py` |
| Service | `backend/app/services/classification/service.py`, `serializer.py`, `assembler.py` |
| Repository | `backend/app/repositories/classification_run_repository.py` |
| DB models | `backend/app/models/classification_run.py`, `classification_region.py` |
| Migration | new Alembic migration |
| Router | `backend/app/routers/classification.py` |
| Frontend pages | `ClassificationPage`, `NewClassificationRunPage`, `ClassificationRunDetailPage` |
| Frontend components | `ClassificationRunForm`, `ClassificationRegionList`, `ClassificationRegionCard`, `ClassificationRunStatusBadge` |

---

## 9. Out of Scope (v1)

- Rules-based classification tier
- Human annotation / manual region labeling (deferred to eval dataset tooling)
- CDM viewer integration (highlighting classified regions in the parsed document viewer)
- Batch mode (classifying multiple documents in one run)
- Cross-run label queries endpoint
- Streaming progress updates during batch processing
