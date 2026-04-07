import { useState } from 'react'
import type { LineItemsScore } from '@/types/extractionEval'
import { Badge } from '@/components/ui/badge'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { ScorePill } from '@/components/evaluation/ScorePill'

interface LineItemsBreakdownViewProps {
  lineItemsScore: LineItemsScore
  expectedLineItems?: Record<string, unknown>[]
  predictedLineItems?: Record<string, unknown>[]
}

interface RowData {
  status: 'match' | 'miss' | 'extra'
  expected?: Record<string, unknown>
  predicted?: Record<string, unknown>
  similarity?: number
  expectedIdx?: number
  predictedIdx?: number
}

export function LineItemsBreakdownView({
  lineItemsScore,
  expectedLineItems,
  predictedLineItems,
}: LineItemsBreakdownViewProps) {
  const [expanded, setExpanded] = useState(false)
  const matches = lineItemsScore.matches ?? []

  const matchedExpectedIndices = new Set(matches.map((m) => m.expectedIdx))
  const matchedPredictedIndices = new Set(matches.map((m) => m.predictedIdx))

  const rows: RowData[] = []

  // Matched pairs
  for (const match of matches) {
    rows.push({
      status: 'match',
      expected: expectedLineItems?.[match.expectedIdx],
      predicted: predictedLineItems?.[match.predictedIdx],
      similarity: 1 - match.cost,
      expectedIdx: match.expectedIdx,
      predictedIdx: match.predictedIdx,
    })
  }

  // Unmatched expected (misses)
  if (expectedLineItems) {
    for (let i = 0; i < expectedLineItems.length; i++) {
      if (!matchedExpectedIndices.has(i)) {
        rows.push({
          status: 'miss',
          expected: expectedLineItems[i],
          expectedIdx: i,
        })
      }
    }
  }

  // Extra predicted (false positives)
  if (predictedLineItems) {
    for (let i = 0; i < predictedLineItems.length; i++) {
      if (!matchedPredictedIndices.has(i)) {
        rows.push({
          status: 'extra',
          predicted: predictedLineItems[i],
          predictedIdx: i,
        })
      }
    }
  }

  return (
    <div className="mt-3 pt-3 border-t">
      <div
        className="flex items-center gap-4 text-xs text-muted-foreground cursor-pointer hover:text-foreground transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0" />
        )}
        <span>
          Line Items: {lineItemsScore.matched} matched of{' '}
          {lineItemsScore.expected} expected, {lineItemsScore.predicted}{' '}
          predicted
        </span>
        <ScorePill score={lineItemsScore.f1} />
      </div>

      {expanded && (
        <div className="mt-2 rounded border bg-background">
          {/* Header */}
          <div className="grid grid-cols-[60px_1fr_1fr_70px_60px] gap-2 px-3 py-2 text-xs font-medium text-muted-foreground border-b">
            <span>Status</span>
            <span>Expected</span>
            <span>Predicted</span>
            <span>Score</span>
            <span>#</span>
          </div>

          {rows.length === 0 ? (
            <div className="px-3 py-4 text-xs text-muted-foreground text-center">
              No line items to display.
            </div>
          ) : (
            rows.map((row, i) => (
              <div
                key={i}
                className="grid grid-cols-[60px_1fr_1fr_70px_60px] gap-2 px-3 py-2 items-start border-b last:border-b-0 text-xs"
              >
                <StatusBadge status={row.status} />
                <div className="min-w-0">
                  {row.expected ? (
                    <FieldValues data={row.expected} />
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </div>
                <div className="min-w-0">
                  {row.predicted ? (
                    <FieldValues data={row.predicted} />
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </div>
                <div>
                  {row.similarity !== undefined ? (
                    <ScorePill score={row.similarity} />
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </div>
                <span className="text-muted-foreground">
                  {row.status === 'match'
                    ? `E${row.expectedIdx!}→P${row.predictedIdx!}`
                    : row.status === 'miss'
                      ? `E${row.expectedIdx!}`
                      : `P${row.predictedIdx!}`}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: 'match' | 'miss' | 'extra' }) {
  const config = {
    match: { variant: 'success' as const, label: 'match' },
    miss: { variant: 'destructive' as const, label: 'miss' },
    extra: { variant: 'warning' as const, label: 'extra' },
  }
  const { variant, label } = config[status]
  return (
    <Badge variant={variant} className="text-xs px-1.5 justify-center w-fit">
      {label}
    </Badge>
  )
}

function FieldValues({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(
    ([, v]) => v !== null && v !== undefined
  )
  if (entries.length === 0) return <span className="text-muted-foreground">—</span>

  return (
    <div className="flex flex-wrap gap-x-3 gap-y-0.5">
      {entries.map(([key, value]) => (
        <span key={key}>
          <span className="text-muted-foreground capitalize">
            {key.replace(/_/g, ' ')}:
          </span>{' '}
          <span className="font-medium">{formatValue(value)}</span>
        </span>
      ))}
    </div>
  )
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return value.toLocaleString()
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
