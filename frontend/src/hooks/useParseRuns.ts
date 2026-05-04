import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as parseRunsApi from '@/api/parseRuns'
import type {
  ParsedDocumentDetail,
  ParseRunListItem,
  ParseRunStatus,
} from '@/types/cdm'

const POLLING_INTERVAL_MS = 5000

const TERMINAL: ReadonlyArray<ParseRunStatus> = [
  'succeeded',
  'failed',
  'partial',
]

function isTerminal(status: ParseRunStatus): boolean {
  return TERMINAL.includes(status)
}

interface UseParseRunsReturn {
  parseRuns: ParseRunListItem[]
  selectedRun: ParseRunListItem | undefined
  parsedDocument: ParsedDocumentDetail | undefined
  isLoading: boolean
  isLoadingContent: boolean
  error: string | null
  selectRun: (id: string) => void
  refresh: () => void
}

function pickInitialRun(
  runs: ParseRunListItem[]
): ParseRunListItem | undefined {
  if (runs.length === 0) return undefined
  // Backend returns newest-first. Prefer succeeded/partial, else newest of any.
  return (
    runs.find((r) => r.status === 'succeeded' || r.status === 'partial') ??
    runs[0]
  )
}

export function useParseRuns(
  documentId: string | null
): UseParseRunsReturn {
  const [parseRuns, setParseRuns] = useState<ParseRunListItem[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [parsedDocument, setParsedDocument] = useState<
    ParsedDocumentDetail | undefined
  >(undefined)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingContent, setIsLoadingContent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // True for a short window after a manual refresh to keep polling alive even
  // when all existing runs are already terminal (new run may not exist yet).
  const [forcePolling, setForcePolling] = useState(false)
  const forcePollingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const fetchList = useCallback(
    async (
      docId: string,
      { silent = false }: { silent?: boolean } = {}
    ): Promise<ParseRunListItem[]> => {
      if (!silent) {
        setIsLoading(true)
        setError(null)
      }
      try {
        const runs = await parseRunsApi.listParseRuns(docId)
        setParseRuns(runs)
        return runs
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to fetch parse runs'
        )
        return []
      } finally {
        if (!silent) setIsLoading(false)
      }
    },
    []
  )

  // Initial fetch + auto-select on documentId change.
  useEffect(() => {
    let cancelled = false
    if (!documentId) {
      setParseRuns([])
      setSelectedRunId(null)
      setParsedDocument(undefined)
      stopPolling()
      return
    }
    void fetchList(documentId).then((runs) => {
      if (cancelled) return
      const initial = pickInitialRun(runs)
      setSelectedRunId(initial?.id ?? null)
    })
    return () => {
      cancelled = true
    }
  }, [documentId, fetchList, stopPolling])

  // Poll while any run is non-terminal, or while forcePolling is active.
  useEffect(() => {
    if (!documentId) return
    const hasActive = parseRuns.some((r) => !isTerminal(r.status))
    if (!hasActive && !forcePolling) {
      stopPolling()
      return
    }
    if (pollingRef.current !== null) return
    pollingRef.current = setInterval(() => {
      void fetchList(documentId, { silent: true })
    }, POLLING_INTERVAL_MS)
    return () => {
      stopPolling()
    }
  }, [documentId, parseRuns, fetchList, stopPolling, forcePolling])

  // Cleanup on unmount.
  useEffect(() => {
    return () => stopPolling()
  }, [stopPolling])

  // Fetch ParsedDocument when selection changes (skip for failed runs).
  useEffect(() => {
    let cancelled = false
    if (selectedRunId === null) {
      setParsedDocument(undefined)
      return
    }
    const run = parseRuns.find((r) => r.id === selectedRunId)
    if (!run) {
      setParsedDocument(undefined)
      return
    }
    if (run.status === 'failed' || run.status === 'pending' || run.status === 'running') {
      setParsedDocument(undefined)
      return
    }
    setIsLoadingContent(true)
    void parseRunsApi
      .getParsedDocument(selectedRunId)
      .then((doc) => {
        if (!cancelled) setParsedDocument(doc)
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : 'Failed to fetch parsed document'
          )
          setParsedDocument(undefined)
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoadingContent(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedRunId, parseRuns])

  const selectRun = useCallback((id: string) => {
    setSelectedRunId(id)
  }, [])

  // Called after triggering a reparse — fetches immediately and holds polling
  // open for 30 s so the new run (which may not exist yet) is picked up.
  const refresh = useCallback(() => {
    if (!documentId) return
    void fetchList(documentId, { silent: true })
    setForcePolling(true)
    if (forcePollingTimerRef.current !== null) {
      clearTimeout(forcePollingTimerRef.current)
    }
    forcePollingTimerRef.current = setTimeout(() => {
      setForcePolling(false)
      forcePollingTimerRef.current = null
    }, 30_000)
  }, [documentId, fetchList])

  const selectedRun = useMemo(
    () => parseRuns.find((r) => r.id === selectedRunId),
    [parseRuns, selectedRunId]
  )

  return {
    parseRuns,
    selectedRun,
    parsedDocument,
    isLoading,
    isLoadingContent,
    error,
    selectRun,
    refresh,
  }
}
