import type { ExtractionResult, ExtractionResultListItem, ExtractionSchema } from '@/types/extraction'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { AlertCircle, ChevronRight, Loader2, RefreshCw } from 'lucide-react'
import { ExtractionResultViewer } from './ExtractionResultViewer'

interface InProgressPhase {
  phase: 'parsing' | 'extracting' | 'failed'
  phaseError?: string | null
  onRetry?: () => void
}

interface ExtractionHistoryProps {
  results: ExtractionResultListItem[]
  isLoading: boolean
  selectedResult: ExtractionResult | null
  isLoadingResult?: boolean
  schemas?: ExtractionSchema[]
  onSelectResult: (resultId: string) => void
  inProgressPhase?: InProgressPhase
}

export function ExtractionHistory({
  results,
  isLoading,
  selectedResult,
  schemas,
  onSelectResult,
  inProgressPhase,
}: ExtractionHistoryProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    )
  }

  // Show synthetic row when actively parsing/extracting and no real pending result exists yet
  const hasPendingResult = results.some((r) => r.status === 'pending')
  const showSyntheticRow =
    inProgressPhase &&
    (inProgressPhase.phase === 'parsing' ||
      inProgressPhase.phase === 'extracting' ||
      inProgressPhase.phase === 'failed') &&
    !hasPendingResult

  const isEmpty = results.length === 0 && !showSyntheticRow

  if (isEmpty) {
    return (
      <p className="text-sm text-muted-foreground text-center py-6">
        No extractions yet. Run one above to get started.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {showSyntheticRow && inProgressPhase && (
        <div className="rounded-md border px-3 py-2.5">
          {inProgressPhase.phase === 'failed' ? (
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span className="text-sm">{inProgressPhase.phaseError ?? 'Failed'}</span>
              </div>
              {inProgressPhase.onRetry && (
                <Button variant="outline" size="sm" className="h-7 text-xs gap-1.5" onClick={inProgressPhase.onRetry}>
                  <RefreshCw className="h-3 w-3" />
                  Retry
                </Button>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
              <span className="text-sm">
                {inProgressPhase.phase === 'parsing' ? 'Parsing document…' : 'Extracting…'}
              </span>
            </div>
          )}
        </div>
      )}

      {results.map((r) => {
        const isExpanded = selectedResult?.id === r.id
        const isPending = r.status === 'pending'
        const schemaName = schemas?.find((s) => s.id === r.extractionSchemaId)?.name

        return (
          <Collapsible
            key={r.id}
            open={isExpanded}
            onOpenChange={(open) => { if (open) onSelectResult(r.id) }}
          >
            <CollapsibleTrigger asChild>
              <Button variant="ghost" className="w-full justify-between h-auto py-2.5 px-3 hover:bg-muted/50">
                <div className="flex items-center gap-2 text-left min-w-0">
                  <ChevronRight className={`h-4 w-4 shrink-0 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                  <div className="flex flex-col items-start gap-0.5 min-w-0">
                    <div className="flex items-center gap-1.5">
                      {schemaName && (
                        <span className="text-xs font-medium truncate">{schemaName}</span>
                      )}
                      <Badge variant="outline" className="text-[10px] font-normal shrink-0">{r.extractionMethod}</Badge>
                      <Badge
                        variant={r.status === 'completed' ? 'default' : r.status === 'pending' ? 'secondary' : 'destructive'}
                        className="text-[10px] shrink-0"
                      >
                        {isPending && <Loader2 className="h-2.5 w-2.5 mr-1 animate-spin" />}
                        {r.status}
                      </Badge>
                    </div>
                    <span className="text-[11px] text-muted-foreground">{formatDate(r.createdAt)}</span>
                  </div>
                </div>
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="ml-6 mr-3 mb-2 mt-1">
                {selectedResult?.id === r.id ? (
                  <ExtractionResultViewer result={selectedResult} isLoading={false} />
                ) : isExpanded ? (
                  <div className="space-y-2 p-3">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-4 w-1/2" />
                  </div>
                ) : null}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )
      })}
    </div>
  )
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
