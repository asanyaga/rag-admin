import type { ExtractionResult, ExtractionResultListItem } from '@/types/extraction'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Button } from '@/components/ui/button'
import { ChevronRight, Loader2 } from 'lucide-react'
import { ExtractionResultViewer } from './ExtractionResultViewer'

interface ExtractionHistoryProps {
  results: ExtractionResultListItem[]
  isLoading: boolean
  selectedResult: ExtractionResult | null
  isLoadingResult?: boolean
  onSelectResult: (resultId: string) => void
}

export function ExtractionHistory({
  results,
  isLoading,
  selectedResult,
  onSelectResult,
}: ExtractionHistoryProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    )
  }

  if (results.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-6">
        No extractions yet. Run one above to get started.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {results.map((r) => {
        const isExpanded = selectedResult?.id === r.id
        const isPending = r.status === 'pending'

        return (
          <Collapsible
            key={r.id}
            open={isExpanded}
            onOpenChange={(open) => {
              if (open) onSelectResult(r.id)
            }}
          >
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className="w-full justify-between h-auto py-2.5 px-3 hover:bg-muted/50"
              >
                <div className="flex items-center gap-2 text-left">
                  <ChevronRight
                    className={`h-4 w-4 shrink-0 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                  />
                  <Badge variant="outline" className="text-[10px] font-normal">
                    {r.extractionMethod}
                  </Badge>
                  <Badge
                    variant={
                      r.status === 'completed'
                        ? 'default'
                        : r.status === 'pending'
                          ? 'secondary'
                          : 'destructive'
                    }
                    className="text-[10px]"
                  >
                    {isPending && <Loader2 className="h-2.5 w-2.5 mr-1 animate-spin" />}
                    {r.status}
                  </Badge>
                </div>
                <span className="text-xs text-muted-foreground">
                  {formatDate(r.createdAt)}
                </span>
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
