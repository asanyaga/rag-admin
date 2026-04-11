import { useState, useCallback, useEffect } from 'react'
import type { FlowDefinition } from '@/types/agent'
import * as agentApi from '@/api/agent'

interface UseFlowDefinitionsReturn {
  flows: FlowDefinition[]
  isLoading: boolean
  error: string | null
  fetchFlows: () => Promise<void>
  deleteFlow: (flowId: string) => Promise<void>
}

export function useFlowDefinitions(
  projectId: string | null
): UseFlowDefinitionsReturn {
  const [flows, setFlows] = useState<FlowDefinition[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchFlows = useCallback(async () => {
    if (!projectId) {
      setFlows([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await agentApi.listFlowDefinitions(projectId)
      setFlows(data)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch flows'
      )
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const deleteFlow = useCallback(
    async (flowId: string) => {
      await agentApi.deleteFlowDefinition(flowId)
      await fetchFlows()
    },
    [fetchFlows]
  )

  useEffect(() => {
    if (projectId) {
      fetchFlows()
    } else {
      setFlows([])
    }
  }, [projectId, fetchFlows])

  return { flows, isLoading, error, fetchFlows, deleteFlow }
}
