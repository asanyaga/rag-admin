import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ComparisonSummary as ComparisonSummaryType } from '@/types/eval-run'

interface ComparisonSummaryProps {
  summary: ComparisonSummaryType
}

export function ComparisonSummary({ summary }: ComparisonSummaryProps) {
  const sign = (v: number) => (v > 0 ? '+' : '')

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Summary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p>
          Average F1 change:{' '}
          <span className="font-mono font-bold">
            {sign(summary.avgDeltaF1)}
            {(summary.avgDeltaF1 * 100).toFixed(1)}%
          </span>
        </p>
        <div className="flex gap-4">
          <span className="text-green-600">
            {summary.improvedQueries} improved
          </span>
          <span className="text-red-600">
            {summary.degradedQueries} degraded
          </span>
          <span className="text-muted-foreground">
            {summary.unchangedQueries} unchanged
          </span>
        </div>
        <p className="text-muted-foreground text-xs">
          Avg P change: {sign(summary.avgDeltaPrecision)}
          {(summary.avgDeltaPrecision * 100).toFixed(1)}% &middot;
          Avg R change: {sign(summary.avgDeltaRecall)}
          {(summary.avgDeltaRecall * 100).toFixed(1)}%
        </p>
      </CardContent>
    </Card>
  )
}
