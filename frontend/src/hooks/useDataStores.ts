// frontend/src/hooks/useDataStores.ts
import { useState, useEffect, useCallback } from 'react'
import * as dataStoresApi from '@/api/dataStores'
import type { DataStore, DataStoreCreate, DataStoreUpdate } from '@/types/dataStore'

export interface UseDataStoresReturn {
  dataStores: DataStore[]
  isLoading: boolean
  error: string | null
  fetchDataStores: () => Promise<void>
  createDataStore: (data: DataStoreCreate) => Promise<DataStore>
  updateDataStore: (storeId: string, data: DataStoreUpdate) => Promise<DataStore>
  deleteDataStore: (storeId: string) => Promise<void>
}

export function useDataStores(projectId: string | null): UseDataStoresReturn {
  const [dataStores, setDataStores] = useState<DataStore[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchDataStores = useCallback(async () => {
    if (!projectId) {
      setDataStores([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await dataStoresApi.listDataStores(projectId)
      setDataStores(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data stores')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createDataStore = useCallback(
    async (data: DataStoreCreate): Promise<DataStore> => {
      if (!projectId) throw new Error('No project selected')
      try {
        const store = await dataStoresApi.createDataStore(projectId, data)
        setDataStores((prev) => [store, ...prev])
        return store
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to create data store'
        setError(msg)
        throw err
      }
    },
    [projectId]
  )

  const updateDataStore = useCallback(
    async (storeId: string, data: DataStoreUpdate): Promise<DataStore> => {
      if (!projectId) throw new Error('No project selected')
      try {
        const updated = await dataStoresApi.updateDataStore(projectId, storeId, data)
        setDataStores((prev) =>
          prev.map((s) => (s.id === storeId ? updated : s))
        )
        return updated
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to update data store'
        setError(msg)
        throw err
      }
    },
    [projectId]
  )

  const deleteDataStore = useCallback(
    async (storeId: string): Promise<void> => {
      if (!projectId) throw new Error('No project selected')
      try {
        await dataStoresApi.deleteDataStore(projectId, storeId)
        setDataStores((prev) => prev.filter((s) => s.id !== storeId))
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to delete data store'
        setError(msg)
        throw err
      }
    },
    [projectId]
  )

  useEffect(() => {
    if (projectId) {
      fetchDataStores()
    }
  }, [projectId, fetchDataStores])

  return {
    dataStores,
    isLoading,
    error,
    fetchDataStores,
    createDataStore,
    updateDataStore,
    deleteDataStore,
  }
}
