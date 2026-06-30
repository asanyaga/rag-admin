import { useState, useCallback } from 'react'
import { probeDocument } from '@/api/probe'
import type { DocumentProfile } from '@/types/probe'

interface UseDocumentProbeReturn {
  profile: DocumentProfile | null
  isLoading: boolean
  error: string | null
  runProbe: () => Promise<void>
  reset: () => void
}

export function useDocumentProbe(documentId: string | null): UseDocumentProbeReturn {
  const [profile, setProfile] = useState<DocumentProfile | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runProbe = useCallback(async () => {
    if (!documentId) return
    setIsLoading(true)
    setError(null)
    try {
      const result = await probeDocument(documentId)
      setProfile(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Probe failed')
    } finally {
      setIsLoading(false)
    }
  }, [documentId])

  const reset = useCallback(() => {
    setProfile(null)
    setError(null)
  }, [])

  return { profile, isLoading, error, runProbe, reset }
}
