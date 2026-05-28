# Classification Provider Refactor — Design Spec

**Date:** 2026-05-28
**Status:** Approved for implementation
**Author:** Asa Nyaga

---

## 1. Problem & Motivation

The current classification feature assumes the only classification provider is an LLM. This is encoded throughout the stack:

- `ClassificationService` takes an `LLMRegistry` directly and owns the LLM batching loop
- `classification_runs` table has `llm_provider`, `llm_model`, `batch_size`, `batch_overlap` as required non-nullable columns — meaningless for non-LLM providers
- The router's `_build_llm_registry()` is a switch over hardcoded LLM provider names
- The frontend `PROVIDER_OPTIONS` lists only LLM providers with its own custom UI

Adding a second provider (e.g. LlamaIndex split, LandingAI, open-source doc processing) would require modifying the core service, the DB model, the router, and the frontend form.

The goal of this refactor is to make classification provider-agnostic: users select a `classifier_type` and provide that provider's specific config. The `LLMClassifier` delegates into the existing shared LLM infrastructure rather than reimplementing it. The `ClassificationService` becomes thin — it manages run lifecycle only.

This refactor also absorbs Plan 4 (system prompt override / `llm_config`): LLM-specific config including `system_prompt`, `temperature`, and `max_tokens` lives inside `classifier_config.llm_config` rather than as a separate top-level column.

---

## 2. Architecture

### ClassificationPort protocol

A new `ClassificationPort` protocol defines the single interface all providers implement:

```python
@dataclass
class ClassificationResult:
    regions: list[ClassifiedRegion]
    input_tokens: int = 0
    output_tokens: int = 0

class ClassificationPort(Protocol):
    async def classify(
        self,
        doc: ParsedDocument,
        labels: list[str],
    ) -> ClassificationResult: ...
```

Non-LLM providers return `input_tokens=0`, `output_tokens=0`. The `ClassificationResult` wrapper keeps the service layer uniform.

### LLMClassifier

Implements `ClassificationPort`. Contains the page-batching loop currently in `ClassificationService.execute()` — logic is unchanged, just relocated. Delegates all LLM calls to the existing `LLMRegistry`/`LLMPort`.

Reads `provider`, `model`, `batch_size`, `batch_overlap` and `llm_config` (system_prompt, temperature, max_tokens) from `classifier_config`. Threads `temperature` and `max_tokens` into `LLMConfig` so controls exposed by `PromptConfigEditor` are functional, not decorative.

### LlamaIndexSplitClassifier (skeleton)

Implements `ClassificationPort`. Constructor accepts `classifier_config: dict`. `classify()` raises `NotImplementedError` until the provider is implemented. Its presence proves the port works and unblocks future implementation.

### classifier_factory.py

Replaces `_build_llm_registry()` in the router. Builds the correct `ClassificationPort` instance from `classifier_type` + `classifier_config` + resolved `api_key`:

```python
def build_classifier(
    classifier_type: str,
    classifier_config: dict,
    api_key: str | None,
) -> ClassificationPort:
    if classifier_type == "llm":
        ...  # builds LLMRegistry, returns LLMClassifier
    elif classifier_type == "llamaindex_split":
        return LlamaIndexSplitClassifier(classifier_config)
    else:
        raise ValueError(f"Unknown classifier type: {classifier_type}")
```

### ClassificationService (thinned)

Takes `ClassificationPort` instead of `LLMRegistry`. Owns only run lifecycle:

```python
class ClassificationService:
    def __init__(self, repo, classifier: ClassificationPort): ...

    async def execute(self, run_id, doc, labels) -> None:
        await self.repo.update_status(run_id=run_id, status="running")
        start = time.monotonic()
        result = await self.classifier.classify(doc, labels)
        await self.repo.save_regions(run_id=run_id, regions=result.regions)
        duration_ms = int((time.monotonic() - start) * 1000)
        await self.repo.update_completed(
            run_id=run_id,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            duration_ms=duration_ms,
        )
```

### What is unchanged

`ClassifiedRegion` CDM value object, `ClassificationRegion` ORM model, `ClassificationRegionResponse` schema, `serializer.py`, `assembler.py`, all region/block endpoints, `ClassificationResultsViewer`, region cards, status badge, `get_annotated_blocks` repository method.

---

## 3. Data Model

### classification_runs table

**Dropped columns:** `llm_provider`, `llm_model`, `batch_size`, `batch_overlap`

**Added columns:**

| Column | Type | Notes |
|---|---|---|
| `classifier_type` | TEXT NOT NULL | `"llm"`, `"llamaindex_split"` |
| `classifier_config` | JSON NOT NULL | Provider-specific config blob |

All other columns (`status`, `error`, `input_tokens`, `output_tokens`, `duration_ms`, `started_at`, `finished_at`, `created_at`, regions FK) are untouched.

### classifier_config shapes

**`"llm"` type:**
```json
{
  "provider": "ollama_local",
  "model": "qwen2.5:7b",
  "batch_size": 10,
  "batch_overlap": 3,
  "llm_config": {
    "system_prompt": null,
    "temperature": 0.0,
    "max_tokens": 4096
  }
}
```

**`"llamaindex_split"` type (skeleton — exact keys TBD at implementation):**
```json
{
  "chunk_size": 1024,
  "chunk_overlap": 128
}
```

### Migration (one Alembic revision)

1. Add `classifier_type TEXT` (nullable), `classifier_config JSON` (nullable)
2. Populate existing rows:
   ```sql
   UPDATE classification_runs
   SET
       classifier_type = 'llm',
       classifier_config = json_build_object(
           'provider', llm_provider,
           'model', llm_model,
           'batch_size', batch_size,
           'batch_overlap', batch_overlap,
           'llm_config', '{}'::json
       );
   ```
3. Set both new columns `NOT NULL`
4. Drop `llm_provider`, `llm_model`, `batch_size`, `batch_overlap`

### ClassificationRunCreate dataclass

```python
@dataclass
class ClassificationRunCreate:
    parse_run_id: UUID
    document_id: UUID
    labels_requested: list[str]
    classifier_type: str
    classifier_config: dict
```

---

## 4. API

### POST /documents/{doc_id}/classification-runs

**Request body:**
```json
{
  "parse_run_id": "uuid",
  "labels": ["balance_sheet", "income_statement"],
  "classifier_type": "llm",
  "classifier_config": {
    "provider": "ollama_local",
    "model": "qwen2.5:7b",
    "batch_size": 10,
    "batch_overlap": 3,
    "llm_config": {
      "system_prompt": null,
      "temperature": 0.0,
      "max_tokens": 4096
    }
  }
}
```

`classifier_type` and `classifier_config` are optional. When omitted, the router defaults to `classifier_type="llm"` and builds a default `classifier_config` from the existing env vars `CLASSIFIER_LLM_PROVIDER` and `CLASSIFIER_LLM_MODEL` (unchanged), with `batch_size=10`, `batch_overlap=3`, and an empty `llm_config`.

### GET response shape

**Replaced fields:**

| Before | After |
|---|---|
| `llmProvider` | `classifierType` |
| `llmModel` | `classifierConfig` |
| `batchSize` | _(removed)_ |
| `batchOverlap` | _(removed)_ |

All other response fields (`status`, `error`, `inputTokens`, `outputTokens`, `durationMs`, `regions`, etc.) unchanged.

### BYOK resolution

`_classification_provider_to_byok(llm_provider)` → replaced by logic that reads `classifier_config["provider"]` when `classifier_type == "llm"`, and returns `None` for all other classifier types (non-LLM providers have no BYOK key requirement).

---

## 5. Frontend

### Types

```typescript
interface ClassificationRun {
  id: string
  parseRunId: string
  documentId: string
  labelsRequested: string[]
  classifierType: string
  classifierConfig: Record<string, unknown>
  status: ClassificationRunStatus
  error: string | null
  inputTokens: number | null
  outputTokens: number | null
  durationMs: number | null
  createdAt: string
  regions: ClassificationRegion[]
}

interface ClassificationRunCreateRequest {
  parseRunId: string
  labels: string[]
  classifierType?: string
  classifierConfig?: Record<string, unknown>
}

interface ClassificationRunFormValues {
  labels: string[]
  classifierType: string
  classifierConfig: Record<string, unknown>
}
```

### ClassificationRunForm layout

1. **Labels input** — unchanged
2. **Classifier type** select — `"llm"` | `"llamaindex_split"` (new providers added here)
3. **Conditional config panel:**
   - `"llm"` → renders `<PromptConfigEditor>` (handles provider, model, system prompt, temperature, max_tokens — no custom LLM UI in the classification form). On change, the form maps PromptConfigEditor values into `classifierConfig` as:
     ```
     classifierConfig.provider       ← promptConfig.provider
     classifierConfig.model          ← promptConfig.model
     classifierConfig.llm_config.system_prompt  ← promptConfig.systemPrompt
     classifierConfig.llm_config.temperature    ← promptConfig.temperature
     classifierConfig.llm_config.max_tokens     ← promptConfig.maxTokens
     ```
   - `"llamaindex_split"` → placeholder note ("not yet implemented")
4. **Advanced collapsible** (LLM only):
   - Batch size (pages) → `classifierConfig.batch_size`
   - Batch overlap (pages) → `classifierConfig.batch_overlap`

The form no longer owns `PROVIDER_OPTIONS` or `DEFAULT_MODELS` — that responsibility moves to `PromptConfigEditor`.

### Run detail page

The metadata header replaces provider/model display with `classifierType` + a human-readable summary derived from `classifierConfig` (for LLM: `{provider} / {model}`). The re-run button passes `classifierType`/`classifierConfig` as `defaultValues` into the form.

---

## 6. File Map

**New backend files:**
- `backend/app/services/classification/port.py` — `ClassificationPort` protocol, `ClassificationResult` dataclass
- `backend/app/services/classification/llm_classifier.py` — `LLMClassifier`
- `backend/app/services/classification/llamaindex_split_classifier.py` — skeleton
- `backend/app/services/classification/classifier_factory.py` — `build_classifier()`
- `backend/alembic/versions/<rev>_classification_provider_refactor.py` — migration

**Modified backend files:**
- `backend/app/services/classification/service.py` — takes `ClassificationPort`, remove LLM-specific code
- `backend/app/models/classification_run.py` — replace dropped columns with `classifier_type`/`classifier_config`
- `backend/app/repositories/classification_run_repository.py` — `ClassificationRunCreate` dataclass
- `backend/app/schemas/classification.py` — request + response schemas
- `backend/app/routers/classification.py` — use `build_classifier()`, new schema fields

**Modified frontend files:**
- `frontend/src/types/classification.ts`
- `frontend/src/api/classification.ts`
- `frontend/src/components/classification/ClassificationRunForm.tsx`
- `frontend/src/pages/NewClassificationRunPage.tsx`
- `frontend/src/pages/ClassificationRunDetailPage.tsx` — metadata header summary

---

## 7. Out of Scope

- Implementing `LlamaIndexSplitClassifier` beyond a skeleton
- Any new classifier type beyond `"llm"` and `"llamaindex_split"` stub
- Streaming progress during classification
- Cross-provider config validation (Pydantic models per classifier type)
