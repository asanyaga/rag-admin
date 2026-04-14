// frontend/src/hooks/useDataStoreRows.ts
import { useState, useEffect, useCallback } from 'react'
import * as dataStoresApi from '@/api/dataStores'
import type { DataStoreRow, CsvImportResponse } from '@/types/dataStore'

export interface UseDataStoreRowsReturn {
  rows: DataStoreRow[]
  total: number
  isLoading: boolean
  error: string | null
  page: number
  setPage: (page: number) => void
  pageSize: number
  fetchRows: () => Promise<void>
  insertRow: (data: Record<string, unknown>) => Promise<DataStoreRow>
  updateRow: (rowId: string, data: Record<string, unknown>) => Promise<DataStoreRow>
  deleteRow: (rowId: string) => Promise<void>
  importCsv: (file: File, columnMapping: Record<string, string>) => Promise<CsvImportResponse>
}

export function useDataStoreRows(
  projectId: string | null,
  storeId: string | null,
  pageSize = 50
): UseDataStoreRowsReturn {
  const [rows, setRows] = useState<DataStoreRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchRows = useCallback(async () => {
    if (!projectId || !storeId) {
      setRows([])
      setTotal(0)
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await dataStoresApi.listRows(projectId, storeId, pageSize, page * pageSize)
      setRows(data.rows)
      setTotal(data.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch rows')
    } finally {
      setIsLoading(false)
    }
  }, [projectId, storeId, page, pageSize])

  const insertRow = useCallback(
    async (data: Record<string, unknown>): Promise<DataStoreRow> => {
      if (!projectId || !storeId) throw new Error('No store selected')
      try {
        const row = await dataStoresApi.insertRow(projectId, storeId, data)
        await fetchRows()
        return row
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to insert row'
        setError(msg)
        throw err
      }
    },
    [projectId, storeId, fetchRows]
  )

  const updateRow = useCallback(
    async (rowId: string, data: Record<string, unknown>): Promise<DataStoreRow> => {
      if (!projectId || !storeId) throw new Error('No store selected')
      try {
        const updated = await dataStoresApi.updateRow(projectId, storeId, rowId, data)
        setRows((prev) => prev.map((r) => (r.id === rowId ? updated : r)))
        return updated
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to update row'
        setError(msg)
        throw err
      }
    },
    [projectId, storeId]
  )

  const deleteRow = useCallback(
    async (rowId: string): Promise<void> => {
      if (!projectId || !storeId) throw new Error('No store selected')
      try {
        await dataStoresApi.deleteRow(projectId, storeId, rowId)
        await fetchRows()
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to delete row'
        setError(msg)
        throw err
      }
    },
    [projectId, storeId, fetchRows]
  )

  const importCsv = useCallback(
    async (file: File, columnMapping: Record<string, string>): Promise<CsvImportResponse> => {
      if (!projectId || !storeId) throw new Error('No store selected')
      try {
        const result = await dataStoresApi.importCsv(projectId, storeId, file, columnMapping)
        await fetchRows()
        return result
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to import CSV'
        setError(msg)
        throw err
      }
    },
    [projectId, storeId, fetchRows]
  )

  useEffect(() => {
    if (projectId && storeId) {
      fetchRows()
    }
  }, [projectId, storeId, fetchRows])

  return {
    rows,
    total,
    isLoading,
    error,
    page,
    setPage,
    pageSize,
    fetchRows,
    insertRow,
    updateRow,
    deleteRow,
    importCsv,
  }
}
