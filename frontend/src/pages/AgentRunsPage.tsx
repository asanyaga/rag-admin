import { useParams, useNavigate } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useAgentRuns } from '@/hooks/useAgentRuns'
import { useAgentComposer } from '@/hooks/useAgentComposer'
import { useDocuments } from '@/hooks/useDocuments'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import { AgentRunInputForm } from '@/components/agent/AgentRunInputForm'
import { AgentRunList } from '@/components/agent/AgentRunList'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { ArrowLeft, Workflow } from 'lucide-react'
import { toast } from 'sonner'
import type { StartExtractRunRequest } from '@/types/agent'

export default function AgentRunsPage(): JSX.Element {
  const { agentId } = useParams<{ agentId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  // Load the agent definition to get its name
  const composer = useAgentComposer(projectId, agentId)

  const {
    runs,
    isLoading: runsLoading,
    isStarting,
    error: runsError,
    startExtractRun,
    deleteRun,
  } = useAgentRuns(projectId)

  const { documents } = useDocuments(projectId)
  const { schemas } = useExtractionSchemas(projectId)

  // Filter runs to this agent
  const agentRuns = agentId
    ? runs.filter((r) => r.agentDefinitionId === agentId)
    : runs

  const handleStartRun = async (request: StartExtractRunRequest) => {
    try {
      await startExtractRun(request)
      toast.success('Run started', {
        description: 'Agent is running...',
      })
    } catch (err) {
      toast.error('Failed to start run', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

  const handleDeleteRun = async (runId: string) => {
    try {
      await deleteRun(runId)
      toast.success('Run deleted')
    } catch (err) {
      toast.error('Failed to delete run', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

  if (!currentProject) {
    return (
      <Alert>
        <AlertDescription>Loading project...</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0"
          onClick={() => navigate('/agent')}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <Workflow className="h-5 w-5 text-muted-foreground" />
        <div>
          <h1 className="text-lg font-semibold">
            {composer.agentName || 'Agent Runs'}
          </h1>
          {composer.agentDescription && (
            <p className="text-sm text-muted-foreground">
              {composer.agentDescription}
            </p>
          )}
        </div>
      </div>

      {runsError && (
        <Alert variant="destructive">
          <AlertDescription>{runsError}</AlertDescription>
        </Alert>
      )}

      {/* Input form */}
      {agentId && (
        <div className="rounded-lg border p-4">
          <h2 className="text-sm font-medium mb-3">Start New Run</h2>
          {composer.isLoading ? (
            <Skeleton className="h-20 w-full" />
          ) : (
            <AgentRunInputForm
              agentDefinitionId={agentId}
              documents={documents}
              schemas={schemas}
              isStarting={isStarting}
              onStart={handleStartRun}
            />
          )}
        </div>
      )}

      <Separator />

      {/* Run list */}
      <div>
        <h2 className="text-sm font-medium mb-3">
          Runs
          {agentRuns.length > 0 && (
            <span className="text-muted-foreground font-normal ml-1.5">
              ({agentRuns.length})
            </span>
          )}
        </h2>
        <AgentRunList
          runs={agentRuns}
          isLoading={runsLoading}
          onDelete={handleDeleteRun}
        />
      </div>
    </div>
  )
}
