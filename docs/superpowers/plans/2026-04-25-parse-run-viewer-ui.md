# ParseRun Viewer UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the user a per-document drilldown showing the verbatim parser SDK payload alongside the adapted CDM `ParsedDocument`, so parses can be debugged and understood without re-running against the parser SDK.

**Architecture:** A small list-style "Parse Runs" timeline lives in the existing document sheet (alongside the current `ParsedDocumentViewer`). Clicking a run navigates to a new dedicated route `/documents/:documentId/runs/:runId` (`ParseRunDetailPage`) that renders a sticky run-metadata header above a two-pane body: raw JSON (collapsible tree) on the left, adapted CDM (reusing the existing block-renderer internals) on the right. Re-parse from the viewer header reuses the existing `ReParseDialog`.

**Tech Stack:** React 18, TypeScript, Vite, react-router-dom, shadcn/ui, Tailwind, vitest. New dependency: `react-json-view-lite` (~10 KB gzipped, MIT) for the JSON tree.

**Spec:** [docs/specs/parse_run_viewer.md](../../specs/parse_run_viewer.md) (Phase 2)

**Depends on:** Phase 1 (`docs/superpowers/plans/2026-04-25-parse-run-raw-payload-persistence.md`) merged to `main`. The left pane has nothing to render until `raw_payload` is persisted and the `/raw-payload` endpoint is live.

---

## Pre-implementation gate

- [ ] **Step 0: Confirm Phase 1 has merged**

Run: `git -C . log --oneline main -- backend/app/routers/parse_runs.py | head -5`

Expected: at least one commit referencing `raw-payload` (the Phase 1 endpoint commit). If not, do not start — Phase 1 must land first.

- [ ] **Step 0.1: Create the GitHub issue**

```bash
gh issue create \
  --title "ParseRun Viewer UI" \
  --body "$(cat <<'EOF'
## Summary
Add a per-document ParseRun drilldown:
- Run timeline inside the existing document sheet
- New route /documents/:documentId/runs/:runId
- Sticky run-metadata header
- Two-pane body: raw JSON | adapted CDM
- Re-parse via existing ReParseDialog

## Acceptance criteria
See docs/specs/parse_run_viewer.md §7 (Phase 2).

## Spec
docs/specs/parse_run_viewer.md
EOF
)"
```

Confirm the issue number with the user. Use `(#NN)` in commit messages.

---

## File structure

**Created:**
- `frontend/src/pages/ParseRunDetailPage.tsx`
- `frontend/src/components/parse-runs/RunHeader.tsx`
- `frontend/src/components/parse-runs/RawPayloadViewer.tsx`
- `frontend/src/components/parse-runs/RunTimeline.tsx`
- `frontend/src/components/parse-runs/ParsedDocumentPane.tsx` *(extracted from current `ParsedDocumentViewer` so the dedicated page can render the right pane standalone)*
- `frontend/src/hooks/useParseRunRawPayload.ts`
- `frontend/src/hooks/useParseRunDetail.ts`
- `frontend/src/components/parse-runs/RunHeader.test.tsx`
- `frontend/src/components/parse-runs/RawPayloadViewer.test.tsx`
- `frontend/src/components/parse-runs/RunTimeline.test.tsx`
- `frontend/src/hooks/useParseRunRawPayload.test.ts`

**Modified:**
- `frontend/src/api/parseRuns.ts` — add `getRawPayload(parseRunId)` and `getParseRun(parseRunId)`
- `frontend/src/types/cdm.ts` — add `RawPayloadResponse`
- `frontend/src/components/documents/ParsedDocumentViewer.tsx` — extract block rendering into `ParsedDocumentPane`; wire timeline rows + "Open viewer" deep link
- `frontend/src/App.tsx` — register `/documents/:documentId/runs/:runId` route
- `frontend/package.json` — add `react-json-view-lite` dep

---

### Task 1: Add `react-json-view-lite` dependency

- [ ] **Step 1.1: Install**

Run: `npm --prefix frontend install react-json-view-lite`

Expected: lockfile updates; `package.json` `dependencies` has the new entry. Version pinning follows the project's existing convention (caret).

- [ ] **Step 1.2: Sanity import**

Run: `npm --prefix frontend exec -- vite-node -e "import('react-json-view-lite').then(m => console.log(Object.keys(m)))"`

Expected: prints something including `JsonView`. (Skip if vite-node isn't set up — the build in Step 11 will catch import errors regardless.)

- [ ] **Step 1.3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "feat(parse-runs): add react-json-view-lite dependency (#NN)"
```

---

### Task 2: Backend wire types — `RawPayloadResponse` + API client

**Files:**
- Modify: `frontend/src/types/cdm.ts`
- Modify: `frontend/src/api/parseRuns.ts`

- [ ] **Step 2.1: Add the type**

Append to `frontend/src/types/cdm.ts`:

```typescript
export interface RawPayloadResponse {
  rawPayload: Record<string, unknown> | null
}
```

- [ ] **Step 2.2: Add the API functions**

Modify `frontend/src/api/parseRuns.ts`. Add the import and two new functions (`getRawPayload` and `getParseRun` — the dedicated page needs run metadata without needing a `documentId`):

```typescript
import apiClient from './client'
import type {
  ParseRunListItem,
  ParsedDocumentDetail,
  RawPayloadResponse,
} from '@/types/cdm'

export async function listParseRuns(
  documentId: string
): Promise<ParseRunListItem[]> {
  const response = await apiClient.get<ParseRunListItem[]>(
    `/documents/${documentId}/parse-runs`
  )
  return response.data
}

export async function getParseRun(
  parseRunId: string
): Promise<ParseRunListItem> {
  // Uses the same wire shape as list rows.
  const response = await apiClient.get<ParseRunListItem>(
    `/parse-runs/${parseRunId}`
  )
  return response.data
}

export async function getParsedDocument(
  parseRunId: string
): Promise<ParsedDocumentDetail> {
  const response = await apiClient.get<ParsedDocumentDetail>(
    `/parse-runs/${parseRunId}/parsed-document`
  )
  return response.data
}

export async function getRawPayload(
  parseRunId: string
): Promise<RawPayloadResponse> {
  const response = await apiClient.get<RawPayloadResponse>(
    `/parse-runs/${parseRunId}/raw-payload`
  )
  return response.data
}
```

> If `GET /api/v1/parse-runs/{id}` does not yet exist (i.e. the backend only exposes the per-document list), add a small router handler in this task's commit. Check `backend/app/routers/parse_runs.py` first; if it's missing, add a `GET /{parse_run_id}` route that returns the same shape as the list rows (one row by id) plus a router test in `backend/tests/routers/test_parse_runs_router.py`. The existing list endpoint's response model is a good source of truth for the shape.

- [ ] **Step 2.3: Commit**

```bash
git add frontend/src/types/cdm.ts frontend/src/api/parseRuns.ts
git commit -m "feat(parse-runs): add raw-payload + single-run API clients (#NN)"
# Include backend changes in the same commit if Step 2.2's footnote required them.
```

---

### Task 3: `useParseRunRawPayload` hook (TDD)

**Files:**
- Create: `frontend/src/hooks/useParseRunRawPayload.ts`
- Create: `frontend/src/hooks/useParseRunRawPayload.test.ts`

- [ ] **Step 3.1: Write the failing test**

Create `frontend/src/hooks/useParseRunRawPayload.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import * as api from '@/api/parseRuns'
import { useParseRunRawPayload } from './useParseRunRawPayload'

vi.mock('@/api/parseRuns', () => ({
  getRawPayload: vi.fn(),
}))

describe('useParseRunRawPayload', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches and exposes the raw payload', async () => {
    vi.mocked(api.getRawPayload).mockResolvedValue({
      rawPayload: { hello: 'world' },
    })

    const { result } = renderHook(() => useParseRunRawPayload('run-1'))

    await waitFor(() => {
      expect(result.current.rawPayload).toEqual({ hello: 'world' })
    })
    expect(result.current.isLoading).toBe(false)
    expect(result.current.error).toBeNull()
    expect(api.getRawPayload).toHaveBeenCalledWith('run-1')
  })

  it('exposes null when the backend returns null', async () => {
    vi.mocked(api.getRawPayload).mockResolvedValue({ rawPayload: null })
    const { result } = renderHook(() => useParseRunRawPayload('run-2'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.rawPayload).toBeNull()
  })

  it('captures errors', async () => {
    vi.mocked(api.getRawPayload).mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useParseRunRawPayload('run-3'))
    await waitFor(() => expect(result.current.error).toBe('boom'))
    expect(result.current.rawPayload).toBeUndefined()
  })

  it('does not fetch when parseRunId is null', () => {
    renderHook(() => useParseRunRawPayload(null))
    expect(api.getRawPayload).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 3.2: Run and watch it fail**

Run: `npm --prefix frontend exec -- vitest run src/hooks/useParseRunRawPayload.test.ts`

Expected: FAIL — module not found.

- [ ] **Step 3.3: Implement the hook**

Create `frontend/src/hooks/useParseRunRawPayload.ts`:

```typescript
import { useEffect, useState } from 'react'
import * as parseRunsApi from '@/api/parseRuns'

interface UseParseRunRawPayloadReturn {
  rawPayload: Record<string, unknown> | null | undefined
  isLoading: boolean
  error: string | null
}

export function useParseRunRawPayload(
  parseRunId: string | null
): UseParseRunRawPayloadReturn {
  const [rawPayload, setRawPayload] = useState<
    Record<string, unknown> | null | undefined
  >(undefined)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    if (!parseRunId) {
      setRawPayload(undefined)
      setError(null)
      return
    }
    setIsLoading(true)
    setError(null)
    parseRunsApi
      .getRawPayload(parseRunId)
      .then((resp) => {
        if (cancelled) return
        setRawPayload(resp.rawPayload)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setRawPayload(undefined)
        setError(err instanceof Error ? err.message : 'Failed to fetch raw payload')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [parseRunId])

  return { rawPayload, isLoading, error }
}
```

- [ ] **Step 3.4: Run and verify**

Run: `npm --prefix frontend exec -- vitest run src/hooks/useParseRunRawPayload.test.ts`

Expected: all four tests PASS.

- [ ] **Step 3.5: Commit**

```bash
git add frontend/src/hooks/useParseRunRawPayload.ts frontend/src/hooks/useParseRunRawPayload.test.ts
git commit -m "feat(parse-runs): add useParseRunRawPayload hook (#NN)"
```

---

### Task 4: `useParseRunDetail` hook

**Files:**
- Create: `frontend/src/hooks/useParseRunDetail.ts`

- [ ] **Step 4.1: Implement the hook**

This is small enough that we skip the standalone test; the page-level integration in Task 9 covers it.

```typescript
import { useEffect, useState } from 'react'
import * as parseRunsApi from '@/api/parseRuns'
import type { ParseRunListItem } from '@/types/cdm'

interface UseParseRunDetailReturn {
  run: ParseRunListItem | undefined
  isLoading: boolean
  error: string | null
}

export function useParseRunDetail(
  parseRunId: string | null
): UseParseRunDetailReturn {
  const [run, setRun] = useState<ParseRunListItem | undefined>(undefined)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    if (!parseRunId) {
      setRun(undefined)
      setError(null)
      return
    }
    setIsLoading(true)
    setError(null)
    parseRunsApi
      .getParseRun(parseRunId)
      .then((r) => {
        if (!cancelled) setRun(r)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setRun(undefined)
        setError(err instanceof Error ? err.message : 'Failed to fetch parse run')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [parseRunId])

  return { run, isLoading, error }
}
```

- [ ] **Step 4.2: Commit**

```bash
git add frontend/src/hooks/useParseRunDetail.ts
git commit -m "feat(parse-runs): add useParseRunDetail hook (#NN)"
```

---

### Task 5: `RawPayloadViewer` component (TDD)

**Files:**
- Create: `frontend/src/components/parse-runs/RawPayloadViewer.tsx`
- Create: `frontend/src/components/parse-runs/RawPayloadViewer.test.tsx`

- [ ] **Step 5.1: Write the failing test**

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RawPayloadViewer } from './RawPayloadViewer'

describe('RawPayloadViewer', () => {
  it('renders an empty state when payload is null', () => {
    render(<RawPayloadViewer payload={null} />)
    expect(
      screen.getByText(/no raw payload was captured/i)
    ).toBeInTheDocument()
  })

  it('renders a loading state', () => {
    render(<RawPayloadViewer payload={undefined} isLoading />)
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('renders an error state', () => {
    render(
      <RawPayloadViewer
        payload={undefined}
        isLoading={false}
        error="boom"
      />
    )
    expect(screen.getByText(/boom/i)).toBeInTheDocument()
  })

  it('renders payload keys when given a dict', () => {
    render(
      <RawPayloadViewer
        payload={{ job_metadata: { job_id: 'j1' }, pages: [] }}
      />
    )
    expect(screen.getByText(/job_metadata/)).toBeInTheDocument()
    expect(screen.getByText(/pages/)).toBeInTheDocument()
  })

  it('copies JSON to clipboard on Copy click', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    render(<RawPayloadViewer payload={{ a: 1 }} />)
    await userEvent.click(screen.getByRole('button', { name: /copy/i }))
    expect(writeText).toHaveBeenCalledWith(
      JSON.stringify({ a: 1 }, null, 2)
    )
  })
})
```

- [ ] **Step 5.2: Run and watch it fail**

Run: `npm --prefix frontend exec -- vitest run src/components/parse-runs/RawPayloadViewer.test.tsx`

Expected: FAIL — module not found.

- [ ] **Step 5.3: Implement the component**

Create `frontend/src/components/parse-runs/RawPayloadViewer.tsx`:

```tsx
import { JsonView, defaultStyles } from 'react-json-view-lite'
import 'react-json-view-lite/dist/index.css'
import { Button } from '@/components/ui/button'
import { Copy, Download } from 'lucide-react'

interface RawPayloadViewerProps {
  payload: Record<string, unknown> | null | undefined
  isLoading?: boolean
  error?: string | null
}

export function RawPayloadViewer({
  payload,
  isLoading = false,
  error = null,
}: RawPayloadViewerProps) {
  if (isLoading) {
    return (
      <div className="p-4 text-sm text-muted-foreground">Loading…</div>
    )
  }
  if (error) {
    return (
      <div className="p-4 text-sm text-destructive">{error}</div>
    )
  }
  if (payload === null) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        No raw payload was captured for this run.
      </div>
    )
  }
  if (payload === undefined) {
    return null
  }

  const json = JSON.stringify(payload, null, 2)

  const handleCopy = () => {
    void navigator.clipboard.writeText(json)
  }
  const handleDownload = () => {
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'raw-payload.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between border-b px-3 py-2 gap-2">
        <span className="text-xs font-medium text-muted-foreground">
          Raw parser payload
        </span>
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" onClick={handleCopy}>
            <Copy className="h-3 w-3 mr-1" /> Copy
          </Button>
          <Button size="sm" variant="ghost" onClick={handleDownload}>
            <Download className="h-3 w-3 mr-1" /> Download
          </Button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-3 text-xs">
        <JsonView data={payload} style={defaultStyles} />
      </div>
    </div>
  )
}
```

- [ ] **Step 5.4: Run and verify**

Run: `npm --prefix frontend exec -- vitest run src/components/parse-runs/RawPayloadViewer.test.tsx`

Expected: all five tests PASS.

- [ ] **Step 5.5: Commit**

```bash
git add frontend/src/components/parse-runs/RawPayloadViewer.tsx frontend/src/components/parse-runs/RawPayloadViewer.test.tsx
git commit -m "feat(parse-runs): add RawPayloadViewer (#NN)"
```

---

### Task 6: `RunHeader` component (TDD)

**Files:**
- Create: `frontend/src/components/parse-runs/RunHeader.tsx`
- Create: `frontend/src/components/parse-runs/RunHeader.test.tsx`

- [ ] **Step 6.1: Write the failing test**

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RunHeader } from './RunHeader'
import type { ParseRunListItem } from '@/types/cdm'

const baseRun: ParseRunListItem = {
  id: 'run-1',
  sourceDocumentId: 'src-1',
  parser: 'llamaparse',
  parserVersion: 'v1',
  representationKind: 'vector_light',
  status: 'succeeded',
  startedAt: '2026-04-25T10:00:00Z',
  finishedAt: '2026-04-25T10:00:04Z',
  durationMs: 4200,
  inputTokens: 100,
  outputTokens: 200,
  cost: { total: 0.012 },
  warnings: [],
  failedPages: [],
  providerRefs: { llamaparse_job_id: 'job-1' },
  error: null,
  config: { tier: 'agentic' },
  createdAt: '2026-04-25T10:00:00Z',
}

describe('RunHeader', () => {
  it('renders parser, status, and duration', () => {
    render(<RunHeader run={baseRun} onReparse={vi.fn()} />)
    expect(screen.getByText(/llamaparse/i)).toBeInTheDocument()
    expect(screen.getByText(/succeeded/i)).toBeInTheDocument()
    expect(screen.getByText(/4\.2s|4200/)).toBeInTheDocument()
  })

  it('exposes config JSON when expanded', async () => {
    render(<RunHeader run={baseRun} onReparse={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /config/i }))
    expect(screen.getByText(/"tier": "agentic"/)).toBeInTheDocument()
  })

  it('triggers onReparse when the button is clicked', async () => {
    const onReparse = vi.fn()
    render(<RunHeader run={baseRun} onReparse={onReparse} />)
    await userEvent.click(screen.getByRole('button', { name: /re-parse/i }))
    expect(onReparse).toHaveBeenCalled()
  })

  it('shows error text for failed runs', () => {
    render(
      <RunHeader
        run={{ ...baseRun, status: 'failed', error: 'sdk down' }}
        onReparse={vi.fn()}
      />
    )
    expect(screen.getByText(/sdk down/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 6.2: Run and watch it fail**

Run: `npm --prefix frontend exec -- vitest run src/components/parse-runs/RunHeader.test.tsx`

Expected: FAIL — module not found.

- [ ] **Step 6.3: Implement the component**

Create `frontend/src/components/parse-runs/RunHeader.tsx`:

```tsx
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import type { ParseRunListItem } from '@/types/cdm'
import { ChevronDown, RefreshCw } from 'lucide-react'

interface RunHeaderProps {
  run: ParseRunListItem
  onReparse: () => void
}

function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function statusVariant(
  status: ParseRunListItem['status']
): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'succeeded': return 'default'
    case 'failed': return 'destructive'
    case 'partial': return 'secondary'
    default: return 'outline'
  }
}

export function RunHeader({ run, onReparse }: RunHeaderProps) {
  const [configOpen, setConfigOpen] = useState(false)
  return (
    <div className="border-b bg-background sticky top-0 z-10">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
        <span className="text-sm font-medium">
          {run.parser}
          {run.parserVersion && (
            <span className="text-muted-foreground">@{run.parserVersion}</span>
          )}
        </span>
        <span className="text-xs text-muted-foreground">
          {run.representationKind}
        </span>
        <span className="text-xs text-muted-foreground">
          {formatDuration(run.durationMs)}
        </span>
        {(run.inputTokens !== null || run.outputTokens !== null) && (
          <span className="text-xs text-muted-foreground">
            tokens: {run.inputTokens ?? '—'} / {run.outputTokens ?? '—'}
          </span>
        )}
        {Object.keys(run.cost).length > 0 && (
          <span className="text-xs text-muted-foreground">
            cost: {JSON.stringify(run.cost)}
          </span>
        )}
        <Button
          size="sm"
          variant="outline"
          className="ml-auto"
          onClick={onReparse}
        >
          <RefreshCw className="h-3 w-3 mr-1" /> Re-parse
        </Button>
      </div>
      {run.error && (
        <div className="px-4 py-2 text-xs text-destructive border-t bg-destructive/5">
          {run.error}
        </div>
      )}
      <Collapsible open={configOpen} onOpenChange={setConfigOpen}>
        <CollapsibleTrigger asChild>
          <button className="w-full text-left px-4 py-1 text-xs text-muted-foreground hover:bg-muted/40 flex items-center gap-1">
            <ChevronDown
              className={`h-3 w-3 transition-transform ${configOpen ? '' : '-rotate-90'}`}
            />
            Config
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <pre className="px-4 pb-3 text-xs font-mono whitespace-pre-wrap text-muted-foreground">
            {JSON.stringify(run.config, null, 2)}
          </pre>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
```

- [ ] **Step 6.4: Run and verify**

Run: `npm --prefix frontend exec -- vitest run src/components/parse-runs/RunHeader.test.tsx`

Expected: all four tests PASS.

- [ ] **Step 6.5: Commit**

```bash
git add frontend/src/components/parse-runs/RunHeader.tsx frontend/src/components/parse-runs/RunHeader.test.tsx
git commit -m "feat(parse-runs): add RunHeader (#NN)"
```

---

### Task 7: Extract `ParsedDocumentPane` from `ParsedDocumentViewer`

**Why:** the existing `ParsedDocumentViewer` couples a documentId-driven run picker with the block-rendering body. The new dedicated page is parseRunId-driven and supplies the run/parsed-document itself. Pulling out the rendering body lets us reuse it without re-implementing block display.

**Files:**
- Create: `frontend/src/components/parse-runs/ParsedDocumentPane.tsx`
- Modify: `frontend/src/components/documents/ParsedDocumentViewer.tsx` — replace its inner block list usage with this new component (no behaviour change there).

- [ ] **Step 7.1: Move the page+block rendering**

Open `frontend/src/components/documents/ParsedDocumentViewer.tsx`. Identify the inner rendering chunk that, given a `ParsedDocumentDetail` and a list of pages, renders the per-page block list (the `PageBlockList` function and the surrounding "Pages" tab body). Move that rendering into a new exported component:

`frontend/src/components/parse-runs/ParsedDocumentPane.tsx`

```tsx
import type { ParsedDocumentDetail } from '@/types/cdm'
// Re-export of the existing PageBlockList rendering. Move PageBlockList here
// from ParsedDocumentViewer.tsx along with its imports (Markdown, Collapsible,
// Badge, etc.). The PageBlockList implementation does NOT change — only its
// home does. Then expose this top-level component:

export interface ParsedDocumentPaneProps {
  parsedDocument: ParsedDocumentDetail | undefined
  isLoading?: boolean
  error?: string | null
}

export function ParsedDocumentPane({
  parsedDocument,
  isLoading = false,
  error = null,
}: ParsedDocumentPaneProps) {
  if (isLoading) {
    return <div className="p-4 text-sm text-muted-foreground">Loading…</div>
  }
  if (error) {
    return <div className="p-4 text-sm text-destructive">{error}</div>
  }
  if (!parsedDocument) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        No adapted document for this run.
      </div>
    )
  }
  // Render the existing per-page tabs + PageBlockList exactly as the original
  // viewer did, but driven by `parsedDocument` instead of a hook.
  // (Copy the JSX from ParsedDocumentViewer.tsx's "Pages" tab body.)
  return (/* … pages + blocks JSX … */)
}
```

- [ ] **Step 7.2: Update `ParsedDocumentViewer` to consume the new component**

In `frontend/src/components/documents/ParsedDocumentViewer.tsx`, replace the inline page/block rendering with `<ParsedDocumentPane parsedDocument={parsedDocument} isLoading={isLoadingContent} error={error} />`. Delete the `PageBlockList` definition that was moved.

- [ ] **Step 7.3: Verify nothing visually changed in the document sheet**

Run: `npm --prefix frontend exec -- vitest run`

Expected: existing `ParsedDocumentViewer` tests still pass (no behaviour change, just relocation).

Then start the dev server (`npm --prefix frontend run dev`), open a document, confirm the existing CDM viewer renders identically.

- [ ] **Step 7.4: Commit**

```bash
git add frontend/src/components/parse-runs/ParsedDocumentPane.tsx frontend/src/components/documents/ParsedDocumentViewer.tsx
git commit -m "refactor(parse-runs): extract ParsedDocumentPane for reuse (#NN)"
```

---

### Task 8: `ParseRunDetailPage` — wire the dedicated route

**Files:**
- Create: `frontend/src/pages/ParseRunDetailPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 8.1: Implement the page**

Create `frontend/src/pages/ParseRunDetailPage.tsx`:

```tsx
import { useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { ChevronLeft } from 'lucide-react'
import { RunHeader } from '@/components/parse-runs/RunHeader'
import { RawPayloadViewer } from '@/components/parse-runs/RawPayloadViewer'
import { ParsedDocumentPane } from '@/components/parse-runs/ParsedDocumentPane'
import { ReParseDialog } from '@/components/documents/ReParseDialog'
import { useParseRunDetail } from '@/hooks/useParseRunDetail'
import { useParseRunRawPayload } from '@/hooks/useParseRunRawPayload'
import { useParseResults } from '@/hooks/useParseResults'
import * as parseRunsApi from '@/api/parseRuns'
import type { ParsedDocumentDetail } from '@/types/cdm'
import { useEffect } from 'react'

export function ParseRunDetailPage() {
  const { documentId, runId } = useParams<{
    documentId: string
    runId: string
  }>()
  const navigate = useNavigate()
  const [reparseOpen, setReparseOpen] = useState(false)

  const { run, isLoading: runLoading, error: runError } = useParseRunDetail(
    runId ?? null
  )
  const {
    rawPayload,
    isLoading: rawLoading,
    error: rawError,
  } = useParseRunRawPayload(runId ?? null)

  const [parsedDoc, setParsedDoc] = useState<ParsedDocumentDetail | undefined>(
    undefined
  )
  const [parsedLoading, setParsedLoading] = useState(false)
  const [parsedError, setParsedError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    if (!runId || !run) {
      setParsedDoc(undefined)
      return
    }
    if (run.status === 'failed' || run.status === 'pending' || run.status === 'running') {
      setParsedDoc(undefined)
      return
    }
    setParsedLoading(true)
    setParsedError(null)
    parseRunsApi
      .getParsedDocument(runId)
      .then((d) => { if (!cancelled) setParsedDoc(d) })
      .catch((err: unknown) => {
        if (cancelled) return
        setParsedError(err instanceof Error ? err.message : 'Failed to fetch parsed document')
        setParsedDoc(undefined)
      })
      .finally(() => { if (!cancelled) setParsedLoading(false) })
    return () => { cancelled = true }
  }, [runId, run])

  const { reparseDocument } = useParseResults(documentId ?? null)
  const handleReparse = useCallback(
    async (parserType: string, config?: Record<string, unknown>) => {
      if (!documentId) return
      const result = await reparseDocument(parserType, config as never)
      // result.parseRunId — navigate to the new run.
      const newRunId = (result as { parseRunId?: string }).parseRunId
      if (newRunId) {
        navigate(`/documents/${documentId}/runs/${newRunId}`)
      }
    },
    [documentId, navigate, reparseDocument]
  )

  if (runLoading) return <div className="p-6">Loading run…</div>
  if (runError) return <div className="p-6 text-destructive">{runError}</div>
  if (!run) return <div className="p-6">Run not found.</div>

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      <div className="px-4 py-2 border-b">
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/documents/${documentId ?? ''}`}>
            <ChevronLeft className="h-4 w-4 mr-1" /> Back to document
          </Link>
        </Button>
      </div>

      <RunHeader run={run} onReparse={() => setReparseOpen(true)} />

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 overflow-hidden">
        <div className="border-r overflow-hidden flex flex-col">
          <RawPayloadViewer
            payload={rawPayload}
            isLoading={rawLoading}
            error={rawError}
          />
        </div>
        <div className="overflow-auto">
          <ParsedDocumentPane
            parsedDocument={parsedDoc}
            isLoading={parsedLoading}
            error={parsedError}
          />
        </div>
      </div>

      <ReParseDialog
        open={reparseOpen}
        onOpenChange={setReparseOpen}
        onReparse={handleReparse}
        // Pre-select the current run's parser if the dialog supports it.
        // If `defaultParserType` is not yet a prop on ReParseDialog, leave it
        // for the user to pick — that's fine for v1.
      />
    </div>
  )
}
```

> If `ReParseDialog`'s prop names differ from `open`/`onOpenChange`/`onReparse` in this codebase (check `frontend/src/components/documents/ReParseDialog.tsx`), match its actual prop API. The contract here is "open/close + on success call our handler."

- [ ] **Step 8.2: Register the route**

In `frontend/src/App.tsx`, add inside the children array of the `'/'` route (alongside the `documents` entry, after line 78):

```tsx
{
  path: 'documents/:documentId/runs/:runId',
  element: <ParseRunDetailPage />,
  handle: { breadcrumb: 'Parse Run' },
},
```

Add the import at the top of `App.tsx`:

```tsx
import { ParseRunDetailPage } from './pages/ParseRunDetailPage'
```

- [ ] **Step 8.3: Smoke test in dev**

Run: `npm --prefix frontend run dev`

Manually visit `/documents/<some-doc-id>/runs/<some-run-id>` (use a real run id from the DB). Confirm:
- Run header renders parser/status/duration.
- Left pane shows raw JSON tree (or empty/legacy state if `raw_payload` is null).
- Right pane shows the adapted CDM page+block list.
- "Back to document" navigates to `/documents/<doc-id>`.
- "Re-parse" opens the existing dialog.

- [ ] **Step 8.4: Commit**

```bash
git add frontend/src/pages/ParseRunDetailPage.tsx frontend/src/App.tsx
git commit -m "feat(parse-runs): add ParseRunDetailPage at /documents/:documentId/runs/:runId (#NN)"
```

---

### Task 9: `RunTimeline` — list rows in the document sheet (TDD)

**Files:**
- Create: `frontend/src/components/parse-runs/RunTimeline.tsx`
- Create: `frontend/src/components/parse-runs/RunTimeline.test.tsx`

- [ ] **Step 9.1: Write the failing test**

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { RunTimeline } from './RunTimeline'
import type { ParseRunListItem } from '@/types/cdm'

const run = (over: Partial<ParseRunListItem> = {}): ParseRunListItem => ({
  id: 'r1',
  sourceDocumentId: 's1',
  parser: 'llamaparse',
  parserVersion: 'v1',
  representationKind: 'vector_light',
  status: 'succeeded',
  startedAt: '2026-04-25T10:00:00Z',
  finishedAt: '2026-04-25T10:00:04Z',
  durationMs: 4200,
  inputTokens: null,
  outputTokens: null,
  cost: {},
  warnings: [],
  failedPages: [],
  providerRefs: {},
  error: null,
  config: {},
  createdAt: '2026-04-25T10:00:00Z',
  ...over,
})

describe('RunTimeline', () => {
  it('renders an empty state', () => {
    render(
      <MemoryRouter>
        <RunTimeline documentId="d1" runs={[]} onReparse={vi.fn()} />
      </MemoryRouter>
    )
    expect(screen.getByText(/no parse runs/i)).toBeInTheDocument()
  })

  it('renders a row per run with an Open viewer link', () => {
    render(
      <MemoryRouter>
        <RunTimeline
          documentId="d1"
          runs={[run({ id: 'r1' }), run({ id: 'r2', status: 'failed' })]}
          onReparse={vi.fn()}
        />
      </MemoryRouter>
    )
    const links = screen.getAllByRole('link', { name: /open viewer/i })
    expect(links).toHaveLength(2)
    expect(links[0].getAttribute('href')).toBe('/documents/d1/runs/r1')
  })

  it('shows Re-parse only on the latest row and triggers handler', async () => {
    const onReparse = vi.fn()
    render(
      <MemoryRouter>
        <RunTimeline
          documentId="d1"
          runs={[run({ id: 'newest' }), run({ id: 'older' })]}
          onReparse={onReparse}
        />
      </MemoryRouter>
    )
    const reparseButtons = screen.getAllByRole('button', { name: /re-parse/i })
    expect(reparseButtons).toHaveLength(1)
    await userEvent.click(reparseButtons[0])
    expect(onReparse).toHaveBeenCalled()
  })
})
```

- [ ] **Step 9.2: Run and watch it fail**

Run: `npm --prefix frontend exec -- vitest run src/components/parse-runs/RunTimeline.test.tsx`

Expected: FAIL — module not found.

- [ ] **Step 9.3: Implement**

```tsx
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ExternalLink, RefreshCw } from 'lucide-react'
import type { ParseRunListItem } from '@/types/cdm'

interface RunTimelineProps {
  documentId: string
  runs: ParseRunListItem[]   // assumed newest-first (matches backend)
  onReparse: () => void
}

function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function relTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const s = Math.round(diffMs / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  return `${Math.round(s / 86400)}d ago`
}

export function RunTimeline({ documentId, runs, onReparse }: RunTimelineProps) {
  if (runs.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-2">
        No parse runs yet.
      </div>
    )
  }
  return (
    <ul className="divide-y rounded-md border">
      {runs.map((r, idx) => (
        <li key={r.id} className="flex items-center gap-3 px-3 py-2 text-sm">
          <Badge variant={r.status === 'failed' ? 'destructive' : r.status === 'succeeded' ? 'default' : 'secondary'}>
            {r.status}
          </Badge>
          <span className="font-medium">{r.parser}</span>
          <span className="text-xs text-muted-foreground">{r.representationKind}</span>
          <span className="text-xs text-muted-foreground">{relTime(r.startedAt)}</span>
          <span className="text-xs text-muted-foreground">{formatDuration(r.durationMs)}</span>
          {r.error && (
            <span className="text-xs text-destructive truncate max-w-[20ch]">
              {r.error}
            </span>
          )}
          <div className="ml-auto flex items-center gap-1">
            <Button asChild size="sm" variant="ghost">
              <Link to={`/documents/${documentId}/runs/${r.id}`}>
                <ExternalLink className="h-3 w-3 mr-1" /> Open viewer
              </Link>
            </Button>
            {idx === 0 && (
              <Button size="sm" variant="ghost" onClick={onReparse}>
                <RefreshCw className="h-3 w-3 mr-1" /> Re-parse
              </Button>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}
```

- [ ] **Step 9.4: Run and verify**

Run: `npm --prefix frontend exec -- vitest run src/components/parse-runs/RunTimeline.test.tsx`

Expected: all three tests PASS.

- [ ] **Step 9.5: Commit**

```bash
git add frontend/src/components/parse-runs/RunTimeline.tsx frontend/src/components/parse-runs/RunTimeline.test.tsx
git commit -m "feat(parse-runs): add RunTimeline (#NN)"
```

---

### Task 10: Wire `RunTimeline` into the document sheet

**Files:**
- Modify: `frontend/src/pages/DocumentsPage.tsx`
- Modify: `frontend/src/pages/ProjectDocumentsPage.tsx`

Both pages render the document sheet with `<ParsedDocumentViewer documentId={viewDocumentId} />` and `<ParseResultViewer documentId={viewDocumentId} />`. Add the timeline above (or below) the existing CDM viewer in both places.

- [ ] **Step 10.1: Add the timeline in `DocumentsPage`**

In `frontend/src/pages/DocumentsPage.tsx`, near the existing `<ParsedDocumentViewer />` usage, add:

```tsx
import { RunTimeline } from '@/components/parse-runs/RunTimeline'
import { useParseRuns } from '@/hooks/useParseRuns'

// inside the sheet body:
const { parseRuns } = useParseRuns(viewDocumentId)
// …
<div className="space-y-4">
  <section>
    <h3 className="text-sm font-medium mb-2">Parse runs</h3>
    <RunTimeline
      documentId={viewDocumentId ?? ''}
      runs={parseRuns}
      onReparse={() => setReparseDialogOpen(true)}
    />
  </section>
  {/* existing ParsedDocumentViewer below */}
  <ParsedDocumentViewer documentId={viewDocumentId} />
  {/* existing ParseResultViewer */}
</div>
```

(Match the surrounding indentation/JSX shape that's already in the file — this is a placement guide, not a verbatim diff.)

- [ ] **Step 10.2: Repeat for `ProjectDocumentsPage`**

Same change in `frontend/src/pages/ProjectDocumentsPage.tsx`.

- [ ] **Step 10.3: Smoke test**

Run: `npm --prefix frontend run dev`

Open a document with parse runs in both `/documents` and `/projects/:id/documents`. Confirm the timeline shows runs, "Open viewer" deep-links into the dedicated page, and "Re-parse" still opens the existing dialog.

- [ ] **Step 10.4: Commit**

```bash
git add frontend/src/pages/DocumentsPage.tsx frontend/src/pages/ProjectDocumentsPage.tsx
git commit -m "feat(parse-runs): surface RunTimeline in document sheet (#NN)"
```

---

### Task 11: Lint, typecheck, unit, build

- [ ] **Step 11.1: Lint**

Run: `npm --prefix frontend run lint`

Expected: no new errors.

- [ ] **Step 11.2: Unit tests**

Run: `npm --prefix frontend exec -- vitest run`

Expected: all tests PASS, including the four new test files (Tasks 3, 5, 6, 9).

- [ ] **Step 11.3: Production build**

Run: `npm --prefix frontend run build`

Expected: build succeeds.

- [ ] **Step 11.4: Manual verification of the v1 acceptance criteria**

Bring the local stack up per `CLAUDE.md` ("Local Testing (Docker)"). Then verify:

- [ ] Document sheet shows a "Parse runs" timeline with one row per run.
- [ ] Clicking "Open viewer" on a row navigates to `/documents/<doc>/runs/<run>`.
- [ ] On the dedicated page: header shows parser/status/duration; config expand reveals JSON.
- [ ] Left pane shows the verbatim parser JSON (collapsible). For a legacy run with no payload, shows the empty state copy.
- [ ] Right pane shows the adapted CDM (same content as the existing CDM viewer).
- [ ] "Re-parse" opens the existing dialog. After it succeeds, the page navigates to the new run.
- [ ] No regressions in the existing document upload flow or the CDM viewer in the sheet.

---

### Task 12: Open the PR

- [ ] **Step 12.1: Push and PR**

```bash
git push -u origin HEAD
gh pr create \
  --title "feat(parse-runs): ParseRun Viewer UI" \
  --body "$(cat <<'EOF'
## Summary
- Run timeline in the document sheet (per-document list of parse runs).
- New `/documents/:documentId/runs/:runId` route with two-pane layout: raw
  parser JSON on the left, adapted CDM (`ParsedDocumentPane`, extracted from
  the existing viewer) on the right, sticky run-metadata header above.
- Re-parse from the viewer reuses the existing `ReParseDialog`.
- New deps: `react-json-view-lite`.

Closes #NN

## Test plan
- [ ] `npm --prefix frontend run lint`
- [ ] `npm --prefix frontend exec -- vitest run`
- [ ] `npm --prefix frontend run build`
- [ ] Manual: timeline renders in sheet, viewer renders both panes, re-parse navigates to new run, legacy null-payload runs render the empty state.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Wait for user merge.

---

## Self-review notes (writer)

- **Spec coverage:**
  - Run timeline in sheet → Tasks 9–10.
  - Dedicated route `/documents/:documentId/runs/:runId` → Task 8.
  - Sticky header with metadata + config → Task 6.
  - Two-pane layout (raw | CDM) → Task 8.
  - Re-parse via existing dialog → Task 8 (`onReparse` wiring).
  - Reuse `ParsedDocumentViewer` internals → Task 7 extraction.
  - API client for `raw-payload` → Task 2.
  - All explicitly-deferred items (search, page sync, PDF preview, diff) — confirmed not implemented.
- **Type consistency:** `RawPayloadResponse.rawPayload` is `Record<string, unknown> | null` everywhere; `ParseRunListItem` reused for both list rows and the new single-run fetch (matches existing list endpoint).
- **Ambiguity guards:** Task 2's footnote and Task 8's `ReParseDialog`-prop note acknowledge two places where the implementation will need to look at the actual code and adapt — preferable to inventing prop or endpoint names that may not match.
- **Dependency:** Task 0 explicitly gates on Phase 1 having merged.
