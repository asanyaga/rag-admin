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

The extractor registry lists `llamaextract` before `llm`. `ExtractionForm` picks the first configured extractor, so when a `LLAMA_CLOUD_KEY` is present both methods are configured and `llamaextract` wins. The desired default is always `llm`.

### Change

**File:** `frontend/src/components/extraction/ExtractionForm.tsx`

The `useEffect` that seeds `extractionMethod` (lines 86–91) currently does:

```tsx
const firstConfigured = extractors.find((e) => e.configured)
setExtractionMethod(firstConfigured?.extractionMethod ?? extractors[0].extractionMethod)
```

Change to prefer `'llm'` first:

```tsx
const llmExtractor = extractors.find((e) => e.extractionMethod === 'llm' && e.configured)
const firstConfigured = extractors.find((e) => e.configured)
setExtractionMethod(
  (llmExtractor ?? firstConfigured)?.extractionMethod ?? extractors[0].extractionMethod
)
```

No backend changes. No test changes needed — the existing `ExtractionForm.test.tsx` covers the form; this logic has no standalone unit test today and is too shallow to warrant one.

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
