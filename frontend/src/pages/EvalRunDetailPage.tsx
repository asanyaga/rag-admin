import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { useProject } from '@/contexts/ProjectContext'
import { useEvalRunDetail } from '@/hooks/useEvalRuns'
import { EvalStatusBadge } from '@/components/evaluation/EvalStatusBadge'
import { ModeBadge } from '@/components/evaluation/ModeBadge'
import { MetricCard } from '@/components/evaluation/MetricCard'
import { RunResultsList } from '@/components/evaluation/RunResultsList'

export default function EvalRunDetailPage() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const { run, results, progress, isLoading, fetchResults } = useEvalRunDetail(
    projectId,
    runId ?? null
  )

  const [activeFilter, setActiveFilter] = useState<string>('all')

  const handleFilterChange = async (filter: string) => {
    setActiveFilter(filter)
    await fetchResults(filter)
  }

  if (isLoading || !run) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const formatMetric = (val: number | undefined | null) =>
    val != null ? (val * 100).toFixed(1) + '%' : '—'

  const isAnswerMode = run.mode === 'retrieval_and_answer'
  const isRunning = run.status === 'pending' || run.status === 'running'
  const isDone =
    run.status === 'completed' || run.status === 'partial_failure'

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
            <ModeBadge mode={run.mode} />
          </div>
          <p className="text-sm text-muted-foreground">
            {run.indexName} &middot; {run.config.searchType} &middot; k=
            {run.config.topK} &middot; {run.goldenSetName}
            {run.generationModel && (
              <>
                {' '}&middot; Gen: {run.generationModel.modelId}
              </>
            )}
          </p>
        </div>
      </div>

      {/* Progress indicator */}
      {isRunning && progress && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              Processing queries: {progress.itemsCompleted} / {progress.itemsTotal}
            </span>
            {progress.failedItemCount > 0 && (
              <span className="text-amber-600">
                {progress.failedItemCount} failed
              </span>
            )}
          </div>
          <Progress
            value={
              progress.itemsTotal > 0
                ? (progress.itemsCompleted / progress.itemsTotal) * 100
                : 0
            }
          />
        </div>
      )}

      {/* Metrics */}
      {run.metrics && (
        <div className={`grid gap-4 ${isAnswerMode ? 'grid-cols-6' : 'grid-cols-4'}`}>
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
            label="Below Threshold"
            value={run.metrics.queriesBelowThreshold}
            subtitle="F1 < 50%"
          />
          {isAnswerMode && (
            <>
              <MetricCard
                label="Avg Faithfulness"
                value={formatMetric(run.metrics.avgFaithfulness)}
                className="border-purple-200 dark:border-purple-800"
              />
              <MetricCard
                label="Avg Relevance"
                value={formatMetric(run.metrics.avgRelevance)}
                className="border-purple-200 dark:border-purple-800"
              />
            </>
          )}
        </div>
      )}

      {/* Error message */}
      {run.status === 'failed' && run.errorMessage && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {run.errorMessage}
        </div>
      )}

      {/* Partial failure warning */}
      {run.status === 'partial_failure' && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-400">
          Some items failed during evaluation. {run.failedItemCount} item(s)
          encountered errors. Results are still available for completed items.
        </div>
      )}

      {/* Pending/running state */}
      {isRunning && !progress && (
        <div className="flex items-center gap-3 py-8 justify-center text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span>Evaluation is {run.status}...</span>
        </div>
      )}

      {/* Per-query results */}
      {isDone && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">Per-Query Results</h2>
            {isAnswerMode && (
              <select
                value={activeFilter}
                onChange={(e) => handleFilterChange(e.target.value)}
                className="text-xs border rounded px-2 py-1 bg-background"
              >
                <option value="all">All</option>
                <option value="low_faithfulness">Low Faithfulness</option>
                <option value="low_relevance">Low Relevance</option>
                <option value="retrieval_miss">Retrieval Miss</option>
              </select>
            )}
          </div>
          <RunResultsList results={results} isAnswerMode={isAnswerMode} runId={runId!} />
        </div>
      )}
    </div>
  )
}
