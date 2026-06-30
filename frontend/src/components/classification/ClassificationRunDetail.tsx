import { useState } from 'react'
import { RotateCw, PanelRightClose, PanelRightOpen } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { ClassificationRunStatusBadge } from './ClassificationRunStatusBadge'
import { ClassificationResultsViewer } from './ClassificationResultsViewer'
import { ParsedDocumentViewer } from '@/components/documents/ParsedDocumentViewer'
import { useClassificationRunDetail, useClassificationRunBlocks } from '@/hooks/useClassificationRuns'

export interface RerunDefaults {
  labels: string[]
  classifierType: string
  classifierConfig: Record<string, unknown>
}

interface ClassificationRunDetailProps {
  runId: string
  documentId: string
  onRerun: (defaults: RerunDefaults) => void
}

export function ClassificationRunDetail({
  runId,
  documentId,
  onRerun,
}: ClassificationRunDetailProps) {
  const { run, isLoading, error } = useClassificationRunDetail(runId)
  const { blocks } = useClassificationRunBlocks(
    run?.status === 'completed' ? runId : null,
  )
  const [viewerCollapsed, setViewerCollapsed] = useState(false)

  if (isLoading) {
    return (
      <div className="p-6 space-y-3">
        <Skeleton className="h-6 w-64" />
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4">
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    )
  }

  if (!run) return null

  const handleRerun = () => {
    onRerun({
      labels: run.labelsRequested,
      classifierType: run.classifierType,
      classifierConfig: run.classifierConfig,
    })
  }

  const modelSummary =
    run.classifierType === 'llm'
      ? `${run.classifierConfig.provider as string} / ${run.classifierConfig.model as string}`
      : run.classifierType

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Metadata strip */}
      <div className="px-4 py-3 border-b shrink-0 flex items-center gap-4 flex-wrap">
        <ClassificationRunStatusBadge status={run.status} />
        <span className="text-sm text-muted-foreground">{modelSummary}</span>
        <span className="text-xs text-muted-foreground">
          {formatDistanceToNow(new Date(run.createdAt), { addSuffix: true })}
        </span>
        <div className="flex gap-4 text-xs text-muted-foreground ml-auto">
          <span><span className="font-medium text-foreground">{run.labelsRequested.length}</span> labels</span>
          <span><span className="font-medium text-foreground">{run.regions.length}</span> regions</span>
          {run.inputTokens !== null && (
            <span>
              <span className="font-medium text-foreground">{run.inputTokens}</span> in /{' '}
              <span className="font-medium text-foreground">{run.outputTokens}</span> out tokens
            </span>
          )}
          {run.durationMs !== null && (
            <span><span className="font-medium text-foreground">{(run.durationMs / 1000).toFixed(1)}s</span></span>
          )}
        </div>
        <Button variant="outline" size="sm" className="h-7 text-xs shrink-0" onClick={handleRerun}>
          <RotateCw className="h-3.5 w-3.5 mr-1.5" />
          Re-run
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          title={viewerCollapsed ? 'Show document viewer' : 'Hide document viewer'}
          onClick={() => setViewerCollapsed((v) => !v)}
        >
          {viewerCollapsed
            ? <PanelRightOpen className="h-4 w-4" />
            : <PanelRightClose className="h-4 w-4" />}
        </Button>
      </div>

      {/* Error / running states */}
      {run.error && (
        <div className="px-4 pt-3 shrink-0">
          <Alert variant="destructive">
            <AlertDescription>{run.error}</AlertDescription>
          </Alert>
        </div>
      )}

      {run.status === 'running' && (
        <p className="px-4 pt-3 text-sm text-muted-foreground animate-pulse shrink-0">
          Classification in progress…
        </p>
      )}

      {/* Results split */}
      {run.status === 'completed' && (
        <div className="flex flex-1 min-h-0">
          {/* Left: label results */}
          <div className="w-80 shrink-0 border-r overflow-y-auto p-4">
            <ClassificationResultsViewer
              runId={run.id}
              labelsRequested={run.labelsRequested}
            />
          </div>

          {/* Right: document viewer */}
          {!viewerCollapsed && (
            <div className="flex-1 overflow-y-auto">
              <ParsedDocumentViewer
                documentId={documentId}
                defaultParseRunId={run.parseRunId}
                regions={run.regions}
                annotatedBlocks={blocks}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
