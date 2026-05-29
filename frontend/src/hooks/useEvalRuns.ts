import { useState, useCallback, useEffect, useRef } from 'react'
import type {
  EvalRun,
  CreateEvalRunRequest,
  EvalRunResult,
  EvalRunProgress,
  RunComparison,
} from '@/types/eval-run'
import * as api from '@/api/eval-runs'

const POLLING_INTERVAL = 3000

// ---------------------------------------------------------------------------
// useEvalRuns — list + create + delete with polling
// ---------------------------------------------------------------------------

interface UseEvalRunsReturn {
  runs: EvalRun[]
  isLoading: boolean
  error: string | null
  fetchRuns: () => Promise<void>
  createRun: (data: CreateEvalRunRequest) => Promise<EvalRun>
  deleteRun: (id: string) => Promise<void>
}

export function useEvalRuns(projectId: string | null): UseEvalRunsReturn {
  const [runs, setRuns] = useState<EvalRun[]>([])
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
      const data = await api.listEvalRuns(projectId)
      setRuns(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch eval runs')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createRun = useCallback(
    async (data: CreateEvalRunRequest): Promise<EvalRun> => {
      if (!projectId) throw new Error('No project selected')
      const run = await api.createEvalRun(projectId, data)
      setRuns((prev) => [run, ...prev])
      return run
    },
    [projectId]
  )

  const deleteRun = useCallback(
    async (id: string): Promise<void> => {
      if (!projectId) throw new Error('No project selected')
      await api.deleteEvalRun(projectId, id)
      setRuns((prev) => prev.filter((r) => r.id !== id))
    },
    [projectId]
  )

  useEffect(() => {
    if (projectId) {
      fetchRuns()
    }
  }, [projectId, fetchRuns])

  // Poll while any run is pending/running
  useEffect(() => {
    const hasActive = runs.some(
      (r) => r.status === 'pending' || r.status === 'running'
    )
    if (hasActive && projectId) {
      pollingRef.current = setInterval(async () => {
        try {
          const data = await api.listEvalRuns(projectId)
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
// useEvalRunDetail — single run + results with polling + progress
// ---------------------------------------------------------------------------

interface UseEvalRunDetailReturn {
  run: EvalRun | null
  results: EvalRunResult[]
  progress: EvalRunProgress | null
  isLoading: boolean
  error: string | null
  fetchRun: () => Promise<void>
  fetchResults: (filter?: string) => Promise<void>
}

export function useEvalRunDetail(
  projectId: string | null,
  runId: string | null
): UseEvalRunDetailReturn {
  const [run, setRun] = useState<EvalRun | null>(null)
  const [results, setResults] = useState<EvalRunResult[]>([])
  const [progress, setProgress] = useState<EvalRunProgress | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<NodeJS.Timeout | null>(null)

  const fetchRun = useCallback(async () => {
    if (!projectId || !runId) return
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.getEvalRun(projectId, runId)
      setRun(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch eval run')
    } finally {
      setIsLoading(false)
    }
  }, [projectId, runId])

  const fetchResults = useCallback(async (filter?: string) => {
    if (!projectId || !runId) return
    try {
      const data = await api.getEvalRunResults(projectId, runId, filter)
      setResults(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch results')
    }
  }, [projectId, runId])

  useEffect(() => {
    if (projectId && runId) {
      fetchRun()
      fetchResults()
    }
  }, [projectId, runId, fetchRun, fetchResults])

  // Poll while pending/running — also fetch progress
  useEffect(() => {
    if (run && (run.status === 'pending' || run.status === 'running') && projectId && runId) {
      pollingRef.current = setInterval(async () => {
        try {
          const [runData, progressData] = await Promise.all([
            api.getEvalRun(projectId, runId),
            api.getEvalRunProgress(projectId, runId),
          ])
          setRun(runData)
          setProgress(progressData)
          if (
            runData.status === 'completed' ||
            runData.status === 'failed' ||
            runData.status === 'partial_failure'
          ) {
            const resultData = await api.getEvalRunResults(projectId, runId)
            setResults(resultData)
            setProgress(null)
          }
        } catch {
          // ignore polling errors
        }
      }, POLLING_INTERVAL)
    }
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [run, projectId, runId])

  return { run, results, progress, isLoading, error, fetchRun, fetchResults }
}

// ---------------------------------------------------------------------------
// useRunComparison
// ---------------------------------------------------------------------------

interface UseRunComparisonReturn {
  comparison: RunComparison | null
  isLoading: boolean
  error: string | null
}

export function useRunComparison(
  projectId: string | null,
  runId1: string | null,
  runId2: string | null
): UseRunComparisonReturn {
  const [comparison, setComparison] = useState<RunComparison | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId || !runId1 || !runId2) return
    let cancelled = false

    const load = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const data = await api.compareRuns(projectId, runId1, runId2)
        if (!cancelled) setComparison(data)
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : 'Failed to compare runs')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [projectId, runId1, runId2])

  return { comparison, isLoading, error }
}

