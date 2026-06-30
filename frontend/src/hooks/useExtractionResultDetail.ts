import { useState, useEffect, useRef, useCallback } from 'react'
import type { ExtractionResult } from '@/types/extraction'
import { getExtractionResult } from '@/api/extraction'

const POLL_INTERVAL = 3_000

export function useExtractionResultDetail(resultId: string | null): {
  result: ExtractionResult | null
  isLoading: boolean
  error: string | null
} {
  const [result, setResult] = useState<ExtractionResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!resultId) {
      setResult(null)
      return
    }
    setIsLoading(true)
    setError(null)
    let cancelled = false

    getExtractionResult(resultId)
      .then((data) => {
        if (cancelled) return
        setResult(data)
        setIsLoading(false)
        if (data.status === 'pending') {
          intervalRef.current = setInterval(() => {
            void getExtractionResult(resultId)
              .then((updated) => {
                if (cancelled) return
                setResult(updated)
                if (updated.status !== 'pending') stopPolling()
              })
              .catch(() => { stopPolling() })
          }, POLL_INTERVAL)
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load result')
        setIsLoading(false)
      })

    return () => {
      cancelled = true
      stopPolling()
    }
  }, [resultId, stopPolling])

  return { result, isLoading, error }
}
