import { useNavigate } from 'react-router-dom'
import type { AgentDefinition } from '@/types/agent'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Pencil, Play, Trash2, Workflow } from 'lucide-react'

interface AgentListProps {
  agents: AgentDefinition[]
  isLoading: boolean
  onDelete: (agentId: string) => Promise<void>
}

export function AgentList({ agents, isLoading, onDelete }: AgentListProps) {
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    )
  }

  if (agents.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
        No agents yet. Click <span className="font-medium">New Agent</span> to
        compose your first agent workflow.
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {agents.map((agent) => (
        <div
          key={agent.id}
          className="flex items-center gap-3 rounded-lg border px-4 py-3 hover:bg-gray-50/50 transition-colors"
        >
          <Workflow className="h-4 w-4 text-muted-foreground shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium truncate">{agent.name}</div>
            {agent.description && (
              <div className="text-xs text-muted-foreground truncate">
                {agent.description}
              </div>
            )}
            <div className="text-[10px] text-muted-foreground mt-0.5">
              {agent.definition.nodes.length} node
              {agent.definition.nodes.length !== 1 ? 's' : ''} &middot;{' '}
              {new Date(agent.updatedAt).toLocaleDateString()}
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => navigate(`/agent/${agent.id}/runs`)}
              title="Runs"
            >
              <Play className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => navigate(`/agent/${agent.id}`)}
              title="Edit agent"
            >
              <Pencil className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-muted-foreground hover:text-red-600"
              onClick={() => onDelete(agent.id)}
              title="Delete agent"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      ))}
    </div>
  )
}
