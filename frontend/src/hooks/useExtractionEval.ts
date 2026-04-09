import { useState, useCallback, useEffect, useRef } from 'react'
import type {
  ExtractionEvalRun,
  ExtractionEvalResult,
  CreateExtractionEvalRunRequest,
} from '@/types/extractionEval'
import * as api from '@/api/extractionEval'

const POLLING_INTERVAL = 3000

// ---------------------------------------------------------------------------
// useExtractionEvalRuns — list + create + delete with polling
// ---------------------------------------------------------------------------

interface UseExtractionEvalRunsReturn {
  runs: ExtractionEvalRun[]
  isLoading: boolean
  error: string | null
  fetchRuns: () => Promise<void>
  createRun: (data: CreateExtractionEvalRunRequest) => Promise<ExtractionEvalRun>
  deleteRun: (id: string) => Promise<void>
}

export function useExtractionEvalRuns(
  projectId: string | null
): UseExtractionEvalRunsReturn {
  const [runs, setRuns] = useState<ExtractionEvalRun[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<NodeJS.Timeout | null>(null)

  const fetchRuns = useCallback(async () => {
    if (!projectId) {
      setRuns([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.listExtractionEvalRuns(projectId)
      setRuns(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch eval runs')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createRun = useCallback(
    async (data: CreateExtractionEvalRunRequest): Promise<ExtractionEvalRun> => {
      if (!projectId) throw new Error('No project selected')
      const run = await api.createExtractionEvalRun(projectId, data)
      setRuns((prev) => [run, ...prev])
      return run
    },
    [projectId]
  )

  const deleteRun = useCallback(async (id: string): Promise<void> => {
    await api.deleteExtractionEvalRun(id)
    setRuns((prev) => prev.filter((r) => r.id !== id))
  }, [])

  useEffect(() => {
    if (projectId) fetchRuns()
  }, [projectId, fetchRuns])

  // Poll while any run is pending/running
  useEffect(() => {
    const hasActive = runs.some(
      (r) => r.status === 'pending' || r.status === 'running'
    )
    if (hasActive && projectId) {
      pollingRef.current = setInterval(async () => {
        try {
          const data = await api.listExtractionEvalRuns(projectId)
          setRuns(data)
        } catch {
          // ignore polling errors
        }
      }, POLLING_INTERVAL)
    }
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [runs, projectId])

  return { runs, isLoading, error, fetchRuns, createRun, deleteRun }
}

// ---------------------------------------------------------------------------
// useExtractionEvalRunDetail — single run + results
// ---------------------------------------------------------------------------

interface UseExtractionEvalRunDetailReturn {
  run: ExtractionEvalRun | null
  results: ExtractionEvalResult[]
  isLoading: boolean
  error: string | null
  fetchRun: () => Promise<void>
  fetchResults: () => Promise<void>
}

export function useExtractionEvalRunDetail(
  runId: string | null
): UseExtractionEvalRunDetailReturn {
  const [run, setRun] = useState<ExtractionEvalRun | null>(null)
  const [results, setResults] = useState<ExtractionEvalResult[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<NodeJS.Timeout | null>(null)

  const fetchRun = useCallback(async () => {
    if (!runId) return
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.getExtractionEvalRun(runId)
      setRun(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch eval run')
    } finally {
      setIsLoading(false)
    }
  }, [runId])

  const fetchResults = useCallback(async () => {
    if (!runId) return
    try {
      const data = await api.getExtractionEvalRunResults(runId)
      setResults(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch results')
    }
  }, [runId])

  useEffect(() => {
    // Clear stale data from previous run before fetching
    setRun(null)
    setResults([])
    setError(null)
    if (runId) {
      fetchRun()
      fetchResults()
    }
  }, [runId, fetchRun, fetchResults])

  // Poll while pending/running
  useEffect(() => {
    if (run && (run.status === 'pending' || run.status === 'running') && runId) {
      pollingRef.current = setInterval(async () => {
        try {
          const runData = await api.getExtractionEvalRun(runId)
          setRun(runData)
          if (runData.status === 'completed' || runData.status === 'failed') {
            const resultData = await api.getExtractionEvalRunResults(runId)
            setResults(resultData)
          }
        } catch {
          // ignore
        }
      }, POLLING_INTERVAL)
    }
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [run, runId])

  return { run, results, isLoading, error, fetchRun, fetchResults }
}
