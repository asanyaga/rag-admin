import { useState, useCallback, useEffect, useRef } from 'react'
import {
  Document,
  DocumentListItem,
  DocumentUpload,
  DocumentUpdate,
  DocumentStatus,
} from '@/types/document'
import * as documentsApi from '@/api/documents'
import { traceAsync } from '@/lib/instrumentation'

interface UseDocumentsReturn {
  documents: DocumentListItem[]
  isLoading: boolean
  error: string | null
  uploadDocument: (data: DocumentUpload) => Promise<Document>
  fetchDocuments: () => Promise<void>
  updateDocument: (id: string, data: DocumentUpdate) => Promise<Document>
  deleteDocument: (id: string) => Promise<void>
  downloadDocument: (id: string, filename: string) => Promise<void>
}

const POLLING_INTERVAL = 2000 // Poll every 2 seconds
const POLLING_TIMEOUT = 5 * 60 * 1000 // Stop polling after 5 minutes

export function useDocuments(
  projectId: string | null,
  statusFilter?: DocumentStatus
): UseDocumentsReturn {
  const [documents, setDocuments] = useState<DocumentListItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Track polling intervals and start times for processing documents
  const pollingIntervals = useRef<Map<string, NodeJS.Timeout>>(new Map())
  const pollingStartTimes = useRef<Map<string, number>>(new Map())

  // Use refs to avoid circular dependencies between callbacks
  const stopPollingRef = useRef<(documentId: string) => void>()
  const startPollingRef = useRef<(documentId: string) => void>()

  const stopPolling = useCallback((documentId: string) => {
    const interval = pollingIntervals.current.get(documentId)
    if (interval) {
      clearInterval(interval)
      pollingIntervals.current.delete(documentId)
      pollingStartTimes.current.delete(documentId)
    }
  }, [])

  stopPollingRef.current = stopPolling

  const startPolling = useCallback((documentId: string) => {
    // Don't start if already polling
    if (pollingIntervals.current.has(documentId)) return

    // Track start time for timeout
    pollingStartTimes.current.set(documentId, Date.now())

    const interval = setInterval(async () => {
      try {
        // Check if polling has timed out
        const startTime = pollingStartTimes.current.get(documentId)
        if (startTime && Date.now() - startTime > POLLING_TIMEOUT) {
          console.warn(`Polling timeout for document ${documentId}`)
          setDocuments((prev) =>
            prev.map((doc) =>
              doc.id === documentId
                ? {
                    ...doc,
                    status: 'failed' as const,
                    statusMessage: 'Processing timeout - please try re-uploading',
                  }
                : doc
            )
          )
          stopPollingRef.current?.(documentId)
          return
        }

        const updated = await documentsApi.getDocument(documentId)

        // Update document in list
        setDocuments((prev) =>
          prev.map((doc) =>
            doc.id === documentId
              ? {
                  ...doc,
                  status: updated.status,
                  statusMessage: updated.statusMessage,
                  updatedAt: updated.updatedAt,
                }
              : doc
          )
        )

        // Stop polling if no longer processing
        if (updated.status !== 'processing') {
          stopPollingRef.current?.(documentId)
        }
      } catch (err) {
        console.error(`Error polling document ${documentId}:`, err)
        // Stop polling on error (document might have been deleted)
        stopPollingRef.current?.(documentId)
      }
    }, POLLING_INTERVAL)

    pollingIntervals.current.set(documentId, interval)
  }, [])

  startPollingRef.current = startPolling

  const fetchDocuments = useCallback(async () => {
    if (!projectId) {
      setDocuments([])
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      const data = await documentsApi.listDocuments({
        projectId,
        status: statusFilter,
      })
      setDocuments(data)

      // Start polling for processing documents
      data.forEach((doc) => {
        if (doc.status === 'processing' && !pollingIntervals.current.has(doc.id)) {
          startPollingRef.current?.(doc.id)
        } else if (doc.status !== 'processing' && pollingIntervals.current.has(doc.id)) {
          stopPollingRef.current?.(doc.id)
        }
      })
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to fetch documents'
      setError(errorMessage)
      console.error('Error fetching documents:', err)
    } finally {
      setIsLoading(false)
    }
  }, [projectId, statusFilter])

  const uploadDocument = useCallback(
    async (data: DocumentUpload): Promise<Document> => {
      return traceAsync('documents.upload', async (span) => {
        try {
          span.setAttribute('document.title', data.title)
          span.setAttribute('document.project_id', data.projectId)
          span.setAttribute('document.file_size', data.file.size)
          span.setAttribute('document.file_type', data.file.type)

          const newDocument = await documentsApi.uploadDocument(data)
          span.setAttribute('document.id', newDocument.id)

          // Add to documents list
          setDocuments((prev) => [
            {
              id: newDocument.id,
              projectId: newDocument.projectId,
              sourceType: newDocument.sourceType,
              title: newDocument.title,
              description: newDocument.description,
              status: newDocument.status,
              statusMessage: newDocument.statusMessage,
              createdAt: newDocument.createdAt,
              updatedAt: newDocument.updatedAt,
            },
            ...prev,
          ])

          // Start polling if processing
          if (newDocument.status === 'processing') {
            startPollingRef.current?.(newDocument.id)
          }

          return newDocument
        } catch (err) {
          const errorMessage =
            err instanceof Error ? err.message : 'Failed to upload document'
          setError(errorMessage)
          throw err
        }
      })
    },
    []
  )

  const updateDocument = useCallback(
    async (id: string, data: DocumentUpdate): Promise<Document> => {
      return traceAsync('documents.update', async (span) => {
        try {
          span.setAttribute('document.id', id)
          if (data.title) span.setAttribute('document.title', data.title)

          const updatedDocument = await documentsApi.updateDocument(id, data)

          // Update in list
          setDocuments((prev) =>
            prev.map((doc) =>
              doc.id === id
                ? {
                    ...doc,
                    title: updatedDocument.title,
                    description: updatedDocument.description,
                    updatedAt: updatedDocument.updatedAt,
                  }
                : doc
            )
          )

          return updatedDocument
        } catch (err) {
          const errorMessage =
            err instanceof Error ? err.message : 'Failed to update document'
          setError(errorMessage)
          throw err
        }
      })
    },
    []
  )

  const deleteDocument = useCallback(
    async (id: string): Promise<void> => {
      return traceAsync('documents.delete', async (span) => {
        try {
          span.setAttribute('document.id', id)

          // Stop polling if active
          stopPollingRef.current?.(id)

          await documentsApi.deleteDocument(id)

          // Remove from list
          setDocuments((prev) => prev.filter((doc) => doc.id !== id))
        } catch (err) {
          const errorMessage =
            err instanceof Error ? err.message : 'Failed to delete document'
          setError(errorMessage)
          throw err
        }
      })
    },
    []
  )

  const downloadDocument = useCallback(
    async (id: string, filename: string): Promise<void> => {
      return traceAsync('documents.download', async (span) => {
        try {
          span.setAttribute('document.id', id)

          const blob = await documentsApi.downloadDocument(id)

          // Create download link
          const url = window.URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = filename
          document.body.appendChild(a)
          a.click()
          window.URL.revokeObjectURL(url)
          document.body.removeChild(a)
        } catch (err) {
          const errorMessage =
            err instanceof Error ? err.message : 'Failed to download document'
          setError(errorMessage)
          throw err
        }
      })
    },
    []
  )

  // Auto-fetch when projectId changes
  useEffect(() => {
    if (projectId) {
      fetchDocuments()
    }
  }, [projectId, fetchDocuments])

  // Cleanup polling intervals on unmount
  useEffect(() => {
    const intervals = pollingIntervals.current
    const startTimes = pollingStartTimes.current
    return () => {
      intervals.forEach((interval) => clearInterval(interval))
      intervals.clear()
      startTimes.clear()
    }
  }, [])

  return {
    documents,
    isLoading,
    error,
    uploadDocument,
    fetchDocuments,
    updateDocument,
    deleteDocument,
    downloadDocument,
  }
}
