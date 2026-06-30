import { useEffect } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ClassificationRunStatusBadge } from './ClassificationRunStatusBadge'
import { useDocumentClassificationRuns } from '@/hooks/useClassificationRuns'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

interface ClassificationRunHistoryProps {
  documentId: string
  selectedRunId: string | null
  onSelectRun: (runId: string) => void
  onNewRun: () => void
}

export function ClassificationRunHistory({
  documentId,
  selectedRunId,
  onSelectRun,
  onNewRun,
}: ClassificationRunHistoryProps) {
  const { runs, isLoading, error, deleteRun } = useDocumentClassificationRuns(documentId)

  // Auto-select the most recent run when the document changes and no run is selected
  useEffect(() => {
    if (runs.length > 0 && !selectedRunId) {
      onSelectRun(runs[0].id)
    }
  }, [runs, selectedRunId, onSelectRun])

  const handleDelete = async (e: React.MouseEvent, runId: string) => {
    e.stopPropagation()
    try {
      await deleteRun(runId)
      toast.success('Classification run deleted')
      if (selectedRunId === runId) {
        const remaining = runs.filter((r) => r.id !== runId)
        if (remaining.length > 0) onSelectRun(remaining[0].id)
      }
    } catch {
      toast.error('Failed to delete run')
    }
  }

  return (
    <div className="border-b shrink-0">
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/20">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Classification runs
        </span>
        <Button size="sm" variant="outline" className="h-7 text-xs" onClick={onNewRun}>
          <Plus className="h-3.5 w-3.5 mr-1" />
          New Run
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="m-2">
          <AlertDescription className="text-xs">{error}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="p-2 space-y-1">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      ) : runs.length === 0 ? (
        <div className="px-4 py-3 text-xs text-muted-foreground">
          No runs yet.{' '}
          <button className="underline hover:no-underline" onClick={onNewRun}>
            Start the first one.
          </button>
        </div>
      ) : (
        <div className="overflow-y-auto max-h-44">
          {runs.map((run) => {
            const isSelected = run.id === selectedRunId
            const modelSummary =
              run.classifierType === 'llm'
                ? `${run.classifierConfig.provider as string} / ${run.classifierConfig.model as string}`
                : run.classifierType
            return (
              <button
                key={run.id}
                onClick={() => onSelectRun(run.id)}
                className={cn(
                  'w-full text-left flex items-center gap-3 px-4 py-2.5 text-sm border-b last:border-0 hover:bg-muted/50 transition-colors',
                  isSelected && 'bg-muted border-l-2 border-l-primary',
                )}
              >
                <ClassificationRunStatusBadge status={run.status} />
                <span className="flex-1 truncate text-xs text-muted-foreground">
                  {run.labelsRequested.join(', ')}
                </span>
                <span className="text-xs text-muted-foreground shrink-0 hidden sm:block">
                  {modelSummary}
                </span>
                <span className="text-xs text-muted-foreground shrink-0">
                  {formatDistanceToNow(new Date(run.createdAt), { addSuffix: true })}
                </span>
                <button
                  aria-label="Delete run"
                  onClick={(e) => handleDelete(e, run.id)}
                  className="shrink-0 hover:text-destructive text-muted-foreground"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
