import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useProject } from '@/contexts/ProjectContext'
import { useEvalRunDetail } from '@/hooks/useEvalRuns'
import { EvalStatusBadge } from '@/components/evaluation/EvalStatusBadge'
import { MetricCard } from '@/components/evaluation/MetricCard'
import { RunResultsList } from '@/components/evaluation/RunResultsList'

export default function EvalRunDetailPage() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const { run, results, isLoading } = useEvalRunDetail(projectId, runId ?? null)

  if (isLoading || !run) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const formatMetric = (val: number | undefined | null) =>
    val != null ? (val * 100).toFixed(1) + '%' : '—'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate('/evaluation')}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{run.name}</h1>
            <EvalStatusBadge status={run.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            {run.indexName} &middot; {run.config.searchType} &middot; k=
            {run.config.topK} &middot; {run.goldenSetName}
          </p>
        </div>
      </div>

      {/* Metrics */}
      {run.metrics && (
        <div className="grid grid-cols-4 gap-4">
          <MetricCard
            label="Avg Precision@k"
            value={formatMetric(run.metrics.avgPrecision)}
          />
          <MetricCard
            label="Avg Recall@k"
            value={formatMetric(run.metrics.avgRecall)}
          />
          <MetricCard
            label="Avg F1"
            value={formatMetric(run.metrics.avgF1)}
          />
          <MetricCard
            label="Queries Below Threshold"
            value={run.metrics.queriesBelowThreshold}
            subtitle="F1 < 50%"
          />
        </div>
      )}

      {/* Error message */}
      {run.status === 'failed' && run.errorMessage && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {run.errorMessage}
        </div>
      )}

      {/* Pending/running state */}
      {(run.status === 'pending' || run.status === 'running') && (
        <div className="flex items-center gap-3 py-8 justify-center text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span>Evaluation is {run.status}...</span>
        </div>
      )}

      {/* Per-query results */}
      {run.status === 'completed' && (
        <div>
          <h2 className="text-lg font-semibold mb-3">Per-Query Results</h2>
          <RunResultsList results={results} />
        </div>
      )}
    </div>
  )
}
