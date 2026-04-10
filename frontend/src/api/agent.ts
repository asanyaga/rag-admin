import apiClient from './client'
import type {
  AgentReceipt,
  AgentReceiptListItem,
  StartProcessingRequest,
  SubmitReviewRequest,
} from '@/types/agent'

export async function startProcessing(
  projectId: string,
  data: StartProcessingRequest
): Promise<AgentReceipt> {
  const response = await apiClient.post<AgentReceipt>(
    `/agent/projects/${projectId}/receipts`,
    data
  )
  return response.data
}

export async function listReceipts(
  projectId: string
): Promise<AgentReceiptListItem[]> {
  const response = await apiClient.get<AgentReceiptListItem[]>(
    `/agent/projects/${projectId}/receipts`
  )
  return response.data
}

export async function getReceipt(
  receiptId: string
): Promise<AgentReceipt> {
  const response = await apiClient.get<AgentReceipt>(
    `/agent/receipts/${receiptId}`
  )
  return response.data
}

export async function submitReview(
  receiptId: string,
  data: SubmitReviewRequest
): Promise<AgentReceipt> {
  const response = await apiClient.post<AgentReceipt>(
    `/agent/receipts/${receiptId}/review`,
    data
  )
  return response.data
}
