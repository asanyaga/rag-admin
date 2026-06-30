import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ExternalLink, Trash2 } from 'lucide-react'
import type { ParseRunListItem } from '@/types/cdm'
import { ParseRunDeleteDialog } from './ParseRunDeleteDialog'

interface RunTimelineProps {
  documentId: string
  runs: ParseRunListItem[]
  onRunDeleted?: () => void
}

function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function relTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const s = Math.round(diffMs / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  return `${Math.round(s / 86400)}d ago`
}

export function RunTimeline({ documentId, runs, onRunDeleted }: RunTimelineProps) {
  const [deletingRunId, setDeletingRunId] = useState<string | null>(null)

  if (runs.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-2">
        No parse runs yet.
      </div>
    )
  }

  return (
    <>
      <ul className="divide-y rounded-md border">
        {runs.map((r) => (
          <li key={r.id} className="flex items-center gap-3 px-3 py-2 text-sm">
            <Badge
              variant={
                r.status === 'failed'
                  ? 'destructive'
                  : r.status === 'succeeded'
                    ? 'default'
                    : 'secondary'
              }
            >
              {r.status}
            </Badge>
            <span className="font-medium">{r.parser}</span>
            <span className="text-xs text-muted-foreground">
              {r.representationKind}
            </span>
            <span className="text-xs text-muted-foreground">
              {relTime(r.startedAt)}
            </span>
            <span className="text-xs text-muted-foreground">
              {formatDuration(r.durationMs)}
            </span>
            {r.error && (
              <span className="text-xs text-destructive truncate max-w-[20ch]">
                {r.error}
              </span>
            )}
            <div className="ml-auto flex items-center gap-1">
              <Button asChild size="sm" variant="ghost">
                <Link to={`/parse/${documentId}/runs/${r.id}`}>
                  <ExternalLink className="h-3 w-3 mr-1" /> Open viewer
                </Link>
              </Button>
              <Button
                size="sm"
                variant="ghost"
                aria-label="Delete"
                onClick={() => setDeletingRunId(r.id)}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          </li>
        ))}
      </ul>

      {deletingRunId && (
        <ParseRunDeleteDialog
          open={true}
          onOpenChange={(open) => {
            if (!open) setDeletingRunId(null)
          }}
          runId={deletingRunId}
          onDeleted={() => {
            setDeletingRunId(null)
            onRunDeleted?.()
          }}
        />
      )}
    </>
  )
}
