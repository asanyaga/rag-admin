# Eval Inference Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy flat `generationModel`/`judgeModel`/`llmConfig` fields in eval runs with two `PromptConfig` JSON objects (`generationConfig`, `judgeConfig`), aligning eval inference with the unified LLM inference architecture used everywhere else in the codebase.

**Architecture:** All eval inference configuration flows through `PromptConfig` (provider, model, temperature, max_tokens, system_prompt, thinking). The backend resolves credentials via `resolve_provider_credentials` + `create_adapter`, matching the pattern already used by extraction and answer generation. Five flat DB columns and the `/settings/llm-models` endpoint are deleted; the frontend swaps two legacy dropdowns for two `PromptConfigEditor` instances.

**Tech Stack:** Python/FastAPI/SQLAlchemy/Alembic (backend), React/TypeScript/shadcn (frontend). Commands: `uv run --directory backend python -m pytest -o "addopts="`, `npm run build` (frontend TypeScript check).

---

## File Map

### Backend — modify
- `backend/app/models/eval_run.py` — remove 5 flat columns, add `generation_config` + `judge_config`
- `backend/app/repositories/eval_run_repository.py` — update `create()` signature
- `backend/app/schemas/eval_run.py` — replace `ModelConfig`, update create/response schemas
- `backend/app/services/eval_service.py` — update `create_run`, `_to_response`, `get_run_config`, execution path
- `backend/app/routers/eval_runs.py` — update background task, delete llm-models endpoint

### Backend — create
- `backend/alembic/versions/0c1d2e3f4a5b_eval_inference_alignment.py` — migration

### Backend — delete
- `backend/app/schemas/llm_models.py`

### Backend — tests
- `backend/tests/services/test_eval_service.py` — update `test_get_run_config*` tests
- `backend/tests/routers/test_eval_runs.py` — add answer-mode creation test

### Frontend — modify
- `frontend/src/types/eval-run.ts` — replace `ModelConfig`/`LlmModelOption` with `PromptConfig` fields
- `frontend/src/types/prompt-config.ts` — add Groq provider + model options
- `frontend/src/api/eval-runs.ts` — delete `fetchLlmModels`
- `frontend/src/hooks/useEvalRuns.ts` — delete `useLlmModels`
- `frontend/src/pages/NewEvalRunPage.tsx` — rewrite answer config section
- `frontend/src/pages/EvalRunDetailPage.tsx` — update model display
- `frontend/src/pages/EvalResultDetailPage.tsx` — update model display

---

## Task 1: Alembic migration + ORM model + repository

**Files:**
- Create: `backend/alembic/versions/0c1d2e3f4a5b_eval_inference_alignment.py`
- Modify: `backend/app/models/eval_run.py:65-73`
- Modify: `backend/app/repositories/eval_run_repository.py:18-54`

- [ ] **Step 1: Write the migration**

Create `backend/alembic/versions/0c1d2e3f4a5b_eval_inference_alignment.py`:

```python
"""eval inference alignment — replace flat model columns with generation_config + judge_config

Revision ID: 0c1d2e3f4a5b
Revises: a9b0c1d2e3f4
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0c1d2e3f4a5b'
down_revision = 'a9b0c1d2e3f4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('eval_runs', sa.Column('generation_config', sa.JSON(), nullable=True))
    op.add_column('eval_runs', sa.Column('judge_config', sa.JSON(), nullable=True))

    # Migrate existing data: pack flat columns + llm_config into the new JSON columns.
    # Uses jsonb_strip_nulls so rows with NULL llm_config don't get a null system_prompt key.
    op.execute("""
        UPDATE eval_runs
        SET generation_config = jsonb_strip_nulls(jsonb_build_object(
            'provider', generation_model_provider,
            'model', generation_model_id,
            'temperature', (llm_config->>'temperature')::float,
            'max_tokens', (llm_config->>'max_tokens')::int,
            'system_prompt', llm_config->>'system_prompt'
        ))
        WHERE generation_model_provider IS NOT NULL
    """)
    op.execute("""
        UPDATE eval_runs
        SET judge_config = jsonb_strip_nulls(jsonb_build_object(
            'provider', judge_model_provider,
            'model', judge_model_id
        ))
        WHERE judge_model_provider IS NOT NULL
    """)

    op.drop_column('eval_runs', 'generation_model_provider')
    op.drop_column('eval_runs', 'generation_model_id')
    op.drop_column('eval_runs', 'judge_model_provider')
    op.drop_column('eval_runs', 'judge_model_id')
    op.drop_column('eval_runs', 'llm_config')


def downgrade() -> None:
    op.add_column('eval_runs', sa.Column('generation_model_provider', sa.String(50), nullable=True))
    op.add_column('eval_runs', sa.Column('generation_model_id', sa.String(100), nullable=True))
    op.add_column('eval_runs', sa.Column('judge_model_provider', sa.String(50), nullable=True))
    op.add_column('eval_runs', sa.Column('judge_model_id', sa.String(100), nullable=True))
    op.add_column('eval_runs', sa.Column('llm_config', sa.JSON(), nullable=True))

    op.execute("""
        UPDATE eval_runs
        SET
            generation_model_provider = generation_config->>'provider',
            generation_model_id = generation_config->>'model',
            judge_model_provider = judge_config->>'provider',
            judge_model_id = judge_config->>'model',
            llm_config = jsonb_strip_nulls(jsonb_build_object(
                'temperature', (generation_config->>'temperature')::float,
                'max_tokens', (generation_config->>'max_tokens')::int,
                'system_prompt', generation_config->>'system_prompt'
            ))
        WHERE generation_config IS NOT NULL
    """)

    op.drop_column('eval_runs', 'generation_config')
    op.drop_column('eval_runs', 'judge_config')
```

- [ ] **Step 2: Update the ORM model**

In `backend/app/models/eval_run.py`, replace lines 64–73:

```python
    # Answer eval fields
    mode: Mapped[str] = mapped_column(
        String(30), nullable=False, default="retrieval_only",
        server_default="retrieval_only"
    )
    generation_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    judge_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    items_completed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    failed_item_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
```

(Remove `generation_model_provider`, `generation_model_id`, `judge_model_provider`, `judge_model_id`, `llm_config` from this block.)

- [ ] **Step 3: Update the repository `create` method**

In `backend/app/repositories/eval_run_repository.py`, replace the `create` method signature and body:

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
        generation_config: dict | None = None,
        judge_config: dict | None = None,
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
            generation_config=generation_config,
            judge_config=judge_config,
            experiment_id=experiment_id,
            variant_label=variant_label,
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run
```

- [ ] **Step 4: Apply the migration**

```bash
uv run --directory backend alembic upgrade head
```

Expected: `Running upgrade a9b0c1d2e3f4 -> 0c1d2e3f4a5b, eval inference alignment`

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0c1d2e3f4a5b_eval_inference_alignment.py backend/app/models/eval_run.py backend/app/repositories/eval_run_repository.py
git commit -m "feat(eval): replace flat model columns with generation_config + judge_config JSON"
```

---

## Task 2: Backend schemas — replace ModelConfig with PromptConfig, delete llm_models.py

**Files:**
- Modify: `backend/app/schemas/eval_run.py`
- Delete: `backend/app/schemas/llm_models.py`

- [ ] **Step 1: Rewrite `eval_run.py` schemas**

Replace the entire content of `backend/app/schemas/eval_run.py`:

```python
"""Pydantic schemas for evaluation runs."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.prompt_config import PromptConfig


class EvalRunConfig(BaseModel):
    """Configuration for an evaluation run."""
    search_type: str = Field("semantic", alias="searchType")
    top_k: int = Field(5, alias="topK", ge=1, le=50)
    similarity_threshold: float = Field(0.0, alias="similarityThreshold", ge=0.0, le=1.0)

    model_config = ConfigDict(populate_by_name=True)


class EvalRunCreate(BaseModel):
    """Request to create and run an evaluation."""
    golden_set_id: UUID = Field(..., alias="goldenSetId")
    index_id: UUID = Field(..., alias="indexId")
    name: str | None = Field(None, max_length=255)
    config: EvalRunConfig
    mode: str = Field("retrieval_only")
    generation_config: PromptConfig | None = Field(None, alias="generationConfig")
    judge_config: PromptConfig | None = Field(None, alias="judgeConfig")
    experiment_id: UUID | None = Field(None, alias="experimentId")
    variant_label: str | None = Field(None, alias="variantLabel", max_length=255)

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_answer_mode_fields(self):
        if self.mode == "retrieval_and_answer":
            if not self.generation_config:
                raise ValueError("generationConfig is required for retrieval_and_answer mode")
            if not self.judge_config:
                raise ValueError("judgeConfig is required for retrieval_and_answer mode")
            if not (self.generation_config.provider and self.generation_config.model):
                raise ValueError("generationConfig must specify provider and model")
            if not (self.judge_config.provider and self.judge_config.model):
                raise ValueError("judgeConfig must specify provider and model")
        return self


class EvalRunMetrics(BaseModel):
    """Aggregated metrics for an evaluation run."""
    avg_precision: float = Field(..., alias="avgPrecision")
    avg_recall: float = Field(..., alias="avgRecall")
    avg_f1: float = Field(..., alias="avgF1")
    queries_below_threshold: int = Field(..., alias="queriesBelowThreshold")

    model_config = ConfigDict(populate_by_name=True)


class EvalRunResponse(BaseModel):
    """Response for an evaluation run."""
    id: UUID
    name: str
    golden_set_id: UUID = Field(..., alias="goldenSetId")
    golden_set_name: str = Field("", alias="goldenSetName")
    index_id: UUID = Field(..., alias="indexId")
    index_name: str = Field("", alias="indexName")
    config: dict
    status: str
    metrics: dict | None = None
    error_message: str | None = Field(None, alias="errorMessage")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    mode: str = Field("retrieval_only")
    generation_config: dict | None = Field(None, alias="generationConfig")
    judge_config: dict | None = Field(None, alias="judgeConfig")
    items_completed: int = Field(0, alias="itemsCompleted")
    failed_item_count: int = Field(0, alias="failedItemCount")
    experiment_id: UUID | None = Field(None, alias="experimentId")
    experiment_name: str | None = Field(None, alias="experimentName")
    variant_label: str | None = Field(None, alias="variantLabel")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class EvalRunProgress(BaseModel):
    """Progress of a running eval run."""
    status: str
    items_total: int = Field(..., alias="itemsTotal")
    items_completed: int = Field(..., alias="itemsCompleted")
    failed_item_count: int = Field(0, alias="failedItemCount")

    model_config = ConfigDict(populate_by_name=True)


class RetrievedChunkInfo(BaseModel):
    """Info about a single retrieved chunk in eval results."""
    chunk_id: str = Field(..., alias="chunkId")
    rank: int
    score: float
    content: str
    document_id: str = Field(..., alias="documentId")
    document_name: str = Field("", alias="documentName")
    page: int | None = None
    is_relevant: bool = Field(False, alias="isRelevant")

    model_config = ConfigDict(populate_by_name=True)


class ExpectedSourceInfo(BaseModel):
    """Info about an expected source in eval results."""
    document_id: str = Field(..., alias="documentId")
    document_name: str = Field("", alias="documentName")
    locator: dict

    model_config = ConfigDict(populate_by_name=True)


class ClaimItem(BaseModel):
    """A single claim from the judge's faithfulness evaluation."""
    text: str
    label: str
    source: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class EvalRunResultResponse(BaseModel):
    """Per-query result within an evaluation run."""
    id: UUID
    query_id: UUID = Field(..., alias="queryId")
    query_text: str = Field("", alias="queryText")
    precision: float
    recall: float
    f1: float
    retrieved_chunks: list[RetrievedChunkInfo] = Field(default_factory=list, alias="retrievedChunks")
    expected_sources: list[ExpectedSourceInfo] = Field(default_factory=list, alias="expectedSources")
    generated_answer: str | None = Field(None, alias="generatedAnswer")
    faithfulness_score: float | None = Field(None, alias="faithfulnessScore")
    relevance_score: float | None = Field(None, alias="relevanceScore")
    claim_breakdown: list[ClaimItem] | None = Field(None, alias="claimBreakdown")
    judge_error: str | None = Field(None, alias="judgeError")
    generation_error: str | None = Field(None, alias="generationError")
    trace_data: dict | None = Field(None, alias="traceData")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class QueryComparisonMetrics(BaseModel):
    precision: float
    recall: float
    f1: float

    model_config = ConfigDict(populate_by_name=True)


class QueryComparisonItem(BaseModel):
    query_id: UUID = Field(..., alias="queryId")
    query_text: str = Field("", alias="queryText")
    baseline: QueryComparisonMetrics
    challenger: QueryComparisonMetrics
    delta_f1: float = Field(..., alias="deltaF1")

    model_config = ConfigDict(populate_by_name=True)


class ComparisonSummary(BaseModel):
    avg_delta_precision: float = Field(..., alias="avgDeltaPrecision")
    avg_delta_recall: float = Field(..., alias="avgDeltaRecall")
    avg_delta_f1: float = Field(..., alias="avgDeltaF1")
    improved_queries: int = Field(..., alias="improvedQueries")
    degraded_queries: int = Field(..., alias="degradedQueries")
    unchanged_queries: int = Field(..., alias="unchangedQueries")

    model_config = ConfigDict(populate_by_name=True)


class RunComparisonResponse(BaseModel):
    baseline_run: EvalRunResponse = Field(..., alias="baselineRun")
    challenger_run: EvalRunResponse = Field(..., alias="challengerRun")
    per_query_comparison: list[QueryComparisonItem] = Field(..., alias="perQueryComparison")
    summary: ComparisonSummary

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 2: Delete `llm_models.py`**

```bash
rm backend/app/schemas/llm_models.py
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/eval_run.py backend/app/schemas/llm_models.py
git commit -m "feat(eval): replace ModelConfig with PromptConfig in eval schemas, delete llm_models"
```

---

## Task 3: Update eval service

**Files:**
- Modify: `backend/app/services/eval_service.py`

The service has four places that reference the old fields. Make all four changes before running tests.

- [ ] **Step 1: Update `create_run` — store generation_config + judge_config**

Find the `create_run` method. Replace the `eval_repo.create(...)` call's five old keyword arguments:

```python
# OLD (remove these five lines):
            generation_model_provider=data.generation_model.provider if data.generation_model else None,
            generation_model_id=data.generation_model.model_id if data.generation_model else None,
            judge_model_provider=data.judge_model.provider if data.judge_model else None,
            judge_model_id=data.judge_model.model_id if data.judge_model else None,
            llm_config=data.llm_config.model_dump(by_alias=False, mode="json") if data.llm_config else None,

# NEW (replace with these two lines):
            generation_config=data.generation_config.model_dump(by_alias=False, mode="json") if data.generation_config else None,
            judge_config=data.judge_config.model_dump(by_alias=False, mode="json") if data.judge_config else None,
```

- [ ] **Step 2: Update `_to_response` — serialize new columns**

Find the `_to_response` method (near the bottom of the file). Remove the `gen_model`/`judge_model` construction block and the `ModelConfig` usage. Replace it so the `EvalRunResponse(...)` call uses:

```python
# REMOVE this block entirely:
        gen_model = None
        if run.generation_model_provider and run.generation_model_id:
            gen_model = ModelConfig(
                provider=run.generation_model_provider,
                model_id=run.generation_model_id,
            )

        judge_model = None
        if run.judge_model_provider and run.judge_model_id:
            judge_model = ModelConfig(
                provider=run.judge_model_provider,
                model_id=run.judge_model_id,
            )

# In the EvalRunResponse(...) call, replace:
            generation_model=gen_model,
            judge_model=judge_model,
            ...
            llmConfig=run.llm_config,
# WITH:
            generationConfig=run.generation_config,
            judgeConfig=run.judge_config,
```

Also remove the `ModelConfig` import from `app.schemas.eval_run` at the top of the file.

- [ ] **Step 3: Update `get_run_config` — return new keys**

Find the `get_run_config` method. Replace the returned dict:

```python
    async def get_run_config(self, run_id: UUID, project_id: UUID) -> dict:
        """Return the full config of a run for the clone feature."""
        run = await self.eval_repo.get_by_id(run_id, project_id)
        if not run:
            raise NotFoundError(f"Eval run {run_id} not found")

        return {
            "goldenSetId": str(run.golden_set_id),
            "indexId": str(run.index_id),
            "name": run.name,
            "config": run.config,
            "mode": run.mode,
            "generationConfig": run.generation_config,
            "judgeConfig": run.judge_config,
            "experimentId": str(run.experiment_id) if run.experiment_id else None,
            "variantLabel": run.variant_label,
        }
```

- [ ] **Step 4: Update the execution path — read from generation_config**

Find the section in `execute_eval_run` (or the execution loop) that builds `gen_config`. It currently reads `run.generation_model_provider`, `run.generation_model_id`, and `run.llm_config`. Replace it:

```python
# OLD — remove this block:
            prompt_config = PromptConfigSchema.model_validate(run.llm_config) if run.llm_config else None
            lc = run.llm_config or {}
            gen_config = LLMConfig(
                provider=run.generation_model_provider,
                model=run.generation_model_id,
                temperature=lc.get("temperature", 0.0),
                max_tokens=lc.get("max_tokens", 1024),
            )
            sys_prompt = (
                prompt_config.system_prompt
                if prompt_config and prompt_config.system_prompt
                else DEFAULT_RAG_SYSTEM_PROMPT
            )

# NEW — replace with:
            gen_pc = PromptConfigSchema.model_validate(run.generation_config) if run.generation_config else None
            resolved = resolve_llm_config(
                gen_pc,
                default_provider="openai",
                default_model="gpt-4o",
                default_temperature=0.0,
                default_max_tokens=1024,
            )
            gen_config = LLMConfig(
                provider=resolved.provider,
                model=resolved.model,
                temperature=resolved.temperature,
                max_tokens=resolved.max_tokens,
            )
            sys_prompt = (
                gen_pc.system_prompt
                if gen_pc and gen_pc.system_prompt
                else DEFAULT_RAG_SYSTEM_PROMPT
            )
```

Ensure these imports exist at the top of `eval_service.py` (add any that are missing):
```python
from app.schemas.prompt_config import PromptConfig as PromptConfigSchema
from app.services.llm.prompt_config import resolve_llm_config
from app.services.llm.types import LLMConfig
```

- [ ] **Step 5: Run the existing service tests to verify they fail with clear errors**

```bash
uv run --directory backend python -m pytest tests/services/test_eval_service.py -x -q 2>&1 | head -40
```

Expected: failures referencing `generation_model_provider` or `generationModel`/`judgeModel`/`llmConfig` — these confirm the test needs updating.

- [ ] **Step 6: Update `test_eval_service.py`**

Replace the `test_get_run_config` and `test_get_run_config_retrieval_only` tests:

```python
@pytest.mark.asyncio
async def test_get_run_config(
    eval_service: EvalService,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
    test_experiment: Experiment,
):
    run = await eval_run_repo.create(
        project_id=test_project.id,
        golden_set_id=test_golden_set.id,
        index_id=test_index.id,
        name="Config Run",
        config={"searchType": "hybrid", "topK": 10, "similarityThreshold": 0.3},
        user_id=test_user.id,
        mode="retrieval_and_answer",
        generation_config={
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.2,
            "max_tokens": 2048,
            "system_prompt": "Custom prompt",
        },
        judge_config={
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
        },
        experiment_id=test_experiment.id,
        variant_label="hybrid k=10",
    )

    config = await eval_service.get_run_config(run.id, test_project.id)

    assert config["goldenSetId"] == str(test_golden_set.id)
    assert config["indexId"] == str(test_index.id)
    assert config["name"] == "Config Run"
    assert config["config"]["searchType"] == "hybrid"
    assert config["config"]["topK"] == 10
    assert config["config"]["similarityThreshold"] == 0.3
    assert config["mode"] == "retrieval_and_answer"
    assert config["generationConfig"]["provider"] == "openai"
    assert config["generationConfig"]["model"] == "gpt-4o"
    assert config["generationConfig"]["system_prompt"] == "Custom prompt"
    assert config["judgeConfig"]["provider"] == "anthropic"
    assert config["judgeConfig"]["model"] == "claude-sonnet-4-6"
    assert config["experimentId"] == str(test_experiment.id)
    assert config["variantLabel"] == "hybrid k=10"


@pytest.mark.asyncio
async def test_get_run_config_retrieval_only(
    eval_service: EvalService,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    run = await eval_run_repo.create(
        project_id=test_project.id,
        golden_set_id=test_golden_set.id,
        index_id=test_index.id,
        name="Simple Run",
        config={"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
        user_id=test_user.id,
    )

    config = await eval_service.get_run_config(run.id, test_project.id)

    assert config["mode"] == "retrieval_only"
    assert config["generationConfig"] is None
    assert config["judgeConfig"] is None
    assert config["experimentId"] is None
    assert config["variantLabel"] is None
```

- [ ] **Step 7: Run service tests and confirm they pass**

```bash
uv run --directory backend python -m pytest tests/services/test_eval_service.py -x -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/eval_service.py backend/tests/services/test_eval_service.py
git commit -m "feat(eval): update eval service — generation_config + judge_config, resolve_llm_config"
```

---

## Task 4: Update eval router — background task + delete llm-models endpoint

**Files:**
- Modify: `backend/app/routers/eval_runs.py`

- [ ] **Step 1: Update `execute_eval_run_background` signature and body**

Replace the function signature and the credential-resolution block:

```python
async def execute_eval_run_background(
    db: AsyncSession,
    run_id: UUID,
    project_id: UUID,
    user_id: UUID,
    mode: str = "retrieval_only",
    generation_config: dict | None = None,
    judge_config: dict | None = None,
) -> None:
    """Background task to execute an eval run."""
    eval_run_repo = EvalRunRepository(db)
    golden_set_repo = GoldenSetRepository(db)
    query_service = QueryService(
        index_repo=IndexRepository(db),
        chunk_repo=ChunkRepository(db),
        provider_key_repo=ProviderKeyRepository(db),
    )

    generation_adapter = None
    judge_adapter = None

    if mode == "retrieval_and_answer":
        if generation_config and generation_config.get("provider"):
            provider = generation_config["provider"]
            creds = await resolve_provider_credentials(provider, user_id, project_id, db)
            generation_adapter = create_adapter(provider, creds.api_key, creds.base_url)
        if judge_config and judge_config.get("provider"):
            provider = judge_config["provider"]
            creds = await resolve_provider_credentials(provider, user_id, project_id, db)
            judge_adapter = create_adapter(provider, creds.api_key, creds.base_url)

    service = EvalService(
        eval_run_repo, golden_set_repo, query_service,
        judge_service=JudgeService(),
        generation_adapter=generation_adapter,
        judge_adapter=judge_adapter,
    )
    await service.execute_eval_run(run_id, project_id, user_id)
```

- [ ] **Step 2: Update the `background_tasks.add_task` call in `create_eval_run`**

Find the `add_task` call and replace the old provider-string arguments:

```python
        background_tasks.add_task(
            execute_eval_run_background,
            db=db,
            run_id=run.id,
            project_id=project_id,
            user_id=current_user.id,
            mode=data.mode,
            generation_config=data.generation_config.model_dump(by_alias=False, mode="json") if data.generation_config else None,
            judge_config=data.judge_config.model_dump(by_alias=False, mode="json") if data.judge_config else None,
        )
```

- [ ] **Step 3: Delete the `/settings/llm-models` endpoint**

Remove the entire `settings_router` block at the bottom of the file (the `@settings_router.get("/llm-models")` function and the `settings_router = APIRouter(...)` declaration).

Also remove from the top of the file:
- `from app.schemas.llm_models import LlmModelsResponse, get_available_chat_models`

- [ ] **Step 4: Check that `settings_router` is not registered in `main.py`**

```bash
grep -n "settings_router" backend/app/main.py
```

If it appears, remove that `app.include_router(settings_router, ...)` line from `main.py`.

- [ ] **Step 5: Run the router tests**

```bash
uv run --directory backend python -m pytest tests/routers/test_eval_runs.py -x -q
```

Expected: all existing tests pass (they test retrieval_only mode which has no inference fields).

- [ ] **Step 6: Add an answer-mode creation test to `test_eval_runs.py`**

Append to `backend/tests/routers/test_eval_runs.py`:

```python
@pytest.mark.asyncio
async def test_create_run_answer_mode_with_prompt_configs(client: AsyncClient):
    """Creating a retrieval_and_answer run with generationConfig + judgeConfig succeeds."""
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)
    gs_id = await create_golden_set(client, token, project_id)
    index_id = await create_index(client, token, project_id)

    resp = await client.post(
        f"/api/v1/projects/{project_id}/eval-runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "goldenSetId": gs_id,
            "indexId": index_id,
            "name": "Answer Run",
            "config": {"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
            "mode": "retrieval_and_answer",
            "generationConfig": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.0,
                "maxTokens": 1024,
            },
            "judgeConfig": {
                "provider": "openai",
                "model": "gpt-4o",
            },
        },
    )

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["mode"] == "retrieval_and_answer"
    assert data["generationConfig"]["provider"] == "openai"
    assert data["generationConfig"]["model"] == "gpt-4o"
    assert data["judgeConfig"]["provider"] == "openai"
    assert data["judgeConfig"]["model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_create_run_answer_mode_missing_generation_config_rejected(client: AsyncClient):
    """Creating a retrieval_and_answer run without generationConfig is rejected."""
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)
    gs_id = await create_golden_set(client, token, project_id)
    index_id = await create_index(client, token, project_id)

    resp = await client.post(
        f"/api/v1/projects/{project_id}/eval-runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "goldenSetId": gs_id,
            "indexId": index_id,
            "config": {"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
            "mode": "retrieval_and_answer",
        },
    )

    assert resp.status_code == 422
```

- [ ] **Step 7: Run all router tests**

```bash
uv run --directory backend python -m pytest tests/routers/test_eval_runs.py -x -q
```

Expected: all tests pass including the two new ones.

- [ ] **Step 8: Run the full backend suite to check for regressions**

```bash
uv run --directory backend python -m pytest -o "addopts=" -q 2>&1 | tail -20
```

Expected: no new failures.

- [ ] **Step 9: Commit**

```bash
git add backend/app/routers/eval_runs.py backend/app/main.py backend/tests/routers/test_eval_runs.py
git commit -m "feat(eval): update router — generation_config/judge_config background task, delete llm-models endpoint"
```

---

## Task 5: Frontend types

**Files:**
- Modify: `frontend/src/types/eval-run.ts`
- Modify: `frontend/src/types/prompt-config.ts`

- [ ] **Step 1: Rewrite `types/eval-run.ts`**

Replace the entire file content:

```typescript
/**
 * Evaluation Run feature types
 */
import type { PromptConfig } from '@/types/prompt-config'

export type EvalRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'partial_failure'

export type EvalMode = 'retrieval_only' | 'retrieval_and_answer'

export interface EvalRunConfig {
  searchType: 'semantic' | 'keyword' | 'hybrid'
  topK: number
  similarityThreshold: number
}

export interface EvalRunMetrics {
  avgPrecision: number
  avgRecall: number
  avgF1: number
  queriesBelowThreshold: number
  avgFaithfulness: number | null
  avgRelevance: number | null
}

export interface EvalRun {
  id: string
  name: string
  goldenSetId: string
  goldenSetName: string
  indexId: string
  indexName: string
  config: EvalRunConfig
  status: EvalRunStatus
  metrics: EvalRunMetrics | null
  errorMessage: string | null
  createdBy: string
  createdAt: string
  mode: EvalMode
  generationConfig: PromptConfig | null
  judgeConfig: PromptConfig | null
  itemsCompleted: number
  failedItemCount: number
  experimentId?: string
  experimentName?: string
  variantLabel?: string
}

export interface CreateEvalRunRequest {
  goldenSetId: string
  indexId: string
  name?: string
  config: EvalRunConfig
  mode: EvalMode
  generationConfig?: PromptConfig
  judgeConfig?: PromptConfig
  experimentId?: string
  variantLabel?: string
}

// Per-query results
export interface RetrievedChunk {
  chunkId: string
  rank: number
  score: number
  content: string
  documentId: string
  documentName: string
  page: number | null
  isRelevant: boolean
}

export interface ExpectedSource {
  documentId: string
  documentName: string
  locator: { type: string; pages?: number[] }
}

export interface ClaimItem {
  text: string
  label: 'supported' | 'unsupported' | 'unclear'
  source: string | null
}

export interface EvalRunResult {
  id: string
  queryId: string
  queryText: string
  precision: number
  recall: number
  f1: number
  retrievedChunks: RetrievedChunk[]
  expectedSources: ExpectedSource[]
  generatedAnswer: string | null
  faithfulnessScore: number | null
  relevanceScore: number | null
  claimBreakdown: ClaimItem[] | null
  judgeError: string | null
  generationError: string | null
  traceData?: import('../types/trace').QueryTrace | null
}

export interface EvalRunProgress {
  status: string
  itemsTotal: number
  itemsCompleted: number
  failedItemCount: number
}

export interface QueryComparisonMetrics {
  precision: number
  recall: number
  f1: number
}

export interface QueryComparisonItem {
  queryId: string
  queryText: string
  baseline: QueryComparisonMetrics
  challenger: QueryComparisonMetrics
  deltaF1: number
}

export interface ComparisonSummary {
  avgDeltaPrecision: number
  avgDeltaRecall: number
  avgDeltaF1: number
  improvedQueries: number
  degradedQueries: number
  unchangedQueries: number
}

export interface RunComparison {
  baselineRun: EvalRun
  challengerRun: EvalRun
  perQueryComparison: QueryComparisonItem[]
  summary: ComparisonSummary
}
```

- [ ] **Step 2: Add Groq to `types/prompt-config.ts`**

In `PROVIDER_MODEL_OPTIONS`, add a `groq` entry after `ollama_local`:

```typescript
  groq: [
    { value: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B' },
    { value: 'llama-3.1-8b-instant', label: 'Llama 3.1 8B Instant' },
    { value: 'mixtral-8x7b-32768', label: 'Mixtral 8x7B' },
  ],
```

In `PROVIDERS`, add after the `ollama_local` entry:

```typescript
  { value: 'groq', label: 'Groq' },
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/eval-run.ts frontend/src/types/prompt-config.ts
git commit -m "feat(eval): update frontend types — PromptConfig replaces ModelConfig/LlmModelOption, add Groq"
```

---

## Task 6: Rewrite `NewEvalRunPage` answer config section

**Files:**
- Modify: `frontend/src/pages/NewEvalRunPage.tsx`

- [ ] **Step 1: Remove legacy imports and state, add new state**

At the top of the file, remove:
- `import { useEvalRuns, useLlmModels } from '@/hooks/useEvalRuns'`

Replace with:
- `import { useEvalRuns } from '@/hooks/useEvalRuns'`

Remove these state declarations:
```typescript
  const { models, isLoading: modelsLoading } = useLlmModels()
  const [generationModel, setGenerationModel] = useState('')
  const [judgeModel, setJudgeModel] = useState('')
```

Add two `usePromptConfig` calls (the hook is already imported):
```typescript
  const {
    promptConfig: generationConfig,
    setPromptConfig: setGenerationConfig,
    setProvider: setGenerationProvider,
  } = usePromptConfig()
  const {
    promptConfig: judgeConfig,
    setPromptConfig: setJudgeConfig,
    setProvider: setJudgeProvider,
  } = usePromptConfig()
```

Remove the `modelsByProvider` memo and the `parseModelValue` helper entirely.

- [ ] **Step 2: Update `sameModelWarning` and `canSubmit`**

Replace:
```typescript
  const sameModelWarning =
    generationModel && judgeModel && generationModel === judgeModel

  const canSubmit =
    goldenSetId &&
    indexId &&
    mode !== null &&
    (mode === 'retrieval_only' || (generationModel && judgeModel))
```

With:
```typescript
  const sameModelWarning =
    mode === 'retrieval_and_answer' &&
    generationConfig.provider &&
    generationConfig.provider === judgeConfig.provider &&
    generationConfig.model === judgeConfig.model

  const canSubmit =
    goldenSetId &&
    indexId &&
    mode !== null &&
    (mode === 'retrieval_only' || (
      generationConfig.provider && generationConfig.model &&
      judgeConfig.provider && judgeConfig.model
    ))
```

- [ ] **Step 3: Update `handleSubmit`**

Replace the `createRun(...)` call's inference arguments:

```typescript
      const run = await createRun({
        goldenSetId,
        indexId,
        name: name.trim() || undefined,
        config: { searchType, topK, similarityThreshold },
        mode,
        generationConfig: mode === 'retrieval_and_answer' ? generationConfig : undefined,
        judgeConfig: mode === 'retrieval_and_answer' ? judgeConfig : undefined,
        experimentId: experimentId || undefined,
        variantLabel: variantLabel.trim() || undefined,
      })
```

- [ ] **Step 4: Update the clone restore logic**

Replace the `if (config.llmConfig)` block and the `genModel`/`jModel` blocks:

```typescript
        const gc = config.generationConfig as Record<string, unknown> | null
        if (gc) {
          setGenerationConfig({
            provider: gc.provider as string | undefined,
            model: gc.model as string | undefined,
            temperature: gc.temperature as number | undefined,
            maxTokens: gc.max_tokens as number | undefined,
            systemPrompt: gc.system_prompt as string | undefined,
            topP: gc.top_p as number | undefined,
          })
        }
        const jc = config.judgeConfig as Record<string, unknown> | null
        if (jc) {
          setJudgeConfig({
            provider: jc.provider as string | undefined,
            model: jc.model as string | undefined,
            temperature: jc.temperature as number | undefined,
          })
        }
```

Remove the old `genModel`/`jModel` clone restore blocks that used `config.generationModel`/`config.judgeModel`.

- [ ] **Step 5: Rewrite the Answer Evaluation Config card JSX**

Replace the entire card content for the answer config section (the `{mode === 'retrieval_and_answer' && (` block). The new JSX:

```tsx
      {mode === 'retrieval_and_answer' && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Answer Evaluation Config</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {sameModelWarning && (
              <div className="flex items-center gap-2 text-xs text-amber-600">
                <AlertTriangle className="h-3 w-3" />
                Using the same model for generation and judging may reduce evaluation quality
              </div>
            )}

            <div className="space-y-2">
              <h3 className="text-sm font-medium">Generation Config</h3>
              <div className="rounded-md border p-3">
                <PromptConfigEditor
                  value={generationConfig}
                  onChange={setGenerationConfig}
                  onProviderChange={setGenerationProvider}
                  capabilities={{ thinking: true }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-medium">Judge Config</h3>
              <div className="rounded-md border p-3">
                <PromptConfigEditor
                  value={judgeConfig}
                  onChange={setJudgeConfig}
                  onProviderChange={setJudgeProvider}
                />
              </div>
            </div>

            {queryCount > 0 && (
              <p className="text-xs text-muted-foreground">
                Estimated: {queryCount} &times; 2 = {queryCount * 2} LLM calls
              </p>
            )}
          </CardContent>
        </Card>
      )}
```

Also remove the unused `AlertTriangle` import check — `AlertTriangle` is still used for `sameModelWarning`, so keep it. Remove `MessageSquare`... actually `MessageSquare` is used in the mode selector card, keep it. Remove `Copy`... `Copy` is used in the clone banner, keep it.

Remove this unused import:
```typescript
import type { EvalMode } from '@/types/eval-run'
```
Wait — `EvalMode` is still used. Keep it. Just remove:
```typescript
import {
  SelectGroup,
  SelectLabel,
} from '@/components/ui/select'
```
if `SelectGroup` and `SelectLabel` are no longer used (they were only in the model dropdowns).

- [ ] **Step 6: TypeScript compile check**

```bash
cd frontend && npm run build 2>&1 | tail -30
```

Expected: build succeeds with no TypeScript errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/NewEvalRunPage.tsx
git commit -m "feat(eval): rewrite answer config — two PromptConfigEditor instances replace legacy model dropdowns"
```

---

## Task 7: Update display components + remove dead code

**Files:**
- Modify: `frontend/src/pages/EvalRunDetailPage.tsx`
- Modify: `frontend/src/pages/EvalResultDetailPage.tsx`
- Modify: `frontend/src/api/eval-runs.ts`
- Modify: `frontend/src/hooks/useEvalRuns.ts`

- [ ] **Step 1: Update `EvalRunDetailPage.tsx` model display**

Find lines 67–69 (the `run.generationModel` block):

```tsx
// OLD:
            {run.generationModel && (
              <span>
                {' '}&middot; Gen: {run.generationModel.modelId}
              </span>
            )}

// NEW:
            {run.generationConfig?.model && (
              <span>
                {' '}&middot; Gen: {run.generationConfig.provider}/{run.generationConfig.model}
              </span>
            )}
```

- [ ] **Step 2: Update `EvalResultDetailPage.tsx` model display**

Find lines 160–162:

```tsx
// OLD:
                  {run.generationModel && (
                    <span>
                      {run.generationModel.modelId}
                    </span>
                  )}

// NEW:
                  {run.generationConfig?.model && (
                    <span>
                      {run.generationConfig.provider}/{run.generationConfig.model}
                    </span>
                  )}
```

- [ ] **Step 3: Remove `fetchLlmModels` from `api/eval-runs.ts`**

Delete the entire `fetchLlmModels` function and its `LlmModelOption` import:

```typescript
// DELETE this import:
  LlmModelOption,

// DELETE this function:
export async function fetchLlmModels(): Promise<LlmModelOption[]> {
  const response = await apiClient.get<{ models: LlmModelOption[] }>(
    '/settings/llm-models'
  )
  return response.data.models
}
```

- [ ] **Step 4: Remove `useLlmModels` from `hooks/useEvalRuns.ts`**

Delete the entire `useLlmModels` hook and its supporting types and imports:

```typescript
// DELETE this interface:
interface UseLlmModelsReturn {
  models: LlmModelOption[]
  isLoading: boolean
  error: string | null
}

// DELETE this export function:
export function useLlmModels(): UseLlmModelsReturn { ... }

// DELETE LlmModelOption from the imports at the top
```

- [ ] **Step 5: Final TypeScript compile check**

```bash
cd frontend && npm run build 2>&1 | tail -30
```

Expected: clean build, no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/EvalRunDetailPage.tsx frontend/src/pages/EvalResultDetailPage.tsx frontend/src/api/eval-runs.ts frontend/src/hooks/useEvalRuns.ts
git commit -m "feat(eval): update display components, remove fetchLlmModels + useLlmModels dead code"
```

---

## Final verification

- [ ] **Run full backend test suite**

```bash
uv run --directory backend python -m pytest -o "addopts=" -q 2>&1 | tail -20
```

Expected: no new failures versus the pre-task baseline.

- [ ] **Run frontend build**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: `✓ built in Xs` with no errors.
