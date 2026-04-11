import { useParams } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useAgentComposer } from '@/hooks/useAgentComposer'
import { AgentComposer } from '@/components/agent/composer/AgentComposer'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'

export default function AgentComposerPage(): JSX.Element {
  const { agentId } = useParams<{ agentId?: string }>()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const composer = useAgentComposer(projectId, agentId)

  if (!currentProject) {
    return (
      <div className="space-y-6">
        <Alert>
          <AlertDescription>Loading project...</AlertDescription>
        </Alert>
      </div>
    )
  }

  if (composer.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  if (composer.error && !composer.tools.length) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{composer.error}</AlertDescription>
      </Alert>
    )
  }

  return <AgentComposer composer={composer} />
}
