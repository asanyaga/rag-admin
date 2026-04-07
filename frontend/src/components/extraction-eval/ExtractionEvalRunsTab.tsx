import { useState } from 'react'
import { useExtractionGroundTruthSets } from '@/hooks/useExtractionGroundTruth'
import { useExtractionEvalRuns, useExtractionEvalRunDetail } from '@/hooks/useExtractionEval'
import { EvalRunConfig } from './EvalRunConfig'
import { AggregateMetrics } from './AggregateMetrics'
import { DocumentResultsTable } from './DocumentResultsTable'
import { EvalStatusBadge } from '@/components/evaluation/EvalStatusBadge'
import { ScorePill } from '@/components/evaluation/ScorePill'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { ArrowLeft, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

interface ExtractionEvalRunsTabProps {
  projectId: string
}

export function ExtractionEvalRunsTab({ projectId }: ExtractionEvalRunsTabProps) {
  const { sets } = useExtractionGroundTruthSets(projectId)
  const { runs, isLoading, createRun, deleteRun } = useExtractionEvalRuns(projectId)

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const { run: selectedRun, results } = useExtractionEvalRunDetail(selectedRunId)

  const [isCreating, setIsCreating] = useState(false)

  const handleCreateRun = async (data: { groundTruthSetId: string; name?: string }) => {
    setIsCreating(true)
    try {
      await createRun(data)
      toast.success('Evaluation started')
    } catch (err) {
      toast.error('Failed to start evaluation', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    } finally {
      setIsCreating(false)
    }
  }

  const handleDeleteRun = async (id: string) => {
    try {
      await deleteRun(id)
      if (selectedRunId === id) setSelectedRunId(null)
      toast.success('Eval run deleted')
    } catch (err) {
      toast.error('Failed to delete run', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

  // Detail view
  if (selectedRunId && selectedRun) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => setSelectedRunId(null)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h2 className="text-lg font-bold">{selectedRun.name}</h2>
            <div className="flex items-center gap-2 mt-0.5">
              <EvalStatusBadge status={selectedRun.status} />
              <span className="text-sm text-muted-foreground">
                {selectedRun.groundTruthSetName}
              </span>
              {selectedRun.status === 'running' && (
                <span className="text-xs text-muted-foreground">
                  {selectedRun.itemsCompleted}/{selectedRun.itemsTotal}
                </span>
              )}
            </div>
          </div>
        </div>

        {selectedRun.metrics && (
          <AggregateMetrics metrics={selectedRun.metrics} />
        )}

        {selectedRun.metrics?.fieldAccuracy && (
          <div>
            <h3 className="text-sm font-medium mb-3">Per-Field Accuracy</h3>
            <div className="rounded-lg border divide-y">
              {Object.entries(selectedRun.metrics.fieldAccuracy).map(
                ([field, acc]) => (
                  <div
                    key={field}
                    className="flex items-center justify-between px-4 py-2"
                  >
                    <span className="text-sm capitalize">
                      {field.replace(/_/g, ' ')}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-muted-foreground">
                        Exact: {(acc.exactMatchRate * 100).toFixed(0)}%
                      </span>
                      <ScorePill score={acc.avgScore} />
                    </div>
                  </div>
                )
              )}
            </div>
          </div>
        )}

        {results.length > 0 && (
          <div>
            <h3 className="text-sm font-medium mb-3">Per-Document Results</h3>
            <DocumentResultsTable results={results} />
          </div>
        )}

        {selectedRun.errorMessage && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4">
            <p className="text-sm text-destructive">{selectedRun.errorMessage}</p>
          </div>
        )}
      </div>
    )
  }

  // List view
  return (
    <div className="space-y-6">
      <EvalRunConfig
        groundTruthSets={sets}
        onRun={handleCreateRun}
        isRunning={isCreating}
      />

      <Separator />

      <div>
        <h3 className="text-sm font-medium mb-3">Evaluation Runs</h3>
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : runs.length === 0 ? (
          <div className="text-center py-12 text-sm text-muted-foreground">
            No evaluation runs yet. Select a ground truth set and run an evaluation.
          </div>
        ) : (
          <div className="space-y-2">
            {runs.map((run) => (
              <Card
                key={run.id}
                className="cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => setSelectedRunId(run.id)}
              >
                <CardContent className="py-3 px-4">
                  <div className="flex items-center justify-between">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium truncate">
                          {run.name}
                        </span>
                        <EvalStatusBadge status={run.status} />
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                        <span>{run.groundTruthSetName}</span>
                        <span>
                          {new Date(run.createdAt).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                        {run.metrics && (
                          <ScorePill score={run.metrics.overallScoreMean} />
                        )}
                        {run.status === 'running' && (
                          <span>
                            {run.itemsCompleted}/{run.itemsTotal}
                          </span>
                        )}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 shrink-0"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteRun(run.id)
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
