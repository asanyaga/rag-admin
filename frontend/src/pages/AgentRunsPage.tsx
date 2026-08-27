import { useParams, useNavigate } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useAgentRuns } from '@/hooks/useAgentRuns'
import { useAgentComposer } from '@/hooks/useAgentComposer'
import { useDocuments } from '@/hooks/useDocuments'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import { AgentRunInputForm } from '@/components/agent/AgentRunInputForm'
import { ParseRunInputForm } from '@/components/agent/ParseRunInputForm'
import { AgentRunForm } from '@/components/agent/AgentRunForm'
import { AgentRunList } from '@/components/agent/AgentRunList'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { ArrowLeft, Workflow } from 'lucide-react'
import { toast } from 'sonner'
import type {
  AgentDefinitionData,
  AgentTool,
  StartExtractRunRequest,
  StartParseRunRequest,
} from '@/types/agent'

/**
 * The entry node is the node that is never the target of an edge (mirrors
 * the backend's auto-inferred START in `build_agent_graph`), falling back
 * to the first node in definition order.
 */
function entryNodeCategory(
  definition: AgentDefinitionData | undefined,
  tools: AgentTool[]
): string | null {
  if (!definition || definition.nodes.length === 0) return null
  const targets = new Set<string>()
  for (const e of definition.edges) targets.add(e.target)
  for (const ce of definition.conditional_edges ?? []) {
    for (const t of ce.targets) {
      if (t !== '__end__') targets.add(t)
    }
  }
  const entryNode =
    definition.nodes.find((n) => !targets.has(n.id)) ?? definition.nodes[0]
  const tool = tools.find((t) => t.slug === entryNode.tool)
  return tool?.category ?? null
}

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
    startParseRun,
    deleteRun,
  } = useAgentRuns(projectId)

  const { documents } = useDocuments(projectId)
  const { schemas } = useExtractionSchemas(projectId)
  const { sourceDocuments } = useSourceDocuments()

  // A "parse-first" agent has a node using the legacy single parse tool.
  const isParseAgent = composer.nodes.some(
    (n) => n.data?.toolSlug === 'parse'
  )

  // A composed parsing agent's entry node uses a tool from the `parsing`
  // category (Task 1-4's composable parse tools, e.g. `parse.llamaparse`).
  const isComposedParsingAgent =
    entryNodeCategory(composer.savedAgent?.definition, composer.tools) ===
    'parsing'

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

  const handleStartParseRun = async (request: StartParseRunRequest) => {
    try {
      await startParseRun(request)
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
          ) : isComposedParsingAgent && composer.savedAgent && projectId ? (
            <AgentRunForm
              projectId={projectId}
              definitionId={agentId}
              definition={composer.savedAgent.definition}
              tools={composer.tools}
              onStarted={(runId) => navigate(`/agent/runs/${runId}`)}
            />
          ) : isParseAgent ? (
            <ParseRunInputForm
              agentDefinitionId={agentId}
              sourceDocuments={sourceDocuments}
              isStarting={isStarting}
              onStart={handleStartParseRun}
            />
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
