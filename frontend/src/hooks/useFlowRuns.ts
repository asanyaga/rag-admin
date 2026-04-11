import { useState, useCallback, useEffect, useRef } from 'react'
import type {
  FlowRunListItem,
  StartFlowRunRequest,
} from '@/types/agent'
import * as agentApi from '@/api/agent'

const POLLING_INTERVAL = 3000
const POLLING_TIMEOUT = 10 * 60 * 1000

interface UseFlowRunsReturn {
  runs: FlowRunListItem[]
  isLoading: boolean
  isStarting: boolean
  error: string | null
  fetchRuns: () => Promise<void>
  startRun: (request: StartFlowRunRequest) => Promise<void>
}

export function useFlowRuns(
  projectId: string | null
): UseFlowRunsReturn {
  const [runs, setRuns] = useState<FlowRunListItem[]>([])
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
      const data = await agentApi.listFlowRuns(projectId)
      setRuns(data)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch flow runs'
      )
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const startRun = useCallback(
    async (request: StartFlowRunRequest) => {
      if (!projectId) throw new Error('No project selected')
      setIsStarting(true)
      setError(null)
      try {
        await agentApi.startFlowRun(projectId, request)
        await fetchRuns()
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to start flow run'
        )
        throw err
      } finally {
        setIsStarting(false)
      }
    },
    [projectId, fetchRuns]
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

  return { runs, isLoading, isStarting, error, fetchRuns, startRun }
}
