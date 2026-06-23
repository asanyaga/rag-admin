import { useState, useEffect, useCallback } from 'react'
import { SourceDocument } from '@/types/sourceDocument'
import * as sourceDocumentsApi from '@/api/sourceDocuments'

interface UseSourceDocumentsReturn {
  sourceDocuments: SourceDocument[]
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
}

export function useSourceDocuments(): UseSourceDocumentsReturn {
  const [sourceDocuments, setSourceDocuments] = useState<SourceDocument[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await sourceDocumentsApi.listSourceDocuments()
      setSourceDocuments(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load source documents')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { sourceDocuments, isLoading, error, refresh: fetch }
}
