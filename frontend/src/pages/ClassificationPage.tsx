// frontend/src/pages/ClassificationPage.tsx
import { useNavigate } from 'react-router-dom'
import { Plus, Trash2 } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useClassificationRuns } from '@/hooks/useClassificationRuns'
import { ClassificationRunStatusBadge } from '@/components/classification/ClassificationRunStatusBadge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { toast } from 'sonner'
import { formatDistanceToNow } from 'date-fns'

export default function ClassificationPage(): JSX.Element {
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const { runs, isLoading, error, deleteRun } = useClassificationRuns(currentProject?.id ?? null)

  const handleDelete = async (runId: string) => {
    try {
      await deleteRun(runId)
      toast.success('Classification run deleted')
    } catch {
      toast.error('Failed to delete run')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Classify</h1>
          <p className="text-muted-foreground mt-1">{currentProject?.name}</p>
        </div>
        <Button onClick={() => navigate('/classify/new')}>
          <Plus className="h-4 w-4 mr-2" />
          New classification run
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : runs.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <p>No classification runs yet.</p>
          <Button className="mt-4" onClick={() => navigate('/classify/new')}>
            Start your first run
          </Button>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Labels</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Provider / Model</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Created</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {runs.map((run) => (
              <TableRow
                key={run.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => navigate(`/classify/${run.id}`)}
              >
                <TableCell>
                  <span className="text-sm">{run.labelsRequested.join(', ')}</span>
                </TableCell>
                <TableCell>
                  <ClassificationRunStatusBadge status={run.status} />
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {run.classifierType === 'llm'
                    ? `${run.classifierConfig.provider as string} / ${run.classifierConfig.model as string}`
                    : run.classifierType}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {run.durationMs !== null ? `${(run.durationMs / 1000).toFixed(1)}s` : '—'}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {formatDistanceToNow(new Date(run.createdAt), { addSuffix: true })}
                </TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDelete(run.id)}
                  >
                    <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
