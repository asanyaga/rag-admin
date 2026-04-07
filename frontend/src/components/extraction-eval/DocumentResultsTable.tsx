import { useState } from 'react'
import type { ExtractionEvalResult } from '@/types/extractionEval'
import { ScorePill } from '@/components/evaluation/ScorePill'
import { FieldBreakdownView } from './FieldBreakdownView'
import { LineItemsBreakdownView } from './LineItemsBreakdownView'
import { Badge } from '@/components/ui/badge'
import { ChevronDown, ChevronRight } from 'lucide-react'

interface DocumentResultsTableProps {
  results: ExtractionEvalResult[]
}

export function DocumentResultsTable({ results }: DocumentResultsTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (results.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-muted-foreground">
        No results yet.
      </div>
    )
  }

  return (
    <div className="rounded-lg border">
      {/* Header */}
      <div className="grid grid-cols-[1fr_80px_80px_80px_60px] gap-2 px-4 py-2 border-b text-xs font-medium text-muted-foreground">
        <span>Document</span>
        <span>Score</span>
        <span>Fields</span>
        <span>Line F1</span>
        <span>Status</span>
      </div>

      {/* Rows */}
      {results.map((result) => {
        const isExpanded = expandedId === result.id
        const scalarScores = Object.entries(result.fieldScores).filter(([k]) => k !== 'line_items')
        const fieldCount = scalarScores.length
        const exactCount = scalarScores.filter(([, s]) => s.exact).length

        return (
          <div key={result.id}>
            <div
              className="grid grid-cols-[1fr_80px_80px_80px_60px] gap-2 px-4 py-3 items-center cursor-pointer hover:bg-muted/50 transition-colors"
              onClick={() => setExpandedId(isExpanded ? null : result.id)}
            >
              <div className="flex items-center gap-2 min-w-0">
                {isExpanded ? (
                  <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                )}
                <span className="text-sm truncate">
                  {result.documentTitle || 'Untitled'}
                </span>
              </div>
              <ScorePill score={result.overallScore} />
              <span className="text-xs text-muted-foreground">
                {exactCount}/{fieldCount}
              </span>
              <span className="text-xs">
                {result.lineItemsScore ? (
                  <ScorePill score={result.lineItemsScore.f1} />
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </span>
              <StatusIcon score={result.overallScore} />
            </div>

            {/* Expanded field breakdown */}
            {isExpanded && (
              <div className="border-t bg-muted/30 px-4 py-3">
                <FieldBreakdownView
                  fieldScores={result.fieldScores}
                  expectedData={result.expectedData ?? undefined}
                  predictedData={result.predictedData ?? undefined}
                />
                {result.lineItemsScore && (
                  <LineItemsBreakdownView
                    lineItemsScore={result.lineItemsScore}
                    expectedLineItems={
                      (result.expectedData?.line_items as Record<string, unknown>[] | undefined)
                    }
                    predictedLineItems={
                      (result.predictedData?.line_items as Record<string, unknown>[] | undefined)
                    }
                  />
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function StatusIcon({ score }: { score: number }) {
  if (score >= 0.9)
    return <Badge variant="success" className="text-xs px-1.5">ok</Badge>
  if (score >= 0.7)
    return <Badge variant="warning" className="text-xs px-1.5">warn</Badge>
  return <Badge variant="destructive" className="text-xs px-1.5">fail</Badge>
}
