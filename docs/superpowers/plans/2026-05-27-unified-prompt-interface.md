# Unified Prompt Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a shared `PromptConfig` abstraction so that Playground, Evals, and Extraction all expose a consistent system-prompt + LLM-parameter editing surface, backed by a single reusable frontend component.

**Architecture:** A new `PromptConfig` Pydantic model (stored as JSON in the DB where needed) replaces ad-hoc `instructions`/`system_prompt` fields across features. A `resolve_llm_config()` translation function converts `PromptConfig` into the existing adapter-facing `LLMConfig`. A single `<PromptConfigEditor>` React component renders the editor surface and is embedded inline (Playground) or in a form section (Evals, Extraction).

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic / Pydantic v2 — React 18 / TypeScript / shadcn/ui / Tailwind CSS / Vitest

**Spec:** `docs/superpowers/specs/2026-05-27-unified-prompt-interface-design.md`

---

## File Map

**New backend files:**
- `backend/app/schemas/prompt_config.py` — `ThinkingConfig`, `PromptConfig` Pydantic models
- `backend/app/services/llm/prompt_config.py` — `resolve_llm_config()` translation function
- `backend/tests/services/llm/test_prompt_config.py` — unit tests for above

**New frontend files:**
- `frontend/src/types/prompt-config.ts` — TypeScript types
- `frontend/src/hooks/usePromptConfig.ts` — state management hook
- `frontend/src/components/shared/PromptConfigEditor.tsx` — reusable editor component

**Modified backend files:**
- `backend/app/models/eval_run.py` — replace `system_prompt TEXT` with `llm_config JSON`
- `backend/app/models/extraction_schema.py` — add `llm_config JSON` + `user_prompt_template TEXT`
- `backend/app/repositories/eval_run_repository.py` — replace `system_prompt` param with `llm_config`
- `backend/app/repositories/extraction_schema_repository.py` — add `llm_config`/`user_prompt_template` to create/update
- `backend/app/schemas/playground.py` — remove `LLMConfigSchema` + `instructions`; add `llm_config: PromptConfig`
- `backend/app/schemas/eval_run.py` — replace `system_prompt` with `llm_config`; add to response
- `backend/app/schemas/extraction_result.py` — add `llm_config` + `user_prompt_template` to create/update/response
- `backend/app/services/llm/prompt.py` — update `build_rag_prompt` signature
- `backend/app/services/answer_service.py` — use `resolve_llm_config` + new prompt signature
- `backend/app/services/answer_generation_service.py` — accept `PromptConfig | None`
- `backend/app/services/eval_service.py` — use `llm_config` in create/get_run_config
- `backend/app/services/extraction_service.py` — pass `llm_config` + `user_prompt_template` into adapter cfg

**Modified frontend files:**
- `frontend/src/api/playground.ts` — update `PlaygroundAnswerRequest`
- `frontend/src/api/eval-runs.ts` — update create request + response types
- `frontend/src/types/extraction.ts` — add `llmConfig` + `userPromptTemplate` fields
- `frontend/src/hooks/usePlayground.ts` — replace individual LLM params + `instructions` with `promptConfig`
- `frontend/src/pages/NewEvalRunPage.tsx` — replace `systemPrompt` textarea with `<PromptConfigEditor>`
- `frontend/src/components/extraction/ExtractionSchemaEditor.tsx` — add `<PromptConfigEditor>` + template textarea

---

## Task 1: PromptConfig schema + resolve_llm_config

**Files:**
- Create: `backend/app/schemas/prompt_config.py`
- Create: `backend/app/services/llm/prompt_config.py`
- Create: `backend/tests/services/llm/test_prompt_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/services/llm/test_prompt_config.py
import pytest
from app.schemas.prompt_config import PromptConfig, ThinkingConfig
from app.services.llm.prompt_config import resolve_llm_config
from app.services.llm.types import LLMConfig


def test_resolve_basic_fields():
    config = PromptConfig(provider="openai", model="gpt-4o", temperature=0.7, max_tokens=2048)
    result = resolve_llm_config(config)
    assert isinstance(result, LLMConfig)
    assert result.provider == "openai"
    assert result.model == "gpt-4o"
    assert result.temperature == 0.7
    assert result.max_tokens == 2048


def test_resolve_uses_defaults_when_provider_model_null():
    config = PromptConfig()
    result = resolve_llm_config(config, default_provider="anthropic", default_model="claude-sonnet-4-6")
    assert result.provider == "anthropic"
    assert result.model == "claude-sonnet-4-6"


def test_resolve_uses_default_temperature_and_tokens():
    config = PromptConfig(provider="openai", model="gpt-4o")
    result = resolve_llm_config(config, default_temperature=0.5, default_max_tokens=2048)
    assert result.temperature == 0.5
    assert result.max_tokens == 2048


def test_resolve_explicit_temperature_overrides_default():
    config = PromptConfig(provider="openai", model="gpt-4o", temperature=0.9)
    result = resolve_llm_config(config, default_temperature=0.0)
    assert result.temperature == 0.9


def test_resolve_structured_output_sets_json_mode():
    config = PromptConfig(provider="openai", model="gpt-4o", structured_output={"type": "object"})
    result = resolve_llm_config(config)
    assert result.json_mode is True


def test_resolve_json_mode_passthrough():
    config = PromptConfig(provider="openai", model="gpt-4o", json_mode=True)
    result = resolve_llm_config(config)
    assert result.json_mode is True


def test_prompt_config_defaults():
    config = PromptConfig()
    assert config.provider is None
    assert config.model is None
    assert config.system_prompt is None
    assert config.temperature is None
    assert config.max_tokens is None
    assert config.thinking is None
    assert config.json_mode is False
    assert config.structured_output is None
    assert config.tools is None


def test_thinking_config_defaults():
    t = ThinkingConfig(enabled=True)
    assert t.effort is None
    assert t.budget_tokens is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/services/llm/test_prompt_config.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — the modules don't exist yet.

- [ ] **Step 3: Create the PromptConfig schema**

```python
# backend/app/schemas/prompt_config.py
"""Shared PromptConfig schema used across all LLM-using features."""
from __future__ import annotations
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ThinkingConfig(BaseModel):
    """Provider-agnostic reasoning/thinking control."""
    enabled: bool = True
    effort: Literal["low", "medium", "high"] | None = None
    budget_tokens: int | None = Field(None, alias="budgetTokens")

    model_config = ConfigDict(populate_by_name=True)


class PromptConfig(BaseModel):
    """User-expressed LLM configuration.

    Stores what the user configured. Converted to adapter-ready LLMConfig
    via resolve_llm_config() before being passed to LLM adapters.
    provider/model are nullable — None means use the feature's default.
    """
    system_prompt: str | None = Field(None, alias="systemPrompt")
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = Field(None, alias="maxTokens")
    top_p: float | None = Field(None, alias="topP")
    thinking: ThinkingConfig | None = None
    json_mode: bool = Field(False, alias="jsonMode")
    structured_output: dict | None = Field(None, alias="structuredOutput")
    tools: list[dict] | None = None

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 4: Create resolve_llm_config**

```python
# backend/app/services/llm/prompt_config.py
"""Translates user-expressed PromptConfig into adapter-ready LLMConfig."""
from app.schemas.prompt_config import PromptConfig
from app.services.llm.types import LLMConfig


def resolve_llm_config(
    config: PromptConfig | None,
    default_provider: str = "openai",
    default_model: str = "gpt-4o",
    default_temperature: float = 0.0,
    default_max_tokens: int = 1024,
) -> LLMConfig:
    """Convert a PromptConfig into an adapter-ready LLMConfig.

    Falls back to supplied defaults for any field that is None.
    thinking/tools/top_p are stored on PromptConfig but not yet forwarded
    to adapters — add per-provider translation here when adapters support them.
    """
    if config is None:
        return LLMConfig(
            provider=default_provider,
            model=default_model,
            temperature=default_temperature,
            max_tokens=default_max_tokens,
        )

    return LLMConfig(
        provider=config.provider or default_provider,
        model=config.model or default_model,
        temperature=config.temperature if config.temperature is not None else default_temperature,
        max_tokens=config.max_tokens if config.max_tokens is not None else default_max_tokens,
        json_mode=bool(config.structured_output) or config.json_mode,
    )
```

- [ ] **Step 5: Run tests — expect green**

```
uv run --directory backend python -m pytest tests/services/llm/test_prompt_config.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/prompt_config.py backend/app/services/llm/prompt_config.py backend/tests/services/llm/test_prompt_config.py
git commit -m "feat(prompt): add PromptConfig schema and resolve_llm_config"
```

---

## Task 2: EvalRun DB — model + migration + repository

**Files:**
- Modify: `backend/app/models/eval_run.py:73`
- Modify: `backend/app/repositories/eval_run_repository.py:18-54`
- New migration (generated via alembic)

- [ ] **Step 1: Update the EvalRun model**

In `backend/app/models/eval_run.py`, replace line 73:
```python
# Remove this:
system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

# Add this:
llm_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

The import `Text` can be removed from the import line if it's no longer used elsewhere in the file. Check: `Text` is also used for `error_message` on line 62, so keep it.

- [ ] **Step 2: Generate the Alembic migration**

```
uv run --directory backend alembic revision --autogenerate -m "eval_run_system_prompt_to_llm_config"
```

Open the generated file in `backend/alembic/versions/`. Replace the generated `upgrade()` and `downgrade()` with:

```python
def upgrade() -> None:
    op.add_column('eval_runs', sa.Column('llm_config', sa.JSON(), nullable=True))
    # Backfill: move existing system_prompt values into llm_config JSON
    op.execute(
        "UPDATE eval_runs "
        "SET llm_config = jsonb_build_object('system_prompt', system_prompt) "
        "WHERE system_prompt IS NOT NULL"
    )
    op.drop_column('eval_runs', 'system_prompt')


def downgrade() -> None:
    op.add_column('eval_runs', sa.Column('system_prompt', sa.Text(), nullable=True))
    op.execute(
        "UPDATE eval_runs "
        "SET system_prompt = llm_config->>'system_prompt' "
        "WHERE llm_config IS NOT NULL AND llm_config ? 'system_prompt'"
    )
    op.drop_column('eval_runs', 'llm_config')
```

- [ ] **Step 3: Apply the migration**

```
uv run --directory backend alembic upgrade head
```

Expected: `Running upgrade <prev> -> <new>, eval_run_system_prompt_to_llm_config`

- [ ] **Step 4: Update the repository**

In `backend/app/repositories/eval_run_repository.py`, update `create()` — replace `system_prompt` param with `llm_config`:

```python
async def create(
    self,
    project_id: UUID,
    golden_set_id: UUID,
    index_id: UUID,
    name: str,
    config: dict,
    user_id: UUID,
    mode: str = "retrieval_only",
    generation_model_provider: str | None = None,
    generation_model_id: str | None = None,
    judge_model_provider: str | None = None,
    judge_model_id: str | None = None,
    llm_config: dict | None = None,
    experiment_id: UUID | None = None,
    variant_label: str | None = None,
) -> EvalRun:
    run = EvalRun(
        project_id=project_id,
        golden_set_id=golden_set_id,
        index_id=index_id,
        name=name,
        config=config,
        created_by=user_id,
        mode=mode,
        generation_model_provider=generation_model_provider,
        generation_model_id=generation_model_id,
        judge_model_provider=judge_model_provider,
        judge_model_id=judge_model_id,
        llm_config=llm_config,
        experiment_id=experiment_id,
        variant_label=variant_label,
    )
    self.session.add(run)
    await self.session.commit()
    await self.session.refresh(run)
    return run
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/eval_run.py backend/app/repositories/eval_run_repository.py backend/alembic/versions/
git commit -m "feat(eval): replace system_prompt TEXT with llm_config JSON on EvalRun"
```

---

## Task 3: ExtractionSchema DB — model + migration + repository

**Files:**
- Modify: `backend/app/models/extraction_schema.py`
- Modify: `backend/app/repositories/extraction_schema_repository.py`
- New migration

- [ ] **Step 1: Update the ExtractionSchema model**

In `backend/app/models/extraction_schema.py`, add two columns after `extraction_target`:

```python
llm_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
user_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Add `Text` to the import line if not already present:
```python
from sqlalchemy import DateTime, ForeignKey, String, Text, JSON
```

- [ ] **Step 2: Generate and fill in the migration**

```
uv run --directory backend alembic revision --autogenerate -m "extraction_schema_add_llm_config"
```

The autogenerated `upgrade()` should contain `add_column` calls. Verify it looks like:

```python
def upgrade() -> None:
    op.add_column('extraction_schemas', sa.Column('llm_config', sa.JSON(), nullable=True))
    op.add_column('extraction_schemas', sa.Column('user_prompt_template', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('extraction_schemas', 'user_prompt_template')
    op.drop_column('extraction_schemas', 'llm_config')
```

- [ ] **Step 3: Apply the migration**

```
uv run --directory backend alembic upgrade head
```

- [ ] **Step 4: Update the repository — create**

In `backend/app/repositories/extraction_schema_repository.py`, update `create()`:

```python
async def create(
    self,
    project_id: UUID,
    name: str,
    schema_definition: dict,
    created_by: UUID,
    description: str | None = None,
    extraction_target: str = "PER_DOC",
    llm_config: dict | None = None,
    user_prompt_template: str | None = None,
) -> ExtractionSchema:
    schema = ExtractionSchema(
        project_id=project_id,
        name=name,
        description=description,
        schema_definition=schema_definition,
        extraction_target=extraction_target,
        created_by=created_by,
        llm_config=llm_config,
        user_prompt_template=user_prompt_template,
    )
    self.session.add(schema)
    await self.session.commit()
    await self.session.refresh(schema)
    return schema
```

- [ ] **Step 5: Update the repository — update**

In `backend/app/repositories/extraction_schema_repository.py`, update `update()`:

```python
async def update(
    self,
    schema_id: UUID,
    user_id: UUID,
    name: str | None = None,
    description: str | None = None,
    schema_definition: dict | None = None,
    extraction_target: str | None = None,
    llm_config: dict | None = None,
    user_prompt_template: str | None = None,
) -> ExtractionSchema | None:
    schema = await self.get_by_id_for_user(schema_id, user_id)
    if not schema:
        return None

    if name is not None:
        schema.name = name
    if description is not None:
        schema.description = description
    if schema_definition is not None:
        schema.schema_definition = schema_definition
    if extraction_target is not None:
        schema.extraction_target = extraction_target
    if llm_config is not None:
        schema.llm_config = llm_config
    if user_prompt_template is not None:
        schema.user_prompt_template = user_prompt_template

    await self.session.commit()
    await self.session.refresh(schema)
    return schema
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/extraction_schema.py backend/app/repositories/extraction_schema_repository.py backend/alembic/versions/
git commit -m "feat(extraction): add llm_config and user_prompt_template to ExtractionSchema"
```

---

## Task 4: Wire Playground backend

**Files:**
- Modify: `backend/app/schemas/playground.py`
- Modify: `backend/app/services/llm/prompt.py`
- Modify: `backend/app/services/answer_service.py`

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

- [ ] **Step 3: Update answer_service.py**

In `backend/app/services/answer_service.py`, make the following changes:

1. Add import at the top:
```python
from app.services.llm.prompt_config import resolve_llm_config
```

2. Remove the `OpenAIAdapter` hard-coded import and use the registry instead. Keep `OpenAIAdapter` for now if changing to registry is out of scope — just update the LLMConfig construction and prompt building.

3. Update Phase 2 (Build prompt) — change both call sites from `instructions=request.instructions` to `system_prompt=request.llm_config.system_prompt if request.llm_config else None`:

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

4. Update Phase 3 (Stream LLM response) — replace the manual `LLMConfig(...)` construction:

```python
# Phase 3: Stream LLM response
llm_config = resolve_llm_config(
    request.llm_config,
    default_provider="openai",
    default_model="gpt-4o",
)
```

- [ ] **Step 4: Run the backend to confirm no import errors**

```
uv run --directory backend uvicorn app.main:app --reload
```

Expected: server starts without errors. Stop with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/playground.py backend/app/services/llm/prompt.py backend/app/services/answer_service.py
git commit -m "feat(playground): replace instructions + LLMConfigSchema with PromptConfig"
```

---

## Task 5: Wire EvalRun backend

**Files:**
- Modify: `backend/app/schemas/eval_run.py`
- Modify: `backend/app/services/answer_generation_service.py`
- Modify: `backend/app/services/eval_service.py`

- [ ] **Step 1: Update EvalRunCreate and EvalRunResponse schemas**

In `backend/app/schemas/eval_run.py`:

1. Add import at top of file:
```python
from app.schemas.prompt_config import PromptConfig
```

2. In `EvalRunCreate`, replace the `system_prompt` field:
```python
# Remove:
system_prompt: str | None = Field(None, alias="systemPrompt")

# Add:
llm_config: PromptConfig | None = Field(None, alias="llmConfig")
```

3. In `EvalRunResponse`, add `llm_config` so the frontend can repopulate on clone:
```python
system_prompt: str | None = Field(None, alias="systemPrompt")  # REMOVE
llm_config: dict | None = Field(None, alias="llmConfig")        # ADD
```

- [ ] **Step 2: Update answer_generation_service.py**

Replace the entire contents of `backend/app/services/answer_generation_service.py`:

```python
"""Answer generation service for eval runs."""
import logging

from app.schemas.prompt_config import PromptConfig
from app.services.llm.types import LLMConfig, CompletionResult
from app.services.llm.port import LLMPort
from app.services.llm.prompt import DEFAULT_RAG_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


async def generate_answer(
    question: str,
    chunks: list[dict],
    generation_adapter: LLMPort,
    generation_config: LLMConfig,
    prompt_config: PromptConfig | None = None,
) -> str:
    """Generate an answer from retrieved chunks using an LLM."""
    sys_prompt = (
        prompt_config.system_prompt
        if prompt_config and prompt_config.system_prompt
        else DEFAULT_RAG_SYSTEM_PROMPT
    )

    context = "\n\n".join(
        f"[{i + 1}] {chunk.get('content', '')}"
        for i, chunk in enumerate(chunks)
    )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]

    result: CompletionResult = await generation_adapter.complete(messages, generation_config)
    return result.content
```

- [ ] **Step 3: Update eval_service.py — imports + create_run**

In `backend/app/services/eval_service.py`:

1. Update imports at the top of the file:
```python
# Remove DEFAULT_SYSTEM_PROMPT from this import:
from app.services.answer_generation_service import generate_answer, DEFAULT_SYSTEM_PROMPT
# Replace with:
from app.services.answer_generation_service import generate_answer
from app.schemas.prompt_config import PromptConfig as PromptConfigSchema
```

2. In `create_run`, replace `system_prompt=data.system_prompt` with `llm_config=...`:

```python
run = await self.eval_repo.create(
    project_id=project_id,
    golden_set_id=data.golden_set_id,
    index_id=data.index_id,
    name=name,
    config=data.config.model_dump(by_alias=True),
    user_id=user_id,
    mode=data.mode,
    generation_model_provider=data.generation_model.provider if data.generation_model else None,
    generation_model_id=data.generation_model.model_id if data.generation_model else None,
    judge_model_provider=data.judge_model.provider if data.judge_model else None,
    judge_model_id=data.judge_model.model_id if data.judge_model else None,
    llm_config=data.llm_config.model_dump(by_alias=False, mode="json") if data.llm_config else None,
    experiment_id=data.experiment_id,
    variant_label=data.variant_label,
)
```

3. In `get_run_config`, replace `"systemPrompt": run.system_prompt` with `"llmConfig": run.llm_config`:

```python
return {
    "goldenSetId": str(run.golden_set_id),
    "indexId": str(run.index_id),
    "name": run.name,
    "config": run.config,
    "mode": run.mode,
    "generationModel": {
        "provider": run.generation_model_provider,
        "modelId": run.generation_model_id,
    } if run.generation_model_provider else None,
    "judgeModel": {
        "provider": run.judge_model_provider,
        "modelId": run.judge_model_id,
    } if run.judge_model_provider else None,
    "llmConfig": run.llm_config,
    "experimentId": str(run.experiment_id) if run.experiment_id else None,
    "variantLabel": run.variant_label,
}
```

4. Find and update the `generate_answer` call site in the run execution loop:

```
grep -n "generate_answer\|system_prompt\|gen_config\|generation_config" backend/app/services/eval_service.py
```

In that method, the existing code builds a `gen_config` from `run.generation_model_*` columns and calls `generate_answer(..., system_prompt=run.system_prompt)`. Replace with:

```python
# Reconstruct PromptConfig from stored JSON (PromptConfigSchema already imported at top)
prompt_config = PromptConfigSchema.model_validate(run.llm_config) if run.llm_config else None

# Build gen_config — provider/model from generation_model columns; sampling from llm_config
lc = run.llm_config or {}
gen_config = LLMConfig(
    provider=run.generation_model_provider,
    model=run.generation_model_id,
    temperature=lc.get("temperature", 0.0),
    max_tokens=lc.get("max_tokens", 1024),
)

# In the generate_answer call, replace system_prompt= with prompt_config=:
generated_answer = await generate_answer(
    question=query_text,
    chunks=chunks,
    generation_adapter=generation_adapter,
    generation_config=gen_config,
    prompt_config=prompt_config,
)
```

- [ ] **Step 4: Update _to_response in eval_service.py**

Find the `_to_response` method (grep: `grep -n "_to_response" backend/app/services/eval_service.py`). Add `llmConfig=run.llm_config` alongside the existing field assignments — do not remove any existing fields, just add this one:

- [ ] **Step 5: Run backend**

```
uv run --directory backend uvicorn app.main:app --reload
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/eval_run.py backend/app/services/answer_generation_service.py backend/app/services/eval_service.py
git commit -m "feat(eval): replace system_prompt with llm_config in EvalRun API and service"
```

---

## Task 6: Wire Extraction backend

**Files:**
- Modify: `backend/app/schemas/extraction_result.py`
- Modify: `backend/app/services/extraction_service.py`

- [ ] **Step 1: Update extraction schemas**

In `backend/app/schemas/extraction_result.py`:

1. Add import:
```python
from app.schemas.prompt_config import PromptConfig
```

2. Add fields to `ExtractionSchemaCreate`:
```python
class ExtractionSchemaCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    schema_definition: dict = Field(..., alias="schemaDefinition")
    extraction_target: str = Field("PER_DOC", alias="extractionTarget")
    llm_config: PromptConfig | None = Field(None, alias="llmConfig")
    user_prompt_template: str | None = Field(None, alias="userPromptTemplate")

    model_config = ConfigDict(populate_by_name=True)
```

3. Add fields to `ExtractionSchemaUpdate`:
```python
class ExtractionSchemaUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    schema_definition: dict | None = Field(None, alias="schemaDefinition")
    extraction_target: str | None = Field(None, alias="extractionTarget")
    llm_config: PromptConfig | None = Field(None, alias="llmConfig")
    user_prompt_template: str | None = Field(None, alias="userPromptTemplate")

    model_config = ConfigDict(populate_by_name=True)
```

4. Add fields to `ExtractionSchemaResponse` and `from_orm_model`:
```python
class ExtractionSchemaResponse(BaseModel):
    id: UUID = Field(..., alias="id")
    project_id: UUID = Field(..., alias="projectId")
    name: str
    description: str | None = None
    schema_definition: dict = Field(..., alias="schemaDefinition")
    extraction_target: str = Field(..., alias="extractionTarget")
    llm_config: dict | None = Field(None, alias="llmConfig")
    user_prompt_template: str | None = Field(None, alias="userPromptTemplate")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_model(cls, obj) -> "ExtractionSchemaResponse":
        return cls(
            id=obj.id,
            projectId=obj.project_id,
            name=obj.name,
            description=obj.description,
            schemaDefinition=obj.schema_definition,
            extractionTarget=obj.extraction_target,
            llmConfig=obj.llm_config,
            userPromptTemplate=obj.user_prompt_template,
            createdBy=obj.created_by,
            createdAt=obj.created_at,
            updatedAt=obj.updated_at,
        )
```

- [ ] **Step 2: Update extraction_service — create_schema**

In `backend/app/services/extraction_service.py`, update `create_schema`:

```python
async def create_schema(
    self,
    project_id: UUID,
    user_id: UUID,
    name: str,
    schema_definition: dict,
    description: str | None = None,
    extraction_target: str = "PER_DOC",
    llm_config: dict | None = None,
    user_prompt_template: str | None = None,
) -> ExtractionSchemaResponse:
    try:
        schema = await self.schema_repo.create(
            project_id=project_id, name=name, schema_definition=schema_definition,
            created_by=user_id, description=description, extraction_target=extraction_target,
            llm_config=llm_config, user_prompt_template=user_prompt_template,
        )
    except Exception as e:
        if "uq_extraction_schemas_project_name" in str(e):
            raise ConflictError(f"Schema with name '{name}' already exists in this project")
        raise
    return ExtractionSchemaResponse.from_orm_model(schema)
```

- [ ] **Step 3: Update extraction_service — update_schema**

```python
async def update_schema(
    self,
    schema_id: UUID,
    user_id: UUID,
    name: str | None = None,
    description: str | None = None,
    schema_definition: dict | None = None,
    extraction_target: str | None = None,
    llm_config: dict | None = None,
    user_prompt_template: str | None = None,
) -> ExtractionSchemaResponse:
    schema = await self.schema_repo.update(
        schema_id=schema_id, user_id=user_id, name=name, description=description,
        schema_definition=schema_definition, extraction_target=extraction_target,
        llm_config=llm_config, user_prompt_template=user_prompt_template,
    )
    if not schema:
        raise NotFoundError(f"Extraction schema {schema_id} not found")
    return ExtractionSchemaResponse.from_orm_model(schema)
```

- [ ] **Step 4: Wire llm_config into run_extraction adapter config**

In `extraction_service.py`, update `run_extraction` to merge `schema.llm_config` and `schema.user_prompt_template` into `merged_config`:

```python
merged_config = dict(config or {})
merged_config["extraction_target"] = schema.extraction_target
# Merge stored llm_config into adapter cfg (system_prompt, model params, etc.)
if schema.llm_config:
    for key in ("system_prompt", "model", "temperature", "max_tokens"):
        if key in schema.llm_config and key not in merged_config:
            merged_config[key] = schema.llm_config[key]
if schema.user_prompt_template and "user_prompt_template" not in merged_config:
    merged_config["user_prompt_template"] = schema.user_prompt_template
```

- [ ] **Step 5: Find and update the router — check that create/update router passes new fields**

Find `backend/app/routers/extraction.py`. Locate the create and update route handlers. Update the `create_schema` service call to pass `llm_config` and `user_prompt_template` from the request body:

```python
# In the create route:
await service.create_schema(
    project_id=project_id,
    user_id=current_user.id,
    name=body.name,
    schema_definition=body.schema_definition,
    description=body.description,
    extraction_target=body.extraction_target,
    llm_config=body.llm_config.model_dump(by_alias=False, mode="json") if body.llm_config else None,
    user_prompt_template=body.user_prompt_template,
)

# In the update route:
await service.update_schema(
    schema_id=schema_id,
    user_id=current_user.id,
    name=body.name,
    description=body.description,
    schema_definition=body.schema_definition,
    extraction_target=body.extraction_target,
    llm_config=body.llm_config.model_dump(by_alias=False, mode="json") if body.llm_config else None,
    user_prompt_template=body.user_prompt_template,
)
```

- [ ] **Step 6: Run backend**

```
uv run --directory backend uvicorn app.main:app --reload
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/extraction_result.py backend/app/services/extraction_service.py backend/app/routers/extraction.py
git commit -m "feat(extraction): add llm_config and user_prompt_template to ExtractionSchema"
```

---

## Task 7: Frontend types and usePromptConfig hook

**Files:**
- Create: `frontend/src/types/prompt-config.ts`
- Create: `frontend/src/hooks/usePromptConfig.ts`

- [ ] **Step 1: Create TypeScript types**

```typescript
// frontend/src/types/prompt-config.ts
export interface ThinkingConfig {
  enabled: boolean
  effort?: 'low' | 'medium' | 'high'
  budgetTokens?: number
}

export interface PromptConfig {
  systemPrompt?: string
  provider?: string
  model?: string
  temperature?: number
  maxTokens?: number
  topP?: number
  thinking?: ThinkingConfig
  jsonMode?: boolean
  structuredOutput?: Record<string, unknown>
  tools?: unknown[]
}

export interface PromptConfigCapabilities {
  thinking?: boolean
  structuredOutput?: boolean
  tools?: boolean
}

export const PROVIDER_MODEL_OPTIONS: Record<string, { value: string; label: string }[]> = {
  openai: [
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
    { value: 'gpt-4.1', label: 'GPT-4.1' },
    { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
    { value: 'o3', label: 'o3' },
    { value: 'o4-mini', label: 'o4-mini' },
  ],
  anthropic: [
    { value: 'claude-opus-4-7', label: 'Claude Opus 4.7' },
    { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
    { value: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5' },
  ],
  ollama: [],
}

export const PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'ollama', label: 'Ollama (local)' },
]

export const THINKING_PROVIDERS = new Set(['openai', 'anthropic', 'deepseek'])

export const DEFAULT_PROMPT_CONFIG: PromptConfig = {
  provider: 'openai',
  model: 'gpt-4o',
  temperature: 0.0,
  maxTokens: 1024,
}
```

- [ ] **Step 2: Create usePromptConfig hook**

```typescript
// frontend/src/hooks/usePromptConfig.ts
import { useState, useCallback } from 'react'
import type { PromptConfig } from '@/types/prompt-config'
import { DEFAULT_PROMPT_CONFIG, PROVIDER_MODEL_OPTIONS } from '@/types/prompt-config'

export function usePromptConfig(initial?: Partial<PromptConfig>) {
  const [promptConfig, setPromptConfig] = useState<PromptConfig>({
    ...DEFAULT_PROMPT_CONFIG,
    ...initial,
  })

  const updatePromptConfig = useCallback((updates: Partial<PromptConfig>) => {
    setPromptConfig((prev) => ({ ...prev, ...updates }))
  }, [])

  const setProvider = useCallback((provider: string) => {
    const models = PROVIDER_MODEL_OPTIONS[provider]
    const firstModel = models?.[0]?.value
    setPromptConfig((prev) => ({
      ...prev,
      provider,
      model: firstModel ?? prev.model,
      // Reset provider-specific fields
      thinking: undefined,
    }))
  }, [])

  const resetToDefaults = useCallback(() => {
    setPromptConfig({ ...DEFAULT_PROMPT_CONFIG, ...initial })
  }, [initial])

  return { promptConfig, updatePromptConfig, setProvider, resetToDefaults, setPromptConfig }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/prompt-config.ts frontend/src/hooks/usePromptConfig.ts
git commit -m "feat(prompt): add PromptConfig types and usePromptConfig hook"
```

---

## Task 8: PromptConfigEditor component

**Files:**
- Create: `frontend/src/components/shared/PromptConfigEditor.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/shared/PromptConfigEditor.tsx
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PromptConfig, PromptConfigCapabilities } from '@/types/prompt-config'
import {
  PROVIDERS,
  PROVIDER_MODEL_OPTIONS,
  THINKING_PROVIDERS,
} from '@/types/prompt-config'

interface PromptConfigEditorProps {
  value: PromptConfig
  onChange: (config: PromptConfig) => void
  onProviderChange?: (provider: string) => void
  capabilities?: PromptConfigCapabilities
  className?: string
}

export function PromptConfigEditor({
  value,
  onChange,
  onProviderChange,
  capabilities = {},
  className,
}: PromptConfigEditorProps) {
  const modelOptions = value.provider ? (PROVIDER_MODEL_OPTIONS[value.provider] ?? []) : []
  const supportsThinking = capabilities.thinking && THINKING_PROVIDERS.has(value.provider ?? '')

  const update = (patch: Partial<PromptConfig>) => onChange({ ...value, ...patch })

  return (
    <div className={cn('space-y-4', className)}>
      {/* System Prompt */}
      <div className="space-y-1.5">
        <Label>System Prompt</Label>
        <Textarea
          className="font-mono text-sm min-h-[120px]"
          placeholder="Leave empty to use the default system prompt…"
          value={value.systemPrompt ?? ''}
          onChange={(e) => update({ systemPrompt: e.target.value || undefined })}
        />
      </div>

      {/* Provider + Model */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>Provider</Label>
          <Select
            value={value.provider ?? ''}
            onValueChange={(p) => {
              onProviderChange?.(p)
              const models = PROVIDER_MODEL_OPTIONS[p]
              update({ provider: p, model: models?.[0]?.value ?? value.model, thinking: undefined })
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select provider" />
            </SelectTrigger>
            <SelectContent>
              {PROVIDERS.map((p) => (
                <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Model</Label>
          {value.provider === 'ollama' ? (
            <Input
              placeholder="e.g. llama3.2"
              value={value.model ?? ''}
              onChange={(e) => update({ model: e.target.value || undefined })}
            />
          ) : (
            <Select
              value={value.model ?? ''}
              onValueChange={(m) => update({ model: m })}
              disabled={!modelOptions.length}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select model" />
              </SelectTrigger>
              <SelectContent>
                {modelOptions.map((m) => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      </div>

      {/* Temperature */}
      <div className="space-y-1.5">
        <div className="flex justify-between">
          <Label>Temperature</Label>
          <span className="text-sm text-muted-foreground">{value.temperature ?? 0}</span>
        </div>
        <Slider
          min={0}
          max={2}
          step={0.05}
          value={[value.temperature ?? 0]}
          onValueChange={([v]) => update({ temperature: v })}
        />
      </div>

      {/* Max Tokens */}
      <div className="space-y-1.5">
        <Label>Max Tokens</Label>
        <Input
          type="number"
          min={64}
          max={32000}
          value={value.maxTokens ?? ''}
          onChange={(e) => update({ maxTokens: e.target.value ? Number(e.target.value) : undefined })}
          placeholder="1024"
        />
      </div>

      {/* Thinking — shown only for providers that support it */}
      {supportsThinking && (
        <div className="space-y-3 border rounded-md p-3">
          <div className="flex items-center justify-between">
            <Label>Thinking / Reasoning</Label>
            <Switch
              checked={value.thinking?.enabled ?? false}
              onCheckedChange={(checked) =>
                update({ thinking: checked ? { enabled: true } : undefined })
              }
            />
          </div>
          {value.thinking?.enabled && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Effort</Label>
                <Select
                  value={value.thinking.effort ?? ''}
                  onValueChange={(v) =>
                    update({ thinking: { ...value.thinking!, effort: v as 'low' | 'medium' | 'high' } })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Default" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Budget Tokens</Label>
                <Input
                  type="number"
                  min={1024}
                  placeholder="e.g. 4000"
                  value={value.thinking.budgetTokens ?? ''}
                  onChange={(e) =>
                    update({
                      thinking: {
                        ...value.thinking!,
                        budgetTokens: e.target.value ? Number(e.target.value) : undefined,
                      },
                    })
                  }
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Advanced — Top P */}
      <Collapsible>
        <CollapsibleTrigger className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ChevronDown className="h-3 w-3" />
          Advanced
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-3 space-y-3">
          <div className="space-y-1.5">
            <Label>Top P</Label>
            <Input
              type="number"
              min={0}
              max={1}
              step={0.01}
              placeholder="1.0"
              value={value.topP ?? ''}
              onChange={(e) => update({ topP: e.target.value ? Number(e.target.value) : undefined })}
            />
          </div>

          {/* Structured Output */}
          {capabilities.structuredOutput && (
            <div className="space-y-1.5">
              <Label>Structured Output Schema (JSON)</Label>
              <Textarea
                className="font-mono text-sm min-h-[80px]"
                placeholder='{"type": "object", "properties": {...}}'
                value={value.structuredOutput ? JSON.stringify(value.structuredOutput, null, 2) : ''}
                onChange={(e) => {
                  try {
                    const parsed = e.target.value ? JSON.parse(e.target.value) : undefined
                    update({ structuredOutput: parsed })
                  } catch {
                    // Invalid JSON — don't update
                  }
                }}
              />
            </div>
          )}
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
```

- [ ] **Step 2: Check that Collapsible is available in the project**

```
Get-ChildItem frontend/src/components/ui/collapsible.tsx
```

If missing, install it:
```
npx --prefix frontend shadcn@latest add collapsible
```

- [ ] **Step 3: Lint**

```
npm --prefix frontend run lint
```

Fix any errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/shared/PromptConfigEditor.tsx
git commit -m "feat(prompt): add PromptConfigEditor shared component"
```

---

## Task 9: Wire Playground frontend

**Files:**
- Modify: `frontend/src/api/playground.ts`
- Modify: `frontend/src/hooks/usePlayground.ts`

- [ ] **Step 1: Update PlaygroundAnswerRequest in playground.ts**

In `frontend/src/api/playground.ts`, replace the request interface:

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

Update the `body` in `streamAnswer` to remove `instructions` and send `llm_config` with snake_case keys:

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

- [ ] **Step 2: Update usePlayground.ts**

In `frontend/src/hooks/usePlayground.ts`:

1. Add imports:
```typescript
import { usePromptConfig } from './usePromptConfig'
import type { PromptConfig } from '@/types/prompt-config'
```

2. Remove the individual LLM state variables and their setters from `UsePlaygroundReturn` and the hook body:
   - Remove: `provider`, `setProvider`, `model`, `setModel`, `temperature`, `setTemperature`, `maxTokens`, `setMaxTokens`, `instructions`, `setInstructions`
   - Remove: the `LLM_MODEL_OPTIONS` export and associated state
   - Remove: the `setProvider` callback with auto-model-select

3. Add `usePromptConfig` in the hook body:
```typescript
const { promptConfig, updatePromptConfig, setProvider, setPromptConfig } = usePromptConfig()
```

4. Add to `UsePlaygroundReturn`:
```typescript
promptConfig: PromptConfig
updatePromptConfig: (updates: Partial<PromptConfig>) => void
setPromptConfigProvider: (provider: string) => void
```

5. In `runSearch`, where `streamAnswer` is called, replace the old `params` object:
```typescript
await streamAnswer(
  projectId,
  indexId,
  {
    query,
    retrievalConfig: { searchType, topK, similarityThreshold: threshold },
    llmConfig: promptConfig,
  },
  // ... callbacks ...
)
```

6. Return the new values from the hook:
```typescript
return {
  // ... existing returns ...
  promptConfig,
  updatePromptConfig,
  setPromptConfigProvider: setProvider,
  // Remove: provider, setProvider, model, setModel, temperature, setTemperature, maxTokens, setMaxTokens, instructions, setInstructions
}
```

- [ ] **Step 3: Update Playground page/component that uses the removed fields**

Find which files destructure the removed fields from `usePlayground`:
```
grep -rn "instructions\|setInstructions\|setProvider\|setModel\|setTemperature\|setMaxTokens\|LLM_MODEL_OPTIONS" frontend/src --include="*.tsx" --include="*.ts" -l
```

For each file found:
- Remove destructured references to `instructions`, `setInstructions`, `provider`, `setProvider`, `model`, `setModel`, `temperature`, `setTemperature`, `maxTokens`, `setMaxTokens`
- Add `promptConfig`, `updatePromptConfig`, `setPromptConfigProvider` from the hook
- Replace the existing LLM parameter controls section in the JSX with:
```tsx
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
// ...
<PromptConfigEditor
  value={promptConfig}
  onChange={setPromptConfig}
  onProviderChange={setPromptConfigProvider}
  capabilities={{ thinking: true }}
/>
```

- [ ] **Step 4: Build frontend**

```
npm --prefix frontend run build
```

Fix any type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/playground.ts frontend/src/hooks/usePlayground.ts
git commit -m "feat(playground): replace ad-hoc LLM params with PromptConfigEditor"
```

---

## Task 10: Wire EvalRun frontend

**Files:**
- Modify: `frontend/src/api/eval-runs.ts`
- Modify: `frontend/src/pages/NewEvalRunPage.tsx`

- [ ] **Step 1: Update eval-runs API types**

Find `frontend/src/api/eval-runs.ts`. Locate the create-run request type and response type.

Add `import type { PromptConfig } from '@/types/prompt-config'`.

In the create request type, replace `systemPrompt?: string` with `llmConfig?: PromptConfig`.

In the response type and `getEvalRunConfig` return type, replace `systemPrompt?: string | null` with `llmConfig?: Record<string, unknown> | null`.

In the body of the create API call, replace the `systemPrompt` key:
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
```

- [ ] **Step 2: Update NewEvalRunPage.tsx**

In `frontend/src/pages/NewEvalRunPage.tsx`:

1. Add imports:
```typescript
import { usePromptConfig } from '@/hooks/usePromptConfig'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
import type { PromptConfig } from '@/types/prompt-config'
```

2. Remove the `DEFAULT_SYSTEM_PROMPT` constant and the `systemPrompt` state.

3. Add `usePromptConfig` after the other hooks:
```typescript
const { promptConfig, setPromptConfig, setProvider } = usePromptConfig()
```

4. In the clone `useEffect`, replace the `systemPrompt` population:
```typescript
// Replace:
if (config.systemPrompt) setSystemPrompt(config.systemPrompt as string)
// With:
if (config.llmConfig) {
  const lc = config.llmConfig as Record<string, unknown>
  setPromptConfig({
    systemPrompt: lc.system_prompt as string | undefined,
    provider: lc.provider as string | undefined,
    model: lc.model as string | undefined,
    temperature: lc.temperature as number | undefined,
    maxTokens: lc.max_tokens as number | undefined,
  })
}
```

5. In the `handleSubmit` / form submission, replace `systemPrompt` with `llmConfig: promptConfig`.

6. Replace the `systemPrompt` textarea section in the JSX with:
```tsx
{mode === 'retrieval_and_answer' && (
  <div className="space-y-2">
    <h3 className="text-sm font-medium">LLM Configuration</h3>
    <PromptConfigEditor
      value={promptConfig}
      onChange={setPromptConfig}
      onProviderChange={setProvider}
      capabilities={{ thinking: true }}
    />
  </div>
)}
```

- [ ] **Step 3: Build frontend**

```
npm --prefix frontend run build
```

Fix any type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/eval-runs.ts frontend/src/pages/NewEvalRunPage.tsx
git commit -m "feat(eval): replace systemPrompt textarea with PromptConfigEditor"
```

---

## Task 11: Wire Extraction frontend

**Files:**
- Modify: `frontend/src/types/extraction.ts`
- Modify: `frontend/src/components/extraction/ExtractionSchemaEditor.tsx`

- [ ] **Step 1: Update extraction TypeScript types**

In `frontend/src/types/extraction.ts`:

1. Add `import type { PromptConfig } from './prompt-config'`.

2. Add `llmConfig` and `userPromptTemplate` to `ExtractionSchema`:
```typescript
export interface ExtractionSchema {
  id: string
  projectId: string
  name: string
  description: string | null
  schemaDefinition: Record<string, unknown>
  extractionTarget: string
  llmConfig: Record<string, unknown> | null
  userPromptTemplate: string | null
  createdBy: string
  createdAt: string
  updatedAt: string
}
```

3. Add to `ExtractionSchemaCreate`:
```typescript
export interface ExtractionSchemaCreate {
  name: string
  description?: string
  schemaDefinition: Record<string, unknown>
  extractionTarget?: string
  llmConfig?: PromptConfig
  userPromptTemplate?: string
}
```

4. Add to `ExtractionSchemaUpdate`:
```typescript
export interface ExtractionSchemaUpdate {
  name?: string
  description?: string
  schemaDefinition?: Record<string, unknown>
  extractionTarget?: string
  llmConfig?: PromptConfig
  userPromptTemplate?: string
}
```

- [ ] **Step 2: Update ExtractionSchemaEditor.tsx**

In `frontend/src/components/extraction/ExtractionSchemaEditor.tsx`:

1. Add imports:
```typescript
import { usePromptConfig } from '@/hooks/usePromptConfig'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
import type { PromptConfig } from '@/types/prompt-config'
```

2. Add `userPromptTemplate` and `promptConfig` state to the component. Inside the component (after existing `useState` declarations):
```typescript
const { promptConfig, setPromptConfig, setProvider } = usePromptConfig(
  schema?.llmConfig ? {
    systemPrompt: (schema.llmConfig as Record<string, unknown>).system_prompt as string | undefined,
    provider: (schema.llmConfig as Record<string, unknown>).provider as string | undefined,
    model: (schema.llmConfig as Record<string, unknown>).model as string | undefined,
  } : {}
)
const [userPromptTemplate, setUserPromptTemplate] = useState(schema?.userPromptTemplate ?? '')
```

3. In the `useEffect` that resets state on `schema`/`open` change, add:
```typescript
if (schema?.llmConfig) {
  const lc = schema.llmConfig as Record<string, unknown>
  setPromptConfig({
    systemPrompt: lc.system_prompt as string | undefined,
    provider: lc.provider as string | undefined,
    model: lc.model as string | undefined,
  })
} else {
  setPromptConfig({})
}
setUserPromptTemplate(schema?.userPromptTemplate ?? '')
```

4. In `handleSave`, include the new fields:
```typescript
await onSave({
  name: name.trim(),
  schemaDefinition: parsedSchema,
  description: description.trim() || undefined,
  extractionTarget,
  llmConfig: promptConfig.provider || promptConfig.systemPrompt ? promptConfig : undefined,
  userPromptTemplate: userPromptTemplate.trim() || undefined,
})
```

5. Add the UI sections inside the `DialogContent`, after the extraction target select:
```tsx
{/* LLM Configuration */}
<div className="space-y-2">
  <Label className="text-sm font-medium">LLM Configuration (optional)</Label>
  <PromptConfigEditor
    value={promptConfig}
    onChange={setPromptConfig}
    onProviderChange={setProvider}
    className="border rounded-md p-3"
  />
</div>

{/* User Prompt Template */}
<div className="space-y-1.5">
  <Label>User Prompt Template (optional)</Label>
  <Textarea
    className="font-mono text-sm min-h-[100px]"
    placeholder="Leave empty to use the default. Available variables: {schema_json}, {document_context}"
    value={userPromptTemplate}
    onChange={(e) => setUserPromptTemplate(e.target.value)}
  />
  <p className="text-xs text-muted-foreground">
    Variables: <code className="bg-muted px-1 rounded">{'{schema_json}'}</code> and <code className="bg-muted px-1 rounded">{'{document_context}'}</code>
  </p>
</div>
```

- [ ] **Step 3: Build frontend**

```
npm --prefix frontend run build
```

Fix any type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/extraction.ts frontend/src/components/extraction/ExtractionSchemaEditor.tsx
git commit -m "feat(extraction): add PromptConfigEditor and user_prompt_template to ExtractionSchemaEditor"
```

---

## Task 12: End-to-end smoke test

- [ ] **Step 1: Start the backend**

```
uv run --directory backend uvicorn app.main:app --reload
```

- [ ] **Step 2: Start the frontend dev server**

```
npm --prefix frontend run dev
```

- [ ] **Step 3: Test Playground**

1. Navigate to any index → Playground tab
2. Switch to "Answer" mode
3. Confirm `<PromptConfigEditor>` is visible with system prompt, provider, model, temperature, max tokens
4. Enter a custom system prompt and run a query — verify the answer reflects it
5. Change provider/model — verify model dropdown updates

- [ ] **Step 4: Test Evals**

1. Navigate to Evals → New Eval Run
2. Switch mode to "Retrieval & Answer"
3. Confirm `<PromptConfigEditor>` appears in the form
4. Create a run with a custom system prompt
5. Navigate to the run detail — confirm it ran with the custom prompt

- [ ] **Step 5: Test Extraction schema editor**

1. Navigate to Extraction → create/edit a schema
2. Confirm `<PromptConfigEditor>` and user prompt template textarea appear
3. Set a system prompt, save — confirm it persists on re-open

- [ ] **Step 6: Test clone eval run**

1. Open an existing eval run → Clone
2. Confirm `<PromptConfigEditor>` is pre-populated with the source run's `llmConfig`

- [ ] **Step 7: Run backend tests**

```
uv run --directory backend python -m pytest tests/services/llm/test_prompt_config.py -v
```

Expected: all pass.

- [ ] **Step 8: Run frontend lint + build**

```
npm --prefix frontend run lint && npm --prefix frontend run build
```

Expected: no errors.

- [ ] **Step 9: Final commit**

```bash
git add .
git commit -m "feat(prompt): unified prompt interface — Playground, Evals, Extraction"
```
