import { useSearchParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useProject } from '@/contexts/ProjectContext'
import { useRunComparison } from '@/hooks/useEvalRuns'
import { RunSummaryCard } from '@/components/evaluation/RunSummaryCard'
import { ComparisonTable } from '@/components/evaluation/ComparisonTable'
import { ComparisonSummary } from '@/components/evaluation/ComparisonSummary'

export default function RunComparisonPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const runsParam = searchParams.get('runs') ?? ''
  const [runId1, runId2] = runsParam.split(',')

  const { comparison, isLoading, error } = useRunComparison(
    projectId,
    runId1 || null,
    runId2 || null
  )

  if (!runId1 || !runId2) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        Two run IDs are required for comparison.
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-12 text-destructive">{error}</div>
    )
  }

  if (!comparison) return null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate('/evaluation/retrieval')}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-2xl font-bold">Run Comparison</h1>
      </div>

      {/* Run summaries */}
      <div className="grid grid-cols-2 gap-6">
        <RunSummaryCard run={comparison.baselineRun} label="Baseline" />
        <RunSummaryCard run={comparison.challengerRun} label="Challenger" />
      </div>

      {/* Summary */}
      <ComparisonSummary summary={comparison.summary} />

      {/* Per-query comparison */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Per-Query Comparison</h2>
        <ComparisonTable items={comparison.perQueryComparison} />
      </div>
    </div>
  )
}
