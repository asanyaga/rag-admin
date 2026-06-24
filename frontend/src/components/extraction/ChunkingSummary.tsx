import { Badge } from '@/components/ui/badge'

interface ScalarConflict {
  path: string
  kept: unknown
  discarded: unknown
}

interface ChunkingSummaryProps {
  metadata: Record<string, unknown> | null | undefined
}

export function ChunkingSummary({ metadata }: ChunkingSummaryProps) {
  if (!metadata) return null

  const chunkCount = typeof metadata.chunkCount === 'number' ? metadata.chunkCount : undefined
  const usage = metadata.usage as { total_tokens?: number } | undefined
  const totalTokens =
    usage && typeof usage.total_tokens === 'number' ? usage.total_tokens : undefined
  const conflicts: ScalarConflict[] = Array.isArray(metadata.scalarConflicts)
    ? (metadata.scalarConflicts as ScalarConflict[])
    : []

  if (chunkCount === undefined && totalTokens === undefined && conflicts.length === 0) {
    return null
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {chunkCount !== undefined && (
          <Badge variant="secondary">
            {chunkCount} chunk{chunkCount === 1 ? '' : 's'}
          </Badge>
        )}
        {totalTokens !== undefined && (
          <Badge variant="outline">{totalTokens.toLocaleString()} tokens</Badge>
        )}
      </div>
      {conflicts.length > 0 && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800">
          <p className="font-medium">Conflicting values across chunks ({conflicts.length})</p>
          <ul className="mt-1 space-y-0.5">
            {conflicts.map((c, i) => (
              <li key={i}>
                <code>{c.path}</code>: kept {String(c.kept)} ≠ {String(c.discarded)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
