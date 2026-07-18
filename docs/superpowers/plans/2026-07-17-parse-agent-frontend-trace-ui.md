# Parse Agent — Frontend Trace UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upload a document and watch a readable, polled-live trace of the parse-agent run — graph strip on top, step timeline below, click-to-detail panel, linking out to the existing parse-results viewer.

**Architecture:** A small backend addition (a runs list endpoint) plus a frontend feature slice following the project's page → component → hook → api flow. No React Query — plain hooks with `setInterval` polling, mirroring the existing `useAgentRun`. The trace detail panel hands off to the parse-results viewer via a new **document-less** viewer route (parse-agent runs have no project `Document` by design).

**Tech Stack:** React 18, TypeScript, Vite, React Router, shadcn/ui + Tailwind, axios, vitest + @testing-library/react. Backend: FastAPI, SQLAlchemy 2.0, pytest (SQLite `test_db`).

## Global Constraints

- Data flow: **page → component → hook → api**. One hook per feature, one page per route, feature-scoped components under `@/components/parse-agent/`.
- **shadcn/ui + Tailwind for all UI.** Available primitives include: `alert`, `badge`, `button`, `card`, `input`, `label`, `select`, `separator`, `skeleton`, `scroll-area`, `table`, `collapsible`. Do not introduce new UI libraries.
- **No React Query anywhere in this repo.** Hooks use `useState`/`useEffect`. Polling mirrors `frontend/src/hooks/useAgentRun.ts`: `setInterval`, poll only while the run is active, stop on terminal status, with a timeout guard.
- API calls go through `apiClient` (axios) from `@/api/client`. Types live in `@/types/*`. **Backend responses are camelCase** (`runId`, `graphNodes`, `stateDelta`, `durationMs`).
- Project id comes from `useProject()` (`@/contexts/ProjectContext`) → `currentProject?.id`.
- Routes are registered in `frontend/src/App.tsx` as children of the `AppLayout` route, each with `handle: { breadcrumb: '...' }`. Nav items live in `frontend/src/config/navigation.ts`.
- Toasts via `toast` from `sonner`. Icons from `lucide-react`.
- Frontend tests: `cd frontend && npx vitest run <path>`. Lint: `npm run lint`. Build: `npm run build`.
- Backend tests: `cd backend && uv run python -m pytest <path> -o "addopts=" -v`. **Never run the whole backend suite** (slow; stalls watchdogs) — run only the named file.
- **Do not modify the existing `/parse-runs` (CDM) router's endpoints.** Task 1 only *adds* a list endpoint to the separate `/parse-agent-runs` router.
- Design reference: `docs/superpowers/specs/2026-07-15-parse-agent-design.md` §6 (Frontend). Backend contract: `backend/app/routers/parse_agent_runs.py`.

---

## File Structure

**Backend (Task 1 only):**
- Modify `backend/app/repositories/parse_agent_run_repository.py` — add `list_by_project`.
- Modify `backend/app/routers/parse_agent_runs.py` — add `GET ""` list endpoint.
- Modify `backend/tests/routers/test_parse_agent_runs_router.py` — list tests.

**Frontend:**
- `frontend/src/types/parseAgent.ts` — API types (one responsibility: the wire contract).
- `frontend/src/api/parseAgent.ts` — axios wrappers.
- `frontend/src/hooks/useParseAgentRuns.ts` — list + start (upload).
- `frontend/src/hooks/useParseAgentRun.ts` — detail + polling.
- `frontend/src/components/parse-agent/GraphStrip.tsx` — graph nodes colored by state.
- `frontend/src/components/parse-agent/RunTimeline.tsx` — step list, selectable.
- `frontend/src/components/parse-agent/StepDetailPanel.tsx` — selected step detail + viewer handoff.
- `frontend/src/pages/ParseAgentRunsPage.tsx` — upload form + runs list.
- `frontend/src/pages/ParseAgentRunDetailPage.tsx` — composition of the three components.
- Modify `frontend/src/App.tsx` — three routes.
- Modify `frontend/src/config/navigation.ts` — nav item.
- Modify `frontend/src/pages/ParseRunDetailPage.tsx` — make `documentId` optional (Task 6).

Each component has one clear responsibility and is independently testable; the pages only compose.

---

### Task 1: Backend — runs list endpoint

**Files:**
- Modify: `backend/app/repositories/parse_agent_run_repository.py`
- Modify: `backend/app/routers/parse_agent_runs.py`
- Test: `backend/tests/routers/test_parse_agent_runs_router.py`

**Interfaces:**
- Consumes: `ParseAgentRun` model, `ParseAgentRunSummary` schema, `ProjectRepository.get_by_id(project_id, user_id)`.
- Produces: `ParseAgentRunRepository.list_by_project(project_id: UUID) -> list[ParseAgentRun]` (newest first); `GET /api/v1/parse-agent-runs?project_id=<uuid>` → `list[ParseAgentRunSummary]` (camelCase), 404 if the project isn't owned.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/routers/test_parse_agent_runs_router.py`:

```python
@pytest.mark.asyncio
async def test_list_runs_returns_project_runs_newest_first(client: AsyncClient, test_db: AsyncSession):
    token = await _signup_and_login(client)
    project_id = await _create_project(client, token)

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=test_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    async def fake_parse_and_persist(**kwargs):
        return _fake_parse_result(str(kwargs["source"].id))

    with (
        patch("app.database.AsyncSessionLocal", mock_session_factory),
        patch("app.services.parsing.parsing_service.ParsingService.parse_and_persist",
              new=AsyncMock(side_effect=fake_parse_and_persist)),
    ):
        for name in ("a.pdf", "b.pdf"):
            resp = await client.post(
                "/api/v1/parse-agent-runs",
                headers={"Authorization": f"Bearer {token}"},
                data={"project_id": project_id, "parser_type": "simple"},
                files=[("file", (name, MINIMAL_PDF + name.encode(), "application/pdf"))],
            )
            assert resp.status_code == 202, resp.text

    listed = await client.get(
        f"/api/v1/parse-agent-runs?project_id={project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert len(body) == 2
    assert {"id", "status", "startedAt", "sourceDocumentId"} <= set(body[0])
    # newest first
    assert body[0]["startedAt"] >= body[1]["startedAt"]


@pytest.mark.asyncio
async def test_list_runs_404_for_unowned_project(client: AsyncClient, test_db: AsyncSession):
    token_a = await _signup_and_login(client)
    project_id = await _create_project(client, token_a)

    token_b = await _signup_and_login(client, email="pc@example.com")
    resp = await client.get(
        f"/api/v1/parse-agent-runs?project_id={project_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/routers/test_parse_agent_runs_router.py -o "addopts=" -v`
Expected: the two new tests FAIL with 405/422 (no list route registered).

- [ ] **Step 3: Add the repository method**

In `backend/app/repositories/parse_agent_run_repository.py`, add to `ParseAgentRunRepository`:

```python
    async def list_by_project(self, project_id: UUID) -> list[ParseAgentRun]:
        """All runs for a project, newest first."""
        result = await self.session.execute(
            select(ParseAgentRun)
            .where(ParseAgentRun.project_id == project_id)
            .order_by(ParseAgentRun.started_at.desc())
        )
        return list(result.scalars().all())
```

- [ ] **Step 4: Add the list endpoint**

In `backend/app/routers/parse_agent_runs.py`, add `Query` to the existing fastapi import line, and add this endpoint **above** the existing `@router.get("/{run_id}")` handler:

```python
@router.get("", response_model=list[ParseAgentRunSummary])
async def list_runs(
    project_id: UUID = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    project = await ProjectRepository(db).get_by_id(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    runs = await ParseAgentRunRepository(db).list_by_project(project_id)
    return [ParseAgentRunSummary.model_validate(r) for r in runs]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/routers/test_parse_agent_runs_router.py -o "addopts=" -v`
Expected: PASS (6 tests — 4 existing + 2 new).

- [ ] **Step 6: Commit**

```bash
git add backend/app/repositories/parse_agent_run_repository.py backend/app/routers/parse_agent_runs.py backend/tests/routers/test_parse_agent_runs_router.py
git commit -m "feat(parse-agent): list runs by project endpoint"
```

---

### Task 2: Frontend types + API client

**Files:**
- Create: `frontend/src/types/parseAgent.ts`
- Create: `frontend/src/api/parseAgent.ts`

**Interfaces:**
- Consumes: `apiClient` from `@/api/client`; the backend contract from Task 1 + `backend/app/routers/parse_agent_runs.py`.
- Produces:
  - Types: `ParseAgentRunStatus`, `ParseAgentRunSummary`, `ParseAgentRunStep`, `ParseAgentRunDetail`, `StartParseAgentRunRequest`.
  - API: `startParseAgentRun(req) -> Promise<{ runId: string }>`, `getParseAgentRun(runId) -> Promise<ParseAgentRunDetail>`, `listParseAgentRuns(projectId) -> Promise<ParseAgentRunSummary[]>`.

- [ ] **Step 1: Write the types**

```typescript
// frontend/src/types/parseAgent.ts
export type ParseAgentRunStatus = 'running' | 'completed' | 'failed'

export interface ParseAgentRunSummary {
  id: string
  projectId: string
  sourceDocumentId: string
  status: ParseAgentRunStatus
  startedAt: string
  finishedAt: string | null
  error: string | null
}

export interface ParseAgentRunStep {
  id: string
  seq: number
  node: string
  phase: string
  status: string
  inputKeys: string[]
  outputKeys: string[]
  stateDelta: Record<string, unknown>
  message: string | null
  durationMs: number | null
  createdAt: string
}

export interface ParseAgentRunDetail {
  run: ParseAgentRunSummary
  steps: ParseAgentRunStep[]
  graphNodes: string[]
}

export interface StartParseAgentRunRequest {
  projectId: string
  file: File
  parserType?: string
  parseConfig?: string
}
```

- [ ] **Step 2: Write the API client**

```typescript
// frontend/src/api/parseAgent.ts
import apiClient from './client'
import type {
  ParseAgentRunDetail,
  ParseAgentRunSummary,
  StartParseAgentRunRequest,
} from '@/types/parseAgent'

export async function startParseAgentRun(
  req: StartParseAgentRunRequest
): Promise<{ runId: string }> {
  const form = new FormData()
  form.append('project_id', req.projectId)
  form.append('parser_type', req.parserType ?? 'simple')
  if (req.parseConfig) form.append('parse_config', req.parseConfig)
  form.append('file', req.file)

  const response = await apiClient.post<{ runId: string }>(
    '/parse-agent-runs',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return response.data
}

export async function getParseAgentRun(
  runId: string
): Promise<ParseAgentRunDetail> {
  const response = await apiClient.get<ParseAgentRunDetail>(
    `/parse-agent-runs/${runId}`
  )
  return response.data
}

export async function listParseAgentRuns(
  projectId: string
): Promise<ParseAgentRunSummary[]> {
  const response = await apiClient.get<ParseAgentRunSummary[]>(
    '/parse-agent-runs',
    { params: { project_id: projectId } }
  )
  return response.data
}
```

- [ ] **Step 3: Verify it typechecks**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors from the two new files. (Pre-existing errors elsewhere, if any, are not yours — report them but don't fix.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/parseAgent.ts frontend/src/api/parseAgent.ts
git commit -m "feat(parse-agent-ui): types + api client"
```

---

### Task 3: Hooks (list + detail with polling)

**Files:**
- Create: `frontend/src/hooks/useParseAgentRun.ts`
- Create: `frontend/src/hooks/useParseAgentRuns.ts`
- Test: `frontend/src/hooks/useParseAgentRun.test.ts`

**Interfaces:**
- Consumes: `@/api/parseAgent` (Task 2), types from `@/types/parseAgent`.
- Produces:
  - `useParseAgentRun(runId: string | null)` → `{ detail: ParseAgentRunDetail | null, isLoading: boolean, error: string | null, refetch: () => Promise<void> }`. Polls every 2s while `detail.run.status === 'running'`; stops on terminal; 10-minute timeout guard.
  - `useParseAgentRuns(projectId: string | null)` → `{ runs: ParseAgentRunSummary[], isLoading: boolean, isStarting: boolean, error: string | null, refetch: () => Promise<void>, startRun: (file: File, parserType?: string) => Promise<string> }` (returns the new `runId`).

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/hooks/useParseAgentRun.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import * as api from '@/api/parseAgent'
import { useParseAgentRun } from './useParseAgentRun'
import type { ParseAgentRunDetail } from '@/types/parseAgent'

vi.mock('@/api/parseAgent', () => ({
  getParseAgentRun: vi.fn(),
}))

function detail(status: 'running' | 'completed'): ParseAgentRunDetail {
  return {
    run: {
      id: 'run-1',
      projectId: 'proj-1',
      sourceDocumentId: 'src-1',
      status,
      startedAt: '2026-07-17T10:00:00Z',
      finishedAt: status === 'completed' ? '2026-07-17T10:00:05Z' : null,
      error: null,
    },
    steps: [
      {
        id: 'step-1', seq: 0, node: 'parse', phase: 'end', status: 'succeeded',
        inputKeys: ['file_path'], outputKeys: ['parse_run_id'],
        stateDelta: { parse_run_id: 'pr-1' }, message: null,
        durationMs: 4200, createdAt: '2026-07-17T10:00:04Z',
      },
    ],
    graphNodes: ['parse', 'health_check'],
  }
}

describe('useParseAgentRun', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })
  afterEach(() => vi.useRealTimers())

  it('fetches the run detail', async () => {
    vi.mocked(api.getParseAgentRun).mockResolvedValue(detail('completed'))
    const { result } = renderHook(() => useParseAgentRun('run-1'))
    await waitFor(() => expect(result.current.detail?.run.id).toBe('run-1'))
    expect(result.current.detail?.graphNodes).toEqual(['parse', 'health_check'])
    expect(result.current.error).toBeNull()
  })

  it('polls while running and stops once terminal', async () => {
    vi.mocked(api.getParseAgentRun)
      .mockResolvedValueOnce(detail('running'))
      .mockResolvedValue(detail('completed'))

    const { result } = renderHook(() => useParseAgentRun('run-1'))
    await waitFor(() => expect(result.current.detail?.run.status).toBe('running'))

    await vi.advanceTimersByTimeAsync(2000)
    await waitFor(() => expect(result.current.detail?.run.status).toBe('completed'))

    const callsAfterTerminal = vi.mocked(api.getParseAgentRun).mock.calls.length
    await vi.advanceTimersByTimeAsync(6000)
    expect(vi.mocked(api.getParseAgentRun).mock.calls.length).toBe(callsAfterTerminal)
  })

  it('does not fetch when runId is null', () => {
    renderHook(() => useParseAgentRun(null))
    expect(api.getParseAgentRun).not.toHaveBeenCalled()
  })

  it('captures errors', async () => {
    vi.mocked(api.getParseAgentRun).mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useParseAgentRun('run-1'))
    await waitFor(() => expect(result.current.error).toBe('boom'))
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/hooks/useParseAgentRun.test.ts`
Expected: FAIL — cannot resolve `./useParseAgentRun`.

- [ ] **Step 3: Write the detail hook**

```typescript
// frontend/src/hooks/useParseAgentRun.ts
import { useState, useCallback, useEffect, useRef } from 'react'
import * as parseAgentApi from '@/api/parseAgent'
import type { ParseAgentRunDetail } from '@/types/parseAgent'

const POLLING_INTERVAL = 2000
const POLLING_TIMEOUT = 10 * 60 * 1000

interface UseParseAgentRunReturn {
  detail: ParseAgentRunDetail | null
  isLoading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export function useParseAgentRun(runId: string | null): UseParseAgentRunReturn {
  const [detail, setDetail] = useState<ParseAgentRunDetail | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollingStartRef = useRef<number>(0)

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const refetch = useCallback(async () => {
    if (!runId) {
      setDetail(null)
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      setDetail(await parseAgentApi.getParseAgentRun(runId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch run')
    } finally {
      setIsLoading(false)
    }
  }, [runId])

  // Poll only while the run is active
  useEffect(() => {
    const isActive = detail?.run.status === 'running'
    if (isActive && !pollingRef.current) {
      pollingStartRef.current = Date.now()
      pollingRef.current = setInterval(async () => {
        if (Date.now() - pollingStartRef.current > POLLING_TIMEOUT) {
          stopPolling()
          return
        }
        await refetch()
      }, POLLING_INTERVAL)
    } else if (!isActive) {
      stopPolling()
    }
    return () => stopPolling()
  }, [detail, refetch, stopPolling])

  useEffect(() => {
    if (runId) {
      refetch()
    } else {
      setDetail(null)
    }
  }, [runId, refetch])

  return { detail, isLoading, error, refetch }
}
```

- [ ] **Step 4: Write the list hook**

```typescript
// frontend/src/hooks/useParseAgentRuns.ts
import { useState, useCallback, useEffect } from 'react'
import * as parseAgentApi from '@/api/parseAgent'
import type { ParseAgentRunSummary } from '@/types/parseAgent'

interface UseParseAgentRunsReturn {
  runs: ParseAgentRunSummary[]
  isLoading: boolean
  isStarting: boolean
  error: string | null
  refetch: () => Promise<void>
  startRun: (file: File, parserType?: string) => Promise<string>
}

export function useParseAgentRuns(
  projectId: string | null
): UseParseAgentRunsReturn {
  const [runs, setRuns] = useState<ParseAgentRunSummary[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStarting, setIsStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    if (!projectId) {
      setRuns([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      setRuns(await parseAgentApi.listParseAgentRuns(projectId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch runs')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const startRun = useCallback(
    async (file: File, parserType?: string): Promise<string> => {
      if (!projectId) throw new Error('No project selected')
      setIsStarting(true)
      setError(null)
      try {
        const { runId } = await parseAgentApi.startParseAgentRun({
          projectId,
          file,
          parserType,
        })
        await refetch()
        return runId
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to start run')
        throw err
      } finally {
        setIsStarting(false)
      }
    },
    [projectId, refetch]
  )

  useEffect(() => {
    refetch()
  }, [refetch])

  return { runs, isLoading, isStarting, error, refetch, startRun }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/hooks/useParseAgentRun.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useParseAgentRun.ts frontend/src/hooks/useParseAgentRuns.ts frontend/src/hooks/useParseAgentRun.test.ts
git commit -m "feat(parse-agent-ui): run list + polled detail hooks"
```

---

### Task 4: Trace components

**Files:**
- Create: `frontend/src/components/parse-agent/GraphStrip.tsx`
- Create: `frontend/src/components/parse-agent/RunTimeline.tsx`
- Create: `frontend/src/components/parse-agent/StepDetailPanel.tsx`

**Interfaces:**
- Consumes: `ParseAgentRunStep`, `ParseAgentRunStatus` from `@/types/parseAgent`; shadcn `badge`, `button`, `card`, `separator`, `collapsible`.
- Produces:
  - `<GraphStrip graphNodes={string[]} steps={ParseAgentRunStep[]} runStatus={ParseAgentRunStatus} selectedNode={string | null} onSelectNode={(node: string) => void} />`
  - `<RunTimeline steps={ParseAgentRunStep[]} selectedStepId={string | null} onSelectStep={(step: ParseAgentRunStep) => void} />`
  - `<StepDetailPanel step={ParseAgentRunStep | null} />` — renders in/out keys, state delta, duration, and (when `stateDelta.parse_run_id` is present) a link to `/parse-runs/{parseRunId}`.

Node state derivation (shared rule): a node is **done** if a step with that `node` exists; **running** if it's the first `graphNodes` entry with no step and `runStatus === 'running'`; otherwise **pending**.

- [ ] **Step 1: Write GraphStrip**

```tsx
// frontend/src/components/parse-agent/GraphStrip.tsx
import { Badge } from '@/components/ui/badge'
import { ChevronRight } from 'lucide-react'
import type { ParseAgentRunStatus, ParseAgentRunStep } from '@/types/parseAgent'

interface GraphStripProps {
  graphNodes: string[]
  steps: ParseAgentRunStep[]
  runStatus: ParseAgentRunStatus
  selectedNode: string | null
  onSelectNode: (node: string) => void
}

type NodeState = 'done' | 'running' | 'pending'

export function nodeState(
  node: string,
  graphNodes: string[],
  steps: ParseAgentRunStep[],
  runStatus: ParseAgentRunStatus
): NodeState {
  if (steps.some((s) => s.node === node)) return 'done'
  const firstPending = graphNodes.find((n) => !steps.some((s) => s.node === n))
  if (runStatus === 'running' && firstPending === node) return 'running'
  return 'pending'
}

const stateClass: Record<NodeState, string> = {
  done: 'border-emerald-500 text-emerald-600',
  running: 'border-amber-500 text-amber-600 animate-pulse',
  pending: 'border-dashed text-muted-foreground',
}

export function GraphStrip({
  graphNodes,
  steps,
  runStatus,
  selectedNode,
  onSelectNode,
}: GraphStripProps): JSX.Element {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border p-4">
      <Badge variant="outline" className="border-dashed text-muted-foreground">
        start
      </Badge>
      {graphNodes.map((node) => (
        <div key={node} className="flex items-center gap-2">
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
          <button type="button" onClick={() => onSelectNode(node)}>
            <Badge
              variant="outline"
              className={`${stateClass[nodeState(node, graphNodes, steps, runStatus)]} ${
                selectedNode === node ? 'ring-2 ring-primary' : ''
              }`}
            >
              {node}
            </Badge>
          </button>
        </div>
      ))}
      <ChevronRight className="h-4 w-4 text-muted-foreground" />
      <Badge variant="outline" className="border-dashed text-muted-foreground">
        end
      </Badge>
    </div>
  )
}
```

- [ ] **Step 2: Write RunTimeline**

```tsx
// frontend/src/components/parse-agent/RunTimeline.tsx
import type { ParseAgentRunStep } from '@/types/parseAgent'

interface RunTimelineProps {
  steps: ParseAgentRunStep[]
  selectedStepId: string | null
  onSelectStep: (step: ParseAgentRunStep) => void
}

export function RunTimeline({
  steps,
  selectedStepId,
  onSelectStep,
}: RunTimelineProps): JSX.Element {
  if (steps.length === 0) {
    return (
      <p className="p-4 text-sm text-muted-foreground">
        No steps yet — waiting for the run to produce its first step.
      </p>
    )
  }

  return (
    <ol className="space-y-1 p-2">
      {steps.map((step) => (
        <li key={step.id}>
          <button
            type="button"
            onClick={() => onSelectStep(step)}
            className={`w-full rounded-md border p-3 text-left transition-colors hover:bg-muted/50 ${
              selectedStepId === step.id
                ? 'border-primary bg-primary/5'
                : 'border-transparent'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-medium">{step.node}</span>
              <span className="text-xs text-muted-foreground">
                {step.durationMs !== null ? `${step.durationMs} ms` : ''}
              </span>
            </div>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              read {step.inputKeys.join(', ') || '—'} → wrote{' '}
              {step.outputKeys.join(', ') || '—'}
            </p>
            {step.message ? (
              <p className="mt-1 text-xs text-muted-foreground">{step.message}</p>
            ) : null}
          </button>
        </li>
      ))}
    </ol>
  )
}
```

- [ ] **Step 3: Write StepDetailPanel**

```tsx
// frontend/src/components/parse-agent/StepDetailPanel.tsx
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { ExternalLink } from 'lucide-react'
import type { ParseAgentRunStep } from '@/types/parseAgent'

interface StepDetailPanelProps {
  step: ParseAgentRunStep | null
}

export function StepDetailPanel({ step }: StepDetailPanelProps): JSX.Element {
  if (!step) {
    return (
      <p className="p-4 text-sm text-muted-foreground">
        Select a step to inspect what it read and wrote.
      </p>
    )
  }

  const parseRunId = step.stateDelta['parse_run_id']

  return (
    <div className="space-y-3 p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium">{step.node}</h3>
        <Badge variant="outline">{step.status}</Badge>
      </div>
      <Separator />
      <div>
        <p className="text-xs uppercase text-muted-foreground">input keys</p>
        <p className="font-mono text-sm">{step.inputKeys.join(', ') || '—'}</p>
      </div>
      <div>
        <p className="text-xs uppercase text-muted-foreground">output keys</p>
        <p className="font-mono text-sm">{step.outputKeys.join(', ') || '—'}</p>
      </div>
      <div>
        <p className="text-xs uppercase text-muted-foreground">state delta</p>
        <pre className="overflow-x-auto rounded-md bg-muted p-2 font-mono text-xs">
          {JSON.stringify(step.stateDelta, null, 2)}
        </pre>
      </div>
      {step.durationMs !== null ? (
        <p className="text-xs text-muted-foreground">
          duration: {step.durationMs} ms
        </p>
      ) : null}
      {typeof parseRunId === 'string' ? (
        <Link
          to={`/parse-runs/${parseRunId}`}
          className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
        >
          Open parsed document in results viewer
          <ExternalLink className="h-3 w-3" />
        </Link>
      ) : null}
    </div>
  )
}
```

- [ ] **Step 4: Verify lint + typecheck**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: no new errors from `src/components/parse-agent/*`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/parse-agent
git commit -m "feat(parse-agent-ui): graph strip, timeline, step detail panel"
```

---

### Task 5: Pages, routes, nav

**Files:**
- Create: `frontend/src/pages/ParseAgentRunsPage.tsx`
- Create: `frontend/src/pages/ParseAgentRunDetailPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/config/navigation.ts`

**Interfaces:**
- Consumes: `useParseAgentRuns`, `useParseAgentRun` (Task 3); `GraphStrip`, `RunTimeline`, `StepDetailPanel` (Task 4); `useProject()`.
- Produces: routes `/parse-agent` (list + upload) and `/parse-agent/runs/:runId` (detail); nav item "Parse Agent".

- [ ] **Step 1: Write the runs list page**

```tsx
// frontend/src/pages/ParseAgentRunsPage.tsx
import { useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useParseAgentRuns } from '@/hooks/useParseAgentRuns'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { toast } from 'sonner'

export function ParseAgentRunsPage(): JSX.Element {
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)

  const { runs, isLoading, isStarting, error, startRun } =
    useParseAgentRuns(projectId)

  const handleStart = async () => {
    if (!file) return
    try {
      const runId = await startRun(file)
      toast.success('Parse agent run started')
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
      navigate(`/parse-agent/runs/${runId}`)
    } catch (err) {
      toast.error('Failed to start run', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

  if (!projectId) {
    return (
      <Alert>
        <AlertDescription>Select a project to run the parse agent.</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Parse Agent</h1>
        <p className="text-sm text-muted-foreground">
          Upload a document to start a traced parse run.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <Input
          ref={fileRef}
          type="file"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="max-w-sm"
        />
        <Button onClick={handleStart} disabled={!file || isStarting}>
          {isStarting ? 'Starting…' : 'Start run'}
        </Button>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : runs.length === 0 ? (
        <p className="text-sm text-muted-foreground">No runs yet.</p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {runs.map((run) => (
            <li key={run.id}>
              <Link
                to={`/parse-agent/runs/${run.id}`}
                className="flex items-center justify-between p-3 hover:bg-muted/50"
              >
                <span className="font-mono text-sm">{run.id.slice(0, 8)}</span>
                <span className="text-xs text-muted-foreground">
                  {new Date(run.startedAt).toLocaleString()}
                </span>
                <Badge variant="outline">{run.status}</Badge>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Write the run detail page**

```tsx
// frontend/src/pages/ParseAgentRunDetailPage.tsx
import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useParseAgentRun } from '@/hooks/useParseAgentRun'
import { GraphStrip } from '@/components/parse-agent/GraphStrip'
import { RunTimeline } from '@/components/parse-agent/RunTimeline'
import { StepDetailPanel } from '@/components/parse-agent/StepDetailPanel'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ArrowLeft } from 'lucide-react'
import type { ParseAgentRunStep } from '@/types/parseAgent'

export function ParseAgentRunDetailPage(): JSX.Element {
  const { runId } = useParams<{ runId: string }>()
  const { detail, isLoading, error } = useParseAgentRun(runId ?? null)
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null)

  if (isLoading && !detail) return <Skeleton className="h-64 w-full" />
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }
  if (!detail) return <p className="text-sm text-muted-foreground">Run not found.</p>

  const { run, steps, graphNodes } = detail
  const selectedStep: ParseAgentRunStep | null =
    steps.find((s) => s.id === selectedStepId) ?? null

  const handleSelectNode = (node: string) => {
    const step = steps.find((s) => s.node === node)
    setSelectedStepId(step ? step.id : null)
  }

  return (
    <div className="space-y-4">
      <Link
        to="/parse-agent"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"
      >
        <ArrowLeft className="h-4 w-4" />
        Parse Agent
      </Link>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-mono text-lg">{run.id}</h1>
          <p className="text-xs text-muted-foreground">
            started {new Date(run.startedAt).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {run.status === 'running' ? (
            <Badge variant="outline" className="border-emerald-500 text-emerald-600">
              ● polling
            </Badge>
          ) : null}
          <Badge variant="outline">{run.status}</Badge>
        </div>
      </div>

      {run.error ? (
        <Alert variant="destructive">
          <AlertDescription>{run.error}</AlertDescription>
        </Alert>
      ) : null}

      <GraphStrip
        graphNodes={graphNodes}
        steps={steps}
        runStatus={run.status}
        selectedNode={selectedStep?.node ?? null}
        onSelectNode={handleSelectNode}
      />

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border">
          <p className="border-b p-2 text-xs uppercase text-muted-foreground">
            Timeline
          </p>
          <RunTimeline
            steps={steps}
            selectedStepId={selectedStepId}
            onSelectStep={(s) => setSelectedStepId(s.id)}
          />
        </div>
        <div className="rounded-lg border bg-muted/20">
          <p className="border-b p-2 text-xs uppercase text-muted-foreground">
            Step detail
          </p>
          <StepDetailPanel step={selectedStep} />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Register the routes**

In `frontend/src/App.tsx`, add the imports alongside the other page imports:

```tsx
import { ParseAgentRunsPage } from './pages/ParseAgentRunsPage'
import { ParseAgentRunDetailPage } from './pages/ParseAgentRunDetailPage'
```

Then add these two route objects to the `AppLayout` children array, immediately after the existing `parse/:documentId/runs/:runId` route object:

```tsx
          {
            path: 'parse-agent',
            element: <ParseAgentRunsPage />,
            handle: { breadcrumb: 'Parse Agent' },
          },
          {
            path: 'parse-agent/runs/:runId',
            element: <ParseAgentRunDetailPage />,
            handle: { breadcrumb: 'Parse Agent Run' },
          },
```

- [ ] **Step 4: Add the nav item**

In `frontend/src/config/navigation.ts`, add `Workflow` to the `lucide-react` import list, and insert this item immediately after the `Parse` entry:

```ts
  { label: 'Parse Agent', href: '/parse-agent', icon: Workflow, activeColor: 'border-l-rose-500' },
```

- [ ] **Step 5: Verify build + lint**

Run: `cd frontend && npm run lint && npm run build`
Expected: both succeed with no new errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ParseAgentRunsPage.tsx frontend/src/pages/ParseAgentRunDetailPage.tsx frontend/src/App.tsx frontend/src/config/navigation.ts
git commit -m "feat(parse-agent-ui): runs list + trace detail pages, routes, nav"
```

---

### Task 6: Document-less results-viewer route

**Files:**
- Modify: `frontend/src/pages/ParseRunDetailPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces: route `/parse-runs/:runId` rendering `ParseRunDetailPage` **without** a `documentId`. This is the target of the trace's "Open parsed document in results viewer" link (Task 4).

Context: `ParseRunDetailPage` already fetches all its content by `runId` alone (`useParseRunDetail(runId)`, `useParseRunRawPayload(runId)`, `parseRunsApi.getParsedDocument(runId)`). Only two things need `documentId`: the back-link to `/parse?documentId=…` and the re-parse action (`createParseRun(documentId, …)`). Parse-agent runs have no project `Document`, so both must degrade gracefully when `documentId` is absent — the page already guards one such spot with `{documentId ? … : …}`.

- [ ] **Step 1: Make `documentId` optional in the page**

Open `frontend/src/pages/ParseRunDetailPage.tsx`. Change the `useParams` destructure so `documentId` is optional:

```tsx
  const { documentId, runId } = useParams<{
    documentId?: string
    runId: string
  }>()
```

Then, for **every** use of `documentId` in the file:
- The back-link (currently `<Link to={`/parse?documentId=${documentId}`}>`): render it only when `documentId` is set; when it's absent, render a back-link to `/parse-agent` instead (the trace is the referrer in that case). Wrap in a `{documentId ? (…) : (…)}` conditional.
- The re-parse handler (`createParseRun(documentId, …)`): it already early-returns with `if (!documentId) return`. Keep that guard, and hide/disable the re-parse UI when `documentId` is absent (the existing `{documentId ? … }` conditional at the re-parse component already does this — verify it covers the control).

Do not change any `runId`-based data fetching.

- [ ] **Step 2: Register the document-less route**

In `frontend/src/App.tsx`, add this route object immediately after the existing `parse/:documentId/runs/:runId` route:

```tsx
          {
            path: 'parse-runs/:runId',
            element: <ParseRunDetailPage />,
            handle: { breadcrumb: 'Parse Run' },
          },
```

(`ParseRunDetailPage` is already imported.)

- [ ] **Step 3: Verify build + lint**

Run: `cd frontend && npm run lint && npm run build`
Expected: both succeed. TypeScript must not complain about `documentId` being possibly `undefined` — if it does, that's a real use you missed in Step 1; guard it.

- [ ] **Step 4: Manual verification**

Start the app (`npm run dev` / the Docker flow), go to **Parse Agent**, upload a small PDF, and confirm:
- you're navigated to the run detail page and the status badge shows `running` then flips to `completed` without a manual refresh (polling);
- the graph strip shows `parse` and `health_check` turning green;
- clicking a step fills the detail panel with input/output keys and the state delta;
- the `parse` step's detail shows "Open parsed document in results viewer" and it lands on `/parse-runs/<id>` rendering the parsed content with no `documentId` errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ParseRunDetailPage.tsx frontend/src/App.tsx
git commit -m "feat(parse-agent-ui): document-less parse-run viewer route for trace handoff"
```

---

## Self-Review

**Spec coverage (spec §6 Frontend):**
- Graph strip (top), nodes colored by state → Task 4 `GraphStrip`, composed in Task 5. ✓
- Timeline (below), read/wrote keys per step, selected step highlighted → Task 4 `RunTimeline`. ✓
- Detail panel on select, in/out values + meta → Task 4 `StepDetailPanel`. ✓
- Polling ~1s while `status == running`, stop on terminal → Task 3 `useParseAgentRun` (2s interval — chosen to match the sibling `useAgentRun`'s conservative cadence; spec says "~1s", 2s is within intent and halves request volume). ✓
- Results-viewer handoff links out rather than re-rendering parsed content → Task 4 link to `/parse-runs/{parseRunId}`, route added in Task 6. ✓
- Entry point (runs list) → Task 1 backend list endpoint + Task 5 list page. ✓ *(This is an addition to the spec, agreed with the user: the spec described only the detail page, but without a list, runs are unreachable after navigation.)*
- **Not covered (intentionally deferred):** human review UI, escalation branches in the graph strip (the strip renders `graphNodes` from the API, so branches appear automatically when v2 adds them), SSE/streamed transport, failure-path per-step trace (v1 backend limitation).

**Placeholder scan:** none — every step has complete code or an exact edit instruction. Task 6 Step 1 is an inspect-and-guard instruction rather than a code block because the target file's current `documentId` uses must be read in place; the two known uses and the required behavior for each are named explicitly.

**Type consistency:** `ParseAgentRunDetail { run, steps, graphNodes }` matches the backend `ParseAgentRunDetailResponse`; `ParseAgentRunSummary` fields match `ParseAgentRunSummary` (backend) and the Task 1 list response; `startParseAgentRun` returns `{ runId }` matching `ParseAgentRunCreatedResponse`. Component props match the types they consume across Tasks 4–5 (`graphNodes`/`steps`/`runStatus`/`selectedNode`/`onSelectNode`, `steps`/`selectedStepId`/`onSelectStep`, `step`). Hook return shapes match page usage.

## Known follow-ups (out of scope)

- Failed runs show `run.error` but no per-step trace (v1 backend limitation, documented in the spec).
- No delete-run action (the backend has no delete endpoint for parse-agent runs).
- The graph strip derives node state from the presence of steps; once v2 adds branches/loops, revisit `nodeState` (a node could legitimately run twice).
