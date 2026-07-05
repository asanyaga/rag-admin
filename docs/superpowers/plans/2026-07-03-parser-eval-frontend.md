# Parser Evaluation — Frontend (Plan 2 of 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the app UI for the parser-evaluation feature: author a benchmark case (pick a source document + per-page `text` ground truth), trigger a run over selected parsers, and view a persisted per-parser results comparison.

**Architecture:** Mirrors the existing evaluation frontend: `types/ → api/ → hooks/ → components/<feature>/ → pages/`, wired into `App.tsx` routing and `config/navigation.ts`. Uses the axios `apiClient` (base `/api/v1`), plain `useState`/`useEffect` hooks with 3s polling while a run is active (the codebase does NOT use react-query), and shadcn/ui + Tailwind. Consumes the backend from Plan 1 (PR #142).

**Tech Stack:** React 18, TypeScript, Vite, React Router v6 (`createBrowserRouter`), shadcn/ui, Tailwind, Vitest + Testing Library.

## Known deviation from the product vision (build as specified; revisit later)

The case form picks a raw **`SourceDocument`** and authors **raw-text** ground truth. Both are
deliberate first-slice conveniences, not the target shape. In the product vision, `Document`
(= the source_document that belongs to this project) and `ParsedDocument` are the first-class
primitives, and the picker + ground-truth authoring should ultimately bind to the project-scoped
`Document` primitive rather than a raw `SourceDocument`. Build the picker as specified here for now;
aligning it to `Document` is a future refactor gated on the Index→`ParsedDocument` work (see the
design spec's "Vision alignment & known deviations"). Do not attempt it in this plan.

## Global Constraints

- Backend contract (all under apiClient base `/api/v1`):
  - `POST /projects/{projectId}/parser-eval/cases` → `CaseResponse`
  - `GET  /projects/{projectId}/parser-eval/cases` → `CaseResponse[]`
  - `POST /projects/{projectId}/parser-eval/runs` → `RunResponse` (202)
  - `GET  /projects/{projectId}/parser-eval/runs` → `RunResponse[]`
  - `GET  /projects/{projectId}/parser-eval/runs/{runId}/results` → `ResultResponse[]`
- Response field names are snake_case exactly as the backend returns them (`doc_type`, `source_document_id`, `source_filename`, `case_id`, `latency_ms`, `error_message`, `created_at`). Do NOT rename to camelCase in the TS types — match the wire format.
- `text` ground truth payload is exactly `{ "pages": string[] }`. The backend rejects a run whose `parsers` are not valid `ParserKind` (422); only offer runnable parsers in the UI: `simple`, `docling`, `llamaparse`, `landing_ai`, `custom_pipeline`.
- `projectId` comes from `useProject()` (`currentProject.id`), not route params.
- Poll every 3000ms while a run is `pending`/`running`; stop on `completed`/`failed`.
- Follow existing patterns: `apiClient` from `@/api/client`, `ScorePill` from `@/components/evaluation/ScorePill`, tab-button styling from `pages/ExtractionEvaluationPage.tsx`.
- Commands: `cd frontend && npx vitest run <path>` (test), `npm run lint`, `npm run build`.

**Reference files to imitate (read before starting):**
- API module: `frontend/src/api/extractionEval.ts`; client: `frontend/src/api/client.ts`
- Hook + polling: `frontend/src/hooks/useExtractionEval.ts`
- Page + tabs: `frontend/src/pages/ExtractionEvaluationPage.tsx`
- Reusable score pill: `frontend/src/components/evaluation/ScorePill.tsx`
- Source docs: `frontend/src/api/sourceDocuments.ts`, `frontend/src/types/sourceDocument.ts`
- Routing: `frontend/src/App.tsx`; nav: `frontend/src/config/navigation.ts`
- Test utils: `frontend/src/test/test-utils`, and a component test e.g. `frontend/src/components/evaluation/EvalRunsTab.test.tsx`

---

## File Structure

- Create `frontend/src/types/parserEval.ts` — TS types matching the wire format.
- Create `frontend/src/api/parserEval.ts` (+ `.test.ts`) — 5 axios calls.
- Create `frontend/src/hooks/useParserEval.ts` (+ `.test.ts`) — cases/runs/results hooks with polling.
- Create `frontend/src/components/parser-eval/ParserEvalResultsTable.tsx` (+ `.test.tsx`) — parser × (case·dimension) table.
- Create `frontend/src/components/parser-eval/ParserEvalCasesTab.tsx` (+ `.test.tsx`) — list + new-case form.
- Create `frontend/src/components/parser-eval/ParserEvalRunsTab.tsx` — list runs + new-run form + expandable results.
- Create `frontend/src/pages/ParserEvaluationPage.tsx` — tabs Cases | Runs.
- Modify `frontend/src/App.tsx` — add `evaluation/parser` route.
- Modify `frontend/src/config/navigation.ts` — add Parser child under Evaluation.

---

## Task 1: Types + API module

**Files:**
- Create: `frontend/src/types/parserEval.ts`
- Create: `frontend/src/api/parserEval.ts`
- Test: `frontend/src/api/parserEval.test.ts`

**Interfaces:**
- Produces types `ParserEvalCase, CreateCaseRequest, ParserEvalTargetInput, ParserEvalRun, CreateRunRequest, ParserEvalResult, ParserEvalRunStatus, ParserEvalDimension`.
- Produces api fns: `createParserEvalCase(projectId, data)`, `listParserEvalCases(projectId)`, `createParserEvalRun(projectId, data)`, `listParserEvalRuns(projectId)`, `getParserEvalRunResults(projectId, runId)`.

- [ ] **Step 1: Write the types**

```typescript
// frontend/src/types/parserEval.ts
export type ParserEvalDimension = 'text'
export type ParserEvalRunStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface ParserEvalTargetInput {
  dimension: ParserEvalDimension
  expected: { pages: string[] }
}

export interface CreateCaseRequest {
  name: string
  doc_type?: string | null
  source_document_id: string
  targets: ParserEvalTargetInput[]
}

export interface ParserEvalCase {
  id: string
  name: string
  doc_type: string | null
  source_document_id: string
  source_filename: string | null
  created_at: string
}

export interface CreateRunRequest {
  name?: string | null
  case_ids: string[]
  parsers: string[]
}

export interface ParserEvalRun {
  id: string
  name: string
  status: ParserEvalRunStatus
  parsers: string[]
  error_message?: string | null
  created_at: string
}

export interface ParserEvalResult {
  case_id: string
  parser: string
  dimension: string
  score: number
  details: Record<string, unknown> | null
  cost: Record<string, unknown> | null
  latency_ms: number | null
}
```

- [ ] **Step 2: Write the failing API test**

```typescript
// frontend/src/api/parserEval.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import apiClient from './client'
import * as api from './parserEval'

vi.mock('./client')

const mockedPost = vi.mocked(apiClient.post)
const mockedGet = vi.mocked(apiClient.get)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('parserEval api', () => {
  it('createParserEvalCase posts to the project-scoped cases URL', async () => {
    mockedPost.mockResolvedValue({ data: { id: 'c1' } } as never)
    const body = {
      name: 'acme', source_document_id: 's1',
      targets: [{ dimension: 'text' as const, expected: { pages: ['hi'] } }],
    }
    const out = await api.createParserEvalCase('p1', body)
    expect(mockedPost).toHaveBeenCalledWith('/projects/p1/parser-eval/cases', body)
    expect(out).toEqual({ id: 'c1' })
  })

  it('listParserEvalCases gets the cases URL', async () => {
    mockedGet.mockResolvedValue({ data: [] } as never)
    await api.listParserEvalCases('p1')
    expect(mockedGet).toHaveBeenCalledWith('/projects/p1/parser-eval/cases')
  })

  it('createParserEvalRun posts the run body', async () => {
    mockedPost.mockResolvedValue({ data: { id: 'r1' } } as never)
    const body = { name: 'run', case_ids: ['c1'], parsers: ['docling'] }
    await api.createParserEvalRun('p1', body)
    expect(mockedPost).toHaveBeenCalledWith('/projects/p1/parser-eval/runs', body)
  })

  it('getParserEvalRunResults gets the run results URL', async () => {
    mockedGet.mockResolvedValue({ data: [] } as never)
    await api.getParserEvalRunResults('p1', 'r1')
    expect(mockedGet).toHaveBeenCalledWith('/projects/p1/parser-eval/runs/r1/results')
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/api/parserEval.test.ts`
Expected: FAIL — cannot resolve `./parserEval`.

- [ ] **Step 4: Write the API module**

```typescript
// frontend/src/api/parserEval.ts
import apiClient from './client'
import type {
  ParserEvalCase, CreateCaseRequest,
  ParserEvalRun, CreateRunRequest, ParserEvalResult,
} from '@/types/parserEval'

export async function createParserEvalCase(
  projectId: string, data: CreateCaseRequest,
): Promise<ParserEvalCase> {
  const res = await apiClient.post<ParserEvalCase>(`/projects/${projectId}/parser-eval/cases`, data)
  return res.data
}

export async function listParserEvalCases(projectId: string): Promise<ParserEvalCase[]> {
  const res = await apiClient.get<ParserEvalCase[]>(`/projects/${projectId}/parser-eval/cases`)
  return res.data
}

export async function createParserEvalRun(
  projectId: string, data: CreateRunRequest,
): Promise<ParserEvalRun> {
  const res = await apiClient.post<ParserEvalRun>(`/projects/${projectId}/parser-eval/runs`, data)
  return res.data
}

export async function listParserEvalRuns(projectId: string): Promise<ParserEvalRun[]> {
  const res = await apiClient.get<ParserEvalRun[]>(`/projects/${projectId}/parser-eval/runs`)
  return res.data
}

export async function getParserEvalRunResults(
  projectId: string, runId: string,
): Promise<ParserEvalResult[]> {
  const res = await apiClient.get<ParserEvalResult[]>(
    `/projects/${projectId}/parser-eval/runs/${runId}/results`)
  return res.data
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/api/parserEval.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/parserEval.ts frontend/src/api/parserEval.ts frontend/src/api/parserEval.test.ts
git commit -m "feat(parser-eval-ui): types + API client"
```

---

## Task 2: Hooks (cases, runs, results) with polling

**Files:**
- Create: `frontend/src/hooks/useParserEval.ts`
- Test: `frontend/src/hooks/useParserEval.test.ts`

**Interfaces:**
- Consumes `@/api/parserEval` (Task 1).
- Produces:
  - `useParserEvalCases(projectId: string | null) → { cases, isLoading, error, createCase, refetch }`
  - `useParserEvalRuns(projectId: string | null) → { runs, isLoading, error, createRun }` (polls while any run active)
  - `useParserEvalResults(projectId: string | null, runId: string | null, active: boolean) → { results, isLoading, error }` (polls while `active`)

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/hooks/useParserEval.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import * as api from '@/api/parserEval'
import { useParserEvalCases, useParserEvalRuns } from './useParserEval'

vi.mock('@/api/parserEval')

beforeEach(() => vi.clearAllMocks())

describe('useParserEvalCases', () => {
  it('loads cases for a project', async () => {
    vi.mocked(api.listParserEvalCases).mockResolvedValue([
      { id: 'c1', name: 'acme', doc_type: null, source_document_id: 's1',
        source_filename: 'a.pdf', created_at: '2026-07-03T00:00:00Z' },
    ])
    const { result } = renderHook(() => useParserEvalCases('p1'))
    await waitFor(() => expect(result.current.cases).toHaveLength(1))
    expect(result.current.cases[0].name).toBe('acme')
  })

  it('createCase prepends the new case', async () => {
    vi.mocked(api.listParserEvalCases).mockResolvedValue([])
    vi.mocked(api.createParserEvalCase).mockResolvedValue({
      id: 'c2', name: 'new', doc_type: null, source_document_id: 's1',
      source_filename: null, created_at: '2026-07-03T00:00:00Z',
    })
    const { result } = renderHook(() => useParserEvalCases('p1'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    await act(async () => {
      await result.current.createCase({
        name: 'new', source_document_id: 's1',
        targets: [{ dimension: 'text', expected: { pages: ['x'] } }],
      })
    })
    expect(result.current.cases[0].id).toBe('c2')
  })
})

describe('useParserEvalRuns', () => {
  it('loads runs for a project', async () => {
    vi.mocked(api.listParserEvalRuns).mockResolvedValue([
      { id: 'r1', name: 'run', status: 'completed', parsers: ['docling'],
        created_at: '2026-07-03T00:00:00Z' },
    ])
    const { result } = renderHook(() => useParserEvalRuns('p1'))
    await waitFor(() => expect(result.current.runs).toHaveLength(1))
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/hooks/useParserEval.test.ts`
Expected: FAIL — cannot resolve `./useParserEval`.

- [ ] **Step 3: Write the hooks** (mirror `useExtractionEval.ts` polling structure)

```typescript
// frontend/src/hooks/useParserEval.ts
import { useState, useCallback, useEffect, useRef } from 'react'
import * as api from '@/api/parserEval'
import type {
  ParserEvalCase, CreateCaseRequest,
  ParserEvalRun, CreateRunRequest, ParserEvalResult,
} from '@/types/parserEval'

const POLLING_INTERVAL = 3000

export function useParserEvalCases(projectId: string | null) {
  const [cases, setCases] = useState<ParserEvalCase[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    if (!projectId) { setCases([]); return }
    setIsLoading(true); setError(null)
    try {
      setCases(await api.listParserEvalCases(projectId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch cases')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createCase = useCallback(async (data: CreateCaseRequest): Promise<ParserEvalCase> => {
    if (!projectId) throw new Error('No project selected')
    const created = await api.createParserEvalCase(projectId, data)
    setCases((prev) => [created, ...prev])
    return created
  }, [projectId])

  useEffect(() => { if (projectId) refetch() }, [projectId, refetch])

  return { cases, isLoading, error, createCase, refetch }
}

export function useParserEvalRuns(projectId: string | null) {
  const [runs, setRuns] = useState<ParserEvalRun[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refetch = useCallback(async () => {
    if (!projectId) { setRuns([]); return }
    setIsLoading(true); setError(null)
    try {
      setRuns(await api.listParserEvalRuns(projectId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch runs')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createRun = useCallback(async (data: CreateRunRequest): Promise<ParserEvalRun> => {
    if (!projectId) throw new Error('No project selected')
    const created = await api.createParserEvalRun(projectId, data)
    setRuns((prev) => [created, ...prev])
    return created
  }, [projectId])

  useEffect(() => { if (projectId) refetch() }, [projectId, refetch])

  useEffect(() => {
    const active = runs.some((r) => r.status === 'pending' || r.status === 'running')
    if (active && projectId) {
      pollingRef.current = setInterval(async () => {
        try { setRuns(await api.listParserEvalRuns(projectId)) } catch { /* ignore */ }
      }, POLLING_INTERVAL)
    }
    return () => { if (pollingRef.current) clearInterval(pollingRef.current) }
  }, [runs, projectId])

  return { runs, isLoading, error, createRun }
}

export function useParserEvalResults(
  projectId: string | null, runId: string | null, active: boolean,
) {
  const [results, setResults] = useState<ParserEvalResult[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchResults = useCallback(async () => {
    if (!projectId || !runId) return
    setIsLoading(true); setError(null)
    try {
      setResults(await api.getParserEvalRunResults(projectId, runId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch results')
    } finally {
      setIsLoading(false)
    }
  }, [projectId, runId])

  useEffect(() => {
    if (!projectId || !runId) { setResults([]); return }
    fetchResults()
  }, [projectId, runId, fetchResults])

  useEffect(() => {
    if (active && projectId && runId) {
      pollingRef.current = setInterval(() => { fetchResults() }, POLLING_INTERVAL)
    }
    return () => { if (pollingRef.current) clearInterval(pollingRef.current) }
  }, [active, projectId, runId, fetchResults])

  return { results, isLoading, error }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/hooks/useParserEval.test.ts`
Expected: PASS (3 tests). If `renderHook` needs a wrapper, follow the pattern in an existing hook test.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useParserEval.ts frontend/src/hooks/useParserEval.test.ts
git commit -m "feat(parser-eval-ui): cases/runs/results hooks with polling"
```

---

## Task 3: Results comparison table

**Files:**
- Create: `frontend/src/components/parser-eval/ParserEvalResultsTable.tsx`
- Test: `frontend/src/components/parser-eval/ParserEvalResultsTable.test.tsx`

**Interfaces:**
- Consumes `ParserEvalResult` (Task 1), `ScorePill`.
- Produces `ParserEvalResultsTable({ results, caseNameById }: { results: ParserEvalResult[]; caseNameById?: Record<string,string> })`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/parser-eval/ParserEvalResultsTable.test.tsx
import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { render } from '@/test/test-utils'
import { ParserEvalResultsTable } from './ParserEvalResultsTable'

const results = [
  { case_id: 'c1', parser: 'docling', dimension: 'text', score: 0.97,
    details: {}, cost: {}, latency_ms: 890 },
  { case_id: 'c1', parser: 'custom_pipeline', dimension: 'text', score: 0.0,
    details: { capture_failed: true }, cost: null, latency_ms: null },
]

describe('ParserEvalResultsTable', () => {
  it('renders a row per result with parser and score', () => {
    render(<ParserEvalResultsTable results={results} caseNameById={{ c1: 'acme' }} />)
    expect(screen.getByText('docling')).toBeInTheDocument()
    expect(screen.getByText('97%')).toBeInTheDocument()
    expect(screen.getByText('acme')).toBeInTheDocument()
  })

  it('flags capture failures', () => {
    render(<ParserEvalResultsTable results={results} />)
    expect(screen.getByText(/failed/i)).toBeInTheDocument()
  })

  it('shows an empty state when there are no results', () => {
    render(<ParserEvalResultsTable results={[]} />)
    expect(screen.getByText(/no results/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/parser-eval/ParserEvalResultsTable.test.tsx`
Expected: FAIL — cannot resolve `./ParserEvalResultsTable`.

- [ ] **Step 3: Write the component**

```tsx
// frontend/src/components/parser-eval/ParserEvalResultsTable.tsx
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { ScorePill } from '@/components/evaluation/ScorePill'
import type { ParserEvalResult } from '@/types/parserEval'

interface Props {
  results: ParserEvalResult[]
  caseNameById?: Record<string, string>
}

function formatCost(cost: Record<string, unknown> | null): string {
  if (!cost) return '—'
  const usd = cost['usd']
  if (typeof usd === 'number') return `$${usd.toFixed(3)}`
  return Object.keys(cost).length === 0 ? '—' : JSON.stringify(cost)
}

function sortKey(r: ParserEvalResult): string {
  return `${r.case_id}|${r.dimension}|${r.parser}`
}

export function ParserEvalResultsTable({ results, caseNameById }: Props) {
  if (results.length === 0) {
    return <div className="text-sm text-muted-foreground py-6">No results yet.</div>
  }
  const rows = [...results].sort((a, b) => sortKey(a).localeCompare(sortKey(b)))
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Case</TableHead>
          <TableHead>Dimension</TableHead>
          <TableHead>Parser</TableHead>
          <TableHead className="text-right">Score</TableHead>
          <TableHead className="text-right">Latency</TableHead>
          <TableHead className="text-right">Cost</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => {
          const failed = Boolean(r.details && (r.details as Record<string, unknown>).capture_failed)
          return (
            <TableRow key={sortKey(r)}>
              <TableCell className="text-sm">
                {caseNameById?.[r.case_id] ?? r.case_id.slice(0, 8)}
              </TableCell>
              <TableCell className="text-sm">{r.dimension}</TableCell>
              <TableCell className="font-mono text-sm">{r.parser}</TableCell>
              <TableCell className="text-right">
                {failed
                  ? <span className="text-xs font-medium text-red-600">failed</span>
                  : <ScorePill score={r.score} />}
              </TableCell>
              <TableCell className="text-right font-mono text-sm">
                {r.latency_ms != null ? `${r.latency_ms} ms` : '—'}
              </TableCell>
              <TableCell className="text-right font-mono text-sm">{formatCost(r.cost)}</TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/parser-eval/ParserEvalResultsTable.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/parser-eval/ParserEvalResultsTable.tsx frontend/src/components/parser-eval/ParserEvalResultsTable.test.tsx
git commit -m "feat(parser-eval-ui): results comparison table"
```

---

## Task 4: Cases tab (list + new-case form)

**Files:**
- Create: `frontend/src/components/parser-eval/ParserEvalCasesTab.tsx`
- Test: `frontend/src/components/parser-eval/ParserEvalCasesTab.test.tsx`

**Interfaces:**
- Consumes `useParserEvalCases` (Task 2), `listSourceDocuments` (`@/api/sourceDocuments`), `SourceDocument` type.
- Produces `ParserEvalCasesTab({ projectId }: { projectId: string })`.

Behavior: shows existing cases (name, source filename, doc type, created). A "New case" form lets the user pick a source document (select from `listSourceDocuments()`), enter a name + optional doc type, and author the `text` ground truth as one textarea per page (Add page / Remove page). Submit builds `CreateCaseRequest` with a single `text` target `{ pages }` and calls `createCase`.

- [ ] **Step 1: Read `frontend/src/types/sourceDocument.ts`** to confirm `SourceDocument` has `id` and `filename`. Use those fields; if the display field differs, adapt.

- [ ] **Step 2: Write the failing test**

```tsx
// frontend/src/components/parser-eval/ParserEvalCasesTab.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '@/test/test-utils'
import { ParserEvalCasesTab } from './ParserEvalCasesTab'
import * as sourceApi from '@/api/sourceDocuments'
import { useParserEvalCases } from '@/hooks/useParserEval'

vi.mock('@/api/sourceDocuments')
vi.mock('@/hooks/useParserEval')

const createCase = vi.fn().mockResolvedValue({ id: 'c9' })

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(sourceApi.listSourceDocuments).mockResolvedValue([
    { id: 's1', filename: 'a.pdf' } as never,
  ])
  vi.mocked(useParserEvalCases).mockReturnValue({
    cases: [], isLoading: false, error: null, createCase, refetch: vi.fn(),
  } as never)
})

describe('ParserEvalCasesTab', () => {
  it('submits a case with a single text target built from page textareas', async () => {
    const user = userEvent.setup()
    render(<ParserEvalCasesTab projectId="p1" />)

    await user.click(await screen.findByRole('button', { name: /new case/i }))
    await user.type(screen.getByLabelText(/name/i), 'acme')
    // pick source document
    await user.selectOptions(screen.getByLabelText(/source document/i), 's1')
    // author page 1 text
    await user.type(screen.getByLabelText(/page 1/i), 'hello world')
    await user.click(screen.getByRole('button', { name: /create case/i }))

    expect(createCase).toHaveBeenCalledWith({
      name: 'acme',
      doc_type: null,
      source_document_id: 's1',
      targets: [{ dimension: 'text', expected: { pages: ['hello world'] } }],
    })
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/parser-eval/ParserEvalCasesTab.test.tsx`
Expected: FAIL — cannot resolve `./ParserEvalCasesTab`.

- [ ] **Step 4: Write the component**

```tsx
// frontend/src/components/parser-eval/ParserEvalCasesTab.tsx
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { useParserEvalCases } from '@/hooks/useParserEval'
import { listSourceDocuments } from '@/api/sourceDocuments'
import type { SourceDocument } from '@/types/sourceDocument'

export function ParserEvalCasesTab({ projectId }: { projectId: string }) {
  const { cases, isLoading, error, createCase } = useParserEvalCases(projectId)
  const [showForm, setShowForm] = useState(false)
  const [sources, setSources] = useState<SourceDocument[]>([])

  const [name, setName] = useState('')
  const [docType, setDocType] = useState('')
  const [sourceId, setSourceId] = useState('')
  const [pages, setPages] = useState<string[]>([''])
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    if (showForm && sources.length === 0) {
      listSourceDocuments().then(setSources).catch(() => setSources([]))
    }
  }, [showForm, sources.length])

  const resetForm = () => {
    setName(''); setDocType(''); setSourceId(''); setPages(['']); setFormError(null)
  }

  const submit = async () => {
    if (!name.trim() || !sourceId) { setFormError('Name and source document are required.'); return }
    setSubmitting(true); setFormError(null)
    try {
      await createCase({
        name: name.trim(),
        doc_type: docType.trim() || null,
        source_document_id: sourceId,
        targets: [{ dimension: 'text', expected: { pages } }],
      })
      resetForm(); setShowForm(false)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to create case')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setShowForm((s) => !s)}>
          {showForm ? 'Cancel' : 'New case'}
        </Button>
      </div>

      {showForm && (
        <div className="rounded-md border p-4 space-y-4">
          <div className="space-y-1">
            <label htmlFor="pe-name" className="text-sm font-medium">Name</label>
            <Input id="pe-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <label htmlFor="pe-doctype" className="text-sm font-medium">Doc type (optional)</label>
            <Input id="pe-doctype" value={docType} onChange={(e) => setDocType(e.target.value)} />
          </div>
          <div className="space-y-1">
            <label htmlFor="pe-source" className="text-sm font-medium">Source document</label>
            <select
              id="pe-source"
              aria-label="Source document"
              className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
            >
              <option value="">Select a document…</option>
              {sources.map((s) => (
                <option key={s.id} value={s.id}>{s.filename}</option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <div className="text-sm font-medium">Text ground truth (per page)</div>
            {pages.map((p, i) => (
              <div key={i} className="space-y-1">
                <label htmlFor={`pe-page-${i}`} className="text-xs text-muted-foreground">
                  Page {i + 1}
                </label>
                <Textarea
                  id={`pe-page-${i}`}
                  value={p}
                  onChange={(e) =>
                    setPages((prev) => prev.map((v, j) => (j === i ? e.target.value : v)))}
                />
                {pages.length > 1 && (
                  <Button variant="ghost" size="sm"
                    onClick={() => setPages((prev) => prev.filter((_, j) => j !== i))}>
                    Remove page
                  </Button>
                )}
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setPages((prev) => [...prev, ''])}>
              Add page
            </Button>
          </div>

          {formError && <div className="text-sm text-red-600">{formError}</div>}
          <div className="flex justify-end">
            <Button onClick={submit} disabled={submitting}>
              {submitting ? 'Creating…' : 'Create case'}
            </Button>
          </div>
        </div>
      )}

      {error && <div className="text-sm text-red-600">{error}</div>}
      {isLoading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : cases.length === 0 ? (
        <div className="text-sm text-muted-foreground">No cases yet.</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Doc type</TableHead>
              <TableHead>Source</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cases.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="text-sm">{c.name}</TableCell>
                <TableCell className="text-sm">{c.doc_type ?? '—'}</TableCell>
                <TableCell className="text-sm">{c.source_filename ?? '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/parser-eval/ParserEvalCasesTab.test.tsx`
Expected: PASS. If `Textarea` isn't at `@/components/ui/textarea`, confirm the path (`ls frontend/src/components/ui`).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/parser-eval/ParserEvalCasesTab.tsx frontend/src/components/parser-eval/ParserEvalCasesTab.test.tsx
git commit -m "feat(parser-eval-ui): cases tab with per-page text authoring"
```

---

## Task 5: Runs tab (list + new-run form + expandable results)

**Files:**
- Create: `frontend/src/components/parser-eval/ParserEvalRunsTab.tsx`
- Test: `frontend/src/components/parser-eval/ParserEvalRunsTab.test.tsx`

**Interfaces:**
- Consumes `useParserEvalRuns`, `useParserEvalCases`, `useParserEvalResults` (Task 2), `ParserEvalResultsTable` (Task 3).
- Produces `ParserEvalRunsTab({ projectId }: { projectId: string })`.

Behavior: a "New run" form with case checkboxes (from cases) + parser checkboxes (the 5 runnable parsers) → `createRun`. A list of runs with status. Selecting a run renders `ParserEvalResultsTable` below, polling while that run is active.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/parser-eval/ParserEvalRunsTab.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '@/test/test-utils'
import { ParserEvalRunsTab } from './ParserEvalRunsTab'
import { useParserEvalRuns, useParserEvalCases, useParserEvalResults } from '@/hooks/useParserEval'

vi.mock('@/hooks/useParserEval')

const createRun = vi.fn().mockResolvedValue({ id: 'r9' })

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useParserEvalCases).mockReturnValue({
    cases: [{ id: 'c1', name: 'acme', doc_type: null, source_document_id: 's1',
      source_filename: 'a.pdf', created_at: '2026-07-03T00:00:00Z' }],
    isLoading: false, error: null, createCase: vi.fn(), refetch: vi.fn(),
  } as never)
  vi.mocked(useParserEvalRuns).mockReturnValue({
    runs: [{ id: 'r1', name: 'run', status: 'completed', parsers: ['docling'],
      created_at: '2026-07-03T00:00:00Z' }],
    isLoading: false, error: null, createRun,
  } as never)
  vi.mocked(useParserEvalResults).mockReturnValue({
    results: [], isLoading: false, error: null,
  } as never)
})

describe('ParserEvalRunsTab', () => {
  it('creates a run from selected cases and parsers', async () => {
    const user = userEvent.setup()
    render(<ParserEvalRunsTab projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: /new run/i }))
    await user.click(screen.getByLabelText(/acme/i))          // case checkbox
    await user.click(screen.getByLabelText('docling'))         // parser checkbox
    await user.click(screen.getByRole('button', { name: /start run/i }))
    expect(createRun).toHaveBeenCalledWith(
      expect.objectContaining({ case_ids: ['c1'], parsers: ['docling'] }),
    )
  })

  it('lists runs with status', () => {
    render(<ParserEvalRunsTab projectId="p1" />)
    expect(screen.getByText('completed')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/parser-eval/ParserEvalRunsTab.test.tsx`
Expected: FAIL — cannot resolve `./ParserEvalRunsTab`.

- [ ] **Step 3: Write the component**

```tsx
// frontend/src/components/parser-eval/ParserEvalRunsTab.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  useParserEvalRuns, useParserEvalCases, useParserEvalResults,
} from '@/hooks/useParserEval'
import { ParserEvalResultsTable } from './ParserEvalResultsTable'

const RUNNABLE_PARSERS = ['simple', 'docling', 'llamaparse', 'landing_ai', 'custom_pipeline']

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

export function ParserEvalRunsTab({ projectId }: { projectId: string }) {
  const { cases } = useParserEvalCases(projectId)
  const { runs, error, createRun } = useParserEvalRuns(projectId)

  const [showForm, setShowForm] = useState(false)
  const [selectedCases, setSelectedCases] = useState<string[]>([])
  const [selectedParsers, setSelectedParsers] = useState<string[]>([])
  const [name, setName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [openRunId, setOpenRunId] = useState<string | null>(null)
  const openRun = runs.find((r) => r.id === openRunId) ?? null
  const active = openRun?.status === 'pending' || openRun?.status === 'running'
  const { results } = useParserEvalResults(projectId, openRunId, active)
  const caseNameById = Object.fromEntries(cases.map((c) => [c.id, c.name]))

  const submit = async () => {
    if (selectedCases.length === 0 || selectedParsers.length === 0) {
      setFormError('Select at least one case and one parser.'); return
    }
    setSubmitting(true); setFormError(null)
    try {
      await createRun({
        name: name.trim() || null,
        case_ids: selectedCases,
        parsers: selectedParsers,
      })
      setShowForm(false); setSelectedCases([]); setSelectedParsers([]); setName('')
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to start run')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setShowForm((s) => !s)}>{showForm ? 'Cancel' : 'New run'}</Button>
      </div>

      {showForm && (
        <div className="rounded-md border p-4 space-y-4">
          <div>
            <div className="text-sm font-medium mb-2">Cases</div>
            {cases.length === 0
              ? <div className="text-sm text-muted-foreground">No cases — create one first.</div>
              : cases.map((c) => (
                <label key={c.id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={selectedCases.includes(c.id)}
                    onChange={() => setSelectedCases((prev) => toggle(prev, c.id))} />
                  {c.name}
                </label>
              ))}
          </div>
          <div>
            <div className="text-sm font-medium mb-2">Parsers</div>
            {RUNNABLE_PARSERS.map((p) => (
              <label key={p} className="flex items-center gap-2 text-sm">
                <input type="checkbox" aria-label={p} checked={selectedParsers.includes(p)}
                  onChange={() => setSelectedParsers((prev) => toggle(prev, p))} />
                {p}
              </label>
            ))}
          </div>
          {formError && <div className="text-sm text-red-600">{formError}</div>}
          <div className="flex justify-end">
            <Button onClick={submit} disabled={submitting}>
              {submitting ? 'Starting…' : 'Start run'}
            </Button>
          </div>
        </div>
      )}

      {error && <div className="text-sm text-red-600">{error}</div>}
      {runs.length === 0 ? (
        <div className="text-sm text-muted-foreground">No runs yet.</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Parsers</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {runs.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="text-sm">{r.name}</TableCell>
                <TableCell className="text-sm">{r.status}</TableCell>
                <TableCell className="font-mono text-xs">{r.parsers.join(', ')}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="sm"
                    onClick={() => setOpenRunId((id) => (id === r.id ? null : r.id))}>
                    {openRunId === r.id ? 'Hide' : 'Results'}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {openRun && (
        <div className="rounded-md border p-4">
          <div className="text-sm font-medium mb-2">Results — {openRun.name}</div>
          <ParserEvalResultsTable results={results} caseNameById={caseNameById} />
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/parser-eval/ParserEvalRunsTab.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/parser-eval/ParserEvalRunsTab.tsx frontend/src/components/parser-eval/ParserEvalRunsTab.test.tsx
git commit -m "feat(parser-eval-ui): runs tab with new-run form and expandable results"
```

---

## Task 6: Page + routing + navigation

**Files:**
- Create: `frontend/src/pages/ParserEvaluationPage.tsx`
- Modify: `frontend/src/App.tsx` (import + route)
- Modify: `frontend/src/config/navigation.ts` (nav child)

**Interfaces:**
- Consumes `ParserEvalCasesTab` (Task 4), `ParserEvalRunsTab` (Task 5), `useProject`.

- [ ] **Step 1: Write the page** (mirror `ExtractionEvaluationPage.tsx`)

```tsx
// frontend/src/pages/ParserEvaluationPage.tsx
import { useState } from 'react'
import { useProject } from '@/contexts/ProjectContext'
import { cn } from '@/lib/utils'
import { ParserEvalCasesTab } from '@/components/parser-eval/ParserEvalCasesTab'
import { ParserEvalRunsTab } from '@/components/parser-eval/ParserEvalRunsTab'

type Tab = 'cases' | 'runs'

export default function ParserEvaluationPage(): JSX.Element {
  const { currentProject } = useProject()
  const [activeTab, setActiveTab] = useState<Tab>('cases')

  if (!currentProject) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        Select a project to manage parser evaluation.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Parser Evaluation</h1>
        <p className="text-muted-foreground">
          Compare parsers against per-dimension ground truth.
        </p>
      </div>

      <div className="inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground">
        <button
          onClick={() => setActiveTab('cases')}
          className={cn(
            'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all',
            activeTab === 'cases' && 'bg-background text-foreground shadow-sm')}
        >
          Cases
        </button>
        <button
          onClick={() => setActiveTab('runs')}
          className={cn(
            'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all',
            activeTab === 'runs' && 'bg-background text-foreground shadow-sm')}
        >
          Runs
        </button>
      </div>

      <div className={activeTab !== 'cases' ? 'hidden' : undefined}>
        <ParserEvalCasesTab projectId={currentProject.id} />
      </div>
      <div className={activeTab !== 'runs' ? 'hidden' : undefined}>
        <ParserEvalRunsTab projectId={currentProject.id} />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Register the route in `App.tsx`**

Add the import near the other page imports:
```typescript
import ParserEvaluationPage from './pages/ParserEvaluationPage'
```
Add a route child immediately after the `evaluation/extraction` route (around line 189):
```tsx
{
  path: 'evaluation/parser',
  element: <ParserEvaluationPage />,
  handle: { breadcrumb: 'Parser Evaluation' },
},
```

- [ ] **Step 3: Add the nav child in `config/navigation.ts`**

In the `Evaluation` entry's `children` array (currently `Retrieval`, `Extraction`), add:
```typescript
{ label: 'Parser', href: '/evaluation/parser' },
```

- [ ] **Step 4: Verify build, lint, and the full parser-eval test set**

Run: `cd frontend && npx vitest run src/api/parserEval.test.ts src/hooks/useParserEval.test.ts src/components/parser-eval/`
Expected: all PASS.
Run: `cd frontend && npm run lint`
Expected: no new errors in the added files.
Run: `cd frontend && npm run build`
Expected: type-checks and builds clean (this catches route/import wiring errors).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ParserEvaluationPage.tsx frontend/src/App.tsx frontend/src/config/navigation.ts
git commit -m "feat(parser-eval-ui): page, route, and navigation entry"
```

---

## Self-Review (completed against the spec)

- **Spec coverage:** author a case (source doc + per-page `text` truth) → Task 4 ✔; select cases + parsers, run → Task 5 ✔; persisted per-parser comparison table with score + cost + latency → Task 3 ✔; capture-failure shown (not hidden) → Task 3 ✔; polling while running → Task 2 ✔; page in the app under Evaluation → Task 6 ✔. Uses `ScorePill` (reuse) ✔.
- **Wire-format consistency:** TS types use snake_case matching the backend (`doc_type`, `source_document_id`, `source_filename`, `case_id`, `latency_ms`, `error_message`). `text` truth is `{ pages: string[] }` in the type, the case form, and the API test.
- **Parser list:** only the 5 runnable parsers are offered (matches backend runners; avoids the ParserKind-without-runner failure).
- **Type consistency:** `createCase`/`createRun`/results signatures match between hooks (Task 2), the API (Task 1), and the components (Tasks 4–5). `ParserEvalResultsTable` prop `caseNameById` is produced in the Runs tab from the cases list.
- **Placeholder scan:** no TBD/TODO; every step has concrete code + commands.

## Notes / confirm-at-implementation
- Confirm shadcn component paths: `@/components/ui/{button,input,textarea,table}`. If `textarea` doesn't exist, use a styled native `<textarea>`.
- Confirm `SourceDocument` fields (`id`, `filename`) in `frontend/src/types/sourceDocument.ts` (Task 4 Step 1).
- If `renderHook`/`render` need a specific wrapper/provider, follow `frontend/src/test/test-utils` and an existing hook/component test.
- Backend must be running (and the migration applied to Postgres) for the UI to work end-to-end in a live app; the tests here mock the API and don't require it.
- **Vision deviation (see the callout after Tech Stack):** the source picker uses raw `SourceDocument` and raw-text ground truth as first-slice conveniences; the target shape binds to the project-scoped `Document`/`ParsedDocument` primitive. Build as specified; realign in a later refactor.
