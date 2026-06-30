# Extract Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Extract section into three pages — a main list page, a new-run config page, and a result detail page with bidirectional PDF provenance — sharing the document picker pattern used by Parse and Classify.

**Architecture:** A new `useExtractionSubmit` hook handles parse+extraction submission and returns the result ID (enabling immediate navigation to the detail page). A new `useExtractionResultDetail` hook polls a single result. A shared `DocumentPickerPanel` component replaces the extraction-specific `DocumentSelector`. The existing `ExtractionForm` is absorbed into `NewExtractionRunPage` and deleted. `ExtractionResultViewer` gains three optional provenance props; its content is otherwise unchanged.

**Tech Stack:** React 18, TypeScript, React Router v6, Vitest + React Testing Library, shadcn/ui, Tailwind CSS, react-pdf (`DocumentPdfViewer` already exists).

## Global Constraints

- Never use `cd X && Y` — use absolute paths or per-tool working-directory flags
- Frontend commands run from `frontend/` directory: `npm run dev`, `npm run lint`, `npm run build`, `npx vitest run`
- All new pages follow the `-m-6 flex flex-col h-[calc(100vh-3.5rem)]` full-bleed layout pattern
- shadcn/ui + Tailwind for all UI; no new UI libraries
- TypeScript strict — no `any`, use `unknown` with type guards
- Spec: `docs/superpowers/specs/2026-06-30-extract-page-redesign-design.md`

---

## File Map

| Action | Path |
|---|---|
| Create | `frontend/src/hooks/useExtractionSubmit.ts` |
| Create | `frontend/src/hooks/useExtractionResultDetail.ts` |
| Create | `frontend/src/components/shared/DocumentPickerPanel.tsx` |
| Create | `frontend/src/pages/NewExtractionRunPage.tsx` |
| Create | `frontend/src/pages/ExtractionResultDetailPage.tsx` |
| Modify | `frontend/src/pages/ExtractionPage.tsx` |
| Modify | `frontend/src/components/extraction/ExtractionHistory.tsx` |
| Modify | `frontend/src/components/extraction/ExtractionResultViewer.tsx` |
| Modify | `frontend/src/App.tsx` |
| Delete | `frontend/src/components/extraction/DocumentSelector.tsx` |
| Delete | `frontend/src/components/extraction/ExtractionForm.tsx` |
| Delete | `frontend/src/components/extraction/ExtractionForm.test.tsx` |

---

## Task 1: Feature branch + `useExtractionSubmit` hook

The existing `useExtractionResults.runExtractionWithParse` returns `void` and sets phase state internally. The new run page needs to get the result ID after submission so it can navigate to it. This hook provides that — it is a parallel, standalone hook used only by `NewExtractionRunPage`; `useExtractionResults` is left unchanged.

**Files:**
- Create: `frontend/src/hooks/useExtractionSubmit.ts`
- Create: `frontend/src/hooks/useExtractionSubmit.test.ts`

**Interfaces:**
- Produces: `useExtractionSubmit(): { phase: SubmitPhase, phaseError: string | null, submit: (documentId, existingParseRuns, request) => Promise<string | null> }`
- `submit` resolves to the new `ExtractionResult.id` on success, `null` on failure

- [ ] **Step 1: Create feature branch**

```bash
git checkout -b feat/extract-page-redesign
```

- [ ] **Step 2: Write the failing test**

```ts
// frontend/src/hooks/useExtractionSubmit.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useExtractionSubmit } from './useExtractionSubmit'
import * as extractionApi from '@/api/extraction'
import * as parseRunsApi from '@/api/parseRuns'
import type { RunWithParseRequest } from '@/types/extraction'
import type { ParseRunListItem } from '@/types/cdm'

vi.mock('@/api/extraction', () => ({
  runExtraction: vi.fn(),
}))
vi.mock('@/api/parseRuns', () => ({
  createParseRun: vi.fn(),
  listParseRuns: vi.fn(),
  getParseRun: vi.fn(),
}))

const matchingRun: ParseRunListItem = {
  id: 'run-1',
  parser: 'simple',
  representationKind: 'extract_rich',
  config: {},
  status: 'succeeded',
  error: null,
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
}

const request: RunWithParseRequest = {
  parseConfig: { parser: 'simple', config: {}, representationKind: 'extract_rich' },
  extractionConfig: { extractionSchemaId: 'schema-1', extractionMethod: 'llm' },
}

describe('useExtractionSubmit', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('returns result id when matching parse run exists', async () => {
    vi.mocked(extractionApi.runExtraction).mockResolvedValue(
      { id: 'result-1', status: 'pending' } as never
    )
    const { result } = renderHook(() => useExtractionSubmit())
    let resultId: string | null = null
    await act(async () => {
      resultId = await result.current.submit('doc-1', [matchingRun], request)
    })
    expect(resultId).toBe('result-1')
    expect(result.current.phase).toBe('idle')
    expect(parseRunsApi.createParseRun).not.toHaveBeenCalled()
  })

  it('sets phase to failed and returns null when runExtraction throws', async () => {
    vi.mocked(extractionApi.runExtraction).mockRejectedValue(new Error('API error'))
    const { result } = renderHook(() => useExtractionSubmit())
    let resultId: string | null = 'not-null'
    await act(async () => {
      resultId = await result.current.submit('doc-1', [matchingRun], request)
    })
    expect(resultId).toBeNull()
    expect(result.current.phase).toBe('failed')
    expect(result.current.phaseError).toBe('API error')
  })
})
```

- [ ] **Step 3: Run test to confirm it fails**

```bash
npx --prefix frontend vitest run src/hooks/useExtractionSubmit.test.ts
```
Expected: FAIL — module not found

- [ ] **Step 4: Create `useExtractionSubmit.ts`**

```ts
// frontend/src/hooks/useExtractionSubmit.ts
import { useState, useCallback, useRef } from 'react'
import type { RunWithParseRequest } from '@/types/extraction'
import type { ParseRunListItem } from '@/types/cdm'
import * as extractionApi from '@/api/extraction'
import { createParseRun, listParseRuns, getParseRun } from '@/api/parseRuns'

const POLLING_INTERVAL = 3_000
const PARSE_TIMEOUT_MS = 10 * 60 * 1_000

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function stableStringify(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${(value as unknown[]).map(stableStringify).join(',')}]`
  const obj = value as Record<string, unknown>
  return `{${Object.keys(obj).sort().map((k) => `${JSON.stringify(k)}:${stableStringify(obj[k])}`).join(',')}}`
}

function findMatchingRun(
  runs: ParseRunListItem[],
  parser: string,
  representationKind: string,
  config: Record<string, unknown>,
): ParseRunListItem | undefined {
  const target = stableStringify({ parser, ...config })
  return runs.find(
    (r) =>
      r.parser === parser &&
      r.representationKind === representationKind &&
      stableStringify(r.config) === target &&
      (r.status === 'succeeded' || r.status === 'partial'),
  )
}

export type SubmitPhase = 'idle' | 'parsing' | 'extracting' | 'failed'

export interface UseExtractionSubmitReturn {
  phase: SubmitPhase
  phaseError: string | null
  submit: (
    documentId: string,
    existingParseRuns: ParseRunListItem[],
    request: RunWithParseRequest,
  ) => Promise<string | null>
}

export function useExtractionSubmit(): UseExtractionSubmitReturn {
  const [phase, setPhase] = useState<SubmitPhase>('idle')
  const [phaseError, setPhaseError] = useState<string | null>(null)
  const cancelledRef = useRef(false)

  const submit = useCallback(
    async (
      documentId: string,
      existingParseRuns: ParseRunListItem[],
      request: RunWithParseRequest,
    ): Promise<string | null> => {
      const { parseConfig, extractionConfig } = request
      setPhaseError(null)
      cancelledRef.current = false

      const matched = findMatchingRun(
        existingParseRuns,
        parseConfig.parser,
        parseConfig.representationKind,
        parseConfig.config,
      )
      let parseRunId: string

      if (matched) {
        parseRunId = matched.id
      } else {
        setPhase('parsing')
        const started = Date.now()
        try {
          await createParseRun(documentId, parseConfig.parser, {
            ...parseConfig.config,
            representation_kind: parseConfig.representationKind,
          })
        } catch {
          setPhase('failed')
          setPhaseError('Failed to start parse')
          return null
        }

        let resolvedId: string | null = null
        while (resolvedId === null) {
          if (cancelledRef.current) return null
          if (Date.now() - started > PARSE_TIMEOUT_MS) {
            setPhase('failed')
            setPhaseError('Parse timed out')
            return null
          }
          await sleep(POLLING_INTERVAL)
          const runs = await listParseRuns(documentId)
          const target = stableStringify({ parser: parseConfig.parser, ...parseConfig.config })
          const found = runs.find(
            (r) =>
              r.parser === parseConfig.parser &&
              r.representationKind === parseConfig.representationKind &&
              stableStringify(r.config) === target,
          )
          if (found) resolvedId = found.id
        }

        const foundId = resolvedId
        for (;;) {
          if (cancelledRef.current) return null
          if (Date.now() - started > PARSE_TIMEOUT_MS) {
            setPhase('failed')
            setPhaseError('Parse timed out')
            return null
          }
          const run = await getParseRun(foundId)
          if (run.status === 'succeeded' || run.status === 'partial') {
            parseRunId = foundId
            break
          }
          if (run.status === 'failed') {
            setPhase('failed')
            setPhaseError(run.error ?? 'Parse failed')
            return null
          }
          await sleep(POLLING_INTERVAL)
        }
      }

      setPhase('extracting')
      try {
        const result = await extractionApi.runExtraction({
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
        setPhase('idle')
        return result.id
      } catch (err) {
        setPhase('failed')
        setPhaseError(err instanceof Error ? err.message : 'Extraction failed')
        return null
      }
    },
    [],
  )

  return { phase, phaseError, submit }
}
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
npx --prefix frontend vitest run src/hooks/useExtractionSubmit.test.ts
```
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useExtractionSubmit.ts frontend/src/hooks/useExtractionSubmit.test.ts
git commit -m "feat(extract): add useExtractionSubmit hook returning result id"
```

---

## Task 2: `useExtractionResultDetail` hook

Fetches a single extraction result by ID and polls every 3 s while `status === 'pending'`, stopping once `status` is `completed` or `failed`.

**Files:**
- Create: `frontend/src/hooks/useExtractionResultDetail.ts`
- Create: `frontend/src/hooks/useExtractionResultDetail.test.ts`

**Interfaces:**
- Produces: `useExtractionResultDetail(resultId: string | null): { result: ExtractionResult | null, isLoading: boolean, error: string | null }`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/hooks/useExtractionResultDetail.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useExtractionResultDetail } from './useExtractionResultDetail'
import * as extractionApi from '@/api/extraction'
import type { ExtractionResult } from '@/types/extraction'

vi.mock('@/api/extraction', () => ({ getExtractionResult: vi.fn() }))

const pending: ExtractionResult = {
  id: 'r1', documentId: 'd1', extractionSchemaId: 's1',
  schemaDefinitionSnapshot: {}, extractionMethod: 'llm', config: null,
  structuredData: null, extractionMetadata: null, citations: null,
  providerResponseRaw: null, sourceParseRunId: null, status: 'pending',
  statusMessage: null, startedAt: null, timeoutMinutes: null,
  createdBy: 'u1', createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z',
}
const completed: ExtractionResult = { ...pending, status: 'completed' }

describe('useExtractionResultDetail', () => {
  beforeEach(() => { vi.clearAllMocks(); vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('fetches and returns result', async () => {
    vi.mocked(extractionApi.getExtractionResult).mockResolvedValue(completed)
    const { result } = renderHook(() => useExtractionResultDetail('r1'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.result?.id).toBe('r1')
    expect(result.current.result?.status).toBe('completed')
  })

  it('stops polling once result is completed', async () => {
    vi.mocked(extractionApi.getExtractionResult)
      .mockResolvedValueOnce(pending)
      .mockResolvedValueOnce(completed)
    const { result } = renderHook(() => useExtractionResultDetail('r1'))
    await waitFor(() => expect(result.current.result?.status).toBe('pending'))
    await act(async () => { vi.advanceTimersByTime(3_100) })
    await waitFor(() => expect(result.current.result?.status).toBe('completed'))
    const callCount = vi.mocked(extractionApi.getExtractionResult).mock.calls.length
    await act(async () => { vi.advanceTimersByTime(6_000) })
    expect(vi.mocked(extractionApi.getExtractionResult).mock.calls.length).toBe(callCount)
  })
})
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
npx --prefix frontend vitest run src/hooks/useExtractionResultDetail.test.ts
```
Expected: FAIL — module not found

- [ ] **Step 3: Implement the hook**

```ts
// frontend/src/hooks/useExtractionResultDetail.ts
import { useState, useEffect, useRef, useCallback } from 'react'
import type { ExtractionResult } from '@/types/extraction'
import { getExtractionResult } from '@/api/extraction'

const POLL_INTERVAL = 3_000

export function useExtractionResultDetail(resultId: string | null): {
  result: ExtractionResult | null
  isLoading: boolean
  error: string | null
} {
  const [result, setResult] = useState<ExtractionResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null }
  }, [])

  useEffect(() => {
    if (!resultId) { setResult(null); return }
    setIsLoading(true)
    setError(null)
    let cancelled = false

    getExtractionResult(resultId)
      .then((data) => {
        if (cancelled) return
        setResult(data)
        setIsLoading(false)
        if (data.status === 'pending') {
          intervalRef.current = setInterval(async () => {
            try {
              const updated = await getExtractionResult(resultId)
              if (cancelled) return
              setResult(updated)
              if (updated.status !== 'pending') stopPolling()
            } catch { stopPolling() }
          }, POLL_INTERVAL)
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load result')
        setIsLoading(false)
      })

    return () => { cancelled = true; stopPolling() }
  }, [resultId, stopPolling])

  return { result, isLoading, error }
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
npx --prefix frontend vitest run src/hooks/useExtractionResultDetail.test.ts
```
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useExtractionResultDetail.ts frontend/src/hooks/useExtractionResultDetail.test.ts
git commit -m "feat(extract): add useExtractionResultDetail hook with pending poll"
```

---

## Task 3: `DocumentPickerPanel` shared component

Folder filter + search + document list + upload button. Matches the visual pattern from `ClassificationPage` and `DocumentsPage`. Replace the extraction-specific `DocumentSelector`.

**Files:**
- Create: `frontend/src/components/shared/DocumentPickerPanel.tsx`
- Create: `frontend/src/components/shared/DocumentPickerPanel.test.tsx`
- Delete: `frontend/src/components/extraction/DocumentSelector.tsx`

**Interfaces:**
- Consumes: `DocumentListItem[]`, `Folder[]` (from `@/types/folder`), `isLoading`, `selectedDocumentId`, `onSelect`, `onUploadClick`
- Produces: the component; used in `ExtractionPage` (Task 6)

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/shared/DocumentPickerPanel.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DocumentPickerPanel } from './DocumentPickerPanel'
import type { DocumentListItem } from '@/types/document'
import type { Folder } from '@/types/folder'

const docs: DocumentListItem[] = [
  { id: 'd1', title: 'Alpha.pdf', status: 'ready', folderId: null, createdAt: '2026-01-01T00:00:00Z' },
  { id: 'd2', title: 'Beta.pdf', status: 'processing', folderId: null, createdAt: '2026-01-01T00:00:00Z' },
]
const folders: Folder[] = [{ id: 'f1', name: 'Invoices', projectId: 'p1', createdAt: '2026-01-01T00:00:00Z' }]

describe('DocumentPickerPanel', () => {
  it('renders document list', () => {
    render(<DocumentPickerPanel documents={docs} folders={folders} isLoading={false}
      selectedDocumentId={null} onSelect={vi.fn()} onUploadClick={vi.fn()} />)
    expect(screen.getByText('Alpha.pdf')).toBeInTheDocument()
    expect(screen.getByText('Beta.pdf')).toBeInTheDocument()
  })

  it('calls onSelect with document id when row clicked', async () => {
    const onSelect = vi.fn()
    render(<DocumentPickerPanel documents={docs} folders={folders} isLoading={false}
      selectedDocumentId={null} onSelect={onSelect} onUploadClick={vi.fn()} />)
    await userEvent.click(screen.getByText('Alpha.pdf'))
    expect(onSelect).toHaveBeenCalledWith('d1')
  })

  it('does not call onSelect for processing documents', async () => {
    const onSelect = vi.fn()
    render(<DocumentPickerPanel documents={docs} folders={folders} isLoading={false}
      selectedDocumentId={null} onSelect={onSelect} onUploadClick={vi.fn()} />)
    await userEvent.click(screen.getByText('Beta.pdf'))
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('filters list by search text', async () => {
    render(<DocumentPickerPanel documents={docs} folders={folders} isLoading={false}
      selectedDocumentId={null} onSelect={vi.fn()} onUploadClick={vi.fn()} />)
    await userEvent.type(screen.getByPlaceholderText('Search documents...'), 'Alpha')
    expect(screen.getByText('Alpha.pdf')).toBeInTheDocument()
    expect(screen.queryByText('Beta.pdf')).not.toBeInTheDocument()
  })

  it('calls onUploadClick when upload button clicked', async () => {
    const onUploadClick = vi.fn()
    render(<DocumentPickerPanel documents={docs} folders={folders} isLoading={false}
      selectedDocumentId={null} onSelect={vi.fn()} onUploadClick={onUploadClick} />)
    await userEvent.click(screen.getByRole('button', { name: /upload/i }))
    expect(onUploadClick).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
npx --prefix frontend vitest run src/components/shared/DocumentPickerPanel.test.tsx
```
Expected: FAIL — module not found

- [ ] **Step 3: Create the component**

```tsx
// frontend/src/components/shared/DocumentPickerPanel.tsx
import { useState } from 'react'
import type { DocumentListItem } from '@/types/document'
import type { Folder } from '@/types/folder'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { DocumentStatusBadge } from '@/components/documents/DocumentStatusBadge'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { Search, Upload, FileText } from 'lucide-react'

interface DocumentPickerPanelProps {
  documents: DocumentListItem[]
  folders: Folder[]
  isLoading: boolean
  selectedDocumentId: string | null
  onSelect: (documentId: string) => void
  onUploadClick: () => void
}

export function DocumentPickerPanel({
  documents, folders, isLoading, selectedDocumentId, onSelect, onUploadClick,
}: DocumentPickerPanelProps) {
  const [search, setSearch] = useState('')
  const [folderId, setFolderId] = useState<string | null>(null)

  const filtered = documents.filter((doc) => {
    const matchesFolder = folderId === null || doc.folderId === folderId
    const matchesSearch = doc.title.toLowerCase().includes(search.toLowerCase())
    return matchesFolder && matchesSearch
  })

  return (
    <div className="flex flex-col h-full">
      {folders.length > 0 && (
        <div className="p-3 border-b">
          <Select value={folderId ?? '__all__'} onValueChange={(v) => setFolderId(v === '__all__' ? null : v)}>
            <SelectTrigger className="h-8 text-sm"><SelectValue placeholder="All folders" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All folders</SelectItem>
              {folders.map((f) => <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      )}
      <div className="p-3 border-b">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search documents..." value={search}
            onChange={(e) => setSearch(e.target.value)} className="pl-9 h-9" />
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2">
          {isLoading ? (
            <div className="space-y-2 p-2">
              {[0, 1, 2].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              {search ? 'No documents match your search' : 'No documents yet'}
            </p>
          ) : (
            filtered.map((doc) => {
              const isProcessing = doc.status === 'processing'
              return (
                <button key={doc.id} onClick={() => { if (!isProcessing) onSelect(doc.id) }}
                  disabled={isProcessing}
                  className={cn(
                    'w-full text-left rounded-md px-3 py-2.5 mb-1 transition-colors',
                    'hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    selectedDocumentId === doc.id && 'bg-muted',
                    isProcessing && 'opacity-50 cursor-not-allowed',
                  )}>
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="text-sm truncate flex-1">{doc.title}</span>
                    <DocumentStatusBadge status={doc.status} />
                  </div>
                </button>
              )
            })
          )}
        </div>
      </ScrollArea>
      <div className="p-3 border-t">
        <Button variant="outline" className="w-full" size="sm" onClick={onUploadClick}>
          <Upload className="h-4 w-4 mr-2" />
          Upload Document
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Delete the old extraction-specific DocumentSelector**

```bash
rm frontend/src/components/extraction/DocumentSelector.tsx
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
npx --prefix frontend vitest run src/components/shared/DocumentPickerPanel.test.tsx
```
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/shared/DocumentPickerPanel.tsx frontend/src/components/shared/DocumentPickerPanel.test.tsx
git add -u frontend/src/components/extraction/DocumentSelector.tsx
git commit -m "feat(extract): add shared DocumentPickerPanel, delete extraction DocumentSelector"
```

---

## Task 4: Simplify `ExtractionHistory` to flat navigation list

Remove `Collapsible`, `ExtractionResultViewer`, and selection props. Each row becomes a `<Link>` to `/extract/:resultId`. Export and delete buttons stay, using `e.stopPropagation()`.

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionHistory.tsx`
- Create: `frontend/src/components/extraction/ExtractionHistory.test.tsx`

**Interfaces:**
- Removed props: `selectedResult`, `isLoadingResult`, `onSelectResult`, `onDeselectResult`, `inProgressPhase`, `projectId`
- Remaining props: `results`, `isLoading`, `schemas?`, `onDeleteResult`, `onExportResult`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/extraction/ExtractionHistory.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { ExtractionHistory } from './ExtractionHistory'
import type { ExtractionResultListItem, ExtractionSchema } from '@/types/extraction'

const results: ExtractionResultListItem[] = [
  { id: 'r1', documentId: 'd1', extractionSchemaId: 's1', extractionMethod: 'llm',
    status: 'completed', statusMessage: null, timeoutMinutes: null, createdAt: '2026-01-01T00:00:00Z' },
]
const schemas: ExtractionSchema[] = [
  { id: 's1', projectId: 'p1', name: 'Invoice Schema', description: null,
    schemaDefinition: {}, extractionTarget: 'PER_DOC', createdBy: 'u1',
    createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z' },
]

function wrap(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('ExtractionHistory', () => {
  it('renders result rows as links to /extract/:id', () => {
    wrap(<ExtractionHistory results={results} isLoading={false} schemas={schemas}
      onDeleteResult={vi.fn()} onExportResult={vi.fn()} />)
    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', '/extract/r1')
  })

  it('shows schema name on the row', () => {
    wrap(<ExtractionHistory results={results} isLoading={false} schemas={schemas}
      onDeleteResult={vi.fn()} onExportResult={vi.fn()} />)
    expect(screen.getByText('Invoice Schema')).toBeInTheDocument()
  })

  it('calls onDeleteResult without navigating when delete clicked', async () => {
    const onDeleteResult = vi.fn()
    wrap(<ExtractionHistory results={results} isLoading={false} schemas={schemas}
      onDeleteResult={onDeleteResult} onExportResult={vi.fn()} />)
    const deleteBtn = screen.getByRole('button', { name: /delete/i })
    await userEvent.click(deleteBtn)
    expect(onDeleteResult).toHaveBeenCalledWith('r1')
  })

  it('shows empty state when no results', () => {
    wrap(<ExtractionHistory results={[]} isLoading={false} schemas={[]}
      onDeleteResult={vi.fn()} onExportResult={vi.fn()} />)
    expect(screen.getByText(/no extractions yet/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
npx --prefix frontend vitest run src/components/extraction/ExtractionHistory.test.tsx
```
Expected: FAIL

- [ ] **Step 3: Rewrite `ExtractionHistory.tsx`**

```tsx
// frontend/src/components/extraction/ExtractionHistory.tsx
import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { ExtractionResultListItem, ExtractionSchema } from '@/types/extraction'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2, Download, Trash2 } from 'lucide-react'

interface ExtractionHistoryProps {
  results: ExtractionResultListItem[]
  isLoading: boolean
  schemas?: ExtractionSchema[]
  onDeleteResult: (resultId: string) => Promise<void>
  onExportResult: (resultId: string) => Promise<void>
}

export function ExtractionHistory({
  results, isLoading, schemas, onDeleteResult, onExportResult,
}: ExtractionHistoryProps) {
  const [exportingId, setExportingId] = useState<string | null>(null)

  const handleExport = async (e: React.MouseEvent, resultId: string) => {
    e.preventDefault()
    e.stopPropagation()
    setExportingId(resultId)
    try { await onExportResult(resultId) } finally { setExportingId(null) }
  }

  const handleDelete = (e: React.MouseEvent, resultId: string) => {
    e.preventDefault()
    e.stopPropagation()
    void onDeleteResult(resultId)
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    )
  }

  if (results.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-6">
        No extractions yet. Run one to get started.
      </p>
    )
  }

  return (
    <div className="space-y-1">
      {results.map((r) => {
        const schemaName = schemas?.find((s) => s.id === r.extractionSchemaId)?.name
        const isPending = r.status === 'pending'
        return (
          <div key={r.id} className="flex items-center rounded-md hover:bg-muted/50 group">
            <Link to={`/extract/${r.id}`} className="flex-1 min-w-0 py-2.5 pl-3 pr-2">
              <div className="flex items-center gap-1.5 min-w-0">
                {schemaName && <span className="text-xs font-medium truncate">{schemaName}</span>}
                <Badge variant="outline" className="text-[10px] font-normal shrink-0">{r.extractionMethod}</Badge>
                <Badge
                  variant={r.status === 'completed' ? 'default' : r.status === 'pending' ? 'secondary' : 'destructive'}
                  className="text-[10px] shrink-0">
                  {isPending && <Loader2 className="h-2.5 w-2.5 mr-1 animate-spin" />}
                  {r.status}
                </Badge>
                <span className="text-[11px] text-muted-foreground ml-auto shrink-0">{formatDate(r.createdAt)}</span>
              </div>
            </Link>
            {!isPending && (
              <>
                <button aria-label="Export as CSV"
                  className="shrink-0 px-2 py-2 text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 transition-opacity disabled:cursor-not-allowed"
                  disabled={exportingId === r.id}
                  onClick={(e) => void handleExport(e, r.id)}>
                  <Download className="h-3.5 w-3.5" />
                </button>
                <button aria-label="Delete extraction run"
                  className="shrink-0 px-2 py-2 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => handleDelete(e, r.id)}>
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </>
            )}
          </div>
        )
      })}
    </div>
  )
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  const diffMins = Math.floor((Date.now() - date.getTime()) / 60000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
npx --prefix frontend vitest run src/components/extraction/ExtractionHistory.test.tsx
```
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/extraction/ExtractionHistory.tsx frontend/src/components/extraction/ExtractionHistory.test.tsx
git commit -m "feat(extract): simplify ExtractionHistory to flat nav list"
```

---

## Task 5: Add provenance props to `ExtractionResultViewer` + fix navigate bug

Add three optional props (`selectedBlockId`, `onBlockSelect`, `onPageSelect`) and fix the broken navigate call in the transform Apply handler (`/extraction?resultId=...` → `/extract/${derived.id}`).

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionResultViewer.tsx`
- Modify: `frontend/src/components/extraction/ExtractionResultViewer.test.tsx`

**Interfaces:**
- New optional props added to `ExtractionResultViewerProps`:
  ```ts
  selectedBlockId?: string | null
  onBlockSelect?: (blockId: string) => void
  onPageSelect?: (pageIndex: number) => void
  ```

- [ ] **Step 1: Fix the navigate bug**

In `frontend/src/components/extraction/ExtractionResultViewer.tsx`, find the `handleApply` function (around line 458). Change:

```ts
navigate(`/extraction?resultId=${derived.id}`)
```
to:
```ts
navigate(`/extract/${derived.id}`)
```

- [ ] **Step 2: Add the three optional props to the interface**

Find `interface ExtractionResultViewerProps` and add after `availableResults?`:

```ts
selectedBlockId?: string | null
onBlockSelect?: (blockId: string) => void
onPageSelect?: (pageIndex: number) => void
```

Destructure in the function signature:
```ts
export function ExtractionResultViewer({
  result, isLoading, schemaName, projectId, availableResults = [],
  selectedBlockId, onBlockSelect, onPageSelect,
}: ExtractionResultViewerProps)
```

- [ ] **Step 3: Wire `onPageSelect` to chunk rows in `ChunkDetailsPanel`**

`ChunkDetailsPanel` is an internal component in the same file. Add `onPageSelect` as a prop and call it when a chunk row is clicked:

```ts
// Update ChunkDetailsPanel signature:
function ChunkDetailsPanel({ chunks, onPageSelect }: {
  chunks: ChunkDetail[]
  onPageSelect?: (pageIndex: number) => void
}) {
```

In the chunk button `onClick`:
```tsx
onClick={() => {
  setSelectedIndex(i)
  if (onPageSelect && c.pageIndices.length > 0) {
    onPageSelect(c.pageIndices[0])
  }
}}
```

Pass `onPageSelect` when rendering `ChunkDetailsPanel`:
```tsx
<ChunkDetailsPanel chunks={chunks} onPageSelect={onPageSelect} />
```

- [ ] **Step 4: Write a test for the navigate fix and new props**

Add to `ExtractionResultViewer.test.tsx`:

```ts
it('chunk click fires onPageSelect with first page index', async () => {
  // This test verifies the onPageSelect prop is called.
  // Find the existing test file pattern and add a test that passes a mock
  // onPageSelect, renders with a completed result that has chunks in
  // extractionMetadata, and clicks a chunk row — then asserts the mock was called.
  // Minimal implementation: render with onPageSelect spy, open Chunk Details,
  // click a chunk row, assert spy called with correct pageIndex.
})
```

Look at the existing `ExtractionResultViewer.test.tsx` for the mock result pattern and add the test following that pattern.

- [ ] **Step 5: Lint check**

```bash
npx --prefix frontend npm run lint -- --max-warnings 0
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/extraction/ExtractionResultViewer.tsx frontend/src/components/extraction/ExtractionResultViewer.test.tsx
git commit -m "fix(extract): fix transform navigate path; add provenance props to ExtractionResultViewer"
```

---

## Task 6: Refactor `ExtractionPage` main page

Replace `DocumentSelector` with `DocumentPickerPanel`, remove `ExtractionForm` and all result-expansion state, add a "New Run" button, pass simplified props to `ExtractionHistory`.

**Files:**
- Modify: `frontend/src/pages/ExtractionPage.tsx`

**Interfaces:**
- Consumes: `DocumentPickerPanel` (Task 3), `ExtractionHistory` simplified (Task 4), `useDocuments`, `useFolders`, `useExtractionSchemas`, `useExtractionResults` (for `results`, `isLoading`, `deleteResult` only)

- [ ] **Step 1: Rewrite `ExtractionPage.tsx`**

```tsx
// frontend/src/pages/ExtractionPage.tsx
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useFolders } from '@/hooks/useFolders'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import { useExtractionResults } from '@/hooks/useExtractionResults'
import type { ExtractionSchema, ExtractionSchemaCreate, ExtractionSchemaUpdate } from '@/types/extraction'
import type { Document as AppDocument, DocumentUpload } from '@/types/document'
import { DocumentPickerPanel } from '@/components/shared/DocumentPickerPanel'
import { ExtractionHistory } from '@/components/extraction/ExtractionHistory'
import { SchemaManager } from '@/components/extraction/SchemaManager'
import { ExtractionSchemaEditor } from '@/components/extraction/ExtractionSchemaEditor'
import { DocumentUploadDialog } from '@/components/documents/DocumentUploadDialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { FileSearch, Plus } from 'lucide-react'
import { toast } from 'sonner'
import * as extractionApi from '@/api/extraction'
import { exportResultToCsv } from '@/lib/exportCsv'

export default function ExtractionPage(): JSX.Element {
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    searchParams.get('documentId'),
  )
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [schemaEditorOpen, setSchemaEditorOpen] = useState(false)
  const [editingSchema, setEditingSchema] = useState<ExtractionSchema | null>(null)

  const { documents, isLoading: documentsLoading, uploadDocument } = useDocuments(projectId, undefined, null)
  const { folders } = useFolders(projectId)
  const { schemas, error: schemasError, createSchema, updateSchema, deleteSchema } = useExtractionSchemas(projectId)
  const { results, isLoading: resultsLoading, deleteResult } = useExtractionResults(selectedDocumentId)

  const handleSelectDocument = (docId: string) => {
    setSelectedDocumentId(docId)
    setSearchParams((prev) => { const next = new URLSearchParams(prev); next.set('documentId', docId); return next })
  }

  const handleNewRun = () => {
    if (!selectedDocumentId) return
    navigate(`/extract/new?documentId=${selectedDocumentId}`, {
      state: { documentTitle: selectedDocument?.title },
    })
  }

  const handleCreateSchema = () => { setEditingSchema(null); setSchemaEditorOpen(true) }
  const handleEditSchema = (schema: ExtractionSchema) => { setEditingSchema(schema); setSchemaEditorOpen(true) }

  const handleDeleteSchema = async (schemaId: string) => {
    try { await deleteSchema(schemaId); toast.success('Schema deleted') }
    catch (err) { toast.error('Failed to delete schema', { description: err instanceof Error ? err.message : undefined }) }
  }

  const handleSaveSchema = async (data: ExtractionSchemaCreate | ExtractionSchemaUpdate) => {
    try {
      if (editingSchema) { await updateSchema(editingSchema.id, data as ExtractionSchemaUpdate); toast.success('Schema updated') }
      else { await createSchema(data as ExtractionSchemaCreate); toast.success('Schema created') }
    } catch (err) { toast.error('Failed to save schema', { description: err instanceof Error ? err.message : undefined }); throw err }
  }

  const handleExportResult = async (resultId: string) => {
    try {
      const result = await extractionApi.getExtractionResult(resultId)
      if (!result.structuredData || Object.keys(result.structuredData).length === 0) return
      const schema = schemas?.find((s) => s.id === result.extractionSchemaId)
      exportResultToCsv(result.structuredData, `${schema?.name ?? 'extraction'}_${resultId.slice(0, 8)}.csv`)
    } catch { toast.error('Failed to fetch result for export') }
  }

  const handleUpload = async (data: DocumentUpload): Promise<AppDocument> => {
    const newDoc = await uploadDocument(data)
    toast.success('Document uploaded')
    handleSelectDocument(newDoc.id)
    return newDoc
  }

  if (!currentProject) {
    return <div className="p-6"><Alert><AlertDescription>Loading project...</AlertDescription></Alert></div>
  }

  const selectedDocument = documents.find((d) => d.id === selectedDocumentId)

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
      <div className="flex items-center justify-between px-6 py-3 border-b shrink-0">
        <div>
          <h1 className="text-lg font-semibold">Extract</h1>
          <p className="text-xs text-muted-foreground">{currentProject.name}</p>
        </div>
      </div>

      {schemasError && (
        <div className="px-6 pt-3 shrink-0">
          <Alert variant="destructive"><AlertDescription>{schemasError}</AlertDescription></Alert>
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        <div className="w-72 border-r shrink-0 flex flex-col">
          <DocumentPickerPanel
            documents={documents}
            folders={folders}
            isLoading={documentsLoading}
            selectedDocumentId={selectedDocumentId}
            onSelect={handleSelectDocument}
            onUploadClick={() => setUploadDialogOpen(true)}
          />
        </div>

        <div className="flex-1 overflow-y-auto">
          {!selectedDocumentId ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <FileSearch className="h-12 w-12 text-muted-foreground/40 mb-4" />
              <h2 className="text-lg font-medium text-muted-foreground">Select a document to get started</h2>
              <p className="text-sm text-muted-foreground/70 mt-1 max-w-sm">
                Choose a document from the list, or upload a new one to begin extracting structured data.
              </p>
            </div>
          ) : (
            <div className="p-6 space-y-6 max-w-3xl">
              <SchemaManager schemas={schemas} onEdit={handleEditSchema} onDelete={handleDeleteSchema} onCreate={handleCreateSchema} />
              <Separator />
              {selectedDocument && (
                <div className="flex items-center gap-3">
                  <h2 className="text-base font-medium truncate">{selectedDocument.title}</h2>
                  <Badge variant={selectedDocument.status === 'ready' ? 'outline' : selectedDocument.status === 'processing' ? 'secondary' : 'destructive'} className="shrink-0 text-xs">
                    {selectedDocument.status}
                  </Badge>
                </div>
              )}
              <Button size="sm" onClick={handleNewRun} disabled={selectedDocument?.status !== 'ready'}>
                <Plus className="h-4 w-4 mr-1.5" />New Run
              </Button>
              <Separator />
              <div>
                <h3 className="text-sm font-medium mb-3">
                  Previous Extractions
                  {results.length > 0 && <span className="text-muted-foreground font-normal ml-1.5">({results.length})</span>}
                </h3>
                <ExtractionHistory
                  results={results}
                  isLoading={resultsLoading}
                  schemas={schemas}
                  onDeleteResult={deleteResult}
                  onExportResult={handleExportResult}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      <ExtractionSchemaEditor open={schemaEditorOpen} onOpenChange={setSchemaEditorOpen}
        schema={editingSchema} onSave={handleSaveSchema} />
      <DocumentUploadDialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}
        onUpload={handleUpload} projectId={projectId ?? ''} documents={documents} folders={folders} />
    </div>
  )
}
```

- [ ] **Step 2: Lint and build check**

```bash
npx --prefix frontend npm run lint -- --max-warnings 0
npx --prefix frontend npm run build
```

Expected: no errors. If TypeScript complains about `useDocuments` or `DocumentUploadDialog` props, check their interfaces — `useDocuments` accepts an optional `folderId` third param; pass `null` for "all folders" (the page now lets `DocumentPickerPanel` own folder filter state, so the page always fetches all docs and the panel filters locally).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ExtractionPage.tsx
git commit -m "feat(extract): refactor ExtractionPage to use DocumentPickerPanel and simplified history"
```

---

## Task 7: `NewExtractionRunPage`

Dedicated page for configuring and submitting an extraction run. Contains the state and UI previously in `ExtractionForm.tsx` (parse config + extraction config), restructured into shadcn `Card` sections. Uses `useExtractionSubmit` to run and navigate to the result detail page. After this task, `ExtractionForm.tsx` and its test are deleted.

**Files:**
- Create: `frontend/src/pages/NewExtractionRunPage.tsx`
- Delete: `frontend/src/components/extraction/ExtractionForm.tsx`
- Delete: `frontend/src/components/extraction/ExtractionForm.test.tsx`

**Interfaces:**
- Consumes: `useExtractionSubmit` (Task 1), `useExtractionSchemas`, `useParseRuns`, existing components: `ParseMethodSelector`, `ExtractionSchemaEditor`, `PromptConfigEditor`
- URL: `/extract/new?documentId=<id>`, state: `{ documentTitle?: string }`

- [ ] **Step 1: Create `NewExtractionRunPage.tsx`**

The page lifts all state from `ExtractionForm.tsx`. Copy its state variables and `handleRun` logic directly — the only changes are: (a) card wrapping, (b) the submit handler calls `useExtractionSubmit.submit` and navigates to `/extract/${resultId}`, (c) no internal "Run" button — submit is at page bottom.

```tsx
// frontend/src/pages/NewExtractionRunPage.tsx
import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useLocation } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import { useExtractionSubmit } from '@/hooks/useExtractionSubmit'
import { useParseRuns } from '@/hooks/useParseRuns'
import { usePromptConfig } from '@/hooks/usePromptConfig'
import type { ExtractionSchema, ExtractionSchemaCreate, ExtractionSchemaUpdate, ExtractorInfo, ChunkingConfig } from '@/types/extraction'
import type { ParseConfig } from '@/types/parsing'
import { getLlmDefaults, listExtractors } from '@/api/extraction'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { ParseMethodSelector } from '@/components/documents/ParseMethodSelector'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
import { ExtractionSchemaEditor } from '@/components/extraction/ExtractionSchemaEditor'
import { ChevronLeft, ChevronDown, Loader2, Pencil } from 'lucide-react'
import { toast } from 'sonner'

const REPRESENTATION_KIND = 'extract_rich'

export function NewExtractionRunPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const documentId = searchParams.get('documentId') ?? ''
  const documentTitle = (location.state as { documentTitle?: string } | null)?.documentTitle

  // Guard: redirect if no documentId
  useEffect(() => {
    if (!documentId) navigate('/extract', { replace: true })
  }, [documentId, navigate])

  const { schemas, createSchema, updateSchema } = useExtractionSchemas(projectId)
  const { parseRuns } = useParseRuns(documentId || null)
  const { phase, phaseError, submit } = useExtractionSubmit()

  const [extractors, setExtractors] = useState<ExtractorInfo[]>([])
  const [schemaEditorOpen, setSchemaEditorOpen] = useState(false)
  const [editingSchema, setEditingSchema] = useState<ExtractionSchema | null>(null)

  // Parse config — seeded from latest viable parse run
  const latestViableRun = parseRuns.find((r) => r.status === 'succeeded' || r.status === 'partial')
  const [parserType, setParserType] = useState('simple')
  const [parserConfig, setParserConfig] = useState<ParseConfig>({})

  useEffect(() => {
    if (!latestViableRun) return
    setParserType(latestViableRun.parser ?? 'simple')
    const cfg = { ...(latestViableRun.config as Record<string, unknown> ?? {}) }
    delete cfg['parser']
    setParserConfig(cfg as ParseConfig)
  }, [latestViableRun?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Extraction config
  const [schemaId, setSchemaId] = useState('')
  const [extractionMethod, setExtractionMethod] = useState('')
  // LlamaExtract options
  const [extractionMode, setExtractionMode] = useState('MULTIMODAL')
  const [citeSources, setCiteSources] = useState(false)
  const [useReasoning, setUseReasoning] = useState(false)
  const [pageRange, setPageRange] = useState('')
  const [extractionTarget, setExtractionTarget] = useState('PER_DOC')
  const [confidenceScores, setConfidenceScores] = useState(false)
  // LLM options
  const { promptConfig, setPromptConfig, setProvider } = usePromptConfig()
  const [userPromptTemplate, setUserPromptTemplate] = useState('')
  const [structuredOutputMode, setStructuredOutputMode] = useState('json_schema')
  const [injectBlockIds, setInjectBlockIds] = useState(false)
  const [chunkStrategy, setChunkStrategy] = useState<'none' | 'token_budget_pages'>('none')
  const [maxInputTokens, setMaxInputTokens] = useState('8000')
  const [pageOverlap, setPageOverlap] = useState('0')
  const [dedupeKey, setDedupeKey] = useState('')
  const [maxTokensPerMinute, setMaxTokensPerMinute] = useState('')
  const [timeoutMinutes, setTimeoutMinutes] = useState('')
  const [citationLevel, setCitationLevel] = useState<'auto' | 'full' | 'page_only' | 'off'>('auto')

  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listExtractors().then(setExtractors).catch(() => {})
  }, [])

  useEffect(() => {
    if (schemas.length > 0 && !schemaId) setSchemaId(schemas[0].id)
  }, [schemas, schemaId])

  useEffect(() => {
    if (extractors.length > 0 && !extractionMethod) {
      const first = extractors.find((e) => e.configured)
      setExtractionMethod(first?.extractionMethod ?? extractors[0].extractionMethod)
    }
  }, [extractors, extractionMethod])

  useEffect(() => {
    if (extractionMethod !== 'llm') return
    let cancelled = false
    getLlmDefaults().then((d) => {
      if (cancelled) return
      setPromptConfig((prev) => ({ ...prev, systemPrompt: prev.systemPrompt || d.systemPrompt }))
      setUserPromptTemplate((prev) => prev || d.userPromptTemplate)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [extractionMethod, setPromptConfig])

  const handleSaveSchema = async (data: ExtractionSchemaCreate | ExtractionSchemaUpdate) => {
    try {
      if (editingSchema) { await updateSchema(editingSchema.id, data as ExtractionSchemaUpdate); toast.success('Schema updated') }
      else { const s = await createSchema(data as ExtractionSchemaCreate); setSchemaId(s.id); toast.success('Schema created') }
    } catch (err) { toast.error('Failed to save schema', { description: err instanceof Error ? err.message : undefined }); throw err }
  }

  const handleSubmit = async () => {
    setError(null)
    if (!schemaId) { setError('Please select a schema'); return }
    if (!extractionMethod) { setError('No extraction method available'); return }

    const parseConfig = { parser: parserType, config: parserConfig as Record<string, unknown>, representationKind: REPRESENTATION_KIND }

    let extractionConfig: Parameters<typeof submit>[2]['extractionConfig']

    if (extractionMethod === 'llamaextract') {
      const config: Record<string, unknown> = { extraction_mode: extractionMode, extraction_target: extractionTarget }
      if (citeSources) config.cite_sources = true
      if (useReasoning) config.use_reasoning = true
      if (pageRange.trim()) config.page_range = pageRange.trim()
      if (confidenceScores) config.confidence_scores = true
      extractionConfig = { extractionSchemaId: schemaId, extractionMethod, config }
    } else if (extractionMethod === 'llm') {
      let chunking: ChunkingConfig | undefined
      if (chunkStrategy !== 'none') {
        const cfg: Record<string, unknown> = {}
        const max = parseInt(maxInputTokens, 10)
        if (!Number.isNaN(max)) cfg.maxInputTokens = max
        const overlap = parseInt(pageOverlap, 10)
        if (!Number.isNaN(overlap) && overlap > 0) cfg.pageOverlap = overlap
        if (dedupeKey.trim()) cfg.dedupeKey = dedupeKey.trim()
        const tpm = parseInt(maxTokensPerMinute, 10)
        chunking = { strategy: chunkStrategy, config: cfg, citationLevel, ...(!Number.isNaN(tpm) && tpm > 0 ? { maxTokensPerMinute: tpm } : {}) }
      } else if (citationLevel !== 'auto') {
        chunking = { strategy: 'none', citationLevel }
      }
      const tm = parseInt(timeoutMinutes, 10)
      extractionConfig = {
        extractionSchemaId: schemaId, extractionMethod,
        config: { structured_output_mode: structuredOutputMode, inject_block_ids: injectBlockIds },
        llmConfig: promptConfig,
        userPromptTemplate: userPromptTemplate.trim() || undefined,
        ...(chunking ? { chunking } : {}),
        ...(!Number.isNaN(tm) && tm >= 1 ? { timeoutMinutes: Math.min(tm, 120) } : {}),
      }
    } else {
      extractionConfig = { extractionSchemaId: schemaId, extractionMethod, config: {} }
    }

    const resultId = await submit(documentId, parseRuns, { parseConfig, extractionConfig })
    if (resultId) {
      navigate(`/extract/${resultId}`)
    }
  }

  const isSubmitting = phase === 'parsing' || phase === 'extracting'
  const backHref = `/extract${documentId ? `?documentId=${documentId}` : ''}`
  const selectedExtractor = extractors.find((e) => e.extractionMethod === extractionMethod)
  const isConfigured = selectedExtractor?.configured ?? true

  return (
    <div className="max-w-2xl mx-auto py-8 px-6 space-y-6">
      <Button variant="ghost" size="sm" asChild className="-ml-2">
        <Link to={backHref}><ChevronLeft className="h-4 w-4 mr-1" />Back</Link>
      </Button>

      <div>
        <h1 className="text-2xl font-semibold">New extraction run</h1>
        {documentTitle && <p className="text-sm text-muted-foreground mt-1">{documentTitle}</p>}
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Parse configuration</CardTitle></CardHeader>
        <CardContent>
          <ParseMethodSelector parserType={parserType} config={parserConfig}
            onParserTypeChange={setParserType} onConfigChange={setParserConfig} disabled={isSubmitting} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Extraction</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {/* Schema selector + edit shortcut */}
          <div className="space-y-1.5">
            <Label className="text-xs">Schema</Label>
            <div className="flex items-center gap-1">
              <Select value={schemaId} onValueChange={setSchemaId}>
                <SelectTrigger className="h-9"><SelectValue placeholder="Select schema" /></SelectTrigger>
                <SelectContent>
                  {schemas.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
                </SelectContent>
              </Select>
              {schemaId && (
                <Button variant="ghost" size="icon" className="h-9 w-9 shrink-0" title="Edit selected schema"
                  onClick={() => { const s = schemas.find((x) => x.id === schemaId); if (s) { setEditingSchema(s); setSchemaEditorOpen(true) } }}>
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
            <button className="text-xs text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
              onClick={() => { setEditingSchema(null); setSchemaEditorOpen(true) }}>
              + New schema
            </button>
          </div>

          {/* Method selector */}
          {extractors.length > 1 && (
            <div className="space-y-1.5">
              <Label className="text-xs">Method</Label>
              <Select value={extractionMethod} onValueChange={setExtractionMethod}>
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {extractors.map((e) => (
                    <SelectItem key={e.extractionMethod} value={e.extractionMethod} disabled={!e.configured}>
                      {e.name}{!e.configured ? ' (not configured)' : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Method-specific config — copy blocks from ExtractionForm.tsx verbatim */}
          {/* LlamaExtract block: extractionMethod === 'llamaextract' */}
          {extractionMethod === 'llamaextract' && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Mode</Label>
                  <Select value={extractionMode} onValueChange={setExtractionMode}>
                    <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="FAST">Fast</SelectItem>
                      <SelectItem value="BALANCED">Balanced</SelectItem>
                      <SelectItem value="MULTIMODAL">Multimodal</SelectItem>
                      <SelectItem value="PREMIUM">Premium</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Page Range</Label>
                  <Input value={pageRange} onChange={(e) => setPageRange(e.target.value)} placeholder="e.g. 1-5" className="h-9" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Target</Label>
                  <Select value={extractionTarget} onValueChange={setExtractionTarget}>
                    <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="PER_DOC">Per Document</SelectItem>
                      <SelectItem value="PER_PAGE">Per Page</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-end pb-2">
                  <div className="flex items-center space-x-2">
                    <Checkbox id="confidence-scores" checked={confidenceScores} onCheckedChange={(c) => setConfidenceScores(c === true)} />
                    <Label htmlFor="confidence-scores" className="text-xs font-normal">Confidence Scores</Label>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center space-x-2">
                  <Checkbox id="cite-sources" checked={citeSources} onCheckedChange={(c) => setCiteSources(c === true)} />
                  <Label htmlFor="cite-sources" className="text-xs font-normal">Citations</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox id="use-reasoning" checked={useReasoning} onCheckedChange={(c) => setUseReasoning(c === true)} />
                  <Label htmlFor="use-reasoning" className="text-xs font-normal">Reasoning</Label>
                </div>
              </div>
            </>
          )}

          {/* LLM block: extractionMethod === 'llm' — copy verbatim from ExtractionForm.tsx */}
          {extractionMethod === 'llm' && (
            <div className="space-y-4">
              <PromptConfigEditor value={promptConfig} onChange={setPromptConfig} onProviderChange={setProvider} capabilities={{ thinking: true }} />
              <div className="space-y-1.5">
                <Label className="text-xs">User prompt template</Label>
                <p className="text-[11px] text-muted-foreground">Variables: <code>{'{schema_json}'}</code> and <code>{'{document_context}'}</code>. Leave blank to use the default.</p>
                <Textarea value={userPromptTemplate} onChange={(e) => setUserPromptTemplate(e.target.value)} className="font-mono text-xs min-h-[80px]" placeholder="Extract structured data from the following document..." />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Output mode</Label>
                  <Select value={structuredOutputMode} onValueChange={setStructuredOutputMode}>
                    <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="json_schema">JSON Schema</SelectItem>
                      <SelectItem value="json_mode">JSON Mode</SelectItem>
                      <SelectItem value="prompt_only">Prompt Only</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-end pb-2">
                  <div className="flex items-center space-x-2">
                    <Checkbox id="inject-block-ids" checked={injectBlockIds} onCheckedChange={(v) => setInjectBlockIds(v === true)} />
                    <Label htmlFor="inject-block-ids" className="text-xs font-normal">Inject block IDs</Label>
                  </div>
                </div>
              </div>
              <Collapsible>
                <CollapsibleTrigger asChild>
                  <Button variant="ghost" size="sm" className="w-full justify-between px-0">
                    <span className="text-xs font-medium">Large document handling</span>
                    <ChevronDown className="h-4 w-4" />
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className="space-y-3 pt-2">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label className="text-xs">Chunking</Label>
                      <Select value={chunkStrategy} onValueChange={(v) => setChunkStrategy(v as 'none' | 'token_budget_pages')}>
                        <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">None (single-shot)</SelectItem>
                          <SelectItem value="token_budget_pages">Token-budgeted pages</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs">Citation detail</Label>
                      <Select value={citationLevel} onValueChange={(v) => setCitationLevel(v as typeof citationLevel)}>
                        <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="auto">Auto</SelectItem>
                          <SelectItem value="full">Full</SelectItem>
                          <SelectItem value="page_only">Page only</SelectItem>
                          <SelectItem value="off">Off</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  {chunkStrategy === 'token_budget_pages' && (
                    <>
                      <div className="grid grid-cols-3 gap-3">
                        <div className="space-y-1.5"><Label className="text-xs">Max input tokens</Label><Input type="number" value={maxInputTokens} onChange={(e) => setMaxInputTokens(e.target.value)} className="h-9" /></div>
                        <div className="space-y-1.5"><Label className="text-xs">Page overlap</Label><Input type="number" value={pageOverlap} onChange={(e) => setPageOverlap(e.target.value)} className="h-9" /></div>
                        <div className="space-y-1.5"><Label className="text-xs">Dedupe key</Label><Input value={dedupeKey} onChange={(e) => setDedupeKey(e.target.value)} placeholder="e.g. sku" className="h-9" /></div>
                      </div>
                      <div className="space-y-1.5">
                        <Label className="text-xs">Rate limit (TPM)</Label>
                        <Input type="number" value={maxTokensPerMinute} onChange={(e) => setMaxTokensPerMinute(e.target.value)} placeholder="e.g. 30000" className="h-9" />
                      </div>
                    </>
                  )}
                  <div className="space-y-1.5">
                    <Label className="text-xs">Timeout (minutes)</Label>
                    <Input type="number" value={timeoutMinutes} onChange={(e) => setTimeoutMinutes(e.target.value)} placeholder="10" min={1} max={120} className="h-9" />
                  </div>
                </CollapsibleContent>
              </Collapsible>
            </div>
          )}
        </CardContent>
      </Card>

      {(error || phaseError) && (
        <Alert variant="destructive">
          <AlertDescription>{error ?? phaseError}</AlertDescription>
        </Alert>
      )}

      {!isConfigured && (
        <p className="text-xs text-amber-600">{selectedExtractor?.name ?? 'This extractor'} is not configured. Contact your administrator.</p>
      )}

      <div className="flex gap-3 pt-2">
        <Button onClick={handleSubmit} disabled={isSubmitting || !schemaId || !isConfigured}>
          {isSubmitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
          {phase === 'parsing' ? 'Parsing document…' : phase === 'extracting' ? 'Starting extraction…' : 'Start extraction'}
        </Button>
        <Button variant="outline" asChild><Link to={backHref}>Cancel</Link></Button>
      </div>

      <ExtractionSchemaEditor open={schemaEditorOpen} onOpenChange={setSchemaEditorOpen}
        schema={editingSchema} onSave={handleSaveSchema} />
    </div>
  )
}
```

- [ ] **Step 2: Delete `ExtractionForm`**

```bash
rm frontend/src/components/extraction/ExtractionForm.tsx
rm frontend/src/components/extraction/ExtractionForm.test.tsx
```

- [ ] **Step 3: Lint and build**

```bash
npx --prefix frontend npm run lint -- --max-warnings 0
npx --prefix frontend npm run build
```

Fix any TypeScript errors (unused imports in `ExtractionPage.tsx` from the removed `ExtractionForm`).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/NewExtractionRunPage.tsx
git add -u frontend/src/components/extraction/ExtractionForm.tsx frontend/src/components/extraction/ExtractionForm.test.tsx
git commit -m "feat(extract): add NewExtractionRunPage, delete ExtractionForm"
```

---

## Task 8: `ExtractionResultDetailPage`

Split-panel page: PDF viewer on the left (loaded from `sourceParseRunId`), `ExtractionResultViewer` on the right. Three provenance cases: block-level highlighting, page-scroll only, or no PDF panel.

**Files:**
- Create: `frontend/src/pages/ExtractionResultDetailPage.tsx`

**Interfaces:**
- Consumes: `useExtractionResultDetail` (Task 2), `ExtractionResultViewer` with new props (Task 5), `DocumentPdfViewer`, `getParsedDocument`
- URL: `/extract/:resultId`

- [ ] **Step 1: Create `ExtractionResultDetailPage.tsx`**

```tsx
// frontend/src/pages/ExtractionResultDetailPage.tsx
import { useState, useEffect, useMemo, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useExtractionResultDetail } from '@/hooks/useExtractionResultDetail'
import { ExtractionResultViewer } from '@/components/extraction/ExtractionResultViewer'
import { DocumentPdfViewer } from '@/components/parse-runs/DocumentPdfViewer'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { getParsedDocument } from '@/api/parseRuns'
import type { Block } from '@/types/cdm'
import { ChevronLeft, ExternalLink, RotateCw } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

export function ExtractionResultDetailPage() {
  const { resultId } = useParams<{ resultId: string }>()
  const navigate = useNavigate()
  const { result, isLoading, error } = useExtractionResultDetail(resultId ?? null)

  const [parseBlocks, setParseBlocks] = useState<Block[]>([])
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null)
  const [selectedPageIndex, setSelectedPageIndex] = useState<number | null>(null)
  const pdfContainerRef = useRef<HTMLDivElement>(null)

  // Load parse blocks when sourceParseRunId is available
  useEffect(() => {
    if (!result?.sourceParseRunId) { setParseBlocks([]); return }
    getParsedDocument(result.sourceParseRunId)
      .then((doc) => setParseBlocks(doc.content?.blocks ?? []))
      .catch(() => setParseBlocks([]))
  }, [result?.sourceParseRunId])

  // Scroll PDF to page when selectedPageIndex changes
  useEffect(() => {
    if (selectedPageIndex === null) return
    const el = pdfContainerRef.current?.querySelector(`[data-page-index="${selectedPageIndex}"]`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [selectedPageIndex])

  // Determine provenance case
  const firstCitation = result?.citations?.[0] as Record<string, unknown> | undefined
  const hasBlockCitations = !!(result?.sourceParseRunId && firstCitation && 'block_id' in firstCitation)
  const hasPageProvenance = !!(result?.sourceParseRunId && (
    (result.citations && result.citations.length > 0) ||
    (result.extractionMetadata as Record<string, unknown> | null)?.['chunks']
  ))
  const showPdf = !!(result?.sourceParseRunId) && result?.config && (result.config as Record<string, unknown>)['citation_level'] !== 'off'

  // Build blockColors for block-level case: highlight all cited blocks in accent colour
  const blockColors = useMemo<Map<string, string>>(() => {
    if (!hasBlockCitations || !result?.citations) return new Map()
    const map = new Map<string, string>()
    for (const c of result.citations as Record<string, unknown>[]) {
      const blockId = c['block_id'] as string | undefined
      if (blockId) map.set(blockId, 'hsl(221 83% 53%)')
    }
    return map
  }, [hasBlockCitations, result?.citations])

  const handlePageSelect = (pageIndex: number) => {
    setSelectedPageIndex(pageIndex)
  }

  const handleBlockSelect = (blockId: string) => {
    setSelectedBlockId(blockId)
    // Scroll PDF to the block's page
    const block = parseBlocks.find((b) => b.id === blockId)
    if (block) setSelectedPageIndex(block.page_index ?? null)
  }

  const handleRerun = () => {
    if (!result) return
    navigate(`/extract/new?documentId=${result.documentId}`, {
      state: {
        documentTitle: undefined,
        defaults: { config: result.config, extractionMethod: result.extractionMethod },
      },
    })
  }

  if (isLoading) {
    return (
      <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
        <div className="px-4 py-2 border-b shrink-0"><Skeleton className="h-8 w-40" /></div>
        <div className="flex flex-1 min-h-0"><Skeleton className="flex-1 m-4" /></div>
      </div>
    )
  }

  if (error || !result) {
    return (
      <div className="-m-6 p-6">
        <Alert variant="destructive">
          <AlertDescription>{error ?? 'Result not found.'}</AlertDescription>
        </Alert>
        <Button variant="ghost" size="sm" className="mt-4" asChild>
          <Link to="/extract"><ChevronLeft className="h-4 w-4 mr-1" />Back to Extract</Link>
        </Button>
      </div>
    )
  }

  const statusVariant = result.status === 'completed' ? 'default' : result.status === 'pending' ? 'secondary' : 'destructive'

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="px-4 py-2 border-b shrink-0 flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/extract?documentId=${result.documentId}`}>
            <ChevronLeft className="h-4 w-4 mr-1" />Back
          </Link>
        </Button>
        <Badge variant={statusVariant}>{result.status}</Badge>
        <Badge variant="outline">{result.extractionMethod}</Badge>
        <span className="text-xs text-muted-foreground">
          {formatDistanceToNow(new Date(result.createdAt), { addSuffix: true })}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="ghost" size="sm" className="h-7 text-xs gap-1" asChild>
            <Link to={`/parse?documentId=${result.documentId}`} target="_blank">
              <ExternalLink className="h-3.5 w-3.5" />
              View document
            </Link>
          </Button>
          <Button variant="outline" size="sm" className="h-7 text-xs gap-1" onClick={handleRerun}>
            <RotateCw className="h-3.5 w-3.5" />
            Re-run
          </Button>
        </div>
      </div>

      {/* Body */}
      {showPdf ? (
        <div className="flex flex-1 min-h-0">
          {/* Left: PDF */}
          <div ref={pdfContainerRef} className="border-r overflow-hidden" style={{ flex: '0 0 55%' }}>
            <DocumentPdfViewer
              documentId={result.documentId}
              blocks={hasBlockCitations ? parseBlocks : []}
              blockColors={hasBlockCitations ? blockColors : undefined}
              selectedBlockId={selectedBlockId}
              onBlockSelect={hasBlockCitations ? setSelectedBlockId : () => {}}
            />
          </div>
          {/* Right: result viewer */}
          <div className="flex-1 overflow-y-auto p-4">
            <ExtractionResultViewer
              result={result}
              isLoading={false}
              selectedBlockId={selectedBlockId}
              onBlockSelect={hasBlockCitations ? handleBlockSelect : undefined}
              onPageSelect={hasPageProvenance && !hasBlockCitations ? handlePageSelect : undefined}
            />
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-3xl mx-auto">
            <ExtractionResultViewer result={result} isLoading={false} />
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Lint and build**

```bash
npx --prefix frontend npm run lint -- --max-warnings 0
npx --prefix frontend npm run build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ExtractionResultDetailPage.tsx
git commit -m "feat(extract): add ExtractionResultDetailPage with PDF provenance"
```

---

## Task 9: Wire routes in `App.tsx` + final verification

Register the two new routes, import the two new pages, and run the full test suite.

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add imports and routes**

In `frontend/src/App.tsx`, add imports after the existing extract/classify imports:

```ts
import { NewExtractionRunPage } from './pages/NewExtractionRunPage'
import { ExtractionResultDetailPage } from './pages/ExtractionResultDetailPage'
```

In the router children array, after the existing `extract` route:

```ts
{
  path: 'extract',
  element: <ExtractionPage />,
  handle: { breadcrumb: 'Extract' },
},
{
  path: 'extract/new',
  element: <NewExtractionRunPage />,
  handle: { breadcrumb: 'New Extraction Run' },
},
{
  path: 'extract/:resultId',
  element: <ExtractionResultDetailPage />,
  handle: { breadcrumb: 'Extraction Result' },
},
```

**Important:** `/extract/new` must appear before `/extract/:resultId` in the array so React Router doesn't treat `"new"` as a `resultId` param. React Router v6 uses specificity-based matching so order matters for same-level siblings.

- [ ] **Step 2: Lint and build**

```bash
npx --prefix frontend npm run lint -- --max-warnings 0
npx --prefix frontend npm run build
```

Expected: clean build.

- [ ] **Step 3: Run full test suite**

```bash
npx --prefix frontend vitest run
```

Fix any failures. Common issues:
- Tests importing `ExtractionForm` — update to use `NewExtractionRunPage` or remove if the test covered deleted behaviour
- Tests importing old `ExtractionHistory` props — update to new simplified interface

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(extract): register /extract/new and /extract/:resultId routes"
```

- [ ] **Step 5: Push branch**

```bash
git push -u origin feat/extract-page-redesign
```

---

## Manual Verification Checklist

After all tasks complete, verify in the browser:

- [ ] `/extract` — document picker shows folder dropdown + search + status badges; "New Run" button disabled for non-ready docs
- [ ] Selecting a document shows `SchemaManager` + history list; clicking a history row navigates to `/extract/:resultId`
- [ ] `/extract/new?documentId=<id>` — back link returns to `/extract?documentId=<id>`; parse card pre-populated from latest parse run; schema dropdown + edit pencil work; "New schema" opens modal; submit button shows parsing/extracting phases then navigates
- [ ] `/extract/:resultId` — header shows back link + "View document" + "Re-run"; result detail shown
  - With `sourceParseRunId` + block citations: PDF left, result right, clicking a block highlights it
  - With `sourceParseRunId` + page citations only: PDF scrolls to page on chunk click
  - Without `sourceParseRunId` (llamaextract): result fills full width, no PDF
- [ ] Re-run button on detail page navigates to `/extract/new` with document pre-selected
- [ ] Upload in picker uploads and auto-selects the new document
- [ ] Schema create/edit/delete still works on main page and new run page
