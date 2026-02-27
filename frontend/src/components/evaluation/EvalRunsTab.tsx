import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, GitCompareArrows, Trash2, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { EvalStatusBadge } from './EvalStatusBadge'
import { ModeBadge } from './ModeBadge'
import { ScorePill } from './ScorePill'
import type { EvalRun, EvalMode } from '@/types/eval-run'

interface EvalRunsTabProps {
  runs: EvalRun[]
  isLoading: boolean
  onDelete: (id: string) => Promise<void>
}

export function EvalRunsTab({ runs, isLoading, onDelete }: EvalRunsTabProps) {
  const navigate = useNavigate()
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [modeFilter, setModeFilter] = useState<EvalMode | 'all'>('all')

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else if (next.size < 2) {
        next.add(id)
      }
      return next
    })
  }

  const handleCompare = () => {
    const ids = Array.from(selectedIds)
    if (ids.length === 2) {
      navigate(`/evaluation/compare?runs=${ids[0]},${ids[1]}`)
    }
  }

  const formatMetric = (val: number | undefined | null) =>
    val != null ? (val * 100).toFixed(1) + '%' : '—'

  const filteredRuns =
    modeFilter === 'all'
      ? runs
      : runs.filter((r) => r.mode === modeFilter)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {selectedIds.size === 2 && (
            <Button variant="outline" size="sm" onClick={handleCompare}>
              <GitCompareArrows className="mr-2 h-4 w-4" />
              Compare Selected
            </Button>
          )}
          <Select
            value={modeFilter}
            onValueChange={(v) => setModeFilter(v as EvalMode | 'all')}
          >
            <SelectTrigger className="w-[160px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Modes</SelectItem>
              <SelectItem value="retrieval_only">Retrieval Only</SelectItem>
              <SelectItem value="retrieval_and_answer">Ret + Answer</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button size="sm" onClick={() => navigate('/evaluation/runs/new')}>
          <Plus className="mr-2 h-4 w-4" />
          New Run
        </Button>
      </div>

      {filteredRuns.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <p>No evaluation runs yet.</p>
          <p className="text-sm mt-1">Create a run to measure retrieval quality.</p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10" />
              <TableHead>Name</TableHead>
              <TableHead>Experiment</TableHead>
              <TableHead>Mode</TableHead>
              <TableHead>Index</TableHead>
              <TableHead className="text-right">P@k</TableHead>
              <TableHead className="text-right">R@k</TableHead>
              <TableHead className="text-right">F1</TableHead>
              <TableHead className="text-right">Faith.</TableHead>
              <TableHead className="text-right">Rel.</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredRuns.map((run) => (
              <TableRow
                key={run.id}
                className="cursor-pointer"
                onClick={() => navigate(`/evaluation/runs/${run.id}`)}
              >
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Checkbox
                    checked={selectedIds.has(run.id)}
                    onCheckedChange={() => toggleSelect(run.id)}
                  />
                </TableCell>
                <TableCell>
                  <div>
                    <p className="font-medium">{run.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(run.createdAt).toLocaleDateString()}
                    </p>
                  </div>
                </TableCell>
                <TableCell className="text-sm" onClick={(e) => {
                  if (run.experimentId) {
                    e.stopPropagation()
                    navigate(`/evaluation/experiments/${run.experimentId}`)
                  }
                }}>
                  {run.experimentName ? (
                    <span className="text-primary hover:underline cursor-pointer">
                      {run.experimentName}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <ModeBadge mode={run.mode} />
                </TableCell>
                <TableCell className="text-sm">{run.indexName}</TableCell>
                <TableCell className="text-right font-mono text-sm">
                  {formatMetric(run.metrics?.avgPrecision)}
                </TableCell>
                <TableCell className="text-right font-mono text-sm">
                  {formatMetric(run.metrics?.avgRecall)}
                </TableCell>
                <TableCell className="text-right font-mono text-sm">
                  {formatMetric(run.metrics?.avgF1)}
                </TableCell>
                <TableCell className="text-right">
                  <ScorePill score={run.metrics?.avgFaithfulness ?? null} />
                </TableCell>
                <TableCell className="text-right">
                  <ScorePill score={run.metrics?.avgRelevance ?? null} />
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <EvalStatusBadge status={run.status} />
                    {(run.status === 'pending' || run.status === 'running') && (
                      <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                    )}
                  </div>
                </TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onDelete(run.id)}
                  >
                    <Trash2 className="h-4 w-4 text-muted-foreground" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
