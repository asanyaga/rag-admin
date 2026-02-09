import { FileText } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { ExpectedSource, RetrievedChunk } from '@/types/eval-run'

interface ExpectedSourcesListProps {
  sources: ExpectedSource[]
  retrievedChunks: RetrievedChunk[]
}

export function ExpectedSourcesList({
  sources,
  retrievedChunks,
}: ExpectedSourcesListProps) {
  if (sources.length === 0) {
    return <p className="text-sm text-muted-foreground">No expected sources.</p>
  }

  // Build a set of (documentId, page) that were actually retrieved
  const retrievedSet = new Set(
    retrievedChunks.map((c) => `${c.documentId}:${c.page}`)
  )

  return (
    <div className="space-y-2">
      {sources.map((source, idx) => {
        const pages = source.locator?.pages ?? []
        return (
          <div
            key={idx}
            className="flex items-center gap-2 p-2 rounded-md border bg-muted/20"
          >
            <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="text-sm truncate">{source.documentName}</span>
            <div className="flex gap-1 flex-wrap">
              {pages.map((page) => {
                const found = retrievedSet.has(`${source.documentId}:${page}`)
                return (
                  <Badge
                    key={page}
                    variant={found ? 'success' : 'destructive'}
                    className="text-xs"
                  >
                    p.{page} {found ? 'hit' : 'miss'}
                  </Badge>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
