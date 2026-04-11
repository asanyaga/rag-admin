import { useParams } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useFlowComposer } from '@/hooks/useFlowComposer'
import { FlowComposer } from '@/components/agent/flow/FlowComposer'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'

export default function FlowComposerPage(): JSX.Element {
  const { flowId } = useParams<{ flowId?: string }>()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const composer = useFlowComposer(projectId, flowId)

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

  return <FlowComposer composer={composer} />
}
