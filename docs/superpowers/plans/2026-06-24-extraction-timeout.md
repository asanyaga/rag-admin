# Configurable Extraction Timeout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users set a per-job timeout (1–120 minutes, default 10) on extraction runs so large documents no longer fail prematurely.

**Architecture:** A nullable `timeout_minutes` column on `extraction_results` carries the per-job value. The backend stale-reaper reads it (falling back to 10 min). The frontend form sends it as a top-level field on the run request; the hook uses it to set its own polling deadline.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic (backend); React 18 / TypeScript / Vitest (frontend).

## Global Constraints

- `timeout_minutes` is a top-level field on `RunExtractionRequest` — not nested in `ChunkingConfig`
- Valid range: 1–120 (inclusive). Pydantic enforces `ge=1, le=120`; `NULL` / omitted means "use default 10"
- Frontend fallback default must match backend default: **10 minutes** (fixing the previous 5-min frontend mismatch)
- All backend tests: `uv run python -m pytest -o "addopts=" <path> -v`
- All frontend tests: `npx vitest run <path>`
- Run commands from repo root using `--directory` / `-C` flags, never `cd`

---

## File Map

| File | Change |
|---|---|
| `backend/alembic/versions/<rev>_add_timeout_minutes_to_extraction_results.py` | **Create** — migration adding nullable `timeout_minutes` column |
| `backend/app/models/extraction_result.py` | **Modify** — add `timeout_minutes: Mapped[int \| None]` |
| `backend/app/schemas/extraction_result.py` | **Modify** — add field to `RunExtractionRequest`; add field to `ExtractionResultResponse` + `from_orm_model` |
| `backend/app/repositories/extraction_result_repository.py` | **Modify** — add `timeout_minutes` param to `create()` |
| `backend/app/services/extraction_service.py` | **Modify** — thread `timeout_minutes` through `run_extraction()`; replace `STALE_TIMEOUT` in `_reap_stale()` |
| `backend/app/routers/extraction.py` | **Modify** — pass `body.timeout_minutes` to `service.run_extraction()` |
| `backend/tests/schemas/test_extraction_result_schemas.py` | **Modify** — add schema validation tests |
| `backend/tests/services/test_extraction_service.py` | **Modify** — add `_reap_stale` and `run_extraction` tests |
| `frontend/src/types/extraction.ts` | **Modify** — add `timeoutMinutes` to `RunExtractionRequest`, `RunWithParseRequest.extractionConfig`, `ExtractionResult` |
| `frontend/src/components/extraction/ExtractionForm.tsx` | **Modify** — add form state + input field |
| `frontend/src/hooks/useExtractionResults.ts` | **Modify** — replace hard-coded polling timeout with per-job value |
| `frontend/src/hooks/useExtractionResults.test.ts` | **Modify** — add polling-timeout tests |

---

## Task 1: DB Migration + ORM Model

**Files:**
- Create: `backend/alembic/versions/<rev>_add_timeout_minutes_to_extraction_results.py`
- Modify: `backend/app/models/extraction_result.py`

**Interfaces:**
- Produces: `ExtractionResult.timeout_minutes: int | None` ORM attribute used by Tasks 2–3

- [ ] **Step 1: Generate the migration file**

```bash
uv run --directory backend alembic revision --autogenerate -m "add_timeout_minutes_to_extraction_results"
```

Alembic will create a file under `backend/alembic/versions/`. Open it and replace its `upgrade`/`downgrade` with the following (autogenerate may produce nothing if it doesn't detect the model change yet — that's fine, replace manually):

```python
import sqlalchemy as sa
from alembic import op

def upgrade() -> None:
    op.add_column(
        "extraction_results",
        sa.Column("timeout_minutes", sa.Integer(), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("extraction_results", "timeout_minutes")
```

- [ ] **Step 2: Add the column to the ORM model**

In `backend/app/models/extraction_result.py`, add after the `started_at` column (line 55):

```python
timeout_minutes: Mapped[int | None] = mapped_column(
    sa.Integer(), nullable=True
)
```

- [ ] **Step 3: Run the migration**

```bash
uv run --directory backend alembic upgrade head
```

Expected: `Running upgrade <prev> -> <rev>, add_timeout_minutes_to_extraction_results`

- [ ] **Step 4: Smoke-test the column exists**

```bash
uv run --directory backend python -c "
from app.models.extraction_result import ExtractionResult
import sqlalchemy as sa
cols = {c.name: c for c in ExtractionResult.__table__.columns}
assert 'timeout_minutes' in cols, 'column missing'
assert cols['timeout_minutes'].nullable, 'must be nullable'
print('OK')
"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/ backend/app/models/extraction_result.py
git commit -m "feat(extraction): add timeout_minutes column to extraction_results"
```

---

## Task 2: Backend Schema + Repository + Service

**Files:**
- Modify: `backend/app/schemas/extraction_result.py`
- Modify: `backend/app/repositories/extraction_result_repository.py`
- Modify: `backend/app/services/extraction_service.py`
- Modify: `backend/tests/schemas/test_extraction_result_schemas.py`
- Modify: `backend/tests/services/test_extraction_service.py`

**Interfaces:**
- Consumes: `ExtractionResult.timeout_minutes` (Task 1)
- Produces:
  - `RunExtractionRequest.timeout_minutes: int | None` — Pydantic field with `ge=1, le=120`
  - `ExtractionResultResponse.timeout_minutes: int | None` — included in `from_orm_model()`
  - `ExtractionResultRepository.create(..., timeout_minutes: int | None = None)`
  - `ExtractionService.run_extraction(..., timeout_minutes: int | None = None)`

- [ ] **Step 1: Write the failing schema tests**

Append to `backend/tests/schemas/test_extraction_result_schemas.py`:

```python
class TestRunExtractionRequestTimeout:
    def test_accepts_valid_timeout(self):
        req = RunExtractionRequest.model_validate({
            "parseRunId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "extractionSchemaId": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
            "extractionMethod": "llm",
            "timeout_minutes": 30,
        })
        assert req.timeout_minutes == 30

    def test_rejects_zero(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RunExtractionRequest.model_validate({
                "parseRunId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "extractionSchemaId": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
                "extractionMethod": "llm",
                "timeout_minutes": 0,
            })

    def test_rejects_121(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RunExtractionRequest.model_validate({
                "parseRunId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "extractionSchemaId": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
                "extractionMethod": "llm",
                "timeout_minutes": 121,
            })

    def test_omitted_timeout_is_none(self):
        req = RunExtractionRequest.model_validate({
            "parseRunId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "extractionSchemaId": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
            "extractionMethod": "llm",
        })
        assert req.timeout_minutes is None


class TestExtractionResultResponseTimeout:
    def _make_mock_orm(self, **kwargs):
        from unittest.mock import MagicMock
        from uuid import uuid4
        from datetime import datetime, timezone
        from app.models.extraction_result import ExtractionResultStatus
        obj = MagicMock()
        obj.id = uuid4()
        obj.document_id = uuid4()
        obj.source_parse_run_id = None
        obj.extraction_schema_id = uuid4()
        obj.schema_definition_snapshot = {}
        obj.extraction_method = "llm"
        obj.config = None
        obj.structured_data = None
        obj.citations = None
        obj.provider_response_raw = None
        obj.extraction_metadata = None
        obj.status = ExtractionResultStatus.pending
        obj.status_message = None
        obj.started_at = None
        obj.created_by = uuid4()
        obj.created_at = datetime.now(timezone.utc)
        obj.updated_at = datetime.now(timezone.utc)
        obj.timeout_minutes = kwargs.get("timeout_minutes", None)
        return obj

    def test_timeout_minutes_serialised(self):
        obj = self._make_mock_orm(timeout_minutes=45)
        resp = ExtractionResultResponse.from_orm_model(obj)
        assert resp.timeout_minutes == 45

    def test_null_timeout_serialised(self):
        obj = self._make_mock_orm(timeout_minutes=None)
        resp = ExtractionResultResponse.from_orm_model(obj)
        assert resp.timeout_minutes is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest -o "addopts=" tests/schemas/test_extraction_result_schemas.py -v
```

Expected: `FAILED` on the new tests (`timeout_minutes` field not found).

- [ ] **Step 3: Add `timeout_minutes` to `RunExtractionRequest`**

In `backend/app/schemas/extraction_result.py`, update `RunExtractionRequest`:

```python
class RunExtractionRequest(BaseModel):
    """Request to run an extraction against a CDM ParsedDocument."""
    parse_run_id: UUID = Field(..., alias="parseRunId")
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")
    extraction_method: str = Field(..., alias="extractionMethod")
    config: dict | None = None
    llm_config: PromptConfig | None = Field(None, alias="llmConfig")
    user_prompt_template: str | None = Field(None, alias="userPromptTemplate")
    preprocess: list[dict] | None = None
    chunking: dict | None = None
    timeout_minutes: int | None = Field(default=None, ge=1, le=120)

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 4: Add `timeout_minutes` to `ExtractionResultResponse`**

In `ExtractionResultResponse`, add the field and wire `from_orm_model`:

```python
class ExtractionResultResponse(BaseModel):
    """Full extraction result response."""
    id: UUID = Field(..., alias="id")
    document_id: UUID = Field(..., alias="documentId")
    extraction_schema_id: UUID = Field(..., alias="extractionSchemaId")
    schema_definition_snapshot: dict = Field(..., alias="schemaDefinitionSnapshot")
    extraction_method: str = Field(..., alias="extractionMethod")
    config: dict | None = None
    structured_data: dict | None = Field(None, alias="structuredData")
    citations: list | None = Field(None, alias="citations")
    provider_response_raw: dict | None = Field(None, alias="providerResponseRaw")
    extraction_metadata: dict | None = Field(None, alias="extractionMetadata")
    status: ExtractionResultStatus
    status_message: str | None = Field(None, alias="statusMessage")
    started_at: datetime | None = Field(None, alias="startedAt")
    source_parse_run_id: UUID | None = Field(None, alias="sourceParseRunId")
    timeout_minutes: int | None = Field(None, alias="timeoutMinutes")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_model(cls, obj) -> "ExtractionResultResponse":
        return cls(
            id=obj.id,
            documentId=obj.document_id,
            extractionSchemaId=obj.extraction_schema_id,
            schemaDefinitionSnapshot=obj.schema_definition_snapshot,
            extractionMethod=obj.extraction_method,
            config=obj.config,
            structuredData=obj.structured_data,
            citations=obj.citations,
            providerResponseRaw=obj.provider_response_raw,
            extractionMetadata=obj.extraction_metadata,
            status=obj.status,
            statusMessage=obj.status_message,
            startedAt=obj.started_at,
            sourceParseRunId=obj.source_parse_run_id,
            timeoutMinutes=obj.timeout_minutes,
            createdBy=obj.created_by,
            createdAt=obj.created_at,
            updatedAt=obj.updated_at,
        )
```

- [ ] **Step 5: Add `timeout_minutes` to `ExtractionResultRepository.create()`**

In `backend/app/repositories/extraction_result_repository.py`, update `create()`:

```python
async def create(
    self,
    document_id: UUID,
    extraction_schema_id: UUID,
    schema_definition_snapshot: dict,
    extraction_method: str,
    created_by: UUID,
    config: dict | None = None,
    source_parse_run_id: UUID | None = None,
    timeout_minutes: int | None = None,
) -> ExtractionResult:
    """Create a new pending extraction result."""
    result = ExtractionResult(
        document_id=document_id,
        extraction_schema_id=extraction_schema_id,
        schema_definition_snapshot=schema_definition_snapshot,
        extraction_method=extraction_method,
        config=config,
        created_by=created_by,
        source_parse_run_id=source_parse_run_id,
        timeout_minutes=timeout_minutes,
        status=ExtractionResultStatus.pending,
    )
    self.session.add(result)
    await self.session.commit()
    await self.session.refresh(result)
    return result
```

- [ ] **Step 6: Write the failing service tests for `_reap_stale`**

Append to `backend/tests/services/test_extraction_service.py`:

```python
class TestReapStale:
    """_reap_stale uses per-job timeout_minutes, falling back to 10."""

    def _make_result(self, *, minutes_old: int, timeout_minutes: int | None):
        from unittest.mock import MagicMock
        result = MagicMock()
        result.status = ExtractionResultStatus.pending
        result.timeout_minutes = timeout_minutes
        result.started_at = None
        result.created_at = datetime.utcnow() - timedelta(minutes=minutes_old)
        return result

    @pytest.mark.asyncio
    @pytest.mark.parametrize("timeout_minutes,minutes_old,expect_reaped", [
        (None, 11, True),   # NULL → default 10 min; 11 min old → reaped
        (None, 9, False),   # NULL → default 10 min; 9 min old → not reaped
        (5, 6, True),       # explicit 5 min; 6 min old → reaped
        (5, 4, False),      # explicit 5 min; 4 min old → not reaped
        (60, 45, False),    # explicit 60 min; 45 min old → not reaped
        (60, 61, True),     # explicit 60 min; 61 min old → reaped
    ])
    async def test_reap_stale_uses_per_job_timeout(
        self, timeout_minutes, minutes_old, expect_reaped
    ):
        result = self._make_result(
            minutes_old=minutes_old, timeout_minutes=timeout_minutes
        )
        mock_result_repo = AsyncMock()
        mock_result_repo.update_status.return_value = result

        service = _make_service(result_repo=mock_result_repo)
        await service._reap_stale(result)

        if expect_reaped:
            mock_result_repo.update_status.assert_called_once()
            args = mock_result_repo.update_status.call_args
            assert ExtractionResultStatus.failed == args[0][1]
            expected_n = timeout_minutes or 10
            assert f"exceeded {expected_n} minutes" in args[0][2]
        else:
            mock_result_repo.update_status.assert_not_called()
```

Also add an import at the top of the test file if not present: `from datetime import timedelta`

- [ ] **Step 7: Run service tests to confirm failure**

```bash
uv run --directory backend python -m pytest -o "addopts=" tests/services/test_extraction_service.py::TestReapStale -v
```

Expected: `FAILED` — `STALE_TIMEOUT` is still hard-coded.

- [ ] **Step 8: Update `ExtractionService`**

In `backend/app/services/extraction_service.py`:

1. **Remove** the module-level constant `STALE_TIMEOUT = timedelta(minutes=10)`.

2. **Update `run_extraction()`** to accept and pass `timeout_minutes`:

```python
async def run_extraction(
    self,
    parse_run_id: UUID,
    extraction_schema_id: UUID,
    extraction_method: str,
    user_id: UUID,
    config: dict | None = None,
    llm_config=None,
    user_prompt_template: str | None = None,
    timeout_minutes: int | None = None,
) -> ExtractionResultResponse:
    """Create a pending extraction result anchored to a CDM ParsedDocument."""
    orm_parsed_doc = await self.parsed_document_repo.get_by_run(parse_run_id)
    if not orm_parsed_doc:
        raise NotFoundError(f"ParsedDocument for parse_run_id {parse_run_id} not found")

    schema = await self.schema_repo.get_by_id(extraction_schema_id)
    if not schema:
        raise NotFoundError(f"Extraction schema {extraction_schema_id} not found")

    document = await self.document_repo.get_by_source_document_for_project(
        source_document_id=orm_parsed_doc.source_document_id,
        project_id=schema.project_id,
    )
    if not document:
        raise NotFoundError(
            f"No document found in project {schema.project_id} "
            f"for source_document {orm_parsed_doc.source_document_id}"
        )

    merged_config = dict(config or {})
    merged_config["extraction_target"] = schema.extraction_target
    if llm_config is not None:
        merged_config["llm_config"] = llm_config.model_dump(by_alias=False, mode="json")
    if user_prompt_template:
        merged_config["user_prompt_template"] = user_prompt_template

    result = await self.result_repo.create(
        document_id=document.id,
        source_parse_run_id=parse_run_id,
        extraction_schema_id=extraction_schema_id,
        schema_definition_snapshot=schema.schema_definition,
        extraction_method=extraction_method,
        created_by=user_id,
        config=merged_config,
        timeout_minutes=timeout_minutes,
    )
    return ExtractionResultResponse.from_orm_model(result)
```

3. **Replace `_reap_stale()`**:

```python
async def _reap_stale(self, result):
    if result.status != ExtractionResultStatus.pending:
        return result
    reference_time = result.started_at or result.created_at
    if not reference_time:
        return result
    age = datetime.utcnow() - reference_time.replace(tzinfo=None)
    effective_timeout = result.timeout_minutes or 10
    if age > timedelta(minutes=effective_timeout):
        result = await self.result_repo.update_status(
            result.id, ExtractionResultStatus.failed,
            f"Extraction job timed out (exceeded {effective_timeout} minutes)",
        )
    return result
```

- [ ] **Step 9: Run all schema + service tests**

```bash
uv run --directory backend python -m pytest -o "addopts=" tests/schemas/test_extraction_result_schemas.py tests/services/test_extraction_service.py -v
```

Expected: all PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/app/schemas/extraction_result.py backend/app/repositories/extraction_result_repository.py backend/app/services/extraction_service.py backend/tests/schemas/test_extraction_result_schemas.py backend/tests/services/test_extraction_service.py
git commit -m "feat(extraction): thread timeout_minutes through schema, repo, and service"
```

---

## Task 3: Router Wiring

**Files:**
- Modify: `backend/app/routers/extraction.py`

**Interfaces:**
- Consumes: `RunExtractionRequest.timeout_minutes` (Task 2), `ExtractionService.run_extraction(..., timeout_minutes)` (Task 2)

- [ ] **Step 1: Pass `timeout_minutes` in the `run_extraction` router call**

In `backend/app/routers/extraction.py`, find the `service.run_extraction(...)` call (around line 219) and add the new argument:

```python
result = await service.run_extraction(
    parse_run_id=body.parse_run_id,
    extraction_schema_id=body.extraction_schema_id,
    extraction_method=body.extraction_method,
    user_id=current_user.id,
    config=body.config,
    llm_config=body.llm_config,
    user_prompt_template=body.user_prompt_template,
    timeout_minutes=body.timeout_minutes,
)
```

- [ ] **Step 2: Verify the app starts without errors**

```bash
uv run --directory backend uvicorn app.main:app --reload
```

Expected: server starts. Stop with Ctrl-C.

- [ ] **Step 3: Run the full backend test suite to catch regressions**

```bash
uv run --directory backend python -m pytest -o "addopts=" -v
```

Expected: all existing tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/extraction.py
git commit -m "feat(extraction): pass timeout_minutes from router to service"
```

---

## Task 4: Frontend — Types, Form, Hook

**Files:**
- Modify: `frontend/src/types/extraction.ts`
- Modify: `frontend/src/components/extraction/ExtractionForm.tsx`
- Modify: `frontend/src/hooks/useExtractionResults.ts`
- Modify: `frontend/src/hooks/useExtractionResults.test.ts`

**Interfaces:**
- Consumes: `timeoutMinutes` returned in `ExtractionResultResponse` from the backend (Task 2)
- Produces: `timeoutMinutes?: number` sent in `RunExtractionRequest` wire format

- [ ] **Step 1: Write the failing hook tests**

Append to `frontend/src/hooks/useExtractionResults.test.ts`:

```typescript
describe('extraction polling timeout', () => {
  it('uses timeoutMinutes from result when set — stops polling after that many minutes', async () => {
    vi.useFakeTimers()

    const pendingResult = {
      ...fakeExtractionResult,
      timeoutMinutes: 20,
    }
    const completedResult = { ...pendingResult, status: 'completed' as const }

    // First call returns pending, subsequent calls return pending until timeout
    mockExtraction.listExtractionResults
      .mockResolvedValueOnce([pendingResult])
      .mockResolvedValue([pendingResult])

    const { result } = renderHook(() => useExtractionResults('doc-1'))
    await act(async () => { await vi.runAllTimersAsync() })

    // Advance time past 20-minute deadline
    await act(async () => {
      vi.advanceTimersByTime(20 * 60 * 1000 + 1)
      await vi.runAllTimersAsync()
    })

    expect(result.current.results[0]?.status).toBe('failed')
    expect(result.current.results[0]?.statusMessage).toBe('Processing timeout')

    vi.useRealTimers()
  })

  it('falls back to 10-minute deadline when timeoutMinutes is null', async () => {
    vi.useFakeTimers()

    const pendingResult = {
      ...fakeExtractionResult,
      timeoutMinutes: null,
    }

    mockExtraction.listExtractionResults
      .mockResolvedValueOnce([pendingResult])
      .mockResolvedValue([pendingResult])

    const { result } = renderHook(() => useExtractionResults('doc-1'))
    await act(async () => { await vi.runAllTimersAsync() })

    // Still pending before 10-minute mark
    await act(async () => {
      vi.advanceTimersByTime(9 * 60 * 1000)
      await vi.runAllTimersAsync()
    })
    expect(result.current.results[0]?.status).toBe('pending')

    // Timed out after 10 minutes
    await act(async () => {
      vi.advanceTimersByTime(2 * 60 * 1000)
      await vi.runAllTimersAsync()
    })
    expect(result.current.results[0]?.status).toBe('failed')

    vi.useRealTimers()
  })
})
```

Also update the `fakeExtractionResult` fixture in the test file to include `timeoutMinutes: null`:

```typescript
const fakeExtractionResult = {
  id: 'result-1',
  documentId: 'doc-1',
  extractionSchemaId: 'schema-1',
  schemaDefinitionSnapshot: {},
  extractionMethod: 'llm',
  config: null,
  structuredData: null,
  extractionMetadata: null,
  citations: null,
  providerResponseRaw: null,
  sourceParseRunId: 'run-1',
  status: 'pending' as const,
  statusMessage: null,
  startedAt: null,
  createdBy: 'user-1',
  createdAt: '2026-06-23T00:00:00Z',
  updatedAt: '2026-06-23T00:00:00Z',
  timeoutMinutes: null,
}
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npx vitest run src/hooks/useExtractionResults.test.ts
```

Expected: new tests `FAIL` (field not on type yet).

- [ ] **Step 3: Update TypeScript types**

In `frontend/src/types/extraction.ts`:

1. Add `timeoutMinutes: number | null` to `ExtractionResult`:

```typescript
export interface ExtractionResult {
  id: string
  documentId: string
  extractionSchemaId: string
  schemaDefinitionSnapshot: Record<string, unknown>
  extractionMethod: string
  config: Record<string, unknown> | null
  structuredData: Record<string, unknown> | null
  extractionMetadata: Record<string, unknown> | null
  citations: Record<string, unknown>[] | null
  providerResponseRaw: Record<string, unknown> | null
  sourceParseRunId: string | null
  status: ExtractionResultStatus
  statusMessage: string | null
  startedAt: string | null
  timeoutMinutes: number | null
  createdBy: string
  createdAt: string
  updatedAt: string
}
```

2. Add `timeoutMinutes?: number` to `RunExtractionRequest`:

```typescript
export interface RunExtractionRequest {
  parseRunId: string
  extractionSchemaId: string
  extractionMethod: string
  config?: Record<string, unknown>
  llmConfig?: PromptConfig
  userPromptTemplate?: string
  chunking?: ChunkingConfig
  preprocess?: PreprocessStage[]
  timeoutMinutes?: number
}
```

3. Add `timeoutMinutes?: number` to `RunWithParseRequest.extractionConfig`:

```typescript
export interface RunWithParseRequest {
  parseConfig: {
    parser: string
    config: Record<string, unknown>
    representationKind: string
  }
  extractionConfig: {
    extractionSchemaId: string
    extractionMethod: string
    config?: Record<string, unknown>
    llmConfig?: PromptConfig
    userPromptTemplate?: string
    chunking?: ChunkingConfig
    preprocess?: PreprocessStage[]
    timeoutMinutes?: number
  }
}
```

- [ ] **Step 4: Update the polling hook**

In `frontend/src/hooks/useExtractionResults.ts`:

1. Remove `EXTRACTION_POLLING_TIMEOUT` and `PARSE_TIMEOUT` constants (lines 14–15). Keep `POLLING_INTERVAL`.

2. Add a timeout ref after `pollingStartRef`:
```typescript
const timeoutMsRef = useRef<number>(10 * 60 * 1_000)
```

3. In `fetchResults`, replace the `EXTRACTION_POLLING_TIMEOUT` check with `timeoutMsRef.current`:

```typescript
if (
  pollingStartRef.current &&
  Date.now() - pollingStartRef.current > timeoutMsRef.current
) {
```

4. In `runExtractionWithParse`, replace the `PARSE_TIMEOUT` references with a local constant and set `timeoutMsRef` before calling `fetchResults()`:

```typescript
const PARSE_TIMEOUT_MS = 10 * 60 * 1_000

// ... (existing parse phase logic — replace all PARSE_TIMEOUT refs with PARSE_TIMEOUT_MS)

// Just before the final fetchResults() call:
timeoutMsRef.current = (extractionConfig.timeoutMinutes ?? 10) * 60 * 1_000

setExtractionPhase('extracting')
try {
  await extractionApi.runExtraction({
    parseRunId: parseRunId!,
    extractionSchemaId: extractionConfig.extractionSchemaId,
    extractionMethod: extractionConfig.extractionMethod,
    config: extractionConfig.config,
    llmConfig: extractionConfig.llmConfig,
    userPromptTemplate: extractionConfig.userPromptTemplate,
    chunking: extractionConfig.chunking,
    preprocess: extractionConfig.preprocess,
    timeoutMinutes: extractionConfig.timeoutMinutes,
  })
  await fetchResults()
  setExtractionPhase('done')
```

- [ ] **Step 5: Add the form field**

In `frontend/src/components/extraction/ExtractionForm.tsx`:

1. Add state after `maxTokensPerMinute` (line 70):
```typescript
const [timeoutMinutes, setTimeoutMinutes] = useState('')
```

2. In `handleRun`, inside the `extractionMethod === 'llm'` branch, add `timeoutMinutes` to `extractionConfig`:

```typescript
const tm = parseInt(timeoutMinutes, 10)
extractionConfig = {
  extractionSchemaId: schemaId,
  extractionMethod,
  config: { structured_output_mode: structuredOutputMode, inject_block_ids: injectBlockIds },
  llmConfig: promptConfig,
  userPromptTemplate: userPromptTemplate.trim() || undefined,
  ...(chunking ? { chunking } : {}),
  ...(!Number.isNaN(tm) && tm >= 1 ? { timeoutMinutes: Math.min(tm, 120) } : {}),
}
```

3. In the JSX, add the timeout input inside the `CollapsibleContent` "Large document handling" section, after the rate limit TPM input (after line 398):

```tsx
<div className="space-y-1.5">
  <Label className="text-xs">Timeout (minutes)</Label>
  <Input
    type="number"
    value={timeoutMinutes}
    onChange={(e) => setTimeoutMinutes(e.target.value)}
    placeholder="10"
    min={1}
    max={120}
    className="h-9"
  />
</div>
```

- [ ] **Step 6: Run the hook tests**

```bash
npx vitest run src/hooks/useExtractionResults.test.ts
```

Expected: all PASS (including the two new tests).

- [ ] **Step 7: Run TypeScript build to catch type errors**

```bash
npm run --prefix frontend build
```

Expected: build succeeds with no type errors.

- [ ] **Step 8: Run the full frontend test suite**

```bash
npx vitest run --reporter=verbose
```

Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/types/extraction.ts frontend/src/components/extraction/ExtractionForm.tsx frontend/src/hooks/useExtractionResults.ts frontend/src/hooks/useExtractionResults.test.ts
git commit -m "feat(extraction): add configurable timeout to extraction form and polling hook"
```
