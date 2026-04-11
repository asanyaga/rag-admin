import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useAgentRun } from '@/hooks/useAgentRun'
import { AgentRunDetail } from '@/components/agent/AgentRunDetail'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'
import type { AgentDefinition, ResumeAgentRunRequest } from '@/types/agent'
import * as agentApi from '@/api/agent'

export default function AgentRunDetailPage(): JSX.Element {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()

  const { run, isLoading, isResuming, error, resumeRun } = useAgentRun(
    runId ?? null
  )

  // Load agent definition for context
  const [agentDef, setAgentDef] = useState<AgentDefinition | null>(null)
  useEffect(() => {
    if (run?.agentDefinitionId) {
      agentApi
        .getAgentDefinition(run.agentDefinitionId)
        .then(setAgentDef)
        .catch(() => {})
    }
  }, [run?.agentDefinitionId])

  const handleResume = async (request: ResumeAgentRunRequest) => {
    try {
      await resumeRun(request)
      toast.success('Run resumed')
    } catch (err) {
      toast.error('Failed to resume run', {
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

      <AgentRunDetail
        run={run}
        agentDefinition={agentDef}
        isLoading={isLoading}
        isResuming={isResuming}
        error={error}
        onResume={handleResume}
      />
    </div>
  )
}
