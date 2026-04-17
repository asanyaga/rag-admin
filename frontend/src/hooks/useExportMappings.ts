// frontend/src/hooks/useExportMappings.ts
import { useState, useCallback, useEffect } from 'react'
import type { ExportMapping, ExportMappingCreate, ExportMappingUpdate } from '@/types/exportMapping'
import * as exportMappingsApi from '@/api/exportMappings'

interface UseExportMappingsReturn {
  mappings: ExportMapping[]
  isLoading: boolean
  error: string | null
  create: (data: ExportMappingCreate) => Promise<ExportMapping>
  update: (mappingId: string, data: ExportMappingUpdate) => Promise<ExportMapping>
  remove: (mappingId: string) => Promise<void>
}

export function useExportMappings(
  projectId: string | null,
  dataStoreId: string | null
): UseExportMappingsReturn {
  const [mappings, setMappings] = useState<ExportMapping[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchMappings = useCallback(async () => {
    if (!projectId || !dataStoreId) {
      setMappings([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const result = await exportMappingsApi.listExportMappings(projectId, dataStoreId)
      setMappings(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch mappings')
    } finally {
      setIsLoading(false)
    }
  }, [projectId, dataStoreId])

  const create = useCallback(
    async (data: ExportMappingCreate): Promise<ExportMapping> => {
      if (!projectId) throw new Error('No project selected')
      const mapping = await exportMappingsApi.createExportMapping(projectId, data)
      await fetchMappings()
      return mapping
    },
    [projectId, fetchMappings]
  )

  const update = useCallback(
    async (mappingId: string, data: ExportMappingUpdate): Promise<ExportMapping> => {
      if (!projectId) throw new Error('No project selected')
      const mapping = await exportMappingsApi.updateExportMapping(projectId, mappingId, data)
      await fetchMappings()
      return mapping
    },
    [projectId, fetchMappings]
  )

  const remove = useCallback(
    async (mappingId: string): Promise<void> => {
      if (!projectId) throw new Error('No project selected')
      await exportMappingsApi.deleteExportMapping(projectId, mappingId)
      await fetchMappings()
    },
    [projectId, fetchMappings]
  )

  useEffect(() => {
    if (projectId && dataStoreId) {
      fetchMappings()
    } else {
      setMappings([])
    }
  }, [projectId, dataStoreId, fetchMappings])

  return { mappings, isLoading, error, create, update, remove }
}
