import { useState, useCallback, useEffect, useRef } from 'react'
import type { AgentReceipt, SubmitReviewRequest } from '@/types/agent'
import * as agentApi from '@/api/agent'

interface UseAgentReceiptReturn {
  receipt: AgentReceipt | null
  isLoading: boolean
  isSubmitting: boolean
  error: string | null
  fetchReceipt: () => Promise<void>
  submitReview: (request: SubmitReviewRequest) => Promise<AgentReceipt>
}

const POLLING_INTERVAL = 3000
const POLLING_TIMEOUT = 10 * 60 * 1000

export function useAgentReceipt(
  receiptId: string | null
): UseAgentReceiptReturn {
  const [receipt, setReceipt] = useState<AgentReceipt | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
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

  const fetchReceipt = useCallback(async () => {
    if (!receiptId) {
      setReceipt(null)
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      const data = await agentApi.getReceipt(receiptId)
      setReceipt(data)

      const isActive =
        data.status === 'pending' || data.status === 'extracting'
      if (isActive && !pollingRef.current) {
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
            const updated = await agentApi.getReceipt(receiptId)
            setReceipt(updated)
            const stillActive =
              updated.status === 'pending' || updated.status === 'extracting'
            if (!stillActive) {
              stopPolling()
            }
          } catch {
            stopPolling()
          }
        }, POLLING_INTERVAL)
      } else if (!isActive) {
        stopPolling()
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch receipt'
      )
    } finally {
      setIsLoading(false)
    }
  }, [receiptId, stopPolling])

  const submitReview = useCallback(
    async (request: SubmitReviewRequest): Promise<AgentReceipt> => {
      if (!receiptId) throw new Error('No receipt selected')
      setIsSubmitting(true)
      setError(null)
      try {
        const result = await agentApi.submitReview(receiptId, request)
        setReceipt(result)
        stopPolling()
        return result
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to submit review'
        setError(message)
        throw err
      } finally {
        setIsSubmitting(false)
      }
    },
    [receiptId, stopPolling]
  )

  useEffect(() => {
    if (receiptId) {
      fetchReceipt()
    } else {
      setReceipt(null)
    }
  }, [receiptId, fetchReceipt])

  useEffect(() => {
    return () => {
      stopPolling()
    }
  }, [stopPolling])

  return {
    receipt,
    isLoading,
    isSubmitting,
    error,
    fetchReceipt,
    submitReview,
  }
}
