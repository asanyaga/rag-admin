import { useCallback, useRef, useState } from 'react'
import { probeDocument } from '@/api/probeReport'
import type { ProbeConfig, ProbeReport } from '@/types/probeReport'

export function useProbe() {
  const [report, setReport] = useState<ProbeReport | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Identifies the most recent run so a slow, superseded probe cannot
  // overwrite the results of the probe the user is actually waiting on.
  const runIdRef = useRef(0)

  const run = useCallback(async (documentId: string, config: ProbeConfig | null = null) => {
    const runId = ++runIdRef.current
    setReport(null)
    setError(null)
    setIsLoading(true)
    try {
      const next = await probeDocument(documentId, config)
      if (runIdRef.current !== runId) return
      setReport(next)
    } catch (e) {
      if (runIdRef.current !== runId) return
      setError(e instanceof Error ? e.message : 'Probe failed')
    } finally {
      if (runIdRef.current === runId) setIsLoading(false)
    }
  }, [])

  return { report, isLoading, error, run }
}
