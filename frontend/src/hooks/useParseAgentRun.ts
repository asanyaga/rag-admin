import { useState, useCallback, useEffect, useRef } from 'react'
import * as parseAgentApi from '@/api/parseAgent'
import type { ParseAgentRunDetail } from '@/types/parseAgent'

const POLLING_INTERVAL = 2000
const POLLING_TIMEOUT = 10 * 60 * 1000

interface UseParseAgentRunReturn {
  detail: ParseAgentRunDetail | null
  isLoading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export function useParseAgentRun(runId: string | null): UseParseAgentRunReturn {
  const [detail, setDetail] = useState<ParseAgentRunDetail | null>(null)
  // Seed from whether a fetch is pending, so the first render already reports loading
  // instead of briefly looking like a resolved-but-empty run.
  const [isLoading, setIsLoading] = useState(!!runId)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollingStartRef = useRef<number>(0)

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const refetch = useCallback(async () => {
    if (!runId) {
      setDetail(null)
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      setDetail(await parseAgentApi.getParseAgentRun(runId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch run')
    } finally {
      setIsLoading(false)
    }
  }, [runId])

  const isActive = detail?.run.status === 'running'

  // Poll only while the run is active.
  // Keyed off the `isActive` primitive, not the `detail` object: every poll replaces
  // `detail` with a new object reference, which would otherwise tear down and recreate
  // the interval on each tick and reset `pollingStartRef`, so the timeout below could
  // never accumulate toward its limit.
  useEffect(() => {
    if (isActive && !pollingRef.current) {
      pollingStartRef.current = Date.now()
      pollingRef.current = setInterval(async () => {
        if (Date.now() - pollingStartRef.current > POLLING_TIMEOUT) {
          stopPolling()
          return
        }
        await refetch()
      }, POLLING_INTERVAL)
    } else if (!isActive) {
      stopPolling()
    }
    return () => stopPolling()
  }, [isActive, refetch, stopPolling])

  // Reset on every runId change: React Router reuses this component on a param-only
  // change, so without clearing, the previous run's detail stays on screen while the
  // new one is in flight. `refetch` is useCallback([runId]), so this runs once per runId.
  useEffect(() => {
    setDetail(null)
    setError(null)
    if (runId) {
      refetch()
    }
  }, [runId, refetch])

  return { detail, isLoading, error, refetch }
}
