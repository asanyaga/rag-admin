import { useState, useCallback, useEffect, useRef } from 'react'
import type {
  ParserEvalCase, ParserEvalCaseDetail, ParserEvalRun, ParserEvalResult,
  CreateCaseRequest, CreateRunRequest, BootstrapTableRequest,
} from '@/types/parserEval'
import * as api from '@/api/parserEval'

const POLLING_INTERVAL = 3000

export function useParserEvalCases(projectId: string | null) {
  const [cases, setCases] = useState<ParserEvalCase[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchCases = useCallback(async () => {
    if (!projectId) { setCases([]); return }
    setIsLoading(true); setError(null)
    try {
      setCases(await api.listCases(projectId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cases')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createCase = useCallback(async (data: CreateCaseRequest): Promise<ParserEvalCase> => {
    if (!projectId) throw new Error('No project selected')
    const created = await api.createCase(projectId, data)
    setCases((prev) => [created, ...prev])
    return created
  }, [projectId])

  const bootstrapTableCase = useCallback(
    async (data: BootstrapTableRequest): Promise<ParserEvalCaseDetail> => {
      if (!projectId) throw new Error('No project selected')
      const created = await api.bootstrapTableCase(projectId, data)
      setCases((prev) => [created, ...prev])
      return created
    }, [projectId])

  const deleteCase = useCallback(async (caseId: string): Promise<void> => {
    if (!projectId) throw new Error('No project selected')
    await api.deleteCase(projectId, caseId)
    setCases((prev) => prev.filter((c) => c.id !== caseId))
  }, [projectId])

  useEffect(() => { if (projectId) fetchCases() }, [projectId, fetchCases])

  return { cases, isLoading, error, fetchCases, createCase, bootstrapTableCase, deleteCase }
}

export function useParserEvalRuns(projectId: string | null) {
  const [runs, setRuns] = useState<ParserEvalRun[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchRuns = useCallback(async () => {
    if (!projectId) { setRuns([]); return }
    setIsLoading(true); setError(null)
    try {
      setRuns(await api.listRuns(projectId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load runs')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createRun = useCallback(async (data: CreateRunRequest): Promise<ParserEvalRun> => {
    if (!projectId) throw new Error('No project selected')
    const run = await api.createRun(projectId, data)
    setRuns((prev) => [run, ...prev])
    return run
  }, [projectId])

  useEffect(() => { if (projectId) fetchRuns() }, [projectId, fetchRuns])

  useEffect(() => {
    const active = runs.some((r) => r.status === 'pending' || r.status === 'running')
    if (active && projectId) {
      pollingRef.current = setInterval(async () => {
        try { setRuns(await api.listRuns(projectId)) } catch { /* ignore */ }
      }, POLLING_INTERVAL)
    }
    return () => { if (pollingRef.current) clearInterval(pollingRef.current) }
  }, [runs, projectId])

  return { runs, isLoading, error, fetchRuns, createRun }
}

export function useParserEvalRunDetail(projectId: string | null, runId: string | null) {
  const [run, setRun] = useState<ParserEvalRun | null>(null)
  const [results, setResults] = useState<ParserEvalResult[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!projectId || !runId) { setRun(null); setResults([]); return }
    let cancelled = false
    ;(async () => {
      setIsLoading(true); setError(null)
      try {
        const runData = await api.getRun(projectId, runId)
        if (cancelled) return
        setRun(runData)
        if (runData.status === 'completed') {
          setResults(await api.getRunResults(projectId, runId))
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load run')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [projectId, runId])

  useEffect(() => {
    if (run && (run.status === 'pending' || run.status === 'running') && projectId && runId) {
      pollingRef.current = setInterval(async () => {
        try {
          const runData = await api.getRun(projectId, runId)
          setRun(runData)
          if (runData.status === 'completed' || runData.status === 'failed') {
            setResults(await api.getRunResults(projectId, runId))
          }
        } catch { /* ignore */ }
      }, POLLING_INTERVAL)
    }
    return () => { if (pollingRef.current) clearInterval(pollingRef.current) }
  }, [run, projectId, runId])

  return { run, results, isLoading, error }
}

export function useParserEvalCase(projectId: string | null, caseId: string | null) {
  const [caseDetail, setCaseDetail] = useState<ParserEvalCaseDetail | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!projectId || !caseId) { setCaseDetail(null); return }
    setIsLoading(true); setError(null)
    try {
      setCaseDetail(await api.getCase(projectId, caseId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load case')
    } finally {
      setIsLoading(false)
    }
  }, [projectId, caseId])

  useEffect(() => { load() }, [load])

  const verify = useCallback(async () => {
    if (!projectId || !caseId) return
    setCaseDetail(await api.updateCaseReview(projectId, caseId, 'verified'))
  }, [projectId, caseId])

  const reject = useCallback(async () => {
    if (!projectId || !caseId) return
    await api.deleteCase(projectId, caseId)
  }, [projectId, caseId])

  const saveTables = useCallback(
    async (tables: { page: number; html: string }[], opts?: { verify?: boolean }) => {
      if (!projectId || !caseId) return
      let updated = await api.replaceCaseTables(projectId, caseId, tables)
      if (opts?.verify) updated = await api.updateCaseReview(projectId, caseId, 'verified')
      setCaseDetail(updated)
    }, [projectId, caseId])

  return { caseDetail, isLoading, error, verify, reject, saveTables }
}
