# Extraction LLM Prompt Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the hardcoded LLM extraction prompts via a backend endpoint and pre-fill both the system prompt and user prompt template fields in ExtractionForm so users can see, edit, and compare prompt variations per run.

**Architecture:** A new `GET /extractors/llm/defaults` endpoint returns the two hardcoded constants from `llm.py`. `ExtractionForm` fetches these when the LLM method is active and pre-fills the fields if they are currently empty — the user can then edit freely before running.

**Tech Stack:** Python 3.12 / FastAPI / Pydantic v2 (backend); React 18 / TypeScript / Vitest / happy-dom (frontend)

## Global Constraints

- No database migration — this is a read-only endpoint returning static strings.
- Auth: endpoint requires `get_current_active_user` dependency (same as all other extractor endpoints).
- Frontend test environment: `happy-dom`. Do not use `waitFor` from `@testing-library/react` — it times out in happy-dom. Use `await act(async () => {})` to flush promises instead.
- Backend tests: use the `client` fixture from `conftest.py` (in-memory SQLite, auth overridden with `_mock_user()`).
- No changes to `PromptConfigEditor`, `ExtractionHistory`, `ExtractionPage`, or any type definitions beyond what is listed.

---

### Task 1: Backend — `GET /extractors/llm/defaults` endpoint

**Files:**
- Modify: `backend/app/schemas/extraction_result.py` — add `LlmDefaultsResponse`
- Modify: `backend/app/routers/extraction.py` — add endpoint
- Modify: `backend/tests/routers/test_extraction_router.py` — add test

**Interfaces:**
- Produces: `GET /api/v1/extractors/llm/defaults` → `{ "systemPrompt": "...", "userPromptTemplate": "..." }`

- [ ] **Step 1: Write the failing test**

Add to the bottom of `backend/tests/routers/test_extraction_router.py`:

```python
@pytest.mark.asyncio
async def test_get_llm_extraction_defaults(client: AsyncClient):
    """GET /extractors/llm/defaults returns the two hardcoded prompt constants."""
    from app.adapters.extraction.llm import (
        DEFAULT_EXTRACTION_SYSTEM_PROMPT,
        DEFAULT_USER_PROMPT_TEMPLATE,
    )
    from app.dependencies.auth import get_current_active_user

    app.dependency_overrides[get_current_active_user] = lambda: _mock_user()
    try:
        response = await client.get("/api/v1/extractors/llm/defaults")
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == 200
    data = response.json()
    assert data["systemPrompt"] == DEFAULT_EXTRACTION_SYSTEM_PROMPT
    assert data["userPromptTemplate"] == DEFAULT_USER_PROMPT_TEMPLATE
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run --directory backend python -m pytest tests/routers/test_extraction_router.py::test_get_llm_extraction_defaults -v
```

Expected: FAIL with 404 (route not yet registered).

- [ ] **Step 3: Add `LlmDefaultsResponse` to Pydantic schemas**

In `backend/app/schemas/extraction_result.py`, after the `ExtractionSchemaResponse` class, add:

```python
class LlmDefaultsResponse(BaseModel):
    """Default prompts for LLM extraction."""
    system_prompt: str = Field(..., alias="systemPrompt")
    user_prompt_template: str = Field(..., alias="userPromptTemplate")

    model_config = ConfigDict(populate_by_name=True)
```

Also add `LlmDefaultsResponse` to the existing imports block at the top of `backend/app/routers/extraction.py`:

```python
from app.schemas.extraction_result import (
    ExtractionSchemaCreate,
    ExtractionSchemaUpdate,
    ExtractionSchemaResponse,
    RunExtractionRequest,
    ExtractionResultResponse,
    ExtractionResultListResponse,
    ExtractorInfoResponse,
    LlmDefaultsResponse,          # ← add this
)
```

- [ ] **Step 4: Add the endpoint to the router**

In `backend/app/routers/extraction.py`, at the end of the `# --- Extractor info ---` section (after `list_extractors`), add:

```python
@router.get(
    "/extractors/llm/defaults",
    response_model=LlmDefaultsResponse,
    summary="Get default LLM extraction prompts",
)
async def get_llm_extraction_defaults(
    current_user: User = Depends(get_current_active_user),
):
    from app.adapters.extraction.llm import (
        DEFAULT_EXTRACTION_SYSTEM_PROMPT,
        DEFAULT_USER_PROMPT_TEMPLATE,
    )
    return LlmDefaultsResponse(
        systemPrompt=DEFAULT_EXTRACTION_SYSTEM_PROMPT,
        userPromptTemplate=DEFAULT_USER_PROMPT_TEMPLATE,
    )
```

- [ ] **Step 5: Run the test to verify it passes**

```
uv run --directory backend python -m pytest tests/routers/test_extraction_router.py::test_get_llm_extraction_defaults -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```
git add backend/app/schemas/extraction_result.py backend/app/routers/extraction.py backend/tests/routers/test_extraction_router.py
git commit -m "feat(extraction): add GET /extractors/llm/defaults endpoint"
```

---

### Task 2: Frontend — pre-fill ExtractionForm with fetched defaults

**Files:**
- Modify: `frontend/src/api/extraction.ts` — add `getLlmDefaults()`
- Modify: `frontend/src/components/extraction/ExtractionForm.tsx` — fetch and pre-fill on LLM method
- Modify: `frontend/src/components/extraction/ExtractionForm.test.tsx` — add test + mock

**Interfaces:**
- Consumes: `GET /api/v1/extractors/llm/defaults` from Task 1
- Produces: no new exports; internal behaviour change to `ExtractionForm`

- [ ] **Step 1: Write the failing test**

In `frontend/src/components/extraction/ExtractionForm.test.tsx`, add the following at the top of the file (after existing imports):

```tsx
import { act } from '@testing-library/react'
import * as extractionApi from '@/api/extraction'
```

Add a `vi.mock` block immediately after the imports (before the `const schema = ...` declarations):

```tsx
vi.mock('@/api/extraction', () => ({
  getLlmDefaults: vi.fn().mockResolvedValue({
    systemPrompt: 'Default system prompt text',
    userPromptTemplate: 'Default user prompt template text',
  }),
}))
```

Add the new test case inside the existing `describe('ExtractionForm', () => { ... })` block:

```tsx
it('pre-fills system prompt and user prompt template with fetched LLM defaults', async () => {
  const llmExtractor: ExtractorInfo = {
    extractionMethod: 'llm',
    name: 'LLM',
    description: 'Generic LLM extraction',
    configSchema: null,
    configured: true,
  }
  render(<ExtractionForm {...defaultProps} extractors={[llmExtractor]} onRun={vi.fn()} />)

  await act(async () => {})

  expect(screen.getByDisplayValue('Default system prompt text')).toBeInTheDocument()
  expect(screen.getByDisplayValue('Default user prompt template text')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

```
npx --prefix frontend vitest run src/components/extraction/ExtractionForm.test.tsx
```

Expected: FAIL — `getByDisplayValue` finds nothing (fields are empty).

- [ ] **Step 3: Add `getLlmDefaults` to the API module**

In `frontend/src/api/extraction.ts`, add after the `listExtractors` function:

```ts
export async function getLlmDefaults(): Promise<{ systemPrompt: string; userPromptTemplate: string }> {
  const response = await apiClient.get<{ systemPrompt: string; userPromptTemplate: string }>(
    '/extractors/llm/defaults'
  )
  return response.data
}
```

- [ ] **Step 4: Update `ExtractionForm` to fetch and pre-fill defaults**

In `frontend/src/components/extraction/ExtractionForm.tsx`:

Add `getLlmDefaults` to the imports at the top of the file:

```tsx
import { getLlmDefaults } from '@/api/extraction'
```

Add a `useEffect` that fires when `extractionMethod` becomes `'llm'` and pre-fills both fields if they are currently unset. Insert it after the existing `useEffect` blocks (around line 79, after the extractor initialisation effect):

```tsx
useEffect(() => {
  if (extractionMethod !== 'llm') return
  let cancelled = false
  getLlmDefaults()
    .then((defaults) => {
      if (cancelled) return
      setPromptConfig((prev) => ({
        ...prev,
        systemPrompt: prev.systemPrompt || defaults.systemPrompt,
      }))
      setUserPromptTemplate((prev) => prev || defaults.userPromptTemplate)
    })
    .catch(() => {})
  return () => {
    cancelled = true
  }
}, [extractionMethod])
```

- [ ] **Step 5: Run all ExtractionForm tests to verify they pass**

```
npx --prefix frontend vitest run src/components/extraction/ExtractionForm.test.tsx
```

Expected: all tests PASS, including the new pre-fill test.

- [ ] **Step 6: Run the full frontend test suite to check for regressions**

```
npx --prefix frontend vitest run
```

Expected: same pass/fail distribution as before this task (pre-existing failures in unrelated files are acceptable — do not investigate them here).

- [ ] **Step 7: Commit**

```
git add frontend/src/api/extraction.ts frontend/src/components/extraction/ExtractionForm.tsx frontend/src/components/extraction/ExtractionForm.test.tsx
git commit -m "feat(extraction): pre-fill LLM prompts from backend defaults in ExtractionForm"
```
