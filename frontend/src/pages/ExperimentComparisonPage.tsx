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
