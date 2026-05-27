# Prompt Config — Plan 4: Classification Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `PromptConfig` into Classification — add `llm_config JSON` to `ClassificationRun`, expose a system-prompt override in the run create form.

**Architecture:** One Alembic migration adds `llm_config JSON` to `classification_runs` alongside the existing `llm_provider`/`llm_model` columns (those are NOT replaced — they control which adapter/model is used; `llm_config` carries optional prompt overrides). The service gains a `system_prompt` param. The router extracts it from `body.llm_config` and threads it through the background task. The frontend adds a system-prompt textarea to the Advanced section of `ClassificationRunForm` — the full `<PromptConfigEditor>` is intentionally deferred because provider/model are already controlled by the existing form dropdowns.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic / Pydantic v2 — React 18 / TypeScript / shadcn/ui

**Spec:** `docs/superpowers/specs/2026-05-27-unified-prompt-interface-design.md`

**Prerequisites:** Plan 1 complete.

**DB migration:** 1 migration on `classification_runs` — add `llm_config JSON` nullable.

---

## File Map

**Modified backend files:**
- `backend/app/models/classification_run.py` — add `llm_config` JSON column
- `backend/app/repositories/classification_run_repository.py` — add `llm_config` to `ClassificationRunCreate` dataclass + `create()`
- `backend/app/schemas/classification.py` — add `llm_config` to request + response schemas
- `backend/app/services/classification/service.py` — add `system_prompt` param to `execute()`
- `backend/app/routers/classification.py` — thread `llm_config`/`system_prompt` through create + background task

**New backend files:**
- `backend/alembic/versions/<rev>_classification_run_llm_config.py` — migration

**Modified frontend files:**
- `frontend/src/types/classification.ts` — add `llmConfig` to response type + create request
- `frontend/src/api/classification.ts` — serialize `llmConfig` in create request
- `frontend/src/components/classification/ClassificationRunForm.tsx` — add system prompt textarea
- `frontend/src/pages/NewClassificationRunPage.tsx` — pass `systemPrompt` from form values

---

## Task 1: DB migration — add llm_config to classification_runs

**Files:**
- Modify: `backend/app/models/classification_run.py`
- New: Alembic migration

- [ ] **Step 1: Update the ClassificationRun model**

In `backend/app/models/classification_run.py`, `JSON` is already in the import. After the `batch_overlap` column (line ~36), add:

```python
llm_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

The full model column block should look like (new line marked):

```python
labels_requested: Mapped[list] = mapped_column(JSON, nullable=False)
llm_provider: Mapped[str] = mapped_column(Text, nullable=False)
llm_model: Mapped[str] = mapped_column(Text, nullable=False)
status: Mapped[str] = mapped_column(Text, nullable=False)
error: Mapped[str | None] = mapped_column(Text, nullable=True)
batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
batch_overlap: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
llm_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # NEW
```

- [ ] **Step 2: Generate the migration**

```
uv run --directory backend alembic revision --autogenerate -m "classification_run_llm_config"
```

Open the generated file in `backend/alembic/versions/`. Replace `upgrade()` and `downgrade()` with:

```python
def upgrade() -> None:
    op.add_column('classification_runs', sa.Column('llm_config', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('classification_runs', 'llm_config')
```

- [ ] **Step 3: Apply the migration**

```
uv run --directory backend alembic upgrade head
```

Expected: `Running upgrade <prev> -> <new>, classification_run_llm_config`

- [ ] **Step 4: Verify**

```
uv run --directory backend alembic current
```

Expected: shows the new revision as the current head.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/classification_run.py backend/alembic/versions/
git commit -m "feat(classification): add llm_config JSON column to classification_runs"
```

---

## Task 2: Repository update

**Files:**
- Modify: `backend/app/repositories/classification_run_repository.py`

- [ ] **Step 1: Add llm_config to ClassificationRunCreate dataclass**

In `backend/app/repositories/classification_run_repository.py`, find the `ClassificationRunCreate` dataclass and add the new field:

```python
@dataclass
class ClassificationRunCreate:
    parse_run_id: UUID
    document_id: UUID
    labels_requested: list[str]
    llm_provider: str
    llm_model: str
    batch_size: int
    batch_overlap: int
    llm_config: dict | None = None
```

- [ ] **Step 2: Pass llm_config in create()**

In the `create()` method, add `llm_config=data.llm_config` to the `ClassificationRunORM(...)` constructor:

```python
async def create(self, data: ClassificationRunCreate) -> ClassificationRunORM:
    run = ClassificationRunORM(
        parse_run_id=data.parse_run_id,
        document_id=data.document_id,
        labels_requested=data.labels_requested,
        llm_provider=data.llm_provider,
        llm_model=data.llm_model,
        batch_size=data.batch_size,
        batch_overlap=data.batch_overlap,
        llm_config=data.llm_config,
        status="pending",
    )
    self.session.add(run)
    await self.session.commit()
    await self.session.refresh(run)
    return run
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/repositories/classification_run_repository.py
git commit -m "feat(classification): add llm_config to ClassificationRunCreate and repository"
```

---

## Task 3: Schema + service + router updates

**Files:**
- Modify: `backend/app/schemas/classification.py`
- Modify: `backend/app/services/classification/service.py`
- Modify: `backend/app/routers/classification.py`

- [ ] **Step 1: Update ClassificationRunCreateRequest schema**

In `backend/app/schemas/classification.py`, add `llm_config` to the create request. The field uses snake_case (no alias) to match the existing pattern in this schema — the frontend serializes manually in the API layer:

```python
class ClassificationRunCreateRequest(BaseModel):
    parse_run_id: UUID
    labels: list[str]
    llm_provider: str | None = None
    llm_model: str | None = None
    batch_size: int | None = None
    batch_overlap: int | None = None
    llm_config: dict | None = None
```

- [ ] **Step 2: Update ClassificationRunResponse schema**

In `ClassificationRunResponse`, add the new field with a camelCase alias (matching the existing `alias` pattern in this schema):

```python
class ClassificationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    parse_run_id: UUID = Field(..., alias="parseRunId")
    document_id: UUID = Field(..., alias="documentId")
    labels_requested: list[str] = Field(..., alias="labelsRequested")
    llm_provider: str = Field(..., alias="llmProvider")
    llm_model: str = Field(..., alias="llmModel")
    llm_config: dict | None = Field(None, alias="llmConfig")  # NEW
    status: str
    error: str | None = None
    batch_size: int = Field(..., alias="batchSize")
    batch_overlap: int = Field(..., alias="batchOverlap")
    input_tokens: int | None = Field(None, alias="inputTokens")
    output_tokens: int | None = Field(None, alias="outputTokens")
    duration_ms: int | None = Field(None, alias="durationMs")
    created_at: datetime = Field(..., alias="createdAt")
    regions: list[ClassificationRegionResponse] = []
```

- [ ] **Step 3: Update ClassificationService.execute()**

In `backend/app/services/classification/service.py`, add `system_prompt: str | None = None` to the `execute()` signature. Inside the method, replace the hardcoded `_SYSTEM_PROMPT` usage:

```python
async def execute(
    self,
    run_id: UUID,
    doc: ParsedDocument,
    labels: list[str],
    llm_provider: str,
    llm_model: str,
    batch_size: int,
    batch_overlap: int,
    system_prompt: str | None = None,
) -> None:
    await self.repo.update_status(run_id=run_id, status="running")
    start = time.monotonic()
    total_input = 0
    total_output = 0

    effective_system_prompt = system_prompt or _SYSTEM_PROMPT

    try:
        adapter = self.llm_registry.get(llm_provider)
        config = LLMConfig(
            provider=llm_provider,
            model=llm_model,
            temperature=0.0,
            max_tokens=4096,
            json_mode=True,
        )
        labels_str = ", ".join(labels)
        batches = build_batches(doc.page_count, batch_size, batch_overlap)
        all_batch_results: list[list[BatchPageResult]] = []

        for batch_start, batch_end in batches:
            serialized = serialize_pages(doc, batch_start, batch_end)
            messages = [
                {"role": "system", "content": effective_system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Labels to identify: {labels_str}\n\n"
                        f"Document pages:\n{serialized}"
                    ),
                },
            ]
            result = await adapter.complete(messages, config)
            total_input += result.usage.prompt_tokens
            total_output += result.usage.completion_tokens

            parsed = _BatchLLMResponse.model_validate_json(result.content)
            batch_page_results = [
                BatchPageResult(
                    page=p.page,
                    label_statuses=p.labels,
                    batch_start=batch_start,
                    batch_end=batch_end,
                )
                for p in parsed.pages
            ]
            all_batch_results.append(batch_page_results)

        resolved = resolve_page_statuses(all_batch_results)
        regions = assemble_regions(resolved, labels, doc)

        await self.repo.save_regions(run_id=run_id, regions=regions)
        duration_ms = int((time.monotonic() - start) * 1000)
        await self.repo.update_completed(
            run_id=run_id,
            input_tokens=total_input,
            output_tokens=total_output,
            duration_ms=duration_ms,
        )

    except Exception as exc:
        logger.exception("Classification run %s failed", run_id)
        await self.repo.update_status(run_id=run_id, status="failed", error=str(exc))
        raise
```

- [ ] **Step 4: Update _run_classification_background in router**

In `backend/app/routers/classification.py`, add `llm_config: dict | None` to the background task function and derive `system_prompt` from it before calling the service:

```python
async def _run_classification_background(
    run_id: UUID,
    parse_run_id: UUID,
    labels: list[str],
    llm_provider: str,
    llm_model: str,
    batch_size: int,
    batch_overlap: int,
    api_key: str | None,
    llm_config: dict | None = None,
) -> None:
    from app.cdm.models import ParsedDocument as CDMParsedDocument

    system_prompt: str | None = (llm_config or {}).get("system_prompt")

    try:
        async with AsyncSessionLocal() as session:
            repo = ClassificationRunRepository(session)
            pd_repo = ParsedDocumentRepository(session)

            pd_orm = await pd_repo.get_by_run(parse_run_id)
            if pd_orm is None:
                await repo.update_status(run_id=run_id, status="failed", error="ParsedDocument not found")
                return

            doc = CDMParsedDocument.model_validate(pd_orm.content)
            registry = _build_llm_registry(llm_provider, api_key)
            service = ClassificationService(repo=repo, llm_registry=registry)

            await service.execute(
                run_id=run_id,
                doc=doc,
                labels=labels,
                llm_provider=llm_provider,
                llm_model=llm_model,
                batch_size=batch_size,
                batch_overlap=batch_overlap,
                system_prompt=system_prompt,
            )
    except Exception:
        logger.exception("Classification background task failed for run %s", run_id)
        async with AsyncSessionLocal() as recovery_session:
            recovery_repo = ClassificationRunRepository(recovery_session)
            run = await recovery_repo.get(run_id)
            if run and run.status == "running":
                await recovery_repo.update_status(run_id=run_id, status="failed", error="Internal error — check server logs")
```

- [ ] **Step 5: Update _to_run_response in router**

In `backend/app/routers/classification.py`, add `llmConfig=run.llm_config` to the `_to_run_response` function:

```python
def _to_run_response(run, regions=None) -> ClassificationRunResponse:
    return ClassificationRunResponse(
        id=run.id,
        parseRunId=run.parse_run_id,
        documentId=run.document_id,
        labelsRequested=run.labels_requested,
        llmProvider=run.llm_provider,
        llmModel=run.llm_model,
        llmConfig=run.llm_config,
        status=run.status,
        error=run.error,
        batchSize=run.batch_size,
        batchOverlap=run.batch_overlap,
        inputTokens=run.input_tokens,
        outputTokens=run.output_tokens,
        durationMs=run.duration_ms,
        createdAt=run.created_at,
        regions=[
            ClassificationRegionResponse(
                id=r.id,
                label=r.label,
                pageStart=r.page_start,
                pageEnd=r.page_end,
                blockIds=r.block_ids,
                confidence=r.confidence,
                reasoning=r.reasoning,
                source=r.source,
            )
            for r in (regions or [])
        ],
    )
```

- [ ] **Step 6: Update create_classification_run endpoint**

In `backend/app/routers/classification.py`, in the `create_classification_run` endpoint, pass `llm_config` to `ClassificationRunCreate` and to the background task:

```python
@documents_router.post(
    "/{document_id}/classification-runs",
    response_model=ClassificationRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_classification_run(
    document_id: UUID,
    body: ClassificationRunCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(document_id, current_user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    llm_provider = body.llm_provider or settings.CLASSIFIER_LLM_PROVIDER
    llm_model = body.llm_model or settings.CLASSIFIER_LLM_MODEL
    batch_size = body.batch_size or 10
    batch_overlap = body.batch_overlap or 3

    repo = ClassificationRunRepository(db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=body.parse_run_id,
        document_id=document_id,
        labels_requested=body.labels,
        llm_provider=llm_provider,
        llm_model=llm_model,
        batch_size=batch_size,
        batch_overlap=batch_overlap,
        llm_config=body.llm_config,
    ))

    byok_provider = _classification_provider_to_byok(llm_provider)
    api_key: str | None = None
    if byok_provider:
        provider_key_repo = ProviderKeyRepository(db)
        api_key = await resolve_api_key(provider_key_repo, current_user.id, byok_provider)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No API key configured for provider '{llm_provider}'. "
                    "Add one in Settings → API Keys."
                ),
            )

    background_tasks.add_task(
        _run_classification_background,
        run_id=run.id,
        parse_run_id=body.parse_run_id,
        labels=body.labels,
        llm_provider=llm_provider,
        llm_model=llm_model,
        batch_size=batch_size,
        batch_overlap=batch_overlap,
        api_key=api_key,
        llm_config=body.llm_config,
    )

    return _to_run_response(run)
```

- [ ] **Step 7: Start backend — confirm no errors**

```
uv run --directory backend uvicorn app.main:app --reload
```

Expected: server starts cleanly. Stop with Ctrl+C.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/classification.py backend/app/services/classification/service.py backend/app/routers/classification.py
git commit -m "feat(classification): wire llm_config system prompt override through schema/service/router"
```

---

## Task 4: Frontend — types, API client, form

**Files:**
- Modify: `frontend/src/types/classification.ts`
- Modify: `frontend/src/api/classification.ts`
- Modify: `frontend/src/components/classification/ClassificationRunForm.tsx`
- Modify: `frontend/src/pages/NewClassificationRunPage.tsx`

- [ ] **Step 1: Update classification TypeScript types**

In `frontend/src/types/classification.ts`:

1. Add `llmConfig: Record<string, unknown> | null` to `ClassificationRun`:

```typescript
export interface ClassificationRun {
  id: string
  parseRunId: string
  documentId: string
  labelsRequested: string[]
  llmProvider: string
  llmModel: string
  llmConfig: Record<string, unknown> | null
  status: ClassificationRunStatus
  error: string | null
  batchSize: number
  batchOverlap: number
  inputTokens: number | null
  outputTokens: number | null
  durationMs: number | null
  createdAt: string
  regions: ClassificationRegion[]
}
```

2. Add `llmConfig?: { systemPrompt?: string }` to `ClassificationRunCreateRequest`:

```typescript
export interface ClassificationRunCreateRequest {
  parseRunId: string
  labels: string[]
  llmProvider?: string
  llmModel?: string
  batchSize?: number
  batchOverlap?: number
  llmConfig?: { systemPrompt?: string }
}
```

- [ ] **Step 2: Update classification API client**

In `frontend/src/api/classification.ts`, update `createClassificationRun` to serialize `llmConfig`:

```typescript
export async function createClassificationRun(
  documentId: string,
  data: ClassificationRunCreateRequest,
): Promise<ClassificationRun> {
  const response = await apiClient.post<ClassificationRun>(
    `/documents/${documentId}/classification-runs`,
    {
      parse_run_id: data.parseRunId,
      labels: data.labels,
      llm_provider: data.llmProvider,
      llm_model: data.llmModel,
      batch_size: data.batchSize,
      batch_overlap: data.batchOverlap,
      llm_config: data.llmConfig
        ? { system_prompt: data.llmConfig.systemPrompt ?? null }
        : null,
    },
  )
  return response.data
}
```

- [ ] **Step 3: Update ClassificationRunFormValues**

In `frontend/src/components/classification/ClassificationRunForm.tsx`, add `systemPrompt` to the form values interface:

```typescript
export interface ClassificationRunFormValues {
  labels: string[]
  llmProvider: string
  llmModel: string
  batchSize: number
  batchOverlap: number
  systemPrompt: string
}
```

- [ ] **Step 4: Add system prompt state and textarea to ClassificationRunForm**

In `ClassificationRunForm`, add state for `systemPrompt` and a textarea in the Advanced collapsible section.

Add state after `batchOverlap`:
```typescript
const [systemPrompt, setSystemPrompt] = useState(defaultValues?.systemPrompt ?? '')
```

Update `handleSubmit` to include it:
```typescript
const handleSubmit = () => {
  if (labels.length === 0) return
  onSubmit({ labels, llmProvider: provider, llmModel: model, batchSize, batchOverlap, systemPrompt })
}
```

In the `CollapsibleContent` (Advanced section), add after the batch overlap field:

```tsx
<div className="space-y-2 col-span-2">
  <Label htmlFor="system-prompt-override">System prompt override</Label>
  <Textarea
    id="system-prompt-override"
    value={systemPrompt}
    onChange={(e) => setSystemPrompt(e.target.value)}
    className="font-mono text-sm min-h-[120px]"
    placeholder="Leave blank to use the default classification prompt"
  />
</div>
```

Also add `Textarea` to the imports at the top of the file:
```typescript
import { Textarea } from '@/components/ui/textarea'
```

- [ ] **Step 5: Update NewClassificationRunPage to pass systemPrompt**

In `frontend/src/pages/NewClassificationRunPage.tsx`, update `handleSubmit` to include `llmConfig`:

```typescript
const handleSubmit = async (values: ClassificationRunFormValues) => {
  if (!selectedDocumentId || !selectedParseRunId) return
  setIsSubmitting(true)
  try {
    const run = await createClassificationRun(selectedDocumentId, {
      parseRunId: selectedParseRunId,
      labels: values.labels,
      llmProvider: values.llmProvider,
      llmModel: values.llmModel,
      batchSize: values.batchSize,
      batchOverlap: values.batchOverlap,
      llmConfig: values.systemPrompt ? { systemPrompt: values.systemPrompt } : undefined,
    })
    toast.success('Classification started')
    navigate(`/classify/${run.id}`)
  } catch (err) {
    toast.error('Failed to start classification', {
      description: err instanceof Error ? err.message : 'An error occurred',
    })
  } finally {
    setIsSubmitting(false)
  }
}
```

- [ ] **Step 6: Build frontend**

```
npm --prefix frontend run build
```

Fix any TypeScript errors before proceeding.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/classification.ts frontend/src/api/classification.ts frontend/src/components/classification/ClassificationRunForm.tsx frontend/src/pages/NewClassificationRunPage.tsx
git commit -m "feat(classification): add system prompt override to classification run form"
```

---

## Task 5: Smoke test

- [ ] **Step 1: Start backend + frontend**

```
uv run --directory backend uvicorn app.main:app --reload
npm --prefix frontend run dev
```

- [ ] **Step 2: Test default (no override)**

1. Navigate to a document → New Classification Run
2. Select document → parse run → configure step
3. Submit without opening Advanced
4. Confirm run is created and uses the default system prompt (verify via logs or successful classification)

- [ ] **Step 3: Test with custom system prompt**

1. Start a new classification run
2. Open the Advanced section → enter a custom system prompt
3. Submit → confirm the run is created
4. Check the run in the DB or API response — `llm_config` should be `{"system_prompt": "<your text>"}`

- [ ] **Step 4: Run backend tests**

```
uv run --directory backend python -m pytest tests/ -v -k "classif"
```

Expected: all pass. Fix any failures caused by the new `llm_config` field or `system_prompt` param addition.
