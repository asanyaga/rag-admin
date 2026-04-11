import { useNavigate } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useAgentDefinitions } from '@/hooks/useAgentDefinitions'
import { AgentList } from '@/components/agent/AgentList'
import { Button } from '@/components/ui/button'
import { Plus } from 'lucide-react'

export default function AgentListPage() {
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null
  const { agents, isLoading, deleteAgent } = useAgentDefinitions(projectId)

  const handleDelete = async (agentId: string) => {
    if (!window.confirm('Delete this agent definition? All associated runs will also be deleted.')) return
    await deleteAgent(agentId)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Agents</h1>
        <Button size="sm" onClick={() => navigate('/agent/new')}>
          <Plus className="h-4 w-4 mr-1.5" />
          New Agent
        </Button>
      </div>
      <AgentList agents={agents} isLoading={isLoading} onDelete={handleDelete} />
    </div>
  )
}
