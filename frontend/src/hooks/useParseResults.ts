import { useState, useCallback, useEffect, useRef } from 'react'
import type {
  ParseResult,
  ParseResultListItem,
  ParseConfig,
} from '@/types/parsing'
import * as parsingApi from '@/api/parsing'

interface UseParseResultsReturn {
  parseResults: ParseResultListItem[]
  selectedResult: ParseResult | null
  isLoading: boolean
  isLoadingResult: boolean
  error: string | null
  fetchParseResults: () => Promise<void>
  selectParseResult: (resultId: string) => Promise<void>
  reparseDocument: (
    parserType: string,
    config?: ParseConfig
  ) => Promise<ParseResult>
}

const POLLING_INTERVAL = 3000
const POLLING_TIMEOUT = 5 * 60 * 1000 // Stop polling after 5 minutes

export function useParseResults(
  documentId: string | null
): UseParseResultsReturn {
  const [parseResults, setParseResults] = useState<ParseResultListItem[]>([])
  const [selectedResult, setSelectedResult] = useState<ParseResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingResult, setIsLoadingResult] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<NodeJS.Timeout | null>(null)
  const pollingStartRef = useRef<number | null>(null)

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
    pollingStartRef.current = null
  }, [])

  const fetchParseResults = useCallback(async () => {
    if (!documentId) {
      setParseResults([])
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      const results = await parsingApi.listParseResults(documentId)
      setParseResults(results)

      // Start polling if any results are pending
      const hasPending = results.some((r) => r.status === 'pending')
      if (hasPending && !pollingRef.current) {
        pollingStartRef.current = Date.now()
        pollingRef.current = setInterval(async () => {
          // Check timeout
          if (
            pollingStartRef.current &&
            Date.now() - pollingStartRef.current > POLLING_TIMEOUT
          ) {
            setParseResults((prev) =>
              prev.map((r) =>
                r.status === 'pending'
                  ? { ...r, status: 'failed' as const, statusMessage: 'Processing timeout' }
                  : r
              )
            )
            stopPolling()
            return
          }
          try {
            const updated = await parsingApi.listParseResults(documentId)
            setParseResults(updated)

            const stillPending = updated.some((r) => r.status === 'pending')
            if (!stillPending) {
              stopPolling()
            }
          } catch {
            stopPolling()
          }
        }, POLLING_INTERVAL)
      } else if (!hasPending) {
        stopPolling()
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch parse results'
      )
    } finally {
      setIsLoading(false)
    }
  }, [documentId, stopPolling])

  const selectParseResult = useCallback(async (resultId: string) => {
    setIsLoadingResult(true)
    setError(null)
    try {
      const result = await parsingApi.getParseResult(resultId)
      setSelectedResult(result)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch parse result'
      )
    } finally {
      setIsLoadingResult(false)
    }
  }, [])

  const reparseDocument = useCallback(
    async (parserType: string, config?: ParseConfig): Promise<ParseResult> => {
      if (!documentId) throw new Error('No document selected')

      const result = await parsingApi.reparseDocument(
        documentId,
        parserType,
        config
      )

      // Refresh list to include new pending result
      await fetchParseResults()
      return result
    },
    [documentId, fetchParseResults]
  )

  useEffect(() => {
    if (documentId) {
      fetchParseResults()
    } else {
      setParseResults([])
      setSelectedResult(null)
    }
  }, [documentId, fetchParseResults])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPolling()
    }
  }, [stopPolling])

  return {
    parseResults,
    selectedResult,
    isLoading,
    isLoadingResult,
    error,
    fetchParseResults,
    selectParseResult,
    reparseDocument,
  }
}
