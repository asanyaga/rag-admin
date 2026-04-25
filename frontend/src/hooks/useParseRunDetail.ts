import { useEffect, useState } from 'react'
import * as parseRunsApi from '@/api/parseRuns'
import type { ParseRunListItem } from '@/types/cdm'

interface UseParseRunDetailReturn {
  run: ParseRunListItem | undefined
  isLoading: boolean
  error: string | null
}

export function useParseRunDetail(
  parseRunId: string | null
): UseParseRunDetailReturn {
  const [run, setRun] = useState<ParseRunListItem | undefined>(undefined)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    if (!parseRunId) {
      setRun(undefined)
      setError(null)
      return
    }
    setIsLoading(true)
    setError(null)
    parseRunsApi
      .getParseRun(parseRunId)
      .then((r) => {
        if (!cancelled) setRun(r)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setRun(undefined)
        setError(
          err instanceof Error ? err.message : 'Failed to fetch parse run'
        )
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [parseRunId])

  return { run, isLoading, error }
}
