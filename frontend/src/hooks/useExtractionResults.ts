import { useState, useCallback, useEffect, useRef } from 'react'
import { toast } from 'sonner'
import type {
  ExtractionResult,
  ExtractionResultListItem,
  ExtractionPhase,
  RunWithParseRequest,
} from '@/types/extraction'
import type { ParseRunListItem } from '@/types/cdm'
import * as extractionApi from '@/api/extraction'
import { createParseRun, listParseRuns, getParseRun } from '@/api/parseRuns'

const POLLING_INTERVAL = 3_000
const EXTRACTION_POLLING_TIMEOUT = 5 * 60 * 1_000
const PARSE_TIMEOUT = 10 * 60 * 1_000

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function stableStringify(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${(value as unknown[]).map(stableStringify).join(',')}]`
  const obj = value as Record<string, unknown>
  const sorted = Object.keys(obj)
    .sort()
    .map((k) => `${JSON.stringify(k)}:${stableStringify(obj[k])}`)
  return `{${sorted.join(',')}}`
}

function findMatchingRun(
  runs: ParseRunListItem[],
  parser: string,
  representationKind: string,
  config: Record<string, unknown>
): ParseRunListItem | undefined {
  const target = stableStringify({ parser, ...config })
  return runs.find(
    (r) =>
      r.parser === parser &&
      r.representationKind === representationKind &&
      stableStringify(r.config) === target &&
      (r.status === 'succeeded' || r.status === 'partial')
  )
}

interface UseExtractionResultsReturn {
  results: ExtractionResultListItem[]
  selectedResult: ExtractionResult | null
  isLoading: boolean
  isLoadingResult: boolean
  error: string | null
  extractionPhase: ExtractionPhase
  phaseError: string | null
  fetchResults: () => Promise<void>
  selectResult: (resultId: string) => Promise<void>
  deleteResult: (resultId: string) => Promise<void>
  runExtractionWithParse: (
    documentId: string,
    existingParseRuns: ParseRunListItem[],
    request: RunWithParseRequest
  ) => Promise<void>
}

export function useExtractionResults(
  documentId: string | null
): UseExtractionResultsReturn {
  const [results, setResults] = useState<ExtractionResultListItem[]>([])
  const [selectedResult, setSelectedResult] = useState<ExtractionResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingResult, setIsLoadingResult] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [extractionPhase, setExtractionPhase] = useState<ExtractionPhase>('idle')
  const [phaseError, setPhaseError] = useState<string | null>(null)
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
            Date.now() - pollingStartRef.current > EXTRACTION_POLLING_TIMEOUT
          ) {
            setResults((prev) =>
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
            const updated = await extractionApi.listExtractionResults(documentId)
            setResults(updated)
            if (!updated.some((r) => r.status === 'pending')) stopPolling()
          } catch {
            stopPolling()
          }
        }, POLLING_INTERVAL)
      } else if (!hasPending) {
        stopPolling()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch extraction results')
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
      setError(err instanceof Error ? err.message : 'Failed to fetch extraction result')
    } finally {
      setIsLoadingResult(false)
    }
  }, [])

  const deleteResult = useCallback(async (resultId: string) => {
    try {
      await extractionApi.deleteExtractionResult(resultId)
      setResults((prev) => prev.filter((r) => r.id !== resultId))
      setSelectedResult((prev) => (prev?.id === resultId ? null : prev))
      toast.success('Extraction deleted')
    } catch (err) {
      toast.error('Failed to delete extraction run', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }, [])

  const runExtractionWithParse = useCallback(
    async (
      documentId: string,
      existingParseRuns: ParseRunListItem[],
      request: RunWithParseRequest
    ): Promise<void> => {
      const { parseConfig, extractionConfig } = request
      setPhaseError(null)

      const matched = findMatchingRun(
        existingParseRuns,
        parseConfig.parser,
        parseConfig.representationKind,
        parseConfig.config
      )

      let parseRunId: string

      if (matched) {
        parseRunId = matched.id
      } else {
        setExtractionPhase('parsing')
        const started = Date.now()

        try {
          await createParseRun(documentId, parseConfig.parser, {
            ...parseConfig.config,
            representation_kind: parseConfig.representationKind,
          })
        } catch {
          setExtractionPhase('failed')
          setPhaseError('Failed to start parse')
          return
        }

        let resolvedId: string | null = null
        while (resolvedId === null) {
          if (Date.now() - started > PARSE_TIMEOUT) {
            setExtractionPhase('failed')
            setPhaseError('Parse timed out')
            return
          }
          await sleep(POLLING_INTERVAL)
          const runs = await listParseRuns(documentId)
          const target = stableStringify({ parser: parseConfig.parser, ...parseConfig.config })
          const found = runs.find(
            (r) =>
              r.parser === parseConfig.parser &&
              r.representationKind === parseConfig.representationKind &&
              stableStringify(r.config) === target
          )
          if (found) resolvedId = found.id
        }

        const foundId = resolvedId as string

        for (;;) {
          if (Date.now() - started > PARSE_TIMEOUT) {
            setExtractionPhase('failed')
            setPhaseError('Parse timed out')
            return
          }
          const run = await getParseRun(foundId)
          if (run.status === 'succeeded' || run.status === 'partial') {
            parseRunId = foundId
            break
          }
          if (run.status === 'failed') {
            setExtractionPhase('failed')
            setPhaseError(run.error ?? 'Parse failed')
            return
          }
          await sleep(POLLING_INTERVAL)
        }
      }

      setExtractionPhase('extracting')
      try {
        await extractionApi.runExtraction({
          parseRunId: parseRunId!,
          extractionSchemaId: extractionConfig.extractionSchemaId,
          extractionMethod: extractionConfig.extractionMethod,
          config: extractionConfig.config,
          llmConfig: extractionConfig.llmConfig,
          userPromptTemplate: extractionConfig.userPromptTemplate,
          chunking: extractionConfig.chunking,
          preprocess: extractionConfig.preprocess,
        })
        await fetchResults()
        setExtractionPhase('done')
      } catch (err) {
        setExtractionPhase('failed')
        setPhaseError(err instanceof Error ? err.message : 'Extraction failed')
      }
    },
    [fetchResults]
  )

  useEffect(() => {
    setExtractionPhase('idle')
    setPhaseError(null)
    if (documentId) {
      fetchResults()
    } else {
      setResults([])
      setSelectedResult(null)
    }
  }, [documentId, fetchResults])

  useEffect(() => {
    return () => { stopPolling() }
  }, [stopPolling])

  return {
    results,
    selectedResult,
    isLoading,
    isLoadingResult,
    error,
    extractionPhase,
    phaseError,
    fetchResults,
    selectResult,
    deleteResult,
    runExtractionWithParse,
  }
}
