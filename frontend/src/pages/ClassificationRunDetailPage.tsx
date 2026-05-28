// frontend/src/pages/ClassificationRunDetailPage.tsx
import { useNavigate, useParams } from 'react-router-dom'
import { useClassificationRunDetail } from '@/hooks/useClassificationRuns'
import { ClassificationRunStatusBadge } from '@/components/classification/ClassificationRunStatusBadge'
import { ClassificationResultsViewer } from '@/components/classification/ClassificationResultsViewer'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ChevronLeft, RotateCw } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

export default function ClassificationRunDetailPage(): JSX.Element {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const { run, isLoading, error } = useClassificationRunDetail(runId ?? null)

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  if (!run) return <></>

  const handleRerun = () => {
    navigate(`/classify/new?documentId=${run.documentId}`)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/classify')}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">Classification run</h1>
            <ClassificationRunStatusBadge status={run.status} />
          </div>
          <p className="text-muted-foreground text-sm mt-1">
            {run.classifierType === 'llm'
              ? `${run.classifierConfig.provider as string} / ${run.classifierConfig.model as string}`
              : run.classifierType}{' '}
            · {formatDistanceToNow(new Date(run.createdAt), { addSuffix: true })}
          </p>
        </div>
        <Button variant="outline" onClick={handleRerun}>
          <RotateCw className="h-4 w-4 mr-2" />
          Re-run
        </Button>
      </div>

      <div className="grid grid-cols-4 gap-4 text-sm">
        <div>
          <p className="text-muted-foreground">Labels</p>
          <p className="font-medium">{run.labelsRequested.join(', ')}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Regions found</p>
          <p className="font-medium">{run.regions.length}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Tokens</p>
          <p className="font-medium">
            {run.inputTokens !== null ? `${run.inputTokens} in / ${run.outputTokens} out` : '—'}
          </p>
        </div>
        <div>
          <p className="text-muted-foreground">Duration</p>
          <p className="font-medium">
            {run.durationMs !== null ? `${(run.durationMs / 1000).toFixed(1)}s` : '—'}
          </p>
        </div>
      </div>

      {run.error && (
        <Alert variant="destructive">
          <AlertDescription>{run.error}</AlertDescription>
        </Alert>
      )}

      {run.status === 'running' && (
        <p className="text-sm text-muted-foreground animate-pulse">
          Classification in progress…
        </p>
      )}

      {run.status === 'completed' && (
        <section>
          <h2 className="text-lg font-medium mb-3">Classification results</h2>
          <ClassificationResultsViewer runId={run.id} labelsRequested={run.labelsRequested} />
        </section>
      )}
    </div>
  )
}
