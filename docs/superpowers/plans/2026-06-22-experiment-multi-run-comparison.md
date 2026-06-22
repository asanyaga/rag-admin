# Experiment Multi-Run Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-query multi-run comparison page for experiments, accessible at `/evaluation/experiments/:id/compare`, replacing the broken pairwise "Compare" button on the experiment detail page.

**Architecture:** New backend endpoint `GET /projects/{project_id}/experiments/{experiment_id}/compare` loads all completed runs with their per-query results in one query and returns a structured response. A new frontend page renders a sortable, filterable table with one column per run. The existing pairwise `RunComparisonPage` and the "Compare Selected" feature in `EvalRunsTab` are untouched.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 async (backend); React 18 / TypeScript / shadcn/ui / Tailwind CSS (frontend)

## Global Constraints

- All SQLAlchemy queries must use `selectinload` for relationship loading — no lazy loads
- `EvalRun.status` is an `EvalRunStatus` enum; compare with `EvalRunStatus.completed` and `EvalRunStatus.partial_failure`
- `EvalRun.metrics` is a JSON dict with keys `avgF1`, `avgPrecision`, `avgRecall` (may be `None`)
- Frontend API calls use `apiClient` from `@/api/client`; hooks use `useState` + `useCallback` + `useEffect`
- All new UI uses shadcn/ui components and Tailwind CSS — no raw HTML styling
- Backend test commands: `uv run --directory backend python -m pytest <path> -v -o "addopts="`
- Frontend lint: `npm run --prefix frontend lint`; build: `npm run --prefix frontend build`

---

## File Map

**Create:**
- `backend/app/schemas/experiment_comparison.py` — Pydantic response schemas
- `backend/tests/services/test_experiment_comparison_service.py` — service unit tests
- `frontend/src/components/evaluation/ExperimentComparisonTable.tsx` — per-query table with sort/filter/expand
- `frontend/src/pages/ExperimentComparisonPage.tsx` — full comparison page

**Modify:**
- `backend/app/repositories/experiment_repository.py` — add `get_for_comparison` method
- `backend/app/services/experiment_service.py` — add `compare` method + schema imports
- `backend/app/routers/experiments.py` — add `GET /{experiment_id}/compare` endpoint
- `frontend/src/types/experiment.ts` — add 4 new types
- `frontend/src/api/experiments.ts` — add `compareExperiment` function
- `frontend/src/hooks/useExperiments.ts` — add `useExperimentComparison` hook
- `frontend/src/App.tsx` — import + register new route
- `frontend/src/pages/ExperimentDetailPage.tsx` — replace broken "Compare" button

---

### Task 1: Backend schemas

**Files:**
- Create: `backend/app/schemas/experiment_comparison.py`

**Interfaces:**
- Produces: `RunMeta`, `PerRunMetrics`, `ComparisonRow`, `ExperimentComparisonResponse` — used by Task 3 (service) and Task 4 (router)

- [ ] **Step 1: Create the schema file**

```python
# backend/app/schemas/experiment_comparison.py
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class RunMeta(BaseModel):
    id: UUID
    name: str
    variant_label: str | None = Field(None, alias="variantLabel")
    avg_f1: float | None = Field(None, alias="avgF1")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PerRunMetrics(BaseModel):
    precision: float
    recall: float
    f1: float
    delta_f1: float | None = Field(None, alias="deltaF1")

    model_config = ConfigDict(populate_by_name=True)


class ComparisonRow(BaseModel):
    query_id: UUID = Field(..., alias="queryId")
    query_text: str = Field(..., alias="queryText")
    results: dict[str, PerRunMetrics]  # keyed by str(run_id)

    model_config = ConfigDict(populate_by_name=True)


class ExperimentComparisonResponse(BaseModel):
    experiment_id: UUID = Field(..., alias="experimentId")
    experiment_name: str = Field(..., alias="experimentName")
    baseline_run_id: UUID | None = Field(None, alias="baselineRunId")
    runs: list[RunMeta]
    rows: list[ComparisonRow]

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/experiment_comparison.py
git commit -m "feat(experiments): add experiment comparison response schemas"
```

---

### Task 2: Repository method

**Files:**
- Modify: `backend/app/repositories/experiment_repository.py`

**Interfaces:**
- Consumes: `Experiment` model (has `.runs`, `.baseline_run_id`); `EvalRun` model (has `.results`, `.status`); `EvalRunResult` model (has `.query_id`, `.precision`, `.recall`, `.f1`, `.query`); `GoldenSetQuery` model (has `.query_text`)
- Produces: `ExperimentRepository.get_for_comparison(experiment_id: UUID, project_id: UUID) -> Experiment | None`

- [ ] **Step 1: Add import for `EvalRunResult` and `GoldenSetQuery` at the top of the repository file**

The file currently imports `Experiment` and `EvalRun`. Add:

```python
from app.models.eval_run import EvalRun, EvalRunResult
from app.models.golden_set import GoldenSetQuery
```

Find the existing imports section:
```python
from app.models.experiment import Experiment
from app.models.eval_run import EvalRun
```

Replace with:
```python
from app.models.experiment import Experiment
from app.models.eval_run import EvalRun, EvalRunResult
from app.models.golden_set import GoldenSetQuery
```

- [ ] **Step 2: Add `get_for_comparison` method to `ExperimentRepository`**

Add after the `get_run_count` method (end of class):

```python
    async def get_for_comparison(
        self, experiment_id: UUID, project_id: UUID
    ) -> Experiment | None:
        """Load experiment with all runs and their per-query results for multi-run comparison."""
        result = await self.session.execute(
            select(Experiment)
            .options(
                selectinload(Experiment.runs)
                .selectinload(EvalRun.results)
                .selectinload(EvalRunResult.query),
            )
            .where(
                Experiment.id == experiment_id,
                Experiment.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()
```

- [ ] **Step 3: Verify the import for `GoldenSetQuery` is correct**

```bash
uv run --directory backend python -c "from app.models.golden_set import GoldenSetQuery; print('ok')"
```

Expected output: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/repositories/experiment_repository.py
git commit -m "feat(experiments): add get_for_comparison repository method"
```

---

### Task 3: Service method + tests

**Files:**
- Modify: `backend/app/services/experiment_service.py`
- Create: `backend/tests/services/test_experiment_comparison_service.py`

**Interfaces:**
- Consumes: `ExperimentRepository.get_for_comparison` (Task 2); `ExperimentComparisonResponse`, `RunMeta`, `PerRunMetrics`, `ComparisonRow` (Task 1)
- Produces: `ExperimentService.compare(experiment_id: UUID, project_id: UUID) -> ExperimentComparisonResponse`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/services/test_experiment_comparison_service.py
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.experiment_service import ExperimentService
from app.services.exceptions import NotFoundError


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_repo):
    return ExperimentService(mock_repo)


def _make_result(query_id, query_text, precision, recall, f1):
    res = MagicMock()
    res.query_id = query_id
    res.precision = precision
    res.recall = recall
    res.f1 = f1
    res.query = MagicMock()
    res.query.query_text = query_text
    return res


def _make_run(run_id, name, variant_label, status_value, avg_f1, results):
    from app.models.eval_run import EvalRunStatus
    run = MagicMock()
    run.id = run_id
    run.name = name
    run.variant_label = variant_label
    run.status = EvalRunStatus(status_value)
    run.metrics = {"avgF1": avg_f1} if avg_f1 is not None else None
    run.results = results
    return run


def _make_experiment(exp_id, project_id, name, baseline_run_id, runs):
    exp = MagicMock()
    exp.id = exp_id
    exp.project_id = project_id
    exp.name = name
    exp.baseline_run_id = baseline_run_id
    exp.runs = runs
    return exp


@pytest.mark.asyncio
async def test_compare_not_found_raises(service, mock_repo):
    mock_repo.get_for_comparison.return_value = None
    with pytest.raises(NotFoundError):
        await service.compare(uuid4(), uuid4())


@pytest.mark.asyncio
async def test_compare_returns_only_completed_runs(service, mock_repo):
    exp_id = uuid4()
    project_id = uuid4()
    qid = uuid4()

    pending_run = _make_run(uuid4(), "Pending", None, "pending", None, [])
    completed_run = _make_run(
        uuid4(), "Done", "v1", "completed", 0.8,
        [_make_result(qid, "What is X?", 0.9, 0.7, 0.8)]
    )
    exp = _make_experiment(exp_id, project_id, "My Exp", completed_run.id, [pending_run, completed_run])
    mock_repo.get_for_comparison.return_value = exp

    response = await service.compare(exp_id, project_id)

    assert len(response.runs) == 1
    assert response.runs[0].name == "Done"


@pytest.mark.asyncio
async def test_compare_baseline_is_first(service, mock_repo):
    exp_id = uuid4()
    project_id = uuid4()
    baseline_id = uuid4()
    challenger_id = uuid4()
    qid = uuid4()

    baseline = _make_run(
        baseline_id, "Baseline", None, "completed", 0.6,
        [_make_result(qid, "Q1", 0.6, 0.6, 0.6)]
    )
    challenger = _make_run(
        challenger_id, "Challenger", "top_k=10", "completed", 0.8,
        [_make_result(qid, "Q1", 0.8, 0.8, 0.8)]
    )
    exp = _make_experiment(exp_id, project_id, "Exp", baseline_id, [challenger, baseline])
    mock_repo.get_for_comparison.return_value = exp

    response = await service.compare(exp_id, project_id)

    assert response.runs[0].id == baseline_id


@pytest.mark.asyncio
async def test_compare_delta_computed_vs_baseline(service, mock_repo):
    exp_id = uuid4()
    project_id = uuid4()
    baseline_id = uuid4()
    challenger_id = uuid4()
    qid = uuid4()

    baseline = _make_run(
        baseline_id, "Baseline", None, "completed", 0.6,
        [_make_result(qid, "Q1", 0.6, 0.6, 0.6)]
    )
    challenger = _make_run(
        challenger_id, "Challenger", "v2", "completed", 0.8,
        [_make_result(qid, "Q1", 0.8, 0.8, 0.8)]
    )
    exp = _make_experiment(exp_id, project_id, "Exp", baseline_id, [baseline, challenger])
    mock_repo.get_for_comparison.return_value = exp

    response = await service.compare(exp_id, project_id)

    assert len(response.rows) == 1
    row = response.rows[0]
    baseline_metrics = row.results[str(baseline_id)]
    challenger_metrics = row.results[str(challenger_id)]
    assert baseline_metrics.delta_f1 is None  # baseline has no delta vs itself
    assert round(challenger_metrics.delta_f1, 4) == round(0.8 - 0.6, 4)


@pytest.mark.asyncio
async def test_compare_missing_result_for_run(service, mock_repo):
    """Run with no result for a query should be absent from that row's results dict."""
    exp_id = uuid4()
    project_id = uuid4()
    baseline_id = uuid4()
    challenger_id = uuid4()
    q1 = uuid4()
    q2 = uuid4()

    baseline = _make_run(
        baseline_id, "Baseline", None, "completed", 0.6,
        [_make_result(q1, "Q1", 0.6, 0.6, 0.6), _make_result(q2, "Q2", 0.5, 0.5, 0.5)]
    )
    challenger = _make_run(
        challenger_id, "Challenger", "v2", "completed", 0.8,
        [_make_result(q1, "Q1", 0.8, 0.8, 0.8)]  # no result for q2
    )
    exp = _make_experiment(exp_id, project_id, "Exp", baseline_id, [baseline, challenger])
    mock_repo.get_for_comparison.return_value = exp

    response = await service.compare(exp_id, project_id)

    assert len(response.rows) == 2
    q2_row = next(r for r in response.rows if r.query_id == q2)
    assert str(challenger_id) not in q2_row.results
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend python -m pytest tests/services/test_experiment_comparison_service.py -v -o "addopts="
```

Expected: `ImportError` or `AttributeError` — `service.compare` does not exist yet.

- [ ] **Step 3: Add the `compare` method to `ExperimentService`**

Add these imports at the top of `backend/app/services/experiment_service.py` (after the existing imports):

```python
from app.models.eval_run import EvalRunStatus
from app.schemas.experiment_comparison import (
    ExperimentComparisonResponse,
    RunMeta,
    PerRunMetrics,
    ComparisonRow,
)
```

Add the method to the `ExperimentService` class (after the `delete` method):

```python
    async def compare(
        self, experiment_id: UUID, project_id: UUID
    ) -> ExperimentComparisonResponse:
        experiment = await self.repo.get_for_comparison(experiment_id, project_id)
        if not experiment:
            raise NotFoundError(f"Experiment {experiment_id} not found")

        completed_statuses = {EvalRunStatus.completed, EvalRunStatus.partial_failure}
        completed_runs = [r for r in experiment.runs if r.status in completed_statuses]

        baseline_id = experiment.baseline_run_id

        def _sort_key(run):
            is_baseline = 0 if run.id == baseline_id else 1
            avg_f1 = run.metrics.get("avgF1") if run.metrics else None
            return (is_baseline, -(avg_f1 or 0))

        completed_runs.sort(key=_sort_key)

        run_metas = [
            RunMeta(
                id=run.id,
                name=run.name,
                variant_label=run.variant_label,
                avg_f1=run.metrics.get("avgF1") if run.metrics else None,
            )
            for run in completed_runs
        ]

        # Index each run's results by query_id
        run_result_maps: dict[UUID, dict[UUID, object]] = {
            run.id: {res.query_id: res for res in run.results}
            for run in completed_runs
        }

        # Union of all query IDs across completed runs
        all_query_ids: set[UUID] = set()
        for result_map in run_result_maps.values():
            all_query_ids.update(result_map.keys())

        # Collect query texts — first run that has a result for a query wins
        query_texts: dict[UUID, str] = {}
        for run in completed_runs:
            for res in run.results:
                if res.query_id not in query_texts and res.query:
                    query_texts[res.query_id] = res.query.query_text

        # Baseline result map for delta computation
        baseline_result_map = run_result_maps.get(baseline_id, {}) if baseline_id else {}

        rows: list[ComparisonRow] = []
        for qid in all_query_ids:
            baseline_res = baseline_result_map.get(qid)
            baseline_f1 = baseline_res.f1 if baseline_res else None

            results_dict: dict[str, PerRunMetrics] = {}
            for run in completed_runs:
                res = run_result_maps[run.id].get(qid)
                if res is None:
                    continue
                # Baseline column has no delta vs itself
                if baseline_id and run.id == baseline_id:
                    delta = None
                elif baseline_f1 is not None:
                    delta = round(res.f1 - baseline_f1, 4)
                else:
                    delta = None
                results_dict[str(run.id)] = PerRunMetrics(
                    precision=res.precision,
                    recall=res.recall,
                    f1=res.f1,
                    delta_f1=delta,
                )

            rows.append(ComparisonRow(
                query_id=qid,
                query_text=query_texts.get(qid, ""),
                results=results_dict,
            ))

        return ExperimentComparisonResponse(
            experiment_id=experiment.id,
            experiment_name=experiment.name,
            baseline_run_id=baseline_id,
            runs=run_metas,
            rows=rows,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run --directory backend python -m pytest tests/services/test_experiment_comparison_service.py -v -o "addopts="
```

Expected: 5 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/experiment_service.py backend/tests/services/test_experiment_comparison_service.py
git commit -m "feat(experiments): add compare service method with unit tests"
```

---

### Task 4: Router endpoint

**Files:**
- Modify: `backend/app/routers/experiments.py`

**Interfaces:**
- Consumes: `ExperimentService.compare` (Task 3); `ExperimentComparisonResponse` (Task 1)
- Produces: `GET /projects/{project_id}/experiments/{experiment_id}/compare → ExperimentComparisonResponse`

- [ ] **Step 1: Add the schema import to the router**

In `backend/app/routers/experiments.py`, find the existing schema imports:

```python
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentUpdate,
    ExperimentResponse,
    ExperimentDetailResponse,
)
```

Add below it:

```python
from app.schemas.experiment_comparison import ExperimentComparisonResponse
```

- [ ] **Step 2: Add the endpoint**

The route `/compare` must come **before** `/{experiment_id}` to avoid being swallowed by the path parameter. Add before the existing `@router.get("/{experiment_id}", ...)` route:

```python
@router.get("/{experiment_id}/compare", response_model=ExperimentComparisonResponse)
async def compare_experiment(
    project_id: UUID,
    experiment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExperimentService = Depends(get_experiment_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.compare(experiment_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 3: Verify the backend starts without import errors**

```bash
uv run --directory backend python -c "from app.routers.experiments import router; print('ok')"
```

Expected output: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/experiments.py
git commit -m "feat(experiments): add GET /{experiment_id}/compare endpoint"
```

---

### Task 5: Frontend types, API function, and hook

**Files:**
- Modify: `frontend/src/types/experiment.ts`
- Modify: `frontend/src/api/experiments.ts`
- Modify: `frontend/src/hooks/useExperiments.ts`

**Interfaces:**
- Produces:
  - Types: `RunMeta`, `PerRunMetrics`, `ComparisonRow`, `ExperimentComparison`
  - API: `compareExperiment(projectId: string, experimentId: string): Promise<ExperimentComparison>`
  - Hook: `useExperimentComparison(projectId: string | null, experimentId: string | null): { comparison: ExperimentComparison | null, isLoading: boolean, error: string | null }`

- [ ] **Step 1: Add types to `frontend/src/types/experiment.ts`**

Append to the end of the file:

```typescript
export interface RunMeta {
  id: string
  name: string
  variantLabel: string | null
  avgF1: number | null
}

export interface PerRunMetrics {
  precision: number
  recall: number
  f1: number
  deltaF1: number | null
}

export interface ComparisonRow {
  queryId: string
  queryText: string
  results: Record<string, PerRunMetrics>
}

export interface ExperimentComparison {
  experimentId: string
  experimentName: string
  baselineRunId: string | null
  runs: RunMeta[]
  rows: ComparisonRow[]
}
```

- [ ] **Step 2: Add `compareExperiment` to `frontend/src/api/experiments.ts`**

Append to the end of the file:

```typescript
export async function compareExperiment(
  projectId: string,
  experimentId: string
): Promise<ExperimentComparison> {
  const response = await apiClient.get<ExperimentComparison>(
    `/projects/${projectId}/experiments/${experimentId}/compare`
  )
  return response.data
}
```

Also add `ExperimentComparison` to the imports at the top of the file:

```typescript
import type {
  Experiment,
  ExperimentDetail,
  ExperimentComparison,
  CreateExperimentRequest,
  UpdateExperimentRequest,
} from '@/types/experiment'
```

- [ ] **Step 3: Add `useExperimentComparison` to `frontend/src/hooks/useExperiments.ts`**

Append to the end of the file:

```typescript
// ---------------------------------------------------------------------------
// useExperimentComparison — multi-run per-query comparison for an experiment
// ---------------------------------------------------------------------------

interface UseExperimentComparisonReturn {
  comparison: ExperimentComparison | null
  isLoading: boolean
  error: string | null
}

export function useExperimentComparison(
  projectId: string | null,
  experimentId: string | null
): UseExperimentComparisonReturn {
  const [comparison, setComparison] = useState<ExperimentComparison | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    if (!projectId || !experimentId) return
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.compareExperiment(projectId, experimentId)
      setComparison(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load comparison')
    } finally {
      setIsLoading(false)
    }
  }, [projectId, experimentId])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { comparison, isLoading, error }
}
```

Also add `ExperimentComparison` to the type import at the top of the hooks file:

```typescript
import type {
  Experiment,
  ExperimentDetail,
  ExperimentComparison,
  CreateExperimentRequest,
  UpdateExperimentRequest,
} from '@/types/experiment'
```

- [ ] **Step 4: Check TypeScript compiles**

```bash
npm run --prefix frontend build 2>&1 | head -30
```

Expected: build succeeds (or only pre-existing errors, none in the files touched here).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/experiment.ts frontend/src/api/experiments.ts frontend/src/hooks/useExperiments.ts
git commit -m "feat(experiments): add comparison types, API function, and hook"
```

---

### Task 6: ExperimentComparisonTable component

**Files:**
- Create: `frontend/src/components/evaluation/ExperimentComparisonTable.tsx`

**Interfaces:**
- Consumes: `RunMeta`, `PerRunMetrics`, `ComparisonRow` from `@/types/experiment` (Task 5)
- Produces: `ExperimentComparisonTable` component — used by Task 7

Props:
```typescript
interface ExperimentComparisonTableProps {
  runs: RunMeta[]
  rows: ComparisonRow[]
  baselineRunId: string | null
}
```

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/evaluation/ExperimentComparisonTable.tsx
import { useState, useMemo } from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { RunMeta, ComparisonRow } from '@/types/experiment'

type FilterMode = 'all' | 'better' | 'worse' | 'same'

interface ExperimentComparisonTableProps {
  runs: RunMeta[]
  rows: ComparisonRow[]
  baselineRunId: string | null
}

export function ExperimentComparisonTable({
  runs,
  rows,
  baselineRunId,
}: ExperimentComparisonTableProps) {
  const [sortRunId, setSortRunId] = useState<string | null>(null)
  const [sortAsc, setSortAsc] = useState(false)
  const [filter, setFilter] = useState<FilterMode>('all')
  const [expanded, setExpanded] = useState(false)

  const nonBaselineRuns = runs.filter((r) => r.id !== baselineRunId)

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      if (filter === 'all') return true
      const deltas = nonBaselineRuns.map((r) => row.results[r.id]?.deltaF1 ?? 0)
      const maxDelta = deltas.length > 0 ? Math.max(...deltas) : 0
      if (filter === 'better') return maxDelta > 0.001
      if (filter === 'worse') return maxDelta < -0.001
      return Math.abs(maxDelta) <= 0.001
    })
  }, [rows, filter, nonBaselineRuns])

  const sortedRows = useMemo(() => {
    if (!sortRunId) return filteredRows
    return [...filteredRows].sort((a, b) => {
      const af1 = a.results[sortRunId]?.f1 ?? -1
      const bf1 = b.results[sortRunId]?.f1 ?? -1
      return sortAsc ? af1 - bf1 : bf1 - af1
    })
  }, [filteredRows, sortRunId, sortAsc])

  const handleSortClick = (runId: string) => {
    if (sortRunId === runId) {
      setSortAsc((prev) => !prev)
    } else {
      setSortRunId(runId)
      setSortAsc(false)
    }
  }

  const SortIcon = ({ runId }: { runId: string }) => {
    if (sortRunId !== runId) return <ChevronsUpDown className="h-3 w-3 ml-1 opacity-40" />
    return sortAsc
      ? <ChevronUp className="h-3 w-3 ml-1" />
      : <ChevronDown className="h-3 w-3 ml-1" />
  }

  const formatPct = (v: number) => (v * 100).toFixed(1) + '%'

  const DeltaSpan = ({ delta }: { delta: number | null }) => {
    if (delta === null) return null
    const pct = (delta * 100).toFixed(1)
    const label = delta > 0 ? `+${pct}` : pct
    const color =
      delta > 0.001
        ? 'text-emerald-600'
        : delta < -0.001
          ? 'text-red-500'
          : 'text-muted-foreground'
    return <span className={`text-xs ml-1 ${color}`}>{label}</span>
  }

  const filterButtons: { label: string; value: FilterMode }[] = [
    { label: 'All', value: 'all' },
    { label: 'Better', value: 'better' },
    { label: 'Worse', value: 'worse' },
    { label: 'Same', value: 'same' },
  ]

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          {filterButtons.map(({ label, value }) => (
            <Button
              key={value}
              size="sm"
              variant={filter === value ? 'default' : 'outline'}
              className="h-7 text-xs"
              onClick={() => setFilter(value)}
            >
              {label}
            </Button>
          ))}
        </div>
        <Button
          size="sm"
          variant="outline"
          className="h-7 text-xs"
          onClick={() => setExpanded((p) => !p)}
        >
          {expanded ? 'Show F1 only' : 'Expand P / R / F1'}
        </Button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="min-w-[200px]">Query</TableHead>
              {runs.map((run) => {
                const isBaseline = run.id === baselineRunId
                if (expanded) {
                  return (
                    <>
                      <TableHead
                        key={`${run.id}-p`}
                        className="text-right text-xs"
                      >
                        {run.name} P
                      </TableHead>
                      <TableHead
                        key={`${run.id}-r`}
                        className="text-right text-xs"
                      >
                        R
                      </TableHead>
                      <TableHead
                        key={`${run.id}-f1`}
                        className="text-right text-xs cursor-pointer select-none"
                        onClick={() => handleSortClick(run.id)}
                      >
                        <span className="flex items-center justify-end">
                          F1
                          {!isBaseline && <SortIcon runId={run.id} />}
                        </span>
                      </TableHead>
                    </>
                  )
                }
                return (
                  <TableHead
                    key={run.id}
                    className="text-right text-xs cursor-pointer select-none"
                    onClick={() => handleSortClick(run.id)}
                  >
                    <span className="flex items-center justify-end">
                      {run.name}
                      {run.variantLabel && (
                        <span className="text-muted-foreground ml-1">({run.variantLabel})</span>
                      )}
                      {!isBaseline && <SortIcon runId={run.id} />}
                    </span>
                  </TableHead>
                )
              })}
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedRows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={expanded ? runs.length * 3 + 1 : runs.length + 1}
                  className="text-center text-muted-foreground py-8"
                >
                  No queries match this filter.
                </TableCell>
              </TableRow>
            ) : (
              sortedRows.map((row) => (
                <TableRow key={row.queryId}>
                  <TableCell className="text-sm max-w-[300px] truncate">
                    {row.queryText}
                  </TableCell>
                  {runs.map((run) => {
                    const m = row.results[run.id]
                    if (expanded) {
                      return (
                        <>
                          <TableCell key={`${run.id}-p`} className="text-right font-mono text-sm">
                            {m ? formatPct(m.precision) : '—'}
                          </TableCell>
                          <TableCell key={`${run.id}-r`} className="text-right font-mono text-sm">
                            {m ? formatPct(m.recall) : '—'}
                          </TableCell>
                          <TableCell key={`${run.id}-f1`} className="text-right font-mono text-sm">
                            {m ? (
                              <>
                                {formatPct(m.f1)}
                                <DeltaSpan delta={m.deltaF1} />
                              </>
                            ) : '—'}
                          </TableCell>
                        </>
                      )
                    }
                    return (
                      <TableCell key={run.id} className="text-right font-mono text-sm">
                        {m ? (
                          <>
                            {formatPct(m.f1)}
                            <DeltaSpan delta={m.deltaF1} />
                          </>
                        ) : '—'}
                      </TableCell>
                    )
                  })}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <p className="text-xs text-muted-foreground">
        Showing {sortedRows.length} of {rows.length} queries
      </p>
    </div>
  )
}
```

- [ ] **Step 2: Check TypeScript compiles**

```bash
npm run --prefix frontend build 2>&1 | head -30
```

Expected: no new errors in `ExperimentComparisonTable.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/evaluation/ExperimentComparisonTable.tsx
git commit -m "feat(experiments): add ExperimentComparisonTable component"
```

---

### Task 7: ExperimentComparisonPage

**Files:**
- Create: `frontend/src/pages/ExperimentComparisonPage.tsx`

**Interfaces:**
- Consumes: `useExperimentComparison` (Task 5); `ExperimentComparisonTable` (Task 6); `RunMeta`, `ExperimentComparison` from `@/types/experiment`
- Produces: `ExperimentComparisonPage` default export — used by Task 8

- [ ] **Step 1: Create the page**

```tsx
// frontend/src/pages/ExperimentComparisonPage.tsx
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2, Star } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { ScorePill } from '@/components/evaluation/ScorePill'
import { ExperimentComparisonTable } from '@/components/evaluation/ExperimentComparisonTable'
import { useProject } from '@/contexts/ProjectContext'
import { useExperimentComparison } from '@/hooks/useExperiments'
import type { RunMeta } from '@/types/experiment'

function RunSummaryCard({
  run,
  isBaseline,
}: {
  run: RunMeta
  isBaseline: boolean
}) {
  return (
    <Card className={isBaseline ? 'border-primary/40 bg-primary/5' : ''}>
      <CardContent className="pt-4 pb-4 space-y-1">
        <div className="flex items-center gap-2">
          {isBaseline && <Star className="h-4 w-4 text-amber-500 fill-amber-500" />}
          <p className="font-semibold text-sm truncate">{run.name}</p>
          {isBaseline && <Badge variant="outline" className="text-xs">Baseline</Badge>}
        </div>
        {run.variantLabel && (
          <p className="text-xs text-muted-foreground">{run.variantLabel}</p>
        )}
        <div className="pt-1">
          <ScorePill score={run.avgF1} />
          <span className="text-xs text-muted-foreground ml-2">avg F1</span>
        </div>
      </CardContent>
    </Card>
  )
}

export default function ExperimentComparisonPage() {
  const { experimentId } = useParams<{ experimentId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const { comparison, isLoading, error } = useExperimentComparison(
    projectId,
    experimentId ?? null
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-24 text-destructive">{error}</div>
    )
  }

  if (!comparison) return null

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate(`/evaluation/experiments/${experimentId}`)}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Per-Query Analysis</h1>
          <p className="text-muted-foreground text-sm">{comparison.experimentName}</p>
        </div>
      </div>

      {/* Run summary cards */}
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: `repeat(${comparison.runs.length}, minmax(160px, 1fr))` }}
      >
        {comparison.runs.map((run) => (
          <RunSummaryCard
            key={run.id}
            run={run}
            isBaseline={run.id === comparison.baselineRunId}
          />
        ))}
      </div>

      {/* Per-query table */}
      <ExperimentComparisonTable
        runs={comparison.runs}
        rows={comparison.rows}
        baselineRunId={comparison.baselineRunId}
      />
    </div>
  )
}
```

- [ ] **Step 2: Check TypeScript compiles**

```bash
npm run --prefix frontend build 2>&1 | head -30
```

Expected: no errors in `ExperimentComparisonPage.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ExperimentComparisonPage.tsx
git commit -m "feat(experiments): add ExperimentComparisonPage"
```

---

### Task 8: Wire up route and replace entry point

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/ExperimentDetailPage.tsx`

**Interfaces:**
- Consumes: `ExperimentComparisonPage` (Task 7)

- [ ] **Step 1: Add the import to `App.tsx`**

Find the existing experiment import:

```typescript
import ExperimentDetailPage from './pages/ExperimentDetailPage'
```

Add after it:

```typescript
import ExperimentComparisonPage from './pages/ExperimentComparisonPage'
```

- [ ] **Step 2: Add the route to `App.tsx`**

Find the existing experiment detail route:

```typescript
          {
            path: 'evaluation/experiments/:experimentId',
            element: <ExperimentDetailPage />,
            handle: { breadcrumb: 'Experiment Detail' },
          },
```

Add **after** it (not before — the more specific `/compare` sub-path must not conflict):

```typescript
          {
            path: 'evaluation/experiments/:experimentId/compare',
            element: <ExperimentComparisonPage />,
            handle: { breadcrumb: 'Experiment Comparison' },
          },
```

- [ ] **Step 3: Replace the broken "Compare" button in `ExperimentDetailPage.tsx`**

Find the existing Compare button block (around line 226):

```tsx
        {completedCount >= 2 && (
          <Button size="sm" variant="outline" onClick={handleCompare}>
            <GitCompareArrows className="mr-2 h-4 w-4" />
            Compare
          </Button>
        )}
```

Replace with:

```tsx
        {completedCount >= 2 && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate(`/evaluation/experiments/${experiment.id}/compare`)}
          >
            <GitCompareArrows className="mr-2 h-4 w-4" />
            Per-Query Analysis
          </Button>
        )}
```

- [ ] **Step 4: Remove the now-unused `handleCompare` function from `ExperimentDetailPage.tsx`**

Find and delete this function (around line 95):

```tsx
  const handleCompare = () => {
    if (!experiment) return
    const completedRuns = experiment.runs.filter(
      (r) => r.status === 'completed' || r.status === 'partial_failure'
    )
    if (completedRuns.length >= 2) {
      navigate(
        `/evaluation/compare?runs=${completedRuns[0].id},${completedRuns[1].id}`
      )
    }
  }
```

- [ ] **Step 5: Final build check**

```bash
npm run --prefix frontend build 2>&1 | head -40
```

Expected: build succeeds with no errors.

- [ ] **Step 6: Final backend test run**

```bash
uv run --directory backend python -m pytest tests/services/test_experiment_comparison_service.py -v -o "addopts="
```

Expected: 5 tests PASSED.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/pages/ExperimentDetailPage.tsx
git commit -m "feat(experiments): wire up experiment comparison route and replace Compare button"
```
