import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { RetrievedChunksList } from './RetrievedChunksList'
import { ExpectedSourcesList } from './ExpectedSourcesList'
import type { EvalRunResult } from '@/types/eval-run'

interface RunResultsListProps {
  results: EvalRunResult[]
}

function metricColor(val: number): string {
  if (val >= 0.8) return 'text-green-600'
  if (val >= 0.5) return 'text-amber-600'
  return 'text-red-600'
}

export function RunResultsList({ results }: RunResultsListProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  const toggle = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  if (results.length === 0) {
    return (
      <p className="text-muted-foreground text-center py-8">
        No results available.
      </p>
    )
  }

  return (
    <div className="space-y-1">
      {results.map((r) => {
        const expanded = expandedIds.has(r.id)
        return (
          <div key={r.id} className="border rounded-lg">
            <button
              className="w-full flex items-center gap-4 p-3 text-left hover:bg-accent/50 transition-colors"
              onClick={() => toggle(r.id)}
            >
              {expanded ? (
                <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
              )}
              <span className="flex-1 text-sm truncate">{r.queryText}</span>
              <span className={cn('text-xs font-mono w-14 text-right', metricColor(r.precision))}>
                P {(r.precision * 100).toFixed(0)}%
              </span>
              <span className={cn('text-xs font-mono w-14 text-right', metricColor(r.recall))}>
                R {(r.recall * 100).toFixed(0)}%
              </span>
              <span className={cn('text-xs font-mono w-14 text-right font-bold', metricColor(r.f1))}>
                F1 {(r.f1 * 100).toFixed(0)}%
              </span>
            </button>
            {expanded && (
              <div className="px-3 pb-3 grid grid-cols-2 gap-4">
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-2">
                    Retrieved Chunks
                  </h4>
                  <RetrievedChunksList chunks={r.retrievedChunks} />
                </div>
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-2">
                    Expected Sources
                  </h4>
                  <ExpectedSourcesList
                    sources={r.expectedSources}
                    retrievedChunks={r.retrievedChunks}
                  />
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
