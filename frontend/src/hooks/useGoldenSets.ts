import { useState, useCallback, useEffect } from 'react'
import type {
  GoldenSet,
  GoldenSetDetail,
  GoldenSetCreate,
  GoldenSetUpdate,
  QueryCreate,
  QueryUpdate,
  SourceCreate,
  GoldenSetQuery,
} from '@/types/golden-set'
import * as api from '@/api/golden-sets'

interface UseGoldenSetsReturn {
  goldenSets: GoldenSet[]
  isLoading: boolean
  error: string | null
  fetchGoldenSets: () => Promise<void>
  createGoldenSet: (data: GoldenSetCreate) => Promise<GoldenSet>
  updateGoldenSet: (id: string, data: GoldenSetUpdate) => Promise<GoldenSet>
  deleteGoldenSet: (id: string) => Promise<void>
}

export function useGoldenSets(projectId: string | null): UseGoldenSetsReturn {
  const [goldenSets, setGoldenSets] = useState<GoldenSet[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchGoldenSets = useCallback(async () => {
    if (!projectId) {
      setGoldenSets([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.listGoldenSets(projectId)
      setGoldenSets(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch golden sets')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createGoldenSet = useCallback(
    async (data: GoldenSetCreate): Promise<GoldenSet> => {
      if (!projectId) throw new Error('No project selected')
      const gs = await api.createGoldenSet(projectId, data)
      setGoldenSets((prev) => [gs, ...prev])
      return gs
    },
    [projectId]
  )

  const updateGoldenSet = useCallback(
    async (id: string, data: GoldenSetUpdate): Promise<GoldenSet> => {
      if (!projectId) throw new Error('No project selected')
      const gs = await api.updateGoldenSet(projectId, id, data)
      setGoldenSets((prev) => prev.map((g) => (g.id === id ? gs : g)))
      return gs
    },
    [projectId]
  )

  const deleteGoldenSet = useCallback(
    async (id: string): Promise<void> => {
      if (!projectId) throw new Error('No project selected')
      await api.deleteGoldenSet(projectId, id)
      setGoldenSets((prev) => prev.filter((g) => g.id !== id))
    },
    [projectId]
  )

  useEffect(() => {
    if (projectId) {
      fetchGoldenSets()
    }
  }, [projectId, fetchGoldenSets])

  return {
    goldenSets,
    isLoading,
    error,
    fetchGoldenSets,
    createGoldenSet,
    updateGoldenSet,
    deleteGoldenSet,
  }
}

// ---------------------------------------------------------------------------
// Golden Set Detail hook
// ---------------------------------------------------------------------------

interface UseGoldenSetDetailReturn {
  goldenSet: GoldenSetDetail | null
  selectedQueryId: string | null
  selectedQuery: GoldenSetQuery | null
  isLoading: boolean
  error: string | null
  setSelectedQueryId: (id: string | null) => void
  fetchGoldenSet: () => Promise<void>
  addQuery: (data: QueryCreate) => Promise<void>
  updateQuery: (queryId: string, data: QueryUpdate) => Promise<void>
  deleteQuery: (queryId: string) => Promise<void>
  addSource: (queryId: string, data: SourceCreate) => Promise<void>
  deleteSource: (queryId: string, sourceId: string) => Promise<void>
}

export function useGoldenSetDetail(
  projectId: string | null,
  goldenSetId: string | null
): UseGoldenSetDetailReturn {
  const [goldenSet, setGoldenSet] = useState<GoldenSetDetail | null>(null)
  const [selectedQueryId, setSelectedQueryId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedQuery =
    goldenSet?.queries.find((q) => q.id === selectedQueryId) ?? null

  const fetchGoldenSet = useCallback(async () => {
    if (!projectId || !goldenSetId) return
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.getGoldenSet(projectId, goldenSetId)
      setGoldenSet(data)
      // Auto-select first query if none selected
      if (!selectedQueryId && data.queries.length > 0) {
        setSelectedQueryId(data.queries[0].id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch golden set')
    } finally {
      setIsLoading(false)
    }
  }, [projectId, goldenSetId, selectedQueryId])

  const addQuery = useCallback(
    async (data: QueryCreate) => {
      if (!projectId || !goldenSetId) return
      const query = await api.addQuery(projectId, goldenSetId, data)
      setGoldenSet((prev) => {
        if (!prev) return prev
        return { ...prev, queries: [...prev.queries, query], queryCount: prev.queryCount + 1 }
      })
      setSelectedQueryId(query.id)
    },
    [projectId, goldenSetId]
  )

  const updateQuery = useCallback(
    async (queryId: string, data: QueryUpdate) => {
      if (!projectId || !goldenSetId) return
      const updated = await api.updateQuery(projectId, goldenSetId, queryId, data)
      setGoldenSet((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          queries: prev.queries.map((q) => (q.id === queryId ? updated : q)),
        }
      })
    },
    [projectId, goldenSetId]
  )

  const deleteQuery = useCallback(
    async (queryId: string) => {
      if (!projectId || !goldenSetId) return
      await api.deleteQuery(projectId, goldenSetId, queryId)
      setGoldenSet((prev) => {
        if (!prev) return prev
        const queries = prev.queries.filter((q) => q.id !== queryId)
        return { ...prev, queries, queryCount: prev.queryCount - 1 }
      })
      if (selectedQueryId === queryId) {
        setSelectedQueryId(null)
      }
    },
    [projectId, goldenSetId, selectedQueryId]
  )

  const addSource = useCallback(
    async (queryId: string, data: SourceCreate) => {
      if (!projectId || !goldenSetId) return
      const source = await api.addSource(projectId, goldenSetId, queryId, data)
      setGoldenSet((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          queries: prev.queries.map((q) =>
            q.id === queryId ? { ...q, sources: [...q.sources, source] } : q
          ),
        }
      })
    },
    [projectId, goldenSetId]
  )

  const deleteSource = useCallback(
    async (queryId: string, sourceId: string) => {
      if (!projectId || !goldenSetId) return
      await api.deleteSource(projectId, goldenSetId, queryId, sourceId)
      setGoldenSet((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          queries: prev.queries.map((q) =>
            q.id === queryId
              ? { ...q, sources: q.sources.filter((s) => s.id !== sourceId) }
              : q
          ),
        }
      })
    },
    [projectId, goldenSetId]
  )

  useEffect(() => {
    if (projectId && goldenSetId) {
      fetchGoldenSet()
    }
  }, [projectId, goldenSetId, fetchGoldenSet])

  return {
    goldenSet,
    selectedQueryId,
    selectedQuery,
    isLoading,
    error,
    setSelectedQueryId,
    fetchGoldenSet,
    addQuery,
    updateQuery,
    deleteQuery,
    addSource,
    deleteSource,
  }
}
