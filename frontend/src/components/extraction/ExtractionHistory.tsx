import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { ExtractionResultListItem, ExtractionSchema } from '@/types/extraction'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Download, Loader2, Trash2 } from 'lucide-react'

interface ExtractionHistoryProps {
  results: ExtractionResultListItem[]
  isLoading: boolean
  schemas?: ExtractionSchema[]
  onDeleteResult: (resultId: string) => Promise<void>
  onExportResult: (resultId: string) => Promise<void>
}

export function ExtractionHistory({
  results,
  isLoading,
  schemas,
  onDeleteResult,
  onExportResult,
}: ExtractionHistoryProps) {
  const [exportingId, setExportingId] = useState<string | null>(null)

  const handleExport = async (e: React.MouseEvent, resultId: string) => {
    e.preventDefault()
    e.stopPropagation()
    setExportingId(resultId)
    try {
      await onExportResult(resultId)
    } finally {
      setExportingId(null)
    }
  }

  const handleDelete = (e: React.MouseEvent, resultId: string) => {
    e.preventDefault()
    e.stopPropagation()
    void onDeleteResult(resultId)
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    )
  }

  if (results.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-6">
        No extractions yet. Run one to get started.
      </p>
    )
  }

  return (
    <div className="space-y-1">
      {results.map((r) => {
        const schemaName = schemas?.find((s) => s.id === r.extractionSchemaId)?.name
        const isPending = r.status === 'pending'
        return (
          <div key={r.id} className="flex items-center rounded-md hover:bg-muted/50 group">
            <Link to={`/extract/${r.id}`} className="flex-1 min-w-0 py-2.5 pl-3 pr-2">
              <div className="flex items-center gap-1.5 min-w-0">
                {schemaName && (
                  <span className="text-xs font-medium truncate">{schemaName}</span>
                )}
                <Badge variant="outline" className="text-[10px] font-normal shrink-0">
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
                  className="text-[10px] shrink-0"
                >
                  {isPending && <Loader2 className="h-2.5 w-2.5 mr-1 animate-spin" />}
                  {r.status}
                </Badge>
                <span className="text-[11px] text-muted-foreground ml-auto shrink-0">
                  {formatDate(r.createdAt)}
                </span>
              </div>
            </Link>
            {!isPending && (
              <>
                <button
                  aria-label="Export as CSV"
                  className="shrink-0 px-2 py-2 text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 transition-opacity disabled:cursor-not-allowed"
                  disabled={exportingId === r.id}
                  onClick={(e) => void handleExport(e, r.id)}
                >
                  <Download className="h-3.5 w-3.5" />
                </button>
                <button
                  aria-label="Delete extraction run"
                  className="shrink-0 px-2 py-2 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => handleDelete(e, r.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </>
            )}
          </div>
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
