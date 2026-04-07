import type { ExtractionEvalRunMetrics } from '@/types/extractionEval'
import { MetricCard } from '@/components/evaluation/MetricCard'

interface AggregateMetricsProps {
  metrics: ExtractionEvalRunMetrics
}

export function AggregateMetrics({ metrics }: AggregateMetricsProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <MetricCard
        label="Overall Score"
        value={`${(metrics.overallScoreMean * 100).toFixed(0)}%`}
        subtitle={`Median: ${(metrics.overallScoreMedian * 100).toFixed(0)}%`}
      />
      <MetricCard
        label="Field Match"
        value={`${Object.keys(metrics.fieldAccuracy).length} fields`}
        subtitle={`Across ${metrics.documentsEvaluated} documents`}
      />
      {metrics.lineItemsF1Mean !== null && (
        <MetricCard
          label="Line Items F1"
          value={`${(metrics.lineItemsF1Mean * 100).toFixed(0)}%`}
        />
      )}
      <MetricCard
        label="Documents"
        value={`${metrics.documentsEvaluated}`}
        subtitle={`${metrics.documentsPerfect} perfect`}
      />
    </div>
  )
}
