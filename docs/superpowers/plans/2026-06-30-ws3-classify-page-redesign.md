# WS3: Classify Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the three-page classify wizard (list page + wizard page + detail page) with a single-page layout: document picker on the left, run history strip at the top-right, and a results split (label viewer + document viewer with overlays) below — with a wide sheet for new-run configuration.

**Architecture:** Five tasks build bottom-up: (1) add `useDocumentClassificationRuns` hook; (2) `ClassificationRunHistory` strip; (3) `ClassificationRunDetail` split panel; (4) `ClassificationRunSheet` config sheet; (5) rewrite `ClassificationPage`, clean up routes, delete old pages. Tasks 2–4 depend on Task 1. Task 5 assembles them all. **Requires WS1 (`ClassificationConfig`) and WS2 (overlay-wired `ParsedDocumentViewer`) to be merged first.**

**Tech Stack:** React 18, TypeScript, React Router v6, shadcn/ui Sheet, Vitest + @testing-library/react

## Global Constraints

- WS1 and WS2 must be complete before starting this workstream
- Run tests: `npm --prefix frontend exec -- npx vitest run <path>`
- Run lint: `npm --prefix frontend run lint`
- Run build: `npm --prefix frontend run build`
- No backend changes
- Layout pattern mirrors `ExtractionPage`: `-m-6 flex flex-col h-[calc(100vh-3.5rem)]`
- `DocumentSelector` is imported from `@/components/extraction/DocumentSelector`
- `ParseMethodSelector` is imported from `@/components/documents/ParseMethodSelector`
- `ClassificationConfig` / `ClassificationConfigValue` from `@/components/classification/ClassificationConfig` (WS1)
- `ParsedDocumentViewer` from `@/components/documents/ParsedDocumentViewer` (overlay-wired, WS2)

---

### Task 1: Add useDocumentClassificationRuns hook

**Files:**
- Modify: `frontend/src/hooks/useClassificationRuns.ts`

**Interfaces:**
- Produces:
  ```typescript
  export function useDocumentClassificationRuns(documentId: string | null): {
    runs: ClassificationRun[]
    isLoading: boolean
    error: string | null
    refresh: () => void
    deleteRun: (runId: string) => Promise<void>
  }
  ```

- [ ] **Step 1: Append useDocumentClassificationRuns to useClassificationRuns.ts**

Open `frontend/src/hooks/useClassificationRuns.ts`. The file already exports `useClassificationRuns`, `useClassificationRunDetail`, and `useClassificationRunBlocks`. Append the following export at the bottom of the file:

```typescript
interface UseDocumentClassificationRunsReturn {
  runs: ClassificationRun[]
  isLoading: boolean
  error: string | null
  refresh: () => void
  deleteRun: (runId: string) => Promise<void>
}

export function useDocumentClassificationRuns(
  documentId: string | null,
): UseDocumentClassificationRunsReturn {
  const [runs, setRuns] = useState<ClassificationRun[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forcePolling, setForcePolling] = useState(false)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const forceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const fetchList = useCallback(async (id: string, silent = false) => {
    if (!silent) { setIsLoading(true); setError(null) }
    try {
      const data = await classificationApi.listDocumentClassificationRuns(id)
      setRuns(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch classification runs')
    } finally {
      if (!silent) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!documentId) { setRuns([]); stopPolling(); return }
    void fetchList(documentId)
  }, [documentId, fetchList, stopPolling])

  useEffect(() => {
    if (!documentId) return
    const hasActive = runs.some((r) => !isTerminal(r.status))
    if (!hasActive && !forcePolling) { stopPolling(); return }
    if (pollingRef.current !== null) return
    pollingRef.current = setInterval(() => void fetchList(documentId, true), POLL_MS)
    return () => stopPolling()
  }, [documentId, runs, fetchList, stopPolling, forcePolling])

  useEffect(() => () => stopPolling(), [stopPolling])

  const refresh = useCallback(() => {
    if (!documentId) return
    void fetchList(documentId, true)
    setForcePolling(true)
    if (forceTimerRef.current !== null) clearTimeout(forceTimerRef.current)
    forceTimerRef.current = setTimeout(() => {
      setForcePolling(false)
      forceTimerRef.current = null
    }, 30_000)
  }, [documentId, fetchList])

  const deleteRun = useCallback(async (runId: string) => {
    await classificationApi.deleteClassificationRun(runId)
    if (documentId) void fetchList(documentId, true)
  }, [documentId, fetchList])

  return { runs, isLoading, error, refresh, deleteRun }
}
```

Note: `POLL_MS`, `isTerminal`, `classificationApi`, `useState`, `useEffect`, `useCallback`, `useRef` are all already in scope from the top of the file. No new imports needed.

- [ ] **Step 2: Verify TypeScript compiles**

```
npm --prefix frontend run build 2>&1 | head -30
```

Expected: no errors.

- [ ] **Step 3: Commit**

```
git add frontend/src/hooks/useClassificationRuns.ts
git commit -m "feat(classify): add useDocumentClassificationRuns hook"
```

---

### Task 2: ClassificationRunHistory component

**Files:**
- Create: `frontend/src/components/classification/ClassificationRunHistory.tsx`

**Interfaces:**
- Consumes: `useDocumentClassificationRuns` from `@/hooks/useClassificationRuns`
- Props:
  ```typescript
  interface ClassificationRunHistoryProps {
    documentId: string
    selectedRunId: string | null
    onSelectRun: (runId: string) => void
    onNewRun: () => void
  }
  ```
- Auto-selects the most recent run when `selectedRunId` is null and runs load.

- [ ] **Step 1: Create ClassificationRunHistory.tsx**

Create `frontend/src/components/classification/ClassificationRunHistory.tsx`:

```typescript
import { useEffect } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ClassificationRunStatusBadge } from './ClassificationRunStatusBadge'
import { useDocumentClassificationRuns } from '@/hooks/useClassificationRuns'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

interface ClassificationRunHistoryProps {
  documentId: string
  selectedRunId: string | null
  onSelectRun: (runId: string) => void
  onNewRun: () => void
}

export function ClassificationRunHistory({
  documentId,
  selectedRunId,
  onSelectRun,
  onNewRun,
}: ClassificationRunHistoryProps) {
  const { runs, isLoading, error, deleteRun } = useDocumentClassificationRuns(documentId)

  // Auto-select the most recent run when the document changes and no run is selected
  useEffect(() => {
    if (runs.length > 0 && !selectedRunId) {
      onSelectRun(runs[0].id)
    }
  }, [runs, selectedRunId, onSelectRun])

  const handleDelete = async (e: React.MouseEvent, runId: string) => {
    e.stopPropagation()
    try {
      await deleteRun(runId)
      toast.success('Classification run deleted')
      if (selectedRunId === runId) {
        const remaining = runs.filter((r) => r.id !== runId)
        if (remaining.length > 0) onSelectRun(remaining[0].id)
      }
    } catch {
      toast.error('Failed to delete run')
    }
  }

  return (
    <div className="border-b shrink-0">
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/20">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Classification runs
        </span>
        <Button size="sm" variant="outline" className="h-7 text-xs" onClick={onNewRun}>
          <Plus className="h-3.5 w-3.5 mr-1" />
          New Run
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="m-2">
          <AlertDescription className="text-xs">{error}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="p-2 space-y-1">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      ) : runs.length === 0 ? (
        <div className="px-4 py-3 text-xs text-muted-foreground">
          No runs yet.{' '}
          <button className="underline hover:no-underline" onClick={onNewRun}>
            Start the first one.
          </button>
        </div>
      ) : (
        <div className="overflow-y-auto max-h-44">
          {runs.map((run) => {
            const isSelected = run.id === selectedRunId
            const modelSummary =
              run.classifierType === 'llm'
                ? `${run.classifierConfig.provider as string} / ${run.classifierConfig.model as string}`
                : run.classifierType
            return (
              <button
                key={run.id}
                onClick={() => onSelectRun(run.id)}
                className={cn(
                  'w-full text-left flex items-center gap-3 px-4 py-2.5 text-sm border-b last:border-0 hover:bg-muted/50 transition-colors',
                  isSelected && 'bg-muted border-l-2 border-l-primary',
                )}
              >
                <ClassificationRunStatusBadge status={run.status} />
                <span className="flex-1 truncate text-xs text-muted-foreground">
                  {run.labelsRequested.join(', ')}
                </span>
                <span className="text-xs text-muted-foreground shrink-0 hidden sm:block">
                  {modelSummary}
                </span>
                <span className="text-xs text-muted-foreground shrink-0">
                  {formatDistanceToNow(new Date(run.createdAt), { addSuffix: true })}
                </span>
                <button
                  aria-label="Delete run"
                  onClick={(e) => handleDelete(e, run.id)}
                  className="shrink-0 hover:text-destructive text-muted-foreground"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```
npm --prefix frontend run build 2>&1 | head -30
```

Expected: no errors.

- [ ] **Step 3: Commit**

```
git add frontend/src/components/classification/ClassificationRunHistory.tsx
git commit -m "feat(classify): add ClassificationRunHistory component"
```

---

### Task 3: ClassificationRunDetail component

**Files:**
- Create: `frontend/src/components/classification/ClassificationRunDetail.tsx`

**Interfaces:**
- Consumes:
  - `useClassificationRunDetail(runId)` → `{ run, isLoading, error }`
  - `useClassificationRunBlocks(runId)` → `{ blocks }`
  - `ClassificationResultsViewer` from `./ClassificationResultsViewer`
  - `ParsedDocumentViewer` (WS2, overlay-capable) from `@/components/documents/ParsedDocumentViewer`
- Props:
  ```typescript
  interface ClassificationRunDetailProps {
    runId: string
    documentId: string
    onRerun: (defaultValues: RerunDefaults) => void
  }
  // RerunDefaults exported so ClassificationPage can type sheetDefaultValues
  export interface RerunDefaults {
    labels: string[]
    classifierType: string
    classifierConfig: Record<string, unknown>
  }
  ```

- [ ] **Step 1: Create ClassificationRunDetail.tsx**

Create `frontend/src/components/classification/ClassificationRunDetail.tsx`:

```typescript
import { useState } from 'react'
import { RotateCw, PanelRightClose, PanelRightOpen } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { ClassificationRunStatusBadge } from './ClassificationRunStatusBadge'
import { ClassificationResultsViewer } from './ClassificationResultsViewer'
import { ParsedDocumentViewer } from '@/components/documents/ParsedDocumentViewer'
import { useClassificationRunDetail, useClassificationRunBlocks } from '@/hooks/useClassificationRuns'

export interface RerunDefaults {
  labels: string[]
  classifierType: string
  classifierConfig: Record<string, unknown>
}

interface ClassificationRunDetailProps {
  runId: string
  documentId: string
  onRerun: (defaults: RerunDefaults) => void
}

export function ClassificationRunDetail({
  runId,
  documentId,
  onRerun,
}: ClassificationRunDetailProps) {
  const { run, isLoading, error } = useClassificationRunDetail(runId)
  const { blocks } = useClassificationRunBlocks(
    run?.status === 'completed' ? runId : null,
  )
  const [viewerCollapsed, setViewerCollapsed] = useState(false)

  if (isLoading) {
    return (
      <div className="p-6 space-y-3">
        <Skeleton className="h-6 w-64" />
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4">
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    )
  }

  if (!run) return null

  const handleRerun = () => {
    onRerun({
      labels: run.labelsRequested,
      classifierType: run.classifierType,
      classifierConfig: run.classifierConfig,
    })
  }

  const modelSummary =
    run.classifierType === 'llm'
      ? `${run.classifierConfig.provider as string} / ${run.classifierConfig.model as string}`
      : run.classifierType

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Metadata strip */}
      <div className="px-4 py-3 border-b shrink-0 flex items-center gap-4 flex-wrap">
        <ClassificationRunStatusBadge status={run.status} />
        <span className="text-sm text-muted-foreground">{modelSummary}</span>
        <span className="text-xs text-muted-foreground">
          {formatDistanceToNow(new Date(run.createdAt), { addSuffix: true })}
        </span>
        <div className="flex gap-4 text-xs text-muted-foreground ml-auto">
          <span><span className="font-medium text-foreground">{run.labelsRequested.length}</span> labels</span>
          <span><span className="font-medium text-foreground">{run.regions.length}</span> regions</span>
          {run.inputTokens !== null && (
            <span>
              <span className="font-medium text-foreground">{run.inputTokens}</span> in /{' '}
              <span className="font-medium text-foreground">{run.outputTokens}</span> out tokens
            </span>
          )}
          {run.durationMs !== null && (
            <span><span className="font-medium text-foreground">{(run.durationMs / 1000).toFixed(1)}s</span></span>
          )}
        </div>
        <Button variant="outline" size="sm" className="h-7 text-xs shrink-0" onClick={handleRerun}>
          <RotateCw className="h-3.5 w-3.5 mr-1.5" />
          Re-run
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          title={viewerCollapsed ? 'Show document viewer' : 'Hide document viewer'}
          onClick={() => setViewerCollapsed((v) => !v)}
        >
          {viewerCollapsed
            ? <PanelRightOpen className="h-4 w-4" />
            : <PanelRightClose className="h-4 w-4" />}
        </Button>
      </div>

      {/* Error / running states */}
      {run.error && (
        <div className="px-4 pt-3 shrink-0">
          <Alert variant="destructive">
            <AlertDescription>{run.error}</AlertDescription>
          </Alert>
        </div>
      )}

      {run.status === 'running' && (
        <p className="px-4 pt-3 text-sm text-muted-foreground animate-pulse shrink-0">
          Classification in progress…
        </p>
      )}

      {/* Results split */}
      {run.status === 'completed' && (
        <div className="flex flex-1 min-h-0">
          {/* Left: label results */}
          <div className="w-80 shrink-0 border-r overflow-y-auto p-4">
            <ClassificationResultsViewer
              runId={run.id}
              labelsRequested={run.labelsRequested}
            />
          </div>

          {/* Right: document viewer */}
          {!viewerCollapsed && (
            <div className="flex-1 overflow-y-auto">
              <ParsedDocumentViewer
                documentId={documentId}
                defaultParseRunId={run.parseRunId}
                regions={run.regions}
                annotatedBlocks={blocks}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```
npm --prefix frontend run build 2>&1 | head -30
```

Expected: no errors.

- [ ] **Step 3: Commit**

```
git add frontend/src/components/classification/ClassificationRunDetail.tsx
git commit -m "feat(classify): add ClassificationRunDetail split-panel component"
```

---

### Task 4: ClassificationRunSheet component

**Files:**
- Create: `frontend/src/components/classification/ClassificationRunSheet.tsx`

**Interfaces:**
- Consumes:
  - `ClassificationConfig`, `ClassificationConfigValue` from `./ClassificationConfig` (WS1)
  - `ParseMethodSelector` from `@/components/documents/ParseMethodSelector`
  - `useParseRuns` from `@/hooks/useParseRuns`
  - `createClassificationRun` from `@/api/classification`
  - shadcn `Sheet`, `SheetContent`, `SheetHeader`, `SheetTitle`, `SheetDescription`
  - `RerunDefaults` from `./ClassificationRunDetail`
- Props:
  ```typescript
  interface ClassificationRunSheetProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    documentId: string
    documentTitle: string
    defaultValues?: RerunDefaults
    onStarted: (runId: string) => void
  }
  ```

- [ ] **Step 1: Create ClassificationRunSheet.tsx**

Create `frontend/src/components/classification/ClassificationRunSheet.tsx`:

```typescript
import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { ParseMethodSelector } from '@/components/documents/ParseMethodSelector'
import { ClassificationConfig } from './ClassificationConfig'
import type { ClassificationConfigValue } from './ClassificationConfig'
import type { RerunDefaults } from './ClassificationRunDetail'
import { useParseRuns } from '@/hooks/useParseRuns'
import { createClassificationRun } from '@/api/classification'
import type { ParseConfig } from '@/types/parsing'

interface ClassificationRunSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  documentId: string
  documentTitle: string
  defaultValues?: RerunDefaults
  onStarted: (runId: string) => void
}

export function ClassificationRunSheet({
  open,
  onOpenChange,
  documentId,
  documentTitle,
  defaultValues,
  onStarted,
}: ClassificationRunSheetProps) {
  const { parseRuns } = useParseRuns(open ? documentId : null)

  const latestViableRun = parseRuns.find(
    (r) => r.status === 'succeeded' || r.status === 'partial',
  )

  const [parserType, setParserType] = useState('simple')
  const [parserConfig, setParserConfig] = useState<ParseConfig>({})
  const [classifyConfig, setClassifyConfig] = useState<ClassificationConfigValue>({
    labels: defaultValues?.labels ?? [],
    classifierType: defaultValues?.classifierType ?? 'llm',
    classifierConfig: defaultValues?.classifierConfig ?? {},
  })
  const [configKey, setConfigKey] = useState(0)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset all form state each time the sheet opens
  useEffect(() => {
    if (!open) return
    setConfigKey((k) => k + 1)
    setClassifyConfig({
      labels: defaultValues?.labels ?? [],
      classifierType: defaultValues?.classifierType ?? 'llm',
      classifierConfig: defaultValues?.classifierConfig ?? {},
    })
    setError(null)
    setIsSubmitting(false)
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  // Seed parse config from latest viable run when it loads
  useEffect(() => {
    if (!latestViableRun) return
    setParserType(latestViableRun.parser ?? 'simple')
    const cfg = { ...(latestViableRun.config as Record<string, unknown> ?? {}) }
    delete cfg['parser']
    setParserConfig(cfg as ParseConfig)
  }, [latestViableRun?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = async () => {
    if (classifyConfig.labels.length === 0) return
    if (!latestViableRun) {
      setError('No completed parse run found for this document. Parse it first.')
      return
    }
    setIsSubmitting(true)
    setError(null)
    try {
      const run = await createClassificationRun(documentId, {
        parseRunId: latestViableRun.id,
        labels: classifyConfig.labels,
        classifierType: classifyConfig.classifierType,
        classifierConfig: classifyConfig.classifierConfig,
      })
      toast.success('Classification started')
      onStarted(run.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start classification')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[60vw] max-w-3xl overflow-y-auto flex flex-col gap-0 p-0">
        <SheetHeader className="px-6 py-4 border-b">
          <SheetTitle>New classification run</SheetTitle>
          <SheetDescription className="truncate">{documentTitle}</SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          <ParseMethodSelector
            parserType={parserType}
            config={parserConfig}
            onParserTypeChange={setParserType}
            onConfigChange={setParserConfig}
            disabled={isSubmitting}
            compact
          />

          <Separator />

          <ClassificationConfig
            key={configKey}
            defaultValues={{
              labels: classifyConfig.labels,
              classifierType: classifyConfig.classifierType,
              classifierConfig: classifyConfig.classifierConfig,
            }}
            onChange={setClassifyConfig}
          />

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <div className="px-6 py-4 border-t flex justify-end shrink-0">
          <Button
            onClick={handleSubmit}
            disabled={
              classifyConfig.labels.length === 0 ||
              isSubmitting ||
              classifyConfig.classifierType === 'llamaindex_split'
            }
          >
            {isSubmitting ? 'Starting…' : 'Start classification'}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```
npm --prefix frontend run build 2>&1 | head -30
```

Expected: no errors. If `Sheet` or related imports aren't found, install via:
```
npm --prefix frontend exec -- npx shadcn@latest add sheet
```

- [ ] **Step 3: Commit**

```
git add frontend/src/components/classification/ClassificationRunSheet.tsx
git commit -m "feat(classify): add ClassificationRunSheet wide-sheet component"
```

---

### Task 5: Rewrite ClassificationPage, clean up routes, delete old pages

**Files:**
- Rewrite: `frontend/src/pages/ClassificationPage.tsx`
- Modify: the React Router config (find the file that registers `/classify`, `/classify/new`, `/classify/:runId` — typically `frontend/src/App.tsx` or `frontend/src/router.tsx`)
- Modify: `frontend/src/components/extraction/DocumentSelector.tsx` — make `onUploadClick` optional
- Delete: `frontend/src/pages/NewClassificationRunPage.tsx`
- Delete: `frontend/src/pages/ClassificationRunDetailPage.tsx`

- [ ] **Step 1: Make DocumentSelector.onUploadClick optional**

Open `frontend/src/components/extraction/DocumentSelector.tsx`.

Find the `DocumentSelectorProps` interface and change `onUploadClick` from required to optional:

```typescript
// Before
interface DocumentSelectorProps {
  documents: DocumentListItem[]
  isLoading: boolean
  selectedDocumentId: string | null
  onSelect: (documentId: string) => void
  onUploadClick: () => void
}

// After
interface DocumentSelectorProps {
  documents: DocumentListItem[]
  isLoading: boolean
  selectedDocumentId: string | null
  onSelect: (documentId: string) => void
  onUploadClick?: () => void
}
```

Find the Upload button inside `DocumentSelector` and guard it: only render when `onUploadClick` is provided:

```typescript
{/* Before */}
<div className="p-3 border-t">
  <Button variant="outline" className="w-full" size="sm" onClick={onUploadClick}>
    <Upload className="h-4 w-4 mr-2" />
    Upload Document
  </Button>
</div>

{/* After */}
{onUploadClick && (
  <div className="p-3 border-t">
    <Button variant="outline" className="w-full" size="sm" onClick={onUploadClick}>
      <Upload className="h-4 w-4 mr-2" />
      Upload Document
    </Button>
  </div>
)}
```

- [ ] **Step 2: Verify TypeScript compiles after DocumentSelector change**

```
npm --prefix frontend run build 2>&1 | head -30
```

Expected: no errors. All existing callers that pass `onUploadClick` still work; no callers break.

- [ ] **Step 3: Rewrite ClassificationPage.tsx**

Replace the entire contents of `frontend/src/pages/ClassificationPage.tsx` with:

```typescript
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Tags } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { DocumentSelector } from '@/components/extraction/DocumentSelector'
import { ClassificationRunHistory } from '@/components/classification/ClassificationRunHistory'
import { ClassificationRunDetail } from '@/components/classification/ClassificationRunDetail'
import { ClassificationRunSheet } from '@/components/classification/ClassificationRunSheet'
import type { RerunDefaults } from '@/components/classification/ClassificationRunDetail'

export default function ClassificationPage(): JSX.Element {
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const { documents, isLoading: documentsLoading } = useDocuments(projectId)

  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    searchParams.get('documentId'),
  )
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [sheetDefaults, setSheetDefaults] = useState<RerunDefaults | undefined>()

  const handleSelectDocument = (docId: string) => {
    setSelectedDocumentId(docId)
    setSelectedRunId(null)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('documentId', docId)
      return next
    })
  }

  const handleNewRun = () => {
    setSheetDefaults(undefined)
    setSheetOpen(true)
  }

  const handleRerun = (defaults: RerunDefaults) => {
    setSheetDefaults(defaults)
    setSheetOpen(true)
  }

  const handleRunStarted = (runId: string) => {
    setSelectedRunId(runId)
    setSheetOpen(false)
  }

  const selectedDocument = documents.find((d) => d.id === selectedDocumentId)

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b shrink-0">
        <div>
          <h1 className="text-lg font-semibold">Classify</h1>
          <p className="text-xs text-muted-foreground">{currentProject?.name}</p>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 min-h-0">
        {/* Left: document picker */}
        <div className="w-56 border-r shrink-0 flex flex-col">
          <DocumentSelector
            documents={documents}
            isLoading={documentsLoading}
            selectedDocumentId={selectedDocumentId}
            onSelect={handleSelectDocument}
          />
        </div>

        {/* Right: run history + detail */}
        <div className="flex-1 min-h-0 flex flex-col">
          {!selectedDocumentId ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <Tags className="h-12 w-12 text-muted-foreground/40 mb-4" />
              <h2 className="text-lg font-medium text-muted-foreground">
                Select a document to get started
              </h2>
              <p className="text-sm text-muted-foreground/70 mt-1 max-w-sm">
                Choose a document from the list to see its classification history.
              </p>
            </div>
          ) : (
            <>
              <ClassificationRunHistory
                documentId={selectedDocumentId}
                selectedRunId={selectedRunId}
                onSelectRun={setSelectedRunId}
                onNewRun={handleNewRun}
              />
              <div className="flex-1 min-h-0 overflow-hidden">
                {selectedRunId ? (
                  <ClassificationRunDetail
                    runId={selectedRunId}
                    documentId={selectedDocumentId}
                    onRerun={handleRerun}
                  />
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-center px-6">
                    <p className="text-sm text-muted-foreground">
                      Select a run above, or{' '}
                      <button
                        className="underline hover:no-underline"
                        onClick={handleNewRun}
                      >
                        start a new one
                      </button>
                      .
                    </p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* New-run sheet */}
      {selectedDocumentId && (
        <ClassificationRunSheet
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          documentId={selectedDocumentId}
          documentTitle={selectedDocument?.title ?? ''}
          defaultValues={sheetDefaults}
          onStarted={handleRunStarted}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 4: Find and update the router**

Search for the file that declares the classify routes:

```
npm --prefix frontend exec -- grep -r "classify" src --include="*.tsx" -l
```

Open the router file (likely `frontend/src/App.tsx` or `frontend/src/router.tsx`). Find the three classify routes and replace them with one:

```typescript
// Remove these two:
{ path: '/classify/new', element: <NewClassificationRunPage /> },
{ path: '/classify/:runId', element: <ClassificationRunDetailPage /> },

// Keep only:
{ path: '/classify', element: <ClassificationPage /> },
```

Also remove the imports for `NewClassificationRunPage` and `ClassificationRunDetailPage` from the router file.

- [ ] **Step 5: Delete the old pages**

```
git rm frontend/src/pages/NewClassificationRunPage.tsx
git rm frontend/src/pages/ClassificationRunDetailPage.tsx
```

- [ ] **Step 6: Verify TypeScript compiles and lint passes**

```
npm --prefix frontend run build 2>&1 | head -50
npm --prefix frontend run lint
```

Expected: no errors. If there are import errors for the deleted pages, verify Step 4 removed all references.

- [ ] **Step 7: Run all vitest tests**

```
npm --prefix frontend exec -- npx vitest run
```

Expected: all existing tests pass.

- [ ] **Step 8: Commit**

```
git add -A
git commit -m "feat(classify): replace wizard with single-page layout and wide-sheet config"
```

---

## Manual Verification (Human + Browser)

Start the frontend dev server and ensure the backend is running:
```
npm --prefix frontend run dev
```

Open `http://localhost:5173` and navigate to **Classify** in the sidebar.

### Layout and navigation

1. **Empty state:** No document selected → centred icon + "Select a document to get started" message.
2. **Select a document:** Click any document in the left panel → run history strip appears at the top of the right panel. If there are existing runs, the most recent one is auto-selected and its results appear below.
3. **No runs for document:** If the document has no classification runs, history strip shows "No runs yet. Start the first one." link.

### Run history strip

4. Each run row shows: status badge, labels (truncated), provider/model, relative date, delete icon.
5. Click a different run row → results panel updates to show that run's results.
6. Clicking the **×** / delete icon on a run shows a success toast and removes the row. If the deleted run was selected, the next run is auto-selected.

### Metadata strip (when a run is selected)

7. Shows: status badge, model summary, relative date, label count, region count, token counts, duration.
8. **Re-run button** is present in the metadata strip.

### Results split panel

9. Left sub-panel (~320px) shows `ClassificationResultsViewer` with label sections. Each section expands to show its blocks (same as before).
10. Right sub-panel shows the `ParsedDocumentViewer`. Navigate to the **Pages** tab and verify:
    - Each page header shows a coloured label badge (e.g. "income_statement" in blue) matching the classification region that covers that page.
    - Block rows within a page show a coloured label badge next to the role badge for classified blocks.
    - Pages with no classified blocks show no label badge.
11. **Collapse toggle** (panel right icon) in the metadata strip → document viewer hides, results viewer expands to full width. Click again → viewer reappears.

### New Run sheet

12. Click **New Run** in the history strip header → a wide sheet (~60% of viewport) slides in from the right.
13. Sheet header shows "New classification run" + document title.
14. Sheet body shows: `ParseMethodSelector` at the top, a separator, then `ClassificationConfig` (labels input, classifier type, LLM config).
15. Add labels, confirm LLM config is populated with defaults.
16. Click **Start classification** → sheet closes, new run appears at the top of the history strip and is auto-selected. The results panel shows "running" state and then updates when complete.

### Re-run sheet

17. With a run selected, click **Re-run** in the metadata strip → sheet opens pre-populated with that run's labels, classifier type, and LLM config.
18. Modify a label or model, submit → new run created with updated config.

### Old routes are gone

19. Navigate to `http://localhost:5173/classify/new` → receives a 404 / "Not Found" page (not the old wizard).
20. Navigate to `http://localhost:5173/classify/<any-run-id>` → receives a 404 / "Not Found" page (not the old detail page).
