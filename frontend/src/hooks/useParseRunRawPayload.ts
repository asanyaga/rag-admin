import { useEffect, useState } from 'react'
import * as parseRunsApi from '@/api/parseRuns'

interface UseParseRunRawPayloadReturn {
  rawPayload: Record<string, unknown> | null | undefined
  isLoading: boolean
  error: string | null
}

export function useParseRunRawPayload(
  parseRunId: string | null
): UseParseRunRawPayloadReturn {
  const [rawPayload, setRawPayload] = useState<
    Record<string, unknown> | null | undefined
  >(undefined)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    if (!parseRunId) {
      setRawPayload(undefined)
      setError(null)
      return
    }
    setIsLoading(true)
    setError(null)
    parseRunsApi
      .getRawPayload(parseRunId)
      .then((resp) => {
        if (cancelled) return
        setRawPayload(resp.rawPayload)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setRawPayload(undefined)
        setError(
          err instanceof Error ? err.message : 'Failed to fetch raw payload'
        )
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [parseRunId])

  return { rawPayload, isLoading, error }
}
