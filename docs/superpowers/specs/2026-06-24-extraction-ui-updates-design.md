---
title: Extraction UI Updates (issue #106, items 2 & 3)
date: 2026-06-24
issue: https://github.com/asanyaga/rag-admin/issues/106
---

# Extraction UI Updates

Two small UX fixes for the Extraction page.

---

## Item 1: Default extraction method — LLM

### Problem

The extractor registry lists `llamaextract` before `llm`. `ExtractionForm` seeds `extractionMethod` by picking the first configured extractor, so when a `LLAMA_CLOUD_KEY` is present both methods are configured and `llamaextract` wins. The desired default is always `llm`.

### Change

**File:** `backend/app/adapters/extraction/registry.py`

Swap the order of the two entries in `get_known_extractors()` so the `llm` dict comes before the `llamaextract` dict. That's it — the frontend `useEffect` already picks `firstConfigured`, and `llm` is always configured, so it becomes the default. The dropdown display order also changes to show LLM first, which is the right UX priority.

No frontend changes. No test changes needed.

---

## Item 2: Collapsible extraction result rows

### Problem

In `ExtractionHistory`, each result row is a `Collapsible`. The `onOpenChange` handler only acts when `open` becomes `true`:

```tsx
onOpenChange={(open) => { if (open) onSelectResult(r.id) }}
```

Clicking an already-expanded row sends `open = false`, which is ignored. The row cannot be collapsed.

### Changes

**File:** `frontend/src/hooks/useExtractionResults.ts`

Add `clearSelection` to the return interface and implementation:

```ts
// Interface
clearSelection: () => void

// Implementation
const clearSelection = useCallback(() => {
  setSelectedResult(null)
}, [])

// Return object
return { ..., clearSelection, ... }
```

**File:** `frontend/src/components/extraction/ExtractionHistory.tsx`

Add `onDeselectResult: () => void` to `ExtractionHistoryProps` and destructure it. Update `onOpenChange`:

```tsx
onOpenChange={(open) => {
  if (open) onSelectResult(r.id)
  else onDeselectResult()
}}
```

**File:** `frontend/src/pages/ExtractionPage.tsx`

Destructure `clearSelection` from the hook and pass it:

```tsx
const { ..., clearSelection, ... } = useExtractionResults(selectedDocumentId)

<ExtractionHistory
  ...
  onDeselectResult={clearSelection}
/>
```

### Scope

No backend changes. No new tests needed — the existing `useExtractionResults.test.ts` covers state management; `clearSelection` is a one-liner with no logic to test independently. If a test is added, it belongs in `useExtractionResults.test.ts` as `it('clearSelection sets selectedResult to null', ...)`.
