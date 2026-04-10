import { useState, useCallback, useEffect } from 'react'
import type { AgentType, AgentConfig, AgentConfigCreate } from '@/types/agent'
import * as agentApi from '@/api/agent'

interface UseAgentConfigsReturn {
  agentTypes: AgentType[]
  configs: AgentConfig[]
  isLoading: boolean
  error: string | null
  fetchConfigs: () => Promise<void>
  enableAgentType: (data: AgentConfigCreate) => Promise<AgentConfig>
  removeConfig: (configId: string) => Promise<void>
}

export function useAgentConfigs(
  projectId: string | null
): UseAgentConfigsReturn {
  const [agentTypes, setAgentTypes] = useState<AgentType[]>([])
  const [configs, setConfigs] = useState<AgentConfig[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchConfigs = useCallback(async () => {
    if (!projectId) {
      setConfigs([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const [typesData, configsData] = await Promise.all([
        agentApi.listAgentTypes(),
        agentApi.listAgentConfigs(projectId),
      ])
      setAgentTypes(typesData)
      setConfigs(configsData)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch agent configs'
      )
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const enableAgentType = useCallback(
    async (data: AgentConfigCreate): Promise<AgentConfig> => {
      if (!projectId) throw new Error('No project selected')
      const config = await agentApi.createAgentConfig(projectId, data)
      await fetchConfigs()
      return config
    },
    [projectId, fetchConfigs]
  )

  const removeConfig = useCallback(
    async (configId: string): Promise<void> => {
      await agentApi.deleteAgentConfig(configId)
      await fetchConfigs()
    },
    [fetchConfigs]
  )

  useEffect(() => {
    if (projectId) {
      fetchConfigs()
    } else {
      setConfigs([])
      setAgentTypes([])
    }
  }, [projectId, fetchConfigs])

  return {
    agentTypes,
    configs,
    isLoading,
    error,
    fetchConfigs,
    enableAgentType,
    removeConfig,
  }
}
