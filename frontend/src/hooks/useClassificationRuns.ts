// frontend/src/hooks/useClassificationRuns.ts
import { useCallback, useEffect, useRef, useState } from 'react'
import * as classificationApi from '@/api/classification'
import type { AnnotatedBlock, ClassificationRun, ClassificationRunStatus } from '@/types/classification'

const POLL_MS = 5000
const TERMINAL: ReadonlyArray<ClassificationRunStatus> = ['completed', 'failed']

function isTerminal(status: ClassificationRunStatus): boolean {
  return TERMINAL.includes(status)
}

interface UseClassificationRunsReturn {
  runs: ClassificationRun[]
  isLoading: boolean
  error: string | null
  refresh: () => void
  deleteRun: (runId: string) => Promise<void>
}

export function useClassificationRuns(projectId: string | null): UseClassificationRunsReturn {
  const [runs, setRuns] = useState<ClassificationRun[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forcePolling, setForcePolling] = useState(false)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const forceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const fetchList = useCallback(
    async (id: string, silent = false) => {
      if (!silent) { setIsLoading(true); setError(null) }
      try {
        const data = await classificationApi.listAllClassificationRuns(id)
        setRuns(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch classification runs')
      } finally {
        if (!silent) setIsLoading(false)
      }
    },
    [],
  )

  useEffect(() => {
    if (!projectId) { setRuns([]); stopPolling(); return }
    void fetchList(projectId)
  }, [projectId, fetchList, stopPolling])

  useEffect(() => {
    if (!projectId) return
    const hasActive = runs.some((r) => !isTerminal(r.status))
    if (!hasActive && !forcePolling) { stopPolling(); return }
    if (pollingRef.current !== null) return
    pollingRef.current = setInterval(() => void fetchList(projectId, true), POLL_MS)
    return () => stopPolling()
  }, [projectId, runs, fetchList, stopPolling, forcePolling])

  useEffect(() => () => stopPolling(), [stopPolling])

  const refresh = useCallback(() => {
    if (!projectId) return
    void fetchList(projectId, true)
    setForcePolling(true)
    if (forceTimerRef.current !== null) clearTimeout(forceTimerRef.current)
    forceTimerRef.current = setTimeout(() => {
      setForcePolling(false)
      forceTimerRef.current = null
    }, 30_000)
  }, [projectId, fetchList])

  const deleteRun = useCallback(
    async (runId: string) => {
      await classificationApi.deleteClassificationRun(runId)
      if (projectId) void fetchList(projectId, true)
    },
    [projectId, fetchList],
  )

  return { runs, isLoading, error, refresh, deleteRun }
}

interface UseClassificationRunDetailReturn {
  run: ClassificationRun | null
  isLoading: boolean
  error: string | null
  refresh: () => void
}

export function useClassificationRunDetail(runId: string | null): UseClassificationRunDetailReturn {
  const [run, setRun] = useState<ClassificationRun | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) { clearInterval(pollingRef.current); pollingRef.current = null }
  }, [])

  const fetchRun = useCallback(async (id: string, silent = false) => {
    if (!silent) { setIsLoading(true); setError(null) }
    try {
      const data = await classificationApi.getClassificationRun(id)
      setRun(data)
      return data
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch run')
      return null
    } finally {
      if (!silent) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!runId) { setRun(null); stopPolling(); return }
    void fetchRun(runId)
  }, [runId, fetchRun, stopPolling])

  useEffect(() => {
    if (!runId) return
    if (run && isTerminal(run.status)) { stopPolling(); return }
    if (pollingRef.current !== null) return
    pollingRef.current = setInterval(() => void fetchRun(runId, true), POLL_MS)
    return () => stopPolling()
  }, [runId, run, fetchRun, stopPolling])

  useEffect(() => () => stopPolling(), [stopPolling])

  const refresh = useCallback(() => {
    if (runId) void fetchRun(runId, true)
  }, [runId, fetchRun])

  return { run, isLoading, error, refresh }
}

interface UseClassificationRunBlocksReturn {
  blocks: AnnotatedBlock[]
  isLoading: boolean
  error: string | null
}

export function useClassificationRunBlocks(runId: string | null): UseClassificationRunBlocksReturn {
  const [blocks, setBlocks] = useState<AnnotatedBlock[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) return
    setIsLoading(true)
    setError(null)
    classificationApi.getClassificationRunBlocks(runId)
      .then((data) => { setBlocks(data) })
      .catch((err) => { setError(err instanceof Error ? err.message : 'Failed to fetch blocks') })
      .finally(() => { setIsLoading(false) })
  }, [runId])

  return { blocks, isLoading, error }
}
