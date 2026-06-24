# Delete Extraction Runs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the ability for users to delete previous extraction runs from the Extraction page.

**Architecture:** Three backend layers (repository → service → router) add a `DELETE /extraction-results/{id}` endpoint following the existing schema-delete pattern exactly. Three frontend layers (api → hook → component) wire the delete action into `ExtractionHistory`, which requires a small structural change to each row (splitting the `<Button>` CollapsibleTrigger into a trigger + a sibling delete icon button). Pending runs never show a delete button.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 (backend); React 18 / TypeScript / shadcn/ui (frontend); pytest + AsyncMock (backend tests); Vitest + @testing-library/react (frontend tests).

## Global Constraints

- All new backend code is async with full type hints
- Services raise exceptions; routers catch and return HTTP responses
- No database migration — this is a plain DELETE with no schema changes
- Follow existing patterns exactly: `delete_extraction_schema` (router), `ExtractionResultRepository` (repo style), `useExtractionResults` (hook style)
- Pending extraction results must NOT be deletable (block at the UI layer only — no backend guard needed since the UI never sends the request)

---

### Task 1: Repository — `delete` method

**Files:**
- Modify: `backend/app/repositories/extraction_result_repository.py`
- Test: `backend/tests/repositories/test_extraction_result_repository.py`

**Interfaces:**
- Produces: `async def delete(self, result_id: UUID) -> bool` — returns `True` if a row was deleted, `False` if not found

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/repositories/test_extraction_result_repository.py`:

```python
class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_returns_true_when_found(self):
        mock_result = _make_mock_result()
        session = AsyncMock()
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=mock_result)

        result = await repo.delete(mock_result.id)

        assert result is True
        session.delete.assert_called_once_with(mock_result)
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self):
        session = AsyncMock()
        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=None)

        result = await repo.delete(uuid4())

        assert result is False
        session.delete.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && uv run python -m pytest tests/repositories/test_extraction_result_repository.py::TestDelete -v -o "addopts="
```

Expected: FAIL with `AttributeError: 'ExtractionResultRepository' object has no attribute 'delete'`

- [ ] **Step 3: Implement `delete` in the repository**

Add to the bottom of the `ExtractionResultRepository` class in `backend/app/repositories/extraction_result_repository.py`:

```python
async def delete(self, result_id: UUID) -> bool:
    """Delete an extraction result. Returns True if deleted, False if not found."""
    extraction_result = await self.get_by_id(result_id)
    if not extraction_result:
        return False
    await self.session.delete(extraction_result)
    await self.session.commit()
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd backend && uv run python -m pytest tests/repositories/test_extraction_result_repository.py::TestDelete -v -o "addopts="
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/extraction_result_repository.py backend/tests/repositories/test_extraction_result_repository.py
git commit -m "feat(extraction): add delete method to ExtractionResultRepository"
```

---

### Task 2: Service — `delete_result` method

**Files:**
- Modify: `backend/app/services/extraction_service.py`
- Test: `backend/tests/services/test_extraction_service.py`

**Interfaces:**
- Consumes: `ExtractionResultRepository.delete(result_id: UUID) -> bool` from Task 1
- Produces: `async def delete_result(self, result_id: UUID, user_id: UUID) -> None` — raises `NotFoundError` if result does not exist

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/test_extraction_service.py`:

```python
class TestDeleteResult:
    @pytest.mark.asyncio
    async def test_delete_result_calls_repo_and_returns(self):
        result_repo = AsyncMock()
        result_repo.delete = AsyncMock(return_value=True)
        service = _make_service(result_repo=result_repo)
        result_id = uuid4()

        await service.delete_result(result_id, uuid4())

        result_repo.delete.assert_called_once_with(result_id)

    @pytest.mark.asyncio
    async def test_delete_result_raises_not_found_when_missing(self):
        from app.services.exceptions import NotFoundError
        result_repo = AsyncMock()
        result_repo.delete = AsyncMock(return_value=False)
        service = _make_service(result_repo=result_repo)

        with pytest.raises(NotFoundError):
            await service.delete_result(uuid4(), uuid4())
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && uv run python -m pytest tests/services/test_extraction_service.py::TestDeleteResult -v -o "addopts="
```

Expected: FAIL with `AttributeError: 'ExtractionService' object has no attribute 'delete_result'`

- [ ] **Step 3: Implement `delete_result` in the service**

Add after the `list_extraction_results` method in the `# --- Results ---` section of `backend/app/services/extraction_service.py`:

```python
async def delete_result(self, result_id: UUID, user_id: UUID) -> None:
    """Delete an extraction result. Raises NotFoundError if not found."""
    deleted = await self.result_repo.delete(result_id)
    if not deleted:
        raise NotFoundError(f"Extraction result {result_id} not found")
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd backend && uv run python -m pytest tests/services/test_extraction_service.py::TestDeleteResult -v -o "addopts="
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction_service.py backend/tests/services/test_extraction_service.py
git commit -m "feat(extraction): add delete_result method to ExtractionService"
```

---

### Task 3: Router — `DELETE /extraction-results/{result_id}`

**Files:**
- Modify: `backend/app/routers/extraction.py`
- Test: `backend/tests/routers/test_extraction_router.py`

**Interfaces:**
- Consumes: `ExtractionService.delete_result(result_id: UUID, user_id: UUID) -> None` from Task 2
- Produces: `DELETE /extraction-results/{result_id}` → 204 on success, 404 if not found

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/routers/test_extraction_router.py`:

```python
@pytest.mark.asyncio
async def test_delete_extraction_result_returns_204(client: AsyncClient):
    """DELETE /extraction-results/{id} returns 204 when the result exists."""
    from app.services.extraction_service import ExtractionService
    from app.services.exceptions import NotFoundError

    result_id = uuid4()
    app.dependency_overrides[get_current_active_user] = _mock_user

    try:
        with patch.object(ExtractionService, "delete_result", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = None
            response = await client.delete(
                f"/api/v1/extraction-results/{result_id}",
            )
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_delete_extraction_result_returns_404_when_not_found(client: AsyncClient):
    """DELETE /extraction-results/{id} returns 404 when the result does not exist."""
    from app.services.extraction_service import ExtractionService
    from app.services.exceptions import NotFoundError

    result_id = uuid4()
    app.dependency_overrides[get_current_active_user] = _mock_user

    try:
        with patch.object(ExtractionService, "delete_result", new_callable=AsyncMock) as mock_delete:
            mock_delete.side_effect = NotFoundError("not found")
            response = await client.delete(
                f"/api/v1/extraction-results/{result_id}",
            )
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == status.HTTP_404_NOT_FOUND
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && uv run python -m pytest tests/routers/test_extraction_router.py::test_delete_extraction_result_returns_204 tests/routers/test_extraction_router.py::test_delete_extraction_result_returns_404_when_not_found -v -o "addopts="
```

Expected: FAIL with 405 Method Not Allowed (route doesn't exist yet)

- [ ] **Step 3: Add the DELETE endpoint to the router**

Add after the `get_extraction_result` endpoint in the `# --- Result endpoints ---` section of `backend/app/routers/extraction.py`:

```python
@router.delete(
    "/extraction-results/{result_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an extraction result",
)
async def delete_extraction_result(
    result_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionService = Depends(get_extraction_service),
):
    try:
        await service.delete_result(result_id, current_user.id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd backend && uv run python -m pytest tests/routers/test_extraction_router.py::test_delete_extraction_result_returns_204 tests/routers/test_extraction_router.py::test_delete_extraction_result_returns_404_when_not_found -v -o "addopts="
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/extraction.py backend/tests/routers/test_extraction_router.py
git commit -m "feat(extraction): add DELETE /extraction-results/{result_id} endpoint"
```

---

### Task 4: Frontend API + hook

**Files:**
- Modify: `frontend/src/api/extraction.ts`
- Modify: `frontend/src/hooks/useExtractionResults.ts`
- Test: `frontend/src/hooks/useExtractionResults.test.ts`

**Interfaces:**
- Produces: `deleteExtractionResult(resultId: string): Promise<void>` in api layer
- Produces: `deleteResult: (resultId: string) => Promise<void>` on `UseExtractionResultsReturn`

Note: `toast` from `sonner` must be imported in `useExtractionResults.ts`.

- [ ] **Step 1: Write the failing hook test**

Append to `frontend/src/hooks/useExtractionResults.test.ts`:

```typescript
describe('deleteResult', () => {
  it('removes the deleted item from results state', async () => {
    const listItem = {
      id: 'result-1',
      documentId: 'doc-1',
      extractionSchemaId: 'schema-1',
      extractionMethod: 'llm',
      status: 'completed' as const,
      statusMessage: null,
      createdAt: '2026-06-24T00:00:00Z',
    }
    mockExtraction.listExtractionResults.mockResolvedValue([listItem])
    mockExtraction.deleteExtractionResult = vi.fn().mockResolvedValue(undefined)

    const { result } = renderHook(() => useExtractionResults('doc-1'))
    await act(async () => {})

    expect(result.current.results).toHaveLength(1)

    await act(async () => {
      await result.current.deleteResult('result-1')
    })

    expect(result.current.results).toHaveLength(0)
    expect(mockExtraction.deleteExtractionResult).toHaveBeenCalledWith('result-1')
  })

  it('clears selectedResult when the deleted item was selected', async () => {
    const listItem = {
      id: 'result-1',
      documentId: 'doc-1',
      extractionSchemaId: 'schema-1',
      extractionMethod: 'llm',
      status: 'completed' as const,
      statusMessage: null,
      createdAt: '2026-06-24T00:00:00Z',
    }
    const fullResult = { ...fakeExtractionResult, id: 'result-1', status: 'completed' as const }
    mockExtraction.listExtractionResults.mockResolvedValue([listItem])
    mockExtraction.getExtractionResult.mockResolvedValue(fullResult)
    mockExtraction.deleteExtractionResult = vi.fn().mockResolvedValue(undefined)

    const { result } = renderHook(() => useExtractionResults('doc-1'))
    await act(async () => {})

    await act(async () => { await result.current.selectResult('result-1') })
    expect(result.current.selectedResult?.id).toBe('result-1')

    await act(async () => { await result.current.deleteResult('result-1') })
    expect(result.current.selectedResult).toBeNull()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```
cd frontend && npx vitest run src/hooks/useExtractionResults.test.ts 2>&1 | tail -20
```

Expected: FAIL — `result.current.deleteResult is not a function`

- [ ] **Step 3: Add `deleteExtractionResult` to the API module**

Add to the bottom of `frontend/src/api/extraction.ts`:

```typescript
export async function deleteExtractionResult(resultId: string): Promise<void> {
  await apiClient.delete(`/extraction-results/${resultId}`)
}
```

- [ ] **Step 4: Add `deleteResult` to the hook**

In `frontend/src/hooks/useExtractionResults.ts`:

1. Add `toast` import at the top:
```typescript
import { toast } from 'sonner'
```

2. Add `deleteResult` to the `UseExtractionResultsReturn` interface:
```typescript
deleteResult: (resultId: string) => Promise<void>
```

3. Add the implementation inside `useExtractionResults`, after `selectResult`:
```typescript
const deleteResult = useCallback(async (resultId: string) => {
  try {
    await extractionApi.deleteExtractionResult(resultId)
    setResults((prev) => prev.filter((r) => r.id !== resultId))
    setSelectedResult((prev) => (prev?.id === resultId ? null : prev))
    toast.success('Extraction deleted')
  } catch (err) {
    toast.error('Failed to delete extraction run', {
      description: err instanceof Error ? err.message : 'An error occurred',
    })
  }
}, [])
```

4. Add `deleteResult` to the return object:
```typescript
return {
  results,
  selectedResult,
  isLoading,
  isLoadingResult,
  error,
  extractionPhase,
  phaseError,
  fetchResults,
  selectResult,
  deleteResult,
  runExtractionWithParse,
}
```

- [ ] **Step 5: Run tests to verify they pass**

```
cd frontend && npx vitest run src/hooks/useExtractionResults.test.ts 2>&1 | tail -20
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/extraction.ts frontend/src/hooks/useExtractionResults.ts frontend/src/hooks/useExtractionResults.test.ts
git commit -m "feat(extraction): add deleteExtractionResult API and deleteResult hook"
```

---

### Task 5: Frontend component + page wiring

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionHistory.tsx`
- Modify: `frontend/src/pages/ExtractionPage.tsx`

**Interfaces:**
- Consumes: `deleteResult: (resultId: string) => Promise<void>` from Task 4's hook

- [ ] **Step 1: Update `ExtractionHistoryProps` and add `onDeleteResult`**

In `frontend/src/components/extraction/ExtractionHistory.tsx`, update the props interface:

```typescript
interface ExtractionHistoryProps {
  results: ExtractionResultListItem[]
  isLoading: boolean
  selectedResult: ExtractionResult | null
  isLoadingResult?: boolean
  schemas?: ExtractionSchema[]
  onSelectResult: (resultId: string) => void
  onDeleteResult: (resultId: string) => Promise<void>
  inProgressPhase?: InProgressPhase
}
```

- [ ] **Step 2: Add `Trash2` to the lucide import and destructure `onDeleteResult`**

Change the lucide import line:
```typescript
import { AlertCircle, ChevronRight, Loader2, RefreshCw, Trash2 } from 'lucide-react'
```

Destructure the new prop in the component signature:
```typescript
export function ExtractionHistory({
  results,
  isLoading,
  selectedResult,
  schemas,
  onSelectResult,
  onDeleteResult,
  inProgressPhase,
}: ExtractionHistoryProps) {
```

- [ ] **Step 3: Restructure each result row**

The current `results.map` block renders a `<Collapsible>` whose trigger is a full-width `<Button>`. Replace it so the trigger and delete button are siblings in a flex wrapper. Replace the entire `{results.map((r) => { ... })}` block with:

```typescript
{results.map((r) => {
  const isExpanded = selectedResult?.id === r.id
  const isPending = r.status === 'pending'
  const schemaName = schemas?.find((s) => s.id === r.extractionSchemaId)?.name

  return (
    <Collapsible
      key={r.id}
      open={isExpanded}
      onOpenChange={(open) => { if (open) onSelectResult(r.id) }}
    >
      <div className="flex items-center rounded-md hover:bg-muted/50 group">
        <CollapsibleTrigger asChild>
          <button className="flex-1 text-left py-2.5 pl-3 pr-2 min-w-0">
            <div className="flex items-center gap-2 min-w-0">
              <ChevronRight className={`h-4 w-4 shrink-0 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
              <div className="flex flex-col items-start gap-0.5 min-w-0">
                <div className="flex items-center gap-1.5">
                  {schemaName && (
                    <span className="text-xs font-medium truncate">{schemaName}</span>
                  )}
                  <Badge variant="outline" className="text-[10px] font-normal shrink-0">{r.extractionMethod}</Badge>
                  <Badge
                    variant={r.status === 'completed' ? 'default' : r.status === 'pending' ? 'secondary' : 'destructive'}
                    className="text-[10px] shrink-0"
                  >
                    {isPending && <Loader2 className="h-2.5 w-2.5 mr-1 animate-spin" />}
                    {r.status}
                  </Badge>
                </div>
                <span className="text-[11px] text-muted-foreground">{formatDate(r.createdAt)}</span>
              </div>
            </div>
          </button>
        </CollapsibleTrigger>

        {!isPending && (
          <button
            className="shrink-0 px-2 py-2 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
            aria-label="Delete extraction run"
            onClick={(e) => { e.stopPropagation(); onDeleteResult(r.id) }}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      <CollapsibleContent>
        <div className="ml-6 mr-3 mb-2 mt-1">
          {selectedResult?.id === r.id ? (
            <ExtractionResultViewer result={selectedResult} isLoading={false} />
          ) : isExpanded ? (
            <div className="space-y-2 p-3">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          ) : null}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
})}
```

- [ ] **Step 4: Wire `onDeleteResult` in `ExtractionPage`**

In `frontend/src/pages/ExtractionPage.tsx`:

1. Destructure `deleteResult` from the hook call:
```typescript
const {
  results,
  selectedResult,
  isLoading: resultsLoading,
  isLoadingResult,
  error: resultsError,
  extractionPhase,
  phaseError,
  selectResult,
  deleteResult,
  runExtractionWithParse,
} = useExtractionResults(selectedDocumentId)
```

2. Pass it to `ExtractionHistory`:
```typescript
<ExtractionHistory
  results={results}
  isLoading={resultsLoading}
  selectedResult={selectedResult}
  isLoadingResult={isLoadingResult}
  schemas={schemas}
  onSelectResult={selectResult}
  onDeleteResult={deleteResult}
  inProgressPhase={inProgressPhase}
/>
```

- [ ] **Step 5: Type-check and lint**

```
cd frontend && npm run build 2>&1 | tail -20
```

Expected: no TypeScript errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/extraction/ExtractionHistory.tsx frontend/src/pages/ExtractionPage.tsx
git commit -m "feat(extraction): add delete button to extraction history rows"
```

---

## Self-Review

**Spec coverage:**
- ✅ Backend `delete` method on repository (Task 1)
- ✅ Backend `delete_result` on service (Task 2)
- ✅ `DELETE /extraction-results/{result_id}` endpoint, 204/404 (Task 3)
- ✅ `deleteExtractionResult` API function (Task 4)
- ✅ `deleteResult` hook function with state update and toast (Task 4)
- ✅ Delete button hidden for pending runs (Task 5, `!isPending` guard)
- ✅ Row restructured to avoid nested `<button>` (Task 5)
- ✅ `selectedResult` cleared on delete of selected item (Task 4)
- ✅ No confirmation dialog — immediate delete with toast (Task 4/5)

**Placeholder scan:** No TBDs, TODOs, or vague steps found.

**Type consistency:**
- `deleteResult(resultId: string): Promise<void>` — defined in Task 4 interface, implemented in Task 4, consumed in Task 5 ✅
- `deleteExtractionResult(resultId: string): Promise<void>` — defined in Task 4 step 3, called in Task 4 step 4 ✅
- `onDeleteResult: (resultId: string) => Promise<void>` — added to props interface in Task 5 step 1, passed from page in Task 5 step 4 ✅
