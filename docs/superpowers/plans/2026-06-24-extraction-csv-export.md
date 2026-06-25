# Extraction CSV Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CSV export button to both the extraction result detail viewer and the history list row, using a pure frontend utility that flattens `structuredData` into a downloadable CSV file.

**Architecture:** A pure TypeScript utility (`exportCsv.ts`) exposes `buildCsvString` (pure, testable) and `exportResultToCsv` (side-effecting download trigger). `ExtractionResultViewer` calls it directly since the data is already in memory. `ExtractionHistory` delegates to a new `onExportResult` prop handled by `ExtractionPage`, which fetches the full result if needed before calling the utility.

**Tech Stack:** React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS, Vitest, React Testing Library

## Global Constraints

- No new npm dependencies
- No backend changes
- TypeScript with strict types throughout
- Follow existing shadcn/ui + Tailwind patterns (`Button`, `lucide-react` icons already installed)
- Run linter with `npm run lint` (from `frontend/` directory) before each commit
- Run tests with `npx vitest run` (from `frontend/` directory)

---

## File Map

| File | Change |
|---|---|
| `frontend/src/lib/exportCsv.ts` | New — CSV utility: `buildCsvString` + `exportResultToCsv` |
| `frontend/src/lib/exportCsv.test.ts` | New — unit tests for `buildCsvString` |
| `frontend/src/components/extraction/ExtractionResultViewer.tsx` | Add `schemaName?: string` prop; add Export CSV button in CardHeader |
| `frontend/src/components/extraction/ExtractionResultViewer.test.tsx` | Add tests for button visibility and click behaviour |
| `frontend/src/components/extraction/ExtractionHistory.tsx` | Add `onExportResult` prop, `useState`, `Download` icon button; pass `schemaName` to `ExtractionResultViewer` |
| `frontend/src/pages/ExtractionPage.tsx` | Import `exportResultToCsv`, add `handleExportResult`, pass `onExportResult` to `ExtractionHistory` |

---

## Task 1: CSV Flattening Utility

**Files:**
- Create: `frontend/src/lib/exportCsv.ts`
- Create: `frontend/src/lib/exportCsv.test.ts`

**Interfaces:**
- Produces:
  - `buildCsvString(structuredData: Record<string, unknown>): string` — pure function, used in tests
  - `exportResultToCsv(structuredData: Record<string, unknown>, filename: string): void` — triggers browser download

---

- [ ] **Step 1: Create the test file**

Create `frontend/src/lib/exportCsv.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { buildCsvString } from './exportCsv'

describe('buildCsvString', () => {
  it('emits header + single row for a flat object', () => {
    expect(buildCsvString({ name: 'Alice', age: 30 })).toBe('name,age\nAlice,30')
  })

  it('emits header + one row per array element', () => {
    const data = { items: [{ sku: 'A', qty: 2 }, { sku: 'B', qty: 1 }] }
    expect(buildCsvString(data)).toBe('sku,qty\nA,2\nB,1')
  })

  it('appends flat sibling fields as extra columns on every array row', () => {
    const data = {
      title: 'Invoice',
      items: [{ sku: 'A', qty: 2 }, { sku: 'B', qty: 1 }],
    }
    expect(buildCsvString(data)).toBe('sku,qty,title\nA,2,Invoice\nB,1,Invoice')
  })

  it('picks the array with the most elements when multiple exist', () => {
    const data = {
      items: [{ sku: 'A' }, { sku: 'B' }, { sku: 'C' }],
      tags: [{ name: 'x' }],
    }
    const lines = buildCsvString(data).split('\n')
    expect(lines).toHaveLength(4) // header + 3 rows
    expect(lines[0]).toBe('sku')
  })

  it('collects all columns from all rows when array items have different keys', () => {
    const data = {
      items: [{ sku: 'A', qty: 2 }, { sku: 'B', note: 'special' }],
    }
    expect(buildCsvString(data)).toBe('sku,qty,note\nA,2,\nB,,special')
  })

  it('wraps cells containing commas in double-quotes', () => {
    expect(buildCsvString({ name: 'Smith, John' })).toBe('name\n"Smith, John"')
  })

  it('escapes embedded double-quotes per RFC 4180', () => {
    expect(buildCsvString({ note: 'He said "hello"' })).toBe('note\n"He said ""hello"""')
  })

  it('wraps cells containing newlines in double-quotes', () => {
    expect(buildCsvString({ text: 'line1\nline2' })).toBe('text\n"line1\nline2"')
  })

  it('serializes nested objects as RFC 4180-quoted JSON strings', () => {
    // JSON.stringify produces double-quotes around keys, triggering quoting
    expect(buildCsvString({ meta: { x: 1 }, name: 'Alice' }))
      .toBe('meta,name\n"{""x"":1}",Alice')
  })

  it('emits empty string for null and undefined values', () => {
    expect(buildCsvString({ a: null, b: 'x' })).toBe('a,b\n,x')
  })

  it('falls back to a data column containing full JSON for an empty object', () => {
    expect(buildCsvString({})).toBe('data\n{}')
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
npx --prefix frontend vitest run src/lib/exportCsv.test.ts
```

Expected: FAIL — `Cannot find module './exportCsv'`

- [ ] **Step 3: Create the utility**

Create `frontend/src/lib/exportCsv.ts`:

```typescript
function toCsvCell(value: unknown): string {
  if (value === null || value === undefined) return ''
  const str = typeof value === 'object' ? JSON.stringify(value) : String(value)
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

function toCsvRow(values: unknown[]): string {
  return values.map(toCsvCell).join(',')
}

function isObjectArray(value: unknown): value is Record<string, unknown>[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((el) => el !== null && typeof el === 'object' && !Array.isArray(el))
  )
}

export function buildCsvString(structuredData: Record<string, unknown>): string {
  const entries = Object.entries(structuredData)

  const flatFields: [string, unknown][] = []
  const arrayFields: [string, Record<string, unknown>[]][] = []

  for (const [key, value] of entries) {
    if (isObjectArray(value)) {
      arrayFields.push([key, value])
    } else {
      flatFields.push([key, value])
    }
  }

  if (arrayFields.length === 0) {
    if (flatFields.length === 0) {
      return 'data\n' + toCsvCell(JSON.stringify(structuredData))
    }
    const headers = flatFields.map(([k]) => k)
    const values = flatFields.map(([, v]) => v)
    return toCsvRow(headers) + '\n' + toCsvRow(values)
  }

  const [, primaryArray] = arrayFields.reduce((best, curr) =>
    curr[1].length > best[1].length ? curr : best
  )

  const arrayColumns = Array.from(
    new Set(primaryArray.flatMap((row) => Object.keys(row)))
  )
  const flatColumns = flatFields.map(([k]) => k)
  const allColumns = [...arrayColumns, ...flatColumns]

  const rows = primaryArray.map((row) => {
    const arrayValues = arrayColumns.map((col) => row[col] ?? null)
    const flatValues = flatFields.map(([, v]) => v)
    return toCsvRow([...arrayValues, ...flatValues])
  })

  return toCsvRow(allColumns) + '\n' + rows.join('\n')
}

export function exportResultToCsv(
  structuredData: Record<string, unknown>,
  filename: string
): void {
  const csvString = buildCsvString(structuredData)
  const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
npx --prefix frontend vitest run src/lib/exportCsv.test.ts
```

Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/exportCsv.ts frontend/src/lib/exportCsv.test.ts
git commit -m "feat(extraction): add CSV flattening utility"
```

---

## Task 2: Export Button in ExtractionResultViewer

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionResultViewer.tsx`
- Modify: `frontend/src/components/extraction/ExtractionResultViewer.test.tsx`

**Interfaces:**
- Consumes: `exportResultToCsv` from `@/lib/exportCsv`
- Prop added: `schemaName?: string` on `ExtractionResultViewerProps`

---

- [ ] **Step 1: Add failing tests**

Open `frontend/src/components/extraction/ExtractionResultViewer.test.tsx` and make two edits:

**1a.** At the top of the file, add `vi` to the existing vitest import and add the mock + import for `exportResultToCsv`. The top of the file should look like:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ExtractionResultViewer } from './ExtractionResultViewer'
import type { ExtractionResult } from '@/types/extraction'

vi.mock('@/lib/exportCsv', () => ({
  exportResultToCsv: vi.fn(),
}))

import { exportResultToCsv } from '@/lib/exportCsv'
```

**1b.** Append the following new `describe` block at the end of the file:

```typescript
describe('Export CSV button', () => {
  it('renders when result is completed with structuredData', () => {
    render(<ExtractionResultViewer result={buildResult()} />)
    expect(screen.getByRole('button', { name: /export csv/i })).toBeInTheDocument()
  })

  it('does not render when result is pending', () => {
    render(<ExtractionResultViewer result={buildResult({ status: 'pending', structuredData: null })} />)
    expect(screen.queryByRole('button', { name: /export csv/i })).not.toBeInTheDocument()
  })

  it('does not render when structuredData is null', () => {
    render(<ExtractionResultViewer result={buildResult({ structuredData: null })} />)
    expect(screen.queryByRole('button', { name: /export csv/i })).not.toBeInTheDocument()
  })

  it('does not render when structuredData is empty', () => {
    render(<ExtractionResultViewer result={buildResult({ structuredData: {} })} />)
    expect(screen.queryByRole('button', { name: /export csv/i })).not.toBeInTheDocument()
  })

  it('calls exportResultToCsv with structuredData and filename on click', async () => {
    const user = userEvent.setup()
    render(
      <ExtractionResultViewer
        result={buildResult({ id: 'abcdef12-0000-0000-0000-000000000000' })}
        schemaName="My Schema"
      />
    )
    await user.click(screen.getByRole('button', { name: /export csv/i }))
    expect(exportResultToCsv).toHaveBeenCalledWith(
      { invoice_number: 'INV-001' },
      'My Schema_abcdef12.csv'
    )
  })

  it('uses "extraction" as fallback filename when schemaName is not provided', async () => {
    const user = userEvent.setup()
    render(
      <ExtractionResultViewer
        result={buildResult({ id: 'abcdef12-0000-0000-0000-000000000000' })}
      />
    )
    await user.click(screen.getByRole('button', { name: /export csv/i }))
    expect(exportResultToCsv).toHaveBeenCalledWith(
      { invoice_number: 'INV-001' },
      'extraction_abcdef12.csv'
    )
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npx --prefix frontend vitest run src/components/extraction/ExtractionResultViewer.test.tsx
```

Expected: The new `Export CSV button` tests FAIL — button not found in DOM.

- [ ] **Step 3: Update ExtractionResultViewer**

In `frontend/src/components/extraction/ExtractionResultViewer.tsx`:

**3a.** Add `Download` to the lucide-react import (line 23):

```typescript
import { ChevronDown, Download, Loader2 } from 'lucide-react'
```

**3b.** Add `exportResultToCsv` import after the existing imports:

```typescript
import { exportResultToCsv } from '@/lib/exportCsv'
```

**3c.** Add `schemaName` to the props interface (after `isLoading`):

```typescript
interface ExtractionResultViewerProps {
  result: ExtractionResult | null
  isLoading?: boolean
  schemaName?: string
}
```

**3d.** Destructure `schemaName` in the component signature:

```typescript
export function ExtractionResultViewer({
  result,
  isLoading,
  schemaName,
}: ExtractionResultViewerProps) {
```

**3e.** In the `CardHeader` section (around line 421), add the Export CSV button to the right-side div — replace:

```typescript
            <div className="flex items-center gap-2">
              <Badge variant={statusColor}>
```

with:

```typescript
            <div className="flex items-center gap-2">
              {result.status === 'completed' &&
                result.structuredData &&
                Object.keys(result.structuredData).length > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs gap-1.5"
                    onClick={() =>
                      exportResultToCsv(
                        result.structuredData!,
                        `${schemaName ?? 'extraction'}_${result.id.slice(0, 8)}.csv`
                      )
                    }
                  >
                    <Download className="h-3.5 w-3.5" />
                    Export CSV
                  </Button>
                )}
              <Badge variant={statusColor}>
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx --prefix frontend vitest run src/components/extraction/ExtractionResultViewer.test.tsx
```

Expected: All tests PASS

- [ ] **Step 5: Lint**

```bash
npm --prefix frontend run lint
```

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/extraction/ExtractionResultViewer.tsx frontend/src/components/extraction/ExtractionResultViewer.test.tsx
git commit -m "feat(extraction): add Export CSV button to result viewer"
```

---

## Task 3: ExtractionHistory Download Icon + ExtractionPage Wiring

Both files must be changed together because `ExtractionHistory` adds a required `onExportResult` prop that `ExtractionPage` must immediately supply.

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionHistory.tsx`
- Modify: `frontend/src/pages/ExtractionPage.tsx`

**Interfaces:**
- Consumes (ExtractionHistory):
  - `onExportResult: (resultId: string) => Promise<void>` — new required prop
  - `exportResultToCsv` from `@/lib/exportCsv` (via ExtractionPage, not imported here)
- Consumes (ExtractionPage):
  - `exportResultToCsv(structuredData, filename)` from `@/lib/exportCsv`
  - `extractionApi.getExtractionResult(resultId)` (already available via `* as extractionApi`)

---

- [ ] **Step 1: Update ExtractionHistory**

In `frontend/src/components/extraction/ExtractionHistory.tsx`:

**1a.** Replace the React import line to add `useState`:

```typescript
import { useState } from 'react'
```

**1b.** Add `Download` to the lucide-react import (currently line 10):

```typescript
import { AlertCircle, ChevronRight, Download, Loader2, RefreshCw, Trash2 } from 'lucide-react'
```

**1c.** Add `onExportResult` to the props interface (after `onDeleteResult`):

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
  onExportResult: (resultId: string) => Promise<void>
  inProgressPhase?: InProgressPhase
}
```

**1d.** Destructure `onExportResult` in the component function signature:

```typescript
export function ExtractionHistory({
  results,
  isLoading,
  selectedResult,
  schemas,
  onSelectResult,
  onDeselectResult,
  onDeleteResult,
  onExportResult,
  inProgressPhase,
}: ExtractionHistoryProps) {
```

**1e.** Add `exportingId` state and `handleExport` immediately after the function signature opening (before the first `if`):

```typescript
  const [exportingId, setExportingId] = useState<string | null>(null)

  const handleExport = async (resultId: string) => {
    setExportingId(resultId)
    try {
      await onExportResult(resultId)
    } finally {
      setExportingId(null)
    }
  }
```

**1f.** In the `results.map` block, replace the single trash button with a fragment containing both the download and trash buttons. Find (around line 136):

```typescript
              {!isPending && (
                <button
                  className="shrink-0 px-2 py-2 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                  aria-label="Delete extraction run"
                  onClick={(e) => { e.stopPropagation(); onDeleteResult(r.id) }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
```

Replace with:

```typescript
              {!isPending && (
                <>
                  <button
                    className="shrink-0 px-2 py-2 text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 transition-opacity disabled:cursor-not-allowed"
                    aria-label="Export as CSV"
                    disabled={exportingId === r.id}
                    onClick={(e) => { e.stopPropagation(); void handleExport(r.id) }}
                  >
                    <Download className="h-3.5 w-3.5" />
                  </button>
                  <button
                    className="shrink-0 px-2 py-2 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                    aria-label="Delete extraction run"
                    onClick={(e) => { e.stopPropagation(); onDeleteResult(r.id) }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </>
              )}
```

**1g.** Pass `schemaName` to `ExtractionResultViewer` inside the `CollapsibleContent`. Find (around line 150):

```typescript
                  <ExtractionResultViewer result={selectedResult} isLoading={false} />
```

Replace with:

```typescript
                  <ExtractionResultViewer
                    result={selectedResult}
                    isLoading={false}
                    schemaName={schemas?.find((s) => s.id === r.extractionSchemaId)?.name}
                  />
```

- [ ] **Step 2: Update ExtractionPage**

In `frontend/src/pages/ExtractionPage.tsx`:

**2a.** Add the `exportResultToCsv` import after the existing imports block:

```typescript
import { exportResultToCsv } from '@/lib/exportCsv'
```

**2b.** Add `handleExportResult` as a new handler alongside the existing handlers (e.g., after `handleRetry`):

```typescript
  const handleExportResult = async (resultId: string) => {
    try {
      const result =
        selectedResult?.id === resultId
          ? selectedResult
          : await extractionApi.getExtractionResult(resultId)
      if (!result.structuredData || Object.keys(result.structuredData).length === 0) return
      const schema = schemas?.find((s) => s.id === result.extractionSchemaId)
      const filename = `${schema?.name ?? 'extraction'}_${resultId.slice(0, 8)}.csv`
      exportResultToCsv(result.structuredData, filename)
    } catch {
      toast.error('Failed to fetch result for export')
    }
  }
```

**2c.** Add `onExportResult` to the `ExtractionHistory` JSX (around line 260):

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
                  onExportResult={handleExportResult}
                  inProgressPhase={inProgressPhase}
                />
```

- [ ] **Step 3: Run full frontend test suite**

```bash
npx --prefix frontend vitest run
```

Expected: All tests PASS (no regressions).

- [ ] **Step 4: Lint**

```bash
npm --prefix frontend run lint
```

Expected: No errors.

- [ ] **Step 5: Build**

```bash
npm --prefix frontend run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/extraction/ExtractionHistory.tsx frontend/src/pages/ExtractionPage.tsx
git commit -m "feat(extraction): add CSV export to history list row"
```

---

## Manual Verification Checklist

After all tasks are complete:

1. Start the dev server: `npm --prefix frontend run dev`
2. Navigate to the Extraction page and select a document
3. Run an extraction and wait for it to complete
4. Expand the completed result — verify the "Export CSV" button appears in the card header
5. Click "Export CSV" — verify a `.csv` file downloads with the schema name and result ID prefix in the filename
6. Open the CSV in Excel or a text editor — verify it matches the structured data shown in the viewer
7. Hover over the completed result in the history list — verify the download icon appears to the left of the trash icon
8. Click the download icon in the list row — verify the same CSV downloads
9. Hover over a pending result — verify neither the download nor trash icon appear
10. Verify no console errors during any of the above steps
