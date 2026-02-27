import { useState, useCallback, useEffect, useRef } from 'react'
import type {
  Experiment,
  ExperimentDetail,
  CreateExperimentRequest,
  UpdateExperimentRequest,
} from '@/types/experiment'
import * as api from '@/api/experiments'

const POLLING_INTERVAL = 5000

// ---------------------------------------------------------------------------
// useExperiments — list + create + delete
// ---------------------------------------------------------------------------

interface UseExperimentsReturn {
  experiments: Experiment[]
  isLoading: boolean
  error: string | null
  createExperiment: (data: CreateExperimentRequest) => Promise<Experiment>
  deleteExperiment: (id: string) => Promise<void>
  refresh: () => Promise<void>
}

export function useExperiments(projectId: string | null): UseExperimentsReturn {
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!projectId) {
      setExperiments([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.listExperiments(projectId)
      setExperiments(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch experiments')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createExperiment = useCallback(
    async (data: CreateExperimentRequest): Promise<Experiment> => {
      if (!projectId) throw new Error('No project selected')
      const experiment = await api.createExperiment(projectId, data)
      setExperiments((prev) => [experiment, ...prev])
      return experiment
    },
    [projectId]
  )

  const deleteExperiment = useCallback(
    async (id: string): Promise<void> => {
      if (!projectId) throw new Error('No project selected')
      await api.deleteExperiment(projectId, id)
      setExperiments((prev) => prev.filter((e) => e.id !== id))
    },
    [projectId]
  )

  useEffect(() => {
    if (projectId) {
      refresh()
    }
  }, [projectId, refresh])

  return { experiments, isLoading, error, createExperiment, deleteExperiment, refresh }
}

// ---------------------------------------------------------------------------
// useExperimentDetail — single experiment with runs, polling while active
// ---------------------------------------------------------------------------

interface UseExperimentDetailReturn {
  experiment: ExperimentDetail | null
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
  updateExperiment: (data: UpdateExperimentRequest) => Promise<void>
}

export function useExperimentDetail(
  projectId: string | null,
  experimentId: string | null
): UseExperimentDetailReturn {
  const [experiment, setExperiment] = useState<ExperimentDetail | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<NodeJS.Timeout | null>(null)

  const refresh = useCallback(async () => {
    if (!projectId || !experimentId) return
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.getExperiment(projectId, experimentId)
      setExperiment(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch experiment')
    } finally {
      setIsLoading(false)
    }
  }, [projectId, experimentId])

  const updateExperiment = useCallback(
    async (data: UpdateExperimentRequest): Promise<void> => {
      if (!projectId || !experimentId) return
      await api.updateExperiment(projectId, experimentId, data)
      await refresh()
    },
    [projectId, experimentId, refresh]
  )

  useEffect(() => {
    if (projectId && experimentId) {
      refresh()
    }
  }, [projectId, experimentId, refresh])

  // Poll while any run is pending/running
  useEffect(() => {
    const hasActiveRun = experiment?.runs.some(
      (r) => r.status === 'pending' || r.status === 'running'
    )
    if (hasActiveRun && projectId && experimentId) {
      pollingRef.current = setInterval(async () => {
        try {
          const data = await api.getExperiment(projectId, experimentId)
          setExperiment(data)
        } catch {
          // ignore polling errors
        }
      }, POLLING_INTERVAL)
    }
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [experiment, projectId, experimentId])

  return { experiment, isLoading, error, refresh, updateExperiment }
}
