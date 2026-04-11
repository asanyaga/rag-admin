import { useState, useCallback, useEffect } from 'react'
import type { AgentDefinition } from '@/types/agent'
import * as agentApi from '@/api/agent'

interface UseAgentDefinitionsReturn {
  agents: AgentDefinition[]
  isLoading: boolean
  error: string | null
  fetchAgents: () => Promise<void>
  deleteAgent: (agentId: string) => Promise<void>
}

export function useAgentDefinitions(
  projectId: string | null
): UseAgentDefinitionsReturn {
  const [agents, setAgents] = useState<AgentDefinition[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchAgents = useCallback(async () => {
    if (!projectId) {
      setAgents([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await agentApi.listAgentDefinitions(projectId)
      setAgents(data)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch agents'
      )
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const deleteAgent = useCallback(
    async (agentId: string) => {
      await agentApi.deleteAgentDefinition(agentId)
      await fetchAgents()
    },
    [fetchAgents]
  )

  useEffect(() => {
    if (projectId) {
      fetchAgents()
    } else {
      setAgents([])
    }
  }, [projectId, fetchAgents])

  return { agents, isLoading, error, fetchAgents, deleteAgent }
}
