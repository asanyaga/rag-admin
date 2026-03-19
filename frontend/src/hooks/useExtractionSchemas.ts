import { useState, useCallback, useEffect } from 'react'
import type {
  ExtractionSchema,
  ExtractionSchemaCreate,
  ExtractionSchemaUpdate,
} from '@/types/extraction'
import * as extractionApi from '@/api/extraction'

interface UseExtractionSchemasReturn {
  schemas: ExtractionSchema[]
  isLoading: boolean
  error: string | null
  fetchSchemas: () => Promise<void>
  createSchema: (data: ExtractionSchemaCreate) => Promise<ExtractionSchema>
  updateSchema: (
    schemaId: string,
    data: ExtractionSchemaUpdate
  ) => Promise<ExtractionSchema>
  deleteSchema: (schemaId: string) => Promise<void>
}

export function useExtractionSchemas(
  projectId: string | null
): UseExtractionSchemasReturn {
  const [schemas, setSchemas] = useState<ExtractionSchema[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchSchemas = useCallback(async () => {
    if (!projectId) {
      setSchemas([])
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      const result = await extractionApi.listExtractionSchemas(projectId)
      setSchemas(result)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch extraction schemas'
      )
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createSchema = useCallback(
    async (data: ExtractionSchemaCreate): Promise<ExtractionSchema> => {
      if (!projectId) throw new Error('No project selected')
      const schema = await extractionApi.createExtractionSchema(projectId, data)
      await fetchSchemas()
      return schema
    },
    [projectId, fetchSchemas]
  )

  const updateSchema = useCallback(
    async (
      schemaId: string,
      data: ExtractionSchemaUpdate
    ): Promise<ExtractionSchema> => {
      const schema = await extractionApi.updateExtractionSchema(schemaId, data)
      await fetchSchemas()
      return schema
    },
    [fetchSchemas]
  )

  const deleteSchema = useCallback(
    async (schemaId: string): Promise<void> => {
      await extractionApi.deleteExtractionSchema(schemaId)
      await fetchSchemas()
    },
    [fetchSchemas]
  )

  useEffect(() => {
    if (projectId) {
      fetchSchemas()
    } else {
      setSchemas([])
    }
  }, [projectId, fetchSchemas])

  return {
    schemas,
    isLoading,
    error,
    fetchSchemas,
    createSchema,
    updateSchema,
    deleteSchema,
  }
}
