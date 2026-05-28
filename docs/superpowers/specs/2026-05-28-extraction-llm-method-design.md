# Extraction LLM Method Design

**Date:** 2026-05-28
**Status:** Approved
**Scope:** Replace the prototype `ollama` extraction method with a generic `llm` extraction method backed by the existing LLM registry infrastructure.

---

## Problem

The current `OllamaExtractor` registered as `extraction_method = "ollama"` was a prototype to prove LLM-based extraction worked. It is hardcoded to Ollama's OpenAI-compatible REST API and exposes Ollama-specific config (endpoint URL, model name) directly in the UI. This conflates the extraction method with the LLM provider.

`ExtractionSchema` was incorrectly identified as the place to store LLM config — it is a pure data shape definition (provider-agnostic) and should remain so.

---

## Goals

1. A generic `"llm"` extraction method that works with any provider in the LLM registry (Ollama, OpenAI, Anthropic, Groq, etc.)
2. `PromptConfigEditor` drives provider/model selection and all LLM parameters for the `"llm"` method
3. `ExtractionSchema` stays clean — no LLM config on the schema
4. Existing extraction method taxonomy (`llamaextract`, `landingai`) is unchanged
5. Existing `ExtractionResult` rows with `extraction_method = "ollama"` are migrated to `"llm"`

---

## Extraction Method Taxonomy

| Method | Description | Config UI |
|---|---|---|
| `"llm"` | Generic LLM extraction via the LLM registry | `<PromptConfigEditor>` + `user_prompt_template` + `structured_output_mode` + `inject_block_ids` |
| `"llamaextract"` | LlamaIndex managed extraction service | Existing LlamaExtract config (unchanged) |
| `"landingai"` | Vision-based extraction | Existing LandingAI config (unchanged) |

`"ollama"` is retired. It is not an extraction method — Ollama is a provider option within the `"llm"` method.

---

## Backend

### New adapter: `LLMExtractor`

**File:** `backend/app/adapters/extraction/llm.py`  
**Replaces:** `backend/app/adapters/extraction/ollama.py`

Registered as `"llm"` in the extractor registry. Uses the existing `LLMRegistry` + `resolve_llm_config()` infrastructure — the same pattern used by classification and playground. Does **not** use `OpenAICompatMixin` (that was an implementation detail of `OllamaExtractor`); LLM calls go through the registry adapter directly.

```python
class LLMExtractor(DataExtractor):
    extractor_type = "llm"
    display_name = "LLM"

    def __init__(self, llm_registry: LLMRegistry) -> None:
        self._registry = llm_registry

    async def extract(self, parsed_document, schema, config=None) -> ExtractionOutput:
        cfg = dict(config or {})
        prompt_config = PromptConfig.model_validate(cfg["llm_config"]) if cfg.get("llm_config") else None
        llm_config = resolve_llm_config(
            prompt_config,
            default_provider="ollama_local",
            default_model="llama3.2:8b",
        )
        adapter = self._registry.get(llm_config.provider)
        # ... build messages, call adapter, parse response
```

`_build_messages()` logic is identical to the current `OllamaExtractor`: reads `cfg.get("system_prompt")` and `cfg.get("user_prompt_template")` with the same defaults.

The `structured_output_mode` config key (`"json_schema"` / `"json_mode"` / `"prompt_only"`) controls how the JSON schema constraint is passed to the model — this logic moves from `OpenAICompatMixin` into `LLMExtractor`. `inject_block_ids` is passed through to `build_extraction_context()` as before.

### `RunExtractionRequest` schema

**File:** `backend/app/schemas/extraction_result.py`

Two new optional fields:

```python
from app.schemas.prompt_config import PromptConfig

class RunExtractionRequest(BaseModel):
    parse_run_id: UUID = Field(..., alias="parseRunId")
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")
    extraction_method: str = Field(..., alias="extractionMethod")
    config: dict | None = None
    llm_config: PromptConfig | None = Field(None, alias="llmConfig")
    user_prompt_template: str | None = Field(None, alias="userPromptTemplate")

    model_config = ConfigDict(populate_by_name=True)
```

### `run_extraction()` service

**File:** `backend/app/services/extraction_service.py`

After building `merged_config`, merge the LLM fields:

```python
merged_config = dict(config or {})
merged_config["extraction_target"] = schema.extraction_target
if llm_config:
    merged_config["llm_config"] = llm_config.model_dump(by_alias=False, mode="json")
if user_prompt_template:
    merged_config["user_prompt_template"] = user_prompt_template
```

`run_extraction()` signature gains `llm_config: PromptConfig | None = None` and `user_prompt_template: str | None = None`.

### Extraction router

**File:** `backend/app/routers/extraction.py`

When `extraction_method == "llm"`:

1. Read the provider from `body.llm_config.provider` (falling back to `"ollama_local"`)
2. Resolve the API key from `ProviderKeyRepository` using the same BYOK pattern as the classification router
3. Build `LLMRegistry` with the resolved key and pass it to `LLMExtractor`

The `run_extraction` endpoint passes `llm_config` and `user_prompt_template` from the request body to the service.

### Extractor registry

**File:** `backend/app/adapters/extraction/registry.py`

- Remove `OllamaExtractor` registration
- Add `LLMExtractor` registered as `"llm"`
- Display name: `"LLM"`, description: `"Structured extraction via any LLM provider (Ollama, OpenAI, Anthropic, Groq, …)"`

### Data migration

One Alembic migration — no schema changes, data-only:

```python
def upgrade() -> None:
    op.execute(
        "UPDATE extraction_results SET extraction_method = 'llm' "
        "WHERE extraction_method = 'ollama'"
    )

def downgrade() -> None:
    op.execute(
        "UPDATE extraction_results SET extraction_method = 'ollama' "
        "WHERE extraction_method = 'llm'"
    )
```

Existing `config` dicts on migrated rows are historical records and are not updated — they are not re-executed.

---

## Frontend

### `ExtractionForm.tsx`

**File:** `frontend/src/components/extraction/ExtractionForm.tsx`

**Remove** the Ollama-specific state and constants:
- `ollamaModel`, `ollamaEndpointPreset`, `ollamaCustomEndpoint`, `ollamaStructuredOutputMode`, `ollamaInjectBlockIds`
- `OLLAMA_ENDPOINTS` constant
- `OllamaEndpointPreset` type

**Add:**
- `usePromptConfig()` hook (provider, model, system prompt, thinking, sampling params)
- `userPromptTemplate: string` state
- `structuredOutputMode: string` state (`"json_schema"` default)
- `injectBlockIds: boolean` state

**LLM section JSX** (rendered when `extractionMethod === "llm"`):

```tsx
{extractionMethod === 'llm' && (
  <div className="space-y-4">
    <PromptConfigEditor
      value={promptConfig}
      onChange={setPromptConfig}
      onProviderChange={setPromptConfigProvider}
      capabilities={{ thinking: true }}
    />

    <div className="space-y-1.5">
      <Label className="text-xs">User prompt template</Label>
      <p className="text-[11px] text-muted-foreground">
        Variables: <code>{'{schema_json}'}</code> and <code>{'{document_context}'}</code>.
        Leave blank to use the default template.
      </p>
      <Textarea
        value={userPromptTemplate}
        onChange={(e) => setUserPromptTemplate(e.target.value)}
        className="font-mono text-xs min-h-[80px]"
        placeholder="Extract structured data from the following document..."
      />
    </div>

    <div className="grid grid-cols-2 gap-3">
      <div className="space-y-1.5">
        <Label className="text-xs">Output mode</Label>
        <Select value={structuredOutputMode} onValueChange={setStructuredOutputMode}>
          <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="json_schema">JSON Schema</SelectItem>
            <SelectItem value="json_mode">JSON Mode</SelectItem>
            <SelectItem value="prompt_only">Prompt Only</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-end pb-2">
        <div className="flex items-center space-x-2">
          <Checkbox
            id="inject-block-ids"
            checked={injectBlockIds}
            onCheckedChange={(v) => setInjectBlockIds(v === true)}
          />
          <Label htmlFor="inject-block-ids" className="text-xs font-normal">
            Inject block IDs
          </Label>
        </div>
      </div>
    </div>
  </div>
)}
```

**`handleRun` config construction** when `extractionMethod === "llm"`:

```typescript
config = {
  structured_output_mode: structuredOutputMode,
  inject_block_ids: injectBlockIds,
}
// llmConfig and userPromptTemplate sent as top-level request fields, not inside config
await onRun({
  parseRunId,
  extractionSchemaId: schemaId,
  extractionMethod,
  config,
  llmConfig: promptConfig,
  userPromptTemplate: userPromptTemplate.trim() || undefined,
})
```

### TypeScript types

**File:** `frontend/src/types/extraction.ts`

```typescript
import type { PromptConfig } from '@/types/prompt-config'

export interface RunExtractionRequest {
  parseRunId: string
  extractionSchemaId: string
  extractionMethod: string
  config?: Record<string, unknown>
  llmConfig?: PromptConfig
  userPromptTemplate?: string
}
```

### API client

**File:** `frontend/src/api/extraction.ts`

The `runExtraction` function serializes the new fields to snake_case in the request body:

```typescript
llm_config: data.llmConfig ? {
  system_prompt: data.llmConfig.systemPrompt ?? null,
  provider: data.llmConfig.provider ?? null,
  model: data.llmConfig.model ?? null,
  temperature: data.llmConfig.temperature ?? null,
  max_tokens: data.llmConfig.maxTokens ?? null,
  top_p: data.llmConfig.topP ?? null,
  thinking: data.llmConfig.thinking ? {
    enabled: data.llmConfig.thinking.enabled,
    effort: data.llmConfig.thinking.effort ?? null,
    budget_tokens: data.llmConfig.thinking.budgetTokens ?? null,
  } : null,
  json_mode: data.llmConfig.jsonMode ?? false,
  structured_output: data.llmConfig.structuredOutput ?? null,
  tools: data.llmConfig.tools ?? null,
} : null,
user_prompt_template: data.userPromptTemplate ?? null,
```

---

## Files changed

**New:**
- `backend/app/adapters/extraction/llm.py`
- `backend/alembic/versions/<rev>_extraction_method_ollama_to_llm.py`

**Modified:**
- `backend/app/adapters/extraction/registry.py` — register `LLMExtractor` as `"llm"`, remove `OllamaExtractor`
- `backend/app/schemas/extraction_result.py` — add `llm_config` + `user_prompt_template` to `RunExtractionRequest`
- `backend/app/services/extraction_service.py` — merge new fields in `run_extraction()`
- `backend/app/routers/extraction.py` — build `LLMExtractor`, resolve BYOK credentials, pass new fields to service
- `frontend/src/types/extraction.ts` — add `llmConfig` + `userPromptTemplate` to `RunExtractionRequest`
- `frontend/src/api/extraction.ts` — serialize new fields
- `frontend/src/components/extraction/ExtractionForm.tsx` — replace Ollama section with LLM section

**Deleted:**
- `backend/app/adapters/extraction/ollama.py`

---

## What is not changing

- `ExtractionSchema` — remains a pure data shape definition; no LLM config stored there
- `llamaextract` and `landingai` extraction methods and their config UIs
- `ExtractionResult` schema — `config: dict` already absorbs everything; no column changes
- `OllamaExtractor`'s `_build_messages()` logic — carried over verbatim into `LLMExtractor`
