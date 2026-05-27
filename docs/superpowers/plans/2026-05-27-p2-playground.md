# Prompt Config — Plan 2: Playground Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `PromptConfig` into the Playground — replace the ad-hoc `instructions` string and separate `LLMConfigSchema` with a single `PromptConfig` field, and replace the existing LLM param controls with `<PromptConfigEditor>`.

**Architecture:** The playground is stateless (no DB migration). The backend `PlaygroundAnswerRequest` schema merges the existing `LLMConfigSchema` + `instructions` into `llm_config: PromptConfig | None`. `build_rag_prompt()` is updated to take `system_prompt` instead of `instructions`. The frontend hook and API client are updated to match.

**Tech Stack:** Python 3.12 / FastAPI / Pydantic v2 — React 18 / TypeScript / shadcn/ui

**Spec:** `docs/superpowers/specs/2026-05-27-unified-prompt-interface-design.md`

**Prerequisites:** Plan 1 complete (`PromptConfig` schema, `resolve_llm_config`, `PromptConfigEditor` component all exist).

**No DB migration required.**

---

## File Map

**Modified backend files:**
- `backend/app/schemas/playground.py` — remove `LLMConfigSchema` + `instructions`; add `llm_config: PromptConfig`
- `backend/app/services/llm/prompt.py` — replace `instructions` param with `system_prompt`; export `DEFAULT_RAG_SYSTEM_PROMPT`
- `backend/app/services/answer_service.py` — use `resolve_llm_config`; pass `system_prompt` to `build_rag_prompt`

**Modified frontend files:**
- `frontend/src/api/playground.ts` — update `PlaygroundAnswerRequest` type + request body
- `frontend/src/hooks/usePlayground.ts` — replace individual LLM state fields with `usePromptConfig`
- Playground page/component (identified by grep) — replace LLM param controls with `<PromptConfigEditor>`

---

## Task 1: Backend — playground schema + prompt builder

**Files:**
- Modify: `backend/app/schemas/playground.py`
- Modify: `backend/app/services/llm/prompt.py`

- [ ] **Step 1: Update playground schema**

Replace the entire contents of `backend/app/schemas/playground.py`:

```python
"""Request schemas for the Answer Playground endpoint."""
from pydantic import BaseModel, Field

from app.schemas.prompt_config import PromptConfig


class RetrievalConfig(BaseModel):
    """Retrieval parameters for the answer pipeline."""
    search_type: str = Field("hybrid", pattern="^(semantic|keyword|hybrid)$")
    top_k: int = Field(5, ge=1, le=50)
    similarity_threshold: float = Field(0.0, ge=0.0, le=1.0)


class PlaygroundAnswerRequest(BaseModel):
    """Request body for the SSE answer endpoint."""
    query: str = Field(..., min_length=1, max_length=2000)
    retrieval_config: RetrievalConfig = Field(default_factory=RetrievalConfig)
    llm_config: PromptConfig | None = None
```

- [ ] **Step 2: Update build_rag_prompt**

Replace the entire contents of `backend/app/services/llm/prompt.py`:

```python
"""RAG prompt construction for answer generation."""
from app.schemas.query import RetrievalResult

DEFAULT_RAG_SYSTEM_PROMPT = (
    "Answer the user's question using ONLY the provided context.\n"
    "Cite sources using [1], [2], etc. corresponding to the chunk numbers.\n"
    "If the context doesn't contain enough information, say so."
)


def build_rag_prompt(
    query: str,
    chunks: list[RetrievalResult],
    system_prompt: str | None = None,
) -> list[dict]:
    """Build the messages array for a RAG answer generation request.

    If system_prompt is provided it replaces the default entirely.
    """
    system_content = system_prompt or DEFAULT_RAG_SYSTEM_PROMPT
    context = "\n\n".join(
        f"[{i + 1}] {chunk.content}" for i, chunk in enumerate(chunks)
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
    ]
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/playground.py backend/app/services/llm/prompt.py
git commit -m "feat(playground): update PlaygroundAnswerRequest and build_rag_prompt for PromptConfig"
```

---

## Task 2: Backend — answer_service wiring

**Files:**
- Modify: `backend/app/services/answer_service.py`

Current file imports `LLMConfig` and constructs it manually from `request.llm_config.*` (the old `LLMConfigSchema`). It also reads `request.instructions` and passes it to `build_rag_prompt`.

- [ ] **Step 1: Add import**

At the top of `backend/app/services/answer_service.py`, add:

```python
from app.services.llm.prompt_config import resolve_llm_config
```

- [ ] **Step 2: Update Phase 2 — Build prompt**

Find the two `build_rag_prompt` call sites in `answer_service.py` (one inside a collector span, one outside). Both currently pass `instructions=request.instructions`. Replace them:

```python
# Phase 2: Build prompt
system_prompt = request.llm_config.system_prompt if request.llm_config else None
if collector:
    with collector.span("prompt_building", "Build RAG Prompt", input={
        "chunk_count": len(query_response.results),
        "has_system_prompt": bool(system_prompt),
    }) as s:
        messages = build_rag_prompt(
            query=request.query,
            chunks=query_response.results,
            system_prompt=system_prompt,
        )
        total_chars = sum(len(m.get("content", "")) for m in messages)
        s.output = {"message_count": len(messages), "total_chars": total_chars}
        s.metrics.char_count = total_chars
else:
    messages = build_rag_prompt(
        query=request.query,
        chunks=query_response.results,
        system_prompt=system_prompt,
    )
```

Also update the span input dict key from `has_instructions` to `has_system_prompt`.

- [ ] **Step 3: Update Phase 3 — LLMConfig construction**

Find the manual `LLMConfig(provider=request.llm_config.provider, ...)` construction (around line 97). Replace it:

```python
# Phase 3: Stream LLM response
llm_config = resolve_llm_config(
    request.llm_config,
    default_provider="openai",
    default_model="gpt-4o",
)
```

- [ ] **Step 4: Start backend — confirm no errors**

```
uv run --directory backend uvicorn app.main:app --reload
```

Expected: server starts cleanly. Stop with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/answer_service.py
git commit -m "feat(playground): wire resolve_llm_config and system_prompt into answer_service"
```

---

## Task 3: Frontend — playground API client

**Files:**
- Modify: `frontend/src/api/playground.ts`

- [ ] **Step 1: Update PlaygroundAnswerRequest type**

In `frontend/src/api/playground.ts`, replace the existing `PlaygroundAnswerRequest` interface:

```typescript
import type { PromptConfig } from '@/types/prompt-config'

export interface PlaygroundAnswerRequest {
  query: string
  retrievalConfig: {
    searchType: string
    topK: number
    similarityThreshold: number
  }
  llmConfig?: PromptConfig
}
```

- [ ] **Step 2: Update the fetch body in streamAnswer**

In `streamAnswer`, replace the existing `body: JSON.stringify({...})` with:

```typescript
body: JSON.stringify({
  query: params.query,
  retrieval_config: {
    search_type: params.retrievalConfig.searchType,
    top_k: params.retrievalConfig.topK,
    similarity_threshold: params.retrievalConfig.similarityThreshold,
  },
  llm_config: params.llmConfig ? {
    system_prompt: params.llmConfig.systemPrompt ?? null,
    provider: params.llmConfig.provider ?? null,
    model: params.llmConfig.model ?? null,
    temperature: params.llmConfig.temperature ?? null,
    max_tokens: params.llmConfig.maxTokens ?? null,
    top_p: params.llmConfig.topP ?? null,
    thinking: params.llmConfig.thinking ? {
      enabled: params.llmConfig.thinking.enabled,
      effort: params.llmConfig.thinking.effort ?? null,
      budget_tokens: params.llmConfig.thinking.budgetTokens ?? null,
    } : null,
    json_mode: params.llmConfig.jsonMode ?? false,
    structured_output: params.llmConfig.structuredOutput ?? null,
    tools: params.llmConfig.tools ?? null,
  } : null,
}),
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/playground.ts
git commit -m "feat(playground): update streamAnswer API to send PromptConfig"
```

---

## Task 4: Frontend — usePlayground hook

**Files:**
- Modify: `frontend/src/hooks/usePlayground.ts`

The current hook exposes individual state fields: `provider`, `setProvider`, `model`, `setModel`, `temperature`, `setTemperature`, `maxTokens`, `setMaxTokens`, `instructions`, `setInstructions`. These are replaced by `promptConfig` + `usePromptConfig`.

- [ ] **Step 1: Add imports**

At the top of `frontend/src/hooks/usePlayground.ts`, add:

```typescript
import { usePromptConfig } from './usePromptConfig'
import type { PromptConfig } from '@/types/prompt-config'
```

- [ ] **Step 2: Remove individual LLM state**

Remove these lines from the hook body:
```typescript
const [provider, setProviderRaw] = useState('openai')
const [model, setModel] = useState('gpt-4o')
const [temperature, setTemperature] = useState(0.0)
const [maxTokens, setMaxTokens] = useState(1024)
const [instructions, setInstructions] = useState('')
const setProvider = useCallback((p: string) => { ... })
```

Remove `LLM_MODEL_OPTIONS` export if it is only used by the removed setProvider logic (check with grep first — it may be used in UI components directly).

- [ ] **Step 3: Add usePromptConfig**

Add after the existing retrieval state declarations:

```typescript
const { promptConfig, setPromptConfig, setProvider: setPromptConfigProvider } = usePromptConfig()
```

- [ ] **Step 4: Update UsePlaygroundReturn interface**

Remove: `provider`, `setProvider`, `model`, `setModel`, `temperature`, `setTemperature`, `maxTokens`, `setMaxTokens`, `instructions`, `setInstructions`

Add:
```typescript
promptConfig: PromptConfig
setPromptConfig: (config: PromptConfig) => void
setPromptConfigProvider: (provider: string) => void
```

- [ ] **Step 5: Update runSearch to use promptConfig**

Find the `streamAnswer` call in `runSearch`. It currently passes `llmConfig` built from the individual fields. Replace with:

```typescript
await streamAnswer(
  projectId,
  indexId,
  {
    query,
    retrievalConfig: { searchType, topK, similarityThreshold: threshold },
    llmConfig: promptConfig,
  },
  // ... callbacks unchanged ...
)
```

- [ ] **Step 6: Update return statement**

Remove the individual LLM fields from the return. Add:
```typescript
promptConfig,
setPromptConfig,
setPromptConfigProvider,
```

- [ ] **Step 7: Fix affected playground UI components**

Find all components that destructure the removed fields:
```
grep -rn "instructions\|setInstructions\|setProvider\|setModel\|setTemperature\|setMaxTokens" frontend/src/pages frontend/src/components --include="*.tsx" -l
```

For each file found, replace destructured LLM field accesses with `promptConfig` / `setPromptConfig`. Replace the LLM parameter controls section in the JSX with:

```tsx
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'

<PromptConfigEditor
  value={promptConfig}
  onChange={setPromptConfig}
  onProviderChange={setPromptConfigProvider}
  capabilities={{ thinking: true }}
/>
```

- [ ] **Step 8: Build frontend**

```
npm --prefix frontend run build
```

Fix any TypeScript errors before proceeding.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/hooks/usePlayground.ts
git commit -m "feat(playground): replace individual LLM state with usePromptConfig in usePlayground"
```

---

## Task 5: Smoke test

- [ ] **Step 1: Start backend + frontend**

```
uv run --directory backend uvicorn app.main:app --reload
npm --prefix frontend run dev
```

- [ ] **Step 2: Test in browser**

1. Navigate to any index → Playground tab
2. Switch to Answer mode
3. Confirm `<PromptConfigEditor>` is visible — system prompt, provider, model, temperature, max tokens
4. Enter a custom system prompt, run a query — verify the answer reflects it
5. Change provider → confirm model dropdown updates automatically
6. Open Advanced — confirm Top P field is present

- [ ] **Step 3: Final commit (if any cleanup needed)**

```bash
git add -p
git commit -m "feat(playground): unified prompt interface — playground complete"
```
