import { useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Plus,
  GitCompareArrows,
  Star,
  Pencil,
  Check,
  Loader2,
  FlaskConical,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { EvalStatusBadge } from '@/components/evaluation/EvalStatusBadge'
import { ScorePill } from '@/components/evaluation/ScorePill'
import { useProject } from '@/contexts/ProjectContext'
import { useExperimentDetail } from '@/hooks/useExperiments'
import type { EvalRun } from '@/types/eval-run'

export default function ExperimentDetailPage() {
  const { experimentId } = useParams<{ experimentId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const { experiment, isLoading, updateExperiment } = useExperimentDetail(
    projectId,
    experimentId ?? null
  )

  const [isEditingName, setIsEditingName] = useState(false)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [notesValue, setNotesValue] = useState<string | null>(null)

  const handleStartEdit = useCallback(() => {
    if (!experiment) return
    setEditName(experiment.name)
    setEditDescription(experiment.description || '')
    setIsEditingName(true)
  }, [experiment])

  const handleSaveName = async () => {
    if (!editName.trim()) return
    await updateExperiment({
      name: editName.trim(),
      description: editDescription.trim() || undefined,
    })
    setIsEditingName(false)
  }

  const handleNotesBlur = async () => {
    if (notesValue === null || !experiment) return
    if (notesValue !== (experiment.notes || '')) {
      await updateExperiment({ notes: notesValue })
    }
  }

  const handleSetBaseline = async (runId: string) => {
    await updateExperiment({ baselineRunId: runId })
  }

  const handleConclude = async () => {
    await updateExperiment({ status: 'concluded' })
  }

  const handleNewVariant = () => {
    if (!experiment) return
    const params = new URLSearchParams()
    params.set('experiment', experiment.id)
    if (experiment.baselineRunId) {
      params.set('clone', experiment.baselineRunId)
    }
    navigate(`/evaluation/runs/new?${params.toString()}`)
  }

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

  const formatMetric = (val: number | undefined | null) =>
    val != null ? (val * 100).toFixed(1) + '%' : '—'

  const formatDelta = (run: EvalRun, baselineF1: number | null) => {
    if (baselineF1 === null || !run.metrics?.avgF1) return null
    const delta = run.metrics.avgF1 - baselineF1
    if (Math.abs(delta) < 0.0001) return null
    const pct = (delta * 100).toFixed(1)
    return delta > 0 ? (
      <span className="text-emerald-600 text-xs ml-1">+{pct}</span>
    ) : (
      <span className="text-red-500 text-xs ml-1">{pct}</span>
    )
  }

  if (isLoading || !experiment) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const baselineF1 =
    experiment.baselineRun?.metrics?.avgF1 ?? null

  // Sort runs: baseline first, then by F1 desc
  const sortedRuns = [...experiment.runs].sort((a, b) => {
    if (a.id === experiment.baselineRunId) return -1
    if (b.id === experiment.baselineRunId) return 1
    const af1 = a.metrics?.avgF1 ?? -1
    const bf1 = b.metrics?.avgF1 ?? -1
    return bf1 - af1
  })

  const completedCount = experiment.runs.filter(
    (r) => r.status === 'completed' || r.status === 'partial_failure'
  ).length

  const currentNotes = notesValue ?? experiment.notes ?? ''

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate('/evaluation')}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          {isEditingName ? (
            <div className="space-y-2">
              <Input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="text-xl font-bold"
                autoFocus
              />
              <Input
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                placeholder="Description..."
                className="text-sm"
              />
              <div className="flex gap-2">
                <Button size="sm" onClick={handleSaveName}>
                  <Check className="mr-1 h-3 w-3" />
                  Save
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setIsEditingName(false)}
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold truncate">
                  {experiment.name}
                </h1>
                <Badge
                  variant={
                    experiment.status === 'active' ? 'blue' : 'secondary'
                  }
                >
                  {experiment.status}
                </Badge>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={handleStartEdit}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
              </div>
              {experiment.description && (
                <p className="text-muted-foreground mt-1">
                  {experiment.description}
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Actions bar */}
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={handleNewVariant}>
          <Plus className="mr-2 h-4 w-4" />
          New Variant
        </Button>
        {completedCount >= 2 && (
          <Button size="sm" variant="outline" onClick={handleCompare}>
            <GitCompareArrows className="mr-2 h-4 w-4" />
            Compare
          </Button>
        )}
        {experiment.status === 'active' && (
          <Button size="sm" variant="outline" onClick={handleConclude}>
            Conclude Experiment
          </Button>
        )}
      </div>

      {/* Leaderboard */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Leaderboard</CardTitle>
        </CardHeader>
        <CardContent>
          {sortedRuns.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <FlaskConical className="mx-auto h-6 w-6 mb-2 opacity-50" />
              <p className="text-sm">
                No runs yet. Click "New Variant" to create the first run.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>Name</TableHead>
                  <TableHead>Variant</TableHead>
                  <TableHead>Index</TableHead>
                  <TableHead className="text-right">P@k</TableHead>
                  <TableHead className="text-right">R@k</TableHead>
                  <TableHead className="text-right">F1</TableHead>
                  <TableHead className="text-right">Faith.</TableHead>
                  <TableHead className="text-right">Rel.</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-8" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedRuns.map((run) => {
                  const isBaseline = run.id === experiment.baselineRunId
                  return (
                    <TableRow
                      key={run.id}
                      className={`cursor-pointer ${isBaseline ? 'bg-primary/5' : ''}`}
                      onClick={() => navigate(`/evaluation/runs/${run.id}`)}
                    >
                      <TableCell>
                        {isBaseline && (
                          <Star className="h-4 w-4 text-amber-500 fill-amber-500" />
                        )}
                      </TableCell>
                      <TableCell>
                        <p className="font-medium">{run.name}</p>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {run.variantLabel || '—'}
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
                        {!isBaseline && formatDelta(run, baselineF1)}
                      </TableCell>
                      <TableCell className="text-right">
                        <ScorePill
                          score={run.metrics?.avgFaithfulness ?? null}
                        />
                      </TableCell>
                      <TableCell className="text-right">
                        <ScorePill
                          score={run.metrics?.avgRelevance ?? null}
                        />
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <EvalStatusBadge status={run.status} />
                          {(run.status === 'pending' ||
                            run.status === 'running') && (
                            <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                          )}
                        </div>
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        {!isBaseline &&
                          (run.status === 'completed' ||
                            run.status === 'partial_failure') && (
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-7 w-7">
                                  <span className="text-xs">...</span>
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem
                                  onClick={() => handleSetBaseline(run.id)}
                                >
                                  <Star className="mr-2 h-4 w-4" />
                                  Set as Baseline
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          )}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Variable Diff Panel */}
      {experiment.runs.length >= 2 && experiment.variableDiff && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">What Varies</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {Object.keys(experiment.variableDiff.varying).length > 0 ? (
              <div className="space-y-3">
                {Object.entries(experiment.variableDiff.varying).map(
                  ([field, values]) => (
                    <div key={field}>
                      <p className="text-sm font-medium mb-1">{field}</p>
                      <div className="flex flex-wrap gap-1">
                        {values.map((val, i) => (
                          <Badge key={i} variant="outline" className="text-xs">
                            {val}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                All runs have identical configuration.
              </p>
            )}

            {Object.keys(experiment.variableDiff.constant).length > 0 && (
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-2">
                  Held Constant
                </p>
                <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                  {Object.entries(experiment.variableDiff.constant).map(
                    ([field, value]) => (
                      <div key={field} className="flex justify-between">
                        <span className="text-muted-foreground">{field}</span>
                        <span className="font-mono">{value}</span>
                      </div>
                    )
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Notes */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Notes</CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            value={currentNotes}
            onChange={(e) => setNotesValue(e.target.value)}
            onBlur={handleNotesBlur}
            placeholder="Record conclusions, observations, next steps..."
            rows={4}
            className="text-sm"
          />
        </CardContent>
      </Card>
    </div>
  )
}
