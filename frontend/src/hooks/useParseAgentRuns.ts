import { useState, useCallback, useEffect } from 'react'
import * as parseAgentApi from '@/api/parseAgent'
import type { ParseAgentRunSummary } from '@/types/parseAgent'

interface UseParseAgentRunsReturn {
  runs: ParseAgentRunSummary[]
  isLoading: boolean
  isStarting: boolean
  error: string | null
  refetch: () => Promise<void>
  startRun: (file: File, parserType?: string) => Promise<string>
}

export function useParseAgentRuns(
  projectId: string | null
): UseParseAgentRunsReturn {
  const [runs, setRuns] = useState<ParseAgentRunSummary[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStarting, setIsStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    if (!projectId) {
      setRuns([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      setRuns(await parseAgentApi.listParseAgentRuns(projectId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch runs')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const startRun = useCallback(
    async (file: File, parserType?: string): Promise<string> => {
      if (!projectId) throw new Error('No project selected')
      setIsStarting(true)
      setError(null)
      try {
        const { runId } = await parseAgentApi.startParseAgentRun({
          projectId,
          file,
          parserType,
        })
        await refetch()
        return runId
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to start run')
        throw err
      } finally {
        setIsStarting(false)
      }
    },
    [projectId, refetch]
  )

  useEffect(() => {
    refetch()
  }, [refetch])

  return { runs, isLoading, isStarting, error, refetch, startRun }
}
