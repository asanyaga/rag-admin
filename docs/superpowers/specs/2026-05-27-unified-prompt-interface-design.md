# Unified Prompt Interface Design

**Date:** 2026-05-27  
**Status:** Approved  
**Scope:** Playground + Evals + Extraction (Phase 1); extensible to Classification, Golden Set, Agents

---

## Problem

LLM prompt configuration is handled ad-hoc across every feature that calls an LLM:

- **Playground** — ad-hoc `instructions` string appended to a hardcoded system prompt
- **Evals** — `system_prompt TEXT` column on `EvalRun`; no model/param control
- **Extraction** — `DEFAULT_SYSTEM_PROMPT` and `DEFAULT_USER_PROMPT_TEMPLATE` hardcoded in `OllamaExtractor`; adapter already accepts overrides via `cfg` dict but neither is persisted on `ExtractionSchema` nor surfaced in the API or UI
- **Classification** — `_SYSTEM_PROMPT` hardcoded in service, not user-editable
- **Golden Set generation** — prompt constructed at runtime, not user-editable
- **Judge** — `JUDGE_PROMPT_TEMPLATE` hardcoded, not user-editable

There is no shared abstraction for "what the user wants the LLM to do." Adding new LLM-using features means re-inventing prompt storage, API shape, and UI each time.

---

## Goals

1. One backend type (`PromptConfig`) that represents user-expressed LLM configuration
2. One frontend component (`<PromptConfigEditor>`) that any feature can embed
3. Per-use overrides for Playground and Evals in Phase 1
4. Architecture that supports named/saved templates in a future phase without breaking changes

---

## Non-Goals (deferred)

- Persistent named prompt templates (Phase 2)
- Few-shot examples / multi-role message editing
- Multi-turn conversation history
- Multimodal input configuration
- Editing judge or classification prompts (internal system prompts, not user-facing yet)
- LlamaExtract extraction adapter (prompts are provider-managed; only Ollama/OpenAI-compatible adapters support prompt overrides)

---

## Architecture

### Two-layer split

```
User configures → PromptConfig (user-expressed, stored in DB)
                        ↓
              resolve_llm_config()
                        ↓
                  LLMConfig (adapter-ready, ephemeral)
                        ↓
               LLM adapter (OpenAI, Anthropic, Ollama, ...)
```

`PromptConfig` is what users edit and what gets persisted. `LLMConfig` is what adapters receive. The translation step (`resolve_llm_config`) handles all per-provider normalization — it is the only place provider-specific logic lives outside the adapters.

---

## Backend

### `PromptConfig` internal type

**File:** `backend/app/services/llm/prompt_config.py`

```python
class ThinkingConfig(BaseModel):
    enabled: bool = True
    effort: Literal["low", "medium", "high"] | None = None   # OpenAI, DeepSeek
    budget_tokens: int | None = None                          # vLLM/Ollama open-weight

class PromptConfig(BaseModel):
    system_prompt: str | None = None
    provider: str | None = None   # None = use feature's default provider
    model: str | None = None      # None = use feature's default model
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    thinking: ThinkingConfig | None = None
    json_mode: bool = False
    structured_output: dict | None = None   # JSON schema; supersedes json_mode
    tools: list[dict] | None = None
```

### `resolve_llm_config(config: PromptConfig) -> LLMConfig`

Also in `backend/app/services/llm/prompt_config.py`. Per-provider translation rules:

| Provider | `thinking` handling |
|---|---|
| Anthropic | `thinking: {type: "adaptive"}` when `thinking.enabled`; `effort`/`budget_tokens` ignored (Anthropic deprecated explicit budgets in Claude 4.x) |
| OpenAI o-series | `reasoning: {effort: thinking.effort}` |
| DeepSeek | `reasoning_effort: thinking.effort` |
| vLLM / Ollama open-weight | `thinking_budget_tokens` where supported; silently dropped otherwise |
| All others | `thinking` silently ignored |

`structured_output` overrides `json_mode` when both are set. `tools` is passed through as-is to the adapter.

### API schema

**File:** `backend/app/schemas/prompt_config.py`

Mirrors the internal `PromptConfig` with camelCase aliases for the API layer. Used in all feature request/response schemas that involve LLM configuration.

### DB changes

**EvalRun** — replace `system_prompt TEXT` with `llm_config JSON`:

```python
# models/eval_run.py
llm_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

Alembic migration: add `llm_config`, backfill `{"system_prompt": <old_value>}` for existing rows (provider/model not available on existing rows — left as `null`, features fall back to their defaults), drop `system_prompt`.

**ExtractionSchema** — add two new columns:

```python
# models/extraction_schema.py
llm_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
user_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
```

`user_prompt_template` is extraction-specific — it is a template string with two runtime-injected variables: `{schema_json}` (the augmented JSON schema) and `{document_context}` (the page-annotated markdown). It is not part of `PromptConfig` because it is not a universal LLM configuration concept. When `None`, the adapter falls back to `DEFAULT_USER_PROMPT_TEMPLATE`.

Alembic migration: add both columns as nullable with no backfill (all existing schemas use adapter defaults).

No other features require DB changes in Phase 1 (Playground is stateless; Classification and Golden Set do not yet persist config).

### Endpoint changes

**Playground** (`schemas/playground.py`):
- Remove `instructions: str | None` and the existing `LLMConfigSchema` field (provider, model, temperature, max_tokens)
- Add `llm_config: PromptConfig | None` — consolidates both into one shape
- `query: str` is unchanged — it is the live user input, constructed at runtime, and is not part of `PromptConfig`

**ExtractionSchema** (`schemas/extraction_schema.py`):
- Add `llm_config: PromptConfig | None` (alias `llmConfig`)
- Add `user_prompt_template: str | None` (alias `userPromptTemplate`)
- Both fields included in create and read schemas
- `ExtractionSchemaRead` returns both so the UI can repopulate on edit

**EvalRun** (`schemas/eval_run.py`):
- Remove `system_prompt: str | None` (alias `systemPrompt`)
- Add `llm_config: PromptConfig | None` (alias `llmConfig`)
- `EvalRunRead` includes `llm_config` so the frontend can repopulate on clone

### Service wiring

Each service that currently constructs `LLMConfig` manually accepts `PromptConfig` and calls `resolve_llm_config()`:

| Service | Change |
|---|---|
| `answer_service.py` | Accept `llm_config: PromptConfig` from request; call `resolve_llm_config()` |
| `answer_generation_service.py` | Accept `llm_config: PromptConfig` from eval run; replace `DEFAULT_SYSTEM_PROMPT` fallback |
| `services/llm/prompt.py` | `build_rag_prompt()` takes `system_prompt: str | None` from `PromptConfig` instead of `instructions` |
| `extraction_service.py` | Pass `llm_config` and `user_prompt_template` from `ExtractionSchema` into the adapter `cfg` dict |
| `adapters/extraction/ollama.py` | Already reads `cfg.get("system_prompt")` and `cfg.get("user_prompt_template")` — no change needed |
| `judge_service.py` | No change — judge prompt remains hardcoded (internal, not user-facing) |

---

## Frontend

### TypeScript types

**File:** `frontend/src/types/prompt-config.ts`

```typescript
export interface ThinkingConfig {
  enabled: boolean
  effort?: 'low' | 'medium' | 'high'
  budgetTokens?: number
}

export interface PromptConfig {
  systemPrompt?: string
  provider?: string   // undefined = use feature's default provider
  model?: string      // undefined = use feature's default model
  temperature?: number
  maxTokens?: number
  topP?: number
  thinking?: ThinkingConfig
  jsonMode?: boolean
  structuredOutput?: Record<string, unknown>
  tools?: unknown[]
}

export interface PromptConfigCapabilities {
  thinking?: boolean         // show thinking controls
  structuredOutput?: boolean // show structured output section
  tools?: boolean            // show tools section
}
```

### `usePromptConfig` hook

**File:** `frontend/src/hooks/usePromptConfig.ts`

Manages `PromptConfig` state. Accepts an `initial: Partial<PromptConfig>` (from DB for evals, from local defaults for playground). When `provider` changes, resets provider-specific fields (thinking, structured output) that don't transfer.

```typescript
const { promptConfig, updatePromptConfig, resetToDefaults } = usePromptConfig(initial)
```

### `<PromptConfigEditor>` component

**File:** `frontend/src/components/shared/PromptConfigEditor.tsx`

Fully controlled (no internal state). Props:

```typescript
interface PromptConfigEditorProps {
  value: PromptConfig
  onChange: (config: PromptConfig) => void
  capabilities?: PromptConfigCapabilities
  className?: string
}
```

Renders in sections using existing shadcn/ui primitives:

| Section | Controls | Condition |
|---|---|---|
| System Prompt | `<Textarea>` (monospace) | Always |
| Model | Provider `<Select>` → Model `<Select>` (chained) | Always |
| Sampling | Temperature `<Slider>`, Max Tokens `<Input>`, Top P `<Input>` | Always |
| Thinking | Enable `<Switch>`, Effort `<Select>`, Budget Tokens `<Input>` | `capabilities.thinking` and provider supports it |
| Structured Output | JSON schema `<Textarea>` with inline JSON validation | `capabilities.structuredOutput` |
| Tools | Tool definitions list with add/remove | `capabilities.tools` |

Provider and model options come from the existing provider registry already used elsewhere in the app.

### Feature integration

**Playground:**
- Location: inline collapsible panel alongside the query input
- Hook: `usePromptConfig` initialised from existing playground defaults
- Capabilities: `{ thinking: true }`
- Replaces: `instructions` textarea and `GenerationParameters.tsx` LLM param controls
- `usePlayground` hook: `instructions` state replaced by `promptConfig: PromptConfig`

**EvalRun create/clone form:**
- Location: labelled section in the form, between dataset picker and submit
- Hook: `usePromptConfig` initialised from cloned run's `llm_config` or defaults
- Capabilities: `{ thinking: true }`
- Replaces: `systemPrompt` textarea in `NewEvalRunPage.tsx`
- Clone flow: `EvalRunRead.llm_config` pre-populates the editor

**ExtractionSchema create/edit form:**
- Location: a "Prompt & Model" section within the existing schema editor UI
- Hook: `usePromptConfig` initialised from existing schema's `llm_config` or defaults
- Capabilities: `{ structuredOutput: false, thinking: false }` (extraction handles structured output via its own JSON schema field)
- Replaces: nothing (prompt editing is new for extraction)
- Additional field: a `user_prompt_template` textarea below `<PromptConfigEditor>`, with an inline helper note listing the available variables: `{schema_json}` and `{document_context}`
- This field is only shown for adapters that support prompt overrides (Ollama and OpenAI-compatible); hidden for LlamaExtract

### API client updates

- `frontend/src/api/playground.ts` — request type uses `llmConfig: PromptConfig` instead of `instructions`
- `frontend/src/api/eval-runs.ts` — request type uses `llmConfig: PromptConfig`; response type includes `llmConfig` for clone support
- `frontend/src/api/extraction-schemas.ts` — request and response types include `llmConfig: PromptConfig` and `userPromptTemplate: string | undefined`

---

## Extensibility path

### Adding a new feature (e.g. Classification, Golden Set)

1. Add `llm_config JSON` column to the feature's DB model + migration
2. Add `llm_config: PromptConfig | None` to the feature's create/read schemas
3. Pass `PromptConfig` into the service; call `resolve_llm_config()`
4. Embed `<PromptConfigEditor>` in the feature's UI with appropriate `capabilities`

### Phase 2: Named templates

`PromptConfig` becomes a named, owned DB entity:

```python
class PromptTemplate(Base):
    id: UUID
    name: str
    scope: Literal["global", "project"]
    project_id: UUID | None
    config: PromptConfig   # stored as JSON
```

Feature models add an optional FK: `prompt_template_id`. Per-use overrides remain as inline JSON on the feature model. The `<PromptConfigEditor>` gains a template picker at the top.

### Future additions to `PromptConfig` (no breaking changes)

- `few_shot_examples: list[{"role": "user"|"assistant", "content": str}] | None` — for agent few-shot configuration
- `vision: bool` — capability flag for multimodal models

---

## Open questions / known gaps

- Provider/model list in the frontend currently comes from the existing registry — confirm it covers all providers supported by `LLMRegistry`
- `structured_output` field accepts a raw `dict` — may want a lightweight JSON schema validator on the frontend before this is submitted
- `tools` field is `list[dict]` for now — a proper `ToolDefinition` type should be introduced when agents need it
