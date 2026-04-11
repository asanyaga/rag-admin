import { useNavigate } from 'react-router-dom'
import type { FlowDefinition } from '@/types/agent'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Pencil, Trash2, Workflow } from 'lucide-react'

interface FlowListProps {
  flows: FlowDefinition[]
  isLoading: boolean
  onDelete: (flowId: string) => Promise<void>
}

export function FlowList({ flows, isLoading, onDelete }: FlowListProps) {
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    )
  }

  if (flows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
        No flows yet. Click <span className="font-medium">New Flow</span> to
        compose your first agent workflow.
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {flows.map((flow) => (
        <div
          key={flow.id}
          className="flex items-center gap-3 rounded-lg border px-4 py-3 hover:bg-gray-50/50 transition-colors"
        >
          <Workflow className="h-4 w-4 text-muted-foreground shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium truncate">{flow.name}</div>
            {flow.description && (
              <div className="text-xs text-muted-foreground truncate">
                {flow.description}
              </div>
            )}
            <div className="text-[10px] text-muted-foreground mt-0.5">
              {flow.definition.nodes.length} node
              {flow.definition.nodes.length !== 1 ? 's' : ''} &middot;{' '}
              {new Date(flow.updatedAt).toLocaleDateString()}
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => navigate(`/agent/flows/${flow.id}`)}
              title="Edit flow"
            >
              <Pencil className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-muted-foreground hover:text-red-600"
              onClick={() => onDelete(flow.id)}
              title="Delete flow"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      ))}
    </div>
  )
}
