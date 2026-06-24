# Extraction UI Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two UX issues on the Extraction page — make LLM the default extraction method, and allow expanded extraction result rows to be collapsed.

**Architecture:** Task 1 is a single-line backend registry reorder (no migration, no tests). Task 2 adds `clearSelection` to the extraction hook and threads it through the component and page as `onDeselectResult`, fixing the `onOpenChange` handler that currently ignores collapse events.

**Tech Stack:** Python 3.12 (backend registry); React 18 / TypeScript / shadcn/ui Collapsible (frontend); Vitest + @testing-library/react (frontend tests).

## Global Constraints

- Frontend-only changes for Task 2; backend-only for Task 1
- No database migrations
- Follow existing hook/component/page patterns

---

### Task 1: Reorder extractor registry — LLM first

**Files:**
- Modify: `backend/app/adapters/extraction/registry.py`

**Interfaces:**
- Produces: `get_known_extractors()` returns `llm` entry before `llamaextract` entry

The `ExtractionForm` frontend picks the first configured extractor as the default. `llm` is always configured; `llamaextract` requires a key. Putting `llm` first makes it the default and first in the dropdown.

No test is needed: there is no existing test for ordering, and the change is a pure list reorder with no logic.

- [ ] **Step 1: Reorder the registry list**

In `backend/app/adapters/extraction/registry.py`, swap the two dict entries inside `get_known_extractors()` so the result is:

```python
def get_known_extractors() -> list[dict]:
    """Catalogue of all known extraction adapters."""
    return [
        {
            "extraction_method": "llm",
            "name": "LLM",
            "description": (
                "Structured extraction via any LLM provider "
                "(Ollama, OpenAI, Anthropic, Groq, …)"
            ),
            "config_schema": {
                "type": "object",
                "properties": {
                    "structured_output_mode": {
                        "type": "string",
                        "enum": ["json_schema", "json_mode", "prompt_only"],
                        "default": "json_schema",
                    },
                    "inject_block_ids": {"type": "boolean", "default": False},
                    "user_prompt_template": {"type": "string"},
                },
            },
        },
        {
            "extraction_method": "llamaextract",
            "name": "LlamaExtract",
            "description": (
                "Structured extraction via LlamaCloud. "
                "Multimodal, supports citations and reasoning."
            ),
            "config_schema": {
                "type": "object",
                "properties": {
                    "system_prompt": {
                        "type": "string",
                        "description": "Custom extraction prompt (maps to LlamaExtract prompt_override)",
                    },
                    "extraction_mode": {
                        "type": "string",
                        "enum": ["FAST", "BALANCED", "MULTIMODAL", "PREMIUM"],
                        "default": "MULTIMODAL",
                    },
                    "extraction_target": {
                        "type": "string",
                        "enum": ["PER_DOC", "PER_PAGE"],
                        "default": "PER_DOC",
                    },
                    "cite_sources": {"type": "boolean", "default": False},
                    "use_reasoning": {"type": "boolean", "default": False},
                    "confidence_scores": {"type": "boolean", "default": False},
                    "page_range": {"type": "string"},
                },
            },
        },
    ]
```

- [ ] **Step 2: Verify existing extraction tests still pass**

```
uv run --directory backend python -m pytest tests/services/test_extraction_service.py tests/routers/test_extraction_router.py -v -o "addopts="
```

Expected: all existing tests pass (the reorder touches no logic paths covered by tests).

- [ ] **Step 3: Commit**

```bash
git add backend/app/adapters/extraction/registry.py
git commit -m "feat(extraction): make LLM the default extractor by listing it first in registry"
```

---

### Task 2: Collapsible extraction result rows

**Files:**
- Modify: `frontend/src/hooks/useExtractionResults.ts`
- Modify: `frontend/src/components/extraction/ExtractionHistory.tsx`
- Modify: `frontend/src/pages/ExtractionPage.tsx`
- Test: `frontend/src/hooks/useExtractionResults.test.ts`

**Interfaces:**
- Produces: `clearSelection: () => void` on `UseExtractionResultsReturn`
- Produces: `onDeselectResult: () => void` prop on `ExtractionHistoryProps`

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/hooks/useExtractionResults.test.ts`, inside or after the existing `describe` blocks:

```typescript
describe('clearSelection', () => {
  it('sets selectedResult to null', async () => {
    const fullResult = { ...fakeExtractionResult, id: 'result-1', status: 'completed' as const }
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
    mockExtraction.getExtractionResult.mockResolvedValue(fullResult)

    const { result } = renderHook(() => useExtractionResults('doc-1'))
    await act(async () => {})

    await act(async () => { await result.current.selectResult('result-1') })
    expect(result.current.selectedResult?.id).toBe('result-1')

    act(() => { result.current.clearSelection() })
    expect(result.current.selectedResult).toBeNull()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```
cd frontend && npx vitest run src/hooks/useExtractionResults.test.ts 2>&1 | Select-Object -Last 10
```

Expected: FAIL — `result.current.clearSelection is not a function`

- [ ] **Step 3: Add `clearSelection` to the hook**

In `frontend/src/hooks/useExtractionResults.ts`:

1. Add `clearSelection` to the `UseExtractionResultsReturn` interface (after `selectResult`):

```typescript
clearSelection: () => void
```

2. Add the implementation inside `useExtractionResults`, after the `selectResult` callback:

```typescript
const clearSelection = useCallback(() => {
  setSelectedResult(null)
}, [])
```

3. Add `clearSelection` to the return object:

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
  clearSelection,
  deleteResult,
  runExtractionWithParse,
}
```

- [ ] **Step 4: Run test to verify it passes**

```
cd frontend && npx vitest run src/hooks/useExtractionResults.test.ts 2>&1 | Select-Object -Last 10
```

Expected: all tests PASS

- [ ] **Step 5: Add `onDeselectResult` prop to `ExtractionHistory` and fix `onOpenChange`**

In `frontend/src/components/extraction/ExtractionHistory.tsx`:

1. Add `onDeselectResult` to `ExtractionHistoryProps`:

```typescript
interface ExtractionHistoryProps {
  results: ExtractionResultListItem[]
  isLoading: boolean
  selectedResult: ExtractionResult | null
  isLoadingResult?: boolean
  schemas?: ExtractionSchema[]
  onSelectResult: (resultId: string) => void
  onDeselectResult: () => void
  onDeleteResult: (resultId: string) => Promise<void>
  inProgressPhase?: InProgressPhase
}
```

2. Destructure it in the function signature:

```typescript
export function ExtractionHistory({
  results,
  isLoading,
  selectedResult,
  schemas,
  onSelectResult,
  onDeselectResult,
  onDeleteResult,
  inProgressPhase,
}: ExtractionHistoryProps) {
```

3. Fix the `onOpenChange` handler on the `<Collapsible>` inside `results.map`:

```tsx
onOpenChange={(open) => {
  if (open) onSelectResult(r.id)
  else onDeselectResult()
}}
```

- [ ] **Step 6: Wire `clearSelection` through `ExtractionPage`**

In `frontend/src/pages/ExtractionPage.tsx`:

1. Destructure `clearSelection` from the hook call:

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
  clearSelection,
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
  onDeselectResult={clearSelection}
  onDeleteResult={deleteResult}
  inProgressPhase={inProgressPhase}
/>
```

- [ ] **Step 7: Type-check**

```
cd frontend && npm run build 2>&1 | Select-Object -Last 10
```

Expected: clean build with no TypeScript errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/hooks/useExtractionResults.ts frontend/src/hooks/useExtractionResults.test.ts frontend/src/components/extraction/ExtractionHistory.tsx frontend/src/pages/ExtractionPage.tsx
git commit -m "feat(extraction): allow expanded result rows to be collapsed"
```

---

## Self-Review

**Spec coverage:**
- ✅ LLM listed first in registry — defaults to LLM when both configured (Task 1)
- ✅ Dropdown order also changes to show LLM first (Task 1, bonus)
- ✅ `clearSelection` added to hook (Task 2)
- ✅ `onDeselectResult` wired through component and page (Task 2)
- ✅ `onOpenChange` now handles both expand and collapse (Task 2)

**Placeholder scan:** None found.

**Type consistency:**
- `clearSelection: () => void` — defined in Task 2 interface, implemented in Task 2 step 3, consumed in Task 2 step 6 ✅
- `onDeselectResult: () => void` — added to props in Task 2 step 5, passed from page in Task 2 step 6 ✅
