import type { FieldScore } from '@/types/extractionEval'
import { ScorePill } from '@/components/evaluation/ScorePill'
import { Badge } from '@/components/ui/badge'

interface FieldBreakdownViewProps {
  fieldScores: Record<string, FieldScore>
  expectedData?: Record<string, unknown>
  predictedData?: Record<string, unknown>
}

export function FieldBreakdownView({
  fieldScores,
  expectedData,
  predictedData,
}: FieldBreakdownViewProps) {
  return (
    <div className="divide-y text-sm">
      <div className="grid grid-cols-[1fr_1fr_1fr_80px_60px] gap-2 px-3 py-2 text-xs font-medium text-muted-foreground">
        <span>Field</span>
        <span>Expected</span>
        <span>Got</span>
        <span>Score</span>
        <span>Match</span>
      </div>
      {Object.entries(fieldScores).filter(([field]) => field !== 'line_items').map(([field, score]) => (
        <div
          key={field}
          className="grid grid-cols-[1fr_1fr_1fr_80px_60px] gap-2 px-3 py-2 items-center"
        >
          <span className="font-medium capitalize truncate">
            {field.replace(/_/g, ' ')}
          </span>
          <span className="text-muted-foreground truncate text-xs">
            {expectedData ? formatValue(expectedData[field]) : '—'}
          </span>
          <span className="truncate text-xs">
            {predictedData ? formatValue(predictedData[field]) : '—'}
          </span>
          <ScorePill score={score.score} />
          <Badge
            variant={score.exact ? 'success' : 'destructive'}
            className="text-xs justify-center"
          >
            {score.exact ? 'exact' : 'miss'}
          </Badge>
        </div>
      ))}
    </div>
  )
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
