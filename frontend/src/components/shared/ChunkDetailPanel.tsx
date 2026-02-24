/**
 * Shared chunk detail panel that fetches and displays full chunk info.
 * Used inside a Sheet/sidebar to show chunk content, stats, and metadata.
 */
import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { getChunk } from '@/api/indexes'
import type { Chunk } from '@/types/index'

interface ChunkDetailPanelProps {
  projectId: string
  indexId: string
  chunkId: string
  /** Extra info to display above the chunk details (e.g. relevance, score) */
  header?: React.ReactNode
}

export function ChunkDetailPanel({
  projectId,
  indexId,
  chunkId,
  header,
}: ChunkDetailPanelProps) {
  const [chunk, setChunk] = useState<Chunk | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setError(null)

    getChunk(projectId, indexId, chunkId)
      .then((data) => {
        if (!cancelled) setChunk(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err?.message ?? 'Failed to load chunk')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [projectId, indexId, chunkId])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error || !chunk) {
    return (
      <p className="text-sm text-muted-foreground py-4">
        {error ?? 'Chunk not found.'}
      </p>
    )
  }

  return (
    <div className="space-y-4">
      {header}

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">
            Tokens
          </div>
          <div className="text-sm font-mono text-foreground">
            {chunk.tokenCount}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">
            Chars
          </div>
          <div className="text-sm font-mono text-foreground">
            {chunk.charCount}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">
            Chunk Index
          </div>
          <div className="text-sm font-mono text-foreground">
            #{chunk.chunkIndex}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">
            Source
          </div>
          <div className="text-sm text-foreground truncate">
            {chunk.documentTitle || chunk.documentFilename || 'Unknown'}
          </div>
        </div>
      </div>

      {/* Metadata */}
      {chunk.metadata && Object.keys(chunk.metadata).length > 0 && (
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">
            Metadata
          </div>
          <div className="bg-muted/50 rounded-md border divide-y divide-border">
            {Object.entries(chunk.metadata).map(([key, value]) => (
              <div key={key} className="px-3 py-2 flex items-start gap-2">
                <span className="text-xs font-medium text-muted-foreground shrink-0">
                  {key}
                </span>
                <span className="text-xs text-foreground font-mono break-all ml-auto text-right">
                  {Array.isArray(value)
                    ? value.join(', ')
                    : typeof value === 'object' && value !== null
                      ? JSON.stringify(value)
                      : String(value ?? '—')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Content */}
      <div>
        <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">
          Content
        </div>
        <div className="bg-muted/50 rounded-md p-3 text-sm leading-relaxed border max-h-[60vh] overflow-auto whitespace-pre-wrap break-words">
          {chunk.content}
        </div>
      </div>

      {/* Created timestamp */}
      {chunk.createdAt && (
        <div className="text-[10px] text-muted-foreground pt-2 border-t">
          Created {new Date(chunk.createdAt).toLocaleString()}
        </div>
      )}
    </div>
  )
}
