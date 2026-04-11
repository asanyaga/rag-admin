import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useFlowRun } from '@/hooks/useFlowRun'
import { FlowRunDetail } from '@/components/agent/FlowRunDetail'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'
import type { FlowDefinition, SubmitReviewRequest } from '@/types/agent'
import * as agentApi from '@/api/agent'

export default function FlowRunDetailPage(): JSX.Element {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()

  const { run, isLoading, isResuming, error, resumeRun } = useFlowRun(
    runId ?? null
  )

  // Load flow definition for graph visualization
  const [flowDef, setFlowDef] = useState<FlowDefinition | null>(null)
  useEffect(() => {
    if (run?.flowDefinitionId) {
      agentApi
        .getFlowDefinition(run.flowDefinitionId)
        .then(setFlowDef)
        .catch(() => {})
    }
  }, [run?.flowDefinitionId])

  const handleResume = async (request: SubmitReviewRequest) => {
    try {
      await resumeRun({
        resumeValue: { action: request.action, data: request.data },
      })
      if (request.action === 'reject') {
        toast.info('Run rejected')
      } else {
        toast.success('Review submitted')
      }
    } catch (err) {
      toast.error('Failed to submit review', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

  if (!runId) {
    return (
      <Alert>
        <AlertDescription>No run ID provided.</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0"
          onClick={() => navigate(-1)}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-lg font-semibold">Run Detail</h1>
      </div>

      <FlowRunDetail
        run={run}
        flowDefinition={flowDef}
        isLoading={isLoading}
        isResuming={isResuming}
        error={error}
        onResume={handleResume}
      />
    </div>
  )
}
