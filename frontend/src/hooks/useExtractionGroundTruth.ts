import { useState, useCallback, useEffect } from 'react'
import type {
  ExtractionGroundTruthSet,
  ExtractionGroundTruthItem,
  CreateGroundTruthSetRequest,
  UpdateGroundTruthSetRequest,
  CreateGroundTruthItemRequest,
  UpdateGroundTruthItemRequest,
} from '@/types/extractionGroundTruth'
import * as api from '@/api/extractionGroundTruth'

// ---------------------------------------------------------------------------
// useExtractionGroundTruthSets — list + CRUD for sets
// ---------------------------------------------------------------------------

interface UseGroundTruthSetsReturn {
  sets: ExtractionGroundTruthSet[]
  isLoading: boolean
  error: string | null
  fetchSets: () => Promise<void>
  createSet: (data: CreateGroundTruthSetRequest) => Promise<ExtractionGroundTruthSet>
  updateSet: (id: string, data: UpdateGroundTruthSetRequest) => Promise<ExtractionGroundTruthSet>
  deleteSet: (id: string) => Promise<void>
}

export function useExtractionGroundTruthSets(
  projectId: string | null
): UseGroundTruthSetsReturn {
  const [sets, setSets] = useState<ExtractionGroundTruthSet[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchSets = useCallback(async () => {
    if (!projectId) {
      setSets([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.listGroundTruthSets(projectId)
      setSets(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch ground truth sets')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createSet = useCallback(
    async (data: CreateGroundTruthSetRequest): Promise<ExtractionGroundTruthSet> => {
      if (!projectId) throw new Error('No project selected')
      const set = await api.createGroundTruthSet(projectId, data)
      setSets((prev) => [set, ...prev])
      return set
    },
    [projectId]
  )

  const updateSet = useCallback(
    async (id: string, data: UpdateGroundTruthSetRequest): Promise<ExtractionGroundTruthSet> => {
      const updated = await api.updateGroundTruthSet(id, data)
      setSets((prev) => prev.map((s) => (s.id === id ? updated : s)))
      return updated
    },
    []
  )

  const deleteSet = useCallback(
    async (id: string): Promise<void> => {
      await api.deleteGroundTruthSet(id)
      setSets((prev) => prev.filter((s) => s.id !== id))
    },
    []
  )

  useEffect(() => {
    if (projectId) fetchSets()
  }, [projectId, fetchSets])

  return { sets, isLoading, error, fetchSets, createSet, updateSet, deleteSet }
}

// ---------------------------------------------------------------------------
// useExtractionGroundTruthItems — list + CRUD for items in a set
// ---------------------------------------------------------------------------

interface UseGroundTruthItemsReturn {
  items: ExtractionGroundTruthItem[]
  isLoading: boolean
  error: string | null
  fetchItems: () => Promise<void>
  createItem: (data: CreateGroundTruthItemRequest) => Promise<ExtractionGroundTruthItem>
  updateItem: (id: string, data: UpdateGroundTruthItemRequest) => Promise<ExtractionGroundTruthItem>
  deleteItem: (id: string) => Promise<void>
}

export function useExtractionGroundTruthItems(
  setId: string | null
): UseGroundTruthItemsReturn {
  const [items, setItems] = useState<ExtractionGroundTruthItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchItems = useCallback(async () => {
    if (!setId) {
      setItems([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.listGroundTruthItems(setId)
      setItems(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch ground truth items')
    } finally {
      setIsLoading(false)
    }
  }, [setId])

  const createItem = useCallback(
    async (data: CreateGroundTruthItemRequest): Promise<ExtractionGroundTruthItem> => {
      if (!setId) throw new Error('No set selected')
      const item = await api.createGroundTruthItem(setId, data)
      setItems((prev) => [item, ...prev])
      return item
    },
    [setId]
  )

  const updateItem = useCallback(
    async (id: string, data: UpdateGroundTruthItemRequest): Promise<ExtractionGroundTruthItem> => {
      const updated = await api.updateGroundTruthItem(id, data)
      setItems((prev) => prev.map((i) => (i.id === id ? updated : i)))
      return updated
    },
    []
  )

  const deleteItem = useCallback(
    async (id: string): Promise<void> => {
      await api.deleteGroundTruthItem(id)
      setItems((prev) => prev.filter((i) => i.id !== id))
    },
    []
  )

  useEffect(() => {
    if (setId) fetchItems()
  }, [setId, fetchItems])

  return { items, isLoading, error, fetchItems, createItem, updateItem, deleteItem }
}
