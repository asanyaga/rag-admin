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
