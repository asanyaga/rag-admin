import { CheckCircle2, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { RetrievedChunk } from '@/types/eval-run'

interface RetrievedChunksListProps {
  chunks: RetrievedChunk[]
  selectedChunkId?: string | null
  onChunkClick?: (chunk: RetrievedChunk) => void
}

export function RetrievedChunksList({
  chunks,
  selectedChunkId,
  onChunkClick,
}: RetrievedChunksListProps) {
  if (chunks.length === 0) {
    return <p className="text-sm text-muted-foreground">No chunks retrieved.</p>
  }

  const isClickable = !!onChunkClick

  return (
    <div className="space-y-2">
      {chunks.map((chunk) => (
        <div
          key={chunk.chunkId}
          className={cn(
            'flex items-start gap-3 p-2 rounded-md border bg-muted/20',
            isClickable && 'cursor-pointer hover:bg-muted/40 transition-colors',
            selectedChunkId === chunk.chunkId && 'ring-2 ring-primary/50 bg-primary/5'
          )}
          onClick={() => onChunkClick?.(chunk)}
        >
          <Badge variant="outline" className="shrink-0 font-mono text-xs">
            #{chunk.rank}
          </Badge>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-medium truncate">
                {chunk.documentName}
              </span>
              {chunk.page != null && (
                <Badge variant="secondary" className="text-xs">
                  p.{chunk.page}
                </Badge>
              )}
              <span className="text-xs text-muted-foreground font-mono">
                {(chunk.score * 100).toFixed(1)}%
              </span>
            </div>
            <p className="text-xs text-muted-foreground line-clamp-2">
              {chunk.content}
            </p>
          </div>
          <div className="shrink-0">
            {chunk.isRelevant ? (
              <CheckCircle2 className="h-4 w-4 text-green-600" />
            ) : (
              <XCircle className="h-4 w-4 text-red-400" />
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
