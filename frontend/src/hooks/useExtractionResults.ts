import { useState, useCallback, useEffect, useRef } from 'react'
import type {
  ExtractionResult,
  ExtractionResultListItem,
  RunExtractionRequest,
} from '@/types/extraction'
import * as extractionApi from '@/api/extraction'

interface UseExtractionResultsReturn {
  results: ExtractionResultListItem[]
  selectedResult: ExtractionResult | null
  isLoading: boolean
  isLoadingResult: boolean
  error: string | null
  fetchResults: () => Promise<void>
  selectResult: (resultId: string) => Promise<void>
  runExtraction: (request: RunExtractionRequest) => Promise<ExtractionResult>
}

const POLLING_INTERVAL = 3000
const POLLING_TIMEOUT = 5 * 60 * 1000

export function useExtractionResults(
  documentId: string | null
): UseExtractionResultsReturn {
  const [results, setResults] = useState<ExtractionResultListItem[]>([])
  const [selectedResult, setSelectedResult] = useState<ExtractionResult | null>(
    null
  )
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

  const fetchResults = useCallback(async () => {
    if (!documentId) {
      setResults([])
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      const data = await extractionApi.listExtractionResults(documentId)
      setResults(data)

      const hasPending = data.some((r) => r.status === 'pending')
      if (hasPending && !pollingRef.current) {
        pollingStartRef.current = Date.now()
        pollingRef.current = setInterval(async () => {
          if (
            pollingStartRef.current &&
            Date.now() - pollingStartRef.current > POLLING_TIMEOUT
          ) {
            setResults((prev) =>
              prev.map((r) =>
                r.status === 'pending'
                  ? {
                      ...r,
                      status: 'failed' as const,
                      statusMessage: 'Processing timeout',
                    }
                  : r
              )
            )
            stopPolling()
            return
          }
          try {
            const updated = await extractionApi.listExtractionResults(
              documentId
            )
            setResults(updated)

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
        err instanceof Error
          ? err.message
          : 'Failed to fetch extraction results'
      )
    } finally {
      setIsLoading(false)
    }
  }, [documentId, stopPolling])

  const selectResult = useCallback(async (resultId: string) => {
    setIsLoadingResult(true)
    setError(null)
    try {
      const result = await extractionApi.getExtractionResult(resultId)
      setSelectedResult(result)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to fetch extraction result'
      )
    } finally {
      setIsLoadingResult(false)
    }
  }, [])

  const runExtraction = useCallback(
    async (request: RunExtractionRequest): Promise<ExtractionResult> => {
      const result = await extractionApi.runExtraction(request)
      await fetchResults()
      return result
    },
    [fetchResults]
  )

  useEffect(() => {
    if (documentId) {
      fetchResults()
    } else {
      setResults([])
      setSelectedResult(null)
    }
  }, [documentId, fetchResults])

  useEffect(() => {
    return () => {
      stopPolling()
    }
  }, [stopPolling])

  return {
    results,
    selectedResult,
    isLoading,
    isLoadingResult,
    error,
    fetchResults,
    selectResult,
    runExtraction,
  }
}
