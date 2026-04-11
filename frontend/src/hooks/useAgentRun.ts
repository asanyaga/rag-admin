import { useState, useCallback, useEffect, useRef } from 'react'
import type { AgentRun, ResumeAgentRunRequest } from '@/types/agent'
import * as agentApi from '@/api/agent'

const POLLING_INTERVAL = 3000
const POLLING_TIMEOUT = 10 * 60 * 1000

interface UseAgentRunReturn {
  run: AgentRun | null
  isLoading: boolean
  isResuming: boolean
  error: string | null
  fetchRun: () => Promise<void>
  resumeRun: (data: ResumeAgentRunRequest) => Promise<void>
}

export function useAgentRun(
  runId: string | null
): UseAgentRunReturn {
  const [run, setRun] = useState<AgentRun | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isResuming, setIsResuming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollingStartRef = useRef<number>(0)

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const fetchRun = useCallback(async () => {
    if (!runId) {
      setRun(null)
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await agentApi.getAgentRun(runId)
      setRun(data)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch agent run'
      )
    } finally {
      setIsLoading(false)
    }
  }, [runId])

  const resumeRun = useCallback(
    async (data: ResumeAgentRunRequest) => {
      if (!runId) throw new Error('No run ID')
      setIsResuming(true)
      setError(null)
      try {
        const updated = await agentApi.resumeAgentRun(runId, data)
        setRun(updated)
        stopPolling()
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to resume agent run'
        )
        throw err
      } finally {
        setIsResuming(false)
      }
    },
    [runId, stopPolling]
  )

  // Poll when run is active
  useEffect(() => {
    const isActive =
      run?.status === 'pending' || run?.status === 'running'

    if (isActive && !pollingRef.current) {
      pollingStartRef.current = Date.now()
      pollingRef.current = setInterval(async () => {
        if (Date.now() - pollingStartRef.current > POLLING_TIMEOUT) {
          stopPolling()
          return
        }
        await fetchRun()
      }, POLLING_INTERVAL)
    } else if (!isActive) {
      stopPolling()
    }

    return () => stopPolling()
  }, [run, fetchRun, stopPolling])

  // Initial fetch
  useEffect(() => {
    if (runId) {
      fetchRun()
    } else {
      setRun(null)
    }
  }, [runId, fetchRun])

  return { run, isLoading, isResuming, error, fetchRun, resumeRun }
}
