import { useState, useCallback, useEffect, useRef } from 'react'
import type {
  AgentRunListItem,
  StartAgentRunRequest,
  StartExtractRunRequest,
  StartParseRunRequest,
} from '@/types/agent'
import * as agentApi from '@/api/agent'

const POLLING_INTERVAL = 3000
const POLLING_TIMEOUT = 10 * 60 * 1000

interface UseAgentRunsReturn {
  runs: AgentRunListItem[]
  isLoading: boolean
  isStarting: boolean
  error: string | null
  fetchRuns: () => Promise<void>
  startRun: (request: StartAgentRunRequest) => Promise<void>
  startExtractRun: (request: StartExtractRunRequest) => Promise<void>
  startParseRun: (request: StartParseRunRequest) => Promise<void>
  deleteRun: (runId: string) => Promise<void>
}

export function useAgentRuns(
  projectId: string | null
): UseAgentRunsReturn {
  const [runs, setRuns] = useState<AgentRunListItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStarting, setIsStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollingStartRef = useRef<number>(0)

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const fetchRuns = useCallback(async () => {
    if (!projectId) {
      setRuns([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await agentApi.listAgentRuns(projectId)
      setRuns(data)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch agent runs'
      )
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const startRun = useCallback(
    async (request: StartAgentRunRequest) => {
      if (!projectId) throw new Error('No project selected')
      setIsStarting(true)
      setError(null)
      try {
        await agentApi.startAgentRun(projectId, request)
        await fetchRuns()
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to start agent run'
        )
        throw err
      } finally {
        setIsStarting(false)
      }
    },
    [projectId, fetchRuns]
  )

  const startExtractRun = useCallback(
    async (request: StartExtractRunRequest) => {
      if (!projectId) throw new Error('No project selected')
      setIsStarting(true)
      setError(null)
      try {
        await agentApi.startExtractRun(projectId, request)
        await fetchRuns()
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to start extract run'
        )
        throw err
      } finally {
        setIsStarting(false)
      }
    },
    [projectId, fetchRuns]
  )

  const startParseRun = useCallback(
    async (request: StartParseRunRequest) => {
      if (!projectId) throw new Error('No project selected')
      setIsStarting(true)
      setError(null)
      try {
        await agentApi.startParseRun(projectId, request)
        await fetchRuns()
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to start parse run'
        )
        throw err
      } finally {
        setIsStarting(false)
      }
    },
    [projectId, fetchRuns]
  )

  const deleteRun = useCallback(
    async (runId: string) => {
      await agentApi.deleteAgentRun(runId)
      await fetchRuns()
    },
    [fetchRuns]
  )

  // Poll when there are active runs
  useEffect(() => {
    const hasActive = runs.some(
      (r) => r.status === 'pending' || r.status === 'running'
    )

    if (hasActive && !pollingRef.current) {
      pollingStartRef.current = Date.now()
      pollingRef.current = setInterval(async () => {
        if (Date.now() - pollingStartRef.current > POLLING_TIMEOUT) {
          stopPolling()
          return
        }
        await fetchRuns()
      }, POLLING_INTERVAL)
    } else if (!hasActive) {
      stopPolling()
    }

    return () => stopPolling()
  }, [runs, fetchRuns, stopPolling])

  // Initial fetch
  useEffect(() => {
    if (projectId) {
      fetchRuns()
    } else {
      setRuns([])
    }
  }, [projectId, fetchRuns])

  return {
    runs, isLoading, isStarting, error,
    fetchRuns, startRun, startExtractRun, startParseRun, deleteRun,
  }
}
