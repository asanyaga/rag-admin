# Experiment Multi-Run Comparison

**Date:** 2026-06-22
**Status:** Approved

## Problem

The experiment detail page shows a leaderboard with aggregate F1 deltas but no per-query breakdown across all variants. The existing "Compare" button is broken (always picks the first two completed runs) and navigates away from the experiment context to a pairwise-only view. Ablation studies require seeing all variants side-by-side at the query level to understand where each configuration wins or loses.

## Decision: Keep "Compare Selected" in EvalRunsTab

The checkbox-based "Compare Selected" feature in the all-runs list serves a distinct use case: ad-hoc pairwise comparison of any two runs regardless of experiment (e.g. cross-experiment spot checks). It is not superseded by this feature and should be left as-is. The broken "Compare" button on the experiment page is superseded and will be replaced.

## Backend

### New Endpoint

```
GET /projects/{project_id}/experiments/{experiment_id}/compare
→ ExperimentComparisonResponse
```

### Repository

New method on `ExperimentRepository`:

```python
async def get_for_comparison(
    self, experiment_id: UUID, project_id: UUID
) -> Experiment | None
```

Loads the experiment with all completed runs, each with their results and associated query text. Uses `selectinload` throughout to avoid lazy-load issues:

```
experiment
  └── runs (filter: status in [completed, partial_failure])
        └── results
              └── query
```

### Service

New method on `ExperimentService`:

```python
async def compare(
    self, experiment_id: UUID, project_id: UUID
) -> ExperimentComparisonResponse
```

Logic:
1. Calls `get_for_comparison`; raises `NotFoundError` if experiment not found or not in project
2. Collects the union of all `query_id` values across all completed runs
3. For each query, builds one `ComparisonRow` with a `results` dict keyed by `run_id`
4. Computes `delta_f1` for each cell: `run_f1 - baseline_f1` for that query (null if baseline has no result for that query, or if this run has no result for that query)
5. Returns the full response

### Response Schema

```python
class RunMeta(BaseModel):
    id: UUID
    name: str
    variant_label: str | None
    avg_f1: float | None

class PerRunMetrics(BaseModel):
    precision: float
    recall: float
    f1: float
    delta_f1: float | None  # vs baseline for this query; null if baseline missing

class ComparisonRow(BaseModel):
    query_id: UUID
    query_text: str
    results: dict[str, PerRunMetrics]  # keyed by run_id (str)

class ExperimentComparisonResponse(BaseModel):
    experiment_id: UUID
    experiment_name: str
    baseline_run_id: UUID | None
    runs: list[RunMeta]  # all completed runs; baseline first if set
    rows: list[ComparisonRow]
```

### Router

Add to `backend/app/routers/experiments.py`:

```python
@router.get("/{experiment_id}/compare", response_model=ExperimentComparisonResponse)
async def compare_experiment(...)
```

Catches `NotFoundError` → 404.

---

## Frontend

### New Route

```
/evaluation/experiments/:experimentId/compare
→ ExperimentComparisonPage
```

Add to `App.tsx` alongside the existing experiment detail route.

### API Layer (`api/experiments.ts`)

New function:

```typescript
compareExperiment(projectId: string, experimentId: string): Promise<ExperimentComparison>
```

Calls `GET /projects/:projectId/experiments/:experimentId/compare`.

### Hook (`hooks/useExperiments.ts`)

New hook:

```typescript
useExperimentComparison(projectId: string | null, experimentId: string | null)
→ { comparison, isLoading, error }
```

### Types (`types/experiment.ts`)

```typescript
interface RunMeta {
  id: string
  name: string
  variantLabel: string | null
  avgF1: number | null
}

interface PerRunMetrics {
  precision: number
  recall: number
  f1: number
  deltaF1: number | null
}

interface ComparisonRow {
  queryId: string
  queryText: string
  results: Record<string, PerRunMetrics>  // keyed by run id
}

interface ExperimentComparison {
  experimentId: string
  experimentName: string
  baselineRunId: string | null
  runs: RunMeta[]
  rows: ComparisonRow[]
}
```

### `ExperimentComparisonPage` (`pages/ExperimentComparisonPage.tsx`)

**Header:** Back arrow → `/evaluation/experiments/:id`, experiment name.

**Run summary row:** One card per run showing name, variant label, avg F1. Baseline run gets a "Baseline" badge. Cards are ordered baseline-first.

**Table controls (above table):**
- Filter buttons: All | Better than baseline | Worse than baseline | Same — classification is based on the **maximum `delta_f1` across all non-baseline runs** for that query: positive (> 0.001) → Better, negative (< -0.001) → Worse, otherwise → Same. A query where one run improves and another regresses classifies as Better (the best result leads).
- Expand toggle: toggles between F1-only and P / R / F1 per run column.

**Per-query table:**
- Columns: Query | [Run 1] | [Run 2] | … | [Run N]
- Column header is the run name; clicking it sorts rows by that run's F1 (descending, nulls last). A second click on the same header reverses sort direction.
- In collapsed mode (default): each run cell shows `72.3%` with a colored delta `+4.1` (green) or `-2.0` (red). No delta shown for the baseline column.
- In expanded mode: each run column splits into three sub-columns (P / R / F1), with delta shown only on F1.
- If a run has no result for a query: cell shows `—`.

### Entry Point Change (`ExperimentDetailPage.tsx`)

Replace the existing "Compare" button (which hardcodes `completedRuns[0]` and `completedRuns[1]`) with a **"Per-Query Analysis"** button:

```tsx
{completedCount >= 2 && (
  <Button size="sm" variant="outline" onClick={() =>
    navigate(`/evaluation/experiments/${experiment.id}/compare`)
  }>
    <GitCompareArrows className="mr-2 h-4 w-4" />
    Per-Query Analysis
  </Button>
)}
```

No other changes to `ExperimentDetailPage`, `RunComparisonPage`, or `EvalRunsTab`.

---

## Out of Scope

- Statistical significance / confidence intervals
- Cross-run variance filter ("high disagreement" queries)
- Hiding/showing individual run columns
- Saving or exporting the comparison view
