# Prompt Config — Plan 5: Extraction Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `PromptConfig` and a user-editable `user_prompt_template` into `ExtractionSchema` — add two nullable columns, thread them through the repository/service/router, and expose them in the schema editor dialog via `<PromptConfigEditor>` + a template textarea.

**Architecture:** One Alembic migration adds `llm_config JSON` and `user_prompt_template TEXT` (nullable, no backfill) to `extraction_schemas`. The repository, service, and router are updated to accept and persist both fields. When `run_extraction()` is called, it merges `system_prompt` from `llm_config` and `user_prompt_template` into the per-run `config` dict — the `OllamaExtractor` already reads `cfg.get("system_prompt")` and `cfg.get("user_prompt_template")`, so no adapter changes are needed. The frontend adds `<PromptConfigEditor>` + template textarea to `ExtractionSchemaEditor.tsx`.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic / Pydantic v2 — React 18 / TypeScript / shadcn/ui

**Spec:** `docs/superpowers/specs/2026-05-27-unified-prompt-interface-design.md`

**Prerequisites:** Plan 1 complete (`PromptConfig` schema, `PromptConfigEditor` component, `usePromptConfig` hook all exist).

**DB migration:** 1 migration on `extraction_schemas` — add `llm_config JSON` + `user_prompt_template TEXT`, both nullable with no backfill.

---

## File Map

**Modified backend files:**
- `backend/app/models/extraction_schema.py` — add `llm_config` + `user_prompt_template` columns
- `backend/app/repositories/extraction_schema_repository.py` — add params to `create()` + `update()`
- `backend/app/schemas/extraction_result.py` — add fields to `ExtractionSchemaCreate`, `ExtractionSchemaUpdate`, `ExtractionSchemaResponse`
- `backend/app/services/extraction_service.py` — thread new params through `create_schema()`, `update_schema()`, `run_extraction()`
- `backend/app/routers/extraction.py` — pass new body fields to service

**New backend files:**
- `backend/alembic/versions/<rev>_extraction_schema_llm_config.py` — migration

**Modified frontend files:**
- `frontend/src/types/extraction.ts` — add `llmConfig` + `userPromptTemplate` to schema types
- `frontend/src/api/extraction.ts` — serialize new fields in create/update requests
- `frontend/src/components/extraction/ExtractionSchemaEditor.tsx` — add `PromptConfigEditor` + template textarea

---

## Task 1: DB migration — add llm_config + user_prompt_template to extraction_schemas

**Files:**
- Modify: `backend/app/models/extraction_schema.py`
- New: Alembic migration

- [ ] **Step 1: Update the ExtractionSchema model**

In `backend/app/models/extraction_schema.py`, after the `extraction_target` column add two new nullable columns. `JSON` and `Text` are already imported:

```python
extraction_target: Mapped[str] = mapped_column(
    String(30), nullable=False, default="PER_DOC", server_default="PER_DOC"
)
llm_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
user_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: Generate the migration**

```
uv run --directory backend alembic revision --autogenerate -m "extraction_schema_llm_config"
```

Open the generated file in `backend/alembic/versions/`. Replace `upgrade()` and `downgrade()` with:

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

Expected: `Running upgrade <prev> -> <new>, extraction_schema_llm_config`

- [ ] **Step 4: Verify**

```
uv run --directory backend alembic current
```

Expected: shows the new revision as the current head.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/extraction_schema.py backend/alembic/versions/
git commit -m "feat(extraction): add llm_config and user_prompt_template columns to extraction_schemas"
```

---

## Task 2: Repository update

**Files:**
- Modify: `backend/app/repositories/extraction_schema_repository.py`

- [ ] **Step 1: Update create()**

In `backend/app/repositories/extraction_schema_repository.py`, add `llm_config` and `user_prompt_template` to the `create()` signature and constructor:

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

- [ ] **Step 2: Update update()**

In the `update()` method, add `llm_config: dict | None = None` and `user_prompt_template: str | None = None` to the signature, and apply them when present:

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

- [ ] **Step 3: Commit**

```bash
git add backend/app/repositories/extraction_schema_repository.py
git commit -m "feat(extraction): add llm_config and user_prompt_template to extraction schema repository"
```

---

## Task 3: Schema + service + router updates

**Files:**
- Modify: `backend/app/schemas/extraction_result.py`
- Modify: `backend/app/services/extraction_service.py`
- Modify: `backend/app/routers/extraction.py`

- [ ] **Step 1: Update ExtractionSchemaCreate**

In `backend/app/schemas/extraction_result.py`, add imports and new fields to `ExtractionSchemaCreate`. The `PromptConfig` import goes at the top:

```python
from app.schemas.prompt_config import PromptConfig
```

Updated `ExtractionSchemaCreate`:

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

- [ ] **Step 2: Update ExtractionSchemaUpdate**

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

- [ ] **Step 3: Update ExtractionSchemaResponse and from_orm_model**

Add `llm_config` and `user_prompt_template` fields to `ExtractionSchemaResponse`, and update `from_orm_model` to populate them:

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

- [ ] **Step 4: Update ExtractionService.create_schema()**

In `backend/app/services/extraction_service.py`, add `llm_config` and `user_prompt_template` to `create_schema()`:

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

- [ ] **Step 5: Update ExtractionService.update_schema()**

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

- [ ] **Step 6: Update ExtractionService.run_extraction() to merge prompt overrides**

In `run_extraction()`, after building `merged_config`, merge `system_prompt` from `llm_config` and `user_prompt_template` so the adapter receives them:

Find this block:
```python
merged_config = dict(config or {})
merged_config["extraction_target"] = schema.extraction_target
```

Replace with:
```python
merged_config = dict(config or {})
merged_config["extraction_target"] = schema.extraction_target
if schema.llm_config:
    system_prompt = schema.llm_config.get("system_prompt")
    if system_prompt:
        merged_config["system_prompt"] = system_prompt
if schema.user_prompt_template:
    merged_config["user_prompt_template"] = schema.user_prompt_template
```

- [ ] **Step 7: Update extraction router — create endpoint**

In `backend/app/routers/extraction.py`, update `create_extraction_schema` to pass new fields to the service:

```python
@router.post(
    "/projects/{project_id}/extraction-schemas",
    response_model=ExtractionSchemaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an extraction schema",
)
async def create_extraction_schema(
    project_id: UUID,
    body: ExtractionSchemaCreate,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionService = Depends(get_extraction_service),
):
    try:
        return await service.create_schema(
            project_id=project_id,
            user_id=current_user.id,
            name=body.name,
            schema_definition=body.schema_definition,
            description=body.description,
            extraction_target=body.extraction_target,
            llm_config=body.llm_config.model_dump(by_alias=False, mode="json") if body.llm_config else None,
            user_prompt_template=body.user_prompt_template,
        )
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
```

- [ ] **Step 8: Update extraction router — update endpoint**

```python
@router.put(
    "/extraction-schemas/{schema_id}",
    response_model=ExtractionSchemaResponse,
    summary="Update an extraction schema",
)
async def update_extraction_schema(
    schema_id: UUID,
    body: ExtractionSchemaUpdate,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionService = Depends(get_extraction_service),
):
    try:
        return await service.update_schema(
            schema_id=schema_id,
            user_id=current_user.id,
            name=body.name,
            description=body.description,
            schema_definition=body.schema_definition,
            extraction_target=body.extraction_target,
            llm_config=body.llm_config.model_dump(by_alias=False, mode="json") if body.llm_config else None,
            user_prompt_template=body.user_prompt_template,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 9: Start backend — confirm no errors**

```
uv run --directory backend uvicorn app.main:app --reload
```

Expected: server starts cleanly. Stop with Ctrl+C.

- [ ] **Step 10: Commit**

```bash
git add backend/app/schemas/extraction_result.py backend/app/services/extraction_service.py backend/app/routers/extraction.py
git commit -m "feat(extraction): wire llm_config and user_prompt_template through extraction schema stack"
```

---

## Task 4: Frontend — types, API client, schema editor

**Files:**
- Modify: `frontend/src/types/extraction.ts`
- Modify: `frontend/src/api/extraction.ts`
- Modify: `frontend/src/components/extraction/ExtractionSchemaEditor.tsx`

- [ ] **Step 1: Update extraction TypeScript types**

In `frontend/src/types/extraction.ts`:

1. Add import at the top:
```typescript
import type { PromptConfig } from '@/types/prompt-config'
```

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

3. Add optional fields to `ExtractionSchemaCreate`:
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

4. Add optional fields to `ExtractionSchemaUpdate`:
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

- [ ] **Step 2: Update extraction API client**

In `frontend/src/api/extraction.ts`, update `createExtractionSchema` and `updateExtractionSchema` to serialize the new fields. These functions currently pass `data` directly to axios, which sends camelCase keys. The backend's `ExtractionSchemaCreate` uses `alias="llmConfig"` and `populate_by_name=True`, so camelCase is accepted.

The existing calls already pass `data` directly — axios serializes the TypeScript object as JSON with camelCase keys. No changes are needed to the API function body for `create` and `update` since the new fields (`llmConfig`, `userPromptTemplate`) are camelCase and the backend aliases accept them directly.

Verify by checking `createExtractionSchema`:
```typescript
export async function createExtractionSchema(
  projectId: string,
  data: ExtractionSchemaCreate
): Promise<ExtractionSchema> {
  const response = await apiClient.post<ExtractionSchema>(
    `/projects/${projectId}/extraction-schemas`,
    data  // camelCase keys are already accepted by the backend's populate_by_name=True config
  )
  return response.data
}
```

If the function body is already `data` (not a manually constructed object), no changes are needed. If it manually constructs the body with snake_case, update it to include:
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
} : undefined,
user_prompt_template: data.userPromptTemplate ?? undefined,
```

- [ ] **Step 3: Update ExtractionSchemaEditor — imports + state**

In `frontend/src/components/extraction/ExtractionSchemaEditor.tsx`:

Add imports at the top:
```typescript
import { usePromptConfig } from '@/hooks/usePromptConfig'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
import type { PromptConfig } from '@/types/prompt-config'
```

Inside the component, add state for `userPromptTemplate` after the `error` state:
```typescript
const [userPromptTemplate, setUserPromptTemplate] = useState('')
```

Add the `usePromptConfig` hook after the existing `useState` declarations:
```typescript
const { promptConfig, setPromptConfig, setProvider: setPromptConfigProvider } = usePromptConfig()
```

- [ ] **Step 4: Update useEffect to populate from existing schema**

In the `useEffect` that populates form fields from `schema`, add initialization for the new fields:

```typescript
useEffect(() => {
  if (schema) {
    setName(schema.name)
    setDescription(schema.description || '')
    setSchemaText(JSON.stringify(schema.schemaDefinition, null, 2))
    setExtractionTarget(schema.extractionTarget)
    setUserPromptTemplate(schema.userPromptTemplate || '')
    if (schema.llmConfig) {
      const lc = schema.llmConfig
      setPromptConfig({
        systemPrompt: lc.system_prompt as string | undefined,
        provider: lc.provider as string | undefined,
        model: lc.model as string | undefined,
        temperature: lc.temperature as number | undefined,
        maxTokens: lc.max_tokens as number | undefined,
      })
    }
  } else {
    setName('')
    setDescription('')
    setSchemaText('{\n  "type": "object",\n  "properties": {\n    \n  }\n}')
    setExtractionTarget('PER_DOC')
    setUserPromptTemplate('')
  }
  setError(null)
}, [schema, open])
```

- [ ] **Step 5: Update handleSave to include new fields**

In `handleSave`, include `llmConfig` and `userPromptTemplate` in both create and update objects:

```typescript
const handleSave = async () => {
  setError(null)

  if (!name.trim()) {
    setError('Name is required')
    return
  }

  let parsedSchema: Record<string, unknown>
  try {
    parsedSchema = JSON.parse(schemaText)
  } catch {
    setError('Invalid JSON schema')
    return
  }

  if (parsedSchema.type !== 'object') {
    setError('Root schema type must be "object"')
    return
  }

  const llmConfigValue: PromptConfig | undefined =
    promptConfig.systemPrompt || promptConfig.provider || promptConfig.model
      ? promptConfig
      : undefined

  setIsSaving(true)
  try {
    if (isEditing) {
      const update: ExtractionSchemaUpdate = {
        name: name.trim(),
        description: description.trim() || undefined,
        schemaDefinition: parsedSchema,
        extractionTarget,
        llmConfig: llmConfigValue,
        userPromptTemplate: userPromptTemplate.trim() || undefined,
      }
      await onSave(update)
    } else {
      const create: ExtractionSchemaCreate = {
        name: name.trim(),
        description: description.trim() || undefined,
        schemaDefinition: parsedSchema,
        extractionTarget,
        llmConfig: llmConfigValue,
        userPromptTemplate: userPromptTemplate.trim() || undefined,
      }
      await onSave(create)
    }
    onOpenChange(false)
  } catch (err) {
    setError(err instanceof Error ? err.message : 'Failed to save schema')
  } finally {
    setIsSaving(false)
  }
}
```

- [ ] **Step 6: Add PromptConfigEditor + template textarea to JSX**

In the `DialogContent`, add a "Prompt & Model" section after the JSON Schema textarea. Add before the error `<p>`:

```tsx
<div className="space-y-2">
  <h3 className="text-sm font-medium">Prompt & Model</h3>
  <PromptConfigEditor
    value={promptConfig}
    onChange={setPromptConfig}
    onProviderChange={setPromptConfigProvider}
    capabilities={{ thinking: false, structuredOutput: false }}
  />
</div>

<div className="space-y-2">
  <Label htmlFor="user-prompt-template">User prompt template</Label>
  <p className="text-xs text-muted-foreground">
    Available variables: <code>{'{schema_json}'}</code> and <code>{'{document_context}'}</code>.
    Leave blank to use the default template.
  </p>
  <Textarea
    id="user-prompt-template"
    value={userPromptTemplate}
    onChange={(e) => setUserPromptTemplate(e.target.value)}
    className="font-mono text-sm min-h-[120px]"
    placeholder="Extract structured data from the following document..."
  />
</div>
```

- [ ] **Step 7: Build frontend**

```
npm --prefix frontend run build
```

Fix any TypeScript errors before proceeding.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/types/extraction.ts frontend/src/api/extraction.ts frontend/src/components/extraction/ExtractionSchemaEditor.tsx
git commit -m "feat(extraction): add PromptConfigEditor and user_prompt_template to ExtractionSchemaEditor"
```

---

## Task 5: Smoke test

- [ ] **Step 1: Start backend + frontend**

```
uv run --directory backend uvicorn app.main:app --reload
npm --prefix frontend run dev
```

- [ ] **Step 2: Test schema create with prompt config**

1. Navigate to Extraction → New Schema
2. Fill in name, schema JSON, extraction target
3. In the Prompt & Model section: enter a custom system prompt, set provider and model
4. Enter a custom user prompt template using `{schema_json}` and `{document_context}`
5. Save — confirm no errors
6. Reopen the schema editor for the saved schema
7. Confirm the system prompt, model, and user prompt template are pre-populated

- [ ] **Step 3: Test extraction runs use the custom prompt**

1. Run extraction on a document using the schema with a custom system prompt
2. Confirm the extraction uses the custom prompt (check extraction result / verify via backend logs that `cfg.get("system_prompt")` returns your custom value)

- [ ] **Step 4: Test with default prompts (no override)**

1. Create a schema without filling in Prompt & Model or user prompt template
2. Run extraction — confirm it still works using the adapter defaults

- [ ] **Step 5: Run backend tests**

```
uv run --directory backend python -m pytest tests/ -v -k "extract"
```

Expected: all pass. Fix any failures caused by the new optional params on `create_schema` / `update_schema`.
