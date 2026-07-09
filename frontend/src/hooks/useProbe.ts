import { useCallback, useState } from 'react'
import { probeDocument } from '@/api/probeReport'
import type { ProbeConfig, ProbeReport } from '@/types/probeReport'

export function useProbe() {
  const [report, setReport] = useState<ProbeReport | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async (documentId: string, config: ProbeConfig | null = null) => {
    setIsLoading(true)
    setError(null)
    try {
      setReport(await probeDocument(documentId, config))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Probe failed')
    } finally {
      setIsLoading(false)
    }
  }, [])

  return { report, isLoading, error, run }
}
