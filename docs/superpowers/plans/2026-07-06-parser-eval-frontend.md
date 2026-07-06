# Parser Eval Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a thin end-to-end UI for parser eval — author `text` ground-truth cases, launch adapter-comparison runs, and read a per-parser metric table — at `/evaluation/parser`.

**Architecture:** Follows the peer extraction-eval frontend: `api/*.ts` → `types/*.ts` → hand-rolled `hooks/use*.ts` (useState/useEffect + setInterval polling) → `pages/` + feature `components/parser-eval/`. Reuses `ScorePill`, `MetricCard`, `EvalStatusBadge`, `useSourceDocuments`, and `PARSER_REGISTRY`. One backend prerequisite: conform parser-eval DTOs to camelCase + add a get-one-run route.

**Tech Stack:** React 18 + TypeScript + Vite, shadcn/ui + Tailwind, axios (`apiClient`, base `/api/v1`), Vitest + React Testing Library. Backend: FastAPI + Pydantic v2.

## Global Constraints

- **camelCase JSON everywhere** — backend DTOs use per-field `alias="camelCase"` + `ConfigDict(populate_by_name=True)`; frontend types are camelCase with no boundary mapping (matches `app/schemas/extraction_eval.py` / `types/extractionEval.ts`).
- **Hooks are hand-rolled** (useState/useEffect/useCallback + `setInterval`), mirroring `hooks/useExtractionEval.ts`. Not react-query.
- **Only `text` dimension ships.** Datasets UI, `(adapter,config)` editor, bootstrap, verification, delete/edit are deferred seams.
- Frontend commands: `cd frontend && npm run lint`, `npm run build`, `npx vitest run <path>`. Backend: `cd backend && uv run python -m pytest -o "addopts=" <path> -v`.
- Branch: `feat/parser-eval-frontend`. Commit after each green task. Trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Spec: `docs/superpowers/specs/2026-07-06-parser-eval-frontend-design.md`.

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/schemas/parser_eval.py` (modify) | camelCase aliases on all DTOs |
| `backend/app/routers/parser_eval.py` (modify) | add `GET .../runs/{run_id}` |
| `backend/tests/routers/test_parser_eval_router.py` (modify) | camelCase response reads + get-run test |
| `frontend/src/types/parserEval.ts` (create) | TS interfaces mirroring DTOs |
| `frontend/src/api/parserEval.ts` (create) | axios endpoint functions |
| `frontend/src/hooks/useParserEval.ts` (create) | cases/runs/run-detail hooks + polling |
| `frontend/src/config/navigation.ts` (modify) | add "Parsing" nav child |
| `frontend/src/App.tsx` (modify) | register 2 routes |
| `frontend/src/pages/ParserEvaluationPage.tsx` (create) | tabbed shell (Cases/Runs) |
| `frontend/src/components/parser-eval/ParserEvalCasesTab.tsx` (create) | cases list + New Case |
| `frontend/src/components/parser-eval/CaseEditorDialog.tsx` (create) | author per-page ground truth |
| `frontend/src/components/parser-eval/ParserEvalRunsTab.tsx` (create) | runs list + New Run |
| `frontend/src/components/parser-eval/NewRunDialog.tsx` (create) | pick cases + adapters |
| `frontend/src/components/parser-eval/ParserComparisonTable.tsx` (create) | grouped comparison table |
| `frontend/src/pages/ParserEvalRunDetailPage.tsx` (create) | run header + poll + table |

---

### Task 1: Backend prerequisites (camelCase DTOs + get-one-run route)

**Files:**
- Modify: `backend/app/schemas/parser_eval.py`
- Modify: `backend/app/routers/parser_eval.py`
- Modify: `backend/tests/routers/test_parser_eval_router.py`

**Interfaces:**
- Produces: parser-eval endpoints return camelCase JSON; new `GET /projects/{pid}/parser-eval/runs/{runId}` → `RunResponse`.

- [ ] **Step 1: Update the router test to camelCase reads + add the get-run assertion**

In `test_parser_eval_router.py`, within `test_dataset_run_snapshot_flow`: change `r.json()["review_status"]` → `r.json()["reviewStatus"]`; change the results assertions to `results[0]["metrics"]["similarity"]` (unchanged), `results[0]["primaryMetric"] == "similarity"`, `results[0]["variantKey"].startswith("docling@")`. After fetching results, also assert the new route:

```python
        # get-one-run route (used by the run-detail page)
        r = await client.get(f"/api/v1/projects/{project_id}/parser-eval/runs/{run_id}")
        assert r.status_code == 200
        assert r.json()["id"] == run_id
        assert r.json()["status"] in ("pending", "running", "completed")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/routers/test_parser_eval_router.py -v`
Expected: FAIL (`reviewStatus` KeyError; get-run route 404/405).

- [ ] **Step 3: Add camelCase aliases to the schemas**

Rewrite `backend/app/schemas/parser_eval.py` field declarations to add aliases + `populate_by_name`:

```python
"""Pydantic schemas for the parser-eval API (canonical model, camelCase JSON)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.cdm.models import ParserKind

_CAMEL = ConfigDict(populate_by_name=True)
_CAMEL_ORM = ConfigDict(from_attributes=True, populate_by_name=True)


class CaseCreate(BaseModel):
    source_document_id: UUID = Field(..., alias="sourceDocumentId")
    dimension: str
    expected: dict
    source_method: str | None = Field(None, alias="sourceMethod")
    review_status: str | None = Field(None, alias="reviewStatus")

    model_config = _CAMEL

    @model_validator(mode="after")
    def _validate_expected(self):
        if self.dimension == "text":
            pages = self.expected.get("pages")
            if not isinstance(pages, list) or not all(isinstance(p, str) for p in pages):
                raise ValueError("text case requires expected.pages: list[str]")
        return self


class CaseResponse(BaseModel):
    id: UUID
    source_document_id: UUID = Field(..., alias="sourceDocumentId")
    dimension: str
    source_method: str = Field(..., alias="sourceMethod")
    review_status: str = Field(..., alias="reviewStatus")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = _CAMEL_ORM


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None
    model_config = _CAMEL


class DatasetResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime = Field(..., alias="createdAt")
    model_config = _CAMEL_ORM


class VariantInput(BaseModel):
    adapter: str
    config: dict = {}
    model_config = _CAMEL

    @field_validator("adapter")
    @classmethod
    def _validate_adapter(cls, value: str) -> str:
        valid = {p.value for p in ParserKind}
        if value not in valid:
            raise ValueError(f"Invalid adapter '{value}'. Valid: {sorted(valid)}")
        return value


class RunCreate(BaseModel):
    name: str | None = None
    variants: list[VariantInput]
    eval_case_ids: list[UUID] = Field(default_factory=list, alias="evalCaseIds")
    dataset_id: UUID | None = Field(None, alias="datasetId")
    model_config = _CAMEL


class RunResponse(BaseModel):
    id: UUID
    name: str
    status: str
    variants: list[dict]
    dataset_id: UUID | None = Field(None, alias="datasetId")
    error_message: str | None = Field(None, alias="errorMessage")
    created_at: datetime = Field(..., alias="createdAt")
    model_config = _CAMEL_ORM


class ResultResponse(BaseModel):
    eval_case_id: UUID = Field(..., alias="evalCaseId")
    adapter: str
    config: dict
    variant_key: str = Field(..., alias="variantKey")
    metrics: dict
    primary_metric: str | None = Field(None, alias="primaryMetric")
    details: dict | None
    cost: dict | None
    latency_ms: int | None = Field(None, alias="latencyMs")
    model_config = _CAMEL_ORM
```

- [ ] **Step 4: Add the get-one-run route**

In `backend/app/routers/parser_eval.py`, add before the `get_results` route:

```python
@router.get("/projects/{project_id}/parser-eval/runs/{run_id}", response_model=RunResponse)
async def get_run(
    project_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.get_run(run_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 5: Run backend parser-eval suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests -k parser_eval -v`
Expected: PASS (service/repo/schema tests use field names via `populate_by_name`; router test now reads camelCase + get-run).

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/parser_eval.py backend/app/routers/parser_eval.py backend/tests/routers/test_parser_eval_router.py
git commit -m "feat(parser-eval): camelCase DTO aliases + get-one-run route (frontend prereq)"
```

---

### Task 2: Frontend plumbing — types, api, hooks

**Files:**
- Create: `frontend/src/types/parserEval.ts`
- Create: `frontend/src/api/parserEval.ts`
- Create: `frontend/src/hooks/useParserEval.ts`

**Interfaces:**
- Produces: types `ParserEvalCase`, `ParserEvalRun`, `ParserEvalResult`, `CreateCaseRequest`, `CreateRunRequest`; api fns `listCases/createCase/listRuns/createRun/getRun/getRunResults`; hooks `useParserEvalCases(projectId)`, `useParserEvalRuns(projectId)`, `useParserEvalRunDetail(projectId, runId)`.

- [ ] **Step 1: Create the types**

`frontend/src/types/parserEval.ts`:

```ts
export type ParserEvalRunStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface ParserEvalCase {
  id: string
  sourceDocumentId: string
  dimension: string
  sourceMethod: string
  reviewStatus: string
  createdAt: string
}

export interface ParserEvalVariant {
  adapter: string
  config: Record<string, unknown>
}

export interface ParserEvalRun {
  id: string
  name: string
  status: ParserEvalRunStatus
  variants: ParserEvalVariant[]
  datasetId: string | null
  errorMessage: string | null
  createdAt: string
}

export interface ParserEvalResult {
  evalCaseId: string
  adapter: string
  config: Record<string, unknown>
  variantKey: string
  metrics: Record<string, number>
  primaryMetric: string | null
  details: Record<string, unknown> | null
  cost: Record<string, number> | null
  latencyMs: number | null
}

export interface CreateCaseRequest {
  sourceDocumentId: string
  dimension: string
  expected: { pages: string[] }
}

export interface CreateRunRequest {
  name?: string
  variants: ParserEvalVariant[]
  evalCaseIds: string[]
}
```

- [ ] **Step 2: Create the api module**

`frontend/src/api/parserEval.ts`:

```ts
import apiClient from './client'
import type {
  ParserEvalCase, ParserEvalRun, ParserEvalResult,
  CreateCaseRequest, CreateRunRequest,
} from '@/types/parserEval'

export async function listCases(projectId: string): Promise<ParserEvalCase[]> {
  const r = await apiClient.get<ParserEvalCase[]>(`/projects/${projectId}/parser-eval/cases`)
  return r.data
}

export async function createCase(projectId: string, data: CreateCaseRequest): Promise<ParserEvalCase> {
  const r = await apiClient.post<ParserEvalCase>(`/projects/${projectId}/parser-eval/cases`, data)
  return r.data
}

export async function listRuns(projectId: string): Promise<ParserEvalRun[]> {
  const r = await apiClient.get<ParserEvalRun[]>(`/projects/${projectId}/parser-eval/runs`)
  return r.data
}

export async function createRun(projectId: string, data: CreateRunRequest): Promise<ParserEvalRun> {
  const r = await apiClient.post<ParserEvalRun>(`/projects/${projectId}/parser-eval/runs`, data)
  return r.data
}

export async function getRun(projectId: string, runId: string): Promise<ParserEvalRun> {
  const r = await apiClient.get<ParserEvalRun>(`/projects/${projectId}/parser-eval/runs/${runId}`)
  return r.data
}

export async function getRunResults(projectId: string, runId: string): Promise<ParserEvalResult[]> {
  const r = await apiClient.get<ParserEvalResult[]>(`/projects/${projectId}/parser-eval/runs/${runId}/results`)
  return r.data
}
```

- [ ] **Step 3: Create the hooks**

`frontend/src/hooks/useParserEval.ts` (mirrors `useExtractionEval.ts`):

```ts
import { useState, useCallback, useEffect, useRef } from 'react'
import type {
  ParserEvalCase, ParserEvalRun, ParserEvalResult,
  CreateCaseRequest, CreateRunRequest,
} from '@/types/parserEval'
import * as api from '@/api/parserEval'

const POLLING_INTERVAL = 3000

export function useParserEvalCases(projectId: string | null) {
  const [cases, setCases] = useState<ParserEvalCase[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchCases = useCallback(async () => {
    if (!projectId) { setCases([]); return }
    setIsLoading(true); setError(null)
    try {
      setCases(await api.listCases(projectId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cases')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createCase = useCallback(async (data: CreateCaseRequest): Promise<ParserEvalCase> => {
    if (!projectId) throw new Error('No project selected')
    const created = await api.createCase(projectId, data)
    setCases((prev) => [created, ...prev])
    return created
  }, [projectId])

  useEffect(() => { if (projectId) fetchCases() }, [projectId, fetchCases])

  return { cases, isLoading, error, fetchCases, createCase }
}

export function useParserEvalRuns(projectId: string | null) {
  const [runs, setRuns] = useState<ParserEvalRun[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchRuns = useCallback(async () => {
    if (!projectId) { setRuns([]); return }
    setIsLoading(true); setError(null)
    try {
      setRuns(await api.listRuns(projectId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load runs')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createRun = useCallback(async (data: CreateRunRequest): Promise<ParserEvalRun> => {
    if (!projectId) throw new Error('No project selected')
    const run = await api.createRun(projectId, data)
    setRuns((prev) => [run, ...prev])
    return run
  }, [projectId])

  useEffect(() => { if (projectId) fetchRuns() }, [projectId, fetchRuns])

  useEffect(() => {
    const active = runs.some((r) => r.status === 'pending' || r.status === 'running')
    if (active && projectId) {
      pollingRef.current = setInterval(async () => {
        try { setRuns(await api.listRuns(projectId)) } catch { /* ignore */ }
      }, POLLING_INTERVAL)
    }
    return () => { if (pollingRef.current) clearInterval(pollingRef.current) }
  }, [runs, projectId])

  return { runs, isLoading, error, fetchRuns, createRun }
}

export function useParserEvalRunDetail(projectId: string | null, runId: string | null) {
  const [run, setRun] = useState<ParserEvalRun | null>(null)
  const [results, setResults] = useState<ParserEvalResult[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!projectId || !runId) { setRun(null); setResults([]); return }
    let cancelled = false
    ;(async () => {
      setIsLoading(true); setError(null)
      try {
        const runData = await api.getRun(projectId, runId)
        if (cancelled) return
        setRun(runData)
        if (runData.status === 'completed') {
          setResults(await api.getRunResults(projectId, runId))
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load run')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [projectId, runId])

  useEffect(() => {
    if (run && (run.status === 'pending' || run.status === 'running') && projectId && runId) {
      pollingRef.current = setInterval(async () => {
        try {
          const runData = await api.getRun(projectId, runId)
          setRun(runData)
          if (runData.status === 'completed' || runData.status === 'failed') {
            setResults(await api.getRunResults(projectId, runId))
          }
        } catch { /* ignore */ }
      }, POLLING_INTERVAL)
    }
    return () => { if (pollingRef.current) clearInterval(pollingRef.current) }
  }, [run, projectId, runId])

  return { run, results, isLoading, error }
}
```

- [ ] **Step 4: Verify types compile + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: PASS (tsc resolves all types; no lint errors). This is the verification for pure-plumbing modules (matches the codebase — `useExtractionEval` has no unit test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/parserEval.ts frontend/src/api/parserEval.ts frontend/src/hooks/useParserEval.ts
git commit -m "feat(parser-eval-fe): types, api, and polling hooks"
```

---

### Task 3: Page shell, routing, and nav

**Files:**
- Create: `frontend/src/pages/ParserEvaluationPage.tsx`
- Create: `frontend/src/pages/ParserEvaluationPage.test.tsx`
- Modify: `frontend/src/config/navigation.ts`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `ParserEvalCasesTab`, `ParserEvalRunsTab` (Tasks 4–5 — placeholder imports resolve once those land; this task mocks them in its test).
- Produces: route `/evaluation/parser` → `ParserEvaluationPage`; nav child "Parsing".

- [ ] **Step 1: Write the page test**

`frontend/src/pages/ParserEvaluationPage.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ParserEvaluationPage from './ParserEvaluationPage'

vi.mock('@/contexts/ProjectContext', () => ({
  useProject: () => ({ currentProject: { id: 'proj-1', name: 'Test Project' } }),
}))
vi.mock('@/components/parser-eval/ParserEvalCasesTab', () => ({
  ParserEvalCasesTab: () => <div>cases-tab</div>,
}))
vi.mock('@/components/parser-eval/ParserEvalRunsTab', () => ({
  ParserEvalRunsTab: () => <div>runs-tab</div>,
}))

describe('ParserEvaluationPage', () => {
  it('renders heading and both tabs', () => {
    render(<MemoryRouter><ParserEvaluationPage /></MemoryRouter>)
    expect(screen.getByText('Parser Evaluation')).toBeInTheDocument()
    expect(screen.getByText('Cases')).toBeInTheDocument()
    expect(screen.getByText('Runs')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/pages/ParserEvaluationPage.test.tsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Create the page (tab pattern copied from `ExtractionEvaluationPage`)**

`frontend/src/pages/ParserEvaluationPage.tsx`:

```tsx
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

  const tabBtn = (tab: Tab, label: string) => (
    <button
      onClick={() => setActiveTab(tab)}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all',
        activeTab === tab && 'bg-background text-foreground shadow-sm'
      )}
    >
      {label}
    </button>
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Parser Evaluation</h1>
        <p className="text-muted-foreground">
          Compare parsers against ground truth on quality, cost, and latency.
        </p>
      </div>

      <div className="inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground">
        {tabBtn('cases', 'Cases')}
        {tabBtn('runs', 'Runs')}
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

- [ ] **Step 4: Add the nav child**

In `frontend/src/config/navigation.ts`, add to the Evaluation item's `children`:

```ts
    children: [
      { label: 'Retrieval', href: '/evaluation/retrieval' },
      { label: 'Extraction', href: '/evaluation/extraction' },
      { label: 'Parsing', href: '/evaluation/parser' },
    ],
```

- [ ] **Step 5: Register the routes**

In `frontend/src/App.tsx`: add the import `import ParserEvaluationPage from './pages/ParserEvaluationPage'` and `import ParserEvalRunDetailPage from './pages/ParserEvalRunDetailPage'` (the latter file lands in Task 6; add the import in Task 6 to avoid a broken build here — for THIS task add only the `ParserEvaluationPage` import and route). Add after the `evaluation/extraction` route:

```tsx
          {
            path: 'evaluation/parser',
            element: <ParserEvaluationPage />,
            handle: { breadcrumb: 'Parser Evaluation' },
          },
```

- [ ] **Step 6: Run test + build**

Run: `cd frontend && npx vitest run src/pages/ParserEvaluationPage.test.tsx && npm run build`
Expected: test PASS. Build will FAIL only if the Task 4/5 tab components don't exist yet — create empty stubs to unblock the build:

`frontend/src/components/parser-eval/ParserEvalCasesTab.tsx` and `ParserEvalRunsTab.tsx` temporary stubs:

```tsx
export function ParserEvalCasesTab({ projectId }: { projectId: string }) { void projectId; return null }
```
```tsx
export function ParserEvalRunsTab({ projectId }: { projectId: string }) { void projectId; return null }
```
(Tasks 4–5 replace these.) Re-run build → PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/ParserEvaluationPage.tsx frontend/src/pages/ParserEvaluationPage.test.tsx frontend/src/config/navigation.ts frontend/src/App.tsx frontend/src/components/parser-eval/ParserEvalCasesTab.tsx frontend/src/components/parser-eval/ParserEvalRunsTab.tsx
git commit -m "feat(parser-eval-fe): page shell, route, and nav entry"
```

---

### Task 4: Cases tab + CaseEditorDialog

**Files:**
- Create/replace: `frontend/src/components/parser-eval/ParserEvalCasesTab.tsx`
- Create: `frontend/src/components/parser-eval/CaseEditorDialog.tsx`
- Create: `frontend/src/components/parser-eval/ParserEvalCasesTab.test.tsx`

**Interfaces:**
- Consumes: `useParserEvalCases` (Task 2), `useSourceDocuments`, `CreateCaseRequest`.
- Produces: `ParserEvalCasesTab({ projectId })`, `CaseEditorDialog({ open, onOpenChange, onSubmit, existing })`.

- [ ] **Step 1: Write the cases-tab test**

`frontend/src/components/parser-eval/ParserEvalCasesTab.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('@/hooks/useParserEval', () => ({
  useParserEvalCases: () => ({
    cases: [{ id: 'c1', sourceDocumentId: 's1', dimension: 'text', sourceMethod: 'human', reviewStatus: 'draft', createdAt: '2026-07-06T00:00:00Z' }],
    isLoading: false, error: null, fetchCases: vi.fn(), createCase: vi.fn(),
  }),
}))
vi.mock('@/hooks/useSourceDocuments', () => ({
  useSourceDocuments: () => ({
    sourceDocuments: [{ id: 's1', filename: 'acme.pdf' }], isLoading: false, error: null, refresh: vi.fn(),
  }),
}))

import { ParserEvalCasesTab } from './ParserEvalCasesTab'

describe('ParserEvalCasesTab', () => {
  it('lists cases with the source filename and dimension', () => {
    render(<ParserEvalCasesTab projectId="proj-1" />)
    expect(screen.getByText('acme.pdf')).toBeInTheDocument()
    expect(screen.getByText('text')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /new case/i })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/components/parser-eval/ParserEvalCasesTab.test.tsx`
Expected: FAIL (stub renders null).

- [ ] **Step 3: Implement `CaseEditorDialog`**

`frontend/src/components/parser-eval/CaseEditorDialog.tsx`:

```tsx
import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import type { CreateCaseRequest } from '@/types/parserEval'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: CreateCaseRequest) => Promise<void>
}

export function CaseEditorDialog({ open, onOpenChange, onSubmit }: Props) {
  const { sourceDocuments } = useSourceDocuments()
  const [sourceDocumentId, setSourceDocumentId] = useState('')
  const [pages, setPages] = useState<string[]>([''])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canSubmit = sourceDocumentId !== '' && pages.some((p) => p.trim() !== '')

  const handleSubmit = async () => {
    setSubmitting(true); setError(null)
    try {
      await onSubmit({ sourceDocumentId, dimension: 'text', expected: { pages } })
      onOpenChange(false)
      setSourceDocumentId(''); setPages([''])
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      setError(status === 409 || status === 400
        ? 'A text case already exists for this document.'
        : 'Failed to save case.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader><DialogTitle>New Case</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div>
            <Label>Source document</Label>
            <Select value={sourceDocumentId} onValueChange={setSourceDocumentId}>
              <SelectTrigger><SelectValue placeholder="Select a document" /></SelectTrigger>
              <SelectContent>
                {sourceDocuments.map((d) => (
                  <SelectItem key={d.id} value={d.id}>{d.filename ?? d.id}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Dimension</Label>
            <Select value="text" disabled>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="text">Text faithfulness</SelectItem></SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Ground truth (per page)</Label>
            {pages.map((page, i) => (
              <div key={i} className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Page {i + 1}</span>
                  {pages.length > 1 && (
                    <Button variant="ghost" size="sm"
                      onClick={() => setPages((p) => p.filter((_, idx) => idx !== i))}>
                      Remove
                    </Button>
                  )}
                </div>
                <Textarea value={page} rows={4}
                  onChange={(e) => setPages((p) => p.map((v, idx) => (idx === i ? e.target.value : v)))}
                  placeholder={`Correct readable text for page ${i + 1}`} />
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setPages((p) => [...p, ''])}>
              Add page
            </Button>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={!canSubmit || submitting} onClick={handleSubmit}>
            {submitting ? 'Saving…' : 'Create case'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 4: Implement `ParserEvalCasesTab`**

`frontend/src/components/parser-eval/ParserEvalCasesTab.tsx`:

```tsx
import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EvalStatusBadge } from '@/components/evaluation/EvalStatusBadge'
import { useParserEvalCases } from '@/hooks/useParserEval'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import { CaseEditorDialog } from './CaseEditorDialog'

export function ParserEvalCasesTab({ projectId }: { projectId: string }) {
  const { cases, isLoading, createCase } = useParserEvalCases(projectId)
  const { sourceDocuments } = useSourceDocuments()
  const [dialogOpen, setDialogOpen] = useState(false)

  const filenameById = useMemo(() => {
    const map = new Map<string, string>()
    sourceDocuments.forEach((d) => map.set(d.id, d.filename ?? d.id))
    return map
  }, [sourceDocuments])

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setDialogOpen(true)}>New case</Button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : cases.length === 0 ? (
        <p className="text-center py-8 text-muted-foreground">No cases yet — author one.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Document</TableHead>
              <TableHead>Dimension</TableHead>
              <TableHead>Review</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cases.map((c) => (
              <TableRow key={c.id}>
                <TableCell>{filenameById.get(c.sourceDocumentId) ?? c.sourceDocumentId}</TableCell>
                <TableCell>{c.dimension}</TableCell>
                <TableCell><EvalStatusBadge status={c.reviewStatus} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <CaseEditorDialog open={dialogOpen} onOpenChange={setDialogOpen} onSubmit={createCase} />
    </div>
  )
}
```

- [ ] **Step 5: Run test + build**

Run: `cd frontend && npx vitest run src/components/parser-eval/ParserEvalCasesTab.test.tsx && npm run build`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/parser-eval/ParserEvalCasesTab.tsx frontend/src/components/parser-eval/CaseEditorDialog.tsx frontend/src/components/parser-eval/ParserEvalCasesTab.test.tsx
git commit -m "feat(parser-eval-fe): cases tab + per-page ground-truth authoring dialog"
```

---

### Task 5: Runs tab + NewRunDialog

**Files:**
- Create/replace: `frontend/src/components/parser-eval/ParserEvalRunsTab.tsx`
- Create: `frontend/src/components/parser-eval/NewRunDialog.tsx`
- Modify: `frontend/src/components/documents/ParseMethodSelector.tsx` (export `PARSER_REGISTRY`)
- Create: `frontend/src/components/parser-eval/NewRunDialog.test.tsx`

**Interfaces:**
- Consumes: `useParserEvalRuns`, `useParserEvalCases`, `PARSER_REGISTRY`, `CreateRunRequest`.
- Produces: `ParserEvalRunsTab({ projectId })`, `NewRunDialog({ open, onOpenChange, projectId, onCreate })`.

- [ ] **Step 1: Write the run-dialog test**

`frontend/src/components/parser-eval/NewRunDialog.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

vi.mock('@/hooks/useParserEval', () => ({
  useParserEvalCases: () => ({
    cases: [{ id: 'c1', sourceDocumentId: 's1', dimension: 'text', sourceMethod: 'human', reviewStatus: 'draft', createdAt: 'x' }],
    isLoading: false, error: null, fetchCases: vi.fn(), createCase: vi.fn(),
  }),
}))
vi.mock('@/hooks/useSourceDocuments', () => ({
  useSourceDocuments: () => ({ sourceDocuments: [{ id: 's1', filename: 'acme.pdf' }], isLoading: false, error: null, refresh: vi.fn() }),
}))

import { NewRunDialog } from './NewRunDialog'

describe('NewRunDialog', () => {
  it('disables create until a case and an adapter are selected', () => {
    const onCreate = vi.fn()
    render(<NewRunDialog open onOpenChange={vi.fn()} projectId="p1" onCreate={onCreate} />)
    const createBtn = screen.getByRole('button', { name: /run/i })
    expect(createBtn).toBeDisabled()
    fireEvent.click(screen.getByLabelText('acme.pdf'))   // select case
    fireEvent.click(screen.getByLabelText('Docling'))    // select adapter
    expect(createBtn).not.toBeDisabled()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/components/parser-eval/NewRunDialog.test.tsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Export `PARSER_REGISTRY`**

In `frontend/src/components/documents/ParseMethodSelector.tsx`, change `const PARSER_REGISTRY` to `export const PARSER_REGISTRY` (single-word edit; do not re-list parsers elsewhere).

- [ ] **Step 4: Implement `NewRunDialog`**

`frontend/src/components/parser-eval/NewRunDialog.tsx`:

```tsx
import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { PARSER_REGISTRY } from '@/components/documents/ParseMethodSelector'
import { useParserEvalCases } from '@/hooks/useParserEval'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import type { CreateRunRequest } from '@/types/parserEval'

const ADAPTER_OPTIONS = Object.entries(PARSER_REGISTRY).map(([value, meta]) => ({ value, label: meta.label }))

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  projectId: string
  onCreate: (data: CreateRunRequest) => Promise<void>
}

export function NewRunDialog({ open, onOpenChange, projectId, onCreate }: Props) {
  const { cases } = useParserEvalCases(projectId)
  const { sourceDocuments } = useSourceDocuments()
  const [name, setName] = useState('')
  const [caseIds, setCaseIds] = useState<string[]>([])
  const [adapters, setAdapters] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)

  const filename = (id: string) => sourceDocuments.find((d) => d.id === id)?.filename ?? id
  const toggle = (arr: string[], v: string) => arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]
  const canSubmit = caseIds.length > 0 && adapters.length > 0

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      await onCreate({
        name: name || undefined,
        evalCaseIds: caseIds,
        variants: adapters.map((adapter) => ({ adapter, config: {} })),
      })
      onOpenChange(false)
      setName(''); setCaseIds([]); setAdapters([])
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader><DialogTitle>New Run</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="run-name">Name (optional)</Label>
            <Input id="run-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>Cases</Label>
            {cases.map((c) => (
              <label key={c.id} className="flex items-center gap-2 text-sm">
                <Checkbox id={filename(c.sourceDocumentId)}
                  checked={caseIds.includes(c.id)}
                  onCheckedChange={() => setCaseIds((a) => toggle(a, c.id))}
                  aria-label={filename(c.sourceDocumentId)} />
                {filename(c.sourceDocumentId)} · {c.dimension}
              </label>
            ))}
          </div>
          <div className="space-y-2">
            <Label>Adapters</Label>
            {ADAPTER_OPTIONS.map((o) => (
              <label key={o.value} className="flex items-center gap-2 text-sm">
                <Checkbox id={o.label}
                  checked={adapters.includes(o.value)}
                  onCheckedChange={() => setAdapters((a) => toggle(a, o.value))}
                  aria-label={o.label} />
                {o.label}
              </label>
            ))}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={!canSubmit || submitting} onClick={handleSubmit}>
            {submitting ? 'Starting…' : 'Run'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 5: Implement `ParserEvalRunsTab`**

`frontend/src/components/parser-eval/ParserEvalRunsTab.tsx`:

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EvalStatusBadge } from '@/components/evaluation/EvalStatusBadge'
import { useParserEvalRuns } from '@/hooks/useParserEval'
import { NewRunDialog } from './NewRunDialog'

export function ParserEvalRunsTab({ projectId }: { projectId: string }) {
  const { runs, isLoading, createRun } = useParserEvalRuns(projectId)
  const [dialogOpen, setDialogOpen] = useState(false)
  const navigate = useNavigate()

  const handleCreate = async (data: Parameters<typeof createRun>[0]) => {
    const run = await createRun(data)
    navigate(`/evaluation/parser/runs/${run.id}`)
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setDialogOpen(true)}>New run</Button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : runs.length === 0 ? (
        <p className="text-center py-8 text-muted-foreground">No runs yet.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Adapters</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {runs.map((r) => (
              <TableRow key={r.id} className="cursor-pointer"
                onClick={() => navigate(`/evaluation/parser/runs/${r.id}`)}>
                <TableCell>{r.name}</TableCell>
                <TableCell><EvalStatusBadge status={r.status} /></TableCell>
                <TableCell>{r.variants.map((v) => v.adapter).join(', ')}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <NewRunDialog open={dialogOpen} onOpenChange={setDialogOpen} projectId={projectId} onCreate={handleCreate} />
    </div>
  )
}
```

- [ ] **Step 6: Run test + build**

Run: `cd frontend && npx vitest run src/components/parser-eval/NewRunDialog.test.tsx && npm run build`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/parser-eval/ParserEvalRunsTab.tsx frontend/src/components/parser-eval/NewRunDialog.tsx frontend/src/components/parser-eval/NewRunDialog.test.tsx frontend/src/components/documents/ParseMethodSelector.tsx
git commit -m "feat(parser-eval-fe): runs tab + run-creation dialog (cases x adapters)"
```

---

### Task 6: Comparison table + Run-detail page

**Files:**
- Create: `frontend/src/components/parser-eval/ParserComparisonTable.tsx`
- Create: `frontend/src/components/parser-eval/ParserComparisonTable.test.tsx`
- Create: `frontend/src/pages/ParserEvalRunDetailPage.tsx`
- Modify: `frontend/src/App.tsx` (add the run-detail route)

**Interfaces:**
- Consumes: `useParserEvalRunDetail`, `useParserEvalCases`, `useSourceDocuments`, `ScorePill`, `EvalStatusBadge`, `PARSER_REGISTRY`, `ParserEvalResult`.
- Produces: `ParserComparisonTable({ results, caseLabels })`; route `/evaluation/parser/runs/:runId`.

- [ ] **Step 1: Write the comparison-table test**

`frontend/src/components/parser-eval/ParserComparisonTable.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { ParserComparisonTable } from './ParserComparisonTable'
import type { ParserEvalResult } from '@/types/parserEval'

const results: ParserEvalResult[] = [
  { evalCaseId: 'c1', adapter: 'custom_pipeline', config: {}, variantKey: 'custom_pipeline@a',
    metrics: { similarity: 0.90, omission: 0.05, hallucination: 0.02 }, primaryMetric: 'similarity',
    details: null, cost: { usd: 0 }, latencyMs: 140 },
  { evalCaseId: 'c1', adapter: 'docling', config: {}, variantKey: 'docling@b',
    metrics: { similarity: 0.97, omission: 0.01, hallucination: 0.02 }, primaryMetric: 'similarity',
    details: null, cost: { usd: 0 }, latencyMs: 890 },
]

describe('ParserComparisonTable', () => {
  it('groups by case and orders adapters by similarity desc', () => {
    render(<ParserComparisonTable results={results} caseLabels={{ c1: 'acme.pdf' }} />)
    expect(screen.getByText('acme.pdf · text')).toBeInTheDocument()
    const rows = screen.getAllByTestId('cmp-row')
    // best-first: docling (0.97) before custom_pipeline (0.90)
    expect(within(rows[0]).getByText('Docling')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Custom pipeline')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/components/parser-eval/ParserComparisonTable.test.tsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `ParserComparisonTable`**

`frontend/src/components/parser-eval/ParserComparisonTable.tsx`:

```tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ScorePill } from '@/components/evaluation/ScorePill'
import { PARSER_REGISTRY } from '@/components/documents/ParseMethodSelector'
import type { ParserEvalResult } from '@/types/parserEval'

function adapterLabel(adapter: string): string {
  return PARSER_REGISTRY[adapter]?.label ?? adapter
}
function fmtCost(cost: Record<string, number> | null): string {
  const usd = cost?.usd ?? 0
  return usd === 0 ? '$0' : `$${usd.toFixed(3)}`
}
function fmtLatency(ms: number | null): string {
  if (ms == null) return '—'
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}
function pct(v: number | undefined): string {
  return v == null ? '—' : `${(v * 100).toFixed(0)}%`
}

interface Props {
  results: ParserEvalResult[]
  caseLabels: Record<string, string>   // evalCaseId -> filename
}

export function ParserComparisonTable({ results, caseLabels }: Props) {
  const byCase = new Map<string, ParserEvalResult[]>()
  results.forEach((r) => {
    const arr = byCase.get(r.evalCaseId) ?? []
    arr.push(r)
    byCase.set(r.evalCaseId, arr)
  })

  return (
    <div className="space-y-6">
      {[...byCase.entries()].map(([caseId, rows]) => {
        const sorted = [...rows].sort(
          (a, b) => (b.metrics.similarity ?? 0) - (a.metrics.similarity ?? 0))
        return (
          <div key={caseId} className="space-y-2">
            <h3 className="text-sm font-semibold">{caseLabels[caseId] ?? caseId} · text</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Adapter</TableHead>
                  <TableHead>Similarity</TableHead>
                  <TableHead>Omission</TableHead>
                  <TableHead>Hallucination</TableHead>
                  <TableHead>Cost</TableHead>
                  <TableHead>Latency</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((r) => (
                  <TableRow key={r.variantKey} data-testid="cmp-row">
                    <TableCell>{adapterLabel(r.adapter)}</TableCell>
                    <TableCell><ScorePill score={r.metrics.similarity ?? null} /></TableCell>
                    <TableCell>{pct(r.metrics.omission)}</TableCell>
                    <TableCell>{pct(r.metrics.hallucination)}</TableCell>
                    <TableCell>{fmtCost(r.cost)}</TableCell>
                    <TableCell>{fmtLatency(r.latencyMs)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 4: Implement `ParserEvalRunDetailPage`**

`frontend/src/pages/ParserEvalRunDetailPage.tsx`:

```tsx
import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { EvalStatusBadge } from '@/components/evaluation/EvalStatusBadge'
import { ParserComparisonTable } from '@/components/parser-eval/ParserComparisonTable'
import { useParserEvalRunDetail, useParserEvalCases } from '@/hooks/useParserEval'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'

export default function ParserEvalRunDetailPage(): JSX.Element {
  const { runId } = useParams<{ runId: string }>()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null
  const { run, results, isLoading } = useParserEvalRunDetail(projectId, runId ?? null)
  const { cases } = useParserEvalCases(projectId)
  const { sourceDocuments } = useSourceDocuments()

  const caseLabels = useMemo(() => {
    const fname = new Map(sourceDocuments.map((d) => [d.id, d.filename ?? d.id]))
    const labels: Record<string, string> = {}
    cases.forEach((c) => { labels[c.id] = fname.get(c.sourceDocumentId) ?? c.sourceDocumentId })
    return labels
  }, [cases, sourceDocuments])

  if (isLoading && !run) return <p className="text-muted-foreground">Loading…</p>
  if (!run) return <p className="text-muted-foreground">Run not found.</p>

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">{run.name}</h1>
        <EvalStatusBadge status={run.status} />
      </div>
      <p className="text-sm text-muted-foreground">
        {run.variants.map((v) => v.adapter).join(', ')}
      </p>

      {run.status === 'failed' && (
        <p className="text-sm text-destructive">{run.errorMessage ?? 'Run failed.'}</p>
      )}
      {(run.status === 'pending' || run.status === 'running') && (
        <p className="text-muted-foreground">Running… results will appear when complete.</p>
      )}
      {run.status === 'completed' && (
        <ParserComparisonTable results={results} caseLabels={caseLabels} />
      )}
    </div>
  )
}
```

- [ ] **Step 5: Register the run-detail route**

In `frontend/src/App.tsx`: add `import ParserEvalRunDetailPage from './pages/ParserEvalRunDetailPage'` and the route after `evaluation/parser`:

```tsx
          {
            path: 'evaluation/parser/runs/:runId',
            element: <ParserEvalRunDetailPage />,
            handle: { breadcrumb: 'Run Detail' },
          },
```

- [ ] **Step 6: Run test + full frontend checks**

Run: `cd frontend && npx vitest run src/components/parser-eval src/pages/ParserEvaluationPage.test.tsx && npm run build && npm run lint`
Expected: PASS across parser-eval tests, tsc build, and lint.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/parser-eval/ParserComparisonTable.tsx frontend/src/components/parser-eval/ParserComparisonTable.test.tsx frontend/src/pages/ParserEvalRunDetailPage.tsx frontend/src/App.tsx
git commit -m "feat(parser-eval-fe): comparison table + run-detail page with polling"
```

---

## Self-Review

**Spec coverage:**
- §2a camelCase DTOs → Task 1. §2b get-one-run route → Task 1. ✅
- §3 routes + nav → Task 3. ✅
- §4 types → Task 2; §5 api → Task 2; §6 hooks → Task 2. ✅
- Cases tab + authoring (§7) → Task 4. Runs tab + creation (§7) → Task 5. Run detail + comparison table (§7) → Task 6. ✅
- §8 reuse (ScorePill/MetricCard/EvalStatusBadge/PARSER_REGISTRY/useSourceDocuments) → Tasks 4–6. `MetricCard` summary was marked optional in the spec and is omitted here to keep scope tight (acceptable — it was "in scope if cheap", not required); acceptance criterion 4 does not require it. ✅
- §9 acceptance criteria → Tasks 3–6 + final build/lint/vitest. ✅
- §10 tests → each UI task ships an RTL test; plumbing verified by tsc (matches codebase convention where hooks/api lack unit tests). ✅

**Placeholder scan:** No TBD/TODO. Temporary tab stubs in Task 3 are explicitly replaced in Tasks 4–5 (a real build-ordering step, not a placeholder). No "add error handling" hand-waves — dialog error states and empty/loading states are shown in code.

**Type consistency:** `CreateCaseRequest`/`CreateRunRequest` shapes match Task 2 defs and the backend aliases (Task 1). `useParserEvalCases/Runs/RunDetail` return shapes are consistent between hook defs (Task 2) and consumers (Tasks 4–6). `ParserComparisonTable({ results, caseLabels })` prop names match between the test (Task 6 Step 1) and impl (Step 3). `PARSER_REGISTRY` export (Task 5) is consumed by Tasks 5 & 6.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-06-parser-eval-frontend.md`. Per the project pre-implementation gate, a GitHub issue must exist and be confirmed before implementation. Two execution options after that:

1. **Subagent-Driven (recommended)** — a fresh subagent per task, review between tasks.
2. **Inline Execution** — execute tasks in this session with checkpoints.
