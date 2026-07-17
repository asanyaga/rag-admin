import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useParseAgentRun } from '@/hooks/useParseAgentRun'
import { GraphStrip } from '@/components/parse-agent/GraphStrip'
import { RunTimeline } from '@/components/parse-agent/RunTimeline'
import { StepDetailPanel } from '@/components/parse-agent/StepDetailPanel'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ArrowLeft } from 'lucide-react'
import type { ParseAgentRunStep } from '@/types/parseAgent'

export function ParseAgentRunDetailPage(): JSX.Element {
  const { runId } = useParams<{ runId: string }>()
  const { detail, error } = useParseAgentRun(runId ?? null)
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null)

  // The selection is keyed to a specific run's steps; carry-over would point at a
  // step that does not exist in the newly loaded run.
  useEffect(() => {
    setSelectedStepId(null)
  }, [runId])

  // Independent of isLoading timing: anything that is neither loaded nor errored is
  // still in flight. A missing run surfaces via `error`, not via a null detail.
  if (!detail && !error) return <Skeleton className="h-64 w-full" />
  if (!detail) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  const { run, steps, graphNodes } = detail
  const selectedStep: ParseAgentRunStep | null =
    steps.find((s) => s.id === selectedStepId) ?? null

  const handleSelectNode = (node: string) => {
    const step = steps.find((s) => s.node === node)
    setSelectedStepId(step ? step.id : null)
  }

  return (
    <div className="space-y-4">
      <Link
        to="/parse-agent"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"
      >
        <ArrowLeft className="h-4 w-4" />
        Parse Agent
      </Link>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-mono text-lg">{run.id}</h1>
          <p className="text-xs text-muted-foreground">
            started {new Date(run.startedAt).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {run.status === 'running' ? (
            <Badge variant="outline" className="border-emerald-500 text-emerald-600">
              ● polling
            </Badge>
          ) : null}
          <Badge variant="outline">{run.status}</Badge>
        </div>
      </div>

      {error ? (
        <Alert>
          <AlertDescription>Live updates interrupted: {error}</AlertDescription>
        </Alert>
      ) : null}

      {run.error ? (
        <Alert variant="destructive">
          <AlertDescription>{run.error}</AlertDescription>
        </Alert>
      ) : null}

      <GraphStrip
        graphNodes={graphNodes}
        steps={steps}
        runStatus={run.status}
        selectedNode={selectedStep?.node ?? null}
        onSelectNode={handleSelectNode}
      />

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border">
          <p className="border-b p-2 text-xs uppercase text-muted-foreground">
            Timeline
          </p>
          <RunTimeline
            steps={steps}
            selectedStepId={selectedStepId}
            onSelectStep={(s) => setSelectedStepId(s.id)}
          />
        </div>
        <div className="rounded-lg border bg-muted/20">
          <p className="border-b p-2 text-xs uppercase text-muted-foreground">
            Step detail
          </p>
          <StepDetailPanel step={selectedStep} />
        </div>
      </div>
    </div>
  )
}
