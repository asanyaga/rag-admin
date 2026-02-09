import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { EvalRun } from '@/types/eval-run'

interface RunSummaryCardProps {
  run: EvalRun
  label: 'Baseline' | 'Challenger'
}

export function RunSummaryCard({ run, label }: RunSummaryCardProps) {
  const formatMetric = (val: number | undefined | null) =>
    val != null ? (val * 100).toFixed(1) + '%' : '—'

  return (
    <Card>
      <CardContent className="pt-6">
        <Badge variant={label === 'Baseline' ? 'secondary' : 'blue'} className="mb-2">
          {label}
        </Badge>
        <h3 className="font-medium">{run.name}</h3>
        <p className="text-xs text-muted-foreground mt-1">
          {run.indexName} &middot; {run.config.searchType} &middot; k={run.config.topK}
        </p>
        <div className="grid grid-cols-3 gap-4 mt-4">
          <div>
            <p className="text-xs text-muted-foreground">Precision</p>
            <p className="text-lg font-mono font-bold">
              {formatMetric(run.metrics?.avgPrecision)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Recall</p>
            <p className="text-lg font-mono font-bold">
              {formatMetric(run.metrics?.avgRecall)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">F1</p>
            <p className="text-lg font-mono font-bold">
              {formatMetric(run.metrics?.avgF1)}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
