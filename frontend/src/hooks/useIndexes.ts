/**
 * Hook for managing indexes
 */
import { useState, useCallback, useEffect, useRef } from 'react'
import {
  Index,
  IndexListItem,
  IndexCreate,
  IndexUpdate,
  IndexProcessingStatus,
  ChunkPreviewRequest,
  ChunkPreviewResponse,
  ChunkListResponse,
  Chunk,
} from '@/types/index'
import * as indexesApi from '@/api/indexes'

const POLLING_INTERVAL = 2000 // Poll every 2 seconds
const POLLING_TIMEOUT = 10 * 60 * 1000 // Stop polling after 10 minutes

interface UseIndexesReturn {
  indexes: IndexListItem[]
  isLoading: boolean
  error: string | null
  fetchIndexes: () => Promise<void>
  createIndex: (data: IndexCreate) => Promise<Index>
  updateIndex: (indexId: string, data: IndexUpdate) => Promise<Index>
  deleteIndex: (indexId: string) => Promise<void>
  processIndex: (indexId: string) => Promise<Index>
  retryIndex: (indexId: string) => Promise<Index>
  getProcessingStatus: (indexId: string) => Promise<IndexProcessingStatus>
  previewChunks: (data: ChunkPreviewRequest) => Promise<ChunkPreviewResponse>
}

export function useIndexes(projectId: string | null): UseIndexesReturn {
  const [indexes, setIndexes] = useState<IndexListItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<NodeJS.Timeout | null>(null)
  const pollingStartRef = useRef<number | null>(null)

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
      }
    }
  }, [])

  const fetchIndexes = useCallback(async () => {
    if (!projectId) {
      setIndexes([])
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      const data = await indexesApi.listIndexes(projectId)
      setIndexes(data)

      // Check if any indexes are processing and start polling
      const hasProcessing = data.some((idx) => idx.status === 'processing')
      if (hasProcessing && !pollingRef.current) {
        pollingStartRef.current = Date.now()
        pollingRef.current = setInterval(async () => {
          // Check timeout
          if (
            pollingStartRef.current &&
            Date.now() - pollingStartRef.current > POLLING_TIMEOUT
          ) {
            if (pollingRef.current) {
              clearInterval(pollingRef.current)
              pollingRef.current = null
            }
            return
          }

          try {
            const refreshedData = await indexesApi.listIndexes(projectId)
            setIndexes(refreshedData)

            // Stop polling if no more processing
            const stillProcessing = refreshedData.some(
              (idx) => idx.status === 'processing'
            )
            if (!stillProcessing && pollingRef.current) {
              clearInterval(pollingRef.current)
              pollingRef.current = null
              pollingStartRef.current = null
            }
          } catch {
            // Ignore polling errors
          }
        }, POLLING_INTERVAL)
      } else if (!hasProcessing && pollingRef.current) {
        clearInterval(pollingRef.current)
        pollingRef.current = null
        pollingStartRef.current = null
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to fetch indexes'
      setError(errorMessage)
      console.error('Error fetching indexes:', err)
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createIndex = useCallback(
    async (data: IndexCreate): Promise<Index> => {
      if (!projectId) throw new Error('No project selected')

      try {
        const newIndex = await indexesApi.createIndex(projectId, data)

        // Add to list
        setIndexes((prev) => [
          {
            id: newIndex.id,
            projectId: newIndex.projectId,
            name: newIndex.name,
            description: newIndex.description,
            status: newIndex.status,
            documentCount: newIndex.documentCount,
            chunkCount: newIndex.chunkCount,
            embeddingModel: newIndex.config.embeddingModel,
            chunkingStrategy: newIndex.config.chunkingStrategy,
            createdAt: newIndex.createdAt,
          },
          ...prev,
        ])

        // Start polling if processing
        if (newIndex.status === 'processing') {
          fetchIndexes()
        }

        return newIndex
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to create index'
        setError(errorMessage)
        throw err
      }
    },
    [projectId, fetchIndexes]
  )

  const updateIndex = useCallback(
    async (indexId: string, data: IndexUpdate): Promise<Index> => {
      if (!projectId) throw new Error('No project selected')

      try {
        const updatedIndex = await indexesApi.updateIndex(
          projectId,
          indexId,
          data
        )

        setIndexes((prev) =>
          prev.map((idx) =>
            idx.id === indexId
              ? {
                  ...idx,
                  name: updatedIndex.name,
                  description: updatedIndex.description,
                }
              : idx
          )
        )

        return updatedIndex
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to update index'
        setError(errorMessage)
        throw err
      }
    },
    [projectId]
  )

  const deleteIndex = useCallback(
    async (indexId: string): Promise<void> => {
      if (!projectId) throw new Error('No project selected')

      try {
        await indexesApi.deleteIndex(projectId, indexId)
        setIndexes((prev) => prev.filter((idx) => idx.id !== indexId))
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to delete index'
        setError(errorMessage)
        throw err
      }
    },
    [projectId]
  )

  const processIndex = useCallback(
    async (indexId: string): Promise<Index> => {
      if (!projectId) throw new Error('No project selected')

      try {
        const index = await indexesApi.processIndex(projectId, indexId)

        setIndexes((prev) =>
          prev.map((idx) =>
            idx.id === indexId ? { ...idx, status: index.status } : idx
          )
        )

        // Start polling
        fetchIndexes()

        return index
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to start processing'
        setError(errorMessage)
        throw err
      }
    },
    [projectId, fetchIndexes]
  )

  const retryIndex = useCallback(
    async (indexId: string): Promise<Index> => {
      if (!projectId) throw new Error('No project selected')

      try {
        const index = await indexesApi.retryIndex(projectId, indexId)

        setIndexes((prev) =>
          prev.map((idx) =>
            idx.id === indexId ? { ...idx, status: index.status } : idx
          )
        )

        // Start polling
        fetchIndexes()

        return index
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to retry processing'
        setError(errorMessage)
        throw err
      }
    },
    [projectId, fetchIndexes]
  )

  const getProcessingStatus = useCallback(
    async (indexId: string): Promise<IndexProcessingStatus> => {
      if (!projectId) throw new Error('No project selected')
      return indexesApi.getProcessingStatus(projectId, indexId)
    },
    [projectId]
  )

  const previewChunks = useCallback(
    async (data: ChunkPreviewRequest): Promise<ChunkPreviewResponse> => {
      if (!projectId) throw new Error('No project selected')
      return indexesApi.previewChunks(projectId, data)
    },
    [projectId]
  )

  // Auto-fetch when projectId changes
  useEffect(() => {
    if (projectId) {
      fetchIndexes()
    } else {
      setIndexes([])
    }
  }, [projectId, fetchIndexes])

  return {
    indexes,
    isLoading,
    error,
    fetchIndexes,
    createIndex,
    updateIndex,
    deleteIndex,
    processIndex,
    retryIndex,
    getProcessingStatus,
    previewChunks,
  }
}

// Hook for a single index with chunks
interface UseIndexDetailReturn {
  index: Index | null
  chunks: ChunkListResponse | null
  isLoading: boolean
  error: string | null
  fetchIndex: () => Promise<void>
  fetchChunks: (page?: number, search?: string) => Promise<void>
  getChunk: (chunkId: string) => Promise<Chunk>
}

export function useIndexDetail(
  projectId: string | null,
  indexId: string | null
): UseIndexDetailReturn {
  const [index, setIndex] = useState<Index | null>(null)
  const [chunks, setChunks] = useState<ChunkListResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchIndex = useCallback(async () => {
    if (!projectId || !indexId) return

    setIsLoading(true)
    setError(null)
    try {
      const data = await indexesApi.getIndex(projectId, indexId)
      setIndex(data)
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to fetch index'
      setError(errorMessage)
      console.error('Error fetching index:', err)
    } finally {
      setIsLoading(false)
    }
  }, [projectId, indexId])

  const fetchChunks = useCallback(
    async (page: number = 1, search?: string) => {
      if (!projectId || !indexId) return

      try {
        const data = await indexesApi.listChunks(
          projectId,
          indexId,
          page,
          20,
          search
        )
        setChunks(data)
      } catch (err) {
        console.error('Error fetching chunks:', err)
      }
    },
    [projectId, indexId]
  )

  const getChunk = useCallback(
    async (chunkId: string): Promise<Chunk> => {
      if (!projectId || !indexId) throw new Error('No index selected')
      return indexesApi.getChunk(projectId, indexId, chunkId)
    },
    [projectId, indexId]
  )

  useEffect(() => {
    if (projectId && indexId) {
      fetchIndex()
      fetchChunks()
    }
  }, [projectId, indexId, fetchIndex, fetchChunks])

  return {
    index,
    chunks,
    isLoading,
    error,
    fetchIndex,
    fetchChunks,
    getChunk,
  }
}
