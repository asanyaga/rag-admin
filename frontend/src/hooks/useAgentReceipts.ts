import { useState, useCallback, useEffect, useRef } from 'react'
import type {
  AgentReceipt,
  AgentReceiptListItem,
  StartProcessingRequest,
} from '@/types/agent'
import * as agentApi from '@/api/agent'

interface UseAgentReceiptsReturn {
  receipts: AgentReceiptListItem[]
  isLoading: boolean
  isProcessing: boolean
  error: string | null
  fetchReceipts: () => Promise<void>
  startProcessing: (request: StartProcessingRequest) => Promise<AgentReceipt>
}

const POLLING_INTERVAL = 3000
const POLLING_TIMEOUT = 10 * 60 * 1000

export function useAgentReceipts(
  projectId: string | null
): UseAgentReceiptsReturn {
  const [receipts, setReceipts] = useState<AgentReceiptListItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<NodeJS.Timeout | null>(null)
  const pollingStartRef = useRef<number | null>(null)

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
    pollingStartRef.current = null
  }, [])

  const fetchReceipts = useCallback(async () => {
    if (!projectId) {
      setReceipts([])
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      const data = await agentApi.listReceipts(projectId)
      setReceipts(data)

      const hasActive = data.some(
        (r) => r.status === 'pending' || r.status === 'extracting'
      )
      if (hasActive && !pollingRef.current) {
        pollingStartRef.current = Date.now()
        pollingRef.current = setInterval(async () => {
          if (
            pollingStartRef.current &&
            Date.now() - pollingStartRef.current > POLLING_TIMEOUT
          ) {
            stopPolling()
            return
          }
          try {
            const updated = await agentApi.listReceipts(projectId)
            setReceipts(updated)
            const stillActive = updated.some(
              (r) => r.status === 'pending' || r.status === 'extracting'
            )
            if (!stillActive) {
              stopPolling()
            }
          } catch {
            stopPolling()
          }
        }, POLLING_INTERVAL)
      } else if (!hasActive) {
        stopPolling()
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch receipts'
      )
    } finally {
      setIsLoading(false)
    }
  }, [projectId, stopPolling])

  const startProcessing = useCallback(
    async (request: StartProcessingRequest): Promise<AgentReceipt> => {
      if (!projectId) throw new Error('No project selected')
      setIsProcessing(true)
      setError(null)
      try {
        const result = await agentApi.startProcessing(projectId, request)
        await fetchReceipts()
        return result
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to start processing'
        setError(message)
        throw err
      } finally {
        setIsProcessing(false)
      }
    },
    [projectId, fetchReceipts]
  )

  useEffect(() => {
    if (projectId) {
      fetchReceipts()
    } else {
      setReceipts([])
    }
  }, [projectId, fetchReceipts])

  useEffect(() => {
    return () => {
      stopPolling()
    }
  }, [stopPolling])

  return {
    receipts,
    isLoading,
    isProcessing,
    error,
    fetchReceipts,
    startProcessing,
  }
}
