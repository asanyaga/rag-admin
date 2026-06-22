# Run Vertical Emphasis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-run color identity to the Per-Query Analysis page so each experiment run has a visually distinct vertical lane in the comparison table.

**Architecture:** A `RUN_COLORS` palette constant assigns one of 6 Tailwind color tokens to each non-baseline run by index; the baseline always gets a neutral slate treatment. The color is threaded from `ExperimentComparisonPage` down to `RunSummaryCard` (left border) and `ExperimentComparisonTable` (column header top-border, cell background tint, expanded-mode group separator, sticky query column).

**Tech Stack:** React 18, TypeScript, Tailwind CSS, shadcn/ui

## Global Constraints

- No new npm packages — Tailwind and existing shadcn components only
- All Tailwind class names must appear as complete strings (no dynamic concatenation) so purge works correctly
- Do not change any backend code or API contracts
- Feature branch: `feat/run-vertical-emphasis`

---

### Task 1: Create feature branch and color utility

**Files:**
- Create: `frontend/src/lib/runColors.ts`
- Test: `frontend/src/lib/runColors.test.ts`

**Interfaces:**
- Produces:
  ```typescript
  interface RunColorSet {
    card: string        // border-l-* color class for RunSummaryCard left border
    headerTop: string   // border-t-* color class for table column header top border
    cellBg: string      // bg-* class for metric cell background tint
    groupBorder: string // border-l-* color class for first cell in expanded run group
  }
  function getRunColor(index: number): RunColorSet
  const BASELINE_COLOR: RunColorSet
  ```

- [ ] **Step 1: Create the feature branch**

```bash
git checkout -b feat/run-vertical-emphasis
```

- [ ] **Step 2: Write the failing test**

Create `frontend/src/lib/runColors.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { getRunColor, BASELINE_COLOR } from './runColors'

describe('getRunColor', () => {
  it('returns a color set for index 0', () => {
    const color = getRunColor(0)
    expect(color.card).toBeTruthy()
    expect(color.headerTop).toBeTruthy()
    expect(color.cellBg).toBeTruthy()
    expect(color.groupBorder).toBeTruthy()
  })

  it('wraps around for indices beyond palette length', () => {
    const color0 = getRunColor(0)
    const color6 = getRunColor(6)
    expect(color0.card).toBe(color6.card)
  })

  it('returns distinct colors for indices 0-5', () => {
    const cards = Array.from({ length: 6 }, (_, i) => getRunColor(i).card)
    const unique = new Set(cards)
    expect(unique.size).toBe(6)
  })

  it('exports BASELINE_COLOR with all required fields', () => {
    expect(BASELINE_COLOR.card).toBeTruthy()
    expect(BASELINE_COLOR.headerTop).toBeTruthy()
    expect(BASELINE_COLOR.cellBg).toBeTruthy()
    expect(BASELINE_COLOR.groupBorder).toBeTruthy()
  })
})
```

- [ ] **Step 3: Run to confirm failure**

```bash
cd frontend && npx vitest run src/lib/runColors.test.ts
```

Expected: `FAIL` — module not found.

- [ ] **Step 4: Implement `runColors.ts`**

Create `frontend/src/lib/runColors.ts`:

```typescript
export interface RunColorSet {
  card: string
  headerTop: string
  cellBg: string
  groupBorder: string
}

const PALETTE: RunColorSet[] = [
  { card: 'border-l-indigo-500',  headerTop: 'border-t-indigo-500',  cellBg: 'bg-indigo-50/60',  groupBorder: 'border-l-indigo-300' },
  { card: 'border-l-emerald-500', headerTop: 'border-t-emerald-500', cellBg: 'bg-emerald-50/60', groupBorder: 'border-l-emerald-300' },
  { card: 'border-l-amber-500',   headerTop: 'border-t-amber-500',   cellBg: 'bg-amber-50/60',   groupBorder: 'border-l-amber-300' },
  { card: 'border-l-rose-500',    headerTop: 'border-t-rose-500',    cellBg: 'bg-rose-50/60',    groupBorder: 'border-l-rose-300' },
  { card: 'border-l-violet-500',  headerTop: 'border-t-violet-500',  cellBg: 'bg-violet-50/60',  groupBorder: 'border-l-violet-300' },
  { card: 'border-l-sky-500',     headerTop: 'border-t-sky-500',     cellBg: 'bg-sky-50/60',     groupBorder: 'border-l-sky-300' },
]

export const BASELINE_COLOR: RunColorSet = {
  card: 'border-l-slate-400',
  headerTop: 'border-t-slate-400',
  cellBg: 'bg-slate-50/60',
  groupBorder: 'border-l-slate-300',
}

export function getRunColor(index: number): RunColorSet {
  return PALETTE[index % PALETTE.length]
}
```

- [ ] **Step 5: Run test to confirm pass**

```bash
cd frontend && npx vitest run src/lib/runColors.test.ts
```

Expected: all 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/runColors.ts frontend/src/lib/runColors.test.ts
git commit -m "feat(eval): add run color palette utility"
```

---

### Task 2: Update RunSummaryCard with color identity

**Files:**
- Modify: `frontend/src/pages/ExperimentComparisonPage.tsx`

**Interfaces:**
- Consumes: `getRunColor(index: number): RunColorSet`, `BASELINE_COLOR: RunColorSet` from `@/lib/runColors`
- Produces: `RunSummaryCard` accepts `colorSet: RunColorSet` prop and renders a `border-l-4` left border in the run's color; `ExperimentComparisonPage` builds a `runColors: RunColorSet[]` array (baseline → `BASELINE_COLOR`, others → `getRunColor(nonBaselineIndex++)` in order) and passes it to `ExperimentComparisonTable`

- [ ] **Step 1: Update `ExperimentComparisonPage.tsx`**

Replace the file with:

```typescript
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2, Star } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { ScorePill } from '@/components/evaluation/ScorePill'
import { ExperimentComparisonTable } from '@/components/evaluation/ExperimentComparisonTable'
import { useProject } from '@/contexts/ProjectContext'
import { useExperimentComparison } from '@/hooks/useExperiments'
import { getRunColor, BASELINE_COLOR } from '@/lib/runColors'
import type { RunMeta } from '@/types/experiment'
import type { RunColorSet } from '@/lib/runColors'

function RunSummaryCard({
  run,
  isBaseline,
  colorSet,
}: {
  run: RunMeta
  isBaseline: boolean
  colorSet: RunColorSet
}) {
  return (
    <Card className={`border-l-4 ${colorSet.card} ${isBaseline ? 'bg-primary/5' : ''}`}>
      <CardContent className="pt-4 pb-4 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          {isBaseline && <Star className="h-4 w-4 text-amber-500 fill-amber-500 shrink-0" />}
          <p className="font-semibold text-sm truncate">{run.name}</p>
          {isBaseline && <Badge variant="outline" className="text-xs shrink-0">Baseline</Badge>}
        </div>
        {run.variantLabel && (
          <p className="text-xs text-muted-foreground truncate">{run.variantLabel}</p>
        )}
        <div className="pt-1 flex items-center gap-2">
          <ScorePill score={run.avgF1} />
          <span className="text-xs text-muted-foreground">avg F1</span>
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

  let nonBaselineIndex = 0
  const runColors = comparison.runs.map((run) => {
    if (run.id === comparison.baselineRunId) return BASELINE_COLOR
    return getRunColor(nonBaselineIndex++)
  })

  return (
    <div className="space-y-6 max-w-7xl">
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

      <div
        className="grid gap-3"
        style={{
          gridTemplateColumns: `repeat(${Math.min(comparison.runs.length, 6)}, minmax(150px, 1fr))`,
        }}
      >
        {comparison.runs.map((run, i) => (
          <RunSummaryCard
            key={run.id}
            run={run}
            isBaseline={run.id === comparison.baselineRunId}
            colorSet={runColors[i]}
          />
        ))}
      </div>

      <ExperimentComparisonTable
        runs={comparison.runs}
        rows={comparison.rows}
        baselineRunId={comparison.baselineRunId}
        runColors={runColors}
      />
    </div>
  )
}
```

- [ ] **Step 2: Check TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

Expected: errors about `runColors` prop not existing on `ExperimentComparisonTable` — that's expected until Task 3.

- [ ] **Step 3: Commit (with TS error acknowledged — Task 3 will fix it)**

```bash
git add frontend/src/pages/ExperimentComparisonPage.tsx
git commit -m "feat(eval): thread run color identity through ExperimentComparisonPage"
```

---

### Task 3: Add vertical color emphasis to ExperimentComparisonTable

**Files:**
- Modify: `frontend/src/components/evaluation/ExperimentComparisonTable.tsx`

**Interfaces:**
- Consumes: `runColors: RunColorSet[]` prop (parallel to `runs` prop — `runColors[i]` is the color for `runs[i]`), `RunColorSet` from `@/lib/runColors`
- The `card` and `groupBorder` fields provide the border color; component always adds `border-l-2` width separately. Similarly `headerTop` provides color; component always adds `border-t-2` width separately.

- [ ] **Step 1: Update `ExperimentComparisonTable.tsx`**

Replace the file with:

```typescript
import { Fragment, useState, useMemo } from 'react'
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
import type { RunColorSet } from '@/lib/runColors'

type FilterMode = 'all' | 'better' | 'worse' | 'same'

interface ExperimentComparisonTableProps {
  runs: RunMeta[]
  rows: ComparisonRow[]
  baselineRunId: string | null
  runColors: RunColorSet[]
}

export function ExperimentComparisonTable({
  runs,
  rows,
  baselineRunId,
  runColors,
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

  const colSpan = expanded ? runs.length * 3 + 1 : runs.length + 1

  return (
    <div className="space-y-3">
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

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="min-w-[200px] sticky left-0 bg-background z-10 border-r">
                Query
              </TableHead>
              {runs.map((run, i) => {
                const isBaseline = run.id === baselineRunId
                const color = runColors[i]
                if (expanded) {
                  return (
                    <Fragment key={run.id}>
                      <TableHead
                        className={`text-right text-xs whitespace-nowrap border-t-2 ${color.headerTop} border-l-2 ${color.groupBorder}`}
                      >
                        {run.name} P
                      </TableHead>
                      <TableHead
                        className={`text-right text-xs border-t-2 ${color.headerTop}`}
                      >
                        R
                      </TableHead>
                      <TableHead
                        className={`text-right text-xs cursor-pointer select-none border-t-2 ${color.headerTop}`}
                        onClick={() => handleSortClick(run.id)}
                      >
                        <span className="flex items-center justify-end">
                          F1
                          {!isBaseline && <SortIcon runId={run.id} />}
                        </span>
                      </TableHead>
                    </Fragment>
                  )
                }
                return (
                  <TableHead
                    key={run.id}
                    className={`text-right text-xs cursor-pointer select-none whitespace-nowrap border-t-2 ${color.headerTop}`}
                    onClick={() => handleSortClick(run.id)}
                  >
                    <span className="flex items-center justify-end">
                      <span className="truncate max-w-[120px]">{run.name}</span>
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
                <TableCell colSpan={colSpan} className="text-center text-muted-foreground py-8">
                  No queries match this filter.
                </TableCell>
              </TableRow>
            ) : (
              sortedRows.map((row) => (
                <TableRow key={row.queryId}>
                  <TableCell className="text-sm max-w-[300px] truncate sticky left-0 bg-background z-10 border-r">
                    {row.queryText}
                  </TableCell>
                  {runs.map((run, i) => {
                    const m = row.results[run.id]
                    const color = runColors[i]
                    if (expanded) {
                      return (
                        <Fragment key={run.id}>
                          <TableCell
                            className={`text-right font-mono text-sm ${color.cellBg} border-l-2 ${color.groupBorder}`}
                          >
                            {m ? formatPct(m.precision) : '—'}
                          </TableCell>
                          <TableCell
                            className={`text-right font-mono text-sm ${color.cellBg}`}
                          >
                            {m ? formatPct(m.recall) : '—'}
                          </TableCell>
                          <TableCell
                            className={`text-right font-mono text-sm ${color.cellBg}`}
                          >
                            {m ? (
                              <>
                                {formatPct(m.f1)}
                                <DeltaSpan delta={m.deltaF1} />
                              </>
                            ) : '—'}
                          </TableCell>
                        </Fragment>
                      )
                    }
                    return (
                      <TableCell
                        key={run.id}
                        className={`text-right font-mono text-sm ${color.cellBg}`}
                      >
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
        Showing {sortedRows.length} of {rows.length} {rows.length === 1 ? 'query' : 'queries'}
      </p>
    </div>
  )
}
```

- [ ] **Step 2: Check TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Run lint**

```bash
cd frontend && npm run lint
```

Expected: no errors.

- [ ] **Step 4: Run all frontend tests**

```bash
cd frontend && npx vitest run
```

Expected: all tests pass including the new `runColors.test.ts`.

- [ ] **Step 5: Build**

```bash
cd frontend && npm run build
```

Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/evaluation/ExperimentComparisonTable.tsx
git commit -m "feat(eval): add vertical run color emphasis to comparison table"
```

---

### Task 4: Visual verification checklist

Navigate to an experiment with 2+ completed runs → "Per-Query Analysis":

- [ ] Each `RunSummaryCard` has a visible colored left border; non-baseline runs use palette colors (indigo, emerald, amber…); baseline uses slate
- [ ] Each column header has a matching colored top border (2px)
- [ ] In collapsed (F1 only) mode: each run column has a faint background tint matching its card color
- [ ] Toggle "Expand P / R / F1": each run's three columns share the same tint; the first column of each run group has a colored left border matching the card
- [ ] The Query column stays fixed when scrolling right
- [ ] Filter buttons (All / Better / Worse / Same) still work
- [ ] Sorting by clicking a column header still works
- [ ] No React key warnings in browser console
